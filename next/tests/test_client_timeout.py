"""Every agent call is synchronous and can produce up to ~17k output tokens.
The SDK default (600 s, two retries) could outlive the Vercel function limit,
so a hung upstream ended as a bare 504 with nothing in our logs. The client
must carry an explicit budget that fails inside the function's lifetime.
"""
from __future__ import annotations

import os
import sys

import anthropic
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia import api_client  # noqa: E402

import json  # noqa: E402

# Read from vercel.json, so raising or lowering the platform limit without
# moving the client budget with it turns this red.
VERCEL_MAX_DURATION_S = json.load(open(os.path.join(
    os.path.dirname(__file__), '..', 'vercel.json')))['builds'][0]['config']['maxDuration']


def test_client_has_an_explicit_timeout_inside_the_function_budget(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    client = api_client.get_client()
    assert client.timeout == api_client.REQUEST_TIMEOUT_S
    assert 0 < api_client.REQUEST_TIMEOUT_S < VERCEL_MAX_DURATION_S
    assert client.max_retries == 0  # complete() retries itself; see below


def test_budget_is_not_the_sdk_default(monkeypatch):
    # The SDK default is what shipped before; if it comes back, this is red.
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    default = anthropic.Anthropic(api_key='x')
    client = api_client.get_client()
    assert client.timeout != default.timeout
    assert client.max_retries < default.max_retries


# ---------- the retry policy ----------

try:  # the SDK's HTTP layer: httpx2 from anthropic 1.x, httpx before that
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx


class _Messages:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, BaseException):
            raise out
        return out


class _Client:
    def __init__(self, outcomes):
        self.messages = _Messages(outcomes)
        self.timeouts = []

    def with_options(self, timeout):
        self.timeouts.append(timeout)
        return self


def _status(cls, code):
    req = httpx.Request('POST', 'https://openrouter.ai/api/v1/messages')
    return cls('x', response=httpx.Response(code, request=req), body=None)


def _timeout():
    return anthropic.APITimeoutError(request=httpx.Request('POST', 'https://openrouter.ai'))


def test_a_timeout_is_not_retried(monkeypatch):
    monkeypatch.setattr(api_client.time, 'sleep', lambda s: None)
    client = _Client([_timeout(), 'never'])
    with pytest.raises(anthropic.APITimeoutError):
        api_client._create(client, {})
    assert len(client.messages.calls) == 1


def test_a_fast_429_is_retried_once_within_the_budget(monkeypatch):
    monkeypatch.setattr(api_client.time, 'sleep', lambda s: None)
    client = _Client([_status(anthropic.RateLimitError, 429), 'svar'])
    assert api_client._create(client, {}) == 'svar'
    assert len(client.messages.calls) == 2
    assert 0 < client.timeouts[0] <= api_client.REQUEST_TIMEOUT_S


def test_a_slow_failure_is_not_retried(monkeypatch):
    clock = iter([0.0, api_client.RETRY_IF_FAILED_WITHIN_S + 1])
    monkeypatch.setattr(api_client.time, 'monotonic', lambda: next(clock))
    client = _Client([_status(anthropic.InternalServerError, 500), 'never'])
    with pytest.raises(anthropic.InternalServerError):
        api_client._create(client, {})
    assert len(client.messages.calls) == 1


def test_a_bad_request_is_not_retried(monkeypatch):
    client = _Client([_status(anthropic.BadRequestError, 400), 'never'])
    with pytest.raises(anthropic.BadRequestError):
        api_client._create(client, {})
    assert len(client.messages.calls) == 1


def test_every_text_block_of_the_answer_is_kept():
    class Block:
        def __init__(self, type, text=''):
            self.type, self.text = type, text

    class Response:
        stop_reason = 'end_turn'
        content = [Block('thinking'), Block('text', 'Första delen. '), Block('text', 'Andra delen.')]

    assert api_client.extract_text(Response()) == 'Första delen. Andra delen.'
