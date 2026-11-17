"""Deterministic emission-reduction engine.

Pure functions — no LLM, no I/O. Given a CalcModel (structured numbers extracted
from the analysis), compute ΔE per driver/scenario/year and aggregate totals,
applying the territorial/consumption/overlap climate-factor logic from the spec.

All emissions are returned in **ton CO2e/year** (kg ÷ 1000).
"""
from __future__ import annotations

import dataclasses
import logging
import math
import re
from dataclasses import dataclass

from ..logsafe import log_failure
from ..mode import UPPFOLJNING
from . import units
from .schema import UNBOUNDED_YEAR, CalcModel, Driver, Triple, spend_post_of

log = logging.getLogger(__name__)

SCENARIOS = ('min', 'med', 'max')
KG_PER_TON = 1000.0

# "Medel effekt/år" is the mean over these years whatever the target year. The
# window is a method choice (it follows the plan period of the energy and
# climate plan), so it is not moved here; it is named wherever the number is
# shown, and sanity_warnings says when the effect falls outside. Since
# 2026-10-13 it is not the headline in potential mode: that is the target year.
AVG_WINDOW = (2026, 2030)


@dataclass
class YearResult:
    year: int
    e_bau: float        # ton CO2e/year, BAU
    e_action: float     # ton CO2e/year, with action
    basis: float        # ΔE before climate factors (e_bau - e_action)
    terr: float         # ΔE territorial
    cons: float         # ΔE consumption
    overlap: float      # overlap magnitude removed
    net: float          # ΔE net (terr + cons - overlap)
    # The intermediate steps, kept so the calculation appendix prints the
    # numbers this function used instead of recomputing them a second way.
    a_bau: float = 0.0     # activity in BAU, driver units/year
    ef_bau: float = 0.0    # emission factor in BAU, kg CO2e/unit
    adoption: float = 0.0  # ramp share 0..1 this year and scenario
    d_a: float = 0.0       # ΔA × adoption
    d_ef: float = 0.0      # ΔEF × adoption
    attribution: float = 1.0  # share of the change the action caused
    charged: float = 1.0      # share of a one-off's lifetime the action brought forward
    # ΔE this year before a write-off (the manufacture bought this year).
    # Equal to basis for a driver that is not written off.
    before_write_off: float = 0.0


def _driver_year(drv: Driver, scenario: str, year: int) -> YearResult:
    """Compute one driver, one scenario, one year: _flow_year, and for a
    driver that is written off (Driver.write_off) its ΔE spread evenly over
    the lifetime. A year then carries 1/lifetime of what was bought in each
    year of the lifetime before it, itself included, and the part of a year
    that remains when the lifetime is no whole number of years; a one-off
    only up to its catch-up year. The other fields are the year's own."""
    r = _flow_year(drv, scenario, year)
    if not drv.write_off or drv.lifetime is None:
        return r
    life = drv.lifetime.get(scenario)
    last = drv.catch_up.get(scenario) if drv.one_off and drv.catch_up is not None else None
    basis = 0.0
    if last is None or year <= last:
        for k in range(0, year - drv.ramp.start_year + 1):
            w = _write_off_share(life, k)
            if w <= 0.0:
                break
            basis += w * (r.basis if k == 0 else _flow_year(drv, scenario, year - k).basis)
    terr, cons, overlap, net = _factored(drv, basis)
    return dataclasses.replace(r, basis=basis, terr=terr, cons=cons, overlap=overlap, net=net)


def _write_off_share(lifetime: float, k: int) -> float:
    """The share of a purchase written off in year k of its lifetime (0 =
    the purchase year): 1/lifetime in each whole year, then the rest of a
    lifetime that is no whole number of years, then nothing."""
    whole = math.floor(lifetime)
    if k < whole:
        return 1.0 / lifetime
    if k == whole:
        return (lifetime - whole) / lifetime
    return 0.0


def _factored(drv: Driver, basis: float) -> tuple[float, float, float, float]:
    """Territorial, consumption, overlap and net from ΔE."""
    terr = basis * drv.terr
    cons = basis * drv.cons
    # overlap removed so the same reduction isn't double-counted territorial+consumption
    overlap = min(abs(basis * drv.overlap), abs(terr), abs(cons))
    overlap = overlap if basis >= 0 else -overlap
    return terr, cons, overlap, terr + cons - overlap


def _flow_year(drv: Driver, scenario: str, year: int) -> YearResult:
    """Compute one driver, one scenario, one year, charged the year it
    happens. BAU uses the medel trend; the action effect (delta) varies by
    scenario (min/med/max)."""
    # In the unit EF0 is per (ton against kg CO2e/kg, tusen km against kg
    # CO2e/km), and EF0 per one of it (per 100 km); 1 when they agree.
    a0 = drv.a0 * drv.a0_scale
    ef0 = drv.ef0 * drv.ef0_scale
    if drv.one_off:
        # A one-off quantity exists in its own year only, without a trend.
        a_bau = a0 if year == drv.ramp.start_year else 0.0
        ef_bau = ef0
        adoption = 1.0 if year == drv.ramp.start_year else 0.0
    else:
        dt = year - drv.baseline_year
        g_a = drv.g_a.med   # BAU is the shared reference across action scenarios
        g_ef = drv.g_ef.med
        a_bau = a0 * ((1.0 + g_a) ** dt)
        ef_bau = ef0 * ((1.0 + g_ef) ** dt)
        adoption = drv.ramp.adoption(year, scenario)
    e_bau_kg = a_bau * ef_bau

    d_a = drv.delta_a.get(scenario) * adoption
    d_ef = drv.delta_ef.get(scenario) * adoption
    a_act = a_bau * (1.0 + d_a)
    ef_act = ef_bau * (1.0 + d_ef)
    e_act_kg = a_act * ef_act

    attribution = drv.attribution.get(scenario)
    charged = drv.charged_share(scenario)
    # ton; positive = reduction. Attribution scales the change, never BAU, and
    # so does the brought-forward share of a one-off.
    basis = (e_bau_kg - e_act_kg) / KG_PER_TON * attribution * charged
    terr, cons, overlap, net = _factored(drv, basis)
    return YearResult(year, e_bau_kg / KG_PER_TON, e_act_kg / KG_PER_TON,
                      basis, terr, cons, overlap, net,
                      a_bau=a_bau, ef_bau=ef_bau, adoption=adoption, d_a=d_a, d_ef=d_ef,
                      attribution=attribution, charged=charged, before_write_off=basis)


def _cum_years(model: CalcModel) -> list[int]:
    """The cumulative window: earliest ramp start .. target year, inclusive.

    One helper for compute() and render_markdown() so the "kumulativt X–Y"
    label can never drift from the years actually summed. Never empty: a ramp
    that starts after the target year still yields [target_year], which sums
    to zero instead of crashing the renderer (and thereby silently sending the
    whole kalkyl down the LLM-math fallback)."""
    # A spend post is out of the result but its year is still the action's:
    # without it klimatkrav i anläggning (run 1) lost 2025, the only year
    # before its drivers start, and the average jumped from 83 to 101 with the
    # cumulative almost unchanged.
    starts = [d.ramp.start_year for d in model.drivers + model.spend_posts]
    if starts:
        start = min(starts)
    else:
        start = model.target_year
    start = min(start, model.target_year)
    return list(range(start, model.target_year + 1))


def avg_years(model: CalcModel) -> list[int]:
    """The years "medel effekt/år" averages over.

    Potential: AVG_WINDOW, a method choice that follows the plan period.
    Follow-up: the cumulative window, so the yearly average and the total
    describe the same years. With 2026-2030 against a cumulative from 2025, a
    measure from 2025 had a first year that counted in the total but not in
    the average (the driftsmedel review, 2026-09-30)."""
    if model.mode == UPPFOLJNING:
        return _cum_years(model)
    return list(range(AVG_WINDOW[0], AVG_WINDOW[1] + 1))


def followup_year(model: CalcModel) -> int:
    """The last year counted as realised in a follow-up: the stated one, or
    else the last grant year (the last year money was spent), or else the last
    year an annual driver starts. One-offs are left out of the last fallback:
    a planned one-off years ahead would count the years before it as done."""
    if model.followup_year is not None:
        return model.followup_year
    if model.grants:
        return max(g.year for g in model.grants)
    annual = [d.ramp.start_year for d in model.drivers if not d.one_off]
    if annual:
        return max(annual)
    if model.drivers:
        return max(d.ramp.start_year for d in model.drivers)
    return model.target_year


