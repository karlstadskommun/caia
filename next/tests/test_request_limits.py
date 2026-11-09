"""What the API accepts, and what it says when a step fails.

Every step takes the whole analysis history from the client and hands it to
a model. Before these checks a client could send any size, any shape, or a
history naming three hundred drivers, and each driver became its own Opus
call. A failed step answered with the raw exception text, which for a wrong
OpenRouter key read "Missing Authentication header".
"""
from __future__ import annotations

import anthropic
import pytest
from caia.api_client import ModelOutputError

try:  # the SDK's HTTP layer: httpx2 from anthropic 1.x, httpx before that
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx
from caia.web import app as A

# The shape the baslinje agent writes (tests/fixtures/baslinje.md).
DRIVER_BLOCK = """**Drivare {n}: Källa {n}**
  Nuläge_år: 2023
  A0: 100
  A0_enhet: enheter/år
  EF0: 0,1
  EF0_enhet: kg CO2e/enhet
"""


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


def _no_model(monkeypatch):
    calls = []
    for name in ('run_intake', 'run_emap', 'run_baslinje_bau', 'run_evidens',
                 'run_cove_qa', 'run_rapport', 'run_kalkyl_extract', 'run_kalkyl'):
        monkeypatch.setattr(A, name, lambda *a, _n=name, **k: calls.append(_n) or 'x')
    return calls


# ---------- size and shape ----------

def test_a_body_over_the_cap_is_refused_before_anything_reads_it(client, monkeypatch):
    calls = _no_model(monkeypatch)
    big = 'x' * (3 * 1024 * 1024)
    resp = client.post('/api/emap', json={'history': [{'role': 'user', 'content': big}]})
    assert resp.status_code == 413
    assert resp.is_json
    assert calls == []


@pytest.mark.parametrize('body,why', [
    ({'history': 'text'}, 'history not a list'),
    ({'history': [{'role': 'system', 'content': 'x'}]}, 'role the API does not take'),
    ({'history': [{'role': 'user', 'content': {'nested': 1}}]}, 'content not text'),
    ({'history': ['bare string']}, 'turn not an object'),
    ({'history': [{'role': 'user', 'content': 'x'}] * (A.MAX_HISTORY_TURNS + 1)}, 'too many turns'),
    (['not', 'an', 'object'], 'body not an object'),
])
def test_a_malformed_history_is_a_400_and_reaches_no_model(client, monkeypatch, body, why):
    calls = _no_model(monkeypatch)
    for route in ('/api/intake', '/api/emap', '/api/kalkyl', '/api/evidens/plan'):
        resp = client.post(route, json=body)
        assert resp.status_code == 400, (route, why, resp.status_code)
        assert resp.is_json
    assert calls == [], why


def test_a_history_with_too_many_drivers_does_not_fan_out(client, monkeypatch):
    blocks = '\n'.join(DRIVER_BLOCK.format(n=n) for n in range(1, A.MAX_DRIVERS + 2))
    history = [{'role': 'user', 'content': 'Åtgärd'},
               {'role': 'assistant', 'content': '## Nulägesbaslinje per drivare\n' + blocks}]
    drivers = A.drivers_from_history(history)
    assert len(drivers) == A.MAX_DRIVERS + 1, 'fixture no longer parses; the test proves nothing'
    resp = client.post('/api/evidens/plan', json={'history': history})
    assert resp.status_code == 422
    assert 'högst' in resp.get_json()['error']
    part = client.post('/api/evidens/part', json={'history': history, 'driver': 1})
    assert part.status_code == 422 or part.status_code == 502
    assert 'högst' in part.get_json()['error']


def test_a_driver_that_is_not_a_number_is_a_400(client):
    resp = client.post('/api/evidens/part', json={'history': [], 'driver': '1'})
    assert resp.status_code == 400


# ---------- errors say something the reader can act on ----------

def _raising(exc):
    def run(*a, **k):
        raise exc
    return run


