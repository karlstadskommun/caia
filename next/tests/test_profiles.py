"""Tests for the åtgärdsprofil parser.

The input is language-model output following a template, so the tests cover
both the template as written and the ways a model drifts from it. The load
bearing property is no silent data loss: every test either finds the field or
asserts the caller gets an empty list and falls back to raw text.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_profiles.py -v
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.profiles import parse_profiles  # noqa: E402

# Template-exact output, the shape agents/intake.py asks for.
SINGLE = """ÅTGÄRDSPROFIL
*Namn:* Bilpool för kommunens anställda
*Beskrivning:* Kommunen ersätter egna tjänstebilar med en gemensam bilpool.
Poolen omfattar 40 elbilar och ersätter cirka 120 tjänstebilar.
*Sektor:* transporter
*Drivare:* antal tjänsteresor med bil
*Målgrupp:* kommunens egna anställda
*Utsläpp som påverkas:* territoriella utsläpp, kommunens egna utsläpp
*Rådighet:* direkt
*Typ av åtgärd:* organisation/styrning
*Tidsram:* 2026–2030 (ANTAGANDE: Tidsram 2026–2030 då inget annat angivits)
*Kommun:* Karlstads kommun (ANTAGANDE: Gäller Karlstads kommun)
*Kommentarer:* Ingen uppdelning gjord.
"""


def test_single_profile_parses_all_fields():
    result = parse_profiles(SINGLE)
    assert len(result['profiles']) == 1
    profile = result['profiles'][0]
    assert profile['name'] == 'Bilpool för kommunens anställda'
    assert profile['index'] == 1
    labels = [f['label'] for f in profile['fields']]
    assert labels == [
        'Beskrivning', 'Sektor', 'Drivare', 'Målgrupp', 'Utsläpp som påverkas',
        'Rådighet', 'Typ av åtgärd', 'Tidsram', 'Kommun', 'Kommentarer',
    ]


def test_wrapped_description_stays_in_its_field():
    # A soft-wrapped Beskrivning must not turn into a second field.
    profile = parse_profiles(SINGLE)['profiles'][0]
    beskrivning = next(f for f in profile['fields'] if f['label'] == 'Beskrivning')
    assert beskrivning['value'].endswith('ersätter cirka 120 tjänstebilar.')
    assert 'Poolen omfattar 40 elbilar' in beskrivning['value']


def test_assumption_is_lifted_out_of_the_value():
    profile = parse_profiles(SINGLE)['profiles'][0]
    tidsram = next(f for f in profile['fields'] if f['label'] == 'Tidsram')
    assert tidsram['value'] == '2026–2030'
    assert tidsram['assumptions'] == ['Tidsram 2026–2030 då inget annat angivits']
    # The raw marker must not leak into what the card renders.
    assert 'ANTAGANDE' not in tidsram['value']
    assert profile['assumption_count'] == 2


def test_field_without_assumption_has_none():
    profile = parse_profiles(SINGLE)['profiles'][0]
    sektor = next(f for f in profile['fields'] if f['label'] == 'Sektor')
    assert sektor['assumptions'] == []
    assert sektor['value'] == 'transporter'


def test_multiple_profiles_keep_their_numbering():
    text = """Jag delade upp beskrivningen i två åtgärder.

ÅTGÄRDSPROFIL 1
*Namn:* Solceller på kommunala tak
*Sektor:* energi

ÅTGÄRDSPROFIL 2
*Namn:* Laddinfrastruktur vid kommunhus
*Sektor:* transporter
"""
    result = parse_profiles(text)
    assert result['preamble'] == 'Jag delade upp beskrivningen i två åtgärder.'
    assert [p['index'] for p in result['profiles']] == [1, 2]
    assert [p['name'] for p in result['profiles']] == [
        'Solceller på kommunala tak', 'Laddinfrastruktur vid kommunhus',
    ]


def test_markdown_variants_still_parse():
    # Bold headings, bold labels and list bullets are all drift the model shows.
    text = """## **ÅTGÄRDSPROFIL 1**
- **Namn:** Cykelvägar
- **Sektor:** transporter
**Rådighet:** direkt
"""
    profile = parse_profiles(text)['profiles'][0]
    assert profile['name'] == 'Cykelvägar'
    assert {f['label'] for f in profile['fields']} == {'Sektor', 'Rådighet'}


def test_unknown_field_is_kept_and_sorted_last():
    text = """ÅTGÄRDSPROFIL
