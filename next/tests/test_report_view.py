"""The report in parts (2026-10-15, after the workshop 14/10): the
title, the report's own verdict with three levels under it, and every part of
the report as a row that opens with one click, with a line saying what is in
it. Run in node against the saved reports in tests/fixtures, like
test_key_points.

The view only regroups the text, so the first thing held is that nothing is
lost or moved between parts: a line the view drops is a line nobody reads.
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
REPORT = (FIX / 'rapport.md').read_text()
RESECENTRUM = (FIX / 'rapport.resecentrum.md').read_text()

PARTS = ['beskrivning', 'klimatnytta', 'mekanism', 'antaganden', 'tidsprofil',
         'osakerhet', 'rekommendation', 'kallor', 'bilaga']


def _lib() -> str:
    js = _inline_script()
    return '\n'.join([
        _between(js, 'function headingText(', 'const QUESTIONS_RE'),
        _between(js, 'function isRule(', '// The baslinje prompt names'),
        _between(js, 'function qaVerdict(', 'function qaKeyPoints('),
        _between(js, '// ---------- The report in parts ----------', '// ---------- The report in parts, drawn'),
    ])


def _run(expr: str):
    program = _lib() + f'\nconsole.log(JSON.stringify({expr}));'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


def _view(md: str, **opts):
    return _run(f'reportView({json.dumps(md)}, {json.dumps(opts)})')


def _sections(md: str):
    return _run(f'reportSections({json.dumps(md)})')


def _part(view, key):
    return next(p for p in view['parts'] if p['key'] == key)


def test_the_report_falls_into_its_own_parts_in_its_own_order():
    v = _view(REPORT, hero=True)
    assert v['title'] == ('Krav på laddbara tjänstebilar och utbyggnad av laddinfrastruktur '
                          'vid kommunala arbetsplatser')
    assert v['preamble'] == ''
    assert [p['key'] for p in v['parts']] == PARTS
    assert _part(v, 'tidsprofil')['title'] == 'Tidsprofil – när kommer effekten?'
    assert _part(v, 'bilaga')['title'] == 'Teknisk bilaga: Beräkningssteg'


def test_the_program_sections_are_parts_too():
    v = _view(RESECENTRUM, hero=True)
    assert [p['key'] for p in v['parts']] == PARTS + ['ursprung']
    urs = _part(v, 'ursprung')
    assert urs['body'].startswith('Kalkylen bygger på 30 inmatade tal.')
    # Kontrollera först and the table stay inside Talens ursprung.
    assert '### Kontrollera först' in urs['body']
    assert '| Drivare | Tal | Värde | Ursprung | Underlag |' in urs['body']


@pytest.mark.parametrize('md', [REPORT, RESECENTRUM], ids=['tjanstebilar', 'resecentrum'])
def test_no_line_is_lost_or_moved(md):
    r = _sections(md)
    kept = [r['title']] + [l for l in r['preamble'].split('\n') if l.strip()]
    for p in r['parts']:
        kept.append(p['title'])
        kept += [l for l in p['body'].split('\n') if l.strip()]
    def norm(line):
        return line.strip().strip('*').strip().lstrip('#').strip()
    assert [norm(k) for k in kept] == [norm(l) for l in md.split('\n') if l.strip()]


def test_a_sub_label_inside_a_part_does_not_split_it():
    body = _part(_view(REPORT, hero=True), 'osakerhet')['body']
    for label in ('Osäkerhet och känslighet', 'QA-status och huvudanmärkningar', 'Dubbelräkning och beroenden'):
        assert label in body


def test_the_recommendation_is_the_verdict_and_read_once():
    v = _view(REPORT, hero=True)
    text = v['verdict']['text']
    assert text.startswith('Åtgärden är principiellt riktig och kommunen har full rådighet')
    rec = _part(v, 'rekommendation')
    assert rec['title'] == 'Nästa steg'
    assert 'Samlad rekommendation' not in rec['body']
    assert text[:60] not in rec['body']
    assert rec['body'].startswith('Förslag på nästa steg:')
    assert 'Förslag på information som skulle förbättra analysen:' in rec['body']


def test_the_three_levels_under_the_verdict():
    v = _view(REPORT, hero=True)
    assert v['verdict']['status'] == [
        {'label': 'Osäkerhet', 'value': 'Hög', 'warn': False},
        {'label': 'Kvalitetsgranskning', 'value': 'Varning', 'warn': True},
        {'label': 'Risk för dubbelräkning', 'value': 'Medel', 'warn': False},
    ]
    # "medel (låg inom åtgärden, men hög mot ...)" is read as medel.
    status = _view(RESECENTRUM, hero=True)['verdict']['status']
    assert status[2] == {'label': 'Risk för dubbelräkning', 'value': 'Medel', 'warn': False}


def test_a_live_run_reads_the_qa_steps_own_verdict():
    """The warning under the number reads state.qaVerdict; the levels must
    not say something else about the same run."""
    status = _view(REPORT, hero=True, qa={'status': 'ok'})['verdict']['status']
    assert {'label': 'Kvalitetsgranskning', 'value': 'Godkänd', 'warn': False} in status


def test_numbers_to_check_are_counted_from_talens_ursprung():
    v = _view(RESECENTRUM, hero=True)
    assert v['verdict']['check'] == 1
    urs = _part(v, 'ursprung')
    assert urs['teaser'] == 'Varifrån vart och ett av de 30 talen i kalkylen kommer. 1 behöver kontrolleras.'
    assert urs['warn'] is True
    assert _view(REPORT, hero=True)['verdict']['check'] == 0


def test_the_lines_under_the_titles():
    teasers = {p['key']: p['teaser'] for p in _view(REPORT, hero=True)['parts']}
    assert teasers['klimatnytta'] == ('År 2030: försiktigt 59, mest sannolikt 118 och full potential '
                                      '201 ton CO₂e/år.')
    assert teasers['mekanism'] == '4 huvuddrivare och hur de ger effekt.'
    assert teasers['antaganden'] == '5 nyckelantaganden och hur beräkningen är gjord.'
    assert teasers['tidsprofil'] == 'Effekten börjar 2027 och är full 2030.'
    assert teasers['osakerhet'] == ('Vad resultatet är mest känsligt för, 6 anmärkningar från granskningen '
                                    'och beroenden till andra beslut.')
    assert teasers['rekommendation'] == '7 förslag på nästa steg, och underlag som skulle göra analysen säkrare.'
    assert teasers['kallor'] == '3 externa studier och underlagen analysen bygger på.'


def test_a_time_profile_in_prose_gets_the_fixed_line():
    """"2025 för profil 1, men kalkylen ger effekt först från 2026" does not
    fit in a line, and a year picked out of it would mislead."""
    tidsprofil = _part(_view(RESECENTRUM, hero=True), 'tidsprofil')
    assert tidsprofil['teaser'] == 'När effekten kommer och hur den byggs upp.'


def test_every_part_starts_closed_under_a_number():
    assert not any(p['open'] for p in _view(REPORT, hero=True)['parts'])
    # Without a number above, the result is open.
    opened = [p['key'] for p in _view(REPORT, hero=False)['parts'] if p['open']]
    assert opened == ['klimatnytta']


@pytest.mark.parametrize('line', [
    '**Beräknad klimatnytta**', '## Beräknad klimatnytta', 'Beräknad klimatnytta',
    '### 3) Beräknad klimatnytta:', '**Beräknad klimatnytta:**', '1) **Beräknad klimatnytta**',
])
def test_a_heading_in_the_forms_the_models_write(line):
    md = f'## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n{line}\n\nB.\n\n**Källor och underlag**\n\nC.\n'
    v = _view(md, hero=True)
    assert [p['key'] for p in v['parts']] == ['beskrivning', 'klimatnytta', 'kallor']
    assert _part(v, 'klimatnytta')['body'] == 'B.'


def test_the_words_inside_a_sentence_are_not_a_heading():
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nSe Beräknad klimatnytta nedan.\n\n'
          '**Hur åtgärden minskar utsläppen**\n\nB.\n\n**Källor och underlag**\n\nC.\n')
    v = _view(md, hero=True)
    assert [p['key'] for p in v['parts']] == ['beskrivning', 'mekanism', 'kallor']


def test_a_text_that_is_not_the_report_is_shown_whole():
    assert _view('Bara text.\n\n**Kort beskrivning av åtgärden**\n\nX', hero=True) is None
    assert _view('', hero=True) is None
    two = '## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Källor och underlag**\n\nC.\n'
    assert _view(two, hero=True) is None


def test_a_follow_up_keeps_its_mode_line_and_its_own_part():
    md = ('## Cykelbanan\n\nAnalysläge: uppföljning av genomförd insats, 2023–2025\n\n'
          '**Kort beskrivning av åtgärden**\n\nA.\n\n**Beräknad klimatnytta**\n\nB.\n\n'
          '**Uppmätt och antaget**\n\n- Uppmätt: flöden.\n\n**Källor och underlag**\n\nC.\n')
    v = _view(md, hero=True)
    assert v['title'] == 'Cykelbanan'
    assert v['preamble'] == 'Analysläge: uppföljning av genomförd insats, 2023–2025'
    assert [p['key'] for p in v['parts']] == ['beskrivning', 'klimatnytta', 'uppmatt', 'kallor']


def test_a_note_above_the_title_does_not_hide_it():
    md = ('> Omkörd.\n\n## Cykelbanan\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n'
          '**Beräknad klimatnytta**\n\nB.\n\n**Källor och underlag**\n\nC.\n')
    v = _view(md, hero=True)
    assert v['title'] == 'Cykelbanan'
    assert v['preamble'] == '> Omkörd.'


def test_a_part_written_twice_gets_two_rows():
    """The prompt says no appendix of the model's own; if one is written
    anyway, the engine's still follows it and neither is dropped."""
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Teknisk bilaga: Beräkningssteg**\n\nModellens.\n\n'
          '**Teknisk bilaga: Beräkningssteg**\n\nMotorns.\n')
    v = _view(md, hero=True)
    assert [p['id'] for p in v['parts']] == ['beskrivning', 'bilaga', 'bilaga-2']
    assert [p['body'] for p in v['parts']][1:] == ['Modellens.', 'Motorns.']


