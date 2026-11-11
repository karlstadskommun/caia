"""The action's own emissions and its benefit treated alike (the review of the
driftsmedel runs 1 and 2, 2026-10-22).

Four things the engine now does itself instead of trusting the extraction:

- turns an attribution band that stands the wrong way round on a driver that
  lowers emissions (klimatkrav i anläggning, run 1: "15 % (30 till 5)");
- keeps "pengarnas egna utsläpp" (the grant in kronor × kg per krona) out of a
  follow-up's result and shows it on its own row at most 0,012 kg/kr
  (krisberedskap, run 2: 204 935 kr × 0,04 = −4,1 ton);
- charges a one-off piece of equipment only for the years of its lifetime it
  brought forward, when the benefit stops at a catch-up year
  (energivisualisering: 1,25 ton of screens in full against a benefit clipped
  in 2027);
- converts an activity in ton against a factor per kg (krisberedskap, run 2:
  210 ton × 2,1 kg/kg counted as 0,44 ton). That one is in test_units.py.

Hand-computed cases. Climate factors terr 0, cons 1, overlap 0, so net = ΔE.
"""
from __future__ import annotations

import pytest
from caia.agents.uppfoljning import KARNA, STEG
from caia.calc import CalcModel, compute, render_appendix, render_markdown
from caia.calc.engine import _driver_year, bearing, sanity_warnings
from caia.calc.schema import SPEND_EF_PER_KR, UNBOUNDED_YEAR, Triple
from caia.mode import POTENTIAL, UPPFOLJNING
from pytest import approx


def _benefit(**over) -> dict:
    """1000 kWh × 1 kg = 1 ton a year, −20 % from 2024, attribution 50 %."""
    d = {
        'name': 'Elanvändning i köken', 'baseline_year': 2022, 'a0': 1000.0, 'a0_unit': 'kWh/år',
        'ef0': 1.0, 'ef0_unit': 'kg CO2e/kWh',
        'ramp': {'start_year': 2024, 'full_effect_year': 2024, 'profile': 'linjär'},
        'g_a': 0.0, 'g_ef': 0.0,
        'delta_a': {'min': -0.1, 'med': -0.2, 'max': -0.3}, 'delta_ef': 0.0,
        'attribution': {'min': 0.3, 'med': 0.5, 'max': 0.7},
        'terr': 0.0, 'cons': 1.0, 'overlap': 0.0,
    }
    d.update(over)
    return d


def _screens(**over) -> dict:
    """Five screens at 400 kg each, a one-off in 2023: 2 ton."""
    d = {
        'name': 'Tillverkning av skärmar', 'kind': 'engång', 'year': 2023, 'baseline_year': 2022,
        'a0': 5.0, 'a0_unit': 'st', 'ef0': 400.0, 'ef0_unit': 'kg CO2e/st',
        'delta_a': 1.0, 'delta_ef': 0.0, 'terr': 0.0, 'cons': 1.0, 'overlap': 0.0,
    }
    d.update(over)
    return d


def _spend(**over) -> dict:
    d = {
        'name': 'Pengarnas egna utsläpp', 'kind': 'engång', 'year': 2025, 'baseline_year': 2024,
        'a0': 204935.0, 'a0_unit': 'kr', 'ef0': 0.04, 'ef0_unit': 'kg CO2e/kr',
        'delta_a': {'min': 1.0, 'med': 0.5, 'max': 0.2}, 'delta_ef': 0.0,
        'terr': 0.05, 'cons': 1.0, 'overlap': 0.05,
    }
    d.update(over)
    return d


def _model(*drivers, mode=UPPFOLJNING) -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                'drivers': list(drivers)}, mode=mode)


def _notes(m) -> list[str]:
    return sanity_warnings(compute(m), m)


# ---------- the attribution band follows the scenario ----------

