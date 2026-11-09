"""tools/step_readout.py through compare_runs.py --step / --tid.

Facit is real saved analyses from 2026-10-13 (tests/fixtures/readouts/):
the återbruk package run on the branch twice (efter, efter2; headlines 409
and 261 ton) and once on main (fore), the laddpunkter package on the branch
twice (150 and 175 ton). The numbers asserted below were read by hand from
the files. A pair that does not differ is made by copying one run: the
readout must then report no source coming and going and every number equal,
so a green run does not depend on the pairs happening to differ.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from caia import api_client
from caia.agents.evidens_split import MERGE_MAX_OUTPUT

NEXT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEXT / 'tools'))

import compare_runs  # noqa: E402
import step_readout as sr  # noqa: E402

FIX = Path(__file__).resolve().parent / 'fixtures' / 'readouts'


def cli(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = compare_runs.main(['compare_runs.py', *args])
    return code, buf.getvalue()


def section(text: str, package: str) -> str:
    """One package's block of a readout."""
    parts = text.split('== ')
    return next('== ' + p for p in parts if p.startswith(package))


@pytest.fixture
def same_twice(tmp_path):
    """The same real analysis twice: a pair that does not differ."""
    for name in ('a', 'b'):
        shutil.copytree(FIX / 'efter2' / '02-aterbruk', tmp_path / name / '02-aterbruk')
    return tmp_path


# --- step 2 ---------------------------------------------------------------------

def test_emap_pair_that_differs():
    code, out = cli('--step', 'emap', str(FIX / 'efter'), str(FIX / 'efter2'), '--paket', '02-aterbruk')
    assert code == 0
    assert 'Antal källor: [1] 4, [2] 3' in out
    # The material is three sources in efter and one in efter2. One source
    # against three categories is not the same source, so none of them is
    # matched: they come and go, and the readout points at the likely pairs
    # instead of comparing their numbers.
    lines = out.splitlines()
    k = {l.split()[0]: l for l in lines if l.startswith('  K') and '(i ' in l}
    assert 'betong- och stommaterial' in k['K1'] and '(i [1] av 2' in k['K1']
    assert 'stål' in k['K2'] and '(i [1] av 2' in k['K2']
    assert 'byggskivor' in k['K3'] and '(i [1] av 2' in k['K3']
    assert 'Demontering' in k['K4'] and 'i alla 2' in k['K4'] and '[2] nr 2' in k['K4']
    assert 'Tillverkning av nyproducerat byggmaterial' in k['K5'] and '(i [2] av 2' in k['K5']
    assert 'Byggavfall' in k['K6'] and '(i [2] av 2' in k['K6']
    assert 'Kommer och går: K1, K2, K3, K5, K6' in out
    assert 'K1 och K5 är aldrig med samtidigt och liknar varandra' in out
    assert 'K4 och' not in out and 'K6 är aldrig' not in out and 'och K6' not in out
    # The handling source is the same source with another mechanism and type.
    assert 'mekanism: [1] Improve ΔEF  [2] Avoid ΔA  SKILJER' in out
    assert 'utsläppstyp: [1] territoriella  [2] konsumtionsbaserade  SKILJER' in out


def test_two_emission_types_read_whole_and_in_one_order():
    # Step 2 may write one source with two types since the split rule
    # (2026-10-15); the readout must not cut it to "territoriella och" or
    # count the reverse order as a difference.
    both = sr._emission_type('territoriella och konsumtionsbaserade')
    assert both == 'territoriella och konsumtionsbaserade'
    assert sr._emission_type('Konsumtionsbaserade och territoriella utsläpp') == both
    assert sr._emission_type('territoriella') == 'territoriella'
    assert sr._emission_type('konsumtionsbaserade (uppströms, inte territoriella)') == 'konsumtionsbaserade'
    assert sr._emission_type('konsumtionsbaserade, inte territoriella') == 'konsumtionsbaserade'
    assert sr._emission_type('ingen direkt (enabler)') == 'ingen direkt'
    assert sr._emission_type('båda (ANTAGANDE: ...)') == 'båda'


def test_emap_pair_that_does_not_differ(same_twice):
    code, out = cli('--step', 'emap', str(same_twice / 'a'), str(same_twice / 'b'))
    assert code == 0
    assert 'Antal källor: [1] 3, [2] 3' in out
    assert 'Kommer och går: inga, samma källor varje gång' in out
    assert 'SKILJER' not in out