def test_a_recommendation_with_nothing_after_it_leaves_no_empty_row():
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Rekommendation och nästa steg**\n\n'
          'Samlad rekommendation:\nGenomför.\n\nMer om det.\n\n**Källor och underlag**\n\nC.\n')
    v = _view(md, hero=True)
    assert v['verdict']['text'] == 'Genomför.\n\nMer om det.'
    assert [p['key'] for p in v['parts']] == ['beskrivning', 'kallor']


def test_a_talens_ursprung_without_a_check_says_so():
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Källor och underlag**\n\nC.\n\n'
          '## Talens ursprung\n\nKällmarkering saknas för den här körningen. Kalkylen räknades av '
          'språkmodellen.\n')
    urs = _part(_view(md, hero=True), 'ursprung')
    assert urs['teaser'] == 'Källmarkering saknas för den här körningen.'
    assert urs['warn'] is True


def test_the_time_profile_with_a_colon_is_its_part():
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Tidsprofil: när kommer effekten?**\n\nB.\n\n'
          '**Källor och underlag**\n\nC.\n')
    assert [p['key'] for p in _view(md, hero=True)['parts']] == ['beskrivning', 'tidsprofil', 'kallor']


def test_the_title_is_drawn_without_its_markup():
    md = '## **Cykelbanan**\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Beräknad klimatnytta**\n\nB.\n\n**Källor och underlag**\n\nC.\n'
    assert _view(md, hero=True)['title'] == 'Cykelbanan'