def test_an_inverted_band_on_a_driver_that_lowers_emissions_is_turned():
    m = _model(_benefit(attribution={'min': 0.3, 'med': 0.15, 'max': 0.05}))
    d = m.drivers[0]
    assert (d.attribution.min, d.attribution.med, d.attribution.max) == (0.05, 0.15, 0.3)
    assert d.attribution_given == Triple(0.3, 0.15, 0.05)
    r = compute(m)
    lo, med, hi = (r[sc]['total']['cumulative_net'] for sc in ('min', 'med', 'max'))
    # 2024-2030, 7 years: 1 ton × ΔA × attribution.
    assert (lo, med, hi) == (approx(7 * 0.1 * 0.05), approx(7 * 0.2 * 0.15),
                             approx(7 * 0.3 * 0.3))
    note = next(w for w in _notes(m) if 'omvänd ordning' in w)
    assert note.startswith('OBS: Elanvändning i köken: attributionen stod i omvänd ordning '
                           '(15 % (30 till 5))')
    assert '15 % (5 till 30)' in note


def test_an_inverted_band_on_a_driver_that_raises_emissions_is_left():
    # Losses in a battery: more emissions, its own share, highest in min.
    m = _model(_benefit(name='Förluster', delta_a={'min': 1.0, 'med': 0.8, 'max': 0.2},
                        attribution={'min': 0.5, 'med': 0.3, 'max': 0.1}))
    d = m.drivers[0]
    assert (d.attribution.min, d.attribution.max) == (0.5, 0.1)
    assert d.attribution_given is None
    assert not any('omvänd ordning' in w for w in _notes(m))


def test_a_band_in_the_right_order_is_left():
    m = _model(_benefit())
    assert m.drivers[0].attribution == Triple(0.3, 0.5, 0.7)
    assert m.drivers[0].attribution_given is None


def test_a_driver_that_changes_sign_between_scenarios_is_left():
    # An annual driver: more emissions in min, fewer in medel and max. Which
    # way its band should go cannot be read off it.
    m = _model(_benefit(delta_a={'min': 1.0, 'med': 0.6, 'max': 0.3},
                        delta_ef={'min': 0.0, 'med': -0.6, 'max': -0.95},
                        attribution={'min': 1.0, 'med': 1.0, 'max': 0.8}))
    d = m.drivers[0]
    assert d.direction('min') == 1 and d.direction('med') == -1
    assert d.attribution == Triple(1.0, 1.0, 0.8) and d.attribution_given is None


def test_a_one_off_that_turned_into_a_reduction_is_a_cost_again():
    # Sola, run 2: a study trip, ΔA 60 % (100 till 30) and ΔEF −60 % (0 till
    # −95): more emissions in min, "fewer" in medel and max. A trip is a cost
    # in every scenario; the band stays as written.
    m = _model(_screens(name='Studieresa', a0=10000.0, a0_unit='pkm', ef0=0.1,
                        ef0_unit='kg CO2e/pkm', year=2024,
                        delta_a={'min': 1.0, 'med': 0.6, 'max': 0.3},
                        delta_ef={'min': 0.0, 'med': -0.6, 'max': -0.95},
                        attribution={'min': 1.0, 'med': 1.0, 'max': 0.8}))
    d = m.drivers[0]
    assert all(d.direction(sc) == 1 for sc in ('min', 'med', 'max'))
    assert d.attribution == Triple(1.0, 1.0, 0.8) and d.attribution_given is None


def test_the_direction_is_read_on_the_change_not_on_one_band():
    # ΔA up, ΔEF down by more: the driver lowers emissions in medel.
    m = _model(_benefit(delta_a=0.1, delta_ef=-0.5,
                        attribution={'min': 0.6, 'med': 0.4, 'max': 0.2}))
    assert m.drivers[0].direction() == -1
    assert m.drivers[0].attribution.min == 0.2


# ---------- pengarnas egna utsläpp ----------

def test_the_grants_own_emissions_are_kept_out_of_a_follow_up():
    alone = _model(_benefit())
    m = _model(_benefit(), _spend())
    assert [d.name for d in m.drivers] == ['Elanvändning i köken']
    assert [d.name for d in m.spend_posts] == ['Pengarnas egna utsläpp']
    assert compute(m)['med']['total']['cumulative_net'] == approx(
        compute(alone)['med']['total']['cumulative_net'])