def compute(model: CalcModel) -> dict:
    """Full computation. Returns a nested dict:
    {
      scenario: {
        'per_driver': [{name, years:{y:YearResult-as-dict}, cumulative_net, avg_net,
                        avg_2026_2030_net}],
        'total': {years:{y:{terr,cons,net}}, cumulative_net, cumulative_terr,
                  cumulative_cons, avg_net, avg_terr, avg_cons, avg_window,
                  avg_2026_2030_net, avg_2026_2030_terr, avg_2026_2030_cons}
      }
    }, plus 'headline' = the medel scenario's terr/cons/net: in potential mode
    the target year (with 'year' set to it), in follow-up mode the average per
    year over avg_years(model). The avg_2026_2030_* keys always mean exactly
    those years; in potential mode they equal avg_*.

    Follow-up mode adds, per scenario total, realised_net (years up to and
    including followup_year) and remaining_net (after it), and at the top
    'followup_year' and 'allocation' (benefit per grant year, see allocate).
    """
    years = sorted(set(model.key_years) | {model.target_year})
    cum_years = _cum_years(model)
    window = avg_years(model)
    plan_window = list(range(AVG_WINDOW[0], AVG_WINDOW[1] + 1))
    follow_up = model.mode == UPPFOLJNING
    fy = followup_year(model)

    def mean(drv, sc, attr, ys):
        return sum(getattr(_driver_year(drv, sc, y), attr) for y in ys) / len(ys)

    out: dict = {}
    for sc in SCENARIOS:
        per_driver = []
        total_years = {y: {'terr': 0.0, 'cons': 0.0, 'net': 0.0} for y in years}
        total = {k: 0.0 for k in (
            'cumulative_net', 'cumulative_terr', 'cumulative_cons',
            'avg_net', 'avg_terr', 'avg_cons',
            'avg_2026_2030_net', 'avg_2026_2030_terr', 'avg_2026_2030_cons')}
        if follow_up:
            total['realised_net'] = total['remaining_net'] = 0.0

        for drv in model.drivers:
            yres = {y: _driver_year(drv, sc, y) for y in years}
            cum_net = sum(_driver_year(drv, sc, y).net for y in cum_years)
            row = {
                'name': drv.name,
                'years': {y: vars(r) for y, r in yres.items()},
                'cumulative_net': cum_net,
                'avg_net': mean(drv, sc, 'net', window),
                'avg_2026_2030_net': mean(drv, sc, 'net', plan_window),
            }
            for y in years:
                total_years[y]['terr'] += yres[y].terr
                total_years[y]['cons'] += yres[y].cons
                total_years[y]['net'] += yres[y].net
            total['cumulative_net'] += cum_net
            total['cumulative_terr'] += sum(_driver_year(drv, sc, y).terr for y in cum_years)
            total['cumulative_cons'] += sum(_driver_year(drv, sc, y).cons for y in cum_years)
            for attr in ('net', 'terr', 'cons'):
                total[f'avg_{attr}'] += mean(drv, sc, attr, window)
                total[f'avg_2026_2030_{attr}'] += mean(drv, sc, attr, plan_window)
            if follow_up:
                row['realised_net'] = sum(_driver_year(drv, sc, y).net
                                          for y in cum_years if y <= fy)
                row['remaining_net'] = cum_net - row['realised_net']
                total['realised_net'] += row['realised_net']
                total['remaining_net'] += row['remaining_net']
            per_driver.append(row)

        total['years'] = total_years
        total['avg_window'] = (window[0], window[-1])
        out[sc] = {'per_driver': per_driver, 'total': total}

    med = out['med']['total']
    if follow_up:
        # A follow-up is judged over its own years, so the average stays.
        out['headline'] = {
            'terr': round(med['avg_terr'], 1),
            'cons': round(med['avg_cons'], 1),
            'net': round(med['avg_net'], 1),
        }
    else:
        # The reduction in the target year, 2030 by default (2026-10-13: a
        # climate target is set for one year). The
        # average per year is still computed and shown, under it. 'year' says
        # which year the number is for; a headline without it is an average.
        ty = model.target_year
        out['headline'] = {
            'terr': round(med['years'][ty]['terr'], 1),
            'cons': round(med['years'][ty]['cons'], 1),
            'net': round(med['years'][ty]['net'], 1),
            'year': ty,
        }
    if follow_up:
        out['followup_year'] = fy
        out['allocation'] = allocate(model, out)
    return out


SERIES_MAX_YEARS = 80


def year_series(model: CalcModel) -> dict:
    """Net benefit per year and scenario, every year from the earliest of the
    cumulative window and the averaging window to the later of the target year
    and the window's end. For the page's year-by-year chart: compute() keeps
    totals only for key_years, which leaves gaps a line would draw straight
    across. Same _driver_year as compute(), so the mean over avg_years() is the
    headline and the sum over the cumulative window is cumulative_net.
    """
    window = avg_years(model)
    cum = _cum_years(model)
    first = min(cum[0], window[0])
    last = max(model.target_year, window[-1])
    first = max(first, last - SERIES_MAX_YEARS + 1)
    years = list(range(first, last + 1))
    out: dict = {'years': years}
    for sc in SCENARIOS:
        out[sc] = [sum(_driver_year(drv, sc, y).net for drv in model.drivers)
                   for y in years]
    return out


def allocate(model: CalcModel, result: dict) -> list[dict]:
    """The cumulative net benefit per grant year, for a measure funded over
    several years and analysed as one.

    A driver tagged with a grant year (it is what that year's money bought)
    goes to that year whole. The rest is shared in proportion to the money
    each year used. Without grant rows, untagged drivers stay in one row,
    year None, "not allocated", rather than being divided on a guess.
    Returns [{year, amount, share, min, med, max}], shares of the untagged
    part; the rows sum to the cumulative total in every scenario.

    No grant rows and at most one tagged year is a measure with one grant
    year (the extraction leaves grants out then): nothing to divide, so no
    table. Klimatpsykologi got "Bidragsår 2025: 0" next to "Ej fördelat: 11"."""
    tagged = {d.grant_year for d in model.drivers if d.grant_year is not None}
    if not model.grants and len(tagged) < 2:
        return []
    total_kr = sum(g.amount for g in model.grants)
    rows: dict = {}

    def row(year):
        if year not in rows:
            amount = next((g.amount for g in model.grants if g.year == year), None)
            rows[year] = {'year': year, 'amount': amount, 'share': 0.0,
                          'min': 0.0, 'med': 0.0, 'max': 0.0}
        return rows[year]

    for g in model.grants:
        row(g.year)['share'] = g.amount / total_kr
    for sc in SCENARIOS:
        for drv, d in zip(model.drivers, result[sc]['per_driver']):
            if drv.grant_year is not None:
                row(drv.grant_year)[sc] += d['cumulative_net']
            elif model.grants:
                for g in model.grants:
                    row(g.year)[sc] += d['cumulative_net'] * g.amount / total_kr
            else:
                row(None)[sc] += d['cumulative_net']
    return sorted(rows.values(), key=lambda r: (r['year'] is None, r['year'] or 0))


def _fmt(n: float) -> str:
    # Whole tons hid every small measure: a 15-unit leaf-blower swap rendered
    # min/med/max all as "1 ton" and the QA step could not tell the scenarios
    # apart. One decimal below 10 ton; decimal comma as the rest of the report.
    if abs(n) < 10 and round(n, 1) != 0:
        return f"{n:.1f}".replace('.', ',')
    return f"{round(n):,}".replace(',', ' ')


def _works(drv: Driver, year: int) -> bool:
    """Whether the driver changes anything this year in the medel scenario:
    it has a ΔA or ΔEF, and the ramp lets some of it through. The same test
    _driver_year makes (d_a and d_ef are delta × adoption), without the BAU
    powers: this is asked about years the result never computes, and a year
    far out must not overflow a warning into an exception."""
    if drv.delta_a.med == 0 and drv.delta_ef.med == 0:
        return False
    if drv.one_off:
        return year == drv.ramp.start_year
    return drv.ramp.adoption(year, 'med') != 0


def _effect_years(model: CalcModel, years) -> list[int]:
    """The years among `years` in which some driver works (medel)."""
    return [y for y in years if any(_works(drv, y) for drv in model.drivers)]


# How far past its start year a driver's ramp is searched year by year.
_RAMP_SCAN = 100


def _first_effect_year(model: CalcModel) -> int | None:
    """The first year the action changes anything (medel), or None if it
    never does. A driver that is not working by its full-effect year never
    will: after it there is only decay or the end year. The search is capped
    so that an absurd year in the extraction costs nothing; the full-effect
    year itself is always tried."""
    firsts = []
    for drv in model.drivers:
        start = drv.ramp.start_year
        full = max(start, drv.ramp.full_effect_year)
        for y in (*range(start, min(full, start + _RAMP_SCAN) + 1), full):
            if _works(drv, y):
                firsts.append(y)
                break
    return min(firsts) if firsts else None


def _factor(f: float) -> str:
    return f"{round(f):,}".replace(',', ' ')


def _qty(x: float, unit: str) -> str:
    """An amount and its unit; "2 000 × 100 kg" when the unit starts with a
    number, so that it never reads as one number."""
    return f"{_num(x)} × {unit}" if unit[:1].isdigit() else f"{_num(x)} {unit}"


def unit_warnings(model: CalcModel) -> list[str]:
    """One warning per driver whose A0 and EF0 units do not fit together.

    The engine computes A0 × EF0 and reads it as kg CO2e. A run with A0 in
    "ton nyvara/år" next to EF0 in "kg CO2e/kg" came out a thousand times too
    small (0,1 ton instead of 86), and an A0 counted in retailers next to a
    factor per kg came out meaningless. Neither the source check nor the
    comparison with what the user approved compares the two units with each
    other. The rules are in calc.units.mismatch; this writes them in words."""
    out: list[str] = []
    for i, d in enumerate(model.drivers, 1):
        who = f"drivare {i} ({d.name})"
        conv = (units.conversion(d.a0_unit, d.ef0_unit)
                if d.a0_scale != 1.0 or d.ef0_scale != 1.0 else None)
        m = conv['mismatch'] if conv is not None else units.plain_mismatch(d.a0_unit, d.ef0_unit)
        if conv is not None and (m is None or m['kind'] == 'prefix'):
            # Converted by the engine (calc.units.conversion): ton against kg,
            # a size word (tusen km) or a factor per a number of units (per
            # 100 km). Say what was done and how wrong it is if the number
            # had already been converted.
            done = []
            if d.a0_scale != 1.0:
                done.append(f"aktiviteten: {_qty(d.a0, d.a0_scale_from)} = "
                            f"{_qty(d.a0 * d.a0_scale, d.a0_scale_unit)}")
            if d.ef0_scale != 1.0:
                done.append(f"utsläppsfaktorn: {_num(d.ef0)} {d.ef0_unit} = "
                            f"{_sig(d.ef0 * d.ef0_scale, 3)} {d.ef0_scale_unit}")
            total = d.a0_scale * d.ef0_scale
            out.append(
                f"VARNING: enheterna går inte ihop för {who}: aktiviteten är i {conv['a0_from']}, "
                f"men utsläppsfaktorn gäller per {conv['ef0_per']}. Kalkylen har räknat om "
                f"{' och '.join(done)}. Stämmer enheterna i underlaget är resultatet rätt nu. Var "
                "talet redan omräknat men enheten fel angiven, är resultatet fel med en faktor "
                f"{_factor(max(total, 1 / total))}; kontrollera aktiviteten (A0) och "
                "utsläppsfaktorn (EF0) under Indata per drivare.")
        elif m is not None:
            a, e = m['a0'], m['ef0']
            if m['kind'] == 'prefix':
                tail = f"Resultatet kan vara fel med en faktor {_factor(m['factor'])}."
            elif m['kind'] == 'quantity':
                tail = "Det ena går inte att räkna om till det andra, så resultatet kan vara helt fel."
            else:
                tail = "Resultatet kan vara helt fel."
            if d.a0_scale != 1.0:
                # A size word is still converted ("tusen handlare").
                tail += (f" Kalkylen har räknat om aktiviteten: {_qty(d.a0, d.a0_scale_from)} = "
                         f"{_qty(d.a0 * d.a0_scale, d.a0_scale_unit)}.")
            out.append(
                f"VARNING: enheterna går inte ihop för {who}: aktiviteten är i {a}, men "
                f"utsläppsfaktorn gäller per {e}. {tail} Kontrollera aktiviteten (A0) och "
                "utsläppsfaktorn (EF0) under Indata per drivare.")
        n = units.numerator_mismatch(d.ef0_unit)
        if n is not None:
            out.append(
                f"VARNING: utsläppsfaktorn för {who} är angiven i {n['ef0']} CO2e, men "
                "kalkylen räknar den som kg CO2e. Resultatet kan vara fel med en faktor "
                f"{_factor(n['factor'])}. Kontrollera utsläppsfaktorn (EF0) under Indata "
                "per drivare.")
    return out


