"""tools/replay_step.py: one step of a saved analysis run again N times from
the same cut, then the rest of the chain to kalkyl.

A saved analysis is made first with run_batch's own driver, then replayed,
both against the real app with the model steps answered by stand-ins that
count their calls and answer differently every time. The kalkyl step runs
the real engine, so every repeat ends in a real headline. No call here
reaches a model.
"""
from __future__ import annotations

import io
import itertools
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from caia import api_client, kommun
from caia.pipeline import BRIDGE, STEPS

NEXT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEXT / 'tools'))

import compare_runs  # noqa: E402
import replay_step  # noqa: E402
import run_batch  # noqa: E402

DRIVER = {
    'name': 'Tjänstebilar', 'baseline_year': 2023,
    'a0': 3_000_000.0, 'a0_unit': 'km/år', 'ef0': 0.15, 'ef0_unit': 'kg CO2e/km',
    'g_a': 0.0, 'g_ef': 0.0, 'delta_a': {'min': -0.05, 'med': -0.1, 'max': -0.2}, 'delta_ef': 0.0,
    'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
    'ramp': {'start_year': 2026, 'full_effect_year': 2028},
    'kallor': {'a0': {'ursprung': 'antagande', 'not': '200 bilar × 15 000 km'},
               'ef0': {'ursprung': 'parameterbibliotek', 'parametrar': ['EF_passenger_car_avg']}},
}
USAGE = SimpleNamespace(input_tokens=10_000, output_tokens=2_000,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0)


class _Client:
    """Stands in for the model client: every call is 10k in and 2k out, which
    is 0.04 USD for baslinje (Sonnet) and 0.08 for evidens (Opus)."""
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type='text', text='modellsvar')],
                               stop_reason='end_turn', usage=USAGE)


@pytest.fixture
def app(monkeypatch):
    """The real app with every agent replaced by a counting stand-in. Each
    agent's answer carries its call number, and the extraction reads the
    baslinje's number into the driver's a0, so a rerun baslinje moves the
    headline and an unchanged one does not."""
    from caia.web import app as A
    before = kommun.active()
    kommun.set_active(kommun.bundled('karlstad'))
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    monkeypatch.setattr(api_client, 'get_client', lambda: _Client())
    calls: dict[str, list] = {s: [] for s in STEPS}
    counters = {s: itertools.count(1) for s in STEPS}

    def agent(step, text):
        def run(history, **_):
            calls[step].append(json.dumps(history, ensure_ascii=False))
            return f'{text} {next(counters[step])}'
        return run

    def intake(history, **_):
        calls['intake'].append(json.dumps(history, ensure_ascii=False))
        k = next(counters['intake'])
        if len(history) == 1:  # the measure only: ask first, as the agent does
            return {'status': 'questions', 'message': f'Hur många bilar? ({k})', 'profiles': []}
        return {'status': 'complete', 'message': f'ÅTGÄRDSPROFIL {k}', 'profiles': []}

    def baslinje(history, **_):
        calls['baslinje'].append(json.dumps(history, ensure_ascii=False))
        api_client.complete('baslinje', 'sys', [{'role': 'user', 'content': 'x'}], 4000)
        return f'BASLINJE {next(counters["baslinje"])}'

    def extract(history, **_):
        calls['kalkyl'].append(json.dumps(history, ensure_ascii=False))
        next(counters['kalkyl'])
        found = [m['content'] for m in history if m['content'].startswith('BASLINJE ')]
        k = int(found[-1].split()[1])
        return {'action_name': 'Bilpool', 'target_year': 2030,
                'drivers': [dict(DRIVER, a0=1_000_000.0 * k)]}

    monkeypatch.setattr(A, 'run_intake', intake)
    monkeypatch.setattr(A, 'run_emap', agent('emap', 'EMAP'))
    monkeypatch.setattr(A, 'run_baslinje_bau', baslinje)
    def evidens(history, **_):
        calls['evidens'].append(json.dumps(history, ensure_ascii=False))
        api_client.complete('evidens', 'sys', [{'role': 'user', 'content': 'x'}], 4000)
        return f'EVIDENS {next(counters["evidens"])}'

    monkeypatch.setattr(A, 'run_evidens', evidens)
    monkeypatch.setattr(A, 'run_kalkyl_extract', extract)
    monkeypatch.setattr(A, 'run_kalkyl', lambda h, **_: 'Kalkyl räknad av språkmodellen.')
    monkeypatch.setattr(A, 'run_cove_qa', agent('qa', 'QA'))
    monkeypatch.setattr(A, 'run_rapport', agent('rapport', '# Åtgärdskort\n\nLöptext'))
    yield SimpleNamespace(app=A.app, calls=calls)
    kommun.set_active(before)


