"""Auth gating on the routes that cost money.

Every /api/* route below reaches an Opus or Sonnet call. Before the S3 fix, a
deploy that lost both SUPABASE_URL and CAIA_PASSWORD served all of them to
anyone who found the URL, and the bill would have been the first sign.

The module reads its config at import time, so each case reloads it under a
different environment.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_auth_gate.py -v
"""
from __future__ import annotations

import importlib
import os
import secrets
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.web import app as A  # noqa: E402

# Generated per run: no password-shaped literal in the repo for a secret
# scanner to flag, and nothing a test could pass by guessing.
TEST_PASSWORD = secrets.token_urlsafe(12)

# Routes that end up calling a model.
MODEL_ROUTES = ('/api/intake', '/api/emap', '/api/baslinje', '/api/evidens',
                '/api/evidens/part', '/api/evidens/merge',
                '/api/kalkyl', '/api/qa', '/api/rapport')
# Gated too, but answer without a model call.
OTHER_API_ROUTES = ('/api/evidens/plan',)

_AUTH_VARS = ('SUPABASE_URL', 'CAIA_PASSWORD', 'CAIA_DEV_OPEN', 'CAIA_SECRET_KEY',
              'SUPABASE_JWT_SECRET', 'CAIA_ALLOWED_EMAILS', 'CAIA_RATE_LIMIT_PER_MIN',
              'CAIA_RATE_LIMIT_PER_DAY', 'CAIA_INSECURE_COOKIE', 'CAIA_AUTH_FALLBACK',
              'CAIA_TRUSTED_PROXIES', 'CAIA_LOGIN_FAILURES_PER_WINDOW')


@pytest.fixture
def configure():
    """Reload the app module with a specific auth configuration.

    The ambient environment is snapshotted and put back exactly as it was, then
    the module is reloaded once more. Skipping that restore leaves the real
    SUPABASE_* config stripped for every test that runs afterwards, which shows
    up as unrelated failures in test_backend.py.
    """
    saved = {var: os.environ.get(var) for var in _AUTH_VARS}

    def _configure(**env):
        for var in _AUTH_VARS:
            os.environ.pop(var, None)
        os.environ.update(env)
        importlib.reload(A)
        return A.app.test_client()

    yield _configure

    for var, value in saved.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value
    importlib.reload(A)


def test_nothing_configured_refuses_every_model_route(configure):
    client = configure()
    for route in MODEL_ROUTES + OTHER_API_ROUTES:
        resp = client.post(route, json={'message': 'x'})
        assert resp.status_code == 503, (route, resp.status_code)


def test_dev_open_is_an_explicit_opt_in(configure):
    client = configure(CAIA_DEV_OPEN='1')
    # Past the gate: the handler itself answers (400 on a payload it dislikes),
    # which is what "open" is supposed to mean.
    assert client.post('/api/intake', json={}).status_code != 503


def test_dev_open_only_accepts_exactly_one(configure):
    for value in ('true', 'yes', '0', ''):
        client = configure(CAIA_DEV_OPEN=value)
        assert client.post('/api/intake', json={'message': 'x'}).status_code == 503, value


def test_password_mode_demands_a_session(configure):
    client = configure(CAIA_PASSWORD=TEST_PASSWORD, CAIA_SECRET_KEY=secrets.token_hex(16))
    assert client.post('/api/intake', json={'message': 'x'}).status_code == 401


def test_password_mode_refuses_to_boot_without_a_stable_secret(configure):
    """A random per-instance key makes password sessions die on every cold
    start, which presents as a random login loop rather than an error. Fail
    at boot instead."""
    with pytest.raises(RuntimeError, match='CAIA_SECRET_KEY'):
        configure(CAIA_PASSWORD=TEST_PASSWORD)


def test_supabase_mode_tolerates_a_missing_secret(configure):
    """With Supabase JWT the Flask session carries no auth, so the random
    fallback is harmless — the guard must not block that deploy."""
    client = configure(SUPABASE_URL='https://example.supabase.co')
    assert client.post('/api/intake', json={'message': 'x'}).status_code == 401


def test_supabase_mode_demands_a_token(configure):
    client = configure(SUPABASE_URL='https://example.supabase.co')
    assert client.post('/api/intake', json={'message': 'x'}).status_code == 401