def sanity_warnings(result: dict, model: CalcModel | None = None) -> list[str]:
    """Sanity checks the rapport and QA agents should see next to the numbers,
    and the page shows next to the headline.

    A negative medel result on a measure that exists to cut emissions almost
    always means the extraction inverted a sign or scaled the wrong thing (the
    KFF workshop run: reach was extracted as +270 % activity, giving -7 000
    ton/yr). A collapsed min = max band means the scenario spread never reached
    the engine. Neither is an engine error, but both must be visible.

    With the model, two more: an analysis with no effect at all (every delta
    zero) comes out as a confident 0, and an effect that starts after the
    averaging window, or a target year past it, makes "medel effekt/år" a
    number that leaves most of the effect out.

    And two about when the action works at all. An action whose first year
    with effect lies after the target year (and, in potential mode, outside
    the averaging window) gave average 0 and cumulative 0 with nothing said.
    An action that works in fewer than half the window's years gave a low
    average with nothing said. Both are notes on the years: no number moves.

    And first of all, per driver, when the units of A0 and EF0 do not fit
    together (unit_warnings)."""
    out: list[str] = []
    med = result['med']['total']
    if model is not None:
        # First: a unit error makes every other number wrong as well. Text
        # only, so a fault in it must not cost the computed result.
        try:
            out += unit_warnings(model)
        except Exception as e:  # noqa: BLE001
            log_failure(log, "unit check failed; warnings go out without it", e)
        out += _symmetry_notes(model)
        if model.drivers and all(
                d.delta_a.med == 0 and d.delta_ef.med == 0 for d in model.drivers):
            out.append(
                "VARNING: ingen drivare har någon effekt i medelscenariot (alla delta är 0). "
                "Resultatet 0 betyder att effekten inte nådde kalkylen, inte att åtgärden saknar effekt.")
        for d in model.drivers:
            if d.one_off and d.ramp.start_year > model.target_year:
                out.append(
                    f"OBS: engångsposten {d.name} ({d.ramp.start_year}) ligger efter målåret "
                    f"{model.target_year} och räknas inte.")
            # A catch-up year at or before the purchase charges that scenario
            # with at most one year of the lifetime, so the post nearly
            # vanishes there while the other scenarios carry it. The medel
            # case is dropped in potential mode (schema.drop_same_year_catch_up);
            # min or max alone is said, not changed.
            if d.one_off and d.catch_up is not None and d.lifetime is not None and d.direction() > 0:
                early = [n for sc, n in (('min', 'min'), ('med', 'medel'), ('max', 'max'))
                         if d.catch_up.get(sc) <= d.ramp.start_year]
                if early:
                    out.append(
                        f"OBS: engångsposten {d.name}: ikapp-året i {' och '.join(early)} "
                        f"är inte senare än inköpsåret {d.ramp.start_year}, så posten belastar "
                        f"{'det scenariot' if len(early) == 1 else 'de scenarierna'} med högst "
                        "ett år av livslängden. Kontrollera ikapp-åren under Indata per drivare.")
            elif not d.one_off and d.ramp.first_year_share != 1.0 and not d.ramp.first_year_share_used:
                out.append(
                    f"OBS: {d.name}: andelen av startåret ({_num(d.ramp.first_year_share * 100)} %) "
                    f"används inte, eftersom effekten trappas upp från noll {d.ramp.start_year}. "
                    "Den gäller bara när full effekt kommer direkt.")
            if (not d.one_off and d.ramp.last_year_share is not None
                    and not (d.ramp.end_year is not None and any(
                        d.ramp.last_year_share_applies(d.ramp.end_year.get(sc), sc)
                        for sc in ('min', 'med', 'max')))):
                out.append(
                    f"OBS: {d.name}: andelen av slutåret används inte, eftersom drivaren "
                    "saknar slutår (ramp.end_year) eller slutar samma år som den börjar.")
        grant_years = {g.year for g in model.grants}
        for d in model.drivers:
            if grant_years and d.grant_year is not None and d.grant_year not in grant_years:
                out.append(
                    f"OBS: {d.name} är märkt med bidragsår {d.grant_year}, men det året finns "
                    "inte bland bidragsraderna. Nyttan står på en egen rad utan belopp.")
        lo_y, hi_y = AVG_WINDOW
        ty = model.target_year
        # The years either number counts, and whether the action does anything
        # in any of them. Measured on the ramp, not on the result: a zero can
        # also come from attribution or the climate factors, and that is not
        # a matter of years.
        counted = sorted(set(avg_years(model)) | set(_cum_years(model)))
        has_effect = any(d.delta_a.med != 0 or d.delta_ef.med != 0 for d in model.drivers)
        outside = has_effect and not _effect_years(model, counted)
        if outside:
            first = _first_effect_year(model)
            if first is None:
                out.append(
                    "OBS: medel effekt/år och kumulativt blir båda 0, eftersom åtgärden inte "
                    "har effekt något år: startår, år för full effekt och slutår ger "
                    "tillsammans ingen verkan. Kontrollera åren under Indata per drivare.")
            elif model.mode == UPPFOLJNING:
                out.append(
                    f"OBS: åtgärden har effekt först {first}. Det är efter målåret {ty}, så "
                    "inget räknas in i medel effekt/år eller kumulativt. Båda blir 0. Nollan "
                    "betyder att effekten faller utanför de år som räknas, inte att åtgärden "
                    "saknar effekt.")
            else:
                out.append(
                    f"OBS: åtgärden har effekt först {first}. Det är efter målåret {ty}, så "
                    f"inget räknas in i kumulativt, och utanför {lo_y}–{hi_y}, så inget räknas "
                    "in i medel effekt/år. Båda blir 0. Nollan betyder att effekten faller "
                    "utanför de år som räknas, inte att åtgärden saknar effekt.")
        # In follow-up mode the average runs over the cumulative years, so
        # neither window note can be true there.
        if model.mode == UPPFOLJNING or outside:
            pass
        elif abs(med['avg_net']) < 1e-9 and abs(med['cumulative_net']) > 1e-9:
            out.append(
                f"OBS: medel effekt/år räknas över {lo_y}–{hi_y} och blir 0 här, eftersom "
                f"effekten ligger utanför de åren. Se kumulativt till {model.target_year}.")
        # A target year after the window used to need a note here, because the
        # headline was the average. It is the target year now (2026-10-13).
        # The average always divides by every year in the window. When the
        # action works in fewer than half of them, most of what is averaged
        # is zeros, and the headline says more about the window than about
        # the action. Potential only: a follow-up averages from its own start.
        if model.mode != UPPFOLJNING and has_effect:
            plan = list(range(lo_y, hi_y + 1))
            working = _effect_years(model, plan)
            if working and 2 * len(working) < len(plan):
                out.append(
                    f"OBS: medel effekt/år delas på {len(plan)} år ({lo_y}–{hi_y}), men "
                    f"åtgärden har effekt bara {len(working)} av dem "
                    f"({', '.join(str(y) for y in working)}). De övriga räknas som noll, så "
                    "medlet är lågt jämfört med effekten de år åtgärden verkar. Läs det "
                    "tillsammans med startåret och det kumulativa talet.")
    # The headline names its year only in potential mode, where it is the target year.
    head_year = (result.get('headline') or {}).get('year')
    target_net = med['years'][head_year]['net'] if head_year in med['years'] else 0.0
    if med['avg_net'] < 0 or med['cumulative_net'] < 0 or target_net < 0:
        out.append(
            "VARNING: medelscenariot ger ÖKADE utsläpp: målårets tal, medeleffekten eller det "
            "kumulativa talet är negativt, och negativt betyder ökade utsläpp jämfört med BAU. "
            "Kontrollera tecken på "
            "delta_a/delta_ef och att räckvidd eller återbruk inte extraherats som ökad "
            "aktivitet.")
    lo = result['min']['total']['cumulative_net']
    hi = result['max']['total']['cumulative_net']
    if abs(hi - lo) < 1e-9 and abs(med['cumulative_net']) > 1e-9:
        out.append(
            "VARNING: min = max kumulativt; scenariospridningen har inte nått kalkylen "
            "(spridning i BAU-trenden används inte, lägg den i delta eller ramp.end_year).")
    # Scenarios are ordered by construction (min <= med <= max). When they come
    # out of order one driver has its band inverted, typically a one-off cost
    # driver (battery manufacturing) whose "min" got the largest penalty.
    if lo > med['cumulative_net'] + 1e-9 or med['cumulative_net'] > hi + 1e-9:
        msg = ("VARNING: scenarierna är i fel ordning kumulativt (min > medel eller medel > max). "
               "Minst en drivare har inverterat band; kontrollera tecken per scenario, särskilt "
               "för engångsposter som räknas som negativ nytta.")
        # Which inputs: text only, so a fault here must not cost the result.
        if model is not None:
            try:
                msg += _inverted_inputs(model, result)
            except Exception as e:  # noqa: BLE001
                log_failure(log, "inverted-input check failed; warning goes out without it", e)
        out.append(msg)
    return out


