"""Deterministic engine tests. Pure, offline, fast — this is the whole point of
moving the math out of the prompt: the numbers are now checkable.

Run: cd next && . .venv/bin/activate && python -m pytest tests/test_calc.py -v
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia.calc import CalcModel, compute, render_markdown  # noqa: E402
from caia.calc.schema import Ramp, Triple  # noqa: E402


def _model(**driver_over):
    base = {
        'action_name': 'Test',
        'target_year': 2030,
        'key_years': [2026, 2030],
        'drivers': [{
            'name': 'd1', 'baseline_year': 2023,
            'a0': 1000.0, 'ef0': 0.15,
            'ramp': {'start_year': 2025, 'full_effect_year': 2030, 'profile': 'linjär'},
            'g_a': 0.0, 'g_ef': 0.0,
            'delta_a': -0.10, 'delta_ef': 0.0,
            'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
        }],
    }
    base['drivers'][0].update(driver_over)
    return CalcModel.from_dict(base)


def test_overlap_prevents_double_count_both_factors_one():
    # 1000 km * 0.15 kg = 150 kg BAU; -10% -> 135; basis 15 kg = 0.015 ton.
    # terr=cons=overlap=1 -> net = 0.015 + 0.015 - 0.015 = 0.015 (NOT doubled).
    r = compute(_model())
    net_2030 = r['med']['total']['years'][2030]['net']
    assert abs(net_2030 - 0.015) < 1e-9, net_2030
    # territorial and consumption each equal the basis
    assert abs(r['med']['total']['years'][2030]['terr'] - 0.015) < 1e-9


def test_consumption_based_household_energy():
    # 100000 kWh * 0.05 kg = 5000 kg BAU; -20% -> 4000; basis 1000 kg = 1.0 ton.
    # terr=0.05, cons=1.0, overlap=0.05 -> net = 0.05 + 1.0 - 0.05 = 1.0.
    m = _model(a0=100000.0, ef0=0.05, delta_a=-0.20,
               terr=0.05, cons=1.0, overlap=0.05)
    r = compute(m)
    t = r['med']['total']['years'][2030]
    assert 'basis' not in t  # the total dict aggregates parts, not the raw basis
    assert abs(t['terr'] - 0.05) < 1e-9, t
    assert abs(t['cons'] - 1.0) < 1e-9, t
    assert abs(t['net'] - 1.0) < 1e-9, t


def test_ramp_linear_midpoint_half_effect():
    # full effect 2030, start 2025 -> 2027 is 2/5 of the way (linear).
    rp = Ramp(2025, 2030, 'linjär')
    assert abs(rp.adoption(2027) - 0.4) < 1e-9
    assert rp.adoption(2024) == 0.0
    assert rp.adoption(2031) == 1.0


# ---------- regressions from the 2026-07-18 code review ----------

def test_triple_without_middle_uses_band_midpoint_not_zero():
    # V1: {low, high} with no 'med' used to yield med=0.0, and the engine reads
    # only .med for the BAU trend and the headline — the result silently zeroed.
    t = Triple.of({'low': -0.20, 'high': -0.40})
    assert abs(t.med - (-0.30)) < 1e-12, t
    assert (t.min, t.max) == (-0.20, -0.40)


def test_triple_accepts_swedish_medel_key():
    assert Triple.of({'min': 1.0, 'medel': 2.0, 'max': 3.0}).med == 2.0


def test_triple_partial_band_falls_back_to_the_one_value():
    assert Triple.of({'low': 0.5}) == Triple(0.5, 0.5, 0.5)


def test_triple_rejects_a_band_with_nothing_in_it():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        Triple.of({'enhet': 'procent'})


def test_band_without_middle_matches_an_explicit_middle():
    # The consequence V1 caused, asserted end-to-end: a {low, high} delta must
    # give the same result as spelling the midpoint out. It used to give zero.
    def build(delta):
        return CalcModel.from_dict({
            'action_name': 'band', 'target_year': 2030,
            'drivers': [{
                'name': 'd', 'baseline_year': 2023, 'a0': 1_000_000.0, 'ef0': 0.15,
                'ramp': {'start_year': 2025, 'full_effect_year': 2030},
                'delta_a': delta, 'terr': 1.0, 'cons': 0.0, 'overlap': 0.0,
            }],
        })
    implied = compute(build({'low': -0.10, 'high': -0.30}))['headline']['net']
    explicit = compute(build({'min': -0.10, 'med': -0.20, 'max': -0.30}))['headline']['net']
    assert implied == explicit
    assert implied != 0.0, implied


def test_ramp_profile_is_case_insensitive():
    # V3: the prompts write 'Stegvis' and 'S-formad' with a capital letter, and
    # matching the raw string sent both down the linear branch.
    assert Ramp(2025, 2030, 'S-formad').adoption(2027) \
        == Ramp(2025, 2030, 's-formad').adoption(2027)
    assert Ramp(2025, 2030, 'Stegvis').adoption(2029) \
        == Ramp(2025, 2030, 'stegvis').adoption(2029)
    assert Ramp(2025, 2030, '  LINJÄR  ').adoption(2027) == Ramp(2025, 2030).adoption(2027)


def test_stepwise_ramp_actually_steps():
    # V2: `frac >= 1.0` was unreachable (the year >= full_effect_year guard
    # returned first), so a lowercase 'stegvis' driver contributed 0.0 for its
    # whole ramp period.
    rp = Ramp(2025, 2030, 'stegvis')
    assert rp.adoption(2026) == 0.0        # before the midpoint
    assert rp.adoption(2028) == 1.0        # at/after the midpoint (frac 0.6)
    assert rp.adoption(2030) == 1.0        # full effect year
    assert any(rp.adoption(y) > 0.0 for y in range(2026, 2030))


def test_non_linear_profiles_do_not_collapse_into_linear():
    # V2 and V3 masked each other. With the capitalised spelling the prompts
    # actually emit, the case-sensitive match sent BOTH non-linear profiles down
    # the linear branch — so the visible symptom was never the zero, it was
    # every ramp silently behaving linearly. Asserting "not linear" is what
    # catches that; asserting the zero alone would not have.
    years = range(2026, 2030)
    linear = [Ramp(2025, 2030, 'linjär').adoption(y) for y in years]
    for profile in ('Stegvis', 'stegvis', 'S-formad', 's-formad'):
        got = [Ramp(2025, 2030, profile).adoption(y) for y in years]
        assert got != linear, f"{profile} collapsed into the linear ramp"


def test_s_curve_is_between_zero_and_one_and_rises():
    rp = Ramp(2025, 2030, 'S-formad')
    vals = [rp.adoption(y) for y in (2026, 2027, 2028, 2029)]
    assert all(0.0 < v < 1.0 for v in vals), vals
    assert vals == sorted(vals)


def test_scenario_band_min_le_med_le_max():
    # action reduction strengthens from min to max -> larger net reduction.
    m = CalcModel.from_dict({
        'action_name': 'band', 'target_year': 2030,
        'drivers': [{
            'name': 'd', 'baseline_year': 2023, 'a0': 1000.0, 'ef0': 0.15,
            'ramp': {'start_year': 2025, 'full_effect_year': 2030},
            'delta_a': {'min': -0.05, 'med': -0.10, 'max': -0.20},
            'terr': 1.0, 'cons': 0.0, 'overlap': 0.0,
        }],
    })
    r = compute(m)
    lo = r['min']['total']['years'][2030]['net']
    md = r['med']['total']['years'][2030]['net']
    hi = r['max']['total']['years'][2030]['net']
    assert lo < md < hi, (lo, md, hi)


def test_growth_trend_increases_bau():
    # +2%/year activity growth raises BAU emissions vs flat.
    flat = compute(_model(g_a=0.0))['med']['total']['years'][2030]['terr']
    grow = compute(_model(g_a=0.02))['med']['total']['years'][2030]['terr']
    assert grow > flat


def test_render_markdown_has_headline_labels():
    md = render_markdown(_model(), compute(_model()))
    assert 'Medel effekt/år (Netto/Total):' in md
    assert 'ton CO2e/år' in md


def test_parse_json_tolerant():
    from caia.agents.kalkyl_extract import _parse_json
    # fenced + prose around it
    assert _parse_json('Här är modellen:\n```json\n{"drivers":[{"name":"d"}]}\n```\nKlart!') \
        == {'drivers': [{'name': 'd'}]}
    # trailing comma + // comment
    assert _parse_json('{"drivers":[{"name":"d"},], // klar\n}')['drivers'][0]['name'] == 'd'
    # prefers the object with drivers over an earlier stray brace object
    txt = 'Tanke: {"not":"this"} sedan {"drivers":[{"name":"x"}]}'
    assert _parse_json(txt).get('drivers')
    # garbage -> None
    assert _parse_json('inget json här') is None


def test_comment_stripping_never_touches_string_contents():
    """The rule: cleanup edits only what is outside string literals. A cited
    source URL contains '//' and a driver name may contain '/*'; both are
    data, and the old regex pass turned a reply with one trailing comma and
    one URL into unparseable JSON."""
    from caia.agents.kalkyl_extract import _clean, _parse_json
    src = 'https://www.smhi.se/data'
    txt = ('{"drivers":[{"name":"a /* b */ c","source":"' + src + '",},], // klar\n'
           '/* block */ "target_year": 2030,}')
    obj = _parse_json(txt)
    assert obj is not None, _clean(txt)
    assert obj['drivers'][0]['source'] == src
    assert obj['drivers'][0]['name'] == 'a /* b */ c'
    assert obj['target_year'] == 2030
    # An escaped quote inside a string does not end the string early.
    assert _parse_json(r'{"drivers":[{"name":"x \" // y"},]}')['drivers'][0]['name'] == 'x " // y'
    # Direct check of the cleaner on the exact old failure shape.
    assert _clean('{"u":"http://x", "a":1, }') == '{"u":"http://x", "a":1 }'


def test_stray_prose_braces_and_quotes_do_not_hide_the_model():
    """Prose around the JSON may hold a lone '}' or an odd number of quotes.
    Either used to desync the brace scanner so the real object was never
    yielded and the pipeline fell back to LLM math."""
    from caia.agents.kalkyl_extract import _parse_json
    body = '{"drivers":[{"name":"d"}]}'
    # A closing brace before the JSON drove depth negative.
    assert _parse_json('Rättelse: förra svaret slutade med } av misstag.\n' + body)['drivers']
    # An unmatched quote in prose flipped string state for everything after it.
    assert _parse_json('Profilen kallas "stegvis i texten.\n' + body)['drivers']


def test_extraction_request_is_the_last_turn(monkeypatch):
    """The bridge turn asks for the prose kalkyl. The extraction request must
    come after it, and the caller's history must not be mutated (the same
    list goes on to the fallback kalkyl and the next steps)."""
    from caia.agents import kalkyl_extract as K
    history = [{'role': 'assistant', 'content': 'Evidens ...'},
               {'role': 'user', 'content': 'Fortsätt med kalkyl och tidsprofil.'}]
    sent = {}

    def fake_complete(step, system, messages, max_output, mode=None, timeout_s=None):
        sent['messages'] = messages
        return '{"drivers":[{"name":"d"}]}'
    monkeypatch.setattr(K, 'complete', fake_complete)

    assert K.run_kalkyl_extract(history)['drivers']
    last = sent['messages'][-1]
    assert last['role'] == 'user'
    assert last['content'].startswith('Fortsätt med kalkyl och tidsprofil.')
    assert last['content'].endswith(K.EXTRACT_TURN)
    assert len(sent['messages']) == 2
    assert history[-1]['content'] == 'Fortsätt med kalkyl och tidsprofil.'

    # A history that ends on the assistant gets its own request turn.
    K.run_kalkyl_extract(history[:1])
    assert sent['messages'][-1] == {'role': 'user', 'content': K.EXTRACT_TURN}
    assert len(sent['messages']) == 2


def test_render_feeds_key_metric_extraction():
    # the deterministic markdown must be parseable by the report key_metric regex
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from caia.web import app as A
    m = _model(a0=100000.0, ef0=0.05, delta_a=-0.20, terr=0.05, cons=1.0, overlap=0.05)
    md = render_markdown(m, compute(m))
    km = A.extract_key_metric(md)
    assert km.get('net') is not None and km.get('cons') is not None


def test_end_year_stops_the_effect_per_scenario():
    # Ex-post: 15 leaf blowers electrified 2025; BAU would have done it anyway
    # in 2026 (min) / 2028 (med) / 2030 (max). Effect must be a step to zero
    # after the scenario's catch-up year, and cumulative must differ per scenario.
    m = _model(
        a0=1275.0, ef0=2.8, delta_a=-1.0,
        ramp={'start_year': 2025, 'full_effect_year': 2025, 'profile': 'stegvis',
              'end_year': {'min': 2026, 'med': 2028, 'max': 2030}},
        baseline_year=2024,
    )
    r = compute(m)
    per_year = lambda sc, y: r[sc]['total']['years'][y]['net']  # noqa: E731
    assert per_year('min', 2026) > 0 and per_year('med', 2026) > 0
    # 2030 is after min's and med's catch-up year, inside max's
    assert r['min']['total']['years'][2030]['net'] == 0.0
    assert r['med']['total']['years'][2030]['net'] == 0.0
    assert r['max']['total']['years'][2030]['net'] > 0
    lo, md, hi = (r[s]['total']['cumulative_net'] for s in ('min', 'med', 'max'))
    assert lo < md < hi, (lo, md, hi)
    # 2 years (2025, 2026) of 1275*2.8 kg = 3.57 ton/yr
    assert abs(lo - 2 * 3.57) < 0.01


def test_partial_end_year_leaves_other_scenarios_unbounded():
    # {"med": 2028} alone must not cap min and max at 2028 too (Triple.of would).
    m = _model(
        a0=1275.0, ef0=2.8, delta_a={'min': -0.6, 'med': -0.8, 'max': -1.0},
        ramp={'start_year': 2025, 'full_effect_year': 2025, 'profile': 'stegvis',
              'end_year': {'med': 2028}},
        baseline_year=2024,
    )
    r = compute(m)
    assert r['med']['total']['years'][2030]['net'] == 0.0
    assert r['min']['total']['years'][2030]['net'] > 0
    assert r['max']['total']['years'][2030]['net'] > 0
    # an all-empty dict means no end_year at all
    from caia.calc.schema import end_year_of
    assert end_year_of({}) is None and end_year_of(None) is None
    assert end_year_of(2027).get('max') == 2027


def test_render_survives_ramp_after_target_year():
    # A driver whose ramp starts after the target year must render (zero
    # effect), not raise IndexError and drop the kalkyl into the LLM fallback.
    m = _model(ramp={'start_year': 2032, 'full_effect_year': 2033})
    r = compute(m)
    md = render_markdown(m, r)
    assert 'kumulativt 2030–2030' in md
    assert r['med']['total']['cumulative_net'] == 0.0


def test_render_flags_inverted_scenario_order():
    # A band where "min" carries the largest effect: min > med > max cumulative.
    m = _model(delta_a={'min': -0.30, 'med': -0.10, 'max': -0.05})
    md = render_markdown(m, compute(m))
    assert 'fel ordning' in md
    ok = _model(delta_a={'min': -0.05, 'med': -0.10, 'max': -0.30})
    assert 'fel ordning' not in render_markdown(ok, compute(ok))


def test_inverted_order_warning_names_the_input_pulling_the_wrong_way():
    m = _model(delta_a={'min': -0.30, 'med': -0.10, 'max': -0.05})
    md = render_markdown(m, compute(m))
    line = next(x for x in md.splitlines() if 'fel ordning' in x)
    assert 'Indata som drar åt fel håll' in line
    assert 'd1, ΔA (effekt på aktiviteten)' in line


def _sola_run1():
    """Sola (driftsmedel 2024-06), run 1 on 2026-10-21, as its kalkyl listed
    the inputs. The engine gave 13 / 15 / -30 cumulative: the reused quantity
    was the activity, raised with ΔA, and a net share was written as ΔEF from
    -25 % in min to -8 % in max."""
    def drv(name, a0, ef0, da, de, terr, cons, ov):
        return {'name': name, 'baseline_year': 2023, 'a0': a0, 'ef0': ef0,
                'ramp': {'start_year': 2024, 'full_effect_year': 2024, 'profile': 'linjär',
                         'end_year': {'min': 2025, 'med': 2026, 'max': 2028},
                         'first_year_share': 0.35},
                'g_a': 0.2, 'g_ef': -0.015,
                'delta_a': dict(zip(('min', 'med', 'max'), da)),
                'delta_ef': dict(zip(('min', 'med', 'max'), de)),
                'attribution': {'min': 0.4, 'med': 0.7, 'max': 0.85},
                'terr': terr, 'cons': cons, 'overlap': ov}
    return CalcModel.from_dict({
        'action_name': 'Sola', 'target_year': 2030, 'key_years': [2026, 2030],
        'mode': 'uppfoljning', 'followup_year': 2024,
        'drivers': [drv('möbler', 12000, 3, (.02, .07, .15), (-.25, -.15, -.08), 0, 1, 0),
                    drv('bygg', 35000, 1, (.03, .08, .15), (-.25, -.15, -.08), 0, 1, 0),
                    drv('avfall', 30, 100, (.03, .08, .15), (-.8, -.2, 0), .8, .5, .5)]})


def test_sola_run1_is_reproduced_and_its_inverted_bands_are_named():
    m = _sola_run1()
    r = compute(m)
    cum = [round(r[s]['total']['cumulative_net']) for s in ('min', 'med', 'max')]
    assert cum == [13, 15, -30]
    line = next(x for x in render_markdown(m, r).splitlines() if 'fel ordning' in x)
    for name in ('möbler', 'bygg'):
        assert f'{name}, ΔA (effekt på aktiviteten)' in line
        assert f'{name}, ΔEF (effekt på emissionsfaktorn)' in line
    # The end year runs the right way for these drivers and is not named.
    assert 'sista år med effekt' not in line


def test_a_cost_driver_lasting_longest_in_max_is_named():
    # A small saving and a larger added load, both ending later in max. Longer
    # effect means more of the load, so max comes out lowest.
    ramp = {'start_year': 2025, 'full_effect_year': 2025,
            'end_year': {'min': 2025, 'med': 2027, 'max': 2030}}
    m = CalcModel.from_dict({
        'action_name': 'Batteri', 'target_year': 2030, 'key_years': [2026, 2030],
        'drivers': [
            {'name': 'besparing', 'baseline_year': 2024, 'a0': 1000.0, 'ef0': 1.0,
             'ramp': ramp, 'delta_a': {'min': -0.05, 'med': -0.1, 'max': -0.15},
             'terr': 0, 'cons': 1, 'overlap': 0},
            {'name': 'förluster', 'baseline_year': 2024, 'a0': 1000.0, 'ef0': 1.0,
             'ramp': ramp, 'delta_a': {'min': 0.5, 'med': 0.4, 'max': 0.35},
             'terr': 0, 'cons': 1, 'overlap': 0}]})
    r = compute(m)
    assert r['med']['total']['cumulative_net'] > r['max']['total']['cumulative_net']
    line = next(x for x in render_markdown(m, r).splitlines() if 'fel ordning' in x)
    assert 'förluster, sista år med effekt' in line
    # The saving's end year and the loss's ΔA run the right way.
    assert 'besparing, sista år med effekt' not in line
    assert 'förluster, ΔA' not in line


def test_no_end_year_keeps_old_behaviour():
    # Default must be identical to before the field existed.
    m = _model()
    rp = m.drivers[0].ramp
    assert rp.end_year is None
    assert rp.adoption(2030) == rp.adoption(2030, 'min') == 1.0


def test_small_values_render_with_one_decimal():
    from caia.calc.engine import _fmt
    assert _fmt(1.23) == '1,2'
    assert _fmt(-0.44) == '-0,4'
    assert _fmt(0.0) == '0'
    assert _fmt(0.04) == '0'          # rounds to zero -> stays integer form
    assert _fmt(12.6) == '13'
    assert _fmt(1234.5) == '1 234' or _fmt(1234.5) == '1 235'


def test_render_flags_negative_and_collapsed_results():
    # Sign error: delta_a +2.7 (reach extracted as activity growth) -> increase.
    bad = _model(delta_a=2.7)
    md = render_markdown(bad, compute(bad))
    assert 'VARNING' in md and 'ÖKADE' in md
    # Collapsed band: identical min/med/max -> spread never reached the engine.
    flat = _model(delta_a={'min': -0.1, 'med': -0.1, 'max': -0.1})
    md2 = render_markdown(flat, compute(flat))
    assert 'min = max' in md2
    # Healthy model: no warning at all.
    ok = _model(delta_a={'min': -0.05, 'med': -0.1, 'max': -0.2})
    assert 'VARNING' not in render_markdown(ok, compute(ok))


def test_render_states_which_sign_is_a_reduction():
    # A real run (02-aterbruk, 2026-09-28) came out negative. The engine warned
    # "ÖKADE utsläpp", and QA dismissed the warning as a false alarm because it
    # read negative as a reduction: nothing in the text said otherwise.
    m = _model()
    md = render_markdown(m, compute(m))
    head = md.split('Sammanlagd effekt')[0]
    assert 'positivt tal = minskade utsläpp' in head
    assert 'negativt tal = ökade utsläpp' in head
    bad = _model(delta_a=2.7)
    warning = next(l for l in render_markdown(bad, compute(bad)).splitlines()
                   if 'ÖKADE' in l)
    assert 'negativt betyder ökade utsläpp' in warning


def test_render_shows_year_by_year_net():
    m = _model()
    md = render_markdown(m, compute(m))
    assert 'Netto per år' in md
    assert '  2030:' in md
