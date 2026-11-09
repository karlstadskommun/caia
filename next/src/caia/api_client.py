"""Shared API client + per-step model configuration. Routes through OpenRouter.

Model assignment: Sonnet 5.5 is the workhorse (from Sonnet 5, 2026-09-29); Opus 5.5 handles the three
judgment-critical steps (intake frames the analysis, evidens sets the numbers,
qa verifies them). Reasoning is adaptive, tuned per step with an effort level.
Every step names its effort explicitly: the default moved from high on Opus 5
to medium on Opus 5.5, so a step that left it out would quietly think less.

Thinking scheme (2026-09-10, replacing the per-step budget_tokens of 2026-06-03):
`thinking.budget_tokens` returns 400 on Sonnet 5, Opus 5 and Opus 4.8 — the whole
budget scheme is gone, not just deprecated. Adaptive thinking replaces it: the
model sizes its own reasoning and `output_config.effort` sets how hard it leans
in. Old budget -> effort, same mapping AIda uses: 1024 -> medium, >=3000 -> high.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

import anthropic

from .kommun import UNRENDERED
from .logsafe import describe, kind
from .mode import UPPFOLJNING

# One INFO line per model call (complete() below). web/app.py routes it to
# where Flask's own lines go, which on Vercel is the function log.
log = logging.getLogger(__name__)

# CAIA_OPENROUTER_REGION picks OpenRouter's entry point. "eu" keeps every request
# inside the EU for its whole path through OpenRouter (decrypted and served by
# providers in the EU only; needs OpenRouter's Business plan, otherwise 403).
# Empty means the global endpoint. An unknown value is a ConfigError, never a
# silent fallback: an operator who typed "EU " or "europe" expecting the EU must
# not end up on the global route without knowing it.
OPENROUTER_BASE_URLS = {
    "": "https://openrouter.ai/api",
    "eu": "https://eu.openrouter.ai/api",
    "us": "https://us.openrouter.ai/api",
}


def openrouter_base_url() -> str:
    region = os.environ.get("CAIA_OPENROUTER_REGION", "").strip().lower()
    if region not in OPENROUTER_BASE_URLS:
        raise ConfigError(
            f"CAIA_OPENROUTER_REGION={region!r} är inte giltig. "
            "Använd eu, us eller lämna tom.")
    return OPENROUTER_BASE_URLS[region]

SONNET = "anthropic/claude-sonnet-5.5"
OPUS = "anthropic/claude-opus-5.5"

DEFAULT_MODEL = SONNET  # capable fallback for any unconfigured step

EFFORT_MEDIUM = "medium"
EFFORT_HIGH = "high"

# Models that accept adaptive thinking + effort. Anything else degrades to no
# thinking rather than erroring, so an unlisted model still answers.
# Built from the constants above rather than spelling the ids out again, so a
# model swap cannot leave the gate pointing at the old id -- the failure mode
# that bit AIda, where the two lived in different files and had to be moved by
# hand together.
ADAPTIVE_MODELS = {SONNET, OPUS}


@dataclass(frozen=True)
class Price:
    """OpenRouter list price, USD per million tokens."""
    input: float
    output: float
    cache_read: float
    cache_write: float


# Keyed by the model constants, like ADAPTIVE_MODELS, so a model swap cannot
# leave the old id's price behind. A model with no row here is logged with
# usd=None, never priced as something else; tests/test_usage.py requires a row
# for every model in AGENT_MODELS. Read from https://openrouter.ai/api/v1/models
# 2026-10-13 (cache_write is the 5-minute write; CAIA sets no cache_control).
PRICES: dict[str, Price] = {
    SONNET: Price(input=2.0, output=10.0, cache_read=0.10, cache_write=2.50),
    OPUS:   Price(input=4.0, output=20.0, cache_read=0.20, cache_write=5.00),
}


def estimate_usd(model: str, input_tokens: int, output_tokens: int,
                 cache_read: int = 0, cache_write: int = 0) -> float | None:
    """List-price estimate of one call, or None for a model without a price.
    Thinking tokens are billed as output and are already in output_tokens."""
    p = PRICES.get(model)
    if p is None:
        return None
    return (input_tokens * p.input + output_tokens * p.output
            + cache_read * p.cache_read + cache_write * p.cache_write) / 1e6

# step -> (model, effort). effort None = thinking off.
AGENT_MODELS: dict[str, tuple[str, str | None]] = {
    "intake":         (OPUS,   EFFORT_MEDIUM),  # frames the whole analysis — worth Opus + light thinking
    "emap":           (SONNET, EFFORT_MEDIUM),  # classification vs fixed taxonomy
    "baslinje":       (SONNET, EFFORT_HIGH),    # sets baseline+BAU, feeds the calc
    "evidens":        (OPUS,   EFFORT_HIGH),    # sets assumptions+factors = the numbers (monolithic fallback)
    "evidens_part":   (OPUS,   EFFORT_HIGH),    # same judgment as evidens, one driver per call
    # The only call that sees every driver: catches double counting. Medium, not
    # high: on identical parts (lövblåsare, 2026-09-23) both levels found the
    # same contradictions and set the same corrected values, in 102 s vs 173 s.
    # The merge is the one call in the step that grows with every driver.
    "evidens_merge":  (OPUS,   EFFORT_MEDIUM),
    # High, not medium: the extraction is a reading task, and at medium Sonnet
    # 5.5 sometimes answers after a short look. On one approved history
    # (reference package återbruk, 2026-10-13) medium read the assumptions
    # right in 4 of 8 extractions and wrong in 4: a relative factor for the
    # avoided amount became a ΔEF on everything still bought, 250 ton in 2030
    # instead of 137, with min above max. The wrong ones were the quick ones,
    # 15-18 s against 31-39 s. High gave 137 ton in 8 of 8, in 54-82 s. On
    # tjänstebilar medium gave -50, 8, 11 and 111 ton on one history, high the
    # same reading every time. What high needed from the prompt to read right
    # is in agents/kalkyl_extract.py (_BASE, _FACTORS). Both modes since
    # 2026-11-08: see EFFORT_UPPFOLJNING below.
    "kalkyl_extract": (SONNET, EFFORT_HIGH),
    "kalkyl":         (SONNET, EFFORT_HIGH),    # legacy LLM-math fallback (rarely hit)
    "qa":             (OPUS,   EFFORT_HIGH),    # verification gate — reads a finished calc, less reasoning room than evidens which sets the numbers
    "rapport":        (SONNET, EFFORT_HIGH),    # synthesis + writing
}

# Follow-up mode, where a step runs at another effort than in the table above.
# Empty since 2026-11-08. kalkyl_extract read at medium there until then; on
# four approved follow-up analyses (omgång 5 of the driftsmedel packages, four
# extractions each) medium gave husbyggnad 107, 173 and 208 ton and one reply
# the engine could not use (the LLM kalkyl took over), anläggning 6.8 to 9.7;
# high gave the same reading in 16 of 16 (husbyggnad 207.5 to 208.8). High
# went in together with the factor rule in the follow-up prompt
# (agents/kalkyl_extract.py), which high needs: without it an approved
# Konsumtion_faktor 1.1 became 1.0 at both levels.
EFFORT_UPPFOLJNING: dict[str, str | None] = {}

# Headroom added on top of the caller's desired answer length, because adaptive
# thinking tokens count toward max_tokens. This is the reason the migration is
# not a one-line model swap: Sonnet 5 reasons by default and will happily spend
# the entire ceiling thinking, returning an empty answer with
# stop_reason="max_tokens". extract_text() turns that into a visible error rather
# than a clipped report, but the headroom is what stops it happening.
#
# Doubled for Opus 5.5 (2026-09-23), which reasons longer than Opus 5 at the
# same effort. Measured on evidens (lövblåsare package, max_output 8000):
# Opus 5 high spent 14.0k output tokens, Opus 5.5 high 21.9k and 5.5 medium
# 16.7k. The old 20k/14k ceilings clipped 5.5 at both levels. A higher ceiling
# only costs when the model actually uses it.
THINKING_HEADROOM = {EFFORT_MEDIUM: 12000, EFFORT_HIGH: 24000}

# Per-request wall-clock budget. Every step is a synchronous call with up to
# ~17k output tokens, and the SDK's default is ten minutes with two retries:
# a hung upstream would sit past the function limit (`maxDuration` in
# vercel.json), and the user would get a bare 504 with nothing in our logs. The
# budget must still fail inside the function's own lifetime, with room for
# Flask around the call. It was 240 s, set when the slowest step took 75 s; by
# 2026-09-23 evidens took 195-222 s on Opus 5 and 216 s on Opus 5.5 (at ~100
# output tokens/s), so 240 s had shrunk to a 10 % margin. 280 s under the
# function's 300 s leaves QA, the evidens merge and baslinje close to the
# edge: steps stay under the limit by being leaner, not by a longer limit.
# A longer limit must show as functionMaxDuration in Vercel's own logs;
# maxDuration under builds[].config was not applied when it was tried
# (DEPLOY.md).
#
# Retries are ours, not the SDK's. The SDK retries a timeout too, which here
# means a second full-budget call inside the same function: the platform kills it
# and the user gets a bare 504. complete() retries once, only on an answer
# that came back fast (429, 5xx, a dropped connection), and gives the retry
# what is left of the budget.
REQUEST_TIMEOUT_S = 280.0
RETRY_IF_FAILED_WITHIN_S = 60.0
RETRY_PAUSE_S = 2.0
_RETRYABLE = (anthropic.RateLimitError, anthropic.InternalServerError,
              anthropic.ServiceUnavailableError, anthropic.OverloadedError)


class ConfigError(RuntimeError):
    """The installation is missing a setting. Message is for the operator."""


# CAIA_ANTHROPIC_API_KEY sends every call straight to Anthropic instead of
# through OpenRouter. It exists for batch runs (tools/run_batch.py) on the API
# credits included in a Claude subscription (2026-10-21, the driftsmedel
# re-run); the web app never sets it. Named apart from ANTHROPIC_API_KEY on
# purpose: that variable takes over every Anthropic call on the machine it is
# set on. The direct route has no EU entry point, so CAIA_OPENROUTER_REGION
# does not apply to it.
DIRECT_MODEL_IDS = {
    SONNET: "claude-sonnet-5-5",
    OPUS: "claude-opus-5-5",
}


def direct_key() -> str:
    return os.environ.get("CAIA_ANTHROPIC_API_KEY", "").strip()


def wire_model(model: str) -> str:
    """The id to send. The tables above stay keyed by OpenRouter's ids, so
    prices and effort follow the model whichever route carries it. A model
    without a direct id is a ConfigError on the direct route, never sent under
    OpenRouter's name to an API that would refuse it mid-run."""
    if not direct_key():
        return model
    if model not in DIRECT_MODEL_IDS:
        raise ConfigError(f"{model} har inget id för Anthropics API (DIRECT_MODEL_IDS).")
    return DIRECT_MODEL_IDS[model]