def test_supabase_wins_over_dev_open(configure):
    # A production deploy that also has the dev flag set must not fall open.
    client = configure(SUPABASE_URL='https://example.supabase.co', CAIA_DEV_OPEN='1')
    assert client.post('/api/intake', json={'message': 'x'}).status_code == 401


def test_report_crud_is_gated_independently(configure):
    client = configure()
    assert client.get('/api/reports').status_code == 501   # Supabase not configured
    client = configure(SUPABASE_URL='https://example.supabase.co')
    assert client.get('/api/reports').status_code == 401   # configured, no token


def test_every_model_route_carries_an_auth_decorator():
    """Guard against a future route being added without a gate."""
    ungated = []
    for rule in A.app.url_map.iter_rules():
        if not str(rule.rule).startswith('/api/'):
            continue
        view = A.app.view_functions[rule.endpoint]
        closure = getattr(view, '__wrapped__', None)
        if closure is None:
            ungated.append(str(rule.rule))
    assert not ungated, f"/api routes without an auth wrapper: {ungated}"


# ---------- Supabase accounts: who gets in ----------
# The Supabase project is shared and open for signup, so a valid token only
# proves someone confirmed an email address. The allowlist decides.

SECRET = secrets.token_hex(32)  # per run, like TEST_PASSWORD
SUPA = dict(SUPABASE_URL='https://example.supabase.co', SUPABASE_JWT_SECRET=SECRET)


def _token(email='anna@kommun.se', **extra):
    import time

    import jwt as pyjwt
    claims = {'sub': 'user-1', 'aud': 'authenticated', 'email': email,
              'exp': int(time.time()) + 600}
    claims.update(extra)
    return {'Authorization': 'Bearer ' + pyjwt.encode(claims, SECRET, algorithm='HS256')}


def _stub_model(monkeypatch):
    """Every model step answers a marker, so a 200 means the gate let it through."""
    monkeypatch.setattr(A, 'run_emap', lambda history, **_: 'EMAP-SVAR')


def test_an_account_outside_the_allowlist_is_refused(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='@kommun.se', **SUPA)
    _stub_model(monkeypatch)
    resp = client.post('/api/emap', json={'history': []}, headers=_token('stranger@gmail.com'))
    assert resp.status_code == 403
    assert 'behörighet' in resp.get_json()['error']


def test_an_allowlisted_domain_gets_in(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='@kommun.se, solo@example.org', **SUPA)
    _stub_model(monkeypatch)
    ok = client.post('/api/emap', json={'history': []}, headers=_token('Anna@Kommun.se'))
    assert ok.status_code == 200, ok.get_json()
    assert client.post('/api/emap', json={'history': []},
                       headers=_token('solo@example.org')).status_code == 200
    # A lookalike domain is not the domain.
    assert client.post('/api/emap', json={'history': []},
                       headers=_token('x@evilkommun.se')).status_code == 403


def test_no_allowlist_lets_nobody_in(configure, monkeypatch):
    """Fail closed: a deploy that forgot the setting must not turn every
    self-registered account into a user of the Opus key."""
    client = configure(**SUPA)
    _stub_model(monkeypatch)
    assert client.post('/api/emap', json={'history': []},
                       headers=_token()).status_code == 403


def test_star_lets_every_account_in_but_not_anonymous_ones(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='*', **SUPA)
    _stub_model(monkeypatch)
    assert client.post('/api/emap', json={'history': []},
                       headers=_token('vem@som.helst')).status_code == 200
    assert client.post('/api/emap', json={'history': []},
                       headers=_token('', is_anonymous=True)).status_code == 403


def test_saved_reports_follow_the_same_allowlist(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='@kommun.se', **SUPA)
    monkeypatch.setattr(A, 'supabase_request', lambda *a, **k: [])
    assert client.get('/api/reports', headers=_token('stranger@gmail.com')).status_code == 403
    assert client.get('/api/reports', headers=_token('anna@kommun.se')).status_code == 200


