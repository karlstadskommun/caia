"""What the action changes in each driver's own unit (DIN SPEC 91637 5.2).

The engine turns A_BAU and ΔA × adoption into sentences beside the tons: so
many km less in the target year and on average over the window, and for a
driver that changes its emission factor, the least amount that must go
without emissions. The tests hold the sentences to the tons themselves: the
change in activity times the emission factor must give the reduction the
engine reports, attribution and unit conversion included.

Every expected number is worked out by hand in the comment above it.
"""
from __future__ import annotations

import pytest
from caia.appendix import activity_for_report, with_activity, with_engine_appendix
from caia.calc import CalcModel, activity_changes, compute, render_activity
from caia.calc.engine import (
    ACTIVITY_HEADING,
    ACTIVITY_STAMP,
    APPENDIX_HEADING,
    _activity_year,
    _driver_year,
    activity_unit,
    render_appendix,
    render_markdown,
)
from caia.mode import UPPFOLJNING
from caia.pipeline import BRIDGE
from caia.web.app import extract_key_metric
from pytest import approx


def _drv(**over) -> dict:
    d = {
        'name': 'Bilresor i tjänsten', 'baseline_year': 2024, 'a0': 1_000_000.0,
        'a0_unit': 'km/år', 'ef0': 0.15, 'ef0_unit': 'kg CO2e/km',
        'ramp': {'start_year': 2026, 'full_effect_year': 2028, 'profile': 'linjär'},
        'g_a': 0.0, 'g_ef': -0.02,
        'delta_a': {'min': -0.05, 'med': -0.1, 'max': -0.2}, 'delta_ef': 0.0,
        'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
    }
    d.update(over)
    return d


def _model(*drivers, mode='potential') -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                'drivers': list(drivers) or [_drv()]}, mode=mode)


def _text(model: CalcModel, i: int = 0) -> str:
    return activity_changes(model)['rows'][i]['text']


# ---------- the numbers ----------

# The worked example in METOD.md: 1 000 000 km, ΔA −10 % (min −5, max −20),
# linear ramp 2026-2028 (0, 50, 100 %). 2030: 100 000 km less, 10 %, span
# 50 000 to 200 000. Average 2026-2030: (0 + 50 000 + 3 × 100 000) / 5 = 70 000.
def test_the_worked_example_in_km():
    assert _text(_model()) == ('100 000 km mindre år 2030 än utan åtgärden (10 %, spann '
                               '50 000–200 000), i snitt 70 000 km mindre per år 2026–2030')


# HVO for diesel: 35 000 litres, ΔEF −60 % (min −30, max −85), full effect 2027.
# 2030: 60 % lower per litre, so at least 0,6 × 35 000 = 21 000 litres without
# emissions. Average 2026-2030: 2026 is 0, then four years of 21 000: 16 800,
# shown with two digits as 17 000.
def test_a_factor_change_states_the_least_amount_that_switches():
    d = _drv(name='Diesel i skolbussar', a0=35_000.0, a0_unit='liter/år', ef0=2.6,
             ef0_unit='kg CO2e/liter', g_ef=0.0, delta_a=0.0,
             delta_ef={'min': -0.3, 'med': -0.6, 'max': -0.85},
             ramp={'start_year': 2026, 'full_effect_year': 2027})
    ac = activity_changes(_model(d))
    assert ac['rows'][0]['text'] == (
        'utsläppen per liter är 60 % lägre år 2030, som om minst 21 000 av 35 000 liter gick '
        'helt utan utsläpp, i snitt minst 17 000 liter per år 2026–2030')
    assert any(n.startswith('Minst:') for n in ac['notes'])


# ---------- the rule: the units and the tons are the same change ----------

@pytest.mark.parametrize('over', [
    {},
    {'attribution': {'min': 0.3, 'med': 0.5, 'max': 0.7}},
    # 210 ton against a factor per kg: the engine counts 210 000 kg.
    {'a0': 210.0, 'a0_unit': 'ton nyvara/år', 'ef0': 2.1, 'ef0_unit': 'kg CO2e/kg', 'g_ef': 0.0},
    {'g_a': 0.03, 'delta_a': {'min': -0.2, 'med': -0.4, 'max': -0.6}},
])
def test_activity_change_times_the_factor_is_the_reduction(over):
    """ΔE = A_BAU × EF_BAU × (−ΔA × adoption) × attribution, so the change in
    activity times the emission factor, in the factor's unit, gives ΔE back
    in every year and scenario."""
    drv = _model(_drv(**over)).drivers[0]
    for sc in ('min', 'med', 'max'):
        for y in range(2026, 2031):
            r = _driver_year(drv, sc, y)
            a = _activity_year(drv, sc, y, 1.0)
            assert -a['change'] * drv.a0_scale * r.ef_bau / 1000 == approx(r.basis)