def test_the_spend_post_is_shown_on_its_own_row_with_a_service_factor():
    m = _model(_benefit(), _spend())
    r = compute(m)
    text = render_markdown(m, r)
    assert 'Pengarnas egna utsläpp (ingår inte i resultatet):' in text
    # 204 935 kr × 0,012 kg/kr = 2 459 kg.
    assert '204 935 kr × 0,012 kg CO2e/kr = 2,5 ton CO2e, 2025.' in text
    assert 'Analysen angav 0,04 kg CO2e/kr' in text
    assert 'Pengarnas egna utsläpp (ingår inte i resultatet):' in render_appendix(m, r)
    assert any(w.startswith('OBS: en post räknade pengarnas egna utsläpp') for w in _notes(m))
    assert SPEND_EF_PER_KR == 0.012


def test_a_lower_spend_factor_is_kept():
    m = _model(_benefit(), _spend(ef0=0.005))
    assert '204 935 kr × 0,005 kg CO2e/kr = 1,0 ton CO2e' in render_markdown(m, compute(m))
    assert 'Analysen angav' not in render_markdown(m, compute(m))


def test_thousands_of_kronor_are_counted_as_kronor():
    m = _model(_benefit(), _spend(a0=204.935, a0_unit='tkr', ef0=40.0, ef0_unit='kg CO2e/tkr'))
    assert '204 935 kr × 0,012 kg CO2e/kr = 2,5 ton CO2e' in render_markdown(m, compute(m))


def test_a_unit_of_a_hundred_kronor_is_money():
    # Testcyklisterna, run 2: gift cards, 600 × 100 kr at 3 kg CO2e per 100 kr.
    # ΔA 33 % (100 till 8,3) and ΔEF −33 % (0 till −67): more emissions in
    # min, fewer in medel. A cost all the same, and since omgång 3 the engine
    # makes it one in every scenario before it sorts out the spend posts.
    m = _model(_benefit(), _spend(name='Presentkort', a0=600.0, a0_unit='100 kr',
                                  ef0=3.0, ef0_unit='kg CO2e/100 kr',
                                  delta_a={'min': 1.0, 'med': 0.333, 'max': 0.083},
                                  delta_ef={'min': 0.0, 'med': -0.333, 'max': -0.667}))
    assert m.spend_posts[0].flip_given is not None and m.spend_posts[0].direction() == 1
    assert [d.name for d in m.spend_posts] == ['Presentkort']
    assert '60 000 kr × 0,012 kg CO2e/kr = 0,7 ton CO2e' in render_markdown(m, compute(m))
    assert 'Analysen angav 0,03 kg CO2e/kr' in render_markdown(m, compute(m))


def test_the_spend_factor_is_read_per_krona_from_its_own_unit():
    # 200 tkr next to 0,04 kg CO2e per kr: 200 000 kr, capped to 0,012.
    m = _model(_benefit(), _spend(a0=200.0, a0_unit='tkr', ef0=0.04, ef0_unit='kg CO2e/kr'))
    text = render_markdown(m, compute(m))
    assert '200 000 kr × 0,012 kg CO2e/kr = 2,4 ton CO2e' in text
    assert 'Analysen angav 0,04 kg CO2e/kr' in text


@pytest.mark.parametrize('unit, kronor', [
    ('mnkr', 1e6), ('Mkr', 1e6), ('miljoner kr', 1e6), ('tusen kronor', 1e3),
    ('1 000 kr', 1e3), ('kr/år', 1.0),
])
def test_money_units(unit, kronor):
    from caia.calc import units
    assert units.kronor_per_unit(unit) == kronor


def test_potential_mode_keeps_the_spend_post_as_a_driver():
    m = _model(_benefit(), _spend(), mode=POTENTIAL)
    assert len(m.drivers) == 2 and m.spend_posts == []


def test_a_driver_in_kronor_that_lowers_emissions_stays():
    m = _model(_benefit(), _spend(name='Undvikna inköp', delta_a=-0.5))
    assert len(m.drivers) == 2 and m.spend_posts == []