*Namn:* Test
*Finansiering:* investeringsmedel
*Sektor:* energi
"""
    profile = parse_profiles(text)['profiles'][0]
    labels = [f['label'] for f in profile['fields']]
    assert labels == ['Sektor', 'Finansiering']


def test_missing_name_gets_a_fallback_label():
    profile = parse_profiles("ÅTGÄRDSPROFIL\n*Sektor:* energi\n")['profiles'][0]
    assert profile['name'] == 'Åtgärd utan namn'
    assert [f['label'] for f in profile['fields']] == ['Sektor']


def test_text_without_profile_returns_empty_list_and_keeps_the_text():
    # The caller falls back to raw markdown on an empty list, so the text
    # itself must survive: an empty result here would lose the agent's answer.
    text = 'Innan jag kan bygga profilen: hur många fordon rör det sig om?'
    result = parse_profiles(text)
    assert result['profiles'] == []
    assert result['preamble'] == text


def test_bare_heading_with_nothing_under_it_is_skipped():
    result = parse_profiles('ÅTGÄRDSPROFIL 1\n\nÅTGÄRDSPROFIL 2\n*Namn:* Riktig\n')
    assert len(result['profiles']) == 1
    assert result['profiles'][0]['name'] == 'Riktig'


def test_profile_with_text_but_no_fields_survives_as_unparsed():
    # The dangerous case: one good profile plus one the parser cannot read.
    # Dropping the second looked like success, since a non-empty list means
    # the UI renders cards and never falls back to the raw text.
    text = (
        'ÅTGÄRDSPROFIL 1\n'
        '*Namn:* Bilpool\n'
        '*Sektor:* transporter\n\n'
        'ÅTGÄRDSPROFIL 2\n'
        'Laddinfrastruktur vid samtliga kommunala arbetsplatser, utan fältstruktur.\n'
    )
    profiles = parse_profiles(text)['profiles']
    assert len(profiles) == 2
    assert profiles[0]['unparsed'] == ''
    assert 'Laddinfrastruktur' in profiles[1]['unparsed']
    assert profiles[1]['fields'] == []


def test_display_position_does_not_inherit_a_gap_in_the_numbering():
    text = (
        'ÅTGÄRDSPROFIL 1\n*Namn:* A\n*Sektor:* s\n\n'
        'ÅTGÄRDSPROFIL 2\n\n'
        'ÅTGÄRDSPROFIL 3\n*Namn:* C\n*Sektor:* s\n'
    )
    profiles = parse_profiles(text)['profiles']
    # Profile 2 is a bare heading and drops out, so the stated numbers gap.
    assert [p['index'] for p in profiles] == [1, 3]
    # Display uses position, so the card cannot read "Åtgärd 3 av 2".
    assert [p['position'] for p in profiles] == [1, 2]


def test_title_on_the_heading_line_still_parses():
    text = 'ÅTGÄRDSPROFIL 1: Bilpool för anställda\n*Namn:* Bilpool\n*Sektor:* transporter\n'
    profiles = parse_profiles(text)['profiles']
    assert len(profiles) == 1
    assert profiles[0]['name'] == 'Bilpool'
    assert {f['label'] for f in profiles[0]['fields']} == {'Sektor'}


def test_heading_title_stands_in_for_a_missing_name():
    text = 'ÅTGÄRDSPROFIL 1: Solceller på kommunala tak\n*Sektor:* energi\n'
    assert parse_profiles(text)['profiles'][0]['name'] == 'Solceller på kommunala tak'


def test_unclosed_assumption_still_flags_the_field():
    # An assumption the model never closed used to leave the field looking
    # like a stated fact, with the raw marker sitting in the value.
    text = (
        'ÅTGÄRDSPROFIL\n*Namn:* Test\n'
        '*Kommentarer:* Se bilaga (ANTAGANDE: gäller endast om fullmäktige beslutar\n'
    )
    field = parse_profiles(text)['profiles'][0]['fields'][0]
    assert field['value'] == 'Se bilaga'
    assert field['assumptions'] == ['gäller endast om fullmäktige beslutar']
    assert 'ANTAGANDE' not in field['value']


def test_nested_parentheses_in_an_assumption_do_not_garble_the_value():
    text = 'ÅTGÄRDSPROFIL\n*Namn:* T\n*Rådighet:* direkt (ANTAGANDE: kommunen äger dem (KF 2019:44))\n'
    field = parse_profiles(text)['profiles'][0]['fields'][0]
    assert field['value'] == 'direkt'
    assert field['assumptions'] == ['kommunen äger dem (KF 2019:44)']


def test_two_assumptions_in_one_value_are_both_kept():
    text = 'ÅTGÄRDSPROFIL\n*Namn:* T\n*Tidsram:* 2026 (ANTAGANDE: start) till 2030 (ANTAGANDE: slut)\n'
    field = parse_profiles(text)['profiles'][0]['fields'][0]
    assert field['assumptions'] == ['start', 'slut']
    assert '2026' in field['value'] and '2030' in field['value']


def test_empty_and_none_input_do_not_crash():
    for value in ('', None):
        result = parse_profiles(value)
        assert result == {'preamble': '', 'profiles': []}


def test_real_intake_output_parses_without_losing_content():
    """Run the parser over every stored production run.

    `streamlit/reports/*.json` holds the 30 EKP analyses from December 2025,
    each with the real intake text in `intake_summary`. The assertion is word
    level: everything the agent wrote must survive into a name, a field, a
    value or an assumption. A parser that quietly drops a field would still
    render a plausible looking card, so counting words is the check that
    actually bites.
    """
    reports = sorted(glob.glob(os.path.join(
        os.path.dirname(__file__), '..', '..', 'streamlit', 'reports', '*.json')))
    if not reports:
        pytest.skip('no stored reports in this checkout')

    def words(text):
        return Counter(w for w in re.findall(r'\w+', (text or '').lower()))

    seen_profiles = 0
    for path in reports:
        with open(path, encoding='utf-8') as fh:
            text = json.load(fh).get('intake_summary', '')
        if 'ÅTGÄRDSPROFIL' not in text or '*Namn:*' not in text:
            continue

        result = parse_profiles(text)
        assert result['profiles'], f'no profile parsed from {os.path.basename(path)}'
        seen_profiles += len(result['profiles'])

        rendered = words(result['preamble'])
        for profile in result['profiles']:
            rendered += words(profile['name'])
            for field in profile['fields']:
                rendered += words(field['label']) + words(field['value'])
                for note in field['assumptions']:
                    rendered += words(note)

        # Drop the heading lines from the comparison rather than exempting
        # numbers: "ÅTGÄRDSPROFIL 2" survives as `index`, but a blanket digit
        # exemption would also hide a dropped year, budget figure or vehicle
        # count, which is exactly the loss this test exists to catch.
        source = re.sub(r'(?im)^.*ÅTGÄRDSPROFIL.*$', '', text)
        missing = words(source) - rendered
        # The ANTAGANDE marker becomes the chip, and the Namn label becomes the
        # card heading, so neither survives as field text.
        for expected in ('antagande', 'antaganden', 'namn'):
            missing.pop(expected, None)

        assert not missing, f'{os.path.basename(path)} lost content: {dict(missing)}'

    assert seen_profiles >= 30, f'expected the full corpus, parsed {seen_profiles}'


def test_assumption_without_colon_or_text_still_flags_the_field():
    text = 'ÅTGÄRDSPROFIL\n*Namn:* Test\n*Kommun:* Karlstads kommun (ANTAGANDE)\n'
    profile = parse_profiles(text)['profiles'][0]
    kommun = next(f for f in profile['fields'] if f['label'] == 'Kommun')
    assert kommun['value'] == 'Karlstads kommun'
    assert kommun['assumptions'] == ['']
    assert profile['assumption_count'] == 1


def test_wrapped_sentence_with_a_colon_stays_in_the_description():
    # "Syfte: ..." mid-sentence is prose, not a field. Splitting it would drop
    # the first half of the description off the card.
    text = (
        'ÅTGÄRDSPROFIL\n'
        '*Namn:* Test\n'
        '*Beskrivning:* Kommunen bygger ut laddinfrastrukturen.\n'
        'Syfte: minska antalet fossila tjänsteresor.\n'
        '*Sektor:* transporter\n'
    )
    profile = parse_profiles(text)['profiles'][0]
    labels = [f['label'] for f in profile['fields']]
    assert labels == ['Beskrivning', 'Sektor']
    beskrivning = profile['fields'][0]['value']
    assert 'laddinfrastrukturen' in beskrivning
    assert 'minska antalet fossila tjänsteresor' in beskrivning


def test_colon_inside_a_value_is_not_a_new_field():
    text = 'ÅTGÄRDSPROFIL\n*Namn:* Test\n*Kommentarer:* Obs: gäller endast etapp 1\n'
    profile = parse_profiles(text)['profiles'][0]
    kommentarer = next(f for f in profile['fields'] if f['label'] == 'Kommentarer')
    assert kommentarer['value'] == 'Obs: gäller endast etapp 1'
