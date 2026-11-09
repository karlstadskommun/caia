"""tools/credit_routes.py: the Anthropic keys first in batch runs, OpenRouter last.

The calls go through the real api_client.complete and the real _create for
OpenRouter; only the network is fake. What is pinned: the first key first,
the second when it is out, OpenRouter when both are, a closed key tried again
after ten minutes, the route in every usage record, and that nothing changes
without CAIA_ANTHROPIC_KEYS (the web app never sets it)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import pytest
from caia import api_client

try:  # the SDK's HTTP layer: httpx2 from anthropic 1.x, httpx before that
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import credit_routes  # noqa: E402
import run_batch  # noqa: E402


def _answer(text):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5,
                            cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=text)],
                           stop_reason='end_turn', usage=usage)


def _err(cls, code, message):
    req = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    return cls(message, response=httpx.Response(code, request=req), body=None)


def _out():  # what Anthropic sends for an empty balance
    return _err(anthropic.BadRequestError, 400,
                'Your credit balance is too low to access the Anthropic API.')


class _Net:
    """Fake clients. `answers[name]` is a callable giving the next outcome;
    `calls` lists (route, model) in the order they were asked."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def client(self, name):
        net = self

        class _Messages:
            def create(self, **kw):
                net.calls.append((name, kw['model']))
                out = net.answers[name]()
                if isinstance(out, BaseException):
                    raise out
                return out

        class _Client:
            messages = _Messages()

            def with_options(self, **kw):
                return self

        return _Client()


@pytest.fixture
def setup(monkeypatch):
    """Install the routes for one test, with the network faked and every
    module-level change undone afterwards."""
    credit_routes.reset()
    monkeypatch.setattr(api_client, '_create', api_client._create)
    monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [])
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-or')
    monkeypatch.delenv('CAIA_ANTHROPIC_API_KEY', raising=False)

    def make(answers, keys='sk-1,sk-2'):
        net = _Net(answers)
        monkeypatch.setenv('CAIA_ANTHROPIC_KEYS', keys)
        monkeypatch.setattr(credit_routes, '_direct_client',
                            lambda key: net.client({'sk-1': 'anthropic:1', 'sk-2': 'anthropic:2'}[key]))
        monkeypatch.setattr(api_client, 'get_client', lambda: net.client('openrouter'))
        assert credit_routes.install()
        records = []
        api_client.USAGE_LISTENERS.append(records.append)
        return net, records

    yield make
    credit_routes.reset()


def _call():
    return api_client.complete('emap', 'system', [{'role': 'user', 'content': 'x'}], 100)


def test_the_work_account_answers_and_nothing_switches(setup):
    net, records = setup({'anthropic:1': lambda: _answer('direkt'),
                          'anthropic:2': lambda: _answer('fel'),
                          'openrouter': lambda: _answer('fel')})
    assert _call() == 'direkt'
    assert net.calls == [('anthropic:1', 'claude-sonnet-5-5')]
    assert [r['route'] for r in records] == ['anthropic:1']
    assert records[0]['model'] == api_client.SONNET  # priced under the table's id


def test_work_account_out_second_takes_over_and_the_next_call_starts_there(setup):
    net, records = setup({'anthropic:1': _out,
                          'anthropic:2': lambda: _answer('andra'),
                          'openrouter': lambda: _answer('fel')})
    assert _call() == 'andra'
    assert _call() == 'andra'
    assert [c[0] for c in net.calls] == ['anthropic:1', 'anthropic:2', 'anthropic:2']
    assert [r['route'] for r in records] == ['anthropic:2', 'anthropic:2']


def test_both_accounts_out_openrouter_with_its_own_id(setup, caplog):
    net, records = setup({'anthropic:1': _out,
                          'anthropic:2': lambda: _err(anthropic.APIStatusError, 402, 'Insufficient funds'),
                          'openrouter': lambda: _answer('via')})
    assert _call() == 'via'
    assert net.calls == [('anthropic:1', 'claude-sonnet-5-5'), ('anthropic:2', 'claude-sonnet-5-5'),
                         ('openrouter', api_client.SONNET)]
    assert records[-1]['route'] == 'openrouter'
    warnings = [r.getMessage() for r in caplog.records if r.levelname == 'WARNING']
    assert any('route anthropic:1 failed: credits' in w and 'trying anthropic:2' in w for w in warnings)
    assert any('route anthropic:2 failed: credits' in w and 'trying openrouter' in w for w in warnings)
    assert not any('sk-1' in w or 'sk-2' in w for w in warnings)
    # The next call asks neither key again.
    net.calls.clear()
    assert _call() == 'via'
    assert net.calls == [('openrouter', api_client.SONNET)]


def test_a_closed_key_is_tried_again_after_ten_minutes(setup, monkeypatch):
    out = {'now': True}
    net, records = setup({'anthropic:1': lambda: _out() if out['now'] else _answer('tillbaka'),
                          'anthropic:2': lambda: _answer('andra'),
                          'openrouter': lambda: _answer('fel')})
    clock = {'t': 1000.0}
    monkeypatch.setattr(credit_routes.time, 'monotonic', lambda: clock['t'])
    assert _call() == 'andra'
    clock['t'] += credit_routes.EXHAUSTED_FOR_S - 1
    net.calls.clear()
    assert _call() == 'andra'
    assert [c[0] for c in net.calls] == ['anthropic:2']
    clock['t'] += 2
    out['now'] = False
    net.calls.clear()
    assert _call() == 'tillbaka'
    assert [c[0] for c in net.calls] == ['anthropic:1']
    assert records[-1]['route'] == 'anthropic:1'


