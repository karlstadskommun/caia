"""Hand-derived results for the calc engine, and the input checks in front of it.

test_calc.py covers the engine's rules one at a time, mostly on full-effect
cases. Mutating the engine showed that most of the arithmetic could change
without any test noticing: the averaging window, which scenario the headline
takes, how drivers add up, the BAU growth exponent, delta_ef, the overlap
clamp, which end of the span is which. Every number below is worked out by
hand in the comment above it, never by running the engine.

Run: cd next && .venv/bin/python -m pytest tests/test_calc_golden.py -v
"""
from __future__ import annotations

import pytest
from caia.calc import CalcModel, compute, render_markdown
from caia.calc.engine import sanity_warnings, year_series
from caia.web import app as A

approx = pytest.approx


def _drv(**over) -> dict:
    d = {
        'name': 'd', 'baseline_year': 2023, 'a0': 1000.0, 'ef0': 2.0,
        'ramp': {'start_year': 2025, 'full_effect_year': 2027, 'profile': 'linjär'},
        'g_a': 0.0, 'g_ef': 0.0,
        'delta_a': {'min': -0.1, 'med': -0.2, 'max': -0.3}, 'delta_ef': 0.0,
        'terr': 1.0, 'cons': 0.5, 'overlap': 0.5,
    }
    d.update(over)
    return d


def _model(*drivers, target=2030) -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': target,
                                'drivers': list(drivers) or [_drv()]})


# Case A, one driver, linear ramp:
#   E_BAU = 1000 × 2,0 kg = 2 t every year (no trend).
#   adoption: 2025 0, 2026 0,5, 2027 on 1.
#   basis = 2 t × |delta_a| × adoption; medel: 2026 0,2 t, 2027–2030 0,4 t.
#   terr = basis × 1, cons = basis × 0,5, overlap = min(basis × 0,5, terr, cons)
#   = 0,5 basis, net = terr + cons − overlap = basis.
#   Medel/år 2026–2030 (medel): (0,2 + 4 × 0,4) / 5 = 0,36 t.
#     min: (0,1 + 4 × 0,2) / 5 = 0,18; max: (0,3 + 4 × 0,6) / 5 = 0,54.
#   Kumulativt 2025–2030 (medel): 0 + 0,2 + 4 × 0,4 = 1,8 t; terr 1,8, cons 0,9.

def test_single_driver_average_window_and_cumulative():
    r = compute(_model())
    med = r['med']['total']
    assert med['avg_2026_2030_net'] == approx(0.36)
    assert med['avg_2026_2030_terr'] == approx(0.36)
    assert med['avg_2026_2030_cons'] == approx(0.18)
    assert med['cumulative_net'] == approx(1.8)
    assert med['cumulative_terr'] == approx(1.8)
    assert med['cumulative_cons'] == approx(0.9)
    assert r['min']['total']['avg_2026_2030_net'] == approx(0.18)
    assert r['max']['total']['avg_2026_2030_net'] == approx(0.54)
    assert med['years'][2026]['net'] == approx(0.2)
    assert med['years'][2030]['net'] == approx(0.4)


def test_headline_is_the_medel_scenario_in_the_target_year():
    # Potential mode: the target year (Henric 2026-10-13), medel scenario.
    # 2030 medel: net 0,4, terr 0,4, cons 0,2. From min it would be 0,2 / 0,1.
    assert compute(_model())['headline'] == {'terr': 0.4, 'cons': 0.2, 'net': 0.4, 'year': 2030}
    assert compute(_model(target=2035))['headline']['year'] == 2035


def test_a_follow_up_headline_is_still_the_average_and_names_no_year():
    # Ramp 2025-2027: the follow-up averages 2025-2030, (0 + 0,2 + 4 × 0,4) / 6 = 0,3,
    # while 2030 alone is 0,4. The headline must be the average, without a year.
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [_drv()]},
                            mode='uppfoljning')
    h = compute(m)['headline']
    assert 'year' not in h
    assert h['net'] == approx(0.3)


# Case B, the effect sits in the emission factor:
#   E_BAU = 100 × 10 kg = 1 t; delta_ef medel −0,5 from 2024 (ramp 2023→2024).
#   basis = 1 − 1 × 0,5 = 0,5 t; terr 1, cons 0, overlap 0 -> net 0,5.

