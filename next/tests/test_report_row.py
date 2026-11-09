"""What gets saved with a report: the numbers the calc computed and the name
the user approved, not whatever a regex finds in the model's prose. (W5a, W5c)

The hero card and the saved-reports list both read `key_metric` from this
row, so this is where "the hero shows the deterministic result" is decided.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia.web import app as A  # noqa: E402

REPORT = """---

## Krav på laddbara tjänstebilar

**Beräknad klimatnytta**

Medel effekt/år (Territoriell): 12,5 ton
Medel effekt/år (Konsumtion): 40 ton
Medel effekt/år (Netto/Total): 42 ton
"""


def _post_report(monkeypatch, payload: dict) -> dict:
    """POST /api/reports with Supabase stubbed; returns the row that would be written."""
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims',
                        lambda: {'sub': 'user-1', 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    written = {}

    def capture(method, table, data=None, token=None, **kw):
        written.update(data)
        return [dict(data, id='r1')]

    monkeypatch.setattr(A, 'supabase_request', capture)
    client = A.app.test_client()
    resp = client.post('/api/reports', json=payload, headers={'Authorization': 'Bearer t'})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return written


# ---------- W5c: headline from the calc, regex only as a marked fallback ----------

def test_client_key_metric_is_saved_as_the_calc_result(monkeypatch):
    calc = {'terr': 1.0, 'cons': 2.0, 'net': 2.5}
    row = _post_report(monkeypatch, {'formatted_report': REPORT, 'key_metric': calc})
    assert row['key_metric'] == dict(calc, source='calc')
    # The prose says 42; the calc said 2.5. The calc wins.
    assert row['key_metric']['net'] == 2.5


def test_without_calc_numbers_the_regex_fallback_is_marked_as_such(monkeypatch):
    row = _post_report(monkeypatch, {'formatted_report': REPORT})
    assert row['key_metric']['net'] == 42.0
    assert row['key_metric']['source'] == 'rapport'


def test_empty_client_key_metric_does_not_masquerade_as_calc(monkeypatch):
    row = _post_report(monkeypatch, {'formatted_report': REPORT, 'key_metric': {}})
    assert row['key_metric']['source'] == 'rapport'


# ---------- S8: only a calc headline is saved as one ----------

@pytest.mark.parametrize('key_metric,why', [
    ({'net': 'mycket'}, 'not a number'),
    ({'net': True}, 'a bool is not a number'),
    ({'net': float('inf')}, 'not finite'),
    ({'net': 1.0, 'verified_by': 'Naturvårdsverket'}, 'a field the calc never writes'),
    (['net', 1.0], 'not an object'),
])
def test_a_key_metric_that_is_not_the_calcs_is_refused(monkeypatch, key_metric, why):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: {'sub': 'user-1', 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    writes = []
    monkeypatch.setattr(A, 'supabase_request', lambda *a, **k: writes.append(a) or [{}])
    body = '{"formatted_report": "x", "key_metric": ' + A.json.dumps(key_metric, allow_nan=True) + '}'
    resp = A.app.test_client().post('/api/reports', data=body, content_type='application/json',
                                    headers={'Authorization': 'Bearer t'})
    assert resp.status_code == 400, why
    assert writes == [], why


@pytest.mark.parametrize('field,size', [('formatted_report', 300_001), ('action_name', 301),
                                        ('intake_summary', 50_001)])
def test_oversized_report_fields_are_refused(monkeypatch, field, size):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: {'sub': 'user-1', 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    monkeypatch.setattr(A, 'supabase_request', lambda *a, **k: pytest.fail('written'))
    payload = {'formatted_report': REPORT, field: 'x' * size}
    resp = A.app.test_client().post('/api/reports', json=payload, headers={'Authorization': 'Bearer t'})
    assert resp.status_code == 400


def test_a_report_id_that_is_not_a_uuid_is_a_404_without_asking_supabase(monkeypatch):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: {'sub': 'user-1', 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    monkeypatch.setattr(A, 'supabase_request', lambda *a, **k: pytest.fail('asked supabase'))
    resp = A.app.test_client().get('/api/reports/1,2', headers={'Authorization': 'Bearer t'})
    assert resp.status_code == 404


# ---------- W5a: the action name ----------

def test_action_name_from_the_client_wins(monkeypatch):
    row = _post_report(monkeypatch, {'formatted_report': REPORT, 'action_name': 'Bilpool + Laddstolpar'})
    assert row['action_name'] == 'Bilpool + Laddstolpar'


def test_fallback_name_skips_the_thematic_break(monkeypatch):
    # The old symptom: the saved-reports list showed a row named '---'.
    row = _post_report(monkeypatch, {'formatted_report': REPORT})
    assert row['action_name'] == 'Krav på laddbara tjänstebilar'


def test_fallback_name_never_returns_a_rule_line():
    for md in ('---\n\n## Titel', '***\n# Titel', '- - -\nTitel', '___\n\n**Titel**'):
        name = A._extract_action_name(md)
        assert name == 'Titel', (md, name)
    assert A._extract_action_name('---\n---\n') == 'Namnlös åtgärd'


def test_heading_wins_over_prose_above_it():
    assert A._extract_action_name('Inledande text.\n\n## Titel\n') == 'Titel'


# ---------- the frontend half, checked structurally ----------

def _inline_script() -> str:
    """The page script as a browser would get it: rendered through Jinja with
    the same kwargs the index route passes, then the last <script> block."""
    from flask import render_template_string
    with A.app.test_request_context('/'):
        html = render_template_string(
            A.HTML_TEMPLATE, has_supabase=False, supabase_url='', supabase_anon_key='',
            **A._page_context(),
        )
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    assert scripts
    return scripts[-1]


@pytest.mark.node
def test_inline_script_parses():
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(_inline_script())
    try:
        subprocess.run(['node', '--check', f.name], check=True, capture_output=True)
    finally:
        os.unlink(f.name)


def test_report_save_sends_calc_headline_and_profile_name():
    js = _inline_script()
    save = js[js.index('async function finishReport'):]
    save = save[:save.index('\n}\n')]
    assert 'key_metric: state.headline' in save
    assert 'action_name: actionName' in save
    assert "state.headline = data.headline" in js  # set on the kalkyl stage
    # Reset must clear it, or a second analysis could save the first one's numbers.
    reset = js[js.index('function resetAll'):]
    assert 'headline:null' in reset[:reset.index('\n}\n')]


def test_failed_gate_feedback_is_taken_back_out_of_history():
    # W5b: after a failed re-run the approve button comes back, so the history
    # must not still carry the unanswered feedback turn.
    js = _inline_script()
    block = js[js.index("if (gate && state.phase !== 'profile')"):]
    block = block[:block.index('showApprove(applied || restored || kept); setInputEnabled(true); state.running = false;')]
    assert 'state.history.pop()' in block
    assert 'if (!applied)' in block