def get_client() -> anthropic.Anthropic:
    """Anthropic client routed through OpenRouter, the one billing path for the
    web app, or straight to Anthropic when CAIA_ANTHROPIC_API_KEY is set.

    Model ids are OpenRouter's ('anthropic/claude-sonnet-5.5'); wire_model()
    translates them for the direct route."""
    key = direct_key()
    if key:
        return anthropic.Anthropic(
            api_key=key,
            timeout=REQUEST_TIMEOUT_S,
            max_retries=0,
        )
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise ConfigError("OPENROUTER_API_KEY saknas. CAIA går via OpenRouter.")
    return anthropic.Anthropic(
        api_key=openrouter_key,
        base_url=openrouter_base_url(),
        timeout=REQUEST_TIMEOUT_S,
        max_retries=0,
    )


def thinking_request(model: str, effort: str | None) -> dict:
    """Request kwargs for adaptive thinking at `effort`, or {} when thinking is
    off or the model can't do it.

    `output_config` rides in extra_body: it is an OpenRouter passthrough, not a
    typed field on the Anthropic SDK's create(). Same shape AIda uses, verified
    against Opus 4.8 on this route.
    """
    if not effort or model not in ADAPTIVE_MODELS:
        return {}
    return {
        "thinking": {"type": "adaptive"},
        "extra_body": {"output_config": {"effort": effort}},
    }