@pytest.mark.parametrize('attribution', [1.0, 0.4])
def test_the_amount_without_emissions_times_the_factor_is_the_reduction(attribution):
    """With ΔEF alone, ΔE = A × EF_BAU × (−ΔEF × adoption) × attribution: the
    amount that would go without emissions times the old factor."""
    drv = _model(_drv(delta_a=0.0, delta_ef={'min': -0.2, 'med': -0.5, 'max': -0.9},
                      attribution=attribution)).drivers[0]
    for sc in ('min', 'med', 'max'):
        for y in range(2026, 2031):
            r = _driver_year(drv, sc, y)
            assert _activity_year(drv, sc, y, 1.0)['zero'] * r.ef_bau / 1000 == approx(r.basis)


def test_attribution_halves_the_change_and_says_so():
    # 1 000 000 × 10 % × 0,5 = 50 000 km in 2030.
    ac = activity_changes(_model(_drv(attribution=0.5)))
    assert ac['rows'][0]['text'].startswith('50 000 km mindre år 2030 än utan åtgärden (5 %, spann')
    assert any('åtgärdens egen del' in n for n in ac['notes'])


def test_a_scaled_unit_is_shown_in_the_unit_the_analysis_wrote():
    # 210 ton, ΔA −10 %: 21 ton, not 21 000 kg.
    m = _model(_drv(a0=210.0, a0_unit='ton nyvara/år', ef0=2.1, ef0_unit='kg CO2e/kg', g_ef=0.0))
    assert _text(m).startswith('21 ton nyvara mindre år 2030')


# ---------- the cases around it ----------

@pytest.mark.parametrize('unit, expected', [
    ('km/år', ('km', 1.0)),
    ('m² BTA/år', ('m² BTA', 1.0)),
    ('kWh batterikapacitet per år (400 kWh fördelat över 10 år)', ('kWh batterikapacitet', 1.0)),
    ('km (58 deltagare', ('km', 1.0)),
    ('100 kr', ('kr', 100.0)),
    ('', ('enheter', 1.0)),
    ('kg CO2e/år', None),
    ('ton CO₂e', None),
])
def test_the_unit_as_a_reader_counts_it(unit, expected):
    assert activity_unit(unit) == expected


def test_a_driver_counted_in_emissions_has_no_other_unit():
    m = _model(_drv(name='Medarbetares arbetssätt', a0=85_000.0, a0_unit='kg CO2e/år', ef0=1.0,
                    ef0_unit='kg CO2e/kg CO2e', g_ef=0.0))
    assert _text(m) == 'räknas direkt i utsläpp, så det finns ingen annan enhet att visa'


def test_a_one_off_is_its_own_year():
    # 40 kWh made in 2027, ΔA +100 %: 40 kWh more that year, no average.
    d = _drv(name='Batteriets tillverkning', kind='engång', year=2027, a0=40.0,
             a0_unit='kWh batterikapacitet', ef0=80.0, ef0_unit='kg CO2e/kWh',
             delta_a={'min': 1.0, 'med': 1.0, 'max': 1.0}, terr=0.0, cons=1.0, overlap=0.0)
    assert _text(_model(d)) == ('40 kWh batterikapacitet mer år 2027 än utan åtgärden '
                                '(engångspost)')


def test_an_effect_that_has_ended_by_the_target_year():
    # Full effect 2026, ended after 2027 (medel): 0 in 2030, 2 of 5 years at
    # 100 000: 40 000 on average.
    d = _drv(ramp={'start_year': 2026, 'full_effect_year': 2026, 'end_year': 2027})
    assert _text(_model(d)) == ('ingen ändring år 2030, i snitt 40 000 km mindre per år '
                                '2026–2030')


def test_a_driver_that_changes_nothing_is_left_out_and_no_section_is_written():
    m = _model(_drv(delta_a=0.0))
    assert activity_changes(m) == {'rows': [], 'notes': []}
    assert render_activity(m) == ''


def test_the_follow_up_window_is_the_measures_own_years():
    # Follow-up: the average runs over the cumulative window, 2026-2030 here.
    m = _model(_drv(), mode=UPPFOLJNING)
    assert 'i snitt 70 000 km mindre per år 2026–2030' in _text(m)


def test_a_name_with_a_newline_stays_on_its_bullet():
    md = render_activity(_model(_drv(name='Bilresor\n## Rubrik')))
    assert '- Bilresor ## Rubrik: 100 000 km' in md


# ---------- the report ----------

def _kalkyl(model: CalcModel) -> str:
    r = compute(model)
    return '\n\n'.join(p for p in (render_markdown(model, r), render_activity(model),
                                   render_appendix(model, r)) if p)


def _history(kalkyl: str) -> list[dict]:
    return [{'role': 'user', 'content': 'åtgärd'}, {'role': 'assistant', 'content': kalkyl},
            {'role': 'user', 'content': BRIDGE['kalkyl']}]


REPORT = """## Tjänstecyklar

**Kort beskrivning av åtgärden**

Text.

**Beräknad klimatnytta**

Huvudresultat (Scenario Medel):
  Medel effekt/år (Netto/Total): 9,5 ton CO2e/år

**Hur åtgärden minskar utsläppen**

Huvuddrivare.

**Källor och underlag**

- En källa.
"""