def test_a_string_that_is_not_a_jwt_never_reaches_supabase(configure, monkeypatch):
    """Any string after "Bearer " used to cost a blocking 5 s call to
    Supabase's /auth/v1/user before the 401."""
    client = configure(CAIA_ALLOWED_EMAILS='*', **SUPA)
    called = []
    monkeypatch.setattr(A, 'urlopen', lambda *a, **k: called.append(a) or 1 / 0)
    for junk in ('x', 'a.b', 'not.a.jwt', 'a' * 9000):
        resp = client.post('/api/emap', json={'history': []},
                           headers={'Authorization': 'Bearer ' + junk})
        assert resp.status_code == 401, junk[:20]
    assert called == []


def test_a_token_with_a_wrong_signature_is_refused_locally(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='*', **SUPA)
    called = []
    monkeypatch.setattr(A, 'urlopen', lambda *a, **k: called.append(a) or 1 / 0)
    import time

    import jwt as pyjwt
    forged = pyjwt.encode({'sub': 'u', 'aud': 'authenticated', 'email': 'a@b.se',
                           'exp': int(time.time()) + 600}, 'wrong-secret-' + 'y' * 32,
                          algorithm='HS256')
    resp = client.post('/api/emap', json={'history': []},
                       headers={'Authorization': 'Bearer ' + forged})
    assert resp.status_code == 401
    assert called == []


# ---------- cost cap per caller ----------