SCENARIOS_PAST_THE_TARGET = (
    '## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Beräknad klimatnytta**\n\n'
    'Nyckelår och målår:\n  Nyckelår: [2030, 2035]\n  Målår: 2030\n\n'
    'Scenario_medel (mest sannolikt):\n  ΔE_2030_total (Netto): 20 ton CO2e/år\n  ΔE_2035_total (Netto): 21 ton CO2e/år\n\n'
    'Scenario_min (försiktigt):\n  ΔE_2030_total (Netto): 10 ton CO2e/år\n  ΔE_2035_total (Netto): 11 ton CO2e/år\n\n'
    'Scenario_max (full potential):\n  ΔE_2030_total (Netto): 30 ton CO2e/år\n  ΔE_2035_total (Netto): 31 ton CO2e/år\n\n'
    'Huvudresultat (Scenario Medel):\n  ΔE_2030_total (Netto): 99 ton CO2e/år\n\n'
    '**Källor och underlag**\n\nC.\n')


def test_the_result_line_is_for_the_target_year_and_each_scenario():
    """The hero shows the target year; a block after the scenarios is not the
    last scenario's (code review 2026-10-20)."""
    t = _part(_view(SCENARIOS_PAST_THE_TARGET, hero=True), 'klimatnytta')['teaser']
    assert t == 'År 2030: försiktigt 10, mest sannolikt 20 och full potential 30 ton CO₂e/år.'