class ModelOutputError(RuntimeError):
    """The model returned nothing usable, or was cut off mid-answer."""


def extract_text(response) -> str:
    """Return the text block, skipping any thinking/redacted blocks.

    Raises rather than returning "". An empty or truncated answer used to
    propagate into the step history, where it surfaced either as an opaque
    failure two steps later or — worse — as a clipped report saved and shown
    as finished. A step that produced nothing has failed, and the pipeline
    already knows how to show a failed step.
    """
    stop_reason = getattr(response, "stop_reason", None)
    # All text blocks, in order. Taking the first one only dropped the rest of
    # an answer the model wrote in several blocks.
    text = "".join(block.text for block in response.content if block.type == "text")

    if stop_reason == "max_tokens":
        # Truncation is not partial success: downstream steps parse this as a
        # complete answer, and the report is what the user is shown.
        raise ModelOutputError(
            "Modellen slog i sitt tokentak och svaret klipptes av. "
            "Kör steget igen, eller höj max_output för steget."
        )
    if not text.strip():
        raise ModelOutputError(
            f"Modellen returnerade tom text (stop_reason={stop_reason!r})."
        )
    return text


def complete(step: str, system: str, messages: list[dict], max_output: int,
             mode: str | None = None, timeout_s: float | None = None) -> str:
    """Run one agent step with its configured model + reasoning effort.

    max_output is the desired answer length. Adaptive thinking tokens count
    toward max_tokens, so the step's headroom is added on top — without it the
    model can spend the whole ceiling reasoning and return nothing.

    mode matters only to a step listed in EFFORT_UPPFOLJNING; the others run
    the same in both modes and need not pass it.

    A system prompt that still holds a kommunprofil placeholder (@@ORT@@ etc.)
    is refused here: an agent that forgot to render its prompt would otherwise
    send the model a municipality called "@@ORT@@" and get a confident answer
    about it.

    timeout_s is the call's budget when it is the second model call of one
    request: what is left of REQUEST_TIMEOUT_S after the first (security
    review S29). None means the whole of it."""
    left = UNRENDERED.search(system)
    if left:
        raise RuntimeError(f"Steget {step} skickar en orenderad platshållare "
                           f"({left.group(0)}); prompten ska gå via kommun.render.")
    model, effort = AGENT_MODELS.get(step, (DEFAULT_MODEL, None))
    if mode == UPPFOLJNING:
        effort = EFFORT_UPPFOLJNING.get(step, effort)
    think = thinking_request(model, effort)
    headroom = THINKING_HEADROOM.get(effort, 0) if think else 0
    kwargs: dict = dict(
        model=wire_model(model),
        max_tokens=max_output + headroom,
        system=system,
        messages=messages,
    )
    kwargs.update(think)
    client = get_client()
    started = time.monotonic()
    try:
        response = _create(client, kwargs, timeout_s)
    except Exception as e:
        _report_usage(step, model, effort, mode, started, error=e)
        raise
    # Before extract_text: a call clipped at max_tokens raises there, and it
    # was billed in full.
    _report_usage(step, model, effort, mode, started, response=response)
    return extract_text(response)