def test_model_routes_are_capped_per_user(configure, monkeypatch):
    client = configure(CAIA_ALLOWED_EMAILS='*', CAIA_RATE_LIMIT_PER_MIN='3', **SUPA)
    _stub_model(monkeypatch)
    codes = [client.post('/api/emap', json={'history': []}, headers=_token()).status_code
             for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    last = client.post('/api/emap', json={'history': []}, headers=_token())
    assert int(last.headers['Retry-After']) >= 1
    # Another user has their own budget.
    other = _token('b@kommun.se', sub='user-2')
    assert client.post('/api/emap', json={'history': []}, headers=other).status_code == 200


def test_the_rate_table_is_pruned_even_when_every_call_hits_the_limit(monkeypatch):
    now = [5000.0]
    monkeypatch.setattr(A.time, 'monotonic', lambda: now[0])
    table = {f'ip:{i}': [now[0]] for i in range(1001)}
    table['busy'] = [now[0]]
    now[0] += 86401
    table['busy'] = [now[0] - 1]
    # 'busy' is over its minute cap, so the call is refused; the stale rest go.
    assert A._check_rate_limit('busy', 1, 150, table) is not None
    assert list(table) == ['busy']


def test_the_service_runs_one_process_so_the_limits_hold():
    # Throttle state lives in the process. Two gunicorn workers would each
    # count for themselves and double every cap (second pre-merge round).
    install = (Path(__file__).resolve().parents[1] / 'INSTALL.md').read_text(encoding='utf-8')
    assert '--workers 1 ' in install


def test_an_empty_limit_setting_means_the_default(configure):
    # The line as .env.example has it. int('') used to stop the app at boot.
    configure(CAIA_RATE_LIMIT_PER_MIN='', CAIA_RATE_LIMIT_PER_DAY=' ')
    assert (A.RATE_LIMIT_PER_MIN, A.RATE_LIMIT_PER_DAY) == (20, 150)


@pytest.mark.parametrize('value', ['tjugo', '0', '-5'])
def test_a_bad_limit_setting_stops_the_app_and_names_it(configure, value):
    with pytest.raises(RuntimeError, match='CAIA_RATE_LIMIT_PER_MIN'):
        configure(CAIA_RATE_LIMIT_PER_MIN=value)


def test_the_env_example_boots_as_it_is():
    """.env.example sourced into a shell, the README's quick start, with only
    the key filled in: every blank line must read as unset."""
    import subprocess
    script = ('set -a; . ./.env.example; set +a; CAIA_DEV_OPEN=1 OPENROUTER_API_KEY=x '
              f'{sys.executable} -c "import caia.web.app"')
    env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': 'src', 'HOME': os.environ.get('HOME', '')}
    done = subprocess.run(['bash', '-c', script], cwd=Path(__file__).resolve().parents[1],
                          env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-800:]


def test_every_model_route_is_rate_limited():
    """A model route added later without the cap is an unmetered one."""
    uncapped = []
    for route in MODEL_ROUTES:
        view = A.app.view_functions[A.app.url_map.bind('x').match(route, method='POST')[0]]
        if not getattr(view, 'rate_limited', False):
            uncapped.append(route)
    assert not uncapped, uncapped


# ---------- shared password ----------

PW = dict(CAIA_PASSWORD=TEST_PASSWORD, CAIA_SECRET_KEY=secrets.token_hex(32))


def _login(client, password=TEST_PASSWORD):
    return client.post('/login', data={'password': password})


def test_password_login_sets_a_hardened_cookie(configure):
    client = configure(**PW)
    resp = _login(client)
    assert resp.status_code == 302
    cookie = resp.headers['Set-Cookie']
    for flag in ('HttpOnly', 'Secure', 'SameSite=Lax', 'Expires='):
        assert flag in cookie, (flag, cookie)


def test_wrong_passwords_lock_the_login_for_a_while(configure):
    client = configure(**PW)
    for _ in range(A.LOGIN_FAILURES_PER_WINDOW):
        assert _login(client, 'fel').status_code == 200
    # Locked: even the right password is not checked now.
    assert _login(client).status_code == 429


def test_a_workshop_room_can_raise_the_wrong_password_limit(configure):
    # One conference IP for the whole room: five typos must not lock everyone out.
    client = configure(**PW, CAIA_LOGIN_FAILURES_PER_WINDOW='7')
    for _ in range(5):
        assert _login(client, 'fel').status_code == 200
    assert _login(client).status_code == 302
    client = configure(**PW)
    assert A.LOGIN_FAILURES_PER_WINDOW == 5


def test_a_forged_forwarded_address_does_not_reset_the_lock(configure):
    """nginx appends the address it saw after whatever the client wrote in
    X-Forwarded-For. Reading the first entry let a new fake one per request
    guess passwords without limit (pre-merge review)."""
    client = configure(**PW)
    for i in range(A.LOGIN_FAILURES_PER_WINDOW):
        resp = client.post('/login', data={'password': 'fel'},
                           headers={'X-Forwarded-For': f'10.0.0.{i}, 203.0.113.7'})
        assert resp.status_code == 200
    resp = client.post('/login', data={'password': TEST_PASSWORD},
                       headers={'X-Forwarded-For': '10.0.0.99, 203.0.113.7'})
    assert resp.status_code == 429


def test_the_login_table_keeps_only_addresses_with_recent_failures(configure, monkeypatch):
    client = configure(**PW)
    for i in range(3):
        client.get('/login', headers={'X-Forwarded-For': f'198.51.100.{i}'})
        client.post('/login', data={'password': TEST_PASSWORD},
                    headers={'X-Forwarded-For': f'198.51.100.{i}'})
    assert A._login_failures == {}
    # Stale failures are dropped once the table is large.
    now = [1000.0]
    monkeypatch.setattr(A.time, 'monotonic', lambda: now[0])
    for i in range(1001):
        A._login_failed(f'ip-{i}')
    now[0] += A.LOGIN_WINDOW_S + 1
    A._login_failed('fresh')
    assert list(A._login_failures) == ['fresh']


def test_changing_the_password_logs_every_session_out(configure, monkeypatch):
    client = configure(CAIA_INSECURE_COOKIE='1', **PW)
    monkeypatch.setattr(A, 'run_emap', lambda history, **_: 'EMAP-SVAR')
    assert _login(client).status_code == 302
    assert client.post('/api/emap', json={'history': []}).status_code == 200
    monkeypatch.setattr(A, 'CAIA_PASSWORD', secrets.token_urlsafe(12))
    assert client.post('/api/emap', json={'history': []}).status_code == 401


def test_logout_ends_the_session(configure, monkeypatch):
    client = configure(CAIA_INSECURE_COOKIE='1', **PW)
    monkeypatch.setattr(A, 'run_emap', lambda history, **_: 'EMAP-SVAR')
    _login(client)
    assert client.post('/api/emap', json={'history': []}).status_code == 200
    assert client.get('/logout').status_code == 302
    assert client.post('/api/emap', json={'history': []}).status_code == 401


def test_an_expired_session_answers_json_not_the_login_page(configure):
    """fetch() parses the answer as JSON. A redirect to the HTML login page
    reached the page as "Av undefined faktorer"."""
    client = configure(**PW)
    resp = client.get('/api/parameters')
    assert resp.status_code == 401
    assert resp.is_json