@pytest.fixture
def saved(app, tmp_path):
    """A saved analysis from run_batch, the way a real one is made."""
    pkg = tmp_path / 'bilpool.md'
    pkg.write_text('Kommunen inför en bilpool.\n\n## Svar till intake-agenten\n\nTvåhundra bilar.\n',
                   encoding='utf-8')
    out = tmp_path / 'saved'
    meter = run_batch.UsageMeter()
    api_client.USAGE_LISTENERS.append(meter)
    try:
        assert run_batch.run_package(app.app.test_client(), pkg, out / 'bilpool', io.StringIO(),
                                     evidens_mode='single', meter=meter)
    finally:
        api_client.USAGE_LISTENERS.remove(meter)
    for step in app.calls:
        app.calls[step].clear()
    return out / 'bilpool'


def _replay(app, saved, tmp_path, step, n=3, **kw):
    out = tmp_path / f'replay-{step}'
    rows = replay_step.replay(app.app, saved, step, n, out, evidens_mode='single', **kw)
    return out, rows


def _history(path: Path) -> list[dict]:
    return json.loads((path / 'history.json').read_text(encoding='utf-8'))


# --- what runs and what stays fixed ------------------------------------------

@pytest.mark.karlstad
def test_baslinje_runs_n_times_and_only_the_steps_from_it_to_kalkyl(app, saved, tmp_path):
    _, rows = _replay(app, saved, tmp_path, 'baslinje', n=3)
    assert [r['ok'] for r in rows] == [True, True, True]
    counts = {s: len(c) for s, c in app.calls.items()}
    assert counts == {'intake': 0, 'emap': 0, 'baslinje': 3, 'evidens': 3, 'kalkyl': 3,
                      'qa': 0, 'rapport': 0}


@pytest.mark.karlstad
def test_the_steps_before_the_cut_are_byte_identical_to_the_saved_analysis(app, saved, tmp_path):
    source = _history(saved)
    cut = replay_step.cut_before(source, 'baslinje')
    assert cut[-1] == {'role': 'user', 'content': BRIDGE['emap']}
    out, _ = _replay(app, saved, tmp_path, 'baslinje', n=3)
    expected = json.dumps(cut, ensure_ascii=False)
    # What the step saw, each time, is exactly the saved conversation up to it.
    assert app.calls['baslinje'] == [expected] * 3
    for i in (1, 2, 3):
        rep = out / f'bilpool-r{i}'
        assert json.dumps(_history(rep)[:len(cut)], ensure_ascii=False) == expected
        for step in ('intake', 'emap'):
            assert (rep / f'{step}.md').read_bytes() == (saved / f'{step}.md').read_bytes()
    meta = json.loads((out / 'replay.json').read_text(encoding='utf-8'))
    assert meta['cut_turns'] == len(cut) and meta['steps_run'] == ['baslinje', 'evidens', 'kalkyl']


