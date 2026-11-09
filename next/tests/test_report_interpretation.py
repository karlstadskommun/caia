"""The report's short interpretation of the medel scenario ("Kort
tolkning_medel") is shown under the headline number and taken out of the
report body (Henric 2026-10-14). Run in node against the saved reports in
tests/fixtures, like test_key_points.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from test_key_points import _between
from test_report_row import _inline_script

pytestmark = pytest.mark.node

FIX = Path(__file__).parent / 'fixtures'


def _split(md: str) -> dict:
    js = _inline_script()
    program = (_between(js, 'const INTERP_LINE', 'function setHeroInterpretation(')
               + f'\nconsole.log(JSON.stringify(reportInterpretation({json.dumps(md)})));')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


def test_the_fixture_report_gives_the_medel_interpretation():
    md = (FIX / 'rapport.md').read_text()
    out = _split(md)
    assert out['text'].startswith('Åtgärden beräknas minska kommunens egna tjänstebilsutsläpp')
    assert out['text'].endswith('till stor del elektrifierad.')
    assert 'Kort tolkning' not in out['text']
    rest = out['rest']
    assert 'Kort tolkning_medel' not in rest
    # The other two scenarios keep theirs, and every number line is still there.
    assert 'Kort tolkning_min: I ett försiktigt scenario' in rest
    assert 'Kort tolkning_max: I ett optimalt scenario' in rest
    assert rest.count('Medel effekt/år') == md.count('Medel effekt/år')
    # Only that line and one of the blank lines around it are gone.
    kept = [l for l in md.splitlines() if not l.lstrip().startswith('Kort tolkning_medel')]
    assert len(kept) - len(rest.splitlines()) == 1
    assert [l for l in rest.splitlines() if l.strip()] == [l for l in kept if l.strip()]


def test_the_resecentrum_report_too():
    out = _split((FIX / 'rapport.resecentrum.md').read_text())
    assert out['text'].startswith('Effekten är störst under byggtiden, 2026–2028')
    assert 'Spannet för kumulativ nytta 2025–2030' in out['rest']


@pytest.mark.parametrize('line', [
    '  Kort tolkning_medel: Liten effekt.',
    '**Kort tolkning_medel:** Liten effekt.',
    '**Kort tolkning_medel**: Liten effekt.',
    '- Kort tolkning_medel: Liten effekt.',
    'Kort tolkning (medel): Liten effekt.',
    '**Kort tolkning_medel: Liten effekt.**',
])
def test_the_label_in_the_forms_the_models_write(line):
    md = f'Scenario_medel (mest sannolikt):\n  ΔE_2030_total (Netto): 5 ton\n{line}\n\nScenario_min (försiktigt):\n'
    out = _split(md)
    assert out['text'] == 'Liten effekt.'
    assert 'Liten effekt' not in out['rest']
    assert 'ΔE_2030_total (Netto): 5 ton' in out['rest']


def test_a_wrapped_interpretation_is_joined_up_to_the_blank_line():
    md = ('  Medel effekt/år (Netto/Total): 50 ton\n\n'
          '  Kort tolkning_medel: Första meningen.\n  Andra meningen.\n'
          '  Tredje meningen, om 8 % av hushållen.\n\n'
          'Scenario_min (försiktigt):\n  Kort tolkning_min: Försiktigt.\n')
    out = _split(md)
    assert out['text'] == 'Första meningen. Andra meningen. Tredje meningen, om 8 % av hushållen.'
    assert out['rest'] == ('  Medel effekt/år (Netto/Total): 50 ton\n\n'
                           'Scenario_min (försiktigt):\n  Kort tolkning_min: Försiktigt.\n')


def test_a_field_line_after_the_label_is_not_part_of_it():
    md = '  Kort tolkning_medel: Liten effekt.\n  Osäkerhetsnivå: hög\n'
    out = _split(md)
    assert out['text'] == 'Liten effekt.'
    assert out['rest'] == '  Osäkerhetsnivå: hög\n'


def test_the_text_on_the_line_after_the_label():
    out = _split('Kort tolkning_medel:\n  Liten effekt.\n\nNästa:\n')
    assert out['text'] == 'Liten effekt.'
    assert out['rest'] == 'Nästa:\n'


def test_a_report_without_one_is_left_as_it_is():
    md = '## Titel\n\nScenario_min (försiktigt):\n  Kort tolkning_min: Försiktigt.\n'
    out = _split(md)
    assert out == {'text': '', 'rest': md}
    assert _split('') == {'text': '', 'rest': ''}


def test_a_new_number_and_a_reset_clear_the_last_interpretation():
    """The kalkyl hero is drawn again on a recalculation, minutes before the
    new report: the old report's interpretation must not sit under the new
    number. Wiring is asserted on the script text, as the save test does."""
    js = _inline_script()
    hero = _between(js, 'function renderKalkylHero(', '\n}\n')
    reset = _between(js, 'function resetAll()', '\n}\n')
    assert "setHeroInterpretation('')" in hero
    assert "setHeroInterpretation('')" in reset
    # And it survives a page without the element (the stubs in test_client_ui).
    assert "if (!el) return;" in _between(js, 'function setHeroInterpretation(', '\n}\n')


def test_the_page_moves_it_under_the_number_only_when_there_is_one():
    """showReport: the interpretation goes to #heroInterp and out of the
    body when the hero card is shown; with no number it stays in the body."""
    js = _inline_script()
    show = _between(js, 'function showReport(', 'function keyMetricText(')
    interp = _between(js, 'const INTERP_LINE', '\nfunction showReport(')
    stub = """
const els = {};
function el(id) { return els[id] || (els[id] = {style: {display: 'none'}, innerHTML: '', textContent: '',
                                                 classList: {add() {}, remove() {}}}); }
const document = {getElementById: el};
function showAnalysisCard() {}
function updateHero(km) { el('heroCard').style.display = ''; }
function renderMarkdown(md) { return md; }
function plainTerms(t) { return t; }
// The text has no parts (test_report_view), so it is drawn whole.
function headingText(line) { return null; }
function trimBlock(lines) { return lines.join('\\n'); }
"""
    md = '## T\n\n  Kort tolkning_medel: Liten effekt.\n\nScenario_min (försiktigt):\n'
    program = stub + interp + '\n' + show + f"""
const out = {{}};
showReport({json.dumps(md)}, null);
out.noNumber = {{interp: el('heroInterp').innerHTML, shown: el('heroInterp').style.display, body: el('reportContent').innerHTML}};
showReport({json.dumps(md)}, {{net: 5}});
out.withNumber = {{interp: el('heroInterp').innerHTML, shown: el('heroInterp').style.display, body: el('reportContent').innerHTML}};
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = json.loads(subprocess.run(['node', f.name], check=True, capture_output=True, text=True).stdout)
    finally:
        os.unlink(f.name)
    assert out['noNumber'] == {'interp': '', 'shown': 'none', 'body': md}
    assert out['withNumber']['interp'] == 'Liten effekt.'
    assert out['withNumber']['shown'] == ''
    assert 'Liten effekt' not in out['withNumber']['body']
    assert out['withNumber']['body'] == '## T\n\nScenario_min (försiktigt):\n'
