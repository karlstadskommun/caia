"""Size words in the drivers' units, and the ramp profile "step".

The review after 1.0.0 (2026-11-10) found that the engine read a size word
in a unit as part of the unit's name: 500 "tusen km/år" against 0,15 kg
CO2e/km counted 500 km, and 15 kg CO2e "per 100 km" was read as per km.
Henric chose "Räkna om och säg det": convert, as ton against kg already is
(tests/test_units.py), and write the conversion in the text. The same review
found that the ramp profile "step", in English, went down the S-curve
branch. The examples are the ones in his decision block; every driver lowers
its activity by 10 % at full effect from 2026, so the headline is 2030.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.calc import CalcModel, compute, render_appendix, render_markdown, units  # noqa: E402
from caia.calc.engine import activity_unit, render_activity, sanity_warnings  # noqa: E402
from caia.calc.schema import Ramp  # noqa: E402


def _model(a0, a0_unit, ef0, ef0_unit, profile="linjär", ramp=(2025, 2026), delta_a=-0.10):
    return CalcModel.from_dict({
        "action_name": "Prov", "target_year": 2030, "key_years": [2028, 2030],
        "drivers": [{
            "name": "Prov", "baseline_year": 2023, "a0": a0, "a0_unit": a0_unit,
            "ef0": ef0, "ef0_unit": ef0_unit, "g_a": 0, "g_ef": 0,
            "delta_a": delta_a, "delta_ef": 0, "terr": 0, "cons": 1, "overlap": 0,
            "ramp": {"start_year": ramp[0], "full_effect_year": ramp[1], "profile": profile}}]})


def _net(*args, **kw):
    return compute(_model(*args, **kw))["headline"]["net"]


def _warnings(m):
    return [w for w in sanity_warnings(compute(m), m) if "enheterna går inte ihop" in w]


# --- The decision block's examples ------------------------------------------

@pytest.mark.parametrize("a0, a0_unit, ef0, ef0_unit, before, after", [
    # 500 tusen km × 0,15 kg/km = 75 ton, 10 % of it. Before: 0,0075 ton.
    (500, "tusen km/år", 0.15, "kg CO2e/km", 0.0075, 7.5),
    # 2 tusen ton = 2 000 000 kg × 2,5 = 5 000 ton, 10 % of it. Before: 0,5
    # (the ton was converted, the tusen was not).
    (2, "tusen ton/år", 2.5, "kg CO2e/kg", 0.5, 500.0),
    # 15 kg per 100 km = 0,15 kg/km × 500 000 km = 75 ton. Before: 750.
    (500000, "km/år", 15, "kg CO2e per 100 km", 750.0, 7.5),
    (500000, "km/år", 15, "kg CO2e/100 km", 750.0, 7.5),
    # The other size words.
    (0.5, "miljoner km/år", 0.15, "kg CO2e/km", 0.0, 7.5),
    (0.5, "milj. km/år", 0.15, "kg CO2e/km", 0.0, 7.5),
    (5, "hundra tusen km/år", 0.15, "kg CO2e/km", 0.0, 7.5),
])
def test_size_words_are_converted(a0, a0_unit, ef0, ef0_unit, before, after):
    assert _net(a0, a0_unit, ef0, ef0_unit) == pytest.approx(after)
    # The same activity written without a size word gives the same tons.
    assert _net(500000, "km/år", 0.15, "kg CO2e/km") == pytest.approx(7.5)
    assert before != pytest.approx(after)


def test_the_conversion_of_tusen_km_is_said_in_the_text():
    m = _model(500, "tusen km/år", 0.15, "kg CO2e/km")
    r = compute(m)
    md = render_markdown(m, r)
    assert "A0 500 tusen km/år (räknat som 500 000 km)" in md
    w = _warnings(m)
    assert len(w) == 1
    assert "aktiviteten är i tusen km, men utsläppsfaktorn gäller per km" in w[0]
    assert "räknat om aktiviteten: 500 tusen km = 500 000 km" in w[0]
    assert "faktor 1 000" in w[0]
    app = render_appendix(m, r)
    assert "A_BAU (km, omräknat från tusen km/år)" in app
    assert "tusen km mot km" in app


def test_tusen_ton_is_converted_both_ways_and_said():
    m = _model(2, "tusen ton/år", 2.5, "kg CO2e/kg")
    assert m.drivers[0].a0_scale == pytest.approx(1e6)
    assert "A0 2 tusen ton/år (räknat som 2 000 000 kg)" in render_markdown(m, compute(m))
    w = _warnings(m)
    assert len(w) == 1
    assert "räknat om aktiviteten: 2 tusen ton = 2 000 000 kg" in w[0]
    assert "faktor 1 000 000" in w[0]


def test_per_100_km_converts_the_factor_and_says_so():
    m = _model(500000, "km/år", 15, "kg CO2e per 100 km")
    d = m.drivers[0]
    assert d.a0_scale == 1.0 and d.ef0_scale == pytest.approx(0.01)
    r = compute(m)
    assert "EF0 15 kg CO2e per 100 km (räknat som 0,15 kg CO2e/km)" in render_markdown(m, r)
    w = _warnings(m)
    assert len(w) == 1
    assert "aktiviteten är i km, men utsläppsfaktorn gäller per 100 km" in w[0]
    assert "räknat om utsläppsfaktorn: 15 kg CO2e per 100 km = 0,15 kg CO2e/km" in w[0]
    assert "faktor 100" in w[0]
    assert "räknas EF0 först om till per enhet" in render_appendix(m, r)


def test_the_activity_sentence_counts_in_the_plain_unit():
    m = _model(500, "tusen km/år", 0.15, "kg CO2e/km")
    assert "50 000 km mindre år 2030" in render_activity(m)
    assert activity_unit("tusen km/år") == ("km", 1000.0)
    assert activity_unit("100 kr") == ("kr", 100.0)


# --- What must not change -----------------------------------------------------

@pytest.mark.parametrize("a0_unit, ef0_unit", [
    # Testcyklisterna (driftsmedel run 2): 600 × 100 kr against 3 kg per 100 kr.
    ("100 kr", "kg CO2e/100 kr"),
    ("tusen km/år", "kg CO2e/tusen km"),
    ("km/år", "kg CO2e/km"),
    ("kWh/år", "kg CO2e/kWh"),
    # A word that only begins like a size word is not one.
    ("tusentals km/år", "kg CO2e/km"),
    ("hundratals resor", "kg CO2e/resa"),
    # A number with no unit word after it is no size.
    ("ton/år", "kg CO2e/ton"),
    ("st", "kg CO2e/enhet"),
])
def test_units_that_agree_are_not_converted(a0_unit, ef0_unit):
    assert units.conversion(a0_unit, ef0_unit) is None
    m = _model(600, a0_unit, 3, ef0_unit)
    assert m.drivers[0].a0_scale == 1.0 and m.drivers[0].ef0_scale == 1.0
    assert _warnings(m) == []


def test_equal_sizes_cancel_but_ton_against_kg_still_converts():
    # 2 × 100 ton against kg per 100 kg: 2 000 × 100 kg.
    c = units.conversion("100 ton", "kg CO2e/100 kg")
    assert c['a0_factor'] == 1000.0 and c['ef0_factor'] == 1.0
    m = _model(2, "100 ton/år", 3, "kg CO2e/100 kg")
    assert "(räknat som 2 000 × 100 kg)" in render_markdown(m, compute(m))
    # 200 ton × 3 kg per 100 kg = 6 ton, 10 % of it.
    assert _net(2, "100 ton/år", 3, "kg CO2e/100 kg") == pytest.approx(0.6)


def test_a_size_word_does_not_hide_a_count_mismatch():
    # "tusen handlare" against per kg: the count warning, about handlare.
    m = _model(30, "tusen handlare", 10, "kg CO2e/kg")
    w = _warnings(m)
    assert len(w) == 1 and "aktiviteten är i handlare" in w[0] and "helt fel" in w[0]


@pytest.mark.parametrize("text, size, rest", [
    ("tusen km", 1000.0, "km"), ("100 km", 100.0, "km"), ("1 000 kg", 1000.0, "kg"),
    ("milj. kWh", 1e6, "kWh"), ("2 miljoner kr", 2e6, "kr"), ("km", 1.0, "km"),
    ("tusentals km", 1.0, "tusentals km"), ("2030", 1.0, "2030"),
])
def test_size_of(text, size, rest):
    got = units.size_of(text)
    assert got[0] == pytest.approx(size) and got[2] == rest


# --- The ramp profile "step" -------------------------------------------------

@pytest.mark.parametrize("profile", ["stegvis", "Stegvis", "step", "Step", "stepwise", "step-wise"])
def test_step_is_a_step_in_both_languages(profile):
    r = Ramp(start_year=2026, full_effect_year=2030, profile=profile)
    # Before: "step" gave the S-curve, 4,7 / 50 / 95 % in 2027-2029.
    assert [r.adoption(y) for y in (2026, 2027, 2028, 2029, 2030)] == [0, 0, 1, 1, 1]


def test_the_s_curve_is_unchanged():
    r = Ramp(start_year=2026, full_effect_year=2030, profile="S-formad")
    assert [round(r.adoption(y), 3) for y in (2027, 2028, 2029)] == [0.047, 0.5, 0.953]


def test_a_step_ramp_2026_2030_gives_full_effect_in_2028():
    # 1 000 000 kWh × 0,2 kg/kWh halved = 100 ton at full effect. Before:
    # 50 ton in 2028 for "step"; the target year was the same either way.
    def run(profile):
        m = _model(1_000_000, "kWh/år", 0.2, "kg CO2e/kWh", profile=profile,
                   ramp=(2026, 2030), delta_a=-0.5)
        return compute(m)["med"]["total"]
    step, stegvis = run("step"), run("stegvis")
    assert step["years"][2028]["net"] == pytest.approx(100.0)
    assert step["years"] == stegvis["years"]
    assert step["avg_net"] == pytest.approx(stegvis["avg_net"]) == pytest.approx(60.0)
    assert step["cumulative_net"] == pytest.approx(300.0)


# --- The code review's findings (2026-11-10) ---------------------------------

@pytest.mark.parametrize("a0_unit, ef0_unit", [
    # "enhet" is per the unit A0 is counted in, whatever its size, and so
    # is a factor per nothing.
    ("tusen km/år", "kg CO2e/enhet"),
    ("tusen kr", "kg CO2e/enhet"),
    ("tusen km/år", "kg CO2e"),
    # A number glued to a word is part of a name.
    ("4WD-bilar", "kg CO2e/bil"),
    ("12V-batterier", "kg CO2e/batteri"),
])
def test_no_size_conversion_without_a_unit_to_convert_to(a0_unit, ef0_unit):
    assert units.conversion(a0_unit, ef0_unit) is None


def test_a_count_mismatch_still_says_the_conversion():
    m = _model(30, "tusen handlare", 10, "kg CO2e/kg")
    w = _warnings(m)
    assert "räknat om aktiviteten: 30 tusen handlare = 30 000 handlare" in w[0]


@pytest.mark.parametrize("a0_unit, kronor", [
    ("2 miljoner kr", 2e6), ("1,5 miljoner kr", 1.5e6), ("hundra kr", 100.0),
    ("tusen kronor", 1e3), ("100 kr", 100.0), ("kr", 1.0),
])
def test_money_with_a_size_is_money(a0_unit, kronor):
    # The follow-up keeps a spend post out of the result only when it sees
    # the money (schema.is_spend_post); the engine converts the same sizes.
    assert units.is_money(a0_unit)
    assert units.kronor_per_unit(a0_unit) == pytest.approx(kronor)