@pytest.mark.karlstad
def test_the_steps_after_see_the_new_answer_and_end_in_a_headline(app, saved, tmp_path):
    out, rows = _replay(app, saved, tmp_path, 'baslinje', n=3)
    # The saved analysis had baslinje 1; the repeats get 2, 3 and 4, in some order.
    seen = sorted((out / f'bilpool-r{i}' / 'baslinje.md').read_text(encoding='utf-8')
                  for i in (1, 2, 3))
    assert seen == ['BASLINJE 2', 'BASLINJE 3', 'BASLINJE 4']
    for i in (1, 2, 3):
        rep = out / f'bilpool-r{i}'
        hist = _history(rep)
        bas = (rep / 'baslinje.md').read_text(encoding='utf-8')
        assert {'role': 'assistant', 'content': bas} in hist  # evidens and kalkyl saw it
        assert hist[-1] == {'role': 'user', 'content': BRIDGE['kalkyl']}
        meta = json.loads((rep / 'kalkyl_meta.json').read_text(encoding='utf-8'))
        assert meta['deterministic'] is True
        assert not (rep / 'qa.md').exists() and not (rep / 'rapport.md').exists()
    nets = sorted(r['net'] for r in rows)
    assert len(set(nets)) == 3 and all(n > 0 for n in nets)
    # a0 is 1, 2, 3 or 4 million km and everything else is fixed: net scales with it.
    assert nets[2] / nets[0] == pytest.approx(4 / 2)


@pytest.mark.karlstad
def test_rerunning_kalkyl_leaves_baslinje_and_evidens_alone(app, saved, tmp_path):
    out, rows = _replay(app, saved, tmp_path, 'kalkyl', n=2)
    assert {s: len(c) for s, c in app.calls.items() if c} == {'kalkyl': 2}
    for i in (1, 2):
        for step in ('intake', 'emap', 'baslinje', 'evidens'):
            rep = out / f'bilpool-r{i}'
            assert (rep / f'{step}.md').read_bytes() == (saved / f'{step}.md').read_bytes()
    saved_net = json.loads((saved / 'kalkyl_meta.json').read_text(encoding='utf-8'))['headline']['net']
    assert [r['net'] for r in rows] == [saved_net, saved_net]


@pytest.mark.karlstad
def test_rerunning_intake_gives_it_the_saved_answer(app, saved, tmp_path):
    source = _history(saved)
    assert source[2]['content'] == 'Tvåhundra bilar.'
    out, rows = _replay(app, saved, tmp_path, 'intake', n=2)
    assert all(r['ok'] for r in rows)
    # Two calls per repeat: the question, then the profile after the saved answer.
    assert len(app.calls['intake']) == 4
    for i in (1, 2):
        hist = _history(out / f'bilpool-r{i}')
        assert hist[0] == source[0] and hist[2] == {'role': 'user', 'content': 'Tvåhundra bilar.'}
        assert (out / f'bilpool-r{i}' / 'kalkyl_meta.json').is_file()
    assert {s: len(c) for s, c in app.calls.items()} == {
        'intake': 4, 'emap': 2, 'baslinje': 2, 'evidens': 2, 'kalkyl': 2, 'qa': 0, 'rapport': 0}


@pytest.mark.karlstad
def test_through_rapport_runs_qa_and_rapport_and_appends_the_section(app, saved, tmp_path):
    out, rows = _replay(app, saved, tmp_path, 'evidens', n=1, through='rapport')
    assert rows[0]['ok']
    assert len(app.calls['qa']) == 1 and len(app.calls['rapport']) == 1
    rep = out / 'bilpool-r1'
    section = json.loads((rep / 'kalkyl_meta.json').read_text(encoding='utf-8'))['kallmarkering_md']
    assert (rep / 'rapport.md').read_text(encoding='utf-8').endswith('\n\n' + section + '\n')


@pytest.mark.karlstad
def test_a_rerun_rapport_gets_the_source_section_of_the_saved_kalkyl(app, saved, tmp_path):
    out, _ = _replay(app, saved, tmp_path, 'rapport', n=1, through='rapport')
    section = json.loads((saved / 'kalkyl_meta.json').read_text(encoding='utf-8'))['kallmarkering_md']
    assert section
    assert (out / 'bilpool-r1' / 'rapport.md').read_text(encoding='utf-8').endswith(section + '\n')