def _symmetry_notes(model: CalcModel) -> list[str]:
    """Where the action's own emissions and its benefit were treated
    differently, and what the engine did about it (the review of driftsmedel
    runs 1 and 2, 2026-10-22): an attribution band turned the right way round,
    a one-off charged in full against a benefit that stops at a catch-up year,
    and the grant's own emissions kept out of the result."""
    out: list[str] = []
    for d in model.drivers:
        if d.attribution_given is not None:
            out.append(
                f"OBS: {d.name}: attributionen stod i omvänd ordning ({_band(d.attribution_given)}), "
                "fast drivaren minskar utsläppen. Kalkylen vände den, så att min har den lägsta "
                f"andelen och max den högsta: {_band(d.attribution)}. Bara en drivare som ökar "
                "utsläppen kan ha den högsta andelen i min.")
        if d.flip_given is not None:
            da, de = d.flip_given
            turned = any((1 + da.get(sc)) * (1 + de.get(sc)) < 1 for sc in ('min', 'med', 'max'))
            out.append(
                f"OBS: engångsposten {d.name} höjde mängden (ΔA {_band(da)}) och sänkte faktorn "
                f"(ΔEF {_band(de)}) på hela posten, så att "
                + ("kostnaden räknades som en minskning av utsläppen. " if turned else
                   "kostnaden blev mindre än den tillkomna mängden. ")
                + "En kostnad blir aldrig en nytta: kalkylen räknar i stället den tillkomna "
                f"mängden med postens egen faktor, ΔA {_band(d.delta_a)} och ΔEF 0.")
    benefits = [b for b in model.drivers if not b.one_off and b.direction() < 0]
    ends = [b.ramp.end_year.med if b.ramp.end_year is not None else UNBOUNDED_YEAR
            for b in benefits]
    if ends and max(ends) < UNBOUNDED_YEAR:
        for d in model.drivers:
            if d.one_off and d.direction() > 0 and d.lifetime is None:
                out.append(
                    f"OBS: engångsposten {d.name} belastar insatsen fullt {d.ramp.start_year}, men "
                    f"nyttan upphör efter {max(ends)} (medel), när det som hade hänt ändå har "
                    "kommit ikapp. Är posten utrustning som insatsen bara köpte tidigare än den "
                    "annars hade köpts, ska bara de tidigarelagda åren av livslängden belasta "
                    "insatsen. Ange då utrustningens livslängd.")
    n = len(model.spend_posts)
    if n:
        out.append(
            ("OBS: en post räknade" if n == 1 else f"OBS: {n} poster räknade")
            + " pengarnas egna utsläpp (bidragsbeloppet i kronor gånger utsläpp per krona). "
            "Pengarna hade använts av kommunen ändå, så det ingår inte i resultatet. Det står "
            "på egen rad under Pengarnas egna utsläpp.")
    return out


def _inverted_inputs(model: CalcModel, result: dict) -> str:
    """The banded inputs that pull against the scenario order, as a sentence
    to add to the out-of-order warning, or ''.

    Moving one input from its min value to its max value, the others at medel
    (the swing bearing() already computes), should never lower the result:
    min is the cautious scenario and max the high one. An input whose swing is
    negative is ordered against the scenarios, and those are what put the
    scenarios out of order. Sola (driftsmedel run 1, 2026-10-21) came out
    13 / 15 / -30: the reused quantity was the driver's activity and was
    raised with ΔA, which the engine reads as more emissions, and a net share
    of 0,75 to 0,92 was written as ΔEF from -25 % (min) to -8 % (max). Its
    four ΔA and ΔEF bands all had a negative swing. A cost driver whose effect
    lasts longest in max (end year) is the other common case."""
    wrong = [it for it in bearing(model, result)['items'] if it['swing'] < -1e-9]
    if not wrong:
        return ""
    wrong.sort(key=lambda it: it['swing'])
    shown = "; ".join(f"{it['driver']}, {it['label']}: {_fmt(it['low'])} vid minvärdet men "
                      f"{_fmt(it['high'])} vid maxvärdet" for it in wrong[:5])
    more = f" (och {len(wrong) - 5} till)" if len(wrong) > 5 else ""
    return (" Indata som drar åt fel håll, prövade ett i taget med övriga på medel (kumulativt "
            f"netto, ton CO2e): {shown}{more}. Ett högre scenario ska aldrig ge lägre resultat. "
            "Vanliga orsaker: drivarens aktivitet är något som minskar utsläppen (till exempel "
            "återbrukad mängd) och höjs med ΔA, fast motorn läser en högre aktivitet som mer "
            "utsläpp; eller en kostnadsdrivare vars värden står i nyttans ordning.")


def render_markdown(model: CalcModel, result: dict) -> str:
    """Render the computed result as the kalkyl markdown the rapport agent reads.

    Crucially this uses the schema's exact field labels so extract_key_metric and
    the rapport agent pick up the headline numbers."""
    med = result['med']['total']
    lo = result['min']['total']
    hi = result['max']['total']
    ty = model.target_year
    warn_lines = sanity_warnings(result, model)
    cum_years = _cum_years(model)
    lines = [
        f"Kalkyl & tidsprofil för åtgärd: {model.action_name}",
        "",
        "Beräknat deterministiskt (Python-motor) från extraherade parametrar. "
        "Min/medel/max är tre separata scenarier; BAU är gemensam referens.",
        "Tecken: ΔE = BAU minus åtgärd, så positivt tal = minskade utsläpp (klimatnytta) "
        "och negativt tal = ökade utsläpp jämfört med BAU.",
        "",
        "Sammanlagd effekt för åtgärden (Scenario Medel):",
        f"  ΔE_{ty}_total (Territoriell): {_fmt(med['years'][ty]['terr'])} ton CO2e/år",
        f"  ΔE_{ty}_total (Konsumtion): {_fmt(med['years'][ty]['cons'])} ton CO2e/år",
        f"  ΔE_{ty}_total (Netto): {_fmt(med['years'][ty]['net'])} ton CO2e/år",
        f"  ΔE_kumulativt_till_målår_total (Netto): {_fmt(med['cumulative_net'])} ton CO2e",
        f"  Medel effekt/år (Territoriell): {_fmt(med['avg_terr'])} ton CO2e/år",
        f"  Medel effekt/år (Konsumtion): {_fmt(med['avg_cons'])} ton CO2e/år",
        f"  Medel effekt/år (Netto/Total): {_fmt(med['avg_net'])} ton CO2e/år",
        _window_note(model),
        "",
        f"Scenariospann (Netto {ty}): {_fmt(lo['years'][ty]['net'])} – "
        f"{_fmt(hi['years'][ty]['net'])} ton CO2e/år (min–max).",
        f"Scenariospann (Netto kumulativt {cum_years[0]}–{ty}): {_fmt(lo['cumulative_net'])} / "
        f"{_fmt(med['cumulative_net'])} / {_fmt(hi['cumulative_net'])} ton CO2e (min / medel / max).",
        "",
    ]
    if model.mode == UPPFOLJNING:
        lines += _followup_lines(model, result) + [""]
    lines += ["Per drivare (Scenario Medel):"]
    for d in result['med']['per_driver']:
        yr = d['years'][ty]
        lines.append(f"  - {d['name']}: ΔE_{ty} netto {_fmt(yr['net'])} ton CO2e/år "
                     f"(territoriell {_fmt(yr['terr'])}, konsumtion {_fmt(yr['cons'])})")
    if model.spend_posts:
        lines += [""] + _spend_lines(model)
    # Year-by-year net per scenario, so a time-limited effect (ramp.end_year)
    # is visible as the step it is, instead of hiding inside the average.
    lines += ["", "Netto per år (min / medel / max, ton CO2e/år):"]
    for y in cum_years:
        vals = []
        for sc in SCENARIOS:
            vals.append(sum(_driver_year(drv, sc, y).net for drv in model.drivers))
        lines.append(f"  {y}: {_fmt(vals[0])} / {_fmt(vals[1])} / {_fmt(vals[2])}")
    # The inputs the engine ran on. Without them the QA step checked a result
    # it could not trace back, and a reader could not see the climate factors
    # or the ramp at all.
    lines += ["", "Indata per drivare (det programmet räknade med):"]
    for drv in model.drivers:
        lines.append(
            f"  - {drv.name}: {_inputs(drv)}"
            + (f", effekten upphör efter {drv.ramp.end_year.med} (medel)"
               if drv.ramp.end_year is not None
               and drv.ramp.end_year.med < UNBOUNDED_YEAR else ""))
    # The bearing check adds text, never numbers: a fault in it must not
    # throw a computed result away for the LLM fallback.
    try:
        lines += [""] + render_bearing(model, bearing(model, result))
    except Exception as e:  # noqa: BLE001
        log_failure(log, "bearing check failed; kalkyl text goes out without it", e)
    if warn_lines:
        lines += [""] + warn_lines
    return "\n".join(lines)


def _window_note(model: CalcModel) -> str:
    years = avg_years(model)
    if model.mode == UPPFOLJNING:
        return (f"  (Medel effekt/år är medelvärdet över {years[0]}–{years[-1]}, samma år som "
                "det kumulativa talet, så kumulativt ÷ antal år ger samma tal.)")
    return (f"  (Medel effekt/år är medelvärdet över {AVG_WINDOW[0]}–{AVG_WINDOW[1]}. År utanför "
            "ingår i kumulativt men inte i medlet, så kumulativt ÷ antal år ger ett annat tal.)")