def test_the_spend_posts_year_stays_in_the_window():
    # The benefit starts 2026, the money was spent 2025. The average is over
    # 2025-2030 with or without the post, as before the post left the result.
    late = _benefit(ramp={'start_year': 2026, 'full_effect_year': 2026})
    m = _model(late, _spend())
    r = compute(m)
    assert r['med']['total']['avg_window'] == (2025, 2030)
    assert r['med']['total']['avg_net'] == approx(5 * 0.2 * 0.5 / 6)


def test_a_follow_up_of_only_a_spend_post_computes_to_zero():
    m = _model(_spend())
    r = compute(m)
    assert m.drivers == [] and r['med']['total']['cumulative_net'] == 0.0
    assert 'Pengarnas egna utsläpp' in render_markdown(m, r)


# ---------- equipment charged for the years it brought forward ----------

ENDS = {'min': 2025, 'med': 2027, 'max': 2029}


def test_screens_are_charged_for_the_years_they_came_earlier():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024,
                              'end_year': ENDS}),
               _screens(lifetime=10))
    s = m.drivers[1]
    assert s.catch_up == Triple(2025, 2027, 2029) and s.catch_up_from == 'nyttan'
    # (catch-up + 1 − 2023) / 10: 3, 5 and 7 years of 10.
    assert [s.charged_share(sc) for sc in ('min', 'med', 'max')] == [0.3, 0.5, 0.7]
    assert _driver_year(s, 'med', 2023).net == approx(-1.0)
    assert _driver_year(s, 'min', 2023).net == approx(-0.6)
    assert _driver_year(s, 'max', 2023).net == approx(-1.4)
    text = render_markdown(m, compute(m))
    assert ('engångspost 2023, livslängd 10 år, ikapp-år 2027 (nyttans sista år): insatsen '
            'belastas med 50 % av posten (medel)') in text


def test_the_analysis_own_catch_up_year_wins():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ENDS}),
               _screens(lifetime=10, end_year=2024))
    s = m.drivers[1]
    assert s.catch_up_from == '' and s.charged_share('med') == approx(0.2)


def test_potential_mode_writes_the_equipment_off_over_its_lifetime():
    # Henric 2026-11-10 (CAIA 1.1): until then the whole 2 ton fell in 2023.
    m = _model(_benefit(), _screens(lifetime=10), mode=POTENTIAL)
    s = m.drivers[1]
    assert s.catch_up is None and s.write_off
    assert [_driver_year(s, 'med', y).net for y in (2023, 2027, 2032)] == approx([-0.2] * 3)
    assert _driver_year(s, 'med', 2033).net == 0.0
    assert sum(_driver_year(s, 'med', y).net for y in range(2023, 2045)) == approx(-2.0)
    # The year's own purchase stays visible beside the share it carries.
    assert _driver_year(s, 'med', 2023).before_write_off == approx(-2.0)


def test_a_lifetime_of_part_years_ends_with_the_part():
    m = _model(_screens(lifetime=2.5), mode=POTENTIAL)
    s = m.drivers[0]
    assert [_driver_year(s, 'med', y).basis for y in range(2023, 2027)] == approx(
        [-0.8, -0.8, -0.4, 0.0])


def test_annual_purchases_carry_a_share_of_each_year_bought():
    """Ten machines a year from 2026 at 100 kg: each year bought adds a
    quarter of a ton to the next four years, so the target year carries
    the whole yearly purchase only once four years have been bought."""
    buy = {'name': 'Tillverkning av maskiner', 'baseline_year': 2025, 'a0': 10.0,
           'a0_unit': 'st/år', 'ef0': 100.0, 'ef0_unit': 'kg CO2e/st', 'g_a': 0.0, 'g_ef': 0.0,
           'delta_a': 1.0, 'delta_ef': 0.0, 'terr': 0.0, 'cons': 1.0, 'overlap': 0.0,
           'ramp': {'start_year': 2026, 'full_effect_year': 2026, 'profile': 'stegvis'},
           'lifetime': {'min': 3, 'med': 4, 'max': 5}}
    m = _model(buy, mode=POTENTIAL)
    s = m.drivers[0]
    assert s.write_off
    assert [_driver_year(s, 'med', y).net for y in range(2026, 2031)] == approx(
        [-0.25, -0.5, -0.75, -1.0, -1.0])
    # Shortest lifetime in min: the cautious scenario carries the most.
    assert _driver_year(s, 'min', 2027).net == approx(-2 / 3)
    assert compute(m)['headline']['net'] == approx(-1.0)