# Called with every usage record, after the log line. tools/run_batch.py
# appends one here to write usage.jsonl per analysis. A listener that raises
# is logged and skipped; it never fails the model call.
UsageListener = Callable[[dict], None]
USAGE_LISTENERS: list[UsageListener] = []


def usage_record(step: str, model: str, effort: str | None, mode: str | None,
                 seconds: float, response=None, error: BaseException | None = None) -> dict:
    """One model call as a flat dict: the log line and what listeners get.
    Tokens and usd are None when the call failed or the answer had no usage."""
    usage = getattr(response, "usage", None)

    def tokens(name: str) -> int | None:
        if usage is None:
            return None
        try:
            return int(getattr(usage, name, 0) or 0)
        except (TypeError, ValueError):
            return None  # unreadable: the call still gets its line, unpriced

    rec = {
        "step": step, "model": model, "effort": effort, "mode": mode,
        "input": tokens("input_tokens"),
        "output": tokens("output_tokens"),
        "cache_read": tokens("cache_read_input_tokens"),
        "cache_write": tokens("cache_creation_input_tokens"),
        "seconds": round(seconds, 1),
        "stop_reason": getattr(response, "stop_reason", None),
        "usd": None,
    }
    counts = (rec["input"], rec["output"], rec["cache_read"], rec["cache_write"])
    if None not in counts:
        usd = estimate_usd(model, rec["input"], rec["output"],
                           rec["cache_read"], rec["cache_write"])
        rec["usd"] = None if usd is None else round(usd, 4)
    if error is not None:
        # The type and status, not the message: a provider's error body can
        # quote the request (security review S31).
        rec["error"] = kind(error)
    return rec


def _report_usage(step, model, effort, mode, started, response=None, error=None) -> None:
    """Log the call and hand it to the listeners. Never raises: metering must
    not fail an analysis that otherwise went through."""
    try:
        rec = usage_record(step, model, effort, mode, time.monotonic() - started,
                           response=response, error=error)
        log.info("model usage %s", json.dumps(rec, ensure_ascii=False))
        for listener in list(USAGE_LISTENERS):
            try:
                listener(rec)
            except Exception as e:
                log.warning("usage listener %r failed: %s", listener, describe(e))
    except Exception as e:
        try:
            log.warning("usage metering failed for step %s: %s", step, describe(e))
        except Exception:
            pass


def _create(client: anthropic.Anthropic, kwargs: dict, budget_s: float | None = None):
    budget = REQUEST_TIMEOUT_S if budget_s is None else budget_s
    started = time.monotonic()
    try:
        first = client if budget_s is None else client.with_options(timeout=budget)
        return first.messages.create(**kwargs)
    except anthropic.APITimeoutError:
        raise
    except (*_RETRYABLE, anthropic.APIConnectionError):
        elapsed = time.monotonic() - started
        # A retry that cannot start before the budget runs out is not one.
        if elapsed > RETRY_IF_FAILED_WITHIN_S or budget - elapsed <= RETRY_PAUSE_S:
            raise
    time.sleep(RETRY_PAUSE_S)
    # The callers leave at least 204 s (kalkyl's fallback) and retry only a
    # failure within the first 60 s, so a retry has over 140 s; the floor is
    # for a sleep that overran, where a timeout of 0 or less would mean none.
    left = max(1.0, budget - (time.monotonic() - started))
    return client.with_options(timeout=left).messages.create(**kwargs)
