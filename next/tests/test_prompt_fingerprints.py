"""A tripwire on what the agents are told.

The agents' behaviour lives in their system prompts, the parameter library
and the data context, and none of it is covered by a unit test: a changed
sentence passes the whole suite. This test runs the pipeline with stubbed
models on the Karlstad profile, hashes every system prompt that would be sent,
and compares with tests/fixtures/prompt-fingerprints.json. It does so once per
analysis mode; follow-up keys are prefixed "uppfoljning/".

When it fails, a prompt, the library or a data file changed. That is allowed,
but not silently: run the reference analyses as docs/RUNBOOK.md describes
("Ändra en prompt"), compare with the previous run, and then record the new
fingerprints:

    UPDATE_PROMPT_FINGERPRINTS=1 python -m pytest tests/test_prompt_fingerprints.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import caia.web.app as A
from caia.mode import UPPFOLJNING
from test_kommunprofil import _run_pipeline, _stub_models, client, use_kommun  # noqa: F401

pytestmark = pytest.mark.karlstad  # reads Karlstad's kommunprofil

FINGERPRINTS = Path(__file__).parent / 'fixtures' / 'prompt-fingerprints.json'


def _fingerprints(calls: list[dict], prefix: str = '') -> dict[str, str]:
    by_step: dict[str, list[str]] = {}
    for c in calls:
        by_step.setdefault(c['step'], []).append(c['system'])
    # evidens_part sends one prompt per driver; hash them in order, together.
    return {prefix + step: hashlib.sha256('\n\x00\n'.join(systems).encode('utf-8')).hexdigest()[:16]
            for step, systems in sorted(by_step.items())}


def test_no_prompt_changed_without_a_rerun(client, monkeypatch, use_kommun):  # noqa: F811
    use_kommun('karlstad')
    calls = _stub_models(monkeypatch)
    _run_pipeline(client)
    now = _fingerprints(calls)
    calls.clear()
    A._rate_hits.clear()  # two full pipelines in one test pass the per-minute cap
    _run_pipeline(client, UPPFOLJNING)
    now |= _fingerprints(calls, f'{UPPFOLJNING}/')
    if os.environ.get('UPDATE_PROMPT_FINGERPRINTS') == '1':
        FINGERPRINTS.write_text(json.dumps(now, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    recorded = json.loads(FINGERPRINTS.read_text(encoding='utf-8'))
    changed = sorted(step for step in now.keys() | recorded.keys() if now.get(step) != recorded.get(step))
    assert not changed, (
        f'Vad agenterna får har ändrats för: {", ".join(changed)}. Kör referensanalyserna '
        '(docs/RUNBOOK.md, "Ändra en prompt") och uppdatera sedan fingeravtrycken med '
        'UPDATE_PROMPT_FINGERPRINTS=1 python -m pytest tests/test_prompt_fingerprints.py')
