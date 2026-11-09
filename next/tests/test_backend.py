"""Backend tests for the CAIA web app: auth, key-metric extraction, report CRUD.

Unit tests run offline. The Supabase round-trip runs only with
RUN_SUPABASE_IT=1 and credentials in the shell, and cleans up after itself.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/ -v
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.web import app as A  # noqa: E402

# ---------- unit: key-metric extraction ----------

def test_extract_key_metric_handles_spaces_and_commas():
    md = (
        "## Bilpool för anställda\n"
        "Medel effekt/år (Territoriell): 1 200 ton CO2e/år\n"
        "Medel effekt/år (Konsumtion): 1 350,5 ton CO2e/år\n"
        "Medel effekt/år (Netto/Total): 1 200 ton CO2e/år\n"
    )
    assert A.extract_key_metric(md) == {'terr': 1200.0, 'cons': 1350.5, 'net': 1200.0}


def test_extract_key_metric_empty_on_no_match():
    assert A.extract_key_metric("ingen siffra här") == {}
    assert A.extract_key_metric("") == {}


def test_extract_key_metric_range_does_not_drop_metric():
    # An LLM range output must not silently drop the metric (greedy-dash bug).
    md = "Medel effekt/år (Netto/Total): 1 200 – 1 400 ton CO2e/år"
    km = A.extract_key_metric(md)
    assert 'net' in km and km['net'] in (1200.0, 1400.0)


def test_extract_key_metric_negative():
    md = "Medel effekt/år (Territoriell): -50 ton CO2e/år"
    assert A.extract_key_metric(md).get('terr') == -50.0


def test_extract_action_name_first_heading():
    assert A._extract_action_name("## Cykelsatsning\nbla") == "Cykelsatsning"
    assert A._extract_action_name("") == "Namnlös åtgärd"


# ---------- unit: auth ----------

def test_protected_route_rejects_without_token(monkeypatch):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    c = A.app.test_client()
    r = c.post('/api/reports', json={'formatted_report': '## x'})
    assert r.status_code == 401


def test_parameters_parses_with_provenance():
    from caia.data.parameters import parse_parameter_library
    secs = parse_parameter_library()
    rows = [r for s in secs for r in s['rows']]
    assert len(rows) > 50, len(rows)
    provs = {r['provenance'] for r in rows}
    assert provs <= {'lokal', 'datafil', 'schablon'} and 'schablon' in provs
    # every row resolves a used value and carries an id
    assert all(r['id'] and 'value_used' in r for r in rows)


def test_get_user_from_token_hs256(monkeypatch):
    import jwt as pyjwt
    secret = secrets.token_hex(32)
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'SUPABASE_JWT_SECRET', secret)
    tok = pyjwt.encode(
        {'sub': 'test-user-123', 'aud': 'authenticated', 'exp': int(time.time()) + 600},
        secret, algorithm='HS256',
    )
    with A.app.test_request_context(headers={'Authorization': f'Bearer {tok}'}):
        assert A.get_user_from_token() == 'test-user-123'


def test_get_user_from_token_none_without_header():
    with A.app.test_request_context():
        assert A.get_user_from_token() is None


# ---------- integration: Supabase reports round-trip ----------
# Writes one row into the real `reports` table and deletes it again. Opt-in
# only (RUN_SUPABASE_IT=1, see tests/conftest.py): credentials that happen to
# be in the shell must never make a plain `pytest` write to production.

_HAS_SUPABASE = (os.environ.get('RUN_SUPABASE_IT') == '1'
                 and bool(os.environ.get('SUPABASE_URL')
                          and os.environ.get('SUPABASE_SERVICE_ROLE_KEY')))


def _rest(method, path, data=None, params=None, base='/rest/v1/'):
    url = os.environ['SUPABASE_URL'].rstrip('/') + base + path
    if params:
        url += '?' + urlencode(params)
    sr = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    req = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None,
        headers={'apikey': sr, 'Authorization': f'Bearer {sr}',
                 'Content-Type': 'application/json', 'Prefer': 'return=representation'},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode()
        return json.loads(body) if body else None


@pytest.mark.skipif(not _HAS_SUPABASE, reason="opt-in: RUN_SUPABASE_IT=1 + Supabase creds")
def test_reports_roundtrip():
    # reports.user_id references auth.users, so borrow a real user id.
    users = _rest('GET', 'users', params={'per_page': '1'}, base='/auth/v1/admin/')
    uid = users['users'][0]['id']
    created = _rest('POST', 'reports', data={
        'user_id': uid, 'action_name': 'PYTEST round-trip',
        'key_metric': {'terr': 1200, 'cons': 1350, 'net': 1200},
        'intake_summary': 'x', 'formatted_report': '## PYTEST',
    })
    rid = created[0]['id']
    try:
        got = _rest('GET', 'reports', params={'select': 'key_metric', 'id': f'eq.{rid}'})
        assert got[0]['key_metric'] == {'terr': 1200, 'cons': 1350, 'net': 1200}
    finally:
        _rest('DELETE', 'reports', params={'id': f'eq.{rid}'})


# ---------- deterministic kalkyl: degrade, never fake ----------

def _kalkyl_client(monkeypatch, extracted):
    """Flask client whose extraction agent returns `extracted` and whose LLM
    fallback is a marker string, so we can see which path answered."""
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    monkeypatch.setattr(A, 'run_kalkyl', lambda h, data_context=None, **_: 'LLM-FALLBACK')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


_GOOD_DRIVER = {
    'name': 'd', 'baseline_year': 2023, 'a0': 1000.0, 'ef0': 0.15,
    'ramp': {'start_year': 2025, 'full_effect_year': 2030, 'profile': 'linjär'},
    'delta_a': -0.10, 'terr': 1.0, 'cons': 0.0, 'overlap': 0.0,
}


def _post(client, driver_over):
    drv = dict(_GOOD_DRIVER)
    drv.update(driver_over)
    return client.post('/api/kalkyl', json={
        'history': [], 'model': {'action_name': 'x', 'target_year': 2030, 'drivers': [drv]},
    })


def test_complete_driver_takes_the_deterministic_path(monkeypatch):
    client = _kalkyl_client(monkeypatch, {
        'action_name': 'x', 'target_year': 2030, 'drivers': [_GOOD_DRIVER]})
    body = _post(client, {}).get_json()
    assert body['deterministic'] is True
    assert 'LLM-FALLBACK' not in body['output']


@pytest.mark.parametrize('broken,why', [
    ({'a0': 0.0}, 'a0 zeroed'),
    ({'ef0': 0.0}, 'ef0 zeroed'),
    ({'a0': None}, 'a0 missing'),
    ({'terr': None}, 'terr missing'),
    ({'cons': None}, 'cons missing'),
    ({'delta_a': {'enhet': 'procent'}}, 'band with no usable value'),
])
def test_incomplete_extraction_degrades_instead_of_returning_a_confident_zero(
        monkeypatch, broken, why):
    """The failure this guards against: a driver with a missing field used to
    default to 0, compute cleanly, and come back labelled deterministic: True.
    A confident zero is worse than an honest fallback."""
    drv = dict(_GOOD_DRIVER)
    for key, value in broken.items():
        if value is None:
            drv.pop(key, None)
        else:
            drv[key] = value
    client = _kalkyl_client(monkeypatch, {
        'action_name': 'x', 'target_year': 2030, 'drivers': [drv]})
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is False, why
    assert body['output'] == 'LLM-FALLBACK', why