def test_a_step_run_twice_is_cut_at_its_last_hand_over():
    """The page lets a step be run again; the history then holds its bridge
    line twice. The cut is the conversation the last run saw."""
    history = [{'role': 'user', 'content': 'Åtgärd'},
               {'role': 'assistant', 'content': 'ÅTGÄRDSPROFIL'},
               {'role': 'user', 'content': BRIDGE['intake']},
               {'role': 'assistant', 'content': 'EMAP 1'},
               {'role': 'user', 'content': BRIDGE['emap']},
               {'role': 'assistant', 'content': 'BASLINJE 1'},
               {'role': 'user', 'content': 'Gör om baslinjen med 2019 som basår.'},
               {'role': 'assistant', 'content': 'BASLINJE 2'},
               {'role': 'user', 'content': BRIDGE['baslinje']},
               {'role': 'assistant', 'content': 'EVIDENS'}]
    assert replay_step.cut_before(history, 'baslinje') == history[:5]
    two = history[:9] + [{'role': 'assistant', 'content': 'EVIDENS 1'},
                         {'role': 'user', 'content': BRIDGE['baslinje'] + '\n'},
                         {'role': 'assistant', 'content': 'EVIDENS 2'}]
    assert replay_step.cut_before(two, 'evidens') == two[:11]


@pytest.mark.parametrize('rounds', [0, 1, 3])
def test_the_intake_answer_is_found_whatever_the_number_of_rounds(rounds):
    history = [{'role': 'user', 'content': 'Åtgärd'}]
    for k in range(rounds):
        history += [{'role': 'assistant', 'content': f'Fråga {k}'},
                    {'role': 'user', 'content': 'Svaret.'}]
    history += [{'role': 'assistant', 'content': 'ÅTGÄRDSPROFIL'},
                {'role': 'user', 'content': BRIDGE['intake']}]
    assert replay_step.intake_answer(history) == ('Svaret.' if rounds else None)


def test_an_analysis_that_never_reached_the_step_is_refused():
    history = [{'role': 'user', 'content': 'Åtgärd'},
               {'role': 'assistant', 'content': 'ÅTGÄRDSPROFIL'},
               {'role': 'user', 'content': BRIDGE['intake']},
               {'role': 'assistant', 'content': 'EMAP'}]
    with pytest.raises(ValueError, match='kom aldrig fram till baslinje'):
        replay_step.cut_before(history, 'baslinje')
    assert replay_step.cut_before(history, 'emap') == history[:3]
    with pytest.raises(ValueError, match='okänt steg'):
        replay_step.cut_before(history, 'baslinjen')


def test_through_before_the_step_is_refused():
    with pytest.raises(ValueError, match='ligger före'):
        replay_step.steps_to_run('kalkyl', 'evidens')
    assert replay_step.steps_to_run('intake', 'kalkyl') == ['emap', 'baslinje', 'evidens', 'kalkyl']


@pytest.mark.karlstad
def test_a_stale_repeat_from_an_earlier_replay_does_not_count(app, saved, tmp_path, monkeypatch):
    """Same --out twice; the second time every repeat fails at evidens. The
    first replay's kalkyl_meta.json must not stand in for the failed one."""
    out, _ = _replay(app, saved, tmp_path, 'baslinje', n=2)
    assert len(compare_runs.collect([out])['bilpool']) == 2
    from caia.web import app as A
    monkeypatch.setattr(A, 'run_evidens', lambda h, **_: (_ for _ in ()).throw(
        api_client.ModelOutputError('stopp')))
    _, rows = _replay(app, saved, tmp_path, 'baslinje', n=2)
    assert [r['ok'] for r in rows] == [False, False]
    assert [r['net'] for r in rows] == [None, None]
    assert compare_runs.collect([out]) == {}


