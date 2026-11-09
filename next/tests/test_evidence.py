"""Tests for the evidens parser.

The evidens step is the approval gate where the numbers get set, so the tests
care most about two things: a span that reaches the card intact, and nothing
disappearing when the model drifts from the template.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_evidence.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.evidence import parse_evidence  # noqa: E402

TEMPLATE = """Evidens & antaganden för åtgärd: Laddbara tjänstebilar

Kort om detta steg
Jag utgår från EMAP och Baslinje & BAU, identifierar påverkade drivare och
föreslår antagandespann med källor.

Antaganden per drivare

Drivare 1: Fossila tjänstebilar i kommunens flotta
  Mekanism: Teknikbyte från fossila till laddbara fordon.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 1,2
    Overlap_faktor: 0.9
    Motivering_faktorer: Full effekt i kommunen, något större ur konsumtionsperspektiv.
  Parameter: ΔEF
    Antagande_min: -0,25 (25 % lägre utsläpp per km)
    Antagande_med: -0,45 (45 % lägre utsläpp per km)
    Antagande_max: -0,70 (70 % lägre utsläpp per km)
    Enhet: andel
    Tidsaspekt: nivå relativt 2030 BAU
    Källor: TR_ev_emission_factor, Energimyndigheten 2024
    Kvalitet: hög
    Lokaliserbarhet: lätt
    Kommentar_antagande: Spannet speglar osäkerhet i elmix.
  Parameter: adoption
    Antagande_min: 0,40
    Antagande_med: 0,65
    Antagande_max: 0,90
    Enhet: andel av flottan
    Kvalitet: medel
    Lokaliserbarhet: medel

Drivare 2: Laddinfrastruktur vid arbetsplatser
  Mekanism: Möjliggörande, ingen egen utsläppsminskning.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 0.0
    Konsumtion_faktor: 0.0
    Overlap_faktor: 0.0
    Motivering_faktorer: Enabler, effekten räknas hem på drivare 1.
  Parameter: adoption
    Antagande_min: 0,50
    Antagande_med: 0,75
    Antagande_max: 1,00
    Enhet: andel arbetsplatser
    Kvalitet: låg
    Lokaliserbarhet: svår

Dataluckor för detta steg
- Saknar lokal uppföljning av laddmönster.

