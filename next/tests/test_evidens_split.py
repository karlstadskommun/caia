"""Evidens split into one call per driver plus a merge (agents/evidens_split.py).

What these guard, in order of what it would cost to get wrong:

1. An incomplete underlag never reaches step 5. A driver that is missing looks
   exactly like a driver with no effect, so a failed part must fail the step:
   in the merge endpoint, in the web client, and in run_batch.
2. The driver blocks reach step 5 as the parts wrote them, or as an explicit
   correction from the merge. Never re-typed by a model.
3. The assembled text reads like the monolithic step's, so the panel parser
   and kalkyl_extract need no change.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from caia.agents import evidens_split as S  # noqa: E402
from caia.api_client import ModelOutputError  # noqa: E402
from caia.evidence import parse_evidence  # noqa: E402
from caia.web import app as A  # noqa: E402

BASLINJE = """Baslinje & BAU för åtgärd: Lövblåsare

## Nulägesbaslinje per drivare

**Drivare 1: Bensin i 15 lövblåsar**
  A0: 1 275 l/år
**Drivare 2: Tillkommande el för laddning**
  A0: 0 kWh/år

## BAU-scenario per drivare

**Drivare 1: Bensin i 15 lövblåsar**
  BAU: byte 2028
**Drivare 2: Tillkommande el för laddning**
  BAU: följer drivare 1
"""

EMAP = """EMAP-analys

Drivare 1: Bensin i handburna lövblåsar
  sektor: transport
Drivare 2: El för laddning
  sektor: energi
Drivare 3: Batteritillverkning
  sektor: konsumtion
"""

HISTORY = [
    {'role': 'user', 'content': 'Åtgärd: 15 batterilövblåsare.'},
    {'role': 'assistant', 'content': EMAP},
    {'role': 'user', 'content': 'EMAP-analysen är godkänd. Fortsätt med baslinje och BAU.'},
    {'role': 'assistant', 'content': BASLINJE},
    {'role': 'user', 'content': 'Baslinjen är godkänd. Fortsätt med evidens och antaganden.'},
]


def part_text(n: int, name: str, med: str = '-1,0') -> str:
    return f"""Drivare {n}: {name}
  Mekanism: teknikbyte
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 1.0
    Overlap_faktor: 1.0
    Motivering_faktorer: förbränning i kommunen
  Parameter: ΔA
    Antagande_min: -0,5
    Antagande_med: {med}
    Antagande_max: -1,0
    Enhet: andel
    Tidsaspekt: per effektår
    Källor: Åtgärdsprofilen
    Kvalitet: låg
    Lokaliserbarhet: lätt
    Kommentar_antagande: schablon

{S.MARK_SCOPE}
Räknar bensinen. Drivare 2: elen räknas där, inte här.

Nyckelantaganden:
- bytet tidigareläggs
Dataluckor:
- drifttimmar
Externa källor:
- Inga
"""


def merge_text(corrections: str = 'Inga') -> str:
    return f"""Evidens & antaganden för åtgärd: Lövblåsare

## Kort om detta steg
Kort text.

## Underlag från tidigare steg
Två drivare.

## Påverkade drivare och parametrar
Drivare 1: påverkas via ΔA
Drivare 2 (el) påverkas via ökad aktivitet.

## Antaganden per drivare

{S.MARK_DRIVERS}

## Nyckelantaganden – överblick
- Tidigareläggning.

## Övergripande antaganden och scenariologik
Utöver BAU.

## Dataluckor för detta steg
- Drifttimmar.

## Externa källor och studier
Inga specifika externa studier hittades, analysen baseras på generella parametrar.

## Samstämmighetskontroll
- Kontrollerade dubbelräkning mellan drivare 1 och 2. Inga motsägelser.

