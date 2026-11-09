"""Several Anthropic keys in turn for CAIA's batch runs, OpenRouter last.

A list of Anthropic API keys is tried in order, and OpenRouter takes the call
when they are all out, without anything checking the balance in advance.

The web app is the exception and never comes here: its one route is
OpenRouter's EU entry (DEPLOY.md, "Hur deployen fungerar"). This module lives
in tools/, is imported only by the batch tools (run_batch.py, replay_step.py),
and does something only when CAIA_ANTHROPIC_KEYS is set (comma-separated keys,
in the order to try them).

The rules:

- failure classes that hand the call on: credits (402, or 400 with credit
  words, the console's spend limit included), auth (401), permission (403),
  rate_limit (429), overloaded (529), server (5xx), connection, bad_request
  (400), rejected; the first three also close the key for ten minutes in this
  process (None is never, not 0);
- a read timeout is not handed on (the call's time is spent), a connect
  timeout is;
- one time budget per call, shared by the routes, and no route is tried with
  less than ten seconds of it left;
- the direct route gets no retry and a pinned base_url; OpenRouter keeps the
  one retry api_client._create gives it;
- the key never stands in a log line;
- every call's usage record gets "route": anthropic:1, anthropic:2 or
  openrouter, and a log line "LLM usage route=... model=... usd=...".

It works by wrapping api_client._create, the one function every model call in
CAIA goes through (api_client.complete). With CAIA_ANTHROPIC_API_KEY unset,
complete() builds the request with OpenRouter's model id and an OpenRouter
client; the wrapper tries the direct keys first with the Anthropic id
(api_client.DIRECT_MODEL_IDS) and hands the untouched request to the original
_create last.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time

import anthropic
from caia import api_client

log = logging.getLogger(__name__)

KEYS_VAR = "CAIA_ANTHROPIC_KEYS"
ROUTE_OPENROUTER = "openrouter"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DIRECT_CONNECT_TIMEOUT = 10.0
MIN_HANDOFF_BUDGET_S = 10.0
EXHAUSTED_FOR_S = 600.0
MARKS_EXHAUSTED = frozenset({"credits", "auth", "permission"})
_CREDIT_WORDS = re.compile(
    r"credit balance|spend limit|usage limits?|insufficient (?:credit|fund)|billing", re.I,
)
_KEY_FORM = re.compile(r"^[\x21-\x7e]+$")

_LOCK = threading.Lock()
_EXHAUSTED_AT: dict[str, float] = {}
_CLIENTS: dict[str, anthropic.Anthropic] = {}
_WARNED: set[str] = set()
_LOCAL = threading.local()


class ConfigError(RuntimeError):
    """The run's settings contradict each other. Message is for the operator."""


def direct_keys() -> list[str]:
    """The keys in CAIA_ANTHROPIC_KEYS, in order. A value that cannot go in an
    HTTP header is dropped with one warning that does not print it."""
    keys: list[str] = []
    for i, part in enumerate(os.environ.get("CAIA_ANTHROPIC_KEYS", "").split(","), start=1):
        key = part.strip()
        if not key:
            continue
        if not _KEY_FORM.match(key):
            with _LOCK:
                first = f"bad:{key}" not in _WARNED
                _WARNED.add(f"bad:{key}")
            if first:
                log.warning("%s: key %d has characters that cannot go in an HTTP header; skipping it",
                            KEYS_VAR, i)
            continue
        keys.append(key)
    return keys