Externa källor och studier
- Energimyndigheten (2024), Transportsektorns elektrifiering.
"""


def test_drivers_and_parameters_parse():
    result = parse_evidence(TEMPLATE)
    assert [d['number'] for d in result['drivers']] == [1, 2]
    assert result['drivers'][0]['name'] == 'Fossila tjänstebilar i kommunens flotta'
    assert [len(d['parameters']) for d in result['drivers']] == [2, 1]


def test_climate_factors_become_numbers():
    driver = parse_evidence(TEMPLATE)['drivers'][0]
    assert driver['factors']['territoriell'] == 1.0
    # Swedish decimal comma has to survive: 1,2 is not 12.
    assert driver['factors']['konsumtion'] == 1.2
    assert driver['factors']['overlap'] == 0.9
    assert 'Full effekt' in driver['factors']['motivering']


def test_zero_factor_is_kept_not_treated_as_missing():
    # An enabler with 0.0 across the board is a real statement: the effect is
    # counted on another driver. Falsy-checking it away would hide that.
    driver = parse_evidence(TEMPLATE)['drivers'][1]
    assert driver['factors']['territoriell'] == 0.0
    assert driver['factors']['konsumtion'] == 0.0
    assert driver['factors']['overlap'] == 0.0


def test_non_numeric_factor_keeps_its_reason():
    # Real output (fixtures/evidens.md) writes "– (kvantifieras ej separat)"
    # for an enabler. Showing only a dash would drop the reason the reviewer
    # needs: the effect is counted on another driver, not missing.
    text = (
        'Drivare 2: Laddinfrastruktur\n'
        '  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):\n'
        '    Territoriell_faktor: – (kvantifieras ej separat)\n'
    )
    driver = parse_evidence(text)['drivers'][0]
    assert driver['factors']['territoriell'] is None
    assert driver['factors_text']['territoriell'] == '(kvantifieras ej separat)'


def test_span_keeps_value_and_interpretation():
    parameter = parse_evidence(TEMPLATE)['drivers'][0]['parameters'][0]
    assert parameter['name'] == 'ΔEF'
    assert parameter['min'] == '-0,25 (25 % lägre utsläpp per km)'
    assert parameter['med'] == '-0,45 (45 % lägre utsläpp per km)'
    assert parameter['max'] == '-0,70 (70 % lägre utsläpp per km)'
    assert parameter['enhet'] == 'andel'
    assert parameter['tidsaspekt'] == 'nivå relativt 2030 BAU'
    assert parameter['kvalitet'] == 'hög'
    assert parameter['lokaliserbarhet'] == 'lätt'
    assert 'elmix' in parameter['kommentar']


def test_long_parameter_name_splits_into_name_and_gloss():
    # Real output: "adoption (andel av BAU-2030:s kvarvarande icke-laddbara
    # delflotta som ytterligare ställs om till laddbar pga åtgärden)". Set as
    # one uppercase heading it is unreadable, so the gloss is split off.
    text = (
        'Drivare 1: X\n'
        '  Parameter: adoption (andel av BAU-2030:s kvarvarande icke-laddbara '
        'delflotta som ytterligare ställs om)\n'
        '    Antagande_med: 0,50\n'
    )
    parameter = parse_evidence(text)['drivers'][0]['parameters'][0]
    assert parameter['name'] == 'adoption'
    assert parameter['detail'].startswith('andel av BAU-2030')
    assert 'ställs om' in parameter['detail']


def test_parameter_without_parentheses_keeps_its_whole_name():
    text = 'Drivare 1: X\n  Parameter: ΔEF\n    Antagande_med: -0,10\n'
    parameter = parse_evidence(text)['drivers'][0]['parameters'][0]
    assert parameter['name'] == 'ΔEF'
    assert parameter['detail'] == ''


def test_sources_split_into_chips():
    parameter = parse_evidence(TEMPLATE)['drivers'][0]['parameters'][0]
    assert parameter['kallor'] == ['TR_ev_emission_factor', 'Energimyndigheten 2024']


def test_source_with_a_comma_inside_parentheses_stays_whole():
    text = (
        'Drivare 1: X\n'
        '  Parameter: ΔA\n'
        '    Källor: Naturvårdsverket (2023, rapport 7091); SCB\n'
    )
    parameter = parse_evidence(text)['drivers'][0]['parameters'][0]
    assert parameter['kallor'] == ['Naturvårdsverket (2023, rapport 7091)', 'SCB']


def test_prose_sections_are_kept():
    sections = {s['title']: s['body'] for s in parse_evidence(TEMPLATE)['sections']}
    assert 'Kort om detta steg' in sections
    assert 'Dataluckor för detta steg' in sections
    assert 'laddmönster' in sections['Dataluckor för detta steg']
    # The driver blocks live in cards, so they must not be duplicated in prose.
    assert 'Territoriell_faktor' not in sections.get('Antaganden per drivare', '')


def test_text_without_drivers_returns_empty_list():
    result = parse_evidence('Här är en analys utan drivarblock alls.')
    assert result['drivers'] == []


def test_empty_input_does_not_crash():
    for value in ('', None):
        result = parse_evidence(value)
        assert result['drivers'] == [] and result['sections'] == []


def test_markdown_bold_driver_heading_parses():
    text = '**Drivare 3: Elektrifierad arbetsmaskinpark**\n  Mekanism: Teknikbyte.\n'
    driver = parse_evidence(text)['drivers'][0]
    assert driver['number'] == 3
    assert driver['name'] == 'Elektrifierad arbetsmaskinpark'
    assert driver['mekanism'] == 'Teknikbyte.'


def test_unknown_label_inside_a_driver_is_kept_as_extra():
    text = 'Drivare 1: X\n  Mekanism: Y\n  Finansiering: investeringsmedel\n'
    driver = parse_evidence(text)['drivers'][0]
    assert any(e['label'] == 'Finansiering' for e in driver['extra'])


def test_wrapped_assumption_line_continues_the_field():
    text = (
        'Drivare 1: X\n'
        '  Parameter: ΔA\n'
        '    Antagande_med: -0,30 (30 % minskning jämfört med BAU,\n'
        '      baserat på utfall i tre jämförbara kommuner)\n'
        '    Enhet: andel\n'
    )
    parameter = parse_evidence(text)['drivers'][0]['parameters'][0]
    assert 'jämförbara kommuner' in parameter['med']
    assert parameter['enhet'] == 'andel'


@pytest.mark.parametrize('fixture', ['evidens.md'])
def test_real_agent_output_parses(fixture):
    """Parse a captured production run.

    Written against tests/fixtures/evidens.md, captured from a real run:
        python tools/run_batch.py tests/reference/01-tjanstebilar.md --out /tmp/cap
    then copy /tmp/cap/01-tjanstebilar/<step>.md into tests/fixtures/. Skips
    when the fixture is absent so the suite still runs in a fresh checkout.
    """
    path = os.path.join(os.path.dirname(__file__), 'fixtures', fixture)
    if not os.path.exists(path):
        pytest.skip('no captured fixture; see the docstring for how to capture one')

    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    result = parse_evidence(text)

    assert result['drivers'], 'real output produced no drivers'
    for driver in result['drivers']:
        assert driver['name'], f"driver {driver['number']} lost its name"
    # At least one parameter should carry a full span, or the gate shows nothing.
    spans = [p for d in result['drivers'] for p in d['parameters']
             if p['min'] and p['med'] and p['max']]
    assert spans, 'no parameter came through with a complete min/med/max span'