def test_a_potential_one_off_is_written_off_only_to_the_benefits_end():
    ends = {'min': 2027, 'med': 2027, 'max': 2027}
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ends}),
               _screens(lifetime=10), mode=POTENTIAL)
    s = m.drivers[1]
    assert s.catch_up == Triple(2027, 2027, 2027) and s.catch_up_from == 'nyttan'
    assert _driver_year(s, 'med', 2027).net == approx(-0.2)
    assert _driver_year(s, 'med', 2028).net == 0.0
    assert sum(_driver_year(s, 'med', y).net for y in range(2023, 2040)) == approx(-1.0)


def test_a_potential_end_year_on_the_purchase_year_is_not_a_catch_up():
    # Lövblåsare 2026-11-09: 2026 / 2026 / 2026 on a one-off from 2026 meant
    # "that year only". As a catch-up year it would charge a tenth.
    m = _model(_screens(lifetime=10, end_year=2023), mode=POTENTIAL)
    s = m.drivers[0]
    assert s.catch_up is None
    assert sum(_driver_year(s, 'med', y).net for y in range(2023, 2040)) == approx(-2.0)


def test_a_catch_up_at_the_purchase_in_one_scenario_is_said():
    # Review 2026-11-10: medel 2027 keeps the catch-up, but min 2023 caps the
    # post at its purchase year, so min carries a tenth of it.
    m = _model(_screens(lifetime=10, end_year={'min': 2023, 'med': 2027, 'max': 2030}), mode=POTENTIAL)
    s = m.drivers[0]
    assert s.catch_up == Triple(2023, 2027, 2030)
    assert sum(_driver_year(s, 'min', y).net for y in range(2023, 2040)) == approx(-0.2)
    said = [w for w in sanity_warnings(compute(m), m) if 'ikapp-året' in w]
    assert len(said) == 1 and 'ikapp-året i min är inte senare än inköpsåret 2023' in said[0], said
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024,
                              'end_year': {'min': 2027, 'med': 2027, 'max': 2027}}),
               _screens(lifetime=10), mode=POTENTIAL)
    assert not [w for w in sanity_warnings(compute(m), m) if 'ikapp-året' in w]


def test_a_follow_up_does_not_write_off_an_annual_driver():
    m = _model(_benefit(delta_a=0.5, lifetime=8))
    assert m.drivers[0].lifetime is None and not m.drivers[0].write_off


def test_a_benefit_with_a_lifetime_is_not_written_off():
    m = _model(_benefit(lifetime=8), mode=POTENTIAL)
    assert m.drivers[0].lifetime is not None and not m.drivers[0].write_off


def test_an_annual_lifetime_that_is_no_number_of_years_is_dropped_not_refused():
    m = _model(_benefit(delta_a=0.5, lifetime={'min': 0, 'med': 8, 'max': 10}), mode=POTENTIAL)
    assert m.drivers[0].lifetime is None and not m.drivers[0].write_off


def test_the_appendix_shows_the_purchase_beside_the_written_off_share():
    m = _model(_benefit(), _screens(lifetime=10), mode=POTENTIAL)
    app = render_appendix(m, compute(m))
    assert '| ΔE före avskrivning (ton) | ΔE (ton) |' in app
    assert 'skrivs av jämnt över livslängden' in app
    assert '| Andel av livslängden |' not in app
    assert ('engångspost 2023, livslängd 10 år, skrivs av jämnt över livslängden'
            in render_markdown(m, compute(m)))