def test_emap_matches_by_name_not_number():
    rows = [sr.read_emap((FIX / r / '04-laddpunkter' / 'emap.md').read_text(encoding='utf-8'))
            for r in ('efter', 'efter2')]
    groups = sr.align([[d['name'] for d in r] for r in rows])
    # Electricity for charging is driver 3 in efter and driver 2 in efter2.
    el = next(g for g in groups if len(g) == 2 and 'Elanvändning' in rows[0][g[0]]['name'])
    assert rows[0][el[0]]['number'] == 3 and rows[1][el[1]]['number'] == 2


# --- step 3 ---------------------------------------------------------------------

def _driver(rows, word):
    return next(d for d in rows if word in d['name'])


def test_baslinje_numbers_read_as_written():
    efter = sr.read_baslinje((FIX / 'efter' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8'))
    efter2 = sr.read_baslinje((FIX / 'efter2' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8'))
    assert len(efter) == 4 and len(efter2) == 3   # each source once, not nuläge and BAU twice
    betong = _driver(efter, 'betong')
    assert (betong['a0'], betong['ef0'], betong['nuläge_år']) == (3400, 180, 2023)
    # "+0,5 %/år" and "-2,5 %/år": the decimal comma is not where the value ends.
    assert (betong['g_a_medel'], betong['g_ef_medel']) == (0.5, -2.5)
    material = _driver(efter2, 'nyproducerat')
    assert (material['a0'], material['ef0']) == (3900, 0.6)
    assert (material['g_a_låg'], material['g_a_medel'], material['g_a_hög']) == (-2, -0.5, 1.5)
    # 3 400 ton x 180 kg/ton and 3 900 ton x 0,6 kg/kg, both in ton CO2e.
    assert betong['e0_ton'] == pytest.approx(612)
    assert material['e0_ton'] == pytest.approx(2340)
    fore = sr.read_baslinje((FIX / 'fore' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8'))
    assert _driver(fore, 'Tillverkning')['g_a_medel'] == 0.0   # "medel: 0 %/år": a zero, not missing
    avfall = _driver(efter2, 'Byggavfall')
    assert avfall['e0_ton'] == pytest.approx(150)   # 600 ton x 0,25 kg/kg
    # 2030 on the medel trends from 2023: the engine's formula.
    assert material['e2030_ton'] == pytest.approx(2340 * 0.995 ** 7 * 0.98 ** 7)


def test_baslinje_pair_that_differs():
    code, out = cli('--step', 'baslinje', str(FIX / 'efter'), str(FIX / 'efter2'), '--paket', '02-aterbruk')
    assert code == 0
    blocks = out.split('\n  K')
    k4 = next(b for b in blocks if b.startswith('4 Demontering') and 'a0 ' in b)
    # The handling source is in both: per-field numbers, units said when they differ.
    assert 'a0_enhet: [1] tonkm/år' in k4 and '[2] ton/år' in k4 and 'SKILJER' in k4
    assert 'a0         [1] 10 000  [2] 120   min 120  median 5 060  max 10 000  max/min 83.33' in k4
    assert 'e0_ton     [1] 1.2  [2] 6   min 1.2  median 3.6  max 6  max/min 5' in k4
    assert 'nuläge_år  [1] 2023  [2] 2023   lika' in k4 and 'nuläge_år  [1] 2023  [2] 2023   lika  max/min' not in k4
    # A source in one run only shows its own numbers.
    k1 = next(b for b in blocks if b.startswith('1 Nyproducerat') and 'a0 ' in b)
    assert 'a0         [1] 3 400\n' in k1 and 'e0_ton     [1] 612\n' in k1
    assert 'Summa e0_ton per körning: [1] 3 478 över 4 källor, [2] 2 496 över 3 källor' in out
    assert 'inte en baslinje' in out


def test_baslinje_pair_that_does_not_differ(same_twice):
    code, out = cli('--step', 'baslinje', str(same_twice / 'a'), str(same_twice / 'b'))
    assert code == 0
    assert 'Kommer och går: inga' in out
    assert 'SKILJER' not in out and 'max/min' not in out
    fields = [l for l in out.splitlines() if l.startswith('    ') and '[1]' in l]
    assert fields and all(l.rstrip().endswith('lika') for l in fields)


def test_missing_field_is_counted_not_dropped(tmp_path):
    text = (FIX / 'efter2' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8')
    (tmp_path / 'a' / 'p').mkdir(parents=True)
    (tmp_path / 'b' / 'p').mkdir(parents=True)
    (tmp_path / 'a' / 'p' / 'baslinje.md').write_text(text, encoding='utf-8')
    (tmp_path / 'b' / 'p' / 'baslinje.md').write_text(text.replace('  EF0: 0,6\n', '', 1),
                                                     encoding='utf-8')
    code, out = cli('--step', 'baslinje', str(tmp_path / 'a'), str(tmp_path / 'b'))
    assert code == 0
    assert 'ef0        [1] 0.6  [2] -   lika  saknas i 1' in out
    assert 'e0_ton     [1] 2 340  [2] -   lika  saknas i 1' in out


def test_units_that_do_not_go_together_are_said():
    assert sr.to_ton(3900, 'ton/år', 0.6, 'kg CO2e/kg material') == pytest.approx(2340)
    assert sr.to_ton(2.4e7, 'km/år', 0.16, 'kg CO2e/km') == pytest.approx(3840)
    assert sr.to_ton(150, 'MWh/år', 50, 'g CO2e/kWh') == pytest.approx(7.5)
    assert sr.to_ton(1e4, 'tonkm/år', 0.12, 'kg CO2e/tonkm') == pytest.approx(1.2)
    assert sr.to_ton(20_000, 'm²/år', 0.6, 'kg CO2e/kg') is None
    assert sr.to_ton(5, 'st', 1, 'ej tillämplig') is None


@pytest.mark.parametrize('text,value', [
    ('0 %/år', 0.0), ('-0,5 %/år (konstant yta)', -0.5), ('+1,5 %/år', 1.5),
    ('−7 %/år (mot 30 g/kWh 2030)', -7.0), ('0,6', 0.6), ('0 (ingen i dag; 2030 ca 120 bilar)', 0.0),
    ('cirka 3 900 ton/år', 3900.0), ('2,4e7 (24 miljoner km)', 2.4e7), ('1,0e4 tonkm/år', 1e4),
    ('0,05', 0.05), ('ingen siffra', None),
])
def test_lead_reads_zero_and_sign(text, value):
    assert sr.lead(text) == value


def test_trend_on_one_line():
    t, notes = sr._trends('  BAU_trend_A (g_A): låg: -2 %/år, medel: 0 %/år, hög: 1 %/år\n'
                          '  BAU_trend_EF (g_EF):\n    - låg: -1 %/år\n    - medel: -3 %/år\n'
                          '    - hög: -6 %/år\n  BAU_årpunkter: [2026, 2030]\n')
    assert t == {'g_a_låg': -2, 'g_a_medel': 0, 'g_a_hög': 1,
                 'g_ef_låg': -1, 'g_ef_medel': -3, 'g_ef_hög': -6}
    assert notes == []


def test_trend_level_without_colon_and_with_a_parenthesis():
    t, notes = sr._trends('- BAU_trend_A:\n  - låg -2 %/år\n  - medel (trolig): -0,5 %/år\n'
                          '  - **hög**: +1,5 %/år\n- Kommentar: hög 40 %\n')
    assert t == {'g_a_låg': -2, 'g_a_medel': -0.5, 'g_a_hög': 1.5}
    assert notes == []


@pytest.mark.parametrize('text,value,note', [
    # A year or a level is never the trend.
    ('2023–2026 0 %/år', 0.0, None),
    ('+34 MWh/år', None, 'ingen %-trend på raden'),
    ('-2 %/år (fossil andel 82 %)', -2.0, None),
    # Two phases on one line: the per-year one is read and the line is said.
    ('0 % till 2026, sedan -10 %/år', -10.0, 'flera trender på raden (-10, 0); läst -10'),
    ('-1 %/år till 2026, sedan -4 %/år', -1.0, 'flera trender på raden (-1, -4); läst -1'),
    ('1–2 %/år', 1.0, 'spann 1 till 2 %'),
])
def test_trend_value(text, value, note):
    assert sr.trend_value(text) == (value, note)


def test_trend_notes_reach_the_readout(tmp_path):
    text = (FIX / 'efter2' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8')
    row = sr.read_baslinje(text)[0]
    assert not row.get('notes')
    body = text.replace('- medel: -0,5 %/år', '- medel: 0 % till 2026, sedan -10 %/år', 1)
    assert body != text
    row = sr.read_baslinje(body)[0]
    assert row['g_a_medel'] == -10
    assert any('g_a_medel: flera trender' in n for n in row['notes'])


# --- step 1 ---------------------------------------------------------------------

def test_intake_questions_from_real_history():
    h = json.loads((FIX / 'efter2' / '04-laddpunkter' / 'history.json').read_text(encoding='utf-8'))
    rounds = sr.intake_questions(h)
    assert [q for q, _ in rounds[0]] == ['Omfattning (viktigast)', 'Ägare och utformning',
                                         'Mognad och kontext']


def test_intake_numbered_profiles_are_not_questions():
    turn = ('Jag delar åtgärden i två:\n1. **Krav på laddbara tjänstebilar.**\n'
            '2. **Laddinfrastruktur.**\n\n## Frågor\n1. **Vad omfattar kravet?** Alla bilar?\n'
            '2. **Körsträckor:** hur långt?\n')
    h = [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': turn},
         {'role': 'user', 'content': 'svar'}, {'role': 'assistant', 'content': 'ÅTGÄRDSPROFIL'},
         {'role': 'user', 'content': 'Profilen är godkänd. Fortsätt med EMAP-analysen.'}]
    assert [q for q, _ in sr.intake_questions(h)[0]] == ['Vad omfattar kravet?', 'Körsträckor']


def test_intake_pair_that_differs():
    code, out = cli('--step', 'intake', str(FIX / 'efter'), str(FIX / 'efter2'), '--paket', '04-laddpunkter')
    assert code == 0
    assert 'Ägare och utformning  (i [2] av 2)' in out
    # A range is kept whole: 0,6-0,8 cars per household is not 0,6.
    assert 'bilar          [1] 0.6/2 400  [2] 0.6-0.8/2 400-3 200  SKILJER' in out
    # A share is not a count: "5–10 % av bilarna" gets its own row.
    assert '% bilarna      [1] 5-10  [2] -  SKILJER' in out
    assert 'mkr            [1] 9  [2] 9\n' in out


def test_intake_pair_that_does_not_differ(same_twice):
    code, out = cli('--step', 'intake', str(same_twice / 'a'), str(same_twice / 'b'))
    assert code == 0
    assert 'Kommer och går: inga' in out and 'SKILJER' not in out


def test_unknown_step_and_no_runs(tmp_path):
    assert cli('--step', 'evidens', str(FIX / 'efter'))[0] == 2
    assert cli('--step', 'emap', str(tmp_path))[0] == 1


# --- time, length and cost --------------------------------------------------------

def test_limits_come_from_the_code():
    vercel = json.loads((NEXT / 'vercel.json').read_text(encoding='utf-8'))
    assert sr.vercel_limit_s() == vercel['builds'][0]['config']['maxDuration']
    effort = api_client.AGENT_MODELS['evidens_merge'][1]
    assert sr.merge_cap() == MERGE_MAX_OUTPUT + api_client.THINKING_HEADROOM[effort]
    assert sr.OUR_LIMIT_S == api_client.REQUEST_TIMEOUT_S


def test_run_log_counts_requests_not_the_evidens_wall_time():
    t = sr.parse_run_log((FIX / 'efter2' / 'run.log').read_text(encoding='utf-8'), '02-aterbruk')
    steps = [(q.step, q.seconds) for q in t.requests]
    assert ('evidens', 181.7) not in steps            # parts + merge, not one request
    assert ('evidens_merge', 91.8) in steps
    assert sorted(s for st, s in steps if st == 'evidens_part') == [75.7, 78.1, 89.8]
    assert ('qa', 273.9) in steps and ('kalkyl', 41.0) in steps
    assert [s for st, s in steps if st == 'intake'] == [30.9, 36.1]
    assert t.skipped == 0


def test_evidens_single_call_is_a_request():
    log = ('[10:00:00] p: intake  10.0s status=complete profiles=1\n'
           '[10:00:10] p: emap       5.0s 100 chars\n'
           '[10:00:20] p: baslinje   9.0s 100 chars\n'
           '[10:00:30] p: evidens: no drivers parsed, falling back to the single call\n'
           '[10:05:30] p: evidens   250.0s 100 chars\n')
    t = sr.parse_run_log(log, 'p')
    assert ('evidens', 250.0) in [(q.step, q.seconds) for q in t.requests]


def test_reused_run_log_reads_the_last_run():
    one = (FIX / 'efter2' / 'run.log').read_text(encoding='utf-8')
    second = one.replace('qa        273.9s', 'qa        120.0s')
    t = sr.parse_run_log(one + second, '02-aterbruk')
    assert t.skipped == 1
    assert [q.seconds for q in t.requests if q.step == 'qa'] == [120.0]
    # A replay of baslinje after a whole run: no DONE between, the chain
    # just starts over at an earlier step.
    replay = ('[11:00:00] 02-aterbruk: baslinje   99.0s 100 chars\n'
              '[11:02:00] 02-aterbruk: kalkyl     30.0s 100 chars\n')
    t = sr.parse_run_log(one.replace('DONE', 'xx') + replay, '02-aterbruk')
    assert t.skipped == 1 and [q.step for q in t.requests] == ['baslinje', 'kalkyl']


def test_time_readout_on_a_real_run():
    code, out = cli('--tid', str(FIX / 'efter2'), '--paket', '02-aterbruk')
    assert code == 0
    assert 'qa              273.9  NÄRA' in out
    assert 'evidens_part     89.8 (längst av 3) part 2' in out
    assert 'kalkyl, modellanropen: kalkyl_extract 40.9 = 40.9 s' in out
    assert 'sammanslagning 7636 av 26000 tokens (29%), 91.8 s, stop_reason end_turn' in out
    assert 'kostnad 2.41 USD (62% av 3.9), 11 modellanrop' in out
    assert 'TVÅ MODELLANROP' not in out and 'I TAKET' not in out


def test_two_calls_in_kalkyl_and_a_merge_at_the_cap(tmp_path):
    run = tmp_path / 'b' / 'p'
    run.mkdir(parents=True)
    (run / 'history.json').write_text('[]', encoding='utf-8')
    (tmp_path / 'b' / 'run.log').write_text(
        '[10:00:00] p: evidens merge 256.0s status=502 corrected=None\n'
        '[10:05:00] p: kalkyl    281.0s 100 chars\n', encoding='utf-8')
    rows = [{'step': 'evidens_merge', 'output': 26000, 'seconds': 256.0, 'stop_reason': 'max_tokens',
             'usd': 0.6}, {'step': 'kalkyl_extract', 'output': 3000, 'seconds': 77.0, 'usd': 0.1},
            {'step': 'kalkyl', 'output': 9000, 'seconds': 204.0, 'usd': 0.2}]
    (run / 'usage.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    code, out = cli('--tid', str(tmp_path / 'b'))
    assert code == 0
    assert 'evidens_merge   256.0  NÄRA' in out
    assert 'kalkyl          281.0  ÖVER VÅR GRÄNS' in out
    assert 'kalkyl_extract 77.0 + kalkyl 204.0 = 281.0 s  TVÅ MODELLANROP  ÖVER VÅR GRÄNS' in out
    assert 'sammanslagning 26000 av 26000 tokens (100%), 256.0 s, stop_reason max_tokens  I TAKET' in out
    assert 'kostnad 0.90 USD' in out


def test_missing_usage_and_log_are_said(tmp_path):
    shutil.copytree(FIX / 'efter' / '02-aterbruk', tmp_path / 'x' / '02-aterbruk')
    code, out = cli('--tid', str(tmp_path / 'x'))
    assert code == 0
    assert 'ingen rad i run.log för den här analysen: tiden okänd.' in out
    assert 'ingen usage.jsonl' in out


# --- the reviewer's cases ------------------------------------------------------------

@pytest.mark.parametrize('a,b,same', [
    ('elanvändning', 'bränsleanvändning', False),      # a shared generic tail is not a match
    ('bensinanvändning', 'dieselanvändning', False),
    ('byggmaterial', 'isoleringsmaterial', False),
    ('material', 'byggmaterial', False),               # nor a generic word inside one
    ('byggavfall', 'rivningsavfall', True),            # what a compound is sits last
    ('bygg', 'byggavfall', True),
    ('laddning', 'laddningen', True),
])
def test_same_word(a, b, same):
    assert sr._same_word(a, b) is same


def test_names_sharing_only_a_generic_tail_are_not_one_source():
    assert sr.similarity('Elanvändning för laddning av bilar',
                         'Bränsleanvändning i fossila personbilar') < sr.MATCH
    assert sr.similarity('Elanvändning för laddning', 'Elanvändning vid laddning') >= sr.MATCH


def test_intake_questions_in_a_bullet_list():
    turn = ('Några frågor innan jag går vidare:\n'
            '- **Hur många laddpunkter?** Ungefär räcker.\n'
            '- Vem äger dem, kommunen eller bostadsbolaget?\n'
            '- Budgeten är 9 Mkr.\n')
    h = [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': turn},
         {'role': 'user', 'content': 'svar'}, {'role': 'assistant', 'content': 'ÅTGÄRDSPROFIL'},
         {'role': 'user', 'content': 'Profilen är godkänd. Fortsätt med EMAP-analysen.'}]
    asked = sr.intake_questions(h)[0]
    assert [q for q, _ in asked][0] == 'Hur många laddpunkter?'
    assert len(asked) == 2   # the budget line is not a question


def test_scope_only_from_its_own_field():
    md = ('ÅTGÄRDSPROFIL\n*Omfattning:* 120 laddpunkter, cirka 30 % av hushållen.\n'
          '*Mognad:* beslutad 2025, 9 Mkr.\n')
    [(has, pairs)] = sr.omfattning(md)
    assert has and pairs == [('laddpunkter', (120.0, None)), ('% hushållen', (30.0, None))]
    assert sr.omfattning('ÅTGÄRDSPROFIL\n*Mognad:* 9 Mkr\n') == [(False, [])]
    [(_, pairs)] = sr.omfattning('ÅTGÄRDSPROFIL\n*Omfattning:* 30 % av de boende, 2 400 bilar i området.\n')
    assert pairs == [('% boende', (30.0, None)), ('bilar', (2400.0, None))]


def test_evidens_after_a_failed_split_is_a_request():
    log = ('[10:00:00] p: evidens part 1  80.0s status=200\n'
           '[10:01:30] p: evidens merge failed: 502\n'
           '[10:06:30] p: evidens   200.0s 100 chars\n')
    t = sr.parse_run_log(log, 'p')
    assert [(q.step, q.seconds) for q in t.requests] == [('evidens_part', 80.0), ('evidens', 200.0)]


def test_co2_written_with_subscript_and_prefixed_units():
    assert sr.to_ton(100, 'MWh/år', 20, 'g CO₂e/kWh') == pytest.approx(2)
    text = ('### Drivare 1: Körning\n- A0: 2 Mkm/år\n- A0_enhet: km/år\n- EF0: 0,16\n'
            '- EF0_enhet: kg CO2e/km\n- Nuläge_år: 2023\n')
    [row] = sr.read_baslinje(text)
    assert row['a0'] == 2
    assert any('prefix' in n for n in row['notes'])
    # The same prefix as the unit field is no note: kWh under kWh/år.
    [row] = sr.read_baslinje(text.replace('2 Mkm/år', '40 000 kWh/år').replace('km/år', 'kWh/år')
                             .replace('kg CO2e/km', 'kg CO2e/kWh'))
    assert row['a0'] == 40000 and not row.get('notes')


def test_two_profiles_number_their_drivers_from_one_each():
    # The tjänstebilar measure is split in two profiles, drivers 1-3 in each.
    text = (FIX / 'efter' / '01-tjanstebilar' / 'baslinje.md').read_text(encoding='utf-8')
    rows = sr.read_baslinje(text)
    assert len(rows) == 6
    assert [r['label'] for r in rows] == ['nr 1', 'nr 2', 'nr 3', 'P2 nr 1', 'P2 nr 2', 'P2 nr 3']
    pendling = _driver(rows, 'privatbilar')
    assert pendling['profile'] == 2 and pendling['number'] == 1 and pendling['a0'] is not None
    assert _driver(rows, 'tjänstebilar (bensin')['a0'] != pendling['a0']
    emap = sr.read_emap((FIX / 'efter' / '01-tjanstebilar' / 'emap.md').read_text(encoding='utf-8'))
    assert [(d['profile'], d['number']) for d in emap] == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]


def test_one_profile_with_nulage_and_bau_blocks_is_one_profile():
    rows = sr.read_baslinje((FIX / 'efter' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8'))
    assert {r['profile'] for r in rows} == {1} and [r['label'] for r in rows] == ['nr 1', 'nr 2', 'nr 3', 'nr 4']


def test_same_run_name_under_two_parents_is_said_everywhere(tmp_path):
    for parent, pkgs in (('x', ('02-aterbruk', '04-laddpunkter')), ('y', ('02-aterbruk',))):
        for pkg in pkgs:
            shutil.copytree(FIX / 'efter' / pkg, tmp_path / parent / 'fore' / pkg)
    runs = sr.find_runs([tmp_path / 'x' / 'fore', tmp_path / 'y' / 'fore'], 'baslinje.md')
    assert [r.label for r in runs['02-aterbruk']] == ['x/fore/02-aterbruk', 'y/fore/02-aterbruk']
    # Only x has this package, but "fore" alone would not say which one.
    assert [r.label for r in runs['04-laddpunkter']] == ['x/fore/04-laddpunkter']
    plain = sr.find_runs([FIX / 'efter', FIX / 'efter2'], 'baslinje.md')
    assert [r.label for r in plain['02-aterbruk']] == ['efter/02-aterbruk', 'efter2/02-aterbruk']


def test_bau_block_with_a_word_more_in_its_name_is_the_same_source():
    # Main 13/10: nuläge says "... återbrukat material (motverkande effekt)",
    # BAU says "... återbrukat material". One source, not a second profile.
    rows = sr.read_baslinje((FIX / 'ref' / '02-aterbruk' / 'baslinje.md').read_text(encoding='utf-8'))
    assert [r['label'] for r in rows] == ['nr 1', 'nr 2', 'nr 3']
    handling = rows[2]
    assert handling['a0'] == 2000 and handling['g_a_medel'] is not None


def _baslinje_text(profiles):
    """A baslinje answer: per profile, every driver's nuläge block, then
    every driver's BAU block (names may differ in BAU)."""
    out = []
    for nulage, bau in profiles:
        out += [f'Drivare {i}: {n}\n  A0: {10 * i}\n' for i, n in enumerate(nulage, 1)]
        out += [f'Drivare {i}: {n}\n  BAU_trend_A:\n    - medel: -1 %/år\n' for i, n in enumerate(bau, 1)]
    return '\n'.join(out)


def test_second_profile_named_like_the_first_is_not_merged():
    p1 = ['Elanvändning för laddning av tjänstebilar', 'Körsträcka med fossildrivna tjänstebilar']
    p2 = ['Elanvändning för laddning av privatbilar', 'Körsträcka med fossildrivna privatbilar']
    assert sr.similarity(p1[0], p2[0]) >= sr.MATCH          # the case the rule must survive
    rows = sr.read_baslinje(_baslinje_text([(p1, p1), (p2, p2)]))
    assert [r['label'] for r in rows] == ['nr 1', 'nr 2', 'P2 nr 1', 'P2 nr 2']
    assert all(r['a0'] is not None and r['g_a_medel'] == -1 for r in rows)


def test_a_renamed_bau_block_after_the_first_does_not_start_a_profile():
    nulage = ['Körsträcka med fossildrivna tjänstebilar', 'Elanvändning för laddning', 'Tillverkning av batterier']
    bau = [nulage[0], 'Laddel i flottan', 'Batteritillverkning för nya bilar']
    rows = sr.read_baslinje(_baslinje_text([(nulage, bau)]))
    assert [r['label'] for r in rows] == ['nr 1', 'nr 2', 'nr 3']


def test_emap_drivers_never_repeat_within_a_profile():
    text = ('Drivare 1: Körsträcka med fossildrivna tjänstebilar\n  Mekanism: Shift\n'
            'Drivare 2: Elanvändning för laddning av tjänstebilar\n  Mekanism: Shift\n'
            'Drivare 1: Körsträcka med fossildrivna tjänstebilar vid pendling\n  Mekanism: Avoid\n')
    assert [(d['profile'], d['label']) for d in sr.read_emap(text)] == [(1, 'nr 1'), (1, 'nr 2'), (2, 'P2 nr 1')]