def test_the_numbers_to_check_come_from_the_last_talens_ursprung():
    """The program appends Talens ursprung last. A line by that name the model
    wrote higher up must not take its place or its warning."""
    md = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\nTalens ursprung\n\nSe nedan.\n\n'
          '**Källor och underlag**\n\nC.\n\n'
          '## Talens ursprung\n\nKalkylen bygger på 12 inmatade tal, och 3 behöver kontrolleras.\n')
    v = _view(md, hero=True)
    assert [p['id'] for p in v['parts']] == ['beskrivning', 'ursprung', 'kallor', 'ursprung-2']
    assert v['verdict']['check'] == 3
    assert v['verdict']['checkPart'] == 'ursprung-2'
    first = v['parts'][1]
    assert first['teaser'] == '' and first['warn'] is False
    assert v['parts'][3]['warn'] is True


def _osak(body: str) -> str:
    return ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Osäkerhet, QA och beroenden**\n\n'
            + body + '\n\n**Källor och underlag**\n\nC.\n')


def test_a_level_is_read_from_its_own_line_only():
    v = _view(_osak('Risk för dubbelräkning: låg, men medel mot andra åtgärder\n\nKommentar:\n  Bedömning: hög'), hero=True)
    assert v['verdict'] is None
    v = _view(_osak('Risk för dubbelräkning:\n  Bedömning: medel'), hero=True)
    assert v['verdict']['status'] == [{'label': 'Risk för dubbelräkning', 'value': 'Medel', 'warn': False}]


def _rec(body: str) -> str:
    return ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Rekommendation och nästa steg**\n\n'
            + body + '\n\n**Källor och underlag**\n\nC.\n')


def test_a_sentence_that_starts_like_the_label_is_not_the_verdict():
    v = _view(_rec('Samlad rekommendationen är att vänta.'), hero=True)
    assert v['verdict'] is None
    assert _part(v, 'rekommendation')['title'] == 'Rekommendation och nästa steg'


@pytest.mark.parametrize('after', ['1. Steg ett\n2. Steg två', '| a | b |\n|---|---|\n| 1 | 2 |'])
def test_the_verdict_stops_at_a_numbered_list_or_a_table(after):
    v = _view(_rec('Samlad rekommendation:\nGenomför.\n' + after), hero=True)
    assert v['verdict']['text'] == 'Genomför.'
    assert _part(v, 'rekommendation')['body'] == after


def test_the_page_wiring():
    """What the browser does around the view, asserted on the script text as
    the save test does: a new analysis and a saved report start closed, a
    redraw keeps what was open, print opens everything and puts it back."""
    js = _inline_script()
    reset = _between(js, 'function resetAll()', '\n}\n')
    assert 'reportOpen.clear()' in reset
    assert "getElementById('reportTitle').style.display = 'none'" in reset
    saved = _between(js, 'async function openSaved(', '\n}\n')
    assert 'reportOpen.clear()' in saved
    assert '{name: row.action_name}' in saved
    finish = _between(js, 'async function finishReport(', '\n}\n')
    assert 'qa: state.qaVerdict' in finish
    assert "addEventListener('beforeprint'" in js and "addEventListener('afterprint'" in js
    # Model text reaches the page through the one sanitiser, titles as text.
    drawn = _between(js, 'function renderReportView(', '\n}\n')
    assert 'innerHTML' not in drawn
    assert drawn.count('sanitizedFragment(') == 3


