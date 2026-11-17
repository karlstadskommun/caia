"""A tripwire on what the agents are told.

The agents' behaviour lives in their system prompts, the parameter library
and the data context, and none of it is covered by a unit test: a changed
sentence passes the whole suite. This test runs the pipeline with stubbed
models on the Karlstad profile, hashes every system prompt that would be sent,
and compares with tests/fixtures/prompt-fingerprints.json. It does so once per
analysis mode; follow-up keys are prefixed "uppfoljning/".

A second set, tests/fixtures/prompt-fingerprints-utgava.json, covers the
profile as the public release has it: without Konsumtionskompassen's files
(conftest.KK_FILES), whose rows then use the standard value. Both sets are
recorded together.

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
import shutil
import tomllib
from pathlib import Path

import pytest

import caia.web.app as A
from caia import kommun
from caia.mode import UPPFOLJNING
from conftest import KK_FILES
from test_kommunprofil import _run_pipeline, _stub_models, client, use_kommun  # noqa: F401

pytestmark = pytest.mark.karlstad  # reads Karlstad's kommunprofil

FIXTURES = Path(__file__).parent / 'fixtures'
FINGERPRINTS = FIXTURES / 'prompt-fingerprints.json'
RELEASE_FINGERPRINTS = FIXTURES / 'prompt-fingerprints-utgava.json'
UPDATE = 'UPDATE_PROMPT_FINGERPRINTS=1 python -m pytest tests/test_prompt_fingerprints.py'


def _fingerprints(calls: list[dict], prefix: str = '') -> dict[str, str]:
    by_step: dict[str, list[str]] = {}
    for c in calls:
        by_step.setdefault(c['step'], []).append(c['system'])
    # evidens_part sends one prompt per driver; hash them in order, together.
    return {prefix + step: hashlib.sha256('\n\x00\n'.join(systems).encode('utf-8')).hexdigest()[:16]
            for step, systems in sorted(by_step.items())}


def _measure(client, monkeypatch, use_kommun, profile, fixture: Path) -> list[str]:  # noqa: F811
    use_kommun(profile)
    calls = _stub_models(monkeypatch)
    _run_pipeline(client)
    now = _fingerprints(calls)
    calls.clear()
    A._rate_hits.clear()  # two full pipelines in one test pass the per-minute cap
    _run_pipeline(client, UPPFOLJNING)
    now |= _fingerprints(calls, f'{UPPFOLJNING}/')
    if os.environ.get('UPDATE_PROMPT_FINGERPRINTS') == '1':
        fixture.write_text(json.dumps(now, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    recorded = json.loads(fixture.read_text(encoding='utf-8'))
    return sorted(step for step in now.keys() | recorded.keys() if now.get(step) != recorded.get(step))


@pytest.mark.konsumtionskompassen
def test_no_prompt_changed_without_a_rerun(client, monkeypatch, use_kommun):  # noqa: F811
    changed = _measure(client, monkeypatch, use_kommun, 'karlstad', FINGERPRINTS)
    assert not changed, (
        f'Vad agenterna får har ändrats för: {", ".join(changed)}. Kör referensanalyserna '
        f'(docs/RUNBOOK.md, "Ändra en prompt") och uppdatera sedan fingeravtrycken med {UPDATE}')


def test_no_prompt_in_the_release_changed_without_a_rerun(client, monkeypatch, use_kommun,  # noqa: F811
                                                          tmp_path):
    """Karlstad's profile as the public release ships it, also in the full tree."""
    root = tmp_path / 'karlstad'
    shutil.copytree(kommun.BUNDLED_DIR / 'karlstad', root,
                    ignore=lambda _dir, names: [n for n in names if n in KK_FILES])
    assert not any((root / 'data' / f).exists() for f in KK_FILES)
    changed = _measure(client, monkeypatch, use_kommun, kommun.load(root), RELEASE_FINGERPRINTS)
    assert not changed, (
        f'Vad agenterna får i den offentliga utgåvan har ändrats för: {", ".join(changed)}. '
        f'Kör referensanalyserna (docs/RUNBOOK.md, "Ändra en prompt") och uppdatera sedan '
        f'fingeravtrycken med {UPDATE}')


def test_the_release_leaves_out_exactly_these_files():
    """kandidat.toml (in publicering/, not in the public release) excludes the
    same five files that the release fingerprints are measured without."""
    toml = Path(__file__).parents[2] / 'publicering' / 'kandidat.toml'
    if not toml.is_file():
        pytest.skip('publicering/ finns bara i förvaltarnas repo')
    excludes = tomllib.loads(toml.read_text(encoding='utf-8'))['exclude']
    prefix = 'next/src/caia/kommuner/karlstad/'
    in_profile = sorted(e[len(prefix):] for e in excludes if e.startswith(prefix))
    assert in_profile == sorted(f'data/{f}' for f in KK_FILES)