{S.MARK_CORRECTIONS}
{corrections}
"""


DRIVERS = [S.Driver(1, 'Bensin i 15 lövblåsar'), S.Driver(2, 'Tillkommande el för laddning')]


def parts() -> list[S.Part]:
    return [S.split_part(d, part_text(d.number, d.name)) for d in DRIVERS]


# ---------- plan: which drivers ----------

def test_drivers_come_from_baslinje_deduplicated_and_numbered_as_upstream():
    assert S.drivers_from_history(HISTORY) == DRIVERS


def test_a_previous_evidens_answer_is_not_mistaken_for_the_driver_list():
    # On a feedback re-run the last assistant message is the old evidens
    # answer, which only lists the drivers it judged affected.
    old = 'Evidens & antaganden för åtgärd: X\n\n' + part_text(1, 'Bensin')
    history = HISTORY + [{'role': 'assistant', 'content': old},
                         {'role': 'user', 'content': 'Sänk ΔA.'}]
    assert S.drivers_from_history(history) == DRIVERS


def test_falls_back_to_emap_when_baslinje_names_no_drivers():
    history = HISTORY[:3] + [{'role': 'assistant', 'content': 'Baslinje utan drivarrubriker.'}]
    assert [d.number for d in S.drivers_from_history(history)] == [1, 2, 3]


def test_a_prose_line_that_looks_like_a_heading_adds_no_driver():
    # Review finding: "Drivare 3: se ovan" in baslinje prose would have made a
    # part invent a third driver that no upstream step defined.
    text = BASLINJE + '\nDrivare 3: se ovan, räknas inte separat.\nDet gäller hela perioden.\n'
    history = HISTORY[:3] + [{'role': 'assistant', 'content': text}]
    assert S.drivers_from_history(history) == DRIVERS


def test_no_drivers_means_the_monolithic_fallback():
    assert S.drivers_from_history([{'role': 'assistant', 'content': 'Inget här.'}]) == []


# ---------- parts ----------

def test_split_part_separates_block_from_notes():
    p = S.split_part(DRIVERS[0], 'Inledande prat.\n' + part_text(1, 'Bensin i 15 lövblåsar'))
    assert p.block.startswith('Drivare 1: Bensin')
    assert S.MARK_SCOPE not in p.block and 'Nyckelantaganden' not in p.block
    assert p.notes.startswith('Räknar bensinen')


def test_a_part_that_answered_for_another_driver_is_rejected():
    with pytest.raises(S.EvidensSplitError, match='drivare 2'):
        S.split_part(DRIVERS[1], part_text(1, 'Bensin'))


def test_a_part_without_a_block_is_rejected():
    with pytest.raises(S.EvidensSplitError, match='saknar ett drivarblock'):
        S.split_part(DRIVERS[0], f'Bara prat.\n{S.MARK_SCOPE}\nnoter')


def test_a_part_without_its_scope_statement_is_rejected():
    # The scope is what the merge reads to find double counting.
    text = part_text(1, 'Bensin').replace(S.MARK_SCOPE, '')
    with pytest.raises(S.EvidensSplitError, match='avgränsning'):
        S.split_part(DRIVERS[0], text)


def test_a_block_with_no_span_and_no_stated_reason_is_rejected():
    text = f'Drivare 1: Bensin\n  Mekanism: teknikbyte\n{S.MARK_SCOPE}\nnoter'
    with pytest.raises(S.EvidensSplitError, match='antagandespann'):
        S.split_part(DRIVERS[0], text)


def test_an_explicitly_unquantified_driver_is_a_valid_part():
    text = (f'Drivare 2: El\n  Mekanism: Klimatnyttan kvantifieras inte för drivaren.\n'
            f'{S.MARK_SCOPE}\nKorrigeringspost.')
    assert S.split_part(DRIVERS[1], text).block.startswith('Drivare 2: El')


def test_part_instruction_names_its_driver_and_all_the_others():
    text = S.part_instruction(DRIVERS[1], DRIVERS)
    assert 'Drivare 2: Tillkommande el för laddning' in text
    assert 'Drivare 1: Bensin i 15 lövblåsar' in text
    assert S.MARK_SCOPE in text


# ---------- merge: completeness ----------

def test_cover_check_names_the_missing_driver():
    with pytest.raises(S.EvidensSplitError, match='saknas för drivare 2'):
        S.check_parts_cover(DRIVERS, parts()[:1])


def test_cover_check_rejects_duplicates_and_strangers():
    ps = parts()
    with pytest.raises(S.EvidensSplitError, match='dubbla'):
        S.check_parts_cover(DRIVERS, ps + [ps[0]])
    stranger = S.Part(S.Driver(9, 'x'), 'Drivare 9: x', '', '')
    with pytest.raises(S.EvidensSplitError, match='okända drivare 9'):
        S.check_parts_cover(DRIVERS, ps + [stranger])


def test_cover_check_accepts_exactly_one_part_per_driver():
    S.check_parts_cover(DRIVERS, list(reversed(parts())))


# ---------- merge: assembly ----------

def test_blocks_are_inserted_verbatim_in_driver_order():
    ps = parts()
    text, corrected = S.assemble(list(reversed(ps)), merge_text())
    assert corrected == []
    assert ps[0].block in text and ps[1].block in text
    assert text.index(ps[0].block) < text.index(ps[1].block)
    assert S.MARK_DRIVERS not in text and S.MARK_CORRECTIONS not in text


def test_assembled_text_has_the_monolithic_sections_in_order():
    text, _ = S.assemble(parts(), merge_text())
    order = ['Evidens & antaganden för åtgärd', 'Kort om detta steg', 'Underlag från tidigare steg',
             'Påverkade drivare och parametrar', 'Antaganden per drivare',
             'Nyckelantaganden', 'Övergripande antaganden', 'Dataluckor för detta steg',
             'Externa källor och studier', 'Samstämmighetskontroll']
    positions = [text.index(h) for h in order]
    assert positions == sorted(positions)
    # The model wrote the section heading before the marker too; one survives.
    assert text.count('Antaganden per drivare') == 1


def test_panel_parser_sees_each_driver_once_with_its_numbers():
    text, _ = S.assemble(parts(), merge_text())
    ev = parse_evidence(text)
    assert [d['number'] for d in ev['drivers']] == [1, 2]
    d1 = ev['drivers'][0]
    assert d1['factors']['territoriell'] == 1.0
    assert d1['parameters'][0]['med'] == '-1,0'
    # The overview line "Drivare 1: påverkas via ΔA" would otherwise have drawn
    # a second, empty card for driver 1.
    assert 'Drivare 1 (påverkas via ΔA)' in text
    assert 'Samstämmighetskontroll' in [s['title'] for s in ev['sections']]


def test_a_correction_replaces_that_block_and_only_that_block():
    ps = parts()
    fixed = part_text(2, 'Tillkommande el för laddning', med='0,0').split(S.MARK_SCOPE)[0]
    text, corrected = S.assemble(ps, merge_text(corrections=fixed))
    assert corrected == [2]
    assert ps[1].block not in text
    assert ps[0].block in text
    meds = [d['parameters'][0]['med'] for d in parse_evidence(text)['drivers']]
    assert meds == ['-1,0', '0,0']


def test_a_correction_for_a_driver_that_does_not_exist_fails():
    with pytest.raises(S.EvidensSplitError, match='drivare 7'):
        S.assemble(parts(), merge_text(corrections=part_text(7, 'Påhittad').split(S.MARK_SCOPE)[0]))


def test_a_stray_sentence_about_a_driver_never_replaces_its_block():
    # Review finding, reproduced: this line matched the heading pattern and
    # contains "kvantifieras", and used to replace driver 1's whole block.
    stray = ('Drivare 2 | ΔA | Antagande_med: 0,0\n\n'
             'Drivare 1: ingen ändring behövs, kvantifieras precis som i delsvaret.')
    with pytest.raises(S.EvidensSplitError, match='varken är en fälträttelse eller ett helt drivarblock'):
        S.assemble(parts(), merge_text(corrections=stray))


def test_two_whole_block_rewrites_of_one_driver_fail():
    block = part_text(2, 'El', med='0,0').split(S.MARK_SCOPE)[0]
    with pytest.raises(S.EvidensSplitError, match='två gånger'):
        S.assemble(parts(), merge_text(corrections=block + '\n' + block))


def test_a_correction_without_numbers_fails():
    with pytest.raises(S.EvidensSplitError, match='varken är en fälträttelse'):
        S.assemble(parts(), merge_text(corrections='Drivare 1: Bensin\n  Mekanism: ändrad'))


def test_field_edits_change_exactly_the_named_fields():
    edits = ('Drivare 2 | ΔA | Antagande_med: 0,0 (följer drivare 1)\n'
             'Drivare 1 | - | Overlap_faktor: 0.82\n'
             '- Drivare 2 | ΔA | Tidsaspekt: per effektår enligt drivare 1')
    ps = parts()
    text, corrected = S.assemble(ps, merge_text(corrections=edits))
    assert corrected == [2, 1]
    d1, d2 = parse_evidence(text)['drivers']
    assert d1['factors']['overlap'] == 0.82 and d1['factors']['territoriell'] == 1.0
    assert d1['parameters'][0]['med'] == '-1,0'
    assert d2['parameters'][0]['med'] == '0,0 (följer drivare 1)'
    assert d2['parameters'][0]['tidsaspekt'] == 'per effektår enligt drivare 1'
    assert d2['parameters'][0]['min'] == '-0,5'
    # The edit lines themselves never reach the text step 5 reads.
    assert '|' not in text


def test_a_field_edit_drops_the_old_values_continuation_lines():
    block = ('Drivare 1: Bensin\n  Parameter: ΔA\n    Antagande_med: -0,9, vilket\n'
             '      fortsätter på nästa rad\n    Enhet: andel')
    out = S.apply_field_edit(block, 1, 'ΔA', 'Antagande_med', '-0,5')
    assert 'fortsätter' not in out
    assert '    Antagande_med: -0,5\n    Enhet: andel' in out


def test_a_field_edit_matches_the_parameter_name_without_its_gloss():
    block = ('Drivare 1: X\n  Parameter: adoption (andel av flottan)\n    Antagande_med: 0,3\n'
             '  Parameter: ΔEF\n    Antagande_med: -0,1')
    out = S.apply_field_edit(block, 1, 'adoption', 'Antagande_med', '0,5')
    assert '0,5' in out and '-0,1' in out and '0,3' not in out


@pytest.mark.parametrize('param,label,value,match', [
    ('ΔEF', 'Antagande_med', '0', 'parametern "ΔEF"'),
    ('ΔA', 'Antagande_typ', '0', 'Antagande_typ'),
    ('-', 'Antagande_med', '0', 'drivarnivån'),
    ('ΔA', 'Antagande_med', ' ', 'saknar ett nytt värde'),
])
def test_a_field_edit_that_cannot_be_applied_raises(param, label, value, match):
    # apply_field_edit never applies it. Whether the step fails is assemble's
    # call: a missing target is skipped with a note (tests below), an empty
    # value fails.
    with pytest.raises(S.EvidensSplitError, match=match):
        S.apply_field_edit(parts()[0].block, 1, param, label, value)


@pytest.mark.parametrize('param,label,value', [
    ('ΔEF', 'Antagande_med', '0'),
    ('ΔA', 'Antagande_typ', '0'),
    ('-', 'Antagande_med', '0'),
])
def test_a_missing_target_is_its_own_error_kind(param, label, value):
    with pytest.raises(S.EditTargetMissing):
        S.apply_field_edit(parts()[0].block, 1, param, label, value)


def test_an_empty_value_is_not_a_missing_target():
    with pytest.raises(S.EvidensSplitError) as e:
        S.apply_field_edit(parts()[0].block, 1, 'ΔA', 'Antagande_med', ' ')
    assert not isinstance(e.value, S.EditTargetMissing)


# The popup package in the driftsmedel run 2026-10-21 stopped with 422 on this
# shape: "Rättelsen av drivare 7 gäller fältet "Kvalitet" på parametern
# "attribution", som inte finns i blocket." The block had the parameter but
# not the field.
POPUP_LIKE = ('Drivare 2 | ΔA | Antagande_med: 0,0 (följer drivare 1)\n'
              'Drivare 1 | ΔA | Kvalitetsbedömning: medel\n'
              'Drivare 1 | attribution | Kvalitet: låg')


def test_an_edit_of_a_field_the_block_lacks_is_skipped_not_fatal():
    ps = parts()
    text, corrected, skipped = S.assemble_with_skipped(ps, merge_text(corrections=POPUP_LIKE))
    # The edit that fits is applied; the two that do not are skipped.
    assert corrected == [2]
    assert len(skipped) == 2
    assert 'fältet "Kvalitetsbedömning" på parametern "ΔA"' in skipped[0]
    assert 'parametern "attribution"' in skipped[1]
    # Driver 1 stands exactly as its part wrote it.
    assert ps[0].block in text
    d1, d2 = parse_evidence(text)['drivers']
    assert d2['parameters'][0]['med'] == '0,0 (följer drivare 1)'
    assert d1['parameters'][0]['med'] == '-1,0'


def test_a_skipped_edit_is_written_into_the_text_steps_6_and_7_read():
    text, _, skipped = S.assemble_with_skipped(parts(), merge_text(corrections=POPUP_LIKE))
    note = S.SKIPPED_NOTE.format(n=2)
    assert note in text
    for msg in skipped:
        assert f'- {msg}' in text
    # After the consistency check, inside its section, so the panel shows it
    # there; and no line of it reads as a driver heading.
    assert text.index('Samstämmighetskontroll') < text.index(note)
    sections = parse_evidence(text)['sections']
    assert note in next(s for s in sections if s['title'] == 'Samstämmighetskontroll')['body']
    assert [d['number'] for d in parse_evidence(text)['drivers']] == [1, 2]
    assert '|' not in text


def test_the_note_never_lands_in_the_last_drivers_card():
    # Review finding: a merge whose tail is empty put the note right after
    # driver 2's block, where its first line read as a field of that driver.
    frame = merge_text(corrections=POPUP_LIKE)
    head, rest = frame.split(S.MARK_DRIVERS)
    _, corr = rest.split(S.MARK_CORRECTIONS)
    text, _, skipped = S.assemble_with_skipped(
        parts(), f'{head}{S.MARK_DRIVERS}\n{S.MARK_CORRECTIONS}{corr}')
    assert len(skipped) == 2
    ev = parse_evidence(text)
    for d in ev['drivers']:
        assert 'anmärkning' not in str(d).lower()
    body = next(s for s in ev['sections'] if s['title'] == 'Samstämmighetskontroll')['body']
    assert S.SKIPPED_NOTE.format(n=2) in body


def test_no_note_when_nothing_was_skipped():
    text, _, skipped = S.assemble_with_skipped(parts(), merge_text(
        corrections='Drivare 1 | - | Overlap_faktor: 0.82'))
    assert skipped == []
    assert 'Programmets anmärkning' not in text


def test_assemble_keeps_its_two_value_shape():
    text, corrected = S.assemble(parts(), merge_text(corrections=POPUP_LIKE))
    assert corrected == [2] and S.SKIPPED_NOTE.format(n=2) in text


def test_an_ambiguous_parameter_still_fails_the_step():
    # Skipping is only for a target that is not there. Two parameters with the
    # name could hide the one the merge meant, so that still stops.
    block = ('Drivare 1: Bensin\n  Mekanism: x\n  Parameter: annan (kapacitet)\n'
             '    Antagande_min: 1\n    Antagande_med: 1,5\n    Antagande_max: 2\n'
             '  Parameter: annan (EF)\n    Antagande_med: 80')
    ps = [S.Part(DRIVERS[0], block, '', ''), parts()[1]]
    with pytest.raises(S.EvidensSplitError, match='2 parametrar'):
        S.assemble(ps, merge_text(corrections='Drivare 1 | annan | Antagande_med: 2'))


def test_a_field_edit_on_an_ambiguous_parameter_name_fails():
    block = ('Drivare 3: Batteri\n  Parameter: annan (kapacitet)\n    Antagande_med: 1,5\n'
             '  Parameter: annan (EF)\n    Antagande_med: 80')
    with pytest.raises(S.EvidensSplitError, match='2 parametrar'):
        S.apply_field_edit(block, 3, 'annan', 'Antagande_med', '2,0')


@pytest.mark.parametrize('line', [
    '**Drivare 1** | - | Overlap_faktor: 0.82',
    '| Drivare 1 | - | Overlap_faktor: 0.82 |',
    '1. Drivare 1 | - | Overlap_faktor: 0.82',
    '* Drivare 1 | - | Overlap_faktor: 0.82',
])
def test_a_field_edit_in_a_near_miss_shape_is_still_applied(line):
    # F29: these used to be dropped without a word while the consistency
    # check said the overlap had been corrected.
    text, corrected = S.assemble(parts(), merge_text(corrections=line))
    assert corrected == [1]
    assert parse_evidence(text)['drivers'][0]['factors']['overlap'] == 0.82


@pytest.mark.parametrize('line', [
    'Drivare 1 | - | Overlap_faktor 0.82',              # no colon
    'Drivare 1 Overlap_faktor: 0.82',                    # no separators
    'Ändra Drivare 1 | Overlap_faktor | 0.82',           # prose in front
    'Drivare 1 – Overlap_faktor: 0.82',                  # dash instead of pipes
    'Drivare 1 (bil), Overlap_faktor: 0.82',             # short name and a comma
    'Drivare 1 – ΔA – Antagande_med: 0,5',               # parameter between dashes
])
def test_a_correction_the_program_cannot_read_fails_the_step(line):
    # The dash forms start like a replacement block and are refused as one.
    with pytest.raises(S.EvidensSplitError, match='inte kan läsa|varken är en fälträttelse'):
        S.assemble(parts(), merge_text(corrections=line))


def test_an_unreadable_edit_after_a_replacement_block_is_not_swallowed_into_it():
    block = parts()[1].block
    with pytest.raises(S.EvidensSplitError, match='inte kan läsa'):
        S.assemble(parts(), merge_text(corrections=block + '\nDrivare 1 Overlap_faktor: 0.82'))


# TLF workshop 2026-10-14: a rebuilt block's comment held a pipe and named
# another driver, and the step stopped as if it were a misformed correction.
WORKSHOP_FIELD = ('    Kommentar_antagande: Minskningen per bytt kilometer blir i stort sett '
                  'hela EF_BAU. Livscykelutsläpp för el | räknas i Drivare 2 (el).')


def test_a_rebuilt_block_field_naming_a_driver_beside_a_pipe_assembles():
    block = parts()[0].block.replace('    Kommentar_antagande: schablon', WORKSHOP_FIELD)
    final, corrected = S.assemble(parts(), merge_text(corrections=block))
    assert corrected == [1]
    assert 'räknas i Drivare 2 (el).' in final


def test_the_same_field_line_outside_a_block_is_still_refused():
    with pytest.raises(S.EvidensSplitError, match='inte kan läsa'):
        S.assemble(parts(), merge_text(corrections=WORKSHOP_FIELD.strip()))


def test_no_corrections_and_prose_mentioning_a_driver_still_assemble():
    # The last two name a field label, but as a sentence about it, not as an
    # edit (pre-merge review: they failed the step with a 422).
    for corrections in ('Inga', 'Inga rättelser behövs, drivare 1 och 2 stämmer överens.',
                        'Drivare 1 och 2 stämmer överens: inga rättelser.',
                        'Drivare 1 och 2 har samma Overlap_faktor: ingen rättelse behövs.',
                        'Drivare 2 (el) har redan rätt Antagande_med: 0,5 räcker.'):
        _text, corrected = S.assemble(parts(), merge_text(corrections=corrections))
        assert corrected == []


def test_a_field_edit_for_a_driver_that_does_not_exist_fails():
    with pytest.raises(S.EvidensSplitError, match='drivare 4'):
        S.assemble(parts(), merge_text(corrections='Drivare 4 | ΔA | Antagande_med: 0'))


def test_a_merge_without_the_block_marker_fails_rather_than_dropping_the_blocks():
    with pytest.raises(S.EvidensSplitError, match='drivarblocken'):
        S.assemble(parts(), merge_text().replace(S.MARK_DRIVERS, ''))


def test_a_merge_without_the_corrections_marker_fails():
    with pytest.raises(S.EvidensSplitError, match='korrigeringar'):
        S.assemble(parts(), merge_text().replace(S.MARK_CORRECTIONS, ''))


def test_merge_instruction_carries_every_part_and_the_double_counting_check():
    text = S.merge_instruction(parts())
    for p in parts():
        assert p.block in text and p.notes in text
    assert 'Dubbelräkning' in text and 'ΔA och ΔEF' in text


# ---------- endpoints, with the model stubbed ----------

def fake_complete(calls: list, fail_driver: int | None = None):
    """A complete() that answers like a part or a merge depending on the
    instruction it was given, and records every call."""
    def complete(step, system, messages, max_output):
        calls.append(step)
        if step == 'evidens_part':
            m = re.search(r'ansvarar ENBART för:\s*\n\s*Drivare (\d+): (.+)', system)
            n, name = int(m.group(1)), m.group(2).strip()
            if n == fail_driver:
                raise ModelOutputError('Modellen slog i sitt tokentak och svaret klipptes av.')
            return part_text(n, name)
        if step == 'evidens_merge':
            return merge_text()
        raise AssertionError(f'unexpected step {step}')
    return complete


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


def test_plan_endpoint_lists_the_drivers(client):
    body = client.post('/api/evidens/plan', json={'history': HISTORY}).get_json()
    assert body == {'drivers': [{'number': 1, 'name': 'Bensin i 15 lövblåsar'},
                                {'number': 2, 'name': 'Tillkommande el för laddning'}]}


def test_merge_endpoint_refuses_an_incomplete_set_without_calling_the_model(client, monkeypatch):
    calls: list = []
    monkeypatch.setattr(S, 'complete', fake_complete(calls))
    resp = client.post('/api/evidens/merge', json={
        'history': HISTORY,
        'parts': [{'number': 1, 'text': part_text(1, 'Bensin i 15 lövblåsar')}],
    })
    assert resp.status_code == 422
    assert 'saknas för drivare 2' in resp.get_json()['error']
    assert calls == []


def test_merge_endpoint_revalidates_part_text_from_the_client(client, monkeypatch):
    calls: list = []
    monkeypatch.setattr(S, 'complete', fake_complete(calls))
    resp = client.post('/api/evidens/merge', json={
        'history': HISTORY,
        'parts': [{'number': 1, 'text': part_text(1, 'Bensin')},
                  {'number': 2, 'text': 'Drivare 2: El\n  Mekanism: x'}],
    })
    assert resp.status_code == 422
    assert calls == []


def test_merge_endpoint_answers_200_and_lists_a_skipped_edit(client, monkeypatch):
    # The 422 that stopped the popup package, through the endpoint.
    def complete(step, system, messages, max_output):
        return merge_text(corrections=POPUP_LIKE)
    monkeypatch.setattr(S, 'complete', complete)
    resp = client.post('/api/evidens/merge', json={
        'history': HISTORY,
        'parts': [{'number': 1, 'text': part_text(1, 'Bensin i 15 lövblåsar')},
                  {'number': 2, 'text': part_text(2, 'Tillkommande el för laddning')}],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['corrected'] == [2]
    assert len(body['skipped']) == 2 and 'Kvalitetsbedömning' in body['skipped'][0]
    assert S.SKIPPED_NOTE.format(n=2) in body['output']


def test_part_endpoint_rejects_an_unknown_driver(client):
    resp = client.post('/api/evidens/part', json={'history': HISTORY, 'driver': 5})
    assert resp.status_code == 400


def test_part_endpoint_surfaces_a_model_failure(client, monkeypatch):
    monkeypatch.setattr(S, 'complete', fake_complete([], fail_driver=1))
    resp = client.post('/api/evidens/part', json={'history': HISTORY, 'driver': 1})
    assert resp.status_code == 502
    assert 'tokentak' in resp.get_json()['error']


def test_full_split_through_run_batch_matches_the_evidens_response_shape(client, monkeypatch):
    import run_batch
    calls: list = []
    monkeypatch.setattr(S, 'complete', fake_complete(calls))
    status, body = run_batch.post_evidens_split(A.app, HISTORY, lambda msg: None)
    assert status == 200, body
    assert sorted(calls) == ['evidens_merge', 'evidens_part', 'evidens_part']
    assert calls[-1] == 'evidens_merge'
    assert [d['number'] for d in body['evidence']['drivers']] == [1, 2]
    assert body['corrected'] == []


def test_run_batch_meters_the_parallel_parts_under_their_package(client, monkeypatch, tmp_path):
    """The parts run in pool threads; their calls must still be counted under
    the package that started them, through the real complete()."""
    import types

    import run_batch
    from caia import api_client

    def answer(kwargs):
        m = re.search(r'ansvarar ENBART för:\s*\n\s*Drivare (\d+): (.+)', kwargs['system'])
        text = part_text(int(m.group(1)), m.group(2).strip()) if m else merge_text()
        usage = types.SimpleNamespace(input_tokens=100, output_tokens=10)
        return types.SimpleNamespace(content=[types.SimpleNamespace(type='text', text=text)],
                                     stop_reason='end_turn', usage=usage)

    stub = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: answer(kw)))
    monkeypatch.setattr(api_client, 'get_client', lambda: stub)
    meter = run_batch.UsageMeter()
    monkeypatch.setattr(api_client, 'USAGE_LISTENERS', [meter])
    token = meter.start('lovblasare', tmp_path / 'usage.jsonl')
    try:
        status, body = run_batch.post_evidens_split(A.app, HISTORY, lambda msg: None)
    finally:
        run_batch._PACKAGE.reset(token)
    assert status == 200, body
    rows = [json.loads(line) for line in (tmp_path / 'usage.jsonl').read_text().splitlines()]
    assert sorted(r['step'] for r in rows) == ['evidens_merge', 'evidens_part', 'evidens_part']
    assert {r['package'] for r in rows} == {'lovblasare'}


def test_run_batch_fails_the_step_when_one_part_fails_and_never_merges(client, monkeypatch):
    import run_batch
    calls: list = []
    monkeypatch.setattr(S, 'complete', fake_complete(calls, fail_driver=2))
    status, body = run_batch.post_evidens_split(A.app, HISTORY, lambda msg: None)
    assert status != 200
    assert 'drivare 2' in body['error']
    assert 'evidens_merge' not in calls


# ---------- the web client's half, run in node ----------

def _post_step_js() -> str:
    from test_report_row import _inline_script
    js = _inline_script()
    start = js.index('async function postJson')
    end = js.index('function showAuth')
    return js[start:end]


def _run_client(responder: str, step: str = 'evidens') -> dict:
    """Run the page's postStep in node against a scripted server. The pauses
    between retries are cut to nothing so a test does not wait them out."""
    page_js = _post_step_js().replace('setTimeout(resolve, ms)', 'setTimeout(resolve, 0)')
    assert page_js != _post_step_js(), 'the retry pause moved; the harness would wait it out'
    harness = f"""