def _followup_lines(model: CalcModel, result: dict) -> list[str]:
    """Realised against remaining, and the benefit per grant year."""
    cum = _cum_years(model)
    fy = result['followup_year']
    t = {sc: result[sc]['total'] for sc in SCENARIOS}
    lines = ["Uppföljning (netto, ton CO2e, min / medel / max):"]
    if fy >= cum[0]:
        lines.append(f"  Realiserat {_span(cum[0], min(fy, cum[-1]))}: "
                     + " / ".join(_fmt(t[sc]['realised_net']) for sc in SCENARIOS))
    if fy < cum[-1]:
        lines.append(f"  Återstår {_span(max(fy + 1, cum[0]), cum[-1])}: "
                     + " / ".join(_fmt(t[sc]['remaining_net']) for sc in SCENARIOS))
    lines.append(f"  (Realiserat är de år som har passerat till och med {fy}. Det är också "
                 "en beräkning, inte en mätning, om inte analysen säger att talet är uppmätt.)")
    alloc = result.get('allocation') or []
    if alloc:
        lines += ["", "Fördelning per bidragsår (kumulativt netto, ton CO2e, min / medel / max):"]
        for r in alloc:
            label = "Ej fördelat" if r['year'] is None else f"Bidragsår {r['year']}"
            money = (f" ({_num(r['amount'])} kr, {_num(r['share'] * 100)} % av beloppet)"
                     if r['amount'] is not None else "")
            lines.append(f"  {label}{money}: "
                         + " / ".join(_fmt(r[sc]) for sc in SCENARIOS))
        lines.append("  (Drivare som ett visst års pengar köpte går till det året. Resten "
                     "fördelas efter hur mycket pengar varje år använde.)")
    return lines


def _spend_lines(model: CalcModel) -> list[str]:
    """The grant's own emissions, outside the result (schema.SPEND_EF_PER_KR)."""
    lines = ["Pengarnas egna utsläpp (ingår inte i resultatet):"]
    for drv in model.spend_posts:
        p = spend_post_of(drv)
        when = f"{p['year']}" if p['one_off'] else f"per år från {p['year']}"
        given = (f" Analysen angav {_sig(p['ef_given'], 3)} kg CO2e/kr; kalkylen räknar med "
                 "en tjänstetung faktor." if p['ef_given'] > p['ef_used'] else "")
        lines.append(f"  - {p['name']}: {_num(p['kronor'])} kr × {_sig(p['ef_used'], 3)} kg CO2e/kr "
                     f"= {_fmt(p['ton'])} ton CO2e, {when}.{given}")
    lines.append("  (Bidragsbeloppet hade använts av kommunen ändå, så det är ingen utsläppskälla "
                 "som insatsen orsakat. Raden visar storleksordningen. Det som köptes och är "
                 "fysiskt, som utrustning, material och transporter, räknas som egna drivare.)")
    return lines


def _span(a: int, b: int) -> str:
    return str(a) if a == b else f"{a}–{b}"


# --- Vad åtgärden ändrar i verksamheten ---------------------------------------
#
# DIN SPEC 91637 5.2 asks that a result can be stated in the activity's own
# unit (kilometres, litres, m²), so that it can be followed up and set against
# a goal; the tons alone could not. The engine already has A_BAU and ΔA ×
# adoption per year. This turns them into one sentence per driver for the
# target year and the averaging window (2026-11-09, recommendation 2 in
# the DIN SPEC comparison). The numbers come from _driver_year, attribution and
# a one-off's charged share included, so the units describe the same change as
# the tons beside them.

ACTIVITY_HEADING = "**Vad åtgärden ändrar i verksamheten**"
ACTIVITY_STAMP = "Skrivet av CAIA:s kalkylmotor ur samma tal som tonnen, scenario medel."
ACTIVITY_INTRO = ("Samma förändring som tonnen, räknad i det som går att följa i "
                  "verksamheten.")
_ACTIVITY_LOWER_NOTE = ("Minst: talen räknar med att det som ersätter inte släpper ut något "
                        "alls. Ger det också utsläpp behöver en större del byta. Blir i stället "
                        "allt lite renare är talet bara en jämförelse.")
_ACTIVITY_SHARE_NOTE = ("Talen är åtgärdens egen del av förändringen, med samma andel som "
                        "tonnen räknas med.")
_ACTIVITY_WRITE_OFF_NOTE = ("Tillverkning räknas här det år den köps. Tonnen skriver av den "
                            "jämnt över utrustningens livslängd.")
# A unit that is itself an emission ("kg CO2e/år", a lumped driver) has no
# other unit to show: the change in it is the tons again.
_CO2_UNIT = re.compile(r"co\s*(?:2|₂)", re.IGNORECASE)
# "100 kr" as a unit: an amount per unit, read as the number times the word
# so that "50 100 kr" never appears.
_COUNTED_UNIT = re.compile(r"^(\d+(?:[.,]\d+)?)\s+(\S.*)$")
# Smaller than this, in the unit shown, is no change.
_ACTIVITY_EPS = 1e-9


def activity_unit(unit_text: str) -> tuple[str, float] | None:
    """The activity's unit as a reader counts it, and what one unit of A0 is
    in it. "km/år" -> ("km", 1); "tusen km/år" -> ("km", 1000);
    "kWh batterikapacitet per år (400 kWh ...)"
    -> ("kWh batterikapacitet", 1); "100 kr" -> ("kr", 100); "" -> ("enheter",
    1). None when the unit is an emission (CO2e): its change is the tons."""
    text = (unit_text or "").split("(")[0]
    if _CO2_UNIT.search(text):
        return None
    part = re.split(r"\s*/\s*|\s+per\s+", text, maxsplit=1, flags=re.IGNORECASE)[0]
    part = part.strip(" ,.;:")
    if not part:
        return ("enheter", 1.0)
    # "tusen km": counted in km, a thousand to each unit of A0.
    size, _, rest = units.size_of(part)
    if size != 1.0 and rest:
        return (rest, size)
    m = _COUNTED_UNIT.match(part)
    if m:
        return (m.group(2).strip(), float(m.group(1).replace(",", ".")))
    return (part, 1.0)


def _amount(x: float) -> str:
    """An amount of activity for a reader: two significant digits, space
    thousands, decimal comma. 108 000 -> '110 000', 1 380 -> '1 400', 0,042 ->
    '0,042'. The result rests on assumptions; more digits would claim more."""
    x = abs(x)
    if x < _ACTIVITY_EPS:
        return "0"
    if x >= 100:
        step = 10 ** (math.floor(math.log10(x)) - 1)
        return f"{round(x / step) * step:,.0f}".replace(",", " ")
    return _sig(x, 2)


def _share(x: float) -> str:
    return f"{_sig(abs(x) * 100, 2)} %"


def _activity_year(drv: Driver, scenario: str, year: int, factor: float) -> dict:
    """One driver's activity this year in the unit shown: without the action
    ('bau'), the action's change in it ('change', negative = less), with the
    action ('act'), the action's share of the change in emissions per unit
    ('ef', negative = lower), and the least amount that must go without
    emissions for that ('zero'). Attribution and a one-off's charged share
    scale the change as they scale ΔE."""
    r = _driver_year(drv, scenario, year)
    k = r.attribution * r.charged
    bau = r.a_bau / drv.a0_scale * factor
    act = bau * (1.0 + r.d_a)
    ef = r.d_ef * k
    return {'bau': bau, 'change': bau * r.d_a * k, 'act': act, 'ef': ef,
            'zero': act * -ef if ef < 0 else 0.0}


def _more_less(x: float) -> str:
    return "mindre" if x < 0 else "mer"


def _activity_text(drv: Driver, model: CalcModel, unit: str, factor: float) -> tuple[str, bool]:
    """The sentence for one driver, and whether it states a least amount.
    '' when the driver changes nothing in its own unit."""
    window = avg_years(model)
    when = _span(window[0], window[-1])
    year = drv.ramp.start_year if drv.one_off else model.target_year
    at = {sc: _activity_year(drv, sc, year, factor) for sc in SCENARIOS}
    med = at['med']
    mean = None
    if not drv.one_off:
        ys = [_activity_year(drv, 'med', y, factor) for y in window]
        mean = {k: sum(v[k] for v in ys) / len(ys) for k in ('change', 'ef', 'zero')}
    label = f"år {year}"
    parts = []
    lower = False

    has_a = any(drv.delta_a.get(sc) != 0 for sc in SCENARIOS)
    if has_a and (abs(med['change']) > _ACTIVITY_EPS
                  or (mean is not None and abs(mean['change']) > _ACTIVITY_EPS)):
        c = med['change']
        if abs(c) > _ACTIVITY_EPS:
            text = f"{_amount(c)} {unit} {_more_less(c)} {label} än utan åtgärden"
            notes = ["engångspost"] if drv.one_off else []
            if med['bau'] > 0 and not drv.one_off:
                notes.append(_share(c / med['bau']))
            ends = sorted(abs(at[sc]['change']) for sc in ('min', 'max'))
            if (all(at[sc]['change'] * c > 0 for sc in ('min', 'max'))
                    and _amount(ends[0]) != _amount(ends[1])):
                notes.append(f"spann {_amount(ends[0])}–{_amount(ends[1])}")
            if notes:
                text += f" ({', '.join(notes)})"
        else:
            text = f"ingen ändring {label}"
        if mean is not None:
            m = mean['change']
            text += (f", i snitt {_amount(m)} {unit} {_more_less(m)} per år {when}"
                     if abs(m) > _ACTIVITY_EPS else f", ingen ändring i snitt {when}")
        parts.append(text)

    has_ef = any(drv.delta_ef.get(sc) != 0 for sc in SCENARIOS)
    if has_ef and (abs(med['ef']) > _ACTIVITY_EPS
                   or (mean is not None and abs(mean['ef']) > _ACTIVITY_EPS)):
        e = med['ef']
        per = f"utsläppen per {unit}"
        if e < -_ACTIVITY_EPS:
            text = (f"{per} är {_share(e)} lägre {label}, som om minst {_amount(med['zero'])} "
                    f"av {_amount(med['act'])} {unit} gick helt utan utsläpp")
            if mean is not None:
                text += (f", i snitt minst {_amount(mean['zero'])} {unit} per år {when}"
                         if mean['zero'] > _ACTIVITY_EPS else f", ingen ändring i snitt {when}")
            lower = True
        elif e > _ACTIVITY_EPS:
            text = f"{per} är {_share(e)} högre {label}"
            if mean is not None:
                m = mean['ef']
                text += (f", i snitt {_share(m)} {'lägre' if m < 0 else 'högre'} per år {when}"
                         if abs(m) > _ACTIVITY_EPS else f", ingen ändring i snitt {when}")
        else:
            text = f"{per} ändras inte {label}"
            m = mean['ef']
            if m < -_ACTIVITY_EPS:
                text += (f", i snitt {_share(m)} lägre per år {when}, som om minst "
                         f"{_amount(mean['zero'])} {unit} per år gick helt utan utsläpp")
                lower = True
            else:
                text += f", i snitt {_share(m)} högre per år {when}"
        parts.append(text)
    return "; ".join(parts), lower