@pytest.mark.karlstad
def test_a_shorter_chain_into_the_same_out_keeps_no_old_headline(app, saved, tmp_path):
    """emap through kalkyl, then emap through emap only, into the same --out:
    the second has no kalkyl, so it has no headline, and nothing older counts."""
    out = tmp_path / 'samma'
    replay_step.replay(app.app, saved, 'emap', 2, out, evidens_mode='single')
    assert len(compare_runs.collect([out])['bilpool']) == 2
    rows = replay_step.replay(app.app, saved, 'emap', 2, out, through='emap',
                              evidens_mode='single')
    assert [r['ok'] for r in rows] == [True, True]
    assert [r['net'] for r in rows] == [None, None]
    assert compare_runs.collect([out]) == {}
    for i in (1, 2):
        assert sorted(p.name for p in (out / f'bilpool-r{i}').iterdir()) == [
            'emap.md', 'history.json', 'intake.md', 'usage.jsonl']


@pytest.mark.karlstad
def test_the_printed_spread_is_this_replays_only(app, saved, tmp_path, capsys):
    out = tmp_path / 'samma'
    replay_step.replay(app.app, saved, 'baslinje', 3, out, evidens_mode='single')
    capsys.readouterr()
    replay_step.replay(app.app, saved, 'baslinje', 1, out, evidens_mode='single')
    printed = capsys.readouterr().out
    assert re.search(r'^bilpool\s+net\s+1\s', printed, re.MULTILINE), printed
    # The older repeats are still there for compare_runs --spread to read.
    assert len(compare_runs.collect([out])['bilpool']) == 3


@pytest.mark.karlstad
def test_replaying_an_earlier_repeat_into_its_own_directory_is_refused(app, saved, tmp_path):
    out, _ = _replay(app, saved, tmp_path, 'baslinje', n=1)
    rep = out / 'bilpool-r1'
    before = sorted(p.name for p in rep.iterdir())
    with pytest.raises(ValueError, match='skulle skrivas över'):
        replay_step.replay(app.app, rep, 'kalkyl', 1, out, name='bilpool')
    assert sorted(p.name for p in rep.iterdir()) == before


# --- cost ------------------------------------------------------------------

@pytest.mark.karlstad
def test_each_repeat_meters_its_own_calls(app, saved, tmp_path):
    out, rows = _replay(app, saved, tmp_path, 'baslinje', n=3, parallel=3)
    for r in rows:
        lines = (out / r['dir'] / 'usage.jsonl').read_text(encoding='utf-8').splitlines()
        recs = [json.loads(line) for line in lines]
        assert [(x['package'], x['step']) for x in recs] == [(r['dir'], 'baslinje'),
                                                             (r['dir'], 'evidens')]
        # The step's own cost is baslinje's; the total adds evidens after it.
        assert r['usd_step'] == pytest.approx(0.04) and r['usd'] == pytest.approx(0.12)
        assert r['calls'] == 2
    summary = [json.loads(line) for line in
               (out / 'summary.jsonl').read_text(encoding='utf-8').splitlines()]
    assert summary == rows
    log = (out / 'run.log').read_text(encoding='utf-8')
    assert 'Kostnad per steg' in log and 'Spridning' in log


def test_the_estimate_adds_up_the_steps_that_will_run(tmp_path):
    rows = [{'step': 'intake', 'usd': 0.1}, {'step': 'baslinje', 'usd': 0.2},
            {'step': 'evidens_part', 'usd': 0.3}, {'step': 'evidens_part', 'usd': 0.3},
            {'step': 'evidens_merge', 'usd': 0.5}, {'step': 'kalkyl_extract', 'usd': 0.2},
            {'step': 'qa', 'usd': 0.6}, {'step': 'emap', 'usd': None}]
    (tmp_path / 'usage.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n',
                                          encoding='utf-8')
    assert replay_step.estimate(tmp_path, {'evidens', 'kalkyl'}) == pytest.approx(1.3)
    assert replay_step.estimate(tmp_path, {'baslinje', 'evidens', 'kalkyl'}) == pytest.approx(1.5)
    assert replay_step.estimate(tmp_path / 'saknas', {'kalkyl'}) is None
    # A replay's usage.jsonl has only the steps it ran: no estimate, not 0.
    assert replay_step.estimate(tmp_path, {'rapport'}) is None