def test_rate_limit_hands_on_without_closing_the_key(setup):
    net, _ = setup({'anthropic:1': lambda: _err(anthropic.RateLimitError, 429, 'slow down'),
                    'anthropic:2': lambda: _answer('andra'),
                    'openrouter': lambda: _answer('fel')})
    assert _call() == 'andra'
    assert _call() == 'andra'
    assert [c[0] for c in net.calls] == ['anthropic:1', 'anthropic:2', 'anthropic:1', 'anthropic:2']


def test_a_read_timeout_is_not_handed_on(setup):
    req = httpx.Request('POST', 'https://api.anthropic.com')
    net, _ = setup({'anthropic:1': lambda: anthropic.APITimeoutError(request=req),
                    'anthropic:2': lambda: _answer('fel'),
                    'openrouter': lambda: _answer('fel')})
    with pytest.raises(anthropic.APITimeoutError):
        _call()
    assert [c[0] for c in net.calls] == ['anthropic:1']


def test_failure_classes():
    k = credit_routes.failover_kind
    assert k(_out()) == 'credits'
    assert k(_err(anthropic.BadRequestError, 400, 'You have reached your specified API usage limits')) == 'credits'
    assert k(_err(anthropic.AuthenticationError, 401, 'x')) == 'auth'
    assert k(_err(anthropic.PermissionDeniedError, 403, 'x')) == 'permission'
    assert k(_err(anthropic.RateLimitError, 429, 'x')) == 'rate_limit'
    assert k(_err(anthropic.APIStatusError, 529, 'x')) == 'overloaded'
    assert k(_err(anthropic.InternalServerError, 500, 'x')) == 'server'
    assert k(_err(anthropic.BadRequestError, 400, 'bad field')) == 'bad_request'
    assert k(ValueError('our bug')) is None
    assert credit_routes.MARKS_EXHAUSTED == {'credits', 'auth', 'permission'}


def test_without_the_variable_nothing_is_installed(monkeypatch):
    monkeypatch.delenv('CAIA_ANTHROPIC_KEYS', raising=False)
    before = api_client._create
    assert credit_routes.install() is False
    assert api_client._create is before


def test_both_key_variables_is_refused(monkeypatch):
    monkeypatch.setenv('CAIA_ANTHROPIC_KEYS', 'sk-1')
    monkeypatch.setenv('CAIA_ANTHROPIC_API_KEY', 'sk-x')
    with pytest.raises(credit_routes.ConfigError):
        credit_routes.install()


def test_the_web_app_never_imports_the_routes():
    src = Path(__file__).resolve().parents[1] / 'src'
    hits = [p for p in src.rglob('*.py') if 'credit_routes' in p.read_text(encoding='utf-8')]
    assert hits == []


def test_summary_splits_cost_per_route():
    recs = [{'step': 'emap', 'route': 'anthropic:1', 'usd': 1.0, 'input': 1, 'output': 1, 'seconds': 1},
            {'step': 'emap', 'route': 'openrouter', 'usd': 2.0, 'input': 1, 'output': 1, 'seconds': 1}]
    text = run_batch.summarize_usage(recs)
    assert 'Per väg:' in text
    assert 'anthropic:1' in text and 'openrouter' in text


def test_no_route_is_tried_with_less_than_ten_seconds_left(setup, monkeypatch):
    clock = {'t': 1000.0}
    monkeypatch.setattr(credit_routes.time, 'monotonic', lambda: clock['t'])

    def slow_out():  # the first key spends the whole budget, then says it is out
        clock['t'] += api_client.REQUEST_TIMEOUT_S
        return _out()

    net, _ = setup({'anthropic:1': slow_out,
                    'anthropic:2': lambda: _answer('fel'),
                    'openrouter': lambda: _answer('fel')})
    with pytest.raises(anthropic.BadRequestError):
        _call()
    assert [c[0] for c in net.calls] == ['anthropic:1']


def test_a_key_in_an_error_message_never_reaches_the_log(setup, caplog):
    setup({'anthropic:1': lambda: _err(anthropic.AuthenticationError, 401, 'invalid x-api-key sk-1'),
           'anthropic:2': lambda: _answer('andra'),
           'openrouter': lambda: _answer('fel')})
    assert _call() == 'andra'
    text = ' '.join(r.getMessage() for r in caplog.records)
    assert 'failed: auth' in text and '[key]' in text
    assert 'sk-1' not in text


def test_the_direct_client_is_pinned_to_anthropic_without_retries(monkeypatch):
    credit_routes.reset()
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://elsewhere.example')
    client = credit_routes._direct_client('sk-test')
    assert str(client.base_url).rstrip('/') == credit_routes.ANTHROPIC_BASE_URL
    assert client.max_retries == 0
    credit_routes.reset()