def _plain_line(text: str) -> str:
    """A driver name on one line: a newline in it would end the bullet."""
    return " ".join(str(text).split())


def activity_changes(model: CalcModel) -> dict:
    """What the action changes in each driver's own unit (medel scenario).

    Returns {'rows': [{'driver', 'text', 'weight'}], 'notes': [...]}. 'text'
    follows the driver's name and a colon; 'weight' is the absolute net of the
    driver in the year its text is about, for a reader that shows only the
    largest. A driver with no ΔA or ΔEF in any scenario is left out; one whose
    activity is counted in emissions says so."""
    rows = []
    lower = shared = written = False
    for drv in model.drivers:
        if all(drv.delta_a.get(sc) == 0 and drv.delta_ef.get(sc) == 0 for sc in SCENARIOS):
            continue
        year = drv.ramp.start_year if drv.one_off else model.target_year
        # A written-off one-off's text is about the whole purchase, so it is
        # weighed by the purchase, not by the first year's share of it.
        flow = _flow_year if drv.one_off and drv.write_off else _driver_year
        weight = abs(flow(drv, 'med', year).net)
        name = _plain_line(drv.name)
        unit = activity_unit(drv.a0_unit)
        if unit is None:
            rows.append({'driver': name, 'weight': weight,
                         'text': "räknas direkt i utsläpp, så det finns ingen annan enhet att visa"})
            continue
        text, low = _activity_text(drv, model, *unit)
        if not text:
            continue
        rows.append({'driver': name, 'text': text, 'weight': weight})
        lower = lower or low
        shared = shared or not _is_one(drv.attribution) or drv.charged_share('med') != 1.0
        written = written or drv.write_off
    notes = (([_ACTIVITY_LOWER_NOTE] if lower else []) + ([_ACTIVITY_SHARE_NOTE] if shared else [])
             + ([_ACTIVITY_WRITE_OFF_NOTE] if written else []))
    return {'rows': rows, 'notes': notes}


def render_activity(model: CalcModel, changes: dict | None = None) -> str:
    """The section as markdown, or '' when no driver changes anything. The
    kalkyl text carries it between the result and the appendix, and
    /api/rapport moves it into the report beside the tons (caia.appendix)."""
    changes = activity_changes(model) if changes is None else changes
    if not changes['rows']:
        return ""
    lines = [ACTIVITY_HEADING, "", ACTIVITY_INTRO, ""]
    lines += [f"- {r['driver']}: {r['text']}." for r in changes['rows']]
    lines += [""] + changes['notes'] + ([""] if changes['notes'] else []) + [f"*{ACTIVITY_STAMP}*"]
    return "\n".join(lines)


def _inputs(drv: Driver) -> str:
    """One driver's inputs as the engine used them, shared by the kalkyl text
    and the appendix so the two cannot describe different inputs. The parts
    after the ramp appear only when the analysis set them, so a potential
    analysis reads exactly as before."""
    if drv.one_off and drv.write_off:
        timing = (f"engångspost {drv.ramp.start_year}, livslängd {_years(drv.lifetime)}, "
                  "skrivs av jämnt över livslängden")
        if drv.catch_up is not None and drv.catch_up.med < UNBOUNDED_YEAR:
            source = " (nyttans sista år)" if drv.catch_up_from else ""
            timing += f" till och med ikapp-år {_show_year(drv.catch_up.med)}{source}"
    elif drv.one_off:
        timing = f"engångspost {drv.ramp.start_year}"
        if drv.lifetime is not None:
            timing += f", livslängd {_years(drv.lifetime)}"
            if drv.catch_up is not None and drv.catch_up.med < UNBOUNDED_YEAR:
                share = _num(drv.charged_share('med') * 100)
                if drv.catch_up_from == "målåret":
                    timing += (f", avskriven till och med målåret {_show_year(drv.catch_up.med)}: "
                               f"insatsen belastas med {share} % av posten (medel), de år av "
                               "livslängden som ryms till och med målåret")
                else:
                    source = " (nyttans sista år)" if drv.catch_up_from else ""
                    timing += (f", ikapp-år {_show_year(drv.catch_up.med)}{source}: insatsen "
                               f"belastas med {share} % av posten (medel), de år av "
                               "livslängden som kom tidigare")
    else:
        timing = (f"ramp {drv.ramp.start_year}–{drv.ramp.full_effect_year} "
                  f"({drv.ramp.profile})")
        if drv.ramp.first_year_share_used:
            timing += f", verkar {_num(drv.ramp.first_year_share * 100)} % av {drv.ramp.start_year}"
        if drv.ramp.last_year_share is not None and drv.ramp.end_year is not None:
            ends = [f"{_num(drv.ramp.last_year_share.get(sc) * 100)} % av {drv.ramp.end_year.get(sc)}"
                    if drv.ramp.last_year_share_applies(drv.ramp.end_year.get(sc), sc) else "helt"
                    for sc in ('min', 'med', 'max')]
            if any(e != "helt" for e in ends):
                timing += (f", sista året verkar {ends[0]}" if len(set(ends)) == 1
                           else f", sista året verkar {' / '.join(ends)} (min / medel / max)")
        if drv.ramp.half_life is not None:
            timing += f", avklingning med halveringstid {_years(drv.ramp.half_life)}"
        if drv.write_off:
            timing += (f"; livslängd {_years(drv.lifetime)}, varje års tillverkning skrivs av "
                       "jämnt över livslängden")
    extra = ""
    if not _is_one(drv.attribution):
        extra += f"; attribution {_band(drv.attribution)}"
    if drv.grant_year is not None:
        extra += f"; köpt med bidragsår {drv.grant_year}"
    if drv.pot is not None:
        extra += f"; utsläppspott {drv.pot}"
    scaled = (f" (räknat som {_qty(drv.a0 * drv.a0_scale, drv.a0_scale_unit)})"
              if drv.a0_scale != 1.0 else "")
    ef_scaled = (f" (räknat som {_sig(drv.ef0 * drv.ef0_scale, 3)} {drv.ef0_scale_unit})"
                 if drv.ef0_scale != 1.0 else "")
    return (f"A0 {_num(drv.a0)} {drv.a0_unit}".rstrip() + scaled
            + f", EF0 {_num(drv.ef0)} {drv.ef0_unit}" + ef_scaled + "; "
            f"ΔA {_band(drv.delta_a)}, ΔEF {_band(drv.delta_ef)}; "
            # The medel only: it is the one the engine uses, in all three scenarios.
            + ("" if drv.one_off else
               f"BAU-trend A {_sig(drv.g_a.med * 100, 3)} %/år, EF {_sig(drv.g_ef.med * 100, 3)} %/år; ")
            + f"klimatfaktorer territoriell {_num(drv.terr)}, konsumtion {_num(drv.cons)}, "
            f"överlapp {_num(drv.overlap)}; nuläge {drv.baseline_year}, {timing}{extra}")


def _is_one(t: Triple) -> bool:
    return t.min == t.med == t.max == 1.0


def _years(t: Triple) -> str:
    """A band of years: '2 år' or '2 år (1 till 4)'."""
    if t.min == t.med == t.max:
        return f"{_num(t.med)} år"
    return f"{_num(t.med)} år ({_num(t.min)} till {_num(t.max)})"


# --- Bärande antaganden -------------------------------------------------------
#
# The QA step used to check a result it could not weigh: every assumption got
# the same attention, and a max scenario built from every extreme at once was
# read as a plausible upper bound (klimatpsykologi: 1 024 ton). Here the engine
# moves one banded input at a time from its min to its max, the others held at
# medel, and reports how far the cumulative result moves and where the input
# says it comes from. Deterministic, so the QA and rapport steps read numbers,
# not a model's impression of which assumption matters.

_BANDED = (
    ('delta_a', "ΔA (effekt på aktiviteten)"),
    ('delta_ef', "ΔEF (effekt på emissionsfaktorn)"),
    ('attribution', "attribution"),
)
_RAMP_BANDED = (
    ('half_life', "halveringstid"),
    ('end_year', "sista år med effekt"),
)
# A one-off's timing, when it is charged for the years it brought forward.
# Shown as timing assumptions like the ramp's.
_ONE_OFF_BANDED = (
    ('lifetime', "livslängd"),
    ('catch_up', "ikapp-år"),
)
# Timing fields that sit on the driver, not on its ramp.
_DRIVER_TIMING = frozenset(f for f, _ in _ONE_OFF_BANDED)
# Where a field's origin is stated in `kallor`, when the name differs.
_KALLA_KEY = {'catch_up': 'end_year'}
# An input that alone moves the cumulative result by this share of the
# drivers' gross effect (medel, absolute values summed, so gains and costs do
# not cancel) is bearing ("bärande"). Gross rather than net: Testcyklisterna's
# net came out near zero because a campaign's gain and its purchases cancelled,
# and a quarter of near zero flagged every input in the analysis.
BEARING_SHARE = 0.25
# A driver whose share of the result is at least this makes its a0 and ef0
# bearing too: the result is proportional to them.
DOMINANT_SHARE = 0.5