def test_delta_ef_reduces_the_emission_factor():
    m = _model(_drv(a0=100.0, ef0=10.0, delta_a=0.0, delta_ef={'min': -0.4, 'med': -0.5,
                                                                'max': -0.6},
                    ramp={'start_year': 2023, 'full_effect_year': 2024},
                    cons=0.0, overlap=0.0))
    r = compute(m)
    assert r['med']['total']['years'][2030]['net'] == approx(0.5)
    assert r['min']['total']['years'][2030]['net'] == approx(0.4)
    assert r['med']['total']['avg_2026_2030_net'] == approx(0.5)


# Case C, BAU grows 10 %/year from the baseline year 2023:
#   E_BAU(2030) = 1 t × 1,1^7 = 1,9487171 t; delta_a −0,5 at full effect
#   -> basis 2030 = 0,97435855 t (terr 1, cons 0).

def test_bau_growth_compounds_from_the_baseline_year():
    m = _model(_drv(a0=100.0, ef0=10.0, g_a=0.1, delta_a=-0.5,
                    ramp={'start_year': 2023, 'full_effect_year': 2024},
                    cons=0.0, overlap=0.0))
    y = compute(m)['med']['total']['years'][2030]
    assert y['net'] == approx(0.97435855)
    per = compute(m)['med']['per_driver'][0]['years'][2030]
    assert per['e_bau'] == approx(1.9487171)
    assert per['e_action'] == approx(1.9487171 * 0.5)


# Case D, the overlap is clamped to the smaller factor:
#   a0 1000, ef0 10 kg -> 10 t; delta_a −0,1 at full effect -> basis 1 t.
#   terr 1, cons 0,2, overlap 0,5 -> overlap = min(0,5; 1; 0,2) = 0,2 t.
#   net = 1 + 0,2 − 0,2 = 1,0 t (unclamped it would be 0,7).

def test_overlap_never_removes_more_than_the_smaller_factor():
    m = _model(_drv(a0=1000.0, ef0=10.0, delta_a=-0.1,
                    ramp={'start_year': 2023, 'full_effect_year': 2024},
                    terr=1.0, cons=0.2, overlap=0.5))
    y = compute(m)['med']['total']['years'][2030]
    per = compute(m)['med']['per_driver'][0]['years'][2030]
    assert per['overlap'] == approx(0.2)
    assert y['net'] == approx(1.0)


# Case E, two drivers add up: case A (net 0,36/år, kumulativt 1,8) plus case B
#   (net 0,5/år 2026–2030; kumulativt over 2023–2030, the earliest ramp start,
#   B has adoption 0 in 2023 and 1 from 2024: 7 × 0,5 = 3,5).
#   A over 2023–2030 is still 1,8 (0 before 2026 apart from 0 in 2025).
#   Total medel/år 0,86; kumulativt 5,3.

def test_drivers_add_up_in_every_total():
    a = _drv(name='a')
    b = _drv(name='b', a0=100.0, ef0=10.0, delta_a=0.0, delta_ef=-0.5,
             ramp={'start_year': 2023, 'full_effect_year': 2024}, cons=0.0, overlap=0.0)
    r = compute(_model(a, b))
    med = r['med']['total']
    assert med['avg_2026_2030_net'] == approx(0.86)
    assert med['cumulative_net'] == approx(5.3)
    assert med['years'][2030]['net'] == approx(0.9)
    assert [d['cumulative_net'] for d in r['med']['per_driver']] == [approx(1.8), approx(3.5)]


