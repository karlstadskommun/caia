""""Det viktigaste": the summary at the top of each step, run in node against
the saved step texts in tests/fixtures.

The points are read out of what the step produced, so these tests hold them
to the fixture's own numbers: a summary that says something the step did not
is worse than none.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from caia.evidence import parse_evidence
from test_report_row import _inline_script

pytestmark = pytest.mark.node

FIX = Path(__file__).parent / 'fixtures'


def _between(js: str, start: str, end: str) -> str:
    i = js.index(start)
    return js[i:js.index(end, i)]


def _functions() -> str:
    js = _inline_script()
    return '\n'.join([
        'const state = {mode: "potential"}; const AVG_WINDOW = [2026, 2030];',
        _between(js, 'function escapeHtml(s)', '// breaks:true'),
        _between(js, 'function readableNumber(', 'const FIELD_LABELS'),
        _between(js, 'function headingText(', '// The parts of a step'),
        'const DRIVER_LINE = /^\\s*(#{1,6}\\s*)?(\\*\\*)?\\s*Drivare\\s+\\d+\\s*:/m;',
        'function isRule(line) { return /^\\s*([-*_])(\\s*\\1){2,}\\s*$/.test(line); }',
        'function renderMarkdownWithChips(md) { return md; }',
        _between(js, 'function startsSentence(', '// The one place model text is sanitised'),
        _between(js, 'const EMAP_CLASS_LABELS', 'function emapRisk('),
        _between(js, 'function paramTitle(', 'function evidenceParamHtml('),
        _between(js, '// ---------- "Det viktigaste"', '// QA runs after the headline is drawn'),
    ])


def _run(expr: str) -> object:
    program = _functions() + f'\nconsole.log(JSON.stringify({expr}));'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


def _texts(points) -> list[str]:
    return [p if isinstance(p, str) else p['text'] for p in points]


def test_emap_names_the_emissions_the_measure_touches():
    md = (FIX / 'emap.dev.md').read_text()
    points = _texts(_run(f'emapKeyPoints(parseEmap({json.dumps(md)}))'))
    assert points[0].startswith('Åtgärden påverkar 3 utsläppskällor: Försäljning av nya varor')
    assert 'och Lokaler och galleri som möjliggörare.' in points[0]
    mech = [p for p in points if p.startswith('Sätt att minska')]
    assert mech and '(' in mech[0], mech


def test_baseline_gives_today_and_the_trend_without_the_measure():
    md = (FIX / 'baslinje.md').read_text()
    points = _texts(_run(f'baselineKeyPoints({json.dumps(md)}, "x")'))
    first = points[0]
    # The fixture: A0 3,0e6 km/år, EF0 0,13 kg CO2/km, medel -5 %/år and -2 %/år.
    assert '3 miljoner km/år' in first and '0,13 kg CO2/km' in first
    assert 'aktiviteten minskar 5 % per år' in first
    assert 'utsläppen per enhet minskar 2 % per år' in first
    # The enabler (A0 0) has no level of its own and is not listed as one.
    assert not any('Laddinfrastruktur' in p for p in points)
    assert points[-1] == 'Dataluckor och frågor till dig står i chatten.'


def test_an_assumed_level_says_so():
    md = (FIX / 'baslinje.md').read_text()
    marked = md.replace('A0: 3,0e6', 'A0: 3,0e6 (ANTAGANDE: omfattningen är antagen i åtgärdsprofilen)', 1)
    assert marked != md, 'the fixture changed; find its A0 line again'
    first = _texts(_run(f'baselineKeyPoints({json.dumps(marked)}, "x")'))[0]
    assert '3 miljoner km/år (antaget) med 0,13 kg CO2/km' in first
    plain = _texts(_run(f'baselineKeyPoints({json.dumps(md)}, "x")'))[0]
    assert 'antaget' not in plain


@pytest.mark.parametrize('value, words', [
    ('-0,02', 'minskar 2 % per år'),
    ('0,01 (1 %/år)', 'ökar 1 % per år'),
    ('−3 %/år', 'minskar 3 % per år'),
    ('0 %/år', 'oförändrad'),
    ('12', ''),            # neither a share nor a percent: not guessed
    ('1', ''),
    ('0,5 till 1 %/år', ''),
    ('0,5-1 %/år', ''),
    ('se kommentar', ''),
])
def test_a_trend_is_put_in_words_only_when_it_can_be_read(value, words):
    assert _run(f'trendWords({json.dumps(value)})') == words


def test_evidence_lists_the_assumptions_with_their_span():
    evidence = parse_evidence((FIX / 'evidens.md').read_text())
    points = _texts(_run(f'evidenceKeyPoints({json.dumps(evidence["drivers"])})'))
    assert points[0].startswith('Åtgärden påverkar')
    # The fixture: adoption 0,50 (0,25-0,85) as a share, ΔEF -0,10 kg CO2/km.
    assert any(p.endswith(': troligt 50 % (spann 25 % till 85 %).') for p in points), points
    assert any(': troligt -0,10 kg CO2/km (spann -0,08 till -0,13).' in p for p in points), points


def test_kalkyl_says_the_result_its_span_and_every_warning():
    meta = json.loads((FIX / 'kalkyl_meta.json').read_text())
    warn = 'Enheterna går inte ihop för drivare 1.'
    points = _run(f'kalkylKeyPoints({json.dumps(meta["headline"])}, {json.dumps(meta["span"])}, [{json.dumps(warn)}])')
    assert _texts(points)[0].startswith('Troligt resultat: ')
    assert {'text': warn, 'warn': True} in points


def test_qa_reads_the_verdict_and_its_remarks():
    md = (FIX / 'qa.md').read_text()
    verdict = _run(f'qaVerdict({json.dumps(md)})')
    assert verdict['status'] == 'varning'
    assert len(verdict['remarks']) == 6
    assert verdict['remarks'][0].startswith('Hela baslinjen')
    # Åtgärdsförslag are not remarks.
    assert not any(r.startswith('Hämta faktiska') for r in verdict['remarks'])
    points = _run(f'qaKeyPoints({json.dumps(verdict)})')
    assert points[0]['warn'] is True


def test_qa_ok_and_no_verdict():
    assert _run('qaVerdict("**QA-status:** ok\\n")')['status'] == 'ok'
    assert _run('qaVerdict("Ingen samlad bedömning här.")') is None
    assert _run('keyPointsHtml(qaKeyPoints(null))') == ''


def test_a_point_is_escaped():
    html = _run('keyPointsHtml(["<b>x</b>"])')
    assert '&lt;b&gt;' in html and '<b>x' not in html


def test_a_share_is_percent_for_all_three_values_or_none():
    p = {'name': 'x', 'detail': 'Andel', 'enhet': 'Andel i procent', 'med': '1', 'min': '0,5', 'max': '2'}
    points = _texts(_run(f'evidenceKeyPoints([{{parameters: [{json.dumps(p)}]}}])'))
    assert points[1] == 'Andel: troligt 1 % (spann 0,5 till 2).', points
    p = dict(p, enhet='andel', med='0,3', min='0,2', max='0,4')
    points = _texts(_run(f'evidenceKeyPoints([{{parameters: [{json.dumps(p)}]}}])'))
    assert points[1] == 'Andel: troligt 30 % (spann 20 % till 40 %).', points


def test_qa_remarks_are_the_remarks_only():
    md = """QA-status: ok (med smärre varningar)