def test_an_annual_write_off_lifetime_is_a_bearing_assumption():
    buy = _benefit(name='Tillverkning', delta_a=1.0, attribution=1.0,
                   lifetime={'min': 2, 'med': 4, 'max': 8})
    m = _model(_benefit(), buy, mode=POTENTIAL)
    items = bearing(m, compute(m))['items']
    life = [it for it in items if it['field'] == 'lifetime']
    assert life and life[0]['driver'] == 'Tillverkning' and life[0]['on_ramp']
    assert life[0]['low'] < life[0]['high']


def test_without_a_catch_up_the_equipment_is_written_off_to_the_target_year():
    # 2026-10-22: the benefit counts to 2030, so does the equipment.
    m = _model(_benefit(), _screens(lifetime=10))
    s = m.drivers[1]
    assert s.catch_up == Triple(2030, 2030, 2030) and s.catch_up_from == 'målåret'
    # (2030 + 1 − 2023) / 10 = 0,8 of 2 ton.
    assert _driver_year(s, 'med', 2023).net == approx(-1.6)
    text = render_markdown(m, compute(m))
    assert ('engångspost 2023, livslängd 10 år, avskriven till och med målåret 2030: insatsen '
            'belastas med 80 % av posten (medel)') in text
    assert '(målåret + 1 − köpår) / livslängd' in render_appendix(m, compute(m))


def test_a_lifetime_within_the_window_is_charged_in_full():
    m = _model(_benefit(), _screens(lifetime=5))
    assert m.drivers[1].charged_share('med') == 1.0


def test_a_catch_up_after_the_target_year_is_capped():
    m = _model(_benefit(), _screens(lifetime=10, end_year=2035))
    s = m.drivers[1]
    assert s.catch_up == Triple(2030, 2030, 2030) and s.catch_up_from == 'målåret'
    assert s.charged_share('med') == approx(0.8)


def test_a_one_off_without_a_lifetime_is_still_charged_in_full():
    m = _model(_benefit(), _screens())
    assert m.drivers[1].catch_up is None
    assert _driver_year(m.drivers[1], 'med', 2023).net == approx(-2.0)


def test_one_benefit_that_never_ends_in_a_scenario_writes_that_scenario_off_to_the_target():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024,
                              'end_year': {'med': 2027}}),
               _screens(lifetime=10))
    s = m.drivers[1]
    assert s.catch_up.min == 2030 and s.charged_share('min') == approx(0.8)
    assert s.charged_share('med') == approx(0.5) and s.catch_up_from == 'nyttan'


# ---------- a cost never becomes a benefit ----------

def test_a_one_off_cost_written_as_more_at_a_lower_factor_is_the_added_part():
    # Återbrukscontainern, omgång 3: the containers' manufacture as ΔA +100 %
    # with ΔEF −60 % on the whole post, (2 × 0,4) − 1 = −0,2: a benefit.
    m = _model(_benefit(), _screens(delta_a=1.0, delta_ef=-0.6))
    s = m.drivers[1]
    assert s.delta_a == Triple(0.4, 0.4, 0.4) and s.delta_ef == Triple(0.0, 0.0, 0.0)
    assert s.flip_given is not None
    # 5 × 400 kg × 0,4 = 0,8 ton charged, not 0,4 ton saved.
    assert _driver_year(s, 'med', 2023).net == approx(-0.8)
    note = next(w for w in _notes(m) if 'En kostnad blir aldrig en nytta' in w)
    assert 'kostnaden räknades som en minskning av utsläppen' in note


def test_the_unflip_is_per_scenario_and_says_when_the_cost_only_shrank():
    m = _model(_benefit(), _screens(delta_a=1.0,
                                    delta_ef={'min': 0.0, 'med': -0.2, 'max': -0.3}))
    s = m.drivers[1]
    assert s.delta_a == Triple(1.0, approx(0.8), approx(0.7))
    assert any('kostnaden blev mindre än den tillkomna mängden' in w for w in _notes(m))


def test_a_one_off_cost_written_plainly_is_left():
    m = _model(_benefit(), _screens())
    assert m.drivers[1].flip_given is None
    assert not any('aldrig en nytta' in w for w in _notes(m))


