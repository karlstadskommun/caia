"""Cost metering: every model call logs its usage and estimated cost, and
tools/run_batch.py collects the same records per analysis.

The calls go through the real complete() against a stub client, so these see
what production logs. No call here reaches a model.
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from caia import api_client  # noqa: E402

USAGE = SimpleNamespace(input_tokens=10_000, output_tokens=2_000,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0)


def _response(text='Svar.', stop_reason='end_turn', usage=USAGE):
    resp = SimpleNamespace(content=[SimpleNamespace(type='text', text=text)],
                           stop_reason=stop_reason)
    if usage is not None:
        resp.usage = usage
    return resp


class _Client:
    def __init__(self, answer):
        self._answer = answer
        self.messages = self

    def create(self, **kwargs):
        if isinstance(self._answer, BaseException):
            raise self._answer
        return self._answer(kwargs) if callable(self._answer) else self._answer


@pytest.fixture
def model(monkeypatch):
    """Point complete() at a stub; returns a setter for what it answers."""
    def answer(a):
        monkeypatch.setattr(api_client, 'get_client', lambda: _Client(a))
    answer(_response())
    return answer


@pytest.fixture
def records(monkeypatch):
    got: list[dict] = []
    monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [got.append])
    return got


# --- the price table -------------------------------------------------------

def test_every_configured_model_has_a_price():
    """A model swap must bring its price: without a row every call of that
    model is logged as unpriced, and the batch summary undercounts."""
    models = {m for m, _ in api_client.AGENT_MODELS.values()} | {api_client.DEFAULT_MODEL}
    for m in sorted(models):
        price = api_client.PRICES.get(m)
        assert price is not None, f'{m} saknar rad i api_client.PRICES'
        assert price.input > 0 and price.output > price.input, m
        assert 0 < price.cache_read < price.input < price.cache_write, m


def test_the_price_rows_are_keyed_by_the_model_constants():
    assert set(api_client.PRICES) == {api_client.SONNET, api_client.OPUS}


def test_list_prices_verified_2026_10_13():
    """OpenRouter's /api/v1/models, read 2026-10-13. Change together with the
    comment above PRICES, from the same source."""
    assert api_client.PRICES[api_client.OPUS] == api_client.Price(4.0, 20.0, 0.20, 5.0)
    assert api_client.PRICES[api_client.SONNET] == api_client.Price(2.0, 10.0, 0.10, 2.5)


def test_estimate_adds_every_kind_of_token():
    usd = api_client.estimate_usd(api_client.OPUS, 1_000_000, 1_000_000, 1_000_000, 1_000_000)
    assert usd == pytest.approx(4.0 + 20.0 + 0.20 + 5.0)
    assert api_client.estimate_usd(api_client.SONNET, 10_000, 2_000) == pytest.approx(0.04)


def test_an_unknown_model_is_unpriced_not_priced_as_another():
    assert api_client.estimate_usd('anthropic/claude-unknown', 1000, 1000) is None


# --- complete() --------------------------------------------------------------

def test_a_call_logs_one_usage_line(model, records, caplog):
    caplog.set_level(logging.INFO, logger='caia.api_client')
    assert api_client.complete('qa', 'sys', [{'role': 'user', 'content': 'x'}], 4000) == 'Svar.'
    lines = [r.getMessage() for r in caplog.records if r.name == 'caia.api_client']
    assert len(lines) == 1 and lines[0].startswith('model usage ')
    logged = json.loads(lines[0].removeprefix('model usage '))
    assert logged == records[0]
    assert logged['step'] == 'qa'
    assert logged['model'] == api_client.OPUS
    assert logged['effort'] == 'high'
    assert (logged['input'], logged['output']) == (10_000, 2_000)
    assert (logged['cache_read'], logged['cache_write']) == (0, 0)
    assert logged['stop_reason'] == 'end_turn'
    assert logged['usd'] == pytest.approx(0.08)
    assert logged['seconds'] >= 0
    assert 'error' not in logged


def test_the_record_carries_the_mode_and_its_effort(model, records, monkeypatch):
    # The effort actually sent, not the table's: a step with its own level in
    # follow-up mode (none since 2026-11-08, so one is put there for the test).
    monkeypatch.setitem(api_client.EFFORT_UPPFOLJNING, 'kalkyl_extract', api_client.EFFORT_MEDIUM)
    api_client.complete('kalkyl_extract', 'sys', [], 12000, mode='uppfoljning')
    assert records[0]['mode'] == 'uppfoljning'
    assert records[0]['effort'] == 'medium'
    api_client.complete('kalkyl_extract', 'sys', [], 12000, mode='potential')
    assert records[1]['effort'] == 'high'


def test_a_clipped_answer_is_metered_before_it_raises(model, records):
    """Billed in full, so it must be counted even though the step fails."""
    model(_response(stop_reason='max_tokens'))
    with pytest.raises(api_client.ModelOutputError):
        api_client.complete('evidens', 'sys', [], 8000)
    assert records[0]['stop_reason'] == 'max_tokens'
    assert records[0]['usd'] > 0


def test_a_failed_call_is_metered_and_still_raises(model, records):
    model(RuntimeError('upstream gone'))
    with pytest.raises(RuntimeError, match='upstream gone'):
        api_client.complete('emap', 'sys', [], 4000)
    assert records[0]['input'] is None and records[0]['usd'] is None
    # The type, not the message: a provider's error can quote the request
    # (security review S31).
    assert records[0]['error'] == 'RuntimeError'
    assert 'upstream gone' not in json.dumps(records[0])


def test_an_answer_without_usage_is_unpriced(model, records):
    model(_response(usage=None))
    assert api_client.complete('emap', 'sys', [], 4000) == 'Svar.'
    assert records[0]['input'] is None and records[0]['usd'] is None


def test_a_listener_that_raises_never_fails_the_call(model, monkeypatch, records):
    def broken(rec):
        raise ValueError('listener broke')
    monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [broken, records.append])
    assert api_client.complete('emap', 'sys', [], 4000) == 'Svar.'
    assert len(records) == 1  # the next listener still ran


def test_a_broken_usage_object_never_fails_the_call(model, records):
    """The call was billed, so it still gets its line, unpriced."""
    model(_response(usage=SimpleNamespace(input_tokens='many', output_tokens=None)))
    assert api_client.complete('emap', 'sys', [], 4000) == 'Svar.'
    assert records[0]['input'] is None and records[0]['output'] == 0
    assert records[0]['usd'] is None


def test_a_failing_log_line_never_fails_the_call(model, monkeypatch):
    def boom(*a, **k):
        raise OSError('log down')
    monkeypatch.setattr(api_client.log, 'info', boom)
    monkeypatch.setattr(api_client.log, 'warning', boom)
    assert api_client.complete('emap', 'sys', [], 4000) == 'Svar.'


def test_the_app_writes_the_usage_line_once_to_stderr():
    """As on Vercel: a fresh process with no logging set up imports the app,
    and an INFO line from api_client must reach stderr, once. Under pytest the
    root logger already has a handler, so this needs its own process."""
    src = os.path.join(os.path.dirname(__file__), '..', 'src')
    code = ("import logging, caia.web.app\n"
            "logging.getLogger('caia.api_client').info('model usage PROBE')\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTEST')}
    env['PYTHONPATH'] = src
    env.setdefault('CAIA_KOMMUN', 'karlstad')
    done = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                          env=env, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stderr.count('model usage PROBE') == 1, done.stderr[-2000:]


# --- run_batch's meter -------------------------------------------------------

def test_the_meter_writes_each_package_to_its_own_file(model, monkeypatch, tmp_path):
    """Two packages in two threads, as --parallel runs them: each file gets
    only its own calls."""
    import run_batch
    meter = run_batch.UsageMeter()
    monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [meter])

    def package(name, steps):
        meter.start(name, tmp_path / name / 'usage.jsonl')
        for step in steps:
            api_client.complete(step, 'sys', [], 4000)

    threads = [threading.Thread(target=package, args=('a', ['intake', 'emap'])),
               threading.Thread(target=package, args=('b', ['qa']))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    def steps(name):
        rows = [json.loads(line) for line in
                (tmp_path / name / 'usage.jsonl').read_text(encoding='utf-8').splitlines()]
        assert {r['package'] for r in rows} == {name}
        return [r['step'] for r in rows]
    assert steps('a') == ['intake', 'emap']
    assert steps('b') == ['qa']
    assert len(meter.records) == 3


def test_start_empties_the_file_from_an_earlier_run(tmp_path):
    import run_batch
    path = tmp_path / 'p' / 'usage.jsonl'
    path.parent.mkdir()
    path.write_text('{"old": 1}\n', encoding='utf-8')
    run_batch._PACKAGE.reset(run_batch.UsageMeter().start('p', path))
    assert path.read_text(encoding='utf-8') == ''


def test_the_summary_adds_up_per_step_and_in_total():
    import run_batch
    rows = [
        {'package': 'a', 'step': 'evidens_part', 'input': 1000, 'output': 500,
         'cache_read': 0, 'cache_write': 0, 'seconds': 100.0, 'usd': 0.5},
        {'package': 'a', 'step': 'evidens_part', 'input': 1000, 'output': 500,
         'cache_read': 0, 'cache_write': 0, 'seconds': 90.0, 'usd': 0.25},
        {'package': 'b', 'step': 'qa', 'input': 2000, 'output': 100,
         'cache_read': 0, 'cache_write': 0, 'seconds': 30.0, 'usd': 1.0},
        {'package': 'b', 'step': 'qa', 'input': None, 'output': None,
         'cache_read': None, 'cache_write': None, 'seconds': 5.0, 'usd': None,
         'error': "RuntimeError('x')"},
    ]
    text = run_batch.summarize_usage(rows)
    line = {ln.split()[0]: ln.split()[1:] for ln in text.splitlines() if ln.strip()}
    assert line['evidens_part'] == ['2', '2000', '1000', '0', '190', '0.75']
    assert line['qa'] == ['2', '2000', '100', '0', '35', '1.00']
    assert line['totalt'] == ['4', '4000', '1100', '0', '225', '1.75']
    assert 'Per analys:' in text
    assert '1 anrop utan pris' in text and '1 anrop slutade med fel' in text
    assert 'undre gräns' in text


def test_the_summary_of_nothing_says_so():
    import run_batch
    assert 'inga modellanrop' in run_batch.summarize_usage([])


@pytest.mark.karlstad
def test_run_package_meters_the_steps_it_runs(model, monkeypatch, tmp_path):
    """run_batch's own driver against the real app, one step calling the real
    complete(): the call lands in the package's usage.jsonl."""
    import run_batch
    from caia import kommun
    from caia.web import app as A
    before = kommun.active()
    kommun.set_active(kommun.bundled('karlstad'))
    try:
        monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
        monkeypatch.setattr(A, 'SUPABASE_URL', '')
        monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
        monkeypatch.setattr(A, 'get_data_context', lambda: '')
        monkeypatch.setattr(A, 'run_intake', lambda h, **_: {
            'status': 'complete', 'message': 'ÅTGÄRDSPROFIL', 'profiles': []})
        monkeypatch.setattr(A, 'run_emap', lambda h, **_: api_client.complete('emap', 's', h, 4000))
        failing = lambda h, **_: (_ for _ in ()).throw(api_client.ModelOutputError('stopp'))  # noqa: E731
        monkeypatch.setattr(A, 'run_baslinje_bau', failing)
        meter = run_batch.UsageMeter()
        monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [meter])
        pkg = tmp_path / 'bilpool.md'
        pkg.write_text('Kommunen inför en bilpool.', encoding='utf-8')
        out = tmp_path / 'out'
        run_batch.run_package(A.app.test_client(), pkg, out, io.StringIO(),
                              evidens_mode='single', meter=meter)
    finally:
        kommun.set_active(before)
    assert run_batch._PACKAGE.get() is None  # the package's name does not outlive it
    rows = [json.loads(line) for line in
            (out / 'usage.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [(r['package'], r['step']) for r in rows] == [('bilpool', 'emap')]