def _cum_med(model: CalcModel) -> float:
    return sum(_driver_year(d, 'med', y).net for d in model.drivers for y in _cum_years(model))


def bearing(model: CalcModel, result: dict) -> dict:
    """One-at-a-time swings and the flags built on them.

    Returns {'items': [...], 'dominant': [...], 'unsourced': [...],
    'joint_extremes': {...} | None}. Items are sorted by size of swing."""
    import copy

    items = []
    for i, drv in enumerate(model.drivers):
        bands = [(f, label, getattr(drv, f), False) for f, label in _BANDED]
        bands += [(f, label, getattr(drv.ramp, f), True) for f, label in _RAMP_BANDED
                  if not drv.one_off]
        if drv.one_off and drv.lifetime is not None and drv.catch_up is not None:
            bands += [(f, label, getattr(drv, f), True) for f, label in _ONE_OFF_BANDED]
        elif drv.write_off:
            # Annual purchases, or a one-off without a catch-up year: the
            # lifetime alone sets how much of the manufacture a year carries.
            bands.append(('lifetime', "livslängd", drv.lifetime, True))
        for field, label, band, on_ramp in bands:
            if band is None or band.min == band.max:
                continue
            ends = []
            for v in (band.min, band.max):
                m = copy.deepcopy(model)
                target = (m.drivers[i].ramp if on_ramp and field not in _DRIVER_TIMING
                          else m.drivers[i])
                setattr(target, field, Triple(v, v, v))
                ends.append(_cum_med(m))
            kalla = drv.kallor.get(_KALLA_KEY.get(field, field))
            items.append({
                'driver': drv.name, 'field': field, 'label': label,
                'low': ends[0], 'high': ends[1], 'swing': ends[1] - ends[0],
                'ursprung': kalla.ursprung.value if kalla and kalla.ursprung else None,
                'on_ramp': on_ramp,
            })
    items.sort(key=lambda x: -abs(x['swing']))

    shares = []
    total_abs = sum(abs(d['cumulative_net']) for d in result['med']['per_driver'])
    for drv, d in zip(model.drivers, result['med']['per_driver']):
        share = abs(d['cumulative_net']) / total_abs if total_abs > 0 else 0.0
        if share >= DOMINANT_SHARE:
            shares.append({'driver': drv.name, 'share': share,
                           'a0': _origin(drv, 'a0'), 'ef0': _origin(drv, 'ef0')})

    unsourced = []
    for it in items:
        if (total_abs > 1e-9 and abs(it['swing']) >= BEARING_SHARE * total_abs
                and it['ursprung'] in (None, 'antagande')):
            unsourced.append(it)
    for d in shares:
        for f in ('a0', 'ef0'):
            if d[f] in (None, 'antagande'):
                unsourced.append({'driver': d['driver'], 'field': f, 'dominant': d['share']})

    joint = None
    if len(items) >= 2:
        hi = result['max']['total']['cumulative_net']
        best_single = max(max(it['high'], it['low']) for it in items)
        if hi > best_single + 1e-9:
            joint = {'n': len(items), 'max': hi, 'best_single': best_single}
    return {'items': items, 'dominant': shares, 'unsourced': unsourced,
            'joint_extremes': joint}


def _origin(drv: Driver, field: str) -> str | None:
    k = drv.kallor.get(field)
    return k.ursprung.value if k and k.ursprung else None


_URSPRUNG_LABEL = {'parameterbibliotek': "parameterbiblioteket", 'kommundata': "kommunens data",
                   'extern': "extern källa", 'antagande': "antagande", None: "ingen källa angiven"}
_FIELD_LABEL = {'a0': "aktiviteten (A0)", 'ef0': "emissionsfaktorn (EF0)"}


def render_bearing(model: CalcModel, b: dict) -> list[str]:
    cum = _cum_years(model)
    lines = [f"Bärande antaganden (prövade ett i taget, övriga på medel, kumulativt netto "
             f"{cum[0]}–{cum[-1]}):"]
    if not b['items'] and not b['dominant']:
        return lines + ["  Inga antaganden har spann, så inget kan prövas ett i taget."]
    for it in b['items'][:5]:
        source = _URSPRUNG_LABEL.get(it['ursprung'], it['ursprung'])
        if it['on_ramp']:
            source = f"tidsantagande, {source}"
        lines.append(f"  - {it['driver']}, {it['label']}: från {_fmt(it['low'])} till "
                     f"{_fmt(it['high'])} ton CO2e ({source}).")
    for d in b['dominant']:
        lines.append(f"  - {d['driver']} står för {_num(d['share'] * 100)} % av resultatet, som "
                     f"är proportionellt mot dess aktivitet ({_URSPRUNG_LABEL.get(d['a0'], d['a0'])}) "
                     f"och emissionsfaktor ({_URSPRUNG_LABEL.get(d['ef0'], d['ef0'])}).")
    for u in b['unsourced']:
        what = _FIELD_LABEL.get(u['field']) or next(
            (label for f, label in _BANDED + _RAMP_BANDED + _ONE_OFF_BANDED
             if f == u['field']), u['field'])
        why = (f"Drivaren står för {_num(u['dominant'] * 100)} % av resultatet, som är "
               "proportionellt mot det talet." if 'dominant' in u
               else "Ensamt flyttar det resultatet minst en fjärdedel av drivarnas samlade "
                    "effekt, räknad utan att vinster och kostnader tar ut varandra.")
        lines.append(f"OBS: bärande antagande utan källa: {u['driver']}, {what}. {why} Pröva "
                     "det mot underlaget, eller redovisa det som det antagande det är.")
    j = b['joint_extremes']
    if j:
        # Not an OBS: with two or more bands max is always every high end at
        # once, so the line would be on nearly every analysis and teach the
        # reader to skip OBS lines. It states what max is, for QA to weigh.
        lines.append(f"Max-scenariot ({_fmt(j['max'])} ton CO2e kumulativt) förutsätter att "
                     f"alla {j['n']} antaganden med spann slår till åt det höga hållet samtidigt. "
                     f"Det enskilt mest bärande antagandet ger ensamt högst {_fmt(j['best_single'])}. "
                     "Läs max som ett ytterfall, inte som ett troligt utfall.")
    return lines


# The calculation appendix. Until 2026-09 the rapport agent wrote it by hand
# from the kalkyl text, and where its own arithmetic did not reach the
# engine's numbers it called the gap "avrundning" (the driftsmedel review,
# 2026-09-30, found several such gaps in one report). Now the engine writes it
# from the very YearResults compute() summed, the kalkyl step ends with it,
# and /api/rapport copies it into the report unchanged (caia.appendix).
APPENDIX_HEADING = "**Teknisk bilaga: Beräkningssteg**"
APPENDIX_STAMP = ("Bilagan är skriven av CAIA:s kalkylmotor ur exakt de tal som gav "
                  "resultaten, inte av språkmodellen.")
SCENARIO_LABELS = (('med', 'medel'), ('min', 'min'), ('max', 'max'))