def test_an_avoided_purchase_is_not_unflipped():
    m = _model(_benefit(), _screens(name='Undvikna inköp', delta_a=-1.0, delta_ef=0.2))
    assert m.drivers[1].flip_given is None


def test_an_annual_driver_is_not_unflipped():
    m = _model(_benefit(delta_a=0.5, delta_ef=-0.6))
    assert m.drivers[0].flip_given is None


def test_potential_mode_does_not_unflip():
    m = _model(_benefit(), _screens(delta_a=1.0, delta_ef=-0.6), mode=POTENTIAL)
    assert m.drivers[1].flip_given is None


def test_a_catch_up_before_the_purchase_charges_nothing():
    m = _model(_benefit(), _screens(lifetime=10, end_year=2021))
    assert m.drivers[1].charged_share('med') == 0.0


def test_a_long_bring_forward_is_capped_at_the_whole_post():
    m = _model(_benefit(), _screens(lifetime=3, end_year=2029))
    assert m.drivers[1].charged_share('med') == 1.0


def test_an_avoided_purchase_is_not_shrunk_by_the_lifetime_share():
    m = _model(_benefit(), _screens(name='Undvikna inköp', delta_a=-1.0, lifetime=5,
                                    end_year=2024))
    assert m.drivers[1].charged_share('med') == 1.0
    assert _driver_year(m.drivers[1], 'med', 2023).net == approx(2.0)


@pytest.mark.parametrize('bad', ['5 år', [5], {'min': 'x'}])
def test_an_unreadable_lifetime_is_dropped_not_refused(bad):
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ENDS}),
               _screens(lifetime=bad))
    assert m.drivers[1].lifetime is None
    assert any('Ange då utrustningens livslängd' in w for w in _notes(m))


def test_a_catch_up_without_a_lifetime_is_not_weighed_as_bearing():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ENDS}),
               _screens(end_year=ENDS))
    fields = {it['field'] for it in bearing(m, compute(m))['items']}
    assert 'catch_up' not in fields and 'lifetime' not in fields


def test_a_lifetime_of_zero_is_refused():
    with pytest.raises(ValueError, match='livslängden'):
        _model(_benefit(), _screens(lifetime=0))


def test_a_one_off_without_lifetime_against_an_ending_benefit_is_noted():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ENDS}),
               _screens())
    note = next(w for w in _notes(m) if 'livslängd' in w)
    assert note.startswith('OBS: engångsposten Tillverkning av skärmar belastar insatsen fullt '
                           '2023, men nyttan upphör efter 2027 (medel)')
    assert _driver_year(m.drivers[1], 'med', 2023).net == approx(-2.0)


def test_no_note_when_the_benefit_does_not_end():
    assert not any('livslängd' in w for w in _notes(_model(_benefit(), _screens())))


def test_the_appendix_shows_the_share_and_the_bearing_check_weighs_it():
    m = _model(_benefit(ramp={'start_year': 2024, 'full_effect_year': 2024, 'end_year': ENDS}),
               _screens(lifetime={'min': 8, 'med': 10, 'max': 12}))
    r = compute(m)
    app = render_appendix(m, r)
    assert '| Andel av livslängden |' in app
    assert '(ikapp-år + 1 − köpår) / livslängd' in app
    assert 'ikapp-år 2025 / 2027 / 2029 (min / medel / max)' in app
    # Every table row has as many cells as its header.
    for block in app.split('\n\n'):
        rows = [ln for ln in block.splitlines() if ln.startswith('|')]
        if rows:
            assert len({ln.count('|') for ln in rows}) == 1, block
    fields = {(it['driver'], it['field']) for it in bearing(m, r)['items']}
    assert ('Tillverkning av skärmar', 'lifetime') in fields
    assert ('Tillverkning av skärmar', 'catch_up') in fields


# ---------- the rules reach the prompts ----------