QA-anmärkningar: inga
Frågor till miljöstrateg
- Fråga?
"""
    v = _run(f'qaVerdict({json.dumps(md)})')
    assert v == {'status': 'varning', 'remarks': [], 'suggestions': []}
    md = "QA-status: varning\nQA-anmärkningar:\n- Ett\n    - delpunkt\n- Två\n"
    assert _run(f'qaVerdict({json.dumps(md)})')['remarks'] == ['Ett', 'Två']


def test_qa_suggestions_are_read_apart_from_the_remarks():
    md = (FIX / 'qa.md').read_text()
    v = _run(f'qaVerdict({json.dumps(md)})')
    assert len(v['suggestions']) == 6
    assert v['suggestions'][0].startswith('Hämta faktiska')
    assert not any(s.startswith('Hela baslinjen') for s in v['suggestions'])


# ---------- the warning under the number ----------

def _gist(remark: str) -> str:
    js = _inline_script()
    program = (_functions() + '\nfunction plainTerms(t) { return t; }\n' +
               _between(js, 'const QA_GIST_MAX', 'function qaList(') +
               f'\nconsole.log(JSON.stringify(qaGist({json.dumps(remark)})));')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


def test_the_short_line_is_a_whole_sentence_or_nothing():
    # Henric 2026-10-15: the remark cut at 160 characters read as broken.
    remark = ('Kalkylen räknar bara 2026–2030, trots att evidenssteget anger effektår till och med 2040. '
              'Det kumulativa resultatet (245 / 899 / 2 109 ton) underskattar därför nyttan.')
    assert _gist(remark) == 'Kalkylen räknar bara 2026–2030, trots att evidenssteget anger effektår till och med 2040.'
    # "t.ex." does not end the sentence.
    assert _gist('Enheten är fel, t.ex. ton mot kg. Mer här.') == 'Enheten är fel, t.ex. ton mot kg.'
    long = 'Hela baslinjen vilar på tre kedjade antaganden ' + 'utan bekräftelse ' * 12 + 'från fordonsregister.'
    gist = _gist(long)
    assert gist == '' and '…' not in gist


# ---------- recalculating with QA's remarks ----------

def _recalc(expr: str):
    js = _inline_script()
    extra = '\n'.join([
        'const BRIDGE = {evidens: "Antagandena är godkända."};',
        _between(js, 'function recalcReasons()', 'function offerRecalc()'),
        _between(js, 'function headlineValue(h)', '// QA runs after the headline is drawn'),
        _between(js, 'function fmt(n)', '\n}\n') + '\n}\n',
    ])
    program = _functions() + '\n' + extra + f'\nconsole.log(JSON.stringify({expr}));'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


def test_the_reasons_are_qa_remarks_when_it_warns_and_every_calc_warning():
    assert _recalc('(state.qaVerdict = {status: "varning", remarks: ["A"]}, '
                   'state.lastKalkyl = {warnings: ["B"]}, recalcReasons())') == ['A', 'B']
    # QA ok: its remarks are not a reason, the calc's own warning still is.
    assert _recalc('(state.qaVerdict = {status: "ok", remarks: ["A"]}, '
                   'state.lastKalkyl = {warnings: ["B"]}, recalcReasons())') == ['B']
    assert _recalc('(state.qaVerdict = null, state.lastKalkyl = null, recalcReasons())') == []


def test_the_correction_turn_keeps_the_approved_assumptions():
    turn = _recalc('recalcTurn(["Enheterna går inte ihop."])')
    assert turn.startswith('Antagandena är godkända.')
    assert '- Enheterna går inte ihop.' in turn
    assert 'ändra dem inte' in turn


def test_the_outcome_says_before_and_after():
    assert '86 blev 215' in _recalc('recalcOutcome({net: 86}, {net: 215})')
    assert 'samma resultat' in _recalc('recalcOutcome({net: 86.04}, {net: 85.96})')
    assert 'språkmodellens' in _recalc('recalcOutcome({net: 86}, null)')