def test_the_section_goes_into_the_report_beside_the_tons():
    hist = _history(_kalkyl(_model()))
    block = activity_for_report(hist)
    assert block.startswith(ACTIVITY_HEADING) and ACTIVITY_STAMP in block
    assert APPENDIX_HEADING not in block
    out, _ = with_engine_appendix(REPORT, hist)
    assert (out.index('**Beräknad klimatnytta**') < out.index(ACTIVITY_HEADING)
            < out.index('**Hur åtgärden minskar utsläppen**') < out.index(APPENDIX_HEADING))
    assert out.count(ACTIVITY_HEADING) == 1
    # The saved report's key numbers are read as before.
    assert extract_key_metric(out) == {'net': 9.5}


def test_a_copy_the_model_made_is_replaced_by_the_engines():
    hist = _history(_kalkyl(_model()))
    copied = REPORT.replace('**Hur åtgärden',
                            f'{ACTIVITY_HEADING}\n\n- Bilresor: 999 km mindre.\n\n**Hur åtgärden')
    out, _ = with_engine_appendix(copied, hist)
    assert out.count(ACTIVITY_HEADING) == 1
    assert '999 km' not in out
    assert '**Hur åtgärden minskar utsläppen**' in out


def test_without_the_result_heading_the_section_goes_last():
    body = "## X\n\n**Annat**\n\nText."
    assert with_activity(body, "BLOCK").endswith("Text.\n\nBLOCK")


def test_a_kalkyl_without_the_section_leaves_the_report_as_before():
    # An older run, or the language model's fallback: no block, nothing moved.
    m = _model()
    r = compute(m)
    hist = _history(render_markdown(m, r) + '\n\n' + render_appendix(m, r))
    assert activity_for_report(hist) == ''
    out, _ = with_engine_appendix(REPORT, hist)
    assert ACTIVITY_HEADING not in out
    assert activity_for_report(_history(f'{ACTIVITY_HEADING}\n\n- påhittat')) == ''


def test_a_sentence_that_starts_like_the_next_heading_does_not_move_the_block():
    # Code review: an intro line "Hur åtgärden minskar utsläppen beskrivs nedan."
    # put the block before the result. Only a whole-line title counts, and
    # only after "Beräknad klimatnytta".
    hist = _history(_kalkyl(_model()))
    prose = REPORT.replace('Text.', 'Hur åtgärden minskar utsläppen beskrivs nedan.')
    out, _ = with_engine_appendix(prose, hist)
    assert (out.index('**Beräknad klimatnytta**') < out.index(ACTIVITY_HEADING)
            < out.index('**Hur åtgärden minskar utsläppen**'))


@pytest.mark.parametrize('heading', ['## 3. Hur åtgärden minskar utsläppen',
                                     'Hur åtgärden minskar utsläppen',
                                     '**Hur åtgärden minskar utsläppen:**'])
def test_the_next_heading_in_any_form_the_model_writes(heading):
    body = REPORT.replace('**Hur åtgärden minskar utsläppen**', heading)
    out = with_activity(body, 'BLOCK')
    assert out.index('Huvudresultat') < out.index('BLOCK') < out.index(heading)


def test_a_follow_up_report_gets_the_block_right_after_the_result():
    body = REPORT.replace('**Hur åtgärden', '**Uppmätt och antaget**\n\nMätt.\n\n**Hur åtgärden')
    out = with_activity(body, 'BLOCK')
    assert out.index('Huvudresultat') < out.index('BLOCK') < out.index('**Uppmätt och antaget**')


def test_removing_a_copy_stops_at_a_bare_title_line():
    # Code review: the copy's removal ran on through a bare next heading and
    # its body. A title on a line of its own ends the copy too.
    copied = REPORT.replace(
        '**Hur åtgärden minskar utsläppen**\n\nHuvuddrivare.',
        f'{ACTIVITY_HEADING}\n\n- Bilresor: 999 km mindre.\n\n'
        'Hur åtgärden minskar utsläppen\n\nHuvuddrivare.')
    out = with_activity(copied, 'BLOCK')
    assert '999 km' not in out
    assert 'Hur åtgärden minskar utsläppen\n\nHuvuddrivare.' in out
    assert out.index('BLOCK') < out.index('Hur åtgärden minskar utsläppen')


def test_a_written_off_purchase_is_weighed_by_the_whole_purchase():
    # Review 2026-11-10: the row's text is about the purchase, so its weight is
    # the purchase's tons, not the first year's tenth of them.
    screens = {'name': 'Tillverkning av skärmar', 'kind': 'engång', 'year': 2026, 'baseline_year': 2024,
               'a0': 5.0, 'a0_unit': 'st', 'ef0': 400.0, 'ef0_unit': 'kg CO2e/st', 'lifetime': 10,
               'delta_a': 1.0, 'delta_ef': 0.0, 'terr': 0.0, 'cons': 1.0, 'overlap': 0.0}
    m = _model(_drv(), screens)
    assert m.drivers[1].write_off
    rows = {r['driver']: r for r in activity_changes(m)['rows']}
    assert rows['Tillverkning av skärmar']['weight'] == approx(2.0)