def test_the_kalkyl_route_reports_the_span_the_right_way_round(monkeypatch):
    """span: net_lo from the min scenario, net_hi from max, cum_net from medel."""
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    extracted = {'action_name': 'x', 'target_year': 2030, 'drivers': [_drv()]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    monkeypatch.setattr(A, 'kallmarkering', lambda m, h=None: ([], ''))
    body = A.app.test_client().post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True
    # round(0,18; 1) = 0,2; round(0,54; 1) = 0,5; round(1,8) = 2.
    # series: case A per year from the ramp start 2025 to 2030, basis =
    # 2 t × |delta_a| × adoption (0; 0,5; 1 from 2027).
    series = body['span'].pop('series')
    # The band is the target year, like the headline: 2030 min 0,2, max 0,6.
    # avg_net is the medel average 2026-2030, round(0,36; 1) = 0,4.
    assert body['span'] == {'net_lo': 0.2, 'net_hi': 0.6, 'avg_net': 0.4, 'headline_year': 2030,
                            'cum_net': 2, 'target_year': 2030, 'window': [2026, 2030],
                            'mode': 'potential', 'avg_lo': 0.2, 'avg_hi': 0.5,
                            'cum_lo': 1, 'cum_hi': 3}
    assert series['years'] == [2025, 2026, 2027, 2028, 2029, 2030]
    assert series['min'] == approx([0, 0.1, 0.2, 0.2, 0.2, 0.2])
    assert series['med'] == approx([0, 0.2, 0.4, 0.4, 0.4, 0.4])
    assert series['max'] == approx([0, 0.3, 0.6, 0.6, 0.6, 0.6])
    assert body['headline'] == {'terr': 0.4, 'cons': 0.2, 'net': 0.4, 'year': 2030}
    assert body['warnings'] == []


# ---------- the year-by-year series behind the hero chart ----------

# Case E again (two drivers, cumulative from 2023): the series must be the
# same numbers the headline and the cumulative were made of, not a second
# computation that can drift. Medel per year: 2023 0 (B adoption 0),
# 2024–2025 0,5 (B), 2026 0,7, 2027–2030 0,9.

def test_the_series_is_what_the_headline_and_cumulative_are_made_of():
    a = _drv(name='a')
    b = _drv(name='b', a0=100.0, ef0=10.0, delta_a=0.0, delta_ef=-0.5,
             ramp={'start_year': 2023, 'full_effect_year': 2024}, cons=0.0, overlap=0.0)
    m = _model(a, b)
    s = year_series(m)
    assert s['years'] == list(range(2023, 2031))
    assert s['med'] == approx([0, 0.5, 0.5, 0.7, 0.9, 0.9, 0.9, 0.9])
    r = compute(m)
    win = [s['med'][s['years'].index(y)] for y in range(2026, 2031)]
    assert sum(win) / len(win) == approx(r['med']['total']['avg_net'])
    for sc in ('min', 'med', 'max'):
        assert sum(s[sc]) == approx(r[sc]['total']['cumulative_net'])


def test_the_series_reaches_the_window_and_the_target_year_whichever_is_later():
    # Ramp from 2028, target 2035: from 2026 (the window) to 2035, nothing
    # before 2028. Target 2028 with the window to 2030: still runs to 2030.
    late = _model(_drv(ramp={'start_year': 2028, 'full_effect_year': 2029}), target=2035)
    s = year_series(late)
    assert s['years'][0] == 2026 and s['years'][-1] == 2035
    assert s['med'][:2] == [0, 0]
    short = year_series(_model(target=2028))
    assert short['years'] == list(range(2025, 2031))


def test_a_one_off_is_one_year_in_the_series():
    # 1000 × 2 kg = 2 t in 2027 only; medel −20 % -> 0,4 t that year.
    m = _model(_drv(kind='engång', ramp={'start_year': 2027, 'full_effect_year': 2027}))
    s = year_series(m)
    assert [v for v in s['med'] if v] == approx([0.4])
    assert s['med'][s['years'].index(2027)] == approx(0.4)


# ---------- what the engine is allowed to receive ----------

@pytest.mark.parametrize('over,why', [
    ({'delta_a': -10.0}, '-10 % written as -10'),
    ({'delta_ef': {'min': -0.2, 'med': -0.5, 'max': -1.5}}, 'one scenario below -100 %'),
    ({'g_a': 2.0}, '2 %/year written as 2'),
    ({'g_ef': -1.0}, 'a trend that removes everything in a year'),
    ({'terr': 100.0}, 'percent for a share'),
    ({'cons': -0.5}, 'negative climate factor'),
    ({'overlap': -0.1}, 'negative overlap'),
    ({'a0': float('nan')}, 'NaN'),
    ({'ef0': float('inf')}, 'infinite'),
    ({'delta_a': float('nan')}, 'NaN band'),
    ({'ramp': {'start_year': 2030, 'full_effect_year': 2026}}, 'ramp backwards'),
])
def test_values_no_reading_of_the_method_allows_are_refused(over, why):
    """Refused means /api/kalkyl falls back to the LLM path and says so
    (deterministic: false), instead of computing a confident wrong number:
    delta_a -10 made the activity negative and the headline 100 times too big."""
    with pytest.raises(ValueError):
        _model(_drv(**over))


def test_a_missing_overlap_is_refused_not_zeroed():
    """terr = cons = 1 with the overlap left out counted a car measure twice."""
    d = _drv(terr=1.0, cons=1.0)
    del d['overlap']
    with pytest.raises(ValueError, match='overlap'):
        _model(d)


def test_values_the_prompts_allow_still_pass():
    # The evidens prompt allows cons 1.2; positive deltas are real (new
    # electricity for charging); a 100 % cut is a real measure.
    _model(_drv(cons=1.2, overlap=1.0))
    _model(_drv(delta_a=0.4))
    _model(_drv(delta_a=-1.0))


# ---------- warnings the page shows next to the headline ----------

def test_an_effect_after_the_window_warns_that_the_average_is_zero():
    m = _model(_drv(ramp={'start_year': 2031, 'full_effect_year': 2033}), target=2035)
    r = compute(m)
    assert r['med']['total']['avg_2026_2030_net'] == 0
    assert r['med']['total']['cumulative_net'] > 0
    w = sanity_warnings(r, m)
    assert any('2026–2030' in x and 'blir 0' in x for x in w), w
    assert 'blir 0' in render_markdown(m, r)


def test_a_target_year_past_the_window_needs_no_note_now_it_is_the_headline():
    # The note explained why the average left out the target year. Since
    # 2026-10-13 the headline is the target year, so there is nothing to explain.
    m = _model(target=2035)
    w = sanity_warnings(compute(m), m)
    assert not any('målåret är 2035' in x for x in w), w


def test_a_negative_target_year_alone_warns_of_increased_emissions():
    # A benefit 2026-2029 that ends, and a smaller cost from 2030: the average
    # (4 × 0,4 − 0,2) / 5 = 0,28 and the cumulative 1,4 are both positive,
    # only the target year (−0,2) is negative. The headline is that year, so
    # the warning must come from it alone.
    end = {'min': 2029, 'med': 2029, 'max': 2029}
    m = _model(_drv(name='nytta', ramp={'start_year': 2026, 'full_effect_year': 2026, 'end_year': end}),
               _drv(name='kostnad', delta_a={'min': 0.1, 'med': 0.1, 'max': 0.1},
                    ramp={'start_year': 2030, 'full_effect_year': 2030}))
    r = compute(m)
    med = r['med']['total']
    assert med['avg_net'] == approx(0.28) and med['cumulative_net'] == approx(1.4)
    assert r['headline']['net'] == approx(-0.2)
    assert any('ÖKADE utsläpp' in x for x in sanity_warnings(r, m))


# ---------- an action that works late, or after the years that count ----------
#
# The driver is case A's: E_BAU 2 t every year, medel delta -0,2, so a year at
# full effect gives basis 0,4 t and net 0,4 t (terr 0,4 + cons 0,2 - overlap 0,2).
# None of these warnings may move a number, so every case states its numbers.

LATE = 'har effekt bara'      # works in fewer than half the window's years
OUTSIDE = 'har effekt först'  # works only after the years that are counted


def _warn(m):
    return sanity_warnings(compute(m), m)


def test_a_start_after_2030_with_target_2030_says_why_both_numbers_are_zero():
    # Start and full effect 2031, target 2030. Cumulative runs 2030–2030 and the
    # average 2026–2030: no year with effect in either. Both 0.
    m = _model(_drv(ramp={'start_year': 2031, 'full_effect_year': 2031}))
    r = compute(m)
    assert r['headline']['net'] == 0 and r['med']['total']['cumulative_net'] == 0
    w = sanity_warnings(r, m)
    hit = [x for x in w if OUTSIDE in x]
    assert len(hit) == 1, w
    for part in ('först 2031', 'efter målåret 2030', 'utanför 2026–2030', 'Båda blir 0',
                 'inte att åtgärden saknar effekt'):
        assert part in hit[0], (part, hit[0])
    # It is not the "no delta reached the engine" case, and not the "average
    # is zero but the cumulative shows it" case: neither is true here.
    assert not any('ingen drivare har någon effekt' in x or 'blir 0 här' in x for x in w), w
    assert not any(LATE in x for x in w), w
    assert hit[0] in render_markdown(m, r)


def test_the_first_year_with_effect_is_read_from_the_ramp_not_the_start_year():
    # Linear 2030 -> 2032: the start year itself is 0 %, 2031 is 50 %. With
    # target 2030 nothing is counted, and the first year that works is 2031.
    m = _model(_drv(ramp={'start_year': 2030, 'full_effect_year': 2032, 'profile': 'linjär'}))
    assert any('först 2031' in x for x in _warn(m)), _warn(m)
    # Stepwise 2029 -> 2033: 2030 is a quarter of the way (0), 2031 half (1).
    m = _model(_drv(ramp={'start_year': 2029, 'full_effect_year': 2033, 'profile': 'Stegvis'}))
    assert compute(m)['headline']['net'] == 0
    assert any('först 2031' in x for x in _warn(m)), _warn(m)


def test_a_driver_without_effect_does_not_count_as_the_action_working():
    # Two drivers: one from 2026 with no delta at all, one with the effect from
    # 2031. Only the second changes anything, so nothing is counted to 2030.
    m = _model(_drv(name='utan effekt', delta_a=0.0, delta_ef=0.0,
                    ramp={'start_year': 2026, 'full_effect_year': 2026}),
               _drv(name='med effekt', ramp={'start_year': 2031, 'full_effect_year': 2031}))
    r = compute(m)
    assert r['headline']['net'] == 0 and r['med']['total']['cumulative_net'] == 0
    assert any('först 2031' in x for x in sanity_warnings(r, m)), sanity_warnings(r, m)
    # And the other way round: the driver with the effect works from 2029 only,
    # the one without from 2026. Two years with effect, not five.
    m = _model(_drv(name='utan effekt', delta_a=0.0, delta_ef=0.0,
                    ramp={'start_year': 2026, 'full_effect_year': 2026}),
               _drv(name='med effekt', ramp={'start_year': 2029, 'full_effect_year': 2029}))
    assert any('bara 2 av dem (2029, 2030)' in x for x in _warn(m)), _warn(m)


def test_a_year_far_out_in_the_extraction_is_a_note_and_never_an_exception():
    # Full effect "9999" with a BAU trend: 1,1 to the power of 7 976 overflows
    # a float. The warning must not be what throws a computed result away.
    m = _model(_drv(g_a=0.1, ramp={'start_year': 2040, 'full_effect_year': 9999}), target=2035)
    r = compute(m)
    w = sanity_warnings(r, m)
    assert any('först 2041' in x for x in w), w  # linear: the year after the start
    assert 'först 2041' in render_markdown(m, r)
    # Stepwise over the same span lands at the midpoint, far past the search:
    # the full-effect year is still tried, so the note names a year that works.
    # That is the year the BAU powers would overflow on, if the search took them.
    m = _model(_drv(g_a=0.1, ramp={'start_year': 2040, 'full_effect_year': 9999,
                                   'profile': 'Stegvis'}), target=2035)
    assert any('först 9999' in x for x in _warn(m)), _warn(m)


def test_the_first_year_is_the_earliest_driver_s_and_a_one_off_works_one_year():
    # Two drivers, effect from 2031 and from 2033: the action works from 2031.
    m = _model(_drv(name='a', ramp={'start_year': 2033, 'full_effect_year': 2033}),
               _drv(name='b', ramp={'start_year': 2031, 'full_effect_year': 2031}))
    assert any('först 2031' in x for x in _warn(m)), _warn(m)
    # A one-off in 2031 (a purchase: 10 units × 100 kg, all of it added) is
    # outside every counted year when the target year is 2030.
    one_off = dict(kind='engång', a0=10.0, ef0=100.0, delta_a=1.0)
    m = _model(_drv(name='Inköp', year=2031, **one_off))
    r = compute(m)
    assert r['headline']['net'] == 0 and r['med']['total']['cumulative_net'] == 0
    assert any('först 2031' in x for x in sanity_warnings(r, m)), sanity_warnings(r, m)
    # The same purchase in 2029: 1 t added that year (basis -1 t, net -1 t with
    # terr 1, cons 0,5, overlap 0,5), nothing in the other four.
    # Medel/år = -1 / 5 = -0,2 t. One year with effect, not five.
    m = _model(_drv(name='Inköp', year=2029, **one_off))
    assert compute(m)['med']['total']['avg_net'] == approx(-0.2)
    assert any('bara 1 av dem (2029)' in x for x in _warn(m)), _warn(m)


def test_past_both_the_window_and_a_later_target_year_is_one_note_not_a_false_one():
    # Start 2036, target 2035. The old note said the effect after 2030 "syns i
    # ΔE_2035 och i kumulativt"; here it shows nowhere.
    m = _model(_drv(ramp={'start_year': 2036, 'full_effect_year': 2036}), target=2035)
    w = _warn(m)
    assert any('först 2036' in x and 'efter målåret 2035' in x for x in w), w
    assert not any('syns i ΔE_2035' in x for x in w), w


def test_an_effect_that_never_comes_is_said_as_that():
    # Linear 2026 -> 2028 is 0 % in 2026, and the effect ends after 2026.
    m = _model(_drv(ramp={'start_year': 2026, 'full_effect_year': 2028, 'end_year': 2026}))
    r = compute(m)
    assert r['med']['total']['cumulative_net'] == 0
    w = sanity_warnings(r, m)
    assert any('inte har effekt något år' in x for x in w), w
    assert not any(OUTSIDE in x for x in w), w


def test_a_start_late_in_the_window_says_why_the_average_is_low():
    # Full effect from 2029, target 2030: 0,4 t in 2029 and 2030, nothing before.
    # Medel/år = (0,4 + 0,4) / 5 = 0,16 t. Kumulativt 2029–2030 = 0,8 t.
    m = _model(_drv(ramp={'start_year': 2029, 'full_effect_year': 2029}))
    r = compute(m)
    assert r['med']['total']['avg_net'] == approx(0.16)
    assert r['med']['total']['cumulative_net'] == approx(0.8)
    w = sanity_warnings(r, m)
    hit = [x for x in w if LATE in x]
    assert len(hit) == 1, w
    for part in ('5 år (2026–2030)', 'bara 2 av dem (2029, 2030)', 'räknas som noll'):
        assert part in hit[0], (part, hit[0])
    assert not any(OUTSIDE in x for x in w), w
    assert hit[0] in render_markdown(m, r)
    # One year: 0,4 / 5 = 0,08 t.
    m = _model(_drv(ramp={'start_year': 2030, 'full_effect_year': 2030}))
    assert compute(m)['med']['total']['avg_net'] == approx(0.08)
    assert any('bara 1 av dem (2030)' in x for x in _warn(m)), _warn(m)


def test_a_year_on_the_way_up_counts_as_a_year_with_effect():
    # Linear 2028 -> 2030: 0 %, 50 %, 100 %. Two years work, 2029 and 2030.
    # Medel/år = (0,2 + 0,4) / 5 = 0,12 t.
    m = _model(_drv(ramp={'start_year': 2028, 'full_effect_year': 2030, 'profile': 'linjär'}))
    assert compute(m)['med']['total']['avg_net'] == approx(0.12)
    assert any('bara 2 av dem (2029, 2030)' in x for x in _warn(m)), _warn(m)


def test_an_effect_that_ends_early_is_counted_by_the_years_it_worked():
    # Full effect 2026, ends after 2027: 0,4 t in 2026 and 2027.
    # Medel/år = 0,8 / 5 = 0,16 t.
    m = _model(_drv(ramp={'start_year': 2026, 'full_effect_year': 2026, 'end_year': 2027}))
    assert compute(m)['med']['total']['avg_net'] == approx(0.16)
    assert any('bara 2 av dem (2026, 2027)' in x for x in _warn(m)), _warn(m)


def test_an_action_that_works_most_of_the_window_gets_neither_note():
    # Full effect from 2028: three of five years. Medel/år = 1,2 / 5 = 0,24 t.
    m = _model(_drv(ramp={'start_year': 2028, 'full_effect_year': 2028}))
    assert compute(m)['med']['total']['avg_net'] == approx(0.24)
    assert not any(LATE in x or OUTSIDE in x for x in _warn(m)), _warn(m)
    # Case A itself (2025 -> 2027, four of five years with effect).
    assert not any(LATE in x or OUTSIDE in x for x in _warn(_model())), _warn(_model())


def test_a_zero_that_is_not_about_the_years_does_not_blame_the_years():
    # No delta at all: the existing warning owns that, whatever the start year.
    m = _model(_drv(delta_a=0.0, delta_ef=0.0, ramp={'start_year': 2031, 'full_effect_year': 2031}))
    w = _warn(m)
    assert any('ingen drivare har någon effekt' in x for x in w), w
    assert not any(LATE in x or OUTSIDE in x or 'inte har effekt något år' in x for x in w), w
    # Climate factors 0: net is 0 every year, but the action works from 2025.
    m = _model(_drv(terr=0.0, cons=0.0, overlap=0.0))
    r = compute(m)
    assert r['headline']['net'] == 0 and r['med']['total']['cumulative_net'] == 0
    assert not any(LATE in x or OUTSIDE in x for x in sanity_warnings(r, m))
    # Effect after the window but before a later target year: the cumulative
    # shows it, and the note that says so is the right one.
    m = _model(_drv(ramp={'start_year': 2031, 'full_effect_year': 2033}), target=2035)
    w = _warn(m)
    assert any('blir 0 här' in x for x in w), w
    assert not any(LATE in x or OUTSIDE in x for x in w), w


def test_a_follow_up_past_its_target_year_is_told_too_but_never_about_the_plan_window():
    # Follow-up averages from the first start year to the target year.
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [
        _drv(ramp={'start_year': 2032, 'full_effect_year': 2032})]}, mode='uppfoljning')
    r = compute(m)
    assert r['headline']['net'] == 0 and r['med']['total']['cumulative_net'] == 0
    w = sanity_warnings(r, m)
    assert any('först 2032' in x and 'efter målåret 2030' in x for x in w), w
    assert not any('2026–2030' in x for x in w), w
    # Start 2029: the average is over 2029–2030, both years work. No note.
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [
        _drv(ramp={'start_year': 2029, 'full_effect_year': 2029})]}, mode='uppfoljning')
    assert compute(m)['med']['total']['avg_net'] == approx(0.4)
    assert not any(LATE in x or OUTSIDE in x for x in _warn(m)), _warn(m)