# ---------- DIN SPEC 91637: "Följ upp med" ----------

_FOLJ_UPP = ('## T\n\n**Kort beskrivning av åtgärden**\n\nA.\n\n**Rekommendation och nästa steg**\n\n'
             'Samlad rekommendation:\nGenomför.\n\nFörslag på nästa steg:\n- Besluta.\n\n'
             '**Följ upp med**\n\nIndikatorer:\n'
             '- Antal laddbara tjänstebilar (st): i dag 41, hämtas ur fordonsregistret. Prövar adoptionen.\n'
             '- Avstånd till närmaste laddpunkt (km): i dag okänt, hämtas ur Nobil.\n'
             '  Prövar attributet.\n\n'
             '**Källor och underlag**\n\nC.\n')


def test_folj_upp_med_is_its_own_part_after_the_next_steps():
    """Recommendation 1 of an internal comparison with DIN SPEC 91637. Without its own
    entry in REPORT_PARTS the section would hide at the end of Nästa steg."""
    v = _view(_FOLJ_UPP, hero=True)
    assert [p['key'] for p in v['parts']] == ['beskrivning', 'rekommendation', 'uppfoljning', 'kallor']
    part = _part(v, 'uppfoljning')
    assert part['title'] == 'Följ upp med'
    assert part['teaser'] == '2 indikatorer som visar om åtgärden ger effekt.'
    assert 'Besluta' not in part['body'] and 'Indikatorer' not in _part(v, 'rekommendation')['body']


def test_folj_upp_med_without_a_list_gets_the_fixed_line():
    md = _FOLJ_UPP.replace('Indikatorer:\n', '')
    v = _view(md, hero=True)
    assert _part(v, 'uppfoljning')['teaser'] == 'Vad som ska mätas för att se om åtgärden ger effekt.'


def test_every_section_the_report_prompt_asks_for_is_a_part_on_the_page():
    """DECISIONS 2026-10-20: a prompt change that adds or renames a heading
    must change REPORT_PARTS in the same PR. This holds it."""
    import re
    from caia.agents.rapport import SYSTEM_PROMPT
    headings = re.findall(r'^\s*\d+\) Avsnitt: "\*\*(.+?)\*\*"', SYSTEM_PROMPT, re.M)
    assert 'Följ upp med' in headings and len(headings) >= 9
    md = '## T\n\n' + ''.join(f'**{h}**\n\nText.\n\n' for h in headings)
    assert [p['title'] for p in _view(md, hero=True)['parts']] == headings


def test_the_follow_up_report_leaves_folj_upp_med_to_vad_som_behover_matas():
    """A follow-up has "Vad som behöver mätas" instead, so its prompt never
    asks for the section, and its numbering has no gap."""
    import re
    from caia.agents.rapport import SYSTEM_PROMPT, SYSTEM_PROMPT_UPPFOLJNING
    assert 'Följ upp med' not in SYSTEM_PROMPT_UPPFOLJNING
    assert 'indikatorer' not in SYSTEM_PROMPT_UPPFOLJNING.lower()
    sections = [int(n) for n in re.findall(r'^\s*(\d+)\) (?:Avsnitt|Ingen teknisk)', SYSTEM_PROMPT_UPPFOLJNING, re.M)]
    steps = [int(n) for n in re.findall(r'<step index="(\d+)">', SYSTEM_PROMPT_UPPFOLJNING)]
    goals = [int(n) for n in re.findall(r'^    (\d+)\) ', SYSTEM_PROMPT_UPPFOLJNING, re.M)]
    for seq in (sections, steps, goals):
        assert seq == list(range(seq[0], seq[0] + len(seq)))
    assert len(steps) == len(re.findall(r'<step index=', SYSTEM_PROMPT)) - 1
    # Everything else is the forecast prompt, word for word.
    assert SYSTEM_PROMPT.count('**Källor och underlag**') == SYSTEM_PROMPT_UPPFOLJNING.count('**Källor och underlag**') == 1