let runToken = 0;
const state = {{mode: 'uppfoljning'}};
const calls = [];
const modes = [];
function panelSection() {{ return null; }}
const respond = {responder};
async function authFetch(url, opts) {{
  const body = JSON.parse(opts.body);
  modes.push(body.mode);
  calls.push([url, body.driver === undefined ? null : body.driver, body.parts ? body.parts.map(p => p.number) : null]);
  const r = await respond(url, body);
  return {{ok: r.status === 200, status: r.status, jsonSafe: async () => r.body}};
}}
{page_js}
postStep({step!r}, [{{role: 'user', content: 'x'}}]).then(res => {{
  console.log(JSON.stringify({{res, calls, modes}}));
}});
"""
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(harness)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


RESPONDER = """async (url, body) => {
  if (url === '/api/evidens/plan') return {status: 200, body: {drivers: [{number: 1, name: 'a'}, {number: 2, name: 'b'}, {number: 3, name: 'c'}]}};
  if (url === '/api/evidens/part') {
    if (body.driver === FAIL) return {status: 500, body: {error: 'Modellen slog i sitt tokentak'}};
    return {status: 200, body: {number: body.driver, name: 'x', text: 'part ' + body.driver}};
  }
  if (url === '/api/evidens/merge') return {status: 200, body: {output: 'merged', evidence: {drivers: []}}};
  if (url === '/api/evidens') return {status: 200, body: {output: 'single'}};
  return {status: 404, body: {error: 'no route'}};
}"""


@pytest.mark.node
def test_client_runs_every_part_then_merges_them_all():
    out = _run_client(RESPONDER.replace('FAIL', 'null'))
    assert out['res'] == {'ok': True, 'status': 200, 'data': {'output': 'merged', 'evidence': {'drivers': []}}}
    urls = [c[0] for c in out['calls']]
    assert urls[0] == '/api/evidens/plan' and urls[-1] == '/api/evidens/merge'
    assert sorted(c[1] for c in out['calls'] if c[0] == '/api/evidens/part') == [1, 2, 3]
    assert out['calls'][-1][2] == [1, 2, 3]
    # The plan, every part and the merge carry the page's analysis mode.
    assert out['modes'] == ['uppfoljning'] * len(out['calls'])


@pytest.mark.node
def test_client_fails_the_step_when_one_part_fails_and_never_merges():
    out = _run_client(RESPONDER.replace('FAIL', '2'))
    assert out['res']['ok'] is False
    assert 'drivare 2' in out['res']['data']['error']
    assert 'tokentak' in out['res']['data']['error']
    assert '/api/evidens/merge' not in [c[0] for c in out['calls']]
    # A 500 is our own fault and would fail again: no retry, and the parts
    # that worked ran once.
    parts = [c[1] for c in out['calls'] if c[0] == '/api/evidens/part']
    assert parts.count(2) == 1 and parts.count(1) == 1 and parts.count(3) == 1


@pytest.mark.node
def test_client_fails_the_step_when_a_part_request_throws():
    responder = RESPONDER.replace('FAIL', 'null').replace(
        "if (url === '/api/evidens/part') {",
        "if (url === '/api/evidens/part') { if (body.driver === 3) throw new Error('Failed to fetch');")
    out = _run_client(responder)
    assert out['res']['ok'] is False
    assert 'drivare 3' in out['res']['data']['error']
    assert '/api/evidens/merge' not in [c[0] for c in out['calls']]


@pytest.mark.node
def test_client_uses_the_single_call_when_no_drivers_parse():
    responder = RESPONDER.replace('FAIL', 'null').replace(
        "{drivers: [{number: 1, name: 'a'}, {number: 2, name: 'b'}, {number: 3, name: 'c'}]}",
        '{drivers: []}')
    out = _run_client(responder)
    assert out['res']['data'] == {'output': 'single'}
    assert [c[0] for c in out['calls']] == ['/api/evidens/plan', '/api/evidens']


# A part the provider refuses once (ten people at step 4 at the same time) is
# tried again on its own. Before, one refusal failed the step and the user's
# retry re-ran every part that had already worked.
FLAKY = """
const tries = {};
const respond_ = RESPONDER_;
const respond = async (url, body) => {
  if (url === '/api/evidens/part' && body.driver === 2) {
    tries[2] = (tries[2] || 0) + 1;
    if (tries[2] <= TIMES) return {status: STATUS, body: Object.assign({error: 'Språkmodelltjänsten tar inte emot fler anrop just nu.'}, RETRYABLE ? {retryable: true} : {})};
  }
  return respond_(url, body);
};
"""


def _flaky(times: int, status: int, retryable: bool = False) -> str:
    # _run_client binds the responder to `respond`; this wraps the plain one.
    return '(() => {' + FLAKY.replace('RESPONDER_', RESPONDER.replace('FAIL', 'null')) \
        .replace('TIMES', str(times)).replace('STATUS', str(status)) \
        .replace('RETRYABLE', 'true' if retryable else 'false') + 'return respond; })()'


@pytest.mark.node
@pytest.mark.parametrize('status,retryable', [(502, True), (503, False)])
def test_a_part_that_fails_once_is_retried_alone_and_the_step_succeeds(status, retryable):
    # 502 marked retryable: the provider busy, unreachable or 5xx, all fast.
    # 503: the platform's own, before our code ran.
    out = _run_client(_flaky(1, status, retryable))
    assert out['res']['ok'] is True and out['res']['data']['output'] == 'merged'
    parts = [c[1] for c in out['calls'] if c[0] == '/api/evidens/part']
    assert parts.count(2) == 2 and parts.count(1) == 1 and parts.count(3) == 1
    assert out['calls'][-1][2] == [1, 2, 3]


@pytest.mark.node
@pytest.mark.parametrize('status', [401, 403, 413, 429, 422, 500, 502, 504])
def test_a_failure_that_would_fail_again_is_not_retried(status):
    # The request itself refused; our own fault (500, 422); a model timeout
    # (502 without retryable: minutes spent, and a new try is a new paid
    # call); the platform's 504 (the function ran out of time).
    out = _run_client(_flaky(1, status))
    assert out['res']['ok'] is False
    parts = [c[1] for c in out['calls'] if c[0] == '/api/evidens/part']
    assert parts.count(2) == 1


@pytest.mark.node
def test_a_dropped_connection_on_a_part_is_retried():
    responder = RESPONDER.replace('FAIL', 'null').replace(
        "if (url === '/api/evidens/part') {",
        "if (url === '/api/evidens/part') { globalThis.n = (globalThis.n || 0) + (body.driver === 3); "
        "if (body.driver === 3 && globalThis.n === 1) throw new Error('Failed to fetch');")
    out = _run_client(responder)
    assert out['res']['ok'] is True
    assert [c[1] for c in out['calls'] if c[0] == '/api/evidens/part'].count(3) == 2


@pytest.mark.node
def test_other_steps_get_one_retry_on_a_passing_failure():
    responder = """async (url, body) => {
      globalThis.n = (globalThis.n || 0) + 1;
      if (globalThis.n === 1) return {status: 502, body: {error: 'Språkmodelltjänsten svarade med fel 529.', retryable: true}};
      return {status: 200, body: {output: 'qa klar'}};
    }"""
    out = _run_client(responder, step='qa')
    assert out['res']['ok'] is True and out['res']['data']['output'] == 'qa klar'
    assert [c[0] for c in out['calls']] == ['/api/qa', '/api/qa']


@pytest.mark.node
def test_other_steps_stop_after_one_retry():
    responder = """async (url, body) => ({status: 502, body: {error: 'Kunde inte nå språkmodelltjänsten.', retryable: true}})"""
    out = _run_client(responder, step='rapport')
    assert out['res']['ok'] is False and 'nå' in out['res']['data']['error']
    assert [c[0] for c in out['calls']] == ['/api/rapport', '/api/rapport']


@pytest.mark.node
def test_a_model_timeout_is_handed_to_the_user_not_retried():
    responder = """async (url, body) => ({status: 502, body: {error: 'Modellen svarade inte i tid. Kör steget igen.'}})"""
    out = _run_client(responder, step='qa')
    assert out['res']['ok'] is False and 'i tid' in out['res']['data']['error']
    assert [c[0] for c in out['calls']] == ['/api/qa']


@pytest.mark.node
def test_a_retry_stops_when_the_user_started_a_new_analysis():
    # "Ny analys" during the pause between tries: the old run must not spend
    # another model call on an analysis nobody is looking at.
    responder = """async (url, body) => { runToken++; return {status: 502, body: {error: 'upptagen', retryable: true}}; }"""
    out = _run_client(responder, step='qa')
    assert [c[0] for c in out['calls']] == ['/api/qa']


# ---------- DIN SPEC 91637: the attribute fields on an indirect driver ----------

def _indirect_part(n: int, name: str) -> str:
    return part_text(n, name).replace(
        '  Mekanism: teknikbyte\n',
        '  Mekanism: möjliggörande, fler laddplatser gör elbil lättare att välja\n'
        '  Attribut: avstånd till närmaste publika laddpunkt, i dag 1,8 km, efter 0,6 km\n'
        '  Uppfattning: bekvämlighet\n'
        '  Osäkraste_led: attribut till beteende, ingen lokal mätning av vad avståndet betyder\n')


def test_the_attribute_fields_stay_at_driver_level_and_leave_the_numbers_alone():
    """Recommendation 3 of an internal comparison with DIN SPEC 91637: the three lines
    sit between Mekanism and the factors. They must not open or end a
    parameter, nor change what step 5 and the panel read."""
    ps = [S.split_part(DRIVERS[0], _indirect_part(1, DRIVERS[0].name)),
          S.split_part(DRIVERS[1], part_text(2, DRIVERS[1].name))]
    text, _ = S.assemble(ps, merge_text())
    d1, d2 = parse_evidence(text)['drivers']
    extra = {e['label']: e['value'] for e in d1['extra']}
    assert extra['Attribut'].startswith('avstånd till närmaste publika laddpunkt')
    assert extra['Uppfattning'] == 'bekvämlighet'
    assert extra['Osäkraste_led'].startswith('attribut till beteende')
    assert d1['mekanism'].startswith('möjliggörande')
    assert d1['factors']['territoriell'] == 1.0 and d1['factors']['overlap'] == 1.0
    assert len(d1['parameters']) == 1 and d1['parameters'][0]['med'] == '-1,0'
    assert d2['extra'] == []


def test_the_merge_can_correct_an_attribute_field():
    ps = [S.split_part(DRIVERS[0], _indirect_part(1, DRIVERS[0].name)),
          S.split_part(DRIVERS[1], part_text(2, DRIVERS[1].name))]
    text, corrected = S.assemble(ps, merge_text(
        corrections='Drivare 1 | - | Osäkraste_led: åtgärdens andel, bytet sker ändå'))
    assert corrected == [1]
    d1 = parse_evidence(text)['drivers'][0]
    assert {e['label']: e['value'] for e in d1['extra']}['Osäkraste_led'] == 'åtgärdens andel, bytet sker ändå'
    assert d1['parameters'][0]['med'] == '-1,0'


def test_the_evidens_prompt_asks_for_the_attribute_before_the_chain():
    from caia.agents.evidens import SYSTEM_PROMPT
    block = SYSTEM_PROMPT[SYSTEM_PROMPT.index('"  Mekanism:'):SYSTEM_PROMPT.index('"  Klimatfaktorer')]
    for label in ('"  Attribut:', '"  Uppfattning:', '"  Osäkraste_led:'):
        assert label in block
    # Only for indirect drivers: a direct one keeps its old, shorter block.
    assert 'indirekt eller möjliggörande' in block and 'utelämnar du dem' in block
    # The merge may name them as driver-level fields.
    assert 'Attribut, Uppfattning, Osäkraste_led' in ' '.join(S.merge_instruction(parts()).split())