def test_the_kalkyl_route_returns_the_late_start_note(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    extracted = {'action_name': 'x', 'target_year': 2030, 'drivers': [
        _drv(ramp={'start_year': 2031, 'full_effect_year': 2031})]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    monkeypatch.setattr(A, 'kallmarkering', lambda m, h=None: ([], ''))
    body = A.app.test_client().post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True and body['headline']
    assert any(OUTSIDE in w for w in body['warnings']), body['warnings']


def test_no_effect_at_all_is_not_a_confident_zero():
    m = _model(_drv(delta_a=0.0, delta_ef=0.0))
    w = sanity_warnings(compute(m), m)
    assert any('ingen drivare har någon effekt' in x for x in w), w


def test_the_kalkyl_text_shows_the_inputs_it_ran_on():
    """The QA step reads this text. Without the inputs it checked a result it
    could not trace, and the report said the climate factors "står i kalkylen"
    when they did not."""
    m = _model()
    text = render_markdown(m, compute(m))
    assert 'Indata per drivare' in text
    line = next(ln for ln in text.splitlines() if ln.strip().startswith('- d: A0'))
    for part in ('A0 1 000', 'EF0 2', 'ΔA -20 % (-10 till -30)', 'territoriell 1', 'konsumtion 0,5',
                 'överlapp 0,5', 'ramp 2025–2027'):
        assert part in line, (part, line)


def test_bau_is_shared_across_scenarios_and_uses_the_medel_trend():
    # g_a band 0 / 0,1 / 0,2: BAU follows medel (1,1^7 = 1,9487171 t in 2030)
    # in every scenario; only the action's effect differs between them.
    m = _model(_drv(a0=100.0, ef0=10.0, g_a={'min': 0.0, 'med': 0.1, 'max': 0.2},
                    delta_a=-0.5, ramp={'start_year': 2023, 'full_effect_year': 2024},
                    cons=0.0, overlap=0.0))
    r = compute(m)
    for sc in ('min', 'med', 'max'):
        assert r[sc]['per_driver'][0]['years'][2030]['e_bau'] == approx(1.9487171), sc


def test_the_kalkyl_route_returns_the_warnings(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    extracted = {'action_name': 'x', 'target_year': 2035, 'drivers': [
        _drv(ramp={'start_year': 2031, 'full_effect_year': 2033})]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    monkeypatch.setattr(A, 'kallmarkering', lambda m, h=None: ([], ''))
    body = A.app.test_client().post('/api/kalkyl', json={'history': []}).get_json()
    assert any('blir 0' in w for w in body['warnings']), body['warnings']