def render_appendix(model: CalcModel, result: dict) -> str:
    """The calculation appendix: every step of every driver, scenario and year
    as the engine computed it, then the sums behind the headline numbers.

    Per-year values come from _driver_year, the function compute() sums, and
    the totals are compute()'s own, so text and numbers cannot diverge."""
    cum = _cum_years(model)
    avg = avg_years(model)
    lo_y, hi_y = avg[0], avg[-1]
    follow_up = model.mode == UPPFOLJNING
    attributed = any(not _is_one(d.attribution) for d in model.drivers)
    charged = any(d.one_off and d.lifetime is not None and d.catch_up is not None
                  and not d.write_off for d in model.drivers)
    written = any(d.write_off for d in model.drivers)
    lines = [
        APPENDIX_HEADING,
        "",
        APPENDIX_STAMP + " Talen är avrundade för visning. Summorna är räknade på "
        "oavrundade tal, så summan av de avrundade raderna kan skilja i sista decimalen.",
        "",
        "Så räknar motorn, för varje drivare, scenario och år t:",
        "- A_BAU(t) = A0 × (1 + g_A)^(t − nulägesår) och EF_BAU(t) = EF0 × (1 + g_EF)^(t − nulägesår). "
        "BAU-trenden är medelvärdet och densamma i min, medel och max.",
        "- Adoption(t) går från 0 vid rampens startår till 1 året för full effekt, enligt drivarens "
        "profil, och är 0 efter sista året med effekt när ett sådant är angivet.",
    ]
    # The method lines for the follow-up inputs appear only when a driver uses
    # them, so a potential analysis's appendix reads exactly as before.
    if any(d.ramp.half_life is not None and not d.one_off for d in model.drivers):
        lines.append("- Med avklingning halveras adoptionen för varje halveringstid som gått "
                     "efter året för full effekt: adoption × 0,5^((t − året för full effekt) / "
                     "halveringstid).")
    if any(d.ramp.first_year_share_used and not d.one_off for d in model.drivers):
        lines.append("- Under startåret multipliceras adoptionen med den andel av året som "
                     "åtgärden verkade.")
    if any(d.ramp.last_year_share is not None and d.ramp.end_year is not None and not d.one_off
           for d in model.drivers):
        lines.append("- Under slutåret multipliceras adoptionen med den andel av året som "
                     "åtgärden fortfarande verkade.")
    if any(d.one_off for d in model.drivers):
        lines.append("- En engångspost finns bara sitt eget år: A_BAU = A0 det året och 0 övriga "
                     "år, utan trend och utan ramp.")
    if any(d.a0_scale != 1.0 for d in model.drivers):
        lines.append("- Är aktiviteten angiven i en annan storlek än den utsläppsfaktorn gäller per "
                     "(ton mot kg, tusen km mot km), räknas A0 först om till faktorns enhet.")
    if any(d.ef0_scale != 1.0 for d in model.drivers):
        lines.append("- Gäller utsläppsfaktorn per ett antal enheter (per 100 km), räknas EF0 först "
                     "om till per enhet.")
    if charged:
        lines.append("- En engångspost som är utrustning, och som insatsen bara köpte tidigare än "
                     "den annars hade köpts, belastar insatsen med andelen (ikapp-år + 1 − köpår) / "
                     "livslängd, högst 1: de år av livslängden som kom tidigare tack vare pengarna.")
    if follow_up and any(d.catch_up_from == "målåret" for d in model.drivers):
        lines.append("- Nyttan räknas bara till och med målåret, och utrustning som insatsen köpte "
                     "skrivs av på samma sätt: den belastar insatsen med (målåret + 1 − köpår) / "
                     "livslängd, högst 1, när inget tidigare ikapp-år finns.")
    factors =(["attribution"] if attributed else []) + (["andel av livslängden"] if charged else [])
    lines += [
        "- E_BAU = A_BAU × EF_BAU och E_åtgärd = A_BAU × (1 + ΔA × adoption) × EF_BAU × "
        "(1 + ΔEF × adoption), omräknat från kg till ton.",
        (f"- ΔE = (E_BAU − E_åtgärd) × {' × '.join(factors)}"
         + (", där attribution är den andel av förändringen som insatsen orsakade"
            if attributed else "")
         + ". Positivt tal är minskade utsläpp." if factors else
         "- ΔE = E_BAU − E_åtgärd. Positivt tal är minskade utsläpp."),
    ]
    if written:
        lines.append(
            "- Tillverkning av utrustning med en livslängd skrivs av jämnt över livslängden. För "
            "en sådan drivare är talet ovan ΔE före avskrivning, det som köps det året, och ΔE "
            "ett år är summan av 1 / livslängd av ΔE före avskrivning för vart och ett av "
            "livslängdens år bakåt, året självt inräknat. Är livslängden inget helt antal år "
            "bär det sista året den del som återstår. En engångspost skrivs av till och med "
            "ikapp-året, när ett sådant finns. Så bär varje år en årlig andel av tillverkningen, "
            "i stället för att hela hamnar det år den köps.")
    lines += [
        "- Territoriell = ΔE × territoriell faktor, konsumtion = ΔE × konsumtionsfaktor, "
        "överlapp = det minsta av |ΔE × överlappsfaktor|, |territoriell| och |konsumtion|, med "
        "ΔE:s tecken. Netto = territoriell + konsumtion − överlapp.",
        (f"- Kumulativt är summan av netto {cum[0]}–{cum[-1]}. Medel effekt/år är samma summa "
         f"delad med {len(avg)}." if follow_up else
         f"- Kumulativt är summan av netto {cum[0]}–{cum[-1]}. Medel effekt/år är summan av netto "
         f"{lo_y}–{hi_y} delad med {len(avg)}; år utanför de åren ingår inte i medlet."),
    ]
    if not model.drivers:
        lines += ["", "Kalkylen har inga drivare, så det finns inga beräkningssteg."]
        return "\n".join(lines)

    years = sorted(set(cum) | set(avg))
    for i, drv in enumerate(model.drivers, 1):
        end_label = "ikapp-år" if drv.one_off else "sista år med effekt"
        lines += ["", f"Drivare {i}: {drv.name}", "", f"Indata: {_inputs(drv)}"
                  + (f"; {end_label} {_end_years(drv)}" if _end_years(drv) else "") + "."]
        # Escaped: a "|" in the unit added a cell to the header, and a table
        # whose header and rule disagree is shown as raw text. The backslash
        # first, or one already standing before a "|" undoes the escape.
        a_unit = (f"{drv.a0_scale_unit}, omräknat från {drv.a0_unit}" if drv.a0_scale != 1.0
                  else drv.a0_unit)
        unit = (" ({})".format(a_unit.replace("\\", "\\\\").replace("|", "\\|"))
                if a_unit else "")
        width = 13 + attributed + charged + written
        for sc, label in SCENARIO_LABELS:
            lines += [
                "",
                f"Scenario {label}:",
                "",
                f"| År | A_BAU{unit} | EF_BAU (kg CO2e/enhet) | E_BAU (ton) | Adoption | "
                "ΔA × adoption | ΔEF × adoption | E_åtgärd (ton) | "
                + ("Attribution | " if attributed else "")
                + ("Andel av livslängden | " if charged else "")
                + ("ΔE före avskrivning (ton) | " if written else "")
                + "ΔE (ton) | Territoriell | Konsumtion | Överlapp | Netto |",
                "|" + "---|" * width,
            ]
            for y in years:
                r = _driver_year(drv, sc, y)
                lines.append(
                    f"| {y} | {_sig(r.a_bau, 4)} | {_sig(r.ef_bau, 4)} | {_ton(r.e_bau)} | "
                    f"{_pct(r.adoption)} | {_pct(r.d_a)} | {_pct(r.d_ef)} | {_ton(r.e_action)} | "
                    + (f"{_pct(r.attribution)} | " if attributed else "")
                    + (f"{_pct(r.charged)} | " if charged else "")
                    + (f"{_ton(r.before_write_off)} | " if written else "")
                    + f"{_ton(r.basis)} | {_ton(r.terr)} | {_ton(r.cons)} | {_ton(r.overlap)} | "
                    f"{_ton(r.net)} |")

    lines += ["", "Summering, netto i ton CO2e (alla drivare):", ""]
    for sc, label in SCENARIO_LABELS:
        tot = result[sc]['total']
        by_year = {y: sum(_driver_year(d, sc, y).net for d in model.drivers) for y in years}
        lines.append(
            f"- Scenario {label}, kumulativt {cum[0]}–{cum[-1]}: "
            f"{' + '.join(_ton(by_year[y]) for y in cum)} = {_ton(tot['cumulative_net'])} ton CO2e.")
        lines.append(
            f"- Scenario {label}, medel effekt/år {lo_y}–{hi_y}: "
            f"({' + '.join(_ton(by_year[y]) for y in avg)}) / {len(avg)} = "
            f"{_ton(tot['avg_net'])} ton CO2e/år.")
        if follow_up:
            fy = result['followup_year']
            done = [y for y in cum if y <= fy]
            left = [y for y in cum if y > fy]
            if done:
                lines.append(f"- Scenario {label}, realiserat {_span(done[0], done[-1])}: "
                             f"{' + '.join(_ton(by_year[y]) for y in done)} = "
                             f"{_ton(tot['realised_net'])} ton CO2e.")
            if left:
                lines.append(f"- Scenario {label}, återstår {_span(left[0], left[-1])}: "
                             f"{' + '.join(_ton(by_year[y]) for y in left)} = "
                             f"{_ton(tot['remaining_net'])} ton CO2e.")
    med = result['med']['total']
    lines.append(
        f"- Scenario medel, medel effekt/år {lo_y}–{hi_y} per perspektiv: territoriell "
        f"{_ton(med['avg_terr'])}, konsumtion {_ton(med['avg_cons'])}, "
        f"netto {_ton(med['avg_net'])} ton CO2e/år.")
    if model.spend_posts:
        lines += [""] + _spend_lines(model)
    return "\n".join(lines)


def _end_years(drv: Driver) -> str:
    """ramp.end_year per scenario (a one-off's catch-up year), or '' when the
    effect runs to the target year."""
    e = drv.catch_up if drv.one_off else drv.ramp.end_year
    if e is None:
        return ""
    return (f"{_show_year(e.min)} / {_show_year(e.med)} / {_show_year(e.max)} "
            "(min / medel / max)")


def _show_year(y) -> str:
    return "ingen" if y >= UNBOUNDED_YEAR else str(int(y))


def _ton(x: float) -> str:
    """Tons in the appendix: two decimals under 10, one under 1 000, whole
    tons above, so a small measure's steps stay visible. Space thousands,
    decimal comma, and no '-0,00'."""
    places = 2 if abs(x) < 10 else 1 if abs(x) < 1000 else 0
    if round(x, places) == 0:
        x = 0.0
    return f"{x:,.{places}f}".replace(',', ' ').replace('.', ',')


def _pct(x: float) -> str:
    """A share as percent, three significant digits: '-11,2 %', '1 000 %'."""
    if abs(x) < 5e-7:
        x = 0.0
    return f"{_sig(x * 100, 3)} %"


def _sig(x: float, digits: int) -> str:
    """x with `digits` significant digits and never in exponent form: whole
    numbers with space thousands from 1000, decimal comma, no trailing zeros.
    0.0000452 -> '0,0000452', 12345.6 -> '12 346'."""
    if x == 0:
        return "0"
    places = max(0, digits - 1 - math.floor(math.log10(abs(x))))
    if abs(round(x, places)) >= 1000:
        return f"{round(x):,}".replace(',', ' ')
    s = f"{x:.{places}f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s.replace('.', ',')


def _num(x: float) -> str:
    """An input as written: whole numbers with space thousands from 1000,
    three significant digits below, decimal comma."""
    if abs(x) >= 1000:
        return f"{round(x):,}".replace(',', ' ')
    return _sig(x, 3)


def _band(t) -> str:
    """A min/med/max share as percent: '-20 % (-10 till -30)'."""
    # _sig, not '.3g': a 15-fold change came out as '1,52e+03' (tjänstebilar,
    # reference run 2026-10-01).
    pct = lambda v: _sig(v * 100, 3)  # noqa: E731
    if t.min == t.med == t.max:
        return f"{pct(t.med)} %"
    return f"{pct(t.med)} % ({pct(t.min)} till {pct(t.max)})"
