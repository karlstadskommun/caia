"""The unit check: A0's unit against the unit EF0 is per (calc.units,
calc.engine.unit_warnings).

The case it was built for (2026-10-13): a run showed about 0,1 ton CO2e/år
where about 86 was right. The extraction carried A0 = 21,6 "ton nyvara/år"
next to EF0 = 10 "kg CO2e/kg", or A0 = 30 "handlare" next to the same
factor, and no check compared the two units. Both extractions are rebuilt
here from the reconstruction (no model calls).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia import kallmarkering  # noqa: E402
from caia.calc import CalcModel, compute, render_markdown, units  # noqa: E402
from caia.calc.engine import sanity_warnings, unit_warnings  # noqa: E402

NAME = "Nyvara som ersätts av cirkulära affärsmodeller hos handlare"


def _driver(a0, a0_unit, ef0, ef0_unit, delta_a):
    return {"name": NAME, "baseline_year": 2023, "a0": a0, "a0_unit": a0_unit,
            "ef0": ef0, "ef0_unit": ef0_unit, "g_a": 0, "g_ef": 0,
            "delta_a": delta_a, "delta_ef": 0, "terr": 0.05, "cons": 1.0, "overlap": 0.05,
            "ramp": {"start_year": 2027, "full_effect_year": 2030, "profile": "linjär"}}


def _model(*drivers):
    return CalcModel.from_dict({"action_name": "x", "target_year": 2030,
                                "drivers": list(drivers)})


RIGHT = _driver(21600, "kg nyvara/år", 10, "kg CO2e/kg",
                {"min": -0.28, "med": -1.0, "max": -1.0})
# Variant A: the activity in ton, the factor per kg.
TON_AS_KG = _driver(21.6, "ton nyvara/år", 10, "kg CO2e/kg",
                    {"min": -0.28, "med": -1.0, "max": -1.0})
# Variant B: 0,72 ton per retailer read as a share, A0 counted in retailers.
RETAILERS = _driver(30, "handlare", 10, "kg CO2e/kg",
                    {"min": -0.4, "med": -0.72, "max": -1.0})


def _unit_lines(m):
    return [w for w in sanity_warnings(compute(m), m) if "enheterna går inte ihop" in w]


def test_the_right_extraction_gives_86_ton_and_no_unit_warning():
    m = _model(RIGHT)
    r = compute(m)
    # 86,4 is the average 2026-2030; the headline is 2030, at full effect.
    assert r["med"]["total"]["avg_net"] == pytest.approx(86.4)
    assert r["headline"]["net"] == pytest.approx(216.0)
    assert _unit_lines(m) == []


def test_ton_next_to_per_kg_is_converted_and_said():
    # Until 2026-10-22 this was only a warning, and the result stayed 0,0864
    # (krisberedskap, run 2: 210 ton × 2,1 kg/kg counted as 0,44 ton). The
    # units as written are now trusted and the activity converted.
    m = _model(TON_AS_KG)
    assert compute(m)["med"]["total"]["avg_net"] == pytest.approx(86.4)
    w = _unit_lines(m)
    assert len(w) == 1, sanity_warnings(compute(m), m)
    assert w[0].startswith("VARNING: enheterna går inte ihop för drivare 1 (" + NAME)
    assert "aktiviteten är i ton, men utsläppsfaktorn gäller per kg" in w[0]
    assert "räknat om aktiviteten: 21,6 ton = 21 600 kg" in w[0]
    assert "faktor 1 000" in w[0]


def test_kg_next_to_per_ton_is_converted_down():
    m = _model(_driver(21600, "kg nyvara/år", 10000, "kg CO2e/ton",
                       {"min": -0.28, "med": -1.0, "max": -1.0}))
    assert m.drivers[0].a0_scale == pytest.approx(0.001)
    assert compute(m)["med"]["total"]["avg_net"] == pytest.approx(86.4)


def test_the_converted_activity_is_shown_in_the_inputs_and_the_appendix():
    from caia.calc import render_appendix
    m = _model(TON_AS_KG)
    r = compute(m)
    assert "A0 21,6 ton nyvara/år (räknat som 21 600 kg)" in render_markdown(m, r)
    app = render_appendix(m, r)
    assert "A_BAU (kg, omräknat från ton nyvara/år)" in app
    assert "räknas A0 först om till faktorns enhet" in app


def test_a_count_mismatch_is_never_converted():
    assert _model(RETAILERS).drivers[0].a0_scale == 1.0


def test_retailers_next_to_per_kg_is_flagged():
    m = _model(RETAILERS)
    w = _unit_lines(m)
    assert len(w) == 1, sanity_warnings(compute(m), m)
    assert "aktiviteten är i handlare, men utsläppsfaktorn gäller per kg" in w[0]
    assert "helt fel" in w[0]


def test_the_unit_warning_comes_first():
    # It makes every other number wrong too, so it heads the list the page
    # shows next to the headline.
    m = _model(TON_AS_KG)
    assert "enheterna går inte ihop" in sanity_warnings(compute(m), m)[0]


def test_the_warning_reaches_the_kalkyl_text():
    m = _model(TON_AS_KG)
    assert "enheterna går inte ihop för drivare 1" in render_markdown(m, compute(m))


def test_only_the_wrong_driver_is_named():
    m = _model(RIGHT, TON_AS_KG)
    w = unit_warnings(m)
    assert len(w) == 1 and "drivare 2" in w[0]


@pytest.mark.parametrize("a0_unit, ef0_unit, kind, factor", [
    ("ton nyvara/år", "kg CO2e/kg nyvara (netto)", "prefix", 1000),
    ("MWh/år", "kg CO2e/kWh", "prefix", 1000),
    ("kWh el/år", "kg CO2e/MWh", "prefix", 1000),
    ("g/år", "kg CO2e/ton", "prefix", 1e6),
    ("kg avfall/år", "kg CO2e/kWh", "quantity", None),
    ("handlare", "kg CO2e/kg", "count", None),
    ("personer per år", "kg CO2e per kg", "count", None),
    ("ton/år", "kg CO2e/tonkm", "count", None),
    ("ton/år", "kg CO2e/ton-km", "count", None),
    ("tonne/år", "kg CO2e/kg", "prefix", 1000),
    ("el (MWh/år)", "kg CO2e/kWh", "prefix", 1000),
    ("handlare (0,72 ton/handlare)", "kg CO2e/kg", "prefix", 1000),
])
def test_mismatches(a0_unit, ef0_unit, kind, factor):
    m = units.mismatch(a0_unit, ef0_unit)
    assert m is not None and m["kind"] == kind
    assert m["factor"] == factor


@pytest.mark.parametrize("a0_unit, ef0_unit", [
    # Every unit pair in the saved real runs (2026-10-13), and their kin.
    ("km/år", "kg CO2e/km"),
    ("kWh/år", "kg CO2e/kWh"),
    ("liter/år", "kg CO2e/liter"),
    ("kr", "kg CO2e/kr"),
    ("st cyklar", "kg CO2e/cykel"),
    ("kg material/år", "kg CO2e/kg material"),
    ("ton återbrukat material/år", "kg CO2e/ton material"),
    ("ton avfall/år", "kg CO2e/ton"),
    ("kWh batterikapacitet (engångsinköp)", "kg CO2e/kWh"),
    ("tonkm/år", "kg CO2e/tonkm"),
    ("tonkm/år", "kg CO2e/ton-km"),
    ("personbilskm per år hos påverkade personer", "kg CO2e/km"),
    ("personer", "kg CO2e/person och år"),
    ("st", "kg CO2e/enhet"),
    ("km/år", "kg CO2e/enhet"),
    # Count words are never compared with each other.
    ("fordonskm/år", "kg CO2e/km"),
    ("km/år", "kg CO2e/fordonskm"),
    ("invånare", "kg CO2e/person"),
    # Case and the unit's spelling do not matter.
    ("KWH/år", "kg CO2e/kWh"),
    ("t/år", "kg CO2e/ton"),
    ("kWh_el/år", "kg CO2e/kWh"),
    # The review's false alarms (2026-10-13): a qualifier before the unit,
    # a suffix after a hyphen, ton-km spelled apart, units spelled out.
    ("el (kWh/år)", "kg CO2e/kWh"),
    ("elförbrukning, kWh/år", "kg CO2e/kWh"),
    ("årlig förbrukning (kWh)", "kg CO2e/kWh"),
    ("Antal ton/år", "kg CO2e/ton"),
    ("kWh-el/år", "kg CO2e/kWh"),
    ("MWh-värme", "kg CO2e/MWh"),
    ("ton km", "kg CO2e/tonkm"),
    ("t·km", "kg CO2e/tkm"),
    ("tonkm", "kg CO2e/ton km"),
    ("kilogram/år", "kg CO2e/kg"),
    ("kilo", "kg CO2e/kg"),
    ("kWh/år", "kg CO2e/kilowattimme"),
    ("ton/år", "kg CO2e/tonne"),
    ("kWh/år", "kgCO2e/kWh"),
    ("kWh/år", "kg CO₂e/kWh"),
    ("kg/år", "kg CO2-ekv/kg"),
    ("personer (ca 2 ton/person)", "kg CO2e/person"),
    # A bare t or g before a hyphen is part of the word (second review).
    ("T-shirts/år", "kg CO2e/st"),
    ("t-baneresor/år", "kg CO2e/resa"),
    ("st", "kg CO2e/T-shirt"),
    # Nothing to compare: no unit, no denominator, a number first.
    ("", "kg CO2e/kg"),
    ("ton/år", "kg CO2e"),
    ("1000 kg", "kg CO2e/kg"),
    ("ton/år", "kg CO2e/enhet"),
])
def test_consistent_or_unknown_units_pass(a0_unit, ef0_unit):
    assert units.mismatch(a0_unit, ef0_unit) is None
    assert units.numerator_mismatch(ef0_unit) is None


def test_a_factor_in_ton_or_gram_co2e_is_flagged():
    m = _model(_driver(5000, "MWh/år", 0.05, "ton CO2e/MWh", -0.5))
    w = unit_warnings(m)
    assert len(w) == 1
    assert "utsläppsfaktorn för drivare 1" in w[0] and "angiven i ton CO2e" in w[0]
    assert "faktor 1 000" in w[0]
    assert units.numerator_mismatch("g CO2e/kWh")["factor"] == 1000
    assert units.numerator_mismatch("tCO2e/MWh")["ef0"] == "t"
    assert units.numerator_mismatch("kg CO2e/kWh") is None
    assert units.numerator_mismatch("kgCO2e/kWh") is None


def test_the_reference_extraction_gets_no_unit_warning():
    raw = json.loads((Path(__file__).parent / "fixtures" / "kalkyl_extract.json")
                     .read_text(encoding="utf-8"))
    assert unit_warnings(CalcModel.from_dict(raw)) == []


def test_the_source_check_reads_the_same_table():
    assert kallmarkering._PREFIX is units.PREFIX
    assert kallmarkering._prefix is units.prefix


def test_a_fault_in_the_unit_check_never_costs_the_warnings(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("x")
    monkeypatch.setattr(units, "mismatch", boom)
    m = _model(TON_AS_KG)
    sanity_warnings(compute(m), m)  # does not raise