def test_the_follow_up_rules_name_the_symmetry_the_money_and_the_pilot():
    assert 'Insatsens egna utsläpp och dess nytta behandlas lika' in KARNA
    assert 'pengarnas egna utsläpp' in KARNA
    assert 'består efter piloten' in KARNA and 'Undanträngning' in KARNA
    assert 'Utan belägg antas det inte' in KARNA
    assert '"lifetime"' in STEG['kalkyl_extract']
    assert 'MINSKAR utsläppen har min den LÄGSTA andelen' in STEG['kalkyl_extract']
    assert 'Ett\n  ikapp-år kräver belägg' in STEG['baslinje']


def test_the_follow_up_rules_after_the_review_of_omgang_3():
    # 2026-10-22: no double deductions, measured persistence first, a
    # cost never a benefit, follow-on effects shown, Klimatklivet's electricity
    # factor and equipment written off to the target year.
    flat = " ".join(KARNA.split())
    assert '"kunde ha" gjort det ändå, utan stöd i underlaget, är däremot inget skäl' in flat
    assert 'Krav i upphandlingar, beslut, avtal, rutiner och köpta saker är inga kampanjer' in flat
    assert 't × ln 2 / (−ln r)' in flat
    assert '15. En kostnad blir aldrig en nytta' in flat
    assert '16. En följdeffekt som underlaget visar har inträffat räknas' in flat
    assert '17. El räknas med 59 g CO2e/kWh' in flat
    assert '18. Köpt utrustning belastas bara med den del av sin livslängd' in flat
    assert 'Skriv aldrig delta_ef < 0' in STEG['kalkyl_extract']
    assert 'ange alltid utrustningens livslängd' in STEG['evidens']
    assert 'Att ingen kostnad har blivit en nytta' in STEG['qa']


def test_attribution_is_a_share_among_causes_after_omgang_4():
    # Omgång 4 (2026-10-22) read "what the money paid has attribution 1" as a
    # default and raised the share on behaviour drivers to 0.85-1. The money's
    # own output keeps 1; an effect through other people's choices is a share
    # among causes, and a high share needs as much reason as a low one.
    flat = " ".join(KARNA.split())
    assert 'Den är 1 bara för det pengarna själva utförde eller köpte och dess egen användning' in flat
    assert 'pengarnas del bland alla orsaker till förändringen' in flat
    assert 'nära 1 kräver lika tydliga skäl som ett lågt' in flat
    assert 'är det en tidigareläggning även när året inte står' in flat
    assert 'Det som gjordes utan pengarna' in flat
    assert 'om den användes vidare efter den tid nyttan räknas för' in flat
    assert '(ofta 1)' not in STEG['kalkyl_extract']
    assert 'pengarnas andel bland orsakerna (regel 2)' in STEG['kalkyl_extract']
    assert 'deltagarnas egen vilja' in STEG['evidens']
    assert 'egen tid eller andra medel' in STEG['qa']


def test_an_unused_tool_has_no_invented_scope():
    # Omgång 5's probe (2026-10-22) counted 204 tonnes from a climate database
    # nobody has reported using, on "4 projects a year" the intake made up.
    flat = " ".join(KARNA.split())
    assert 'Har ingen användning av det redovisats än' in flat
    assert 'aldrig uppskattas fritt, och i det försiktiga scenariot används det inte' in flat
    assert 'Hitta inte på den.' in STEG['intake']
    assert 'som ingen redovisat\n  användning av' in STEG['qa']


def test_an_adoption_ceiling_goes_into_delta_not_the_ramp():
    # Omgång 5, husbyggnad (2026-10-23): the evidence step had the requirements
    # followed in 60 % of projects from 2029, the extraction left that out of
    # delta_ef and let the ramp run to 100 %, so 2030 was 1.7 times too high
    # and the cautious scenario counted full use. The reach rule existed, but
    # under the heading for information measures, so a requirement missed it.
    from caia.agents.kalkyl_extract import SYSTEM_PROMPT, SYSTEM_PROMPT_UPPFOLJNING
    for prompt in (SYSTEM_PROMPT, SYSTEM_PROMPT_UPPFOLJNING):
        flat = " ".join(prompt.split())
        assert 'Rampen går alltid till full effekt, 100 %.' in flat
        assert 'delta_ef = minskningen × adoptionens tak. Rampen bär bara takten, aldrig taket.' in flat