@pytest.mark.karlstad
def test_estimate_only_on_the_command_line_needs_no_key_and_runs_nothing(
        app, saved, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    out = tmp_path / 'aldrig'
    monkeypatch.setattr(sys, 'argv', ['replay_step.py', str(saved), 'baslinje', '--n', '4',
                                      '--estimate'])
    assert replay_step.main() == 0
    # The saved analysis's baslinje and evidens calls cost 0.12: 4 repeats, 0.48.
    assert '0.12 USD per omkörning (baslinje, evidens, kalkyl), 0.48 USD för 4' in \
        capsys.readouterr().out
    assert not out.exists() and not any(app.calls.values())
    monkeypatch.setattr(sys, 'argv', ['replay_step.py', str(saved), 'baslinje', '--out', str(out)])
    assert replay_step.main() == 2  # without --estimate and without a key: refused
    assert not out.exists()
    monkeypatch.setattr(sys, 'argv', ['replay_step.py', str(saved), 'baslinje'])
    assert replay_step.main() == 2  # nowhere to write
    assert not any(app.calls.values())


# --- the spread summary ------------------------------------------------------

def _run(root: Path, name: str, net, terr=None, cons=None, det=True):
    d = root / name
    d.mkdir(parents=True)
    head = {'net': net, 'terr': terr if terr is not None else net,
            'cons': cons if cons is not None else net}
    (d / 'kalkyl_meta.json').write_text(json.dumps({'deterministic': det, 'headline': head}),
                                        encoding='utf-8')


def test_spread_groups_repeats_by_package_and_gives_min_median_max_ratio(tmp_path):
    for i, net in enumerate([42.0, 129.0, 90.0, 60.0], start=1):
        _run(tmp_path, f'resecentrum-r{i}', net)
    _run(tmp_path, 'resecentrum-r5', 999.0, det=False)
    _run(tmp_path, 'laddning-r1', -5.0, terr=10.0)
    _run(tmp_path, 'laddning-r2', 20.0, terr=30.0)
    runs = compare_runs.collect([tmp_path])
    assert set(runs) == {'resecentrum', 'laddning'}
    s = compare_runs.spread(runs['resecentrum'])
    assert (s['n'], s['llm']) == (5, 1)  # the language model's number is left out
    assert s['net'] == {'n': 4, 'min': 42.0, 'median': 75.0, 'max': 129.0,
                        'ratio': pytest.approx(129 / 42)}
    lad = compare_runs.spread(runs['laddning'])
    assert lad['net']['ratio'] is None  # a negative minimum: no ratio
    assert lad['terr']['ratio'] == pytest.approx(3.0)
    text = compare_runs.format_spread(runs)
    row = next(ln for ln in text.splitlines() if ln.startswith('resecentrum'))
    assert re.search(r'net\s+4\s+42\.0\s+75\.0\s+129\.0\s+3\.07', row)
    assert '1 av 5 körningar räknades av språkmodellen' in text


def test_spread_reads_several_run_batch_runs_of_the_same_packages(tmp_path):
    """N plain run_batch runs: package directories without -rN, one per run."""
    for k, net in enumerate([10.0, 30.0, 20.0]):
        _run(tmp_path / f'run{k}', 'bilpool', net)
    s = compare_runs.spread(compare_runs.collect(
        [tmp_path / 'run0', tmp_path / 'run1', tmp_path / 'run2'])['bilpool'])
    assert (s['net']['min'], s['net']['median'], s['net']['max']) == (10.0, 20.0, 30.0)


def test_spread_on_the_command_line(tmp_path, capsys):
    _run(tmp_path, 'bilpool-r1', 10.0)
    _run(tmp_path, 'bilpool-r2', 25.0)
    assert compare_runs.main(['compare_runs.py', '--spread', str(tmp_path)]) == 0
    assert '2.50' in capsys.readouterr().out
    assert compare_runs.main(['compare_runs.py', '--spread', str(tmp_path / 'tom')]) == 1