def _status_error(cls, status):
    req = httpx.Request('POST', 'https://openrouter.ai/api/v1/messages')
    return cls('upstream said no', response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize('exc,expect', [
    (_status_error(anthropic.AuthenticationError, 401), 'OPENROUTER_API_KEY'),
    (_status_error(anthropic.APIStatusError, 402), 'krediter'),
    (_status_error(anthropic.RateLimitError, 429), 'Vänta en minut'),
    (ModelOutputError('Modellen slog i sitt tokentak.'), 'tokentak'),
])
def test_known_failures_become_plain_swedish(client, monkeypatch, exc, expect):
    monkeypatch.setattr(A, 'run_emap', _raising(exc))
    resp = client.post('/api/emap', json={'history': []})
    assert resp.status_code >= 500
    assert expect in resp.get_json()['error']
    assert 'upstream said no' not in resp.get_json()['error']


@pytest.mark.parametrize('exc,retryable', [
    (_status_error(anthropic.RateLimitError, 429), True),
    (_status_error(anthropic.InternalServerError, 529), True),
    (anthropic.APIConnectionError(request=httpx.Request('POST', 'https://openrouter.ai')), True),
    (anthropic.APITimeoutError(request=httpx.Request('POST', 'https://openrouter.ai')), False),
    (ModelOutputError('Modellen slog i sitt tokentak.'), False),
    (_status_error(anthropic.AuthenticationError, 401), False),
    (_status_error(anthropic.APIStatusError, 402), False),
])
def test_only_fast_failures_that_can_pass_are_marked_for_a_retry(client, monkeypatch, exc, retryable):
    """The page retries what the server marks: a timeout already took minutes
    and a new try is a new paid call; a bad answer or a key would fail again."""
    monkeypatch.setattr(A, 'run_emap', _raising(exc))
    body = client.post('/api/emap', json={'history': []}).get_json()
    assert body.get('retryable', False) is retryable


@pytest.mark.parametrize('exc,retryable', [
    (anthropic.APIConnectionError(request=httpx.Request('POST', 'https://openrouter.ai')), True),
    (_status_error(anthropic.InternalServerError, 502), True),
    (anthropic.APITimeoutError(request=httpx.Request('POST', 'https://openrouter.ai')), False),
])
def test_a_provider_failure_in_the_extraction_does_not_start_the_fallback(
        client, monkeypatch, exc, retryable):
    """A connection dropped 108 s into the extraction (2026-10-13). The LLM
    fallback would have started with what was left of the function's 300 s;
    the step answers instead, and the page runs it again."""
    called = []
    monkeypatch.setattr(A, 'run_kalkyl_extract', _raising(exc))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: called.append(1) or 'LLM-FALLBACK')
    resp = client.post('/api/kalkyl', json={'history': []})
    assert resp.status_code == 502
    assert resp.get_json().get('retryable', False) is retryable
    assert not called


def test_a_reading_that_fails_still_falls_back(client, monkeypatch):
    """Only the provider's own failures skip the fallback: an extraction the
    engine refuses is answered by the LLM kalkyl, as before."""
    monkeypatch.setattr(A, 'run_kalkyl_extract', _raising(ValueError('a0 saknas')))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: 'LLM-FALLBACK')
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is False
    assert body['output'] == 'LLM-FALLBACK'


def test_an_unexpected_failure_shows_an_error_id_not_the_exception(client, monkeypatch):
    monkeypatch.setattr(A, 'run_emap', _raising(KeyError('supabase_service_role_key')))
    resp = client.post('/api/emap', json={'history': []})
    assert resp.status_code == 500
    error = resp.get_json()['error']
    assert 'fel-id' in error
    assert 'supabase' not in error.lower()


def test_wrong_method_and_unknown_api_path_answer_json(client):
    for resp in (client.get('/api/intake'), client.post('/api/finns-inte', json={})):
        assert resp.status_code in (404, 405)
        assert resp.is_json


def test_a_page_outside_the_api_still_gets_the_html_404(client):
    resp = client.get('/finns-inte')
    assert resp.status_code == 404
    assert not resp.is_json


def test_supabase_unreachable_is_a_json_502(monkeypatch):
    """Only HTTP errors were caught; a DNS or connection failure escaped as
    Flask's HTML 500 and the saved-reports list said "no analyses yet"."""
    from urllib.error import URLError

    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: {'sub': 'u', 'email': 'a@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    monkeypatch.setattr(A, 'urlopen', _raising(URLError('Name or service not known')))
    resp = A.app.test_client().get('/api/reports', headers={'Authorization': 'Bearer t'})
    assert resp.status_code == 502
    assert resp.get_json()['error'] == 'Kunde inte nå Supabase.'


# ---------- headers every response carries ----------

def test_pages_and_api_answers_carry_the_basic_security_headers(client):
    for resp in (client.get('/'), client.post('/api/intake', json={'history': 'x'})):
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        assert resp.headers['X-Frame-Options'] == 'DENY'
        assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_model_output_is_sanitized_with_forms_images_and_styles_left_out():
    # Since the October 2026 review the config lists what may stay
    # (test_security_review_2026_10.py); forms, images and styles are not on it.
    from test_report_row import _inline_script
    js = _inline_script()
    assert 'DOMPurify.sanitize(marked.parse(tameMarkdown(part), {breaks: true}),' in js
    allowed = js[js.index('ALLOWED_TAGS'):js.index('ALLOWED_ATTR')]
    for tag in ('form', 'input', 'img', 'style'):
        assert f"'{tag}'" not in allowed, tag
    assert js.count('DOMPurify.sanitize(') == 1, 'another render path skips the config'
