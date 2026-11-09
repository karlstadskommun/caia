"""Full pipeline end-to-end test: intake -> ... -> rapport against the real models.

Slow and costs API calls (roughly 2-3 USD), so opt-in:

    RUN_E2E=1 OPENROUTER_API_KEY=... python -m pytest tests/test_e2e.py -s -v

Runs through tools/run_batch.py's driver, which calls the endpoints the way
the web page does (evidens split into one call per driver plus a merge, the
same bridge lines). The test used to post the old single-call evidens step
with its own drifted bridge lines, so it tested a path production no longer
takes.
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

NEXT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEXT / 'tools'))

pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_E2E') != '1',
    reason="set RUN_E2E=1 to run the slow full-pipeline e2e",
)

PACKAGE = Path(__file__).parent / 'reference' / '02-aterbruk.md'


def test_full_pipeline_produces_numeric_report(monkeypatch, tmp_path):
    monkeypatch.setattr('caia.web.app.SUPABASE_URL', '')
    monkeypatch.setattr('caia.web.app.CAIA_PASSWORD', '')
    monkeypatch.setattr('caia.web.app.CAIA_DEV_OPEN', True)
    from run_batch import run_package
    from caia.web import app as A

    out = tmp_path / 'run'
    log = io.StringIO()
    assert run_package(A.app.test_client(), PACKAGE, out, log), log.getvalue()[-1500:]

    meta = json.loads((out / 'kalkyl_meta.json').read_text(encoding='utf-8'))
    assert meta.get('deterministic') is True, meta
    assert meta['headline'], meta
    report = (out / 'rapport.md').read_text(encoding='utf-8')
    assert 'ton' in report.lower() and 'co' in report.lower(), "report lacks CO2e figure"
    assert A.extract_key_metric(report), "no key_metric could be extracted from the report"