def failover_kind(e: BaseException) -> str | None:
    """The class of a direct-route error the next route may get past, or None
    when handing on would not help (a read timeout, or not an API error)."""
    if isinstance(e, anthropic.APITimeoutError):
        return "connection" if type(e.__cause__).__name__ == "ConnectTimeout" else None
    if isinstance(e, anthropic.APIConnectionError):
        return "connection"
    if isinstance(e, anthropic.AuthenticationError):
        return "auth"
    if isinstance(e, anthropic.PermissionDeniedError):
        return "permission"
    if isinstance(e, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(e, anthropic.APIStatusError):
        status = e.status_code
        if status == 402 or (status == 400 and _CREDIT_WORDS.search(str(e))):
            return "credits"
        if status == 529:
            return "overloaded"
        if status >= 500:
            return "server"
        if status == 400:
            return "bad_request"
        return "rejected"
    return None


def _skipped(key: str, now: float) -> bool:
    with _LOCK:
        at = _EXHAUSTED_AT.get(key)
    return at is not None and now - at < EXHAUSTED_FOR_S


def _direct_client(key: str) -> anthropic.Anthropic:
    with _LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            client = _CLIENTS[key] = anthropic.Anthropic(
                api_key=key,
                base_url=ANTHROPIC_BASE_URL,
                timeout=anthropic.Timeout(api_client.REQUEST_TIMEOUT_S, connect=DIRECT_CONNECT_TIMEOUT),
                max_retries=0,
            )
        return client


def _short(e: BaseException, key: str | None) -> str:
    text = " ".join(str(e).split())
    if key:
        text = text.replace(key, "[key]")
    return text if len(text) <= 160 else text[:157] + "..."


def reset() -> None:
    """Forget closed keys, clients and warnings (tests)."""
    with _LOCK:
        _EXHAUSTED_AT.clear()
        _CLIENTS.clear()
        _WARNED.clear()


def routes_for(model: str, now: float | None = None) -> list[tuple[str, str | None, str]]:
    """(name, key or None, model id on the wire) per route, in order: every
    direct key that is not closed, then OpenRouter, always last."""
    now = time.monotonic() if now is None else now
    out: list[tuple[str, str | None, str]] = []
    keys = direct_keys()
    direct_id = api_client.DIRECT_MODEL_IDS.get(model)
    if keys and direct_id is None:
        with _LOCK:
            first = f"model:{model}" not in _WARNED
            _WARNED.add(f"model:{model}")
        if first:
            log.warning("No direct Anthropic id for %s (api_client.DIRECT_MODEL_IDS); "
                        "it goes to OpenRouter only", model)
    elif direct_id is not None:
        for i, key in enumerate(keys, start=1):
            if not _skipped(key, now):
                out.append((f"anthropic:{i}", key, direct_id))
    out.append((ROUTE_OPENROUTER, None, model))
    return out


def routed_create(original):
    """api_client._create with the direct keys in front of it."""

    def create(client, kwargs: dict, budget_s: float | None = None):
        budget = api_client.REQUEST_TIMEOUT_S if budget_s is None else budget_s
        deadline = time.monotonic() + budget
        routes = routes_for(kwargs["model"])
        for i, (name, key, wire) in enumerate(routes):
            _LOCAL.route = name
            left = max(0.0, deadline - time.monotonic())
            if key is None:
                return original(client, kwargs, left)
            try:
                direct = _direct_client(key).with_options(
                    timeout=anthropic.Timeout(left, connect=min(DIRECT_CONNECT_TIMEOUT, left)))
                return direct.messages.create(**{**kwargs, "model": wire})
            except Exception as e:
                kind = failover_kind(e)
                if kind is None:
                    raise
                if kind in MARKS_EXHAUSTED:
                    with _LOCK:
                        _EXHAUSTED_AT[key] = time.monotonic()
                after = deadline - time.monotonic()
                nxt = routes[i + 1][0]
                if after < MIN_HANDOFF_BUDGET_S:
                    log.warning("LLM route %s failed: %s (%s: %s); %.0fs of the budget left, not trying %s",
                                name, kind, type(e).__name__, _short(e, key), after, nxt)
                    raise
                log.warning("LLM route %s failed: %s (%s: %s); trying %s",
                            name, kind, type(e).__name__, _short(e, key), nxt)
        raise RuntimeError("no LLM route")  # unreachable: OpenRouter is always last

    create.credit_routes = True
    return create


def tag_route(rec: dict) -> None:
    """Usage listener, first in line: the route that served the call."""
    route = getattr(_LOCAL, "route", None)
    rec["route"] = route
    usd = rec.get("usd")
    log.info("LLM usage route=%s model=%s input=%s output=%s usd=%s",
             route, rec.get("model"), rec.get("input"), rec.get("output"),
             "n/a" if usd is None else f"{usd:.4f}")


def install() -> bool:
    """Put the direct keys in front of OpenRouter for this process. False when
    CAIA_ANTHROPIC_KEYS is unset (nothing changes). Refuses a run that also sets
    CAIA_ANTHROPIC_API_KEY, the single-key route without switching."""
    if not direct_keys():
        return False
    if api_client.direct_key():
        raise ConfigError("Sätt CAIA_ANTHROPIC_KEYS eller CAIA_ANTHROPIC_API_KEY, inte båda.")
    if not getattr(api_client._create, "credit_routes", False):
        api_client._create = routed_create(api_client._create)
    if tag_route not in api_client.USAGE_LISTENERS:
        api_client.USAGE_LISTENERS.insert(0, tag_route)
    return True
