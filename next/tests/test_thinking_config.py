"""Regressions for the 2026-09-10 Sonnet 5 migration.

`thinking.budget_tokens` returns 400 on Sonnet 5, Opus 5 and Opus 4.8, so the
per-step budget scheme had to go. Two things can silently break in a swap like
this and neither raises locally:

  1. A budget_tokens key surviving anywhere — every pipeline step 400s in prod
     while the app imports and the tests pass.
  2. max_tokens with no headroom — adaptive thinking counts toward the ceiling,
     so the model reasons up to the cap and returns an empty answer with
     stop_reason="max_tokens". That looks like a flaky model, not a config bug.

These tests call the real complete() against a stub client, so they see the
kwargs that would actually go over the wire.
"""

from __future__ import annotations

import re

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia import api_client  # noqa: E402


class _Block:
    def __init__(self, type_, text=''):
        self.type = type_
        self.text = text


class _Response:
    def __init__(self, blocks, stop_reason='end_turn'):
        self.content = blocks
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return _Response([_Block('thinking'), _Block('text', 'Svar.')])


class _Client:
    def __init__(self, sink):
        self.messages = _Messages(sink)


@pytest.fixture
def calls(monkeypatch):
    sink: list[dict] = []
    monkeypatch.setattr(api_client, 'get_client', lambda: _Client(sink))
    return sink


ALL_STEPS = sorted(api_client.AGENT_MODELS)


# --- budget_tokens must be gone everywhere ---------------------------------

@pytest.mark.parametrize('step', ALL_STEPS)
def test_no_step_sends_budget_tokens(step, calls):
    api_client.complete(step, 'sys', [{'role': 'user', 'content': 'x'}], 4000)
    thinking = calls[0].get('thinking', {})
    assert 'budget_tokens' not in thinking, (
        f'{step} would 400 on Sonnet 5 / Opus 4.8'
    )


@pytest.mark.parametrize('step', ALL_STEPS)
def test_configured_steps_use_adaptive_thinking(step, calls):
    api_client.complete(step, 'sys', [{'role': 'user', 'content': 'x'}], 4000)
    assert calls[0]['thinking'] == {'type': 'adaptive'}


@pytest.mark.parametrize('step', ALL_STEPS)
def test_effort_rides_in_extra_body(step, calls):
    _, effort = api_client.AGENT_MODELS[step]
    api_client.complete(step, 'sys', [{'role': 'user', 'content': 'x'}], 4000)
    assert calls[0]['extra_body'] == {'output_config': {'effort': effort}}


# --- headroom --------------------------------------------------------------

@pytest.mark.parametrize('step', ALL_STEPS)
def test_max_tokens_leaves_room_for_thinking(step, calls):
    """Without headroom the answer is whatever is left after reasoning, which on
    a hard question is nothing at all."""
    api_client.complete(step, 'sys', [{'role': 'user', 'content': 'x'}], 4000)
    assert calls[0]['max_tokens'] > 4000


def test_headroom_scales_with_effort(calls):
    api_client.complete('emap', 'sys', [], 4000)       # medium
    api_client.complete('rapport', 'sys', [], 4000)    # high
    medium, high = calls[0]['max_tokens'], calls[1]['max_tokens']
    assert high > medium


# Output tokens (thinking + answer) the evidens step actually spent on Opus 5.5,
# 2026-09-23, lövblåsare package. The 20k ceiling before the headroom was
# doubled clipped it at high, and 14k clipped it at medium. Keep the measured
# use under the ceiling with some margin, whichever effort evidens runs at.
EVIDENS_MEASURED_TOKENS = {'high': 21931, 'medium': 16736}


def test_evidens_ceiling_fits_measured_opus_5_5_reasoning(calls):
    from caia.agents import evidens
    src = open(evidens.__file__, encoding='utf-8').read()
    # The cap the step passes, whatever wraps the system prompt (the mode block).
    assert re.search(r'complete\("evidens", .*, conversation_history, 8000\)', src)
    api_client.complete('evidens', 'sys', [], 8000)
    _, effort = api_client.AGENT_MODELS['evidens']
    assert calls[0]['max_tokens'] >= EVIDENS_MEASURED_TOKENS[effort] * 1.25


# --- effort per mode ---------------------------------------------------------

def test_the_extraction_reads_at_high_in_both_modes(calls):
    """High was measured on forecast packages 2026-10-13 and on follow-up
    analyses 2026-11-08 (16 of 16 the same reading, medium spread)."""
    api_client.complete('kalkyl_extract', 'sys', [], 12000)
    api_client.complete('kalkyl_extract', 'sys', [], 12000, mode='potential')
    api_client.complete('kalkyl_extract', 'sys', [], 12000, mode='uppfoljning')
    efforts = [c['extra_body']['output_config']['effort'] for c in calls]
    assert efforts == ['high', 'high', 'high']
    # The headroom follows the effort actually sent, not the table's.
    assert [c['max_tokens'] for c in calls] == [36000, 36000, 36000]


def test_only_the_extraction_differs_between_the_modes(calls):
    """A step added to EFFORT_UPPFOLJNING changes what a follow-up costs and
    how it reads; this fails so that it is done on purpose."""
    assert set(api_client.EFFORT_UPPFOLJNING) == set()
    for step in ALL_STEPS:
        if step in api_client.EFFORT_UPPFOLJNING:
            continue
        calls.clear()
        api_client.complete(step, 'sys', [], 4000)
        api_client.complete(step, 'sys', [], 4000, mode='uppfoljning')
        assert calls[0] == calls[1], step


# --- models ----------------------------------------------------------------

def test_no_sonnet_4_6_anywhere():
    assert api_client.SONNET == 'anthropic/claude-sonnet-5.5'
    models = {m for m, _ in api_client.AGENT_MODELS.values()}
    assert not any('sonnet-4' in m for m in models | {api_client.DEFAULT_MODEL})


def test_every_configured_model_can_actually_do_adaptive():
    """A model outside ADAPTIVE_MODELS degrades to no thinking *silently* — the
    step keeps working and just stops reasoning, with nothing in the logs."""
    for step, (model, effort) in api_client.AGENT_MODELS.items():
        if effort is not None:
            assert model in api_client.ADAPTIVE_MODELS, step


def test_unsupported_model_degrades_instead_of_erroring():
    assert api_client.thinking_request('anthropic/claude-haiku-4.5', 'high') == {}


def test_effort_none_means_no_thinking():
    assert api_client.thinking_request(api_client.SONNET, None) == {}


def test_unconfigured_step_falls_back_without_thinking(calls):
    api_client.complete('does-not-exist', 'sys', [], 4000)
    assert calls[0]['model'] == api_client.DEFAULT_MODEL
    assert 'thinking' not in calls[0]
    assert calls[0]['max_tokens'] == 4000
