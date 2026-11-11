"""Structured numeric model for deterministic emission calculations.

The LLM (kalkyl_extract agent) produces an instance of CalcModel from the prior
free-form analysis; calc.engine then computes emissions in pure Python. This is
the boundary that moves arithmetic out of the prompt.

UNIT CONTRACT (the extraction agent must normalise to these):
- a0:  activity level per year, in whatever physical unit (km, kWh, kg, ...).
- ef0: emission factor in **kg CO2e per activity unit**.
=> baseline emissions E = a0 * ef0  (kg CO2e/year); the engine reports ton (÷1000).
- g_a, g_ef: annual fractional change of activity / EF in the BAU scenario
  (e.g. 0.01 = +1%/year, -0.02 = -2%/year).
- delta_a, delta_ef: fractional change the ACTION causes vs BAU, at full effect
  (negative = reduction; e.g. -0.10 = 10% less activity).
- terr / cons / overlap: climate factors in [0, 1]. overlap <= min(terr, cons).
  Driver.from_dict refuses values that can only be unit slips (see there).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum

from ..mode import POTENTIAL, UPPFOLJNING, mode_of
from . import units

_TAG_OPEN = re.compile(r'<(?=[A-Za-z/!?])')


def plain(value) -> str:
    """A name, unit or source note from the extraction, as one line of text.

    The program writes these strings into its own sections (the kalkyl text,
    the appendix, Talens ursprung), and they come from a model that has read
    whatever the user pasted. A line break in a driver name put a line of the
    name's own making among the program's, "<!--" hid the rest of the
    appendix, and "[text](address)" set a link in the table of sources
    (re-review 2026-10-07). So: one line, no opening of an HTML tag or
    comment, no link. "< 3,5 ton" and a bare address stay as they are."""
    text = ' '.join(str(value).split())
    return _TAG_OPEN.sub('‹', text).replace('](', '] (').replace('][', '] [')

# --- Källmarkering: where each input number comes from -----------------------
#
# Göteborg's question (2026-09-23): which numbers did the analysis find
# itself, outside the parameter library? Every input that sets the size of the
# effect carries a typed origin. The extraction agent states it; the check
# against the library lives in caia.kallmarkering, and a missing or unparseable
# origin is kept as None so the report can say so instead of guessing.

class Ursprung(str, Enum):
    PARAMETERBIBLIOTEK = "parameterbibliotek"  # a row in the profile's parameter library
    KOMMUNDATA = "kommundata"                  # the municipality's own value or data file
    EXTERN = "extern"                          # a named outside source (study, report, web page)
    ANTAGANDE = "antagande"                    # the analysis' own judgement


# The inputs that set the size of the effect. Climate factors (terr/cons/
# overlap) follow the method's rules and the ramp is a timetable, so they are
# method choices rather than data and carry no origin of their own.
KALLFALT = ("a0", "ef0", "g_a", "g_ef", "delta_a", "delta_ef")
# Inputs that only exist when the analysis sets them (follow-up mode). They
# carry an origin like the rest, and källmarkering asks for one only when the
# value differs from the neutral default.
VALFRIA_KALLFALT = ("attribution",)
# Timing assumptions. Källmarkering does not check them (no library holds a
# half-life), but the bearing check reads their origin, so a sourced decay,
# catch-up year or lifetime is not flagged as unsourced. A one-off's catch-up
# year has its origin under "end_year", like the ramp's.
RAMP_KALLFALT = ("half_life", "end_year", "lifetime")

_URSPRUNG_ALIAS = {
    "parameterbibliotek": Ursprung.PARAMETERBIBLIOTEK,
    "parameterbiblioteket": Ursprung.PARAMETERBIBLIOTEK,
    "bibliotek": Ursprung.PARAMETERBIBLIOTEK,
    "biblioteket": Ursprung.PARAMETERBIBLIOTEK,
    "kommundata": Ursprung.KOMMUNDATA,
    "kommunens data": Ursprung.KOMMUNDATA,
    "lokal data": Ursprung.KOMMUNDATA,
    "extern": Ursprung.EXTERN,
    "extern källa": Ursprung.EXTERN,
    "antagande": Ursprung.ANTAGANDE,
}


def ursprung_of(v) -> Ursprung | None:
    """The origin a label names, or None when it names none of the four."""
    if isinstance(v, Ursprung):
        return v
    return _URSPRUNG_ALIAS.get(str(v or "").strip().lower())


@dataclass(frozen=True)
class Kalla:
    """Where one input number comes from, as the extraction stated it.

    `ursprung` is None when the stated label was missing or not one of the four;
    `angivet` keeps what was written so the report can show it."""
    ursprung: Ursprung | None
    parametrar: tuple[str, ...] = ()  # library Parameter_IDs or data-register names
    kalla: str = ""                   # named outside source, e.g. report + URL
    not_: str = ""                    # how the number was derived from the above
    angivet: str = ""

    @classmethod
    def of(cls, v) -> Kalla | None:
        """Lenient: a malformed entry becomes an origin-less Kalla or None,
        never an exception. Källmarkering must not be able to stop the calc."""
        if isinstance(v, Kalla):
            return v
        if isinstance(v, str) and v.strip():
            return cls(ursprung=ursprung_of(v), angivet=plain(v))
        if not isinstance(v, dict):
            return None
        label = v.get("ursprung")
        params = v.get("parametrar", v.get("parameter_ids", ()))
        if isinstance(params, str):
            params = [p for p in params.replace(";", ",").split(",")]
        if not isinstance(params, (list, tuple)):
            params = ()
        return cls(
            ursprung=ursprung_of(label),
            parametrar=tuple(plain(p) for p in params if plain(p)),
            kalla=plain(v.get("kalla") or v.get("källa") or ""),
            not_=plain(v.get("not") or v.get("anmarkning") or ""),
            angivet=plain(label or ""),
        )


def kallor_of(v) -> dict[str, Kalla]:
    """Parse a driver's `kallor` object: field name -> Kalla. Unknown fields
    and malformed entries are dropped; the check reports what is missing."""
    if not isinstance(v, dict):
        return {}
    out: dict[str, Kalla] = {}
    for key in KALLFALT + VALFRIA_KALLFALT + RAMP_KALLFALT:
        k = Kalla.of(v.get(key))
        if k is not None:
            out[key] = k
    return out


# An emission pot's id in the kommunprofil's register (potter.toml): small
# letters, digits, - and _. It is written into the appendix and read back by
# the portfolio, so it is held to a form that cannot break a line.
POT_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,40}$')


def pot_id_of(v) -> str | None:
    """A driver's pot, or None. Not a number, so nothing is refused over it:
    a malformed id is dropped (the driver counts on its own) rather than
    sending a computed result down the LLM fallback."""
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if POT_ID.match(v) else None


@dataclass
class Triple:
    """A min/med/max (or low/med/high) band. Used for BAU trends and action effects."""
    min: float
    med: float
    max: float

    @classmethod
    def of(cls, v) -> Triple:
        if isinstance(v, Triple):
            return v
        if isinstance(v, dict):
            # accept {min,med,max}, {low,med,high} or Swedish {min,medel,max}
            mid = v.get('med', v.get('medel'))
            lo = v.get('min', v.get('low', mid))
            hi = v.get('max', v.get('high', mid))
            # A band without a middle used to become med=0.0 silently, and the
            # engine reads ONLY .med for the BAU trend and the headline scenario
            # — so the whole result zeroed while min/max still looked sane.
            # Fall back to the midpoint of the band instead.
            if mid is None:
                if lo is None and hi is None:
                    raise ValueError(f"Triple saknar användbara värden: {v!r}")
                mid = (float(lo) + float(hi)) / 2.0 if lo is not None and hi is not None \
                    else (lo if lo is not None else hi)
            lo = mid if lo is None else lo
            hi = mid if hi is None else hi
            return cls(float(lo), float(mid), float(hi))
        f = float(v)
        return cls(f, f, f)

    def get(self, scenario: str) -> float:
        return {'min': self.min, 'med': self.med, 'max': self.max}[scenario]


# "No catch-up year" for a scenario: a year the engine never reaches.
UNBOUNDED_YEAR = 9999

# The years an analysis can be about. A year outside them is a slip ("24" for
# 2024, an amount in a year field) or an attack. The engine walks every year
# from the first start year to the target year and writes a table row for
# each, so nothing bounded the work: target_year 2 000 000 held a worker for
# minutes on one counted request, and start_year 24 gave a headline of 10^15
# ton without a warning (review 2026-11-10). The range is wide on purpose: it
# refuses what no analysis means, not long horizons.
YEAR_MIN, YEAR_MAX = 1950, 2200


def in_years(year: int, what: str) -> int:
    """`year` if it is a year an analysis can be about, else ValueError that
    names the field. A bool is refused too: int(True) is 1."""
    if isinstance(year, bool) or not YEAR_MIN <= year <= YEAR_MAX:
        raise ValueError(f"{what}={year} ligger utanför {YEAR_MIN} till {YEAR_MAX}. "
                         "Ett årtal skrivs med fyra siffror.")
    return year


def end_year_of(v) -> Triple | None:
    """Parse ramp.end_year, where a missing scenario means "unbounded".

    Triple.of fills a missing min/max from med, which is right for a band of
    effects but wrong here: an extractor that writes {"med": 2028} means "BAU
    catches up in 2028 in the middle scenario" and says nothing about min or
    max. Filling them from med would cap all three scenarios at the same year
    and quietly delete the spread that end_year exists to express, without
    tripping the min = max warning (delta spread keeps them apart)."""
    if v is None:
        return None
    if isinstance(v, Triple):
        return v
    if isinstance(v, dict):
        def pick(*keys):
            for k in keys:
                if v.get(k) is not None:
                    return _end_year(v[k])
            return UNBOUNDED_YEAR
        t = Triple(pick('min', 'low'), pick('med', 'medel'), pick('max', 'high'))
        if t.min == t.med == t.max == UNBOUNDED_YEAR:
            return None
        return t
    y = _end_year(v)
    return Triple(y, y, y)


def _end_year(v) -> int:
    """One scenario's end year. Only the lower bound is checked: the engine
    never walks to an end year, and one far away says "never", which is what
    a missing one says. An end year of 28 for 2028 ended the effect before it
    began and gave a zero without a word."""
    y = int(v)
    if isinstance(v, bool) or y < YEAR_MIN:
        raise ValueError(f"ramp.end_year={v} ligger före {YEAR_MIN}. "
                         "Ett årtal skrivs med fyra siffror.")
    return y


_KIND_ALIAS = {
    "årlig": "årlig", "arlig": "årlig", "löpande": "årlig", "annual": "årlig",
    "engång": "engång", "engang": "engång", "engångspost": "engång",
    "engangspost": "engång", "one_off": "engång", "one-off": "engång",
}


def kind_of(v) -> str:
    """A driver's kind: "årlig" (default) or "engång". Raises on anything
    else, so a misspelt one-off is never silently summed every year."""
    if v is None or str(v).strip() == "":
        return "årlig"
    kind = _KIND_ALIAS.get(str(v).strip().lower())
    if kind is None:
        raise ValueError(f"Okänd drivartyp {v!r}; ska vara \"årlig\" eller \"engång\".")
    return kind


@dataclass
class Ramp:
    """Implementation ramp-up. adoption(t) goes 0 -> 1 between the two years."""
    start_year: int
    full_effect_year: int
    profile: str = "linjär"  # linjär | s-formad | stegvis (step, stepwise read as stegvis)
    # Ex-post evaluation: the year after which BAU has caught up and the
    # action no longer makes a difference (e.g. a fleet that a 2026 fossil-free
    # target would have electrified anyway). Scenario-specific because "when
    # would it have happened without the money" IS the main uncertainty of an
    # ex-post counterfactual, and the engine keeps BAU itself shared across
    # scenarios. None = the effect persists to the target year (default).
    end_year: Triple | None = None
    # Decay (avklingning): after full effect the effect halves every
    # half_life years, per scenario. A campaign or a course does not keep
    # working at full strength and then stop; without this the engine could
    # only express it as a plateau and a cliff (the driftsmedel review,
    # 2026-09-30). None = no decay (default, as before).
    half_life: Triple | None = None
    # Share of the start year the action works, for a measure that began
    # mid-year (April = 0.75). Applies to the start year only. 1.0 = the whole
    # year (default, as before).
    first_year_share: float = 1.0
    # Share of the end year the action still works, per scenario, for an
    # effect that stops mid-year (a campaign replaced by next year's on 13 May
    # = 0.36). Applies in end_year only, and not when that is also the start
    # year (first_year_share already says how much of it). Without it an
    # extractor holding "slutårsandel 0,36" had nowhere to put it and counted
    # the whole end year (klimatmånaden, 2026-10-23: about 20 t too much).
    last_year_share: Triple | None = None

    def adoption(self, year: int, scenario: str = "med") -> float:
        if self.end_year is not None and year > self.end_year.get(scenario):
            return 0.0
        share = self.first_year_share if year == self.start_year else 1.0
        if self.last_year_share_applies(year, scenario):
            share *= self.last_year_share.get(scenario)
        if year >= self.full_effect_year:
            return share * self._decay(year, scenario)
        return share * self._ramp_up(year)

    @property
    def first_year_share_used(self) -> bool:
        """The share only changes anything when full effect comes at once: a
        ramp is already 0 in its start year, so a share of it is still 0."""
        return self.first_year_share != 1.0 and self.full_effect_year == self.start_year

    def last_year_share_applies(self, year: int, scenario: str) -> bool:
        if self.last_year_share is None or self.end_year is None:
            return False
        end = self.end_year.get(scenario)
        return year == end != UNBOUNDED_YEAR and year != self.start_year

    def _decay(self, year: int, scenario: str) -> float:
        if self.half_life is None or year <= self.full_effect_year:
            return 1.0
        return 0.5 ** ((year - self.full_effect_year) / self.half_life.get(scenario))

    def _ramp_up(self, year: int) -> float:
        """Share of full effect in a year before full_effect_year."""
        if year >= self.full_effect_year:
            return 1.0
        if year <= self.start_year:
            return 0.0
        span = self.full_effect_year - self.start_year
        if span <= 0:
            return 1.0
        frac = (year - self.start_year) / span
        # The prompts write 'Stegvis' and 'S-formad' with a capital letter, so
        # matching the raw string sent every non-linear profile silently down
        # the linear branch.
        profile = (self.profile or "").strip().lower()
        # English too: "step" began with an s, not with "steg", and went down
        # the S-curve branch (4,7 / 50 / 95 % instead of 0 / 100 / 100 over a
        # ramp 2026-2030; the review after 1.0.0, Henric 2026-11-10).
        if profile.startswith(('steg', 'step')):
            # Stepwise: the effect lands as one discrete jump at the midpoint of
            # the ramp. The old `frac >= 1.0` was unreachable (the guard above
            # already returned for year >= full_effect_year), so a stepwise
            # driver contributed exactly nothing for the whole ramp period.
            return 1.0 if frac >= 0.5 else 0.0
        if profile.startswith('s'):  # logistic S-curve centred on the midpoint
            import math
            x = (frac - 0.5) * 12.0
            return 1.0 / (1.0 + math.exp(-x))
        return frac  # linjär (default)


@dataclass
class Driver:
    name: str
    baseline_year: int
    a0: float
    ef0: float
    ramp: Ramp
    a0_unit: str = ""
    ef0_unit: str = "kg CO2e/enhet"
    g_a: Triple = field(default_factory=lambda: Triple(0.0, 0.0, 0.0))
    g_ef: Triple = field(default_factory=lambda: Triple(0.0, 0.0, 0.0))
    delta_a: Triple = field(default_factory=lambda: Triple(0.0, 0.0, 0.0))
    delta_ef: Triple = field(default_factory=lambda: Triple(0.0, 0.0, 0.0))
    terr: float = 1.0
    cons: float = 0.0
    overlap: float = 0.0
    kallor: dict[str, Kalla] = field(default_factory=dict)
    # Share of the change this action caused, per scenario (follow-up mode:
    # "what did these particular kronor cause"). Applied to ΔE before the
    # climate factors. It used to exist only folded into delta, where it could
    # be forgotten (tjänstecyklar: never applied to driver 2) or applied twice
    # (baljväxter). 1 = the action caused all of it (default, as before).
    attribution: Triple = field(default_factory=lambda: Triple(1.0, 1.0, 1.0))
    # "årlig": a yearly rate, as before. "engång": a one-off quantity in the
    # ramp's start year only (manufacturing a battery, a one-time purchase),
    # with a0 = the quantity, ef0 = kg CO2e per unit and no BAU trend.
    kind: str = "årlig"
    # Follow-up of a measure funded over several years: the grant year that
    # paid for exactly this driver. None = paid by all grant years together.
    grant_year: int | None = None
    # The emission pot (caia.calc.portfolj) this driver works on: an id from
    # the kommunprofil's register. Only a portfolio reads it, to combine the
    # actions that share a pot instead of adding them. None = not marked, and
    # a portfolio counts the driver on its own, as before.
    pot: str | None = None
    # A one-off that is equipment: its lifetime in years and the year BAU had
    # caught up (the last year the benefit counts), per scenario. When the
    # money only brought the purchase forward, the action is charged for the
    # years of the lifetime it brought forward, not the whole manufacture
    # (the review of driftsmedel runs 1 and 2, 2026-10-22: energivisualisering
    # charged 1,25 ton of screens in full against a benefit that stops in
    # 2027). None = charged in full, as before.
    lifetime: Triple | None = None
    catch_up: Triple | None = None
    # Where catch_up came from: "" the analysis set it, "nyttan" the engine
    # took the latest end year among the drivers that lower emissions.
    catch_up_from: str = ""
    # Potential mode: a driver that manufactures equipment with a lifetime
    # (annual purchases or a one-off) is written off evenly over the lifetime,
    # so each year carries a yearly share of the manufacture instead of the
    # purchase year carrying all of it (Henric 2026-11-10, CAIA 1.1). Set by
    # CalcModel.from_dict, see write_off_in_potential; the engine spreads it
    # (engine._driver_year). False = charged the year it is bought, as before.
    write_off: bool = False
    # A0 × a0_scale is in the unit EF0 is per (210 ton against kg CO2e/kg:
    # 1000; 500 tusen km against kg CO2e/km: 1000), and a0_scale_unit is that
    # unit's word. EF0 × ef0_scale is per one of it (15 kg CO2e per 100 km:
    # 0,01), and ef0_scale_unit is EF0's unit after it. Set from the units as
    # written (calc.units.conversion). 1 = no conversion, as before.
    a0_scale: float = 1.0
    a0_scale_unit: str = ""
    a0_scale_from: str = ""
    ef0_scale: float = 1.0
    ef0_scale_unit: str = ""
    # The attribution band as the extraction wrote it, when the engine turned
    # it the right way round (see orient_attribution). None = not turned.
    attribution_given: Triple | None = None
    # ΔA and ΔEF as the extraction wrote them, when the engine rewrote a
    # one-off cost that came out as a benefit (see unflip_cost). None = as
    # written.
    flip_given: tuple[Triple, Triple] | None = None

    @property
    def one_off(self) -> bool:
        return self.kind == "engång"

    def direction(self, scenario: str = 'med') -> int:
        """+1 when the driver raises emissions in the scenario (medel unless
        named), -1 when it lowers them, 0 when it does neither: the sign of
        the change (1 + ΔA)(1 + ΔEF) − 1 at full effect."""
        f = (1.0 + self.delta_a.get(scenario)) * (1.0 + self.delta_ef.get(scenario)) - 1.0
        return (f > 1e-12) - (f < -1e-12)

    def charged_share(self, scenario: str) -> float:
        """The share of a one-off the action is charged with: the years of
        the lifetime that came before BAU caught up, (catch-up year + 1 −
        purchase year) / lifetime, between 0 and 1. 1 without a lifetime and
        a catch-up year, or when BAU never catches up in this scenario. 1 for
        a driver that is written off (write_off): the engine spreads its
        charge over the years instead, up to the catch-up year."""
        # Costs only: an avoided purchase is a benefit, and how much of it a
        # brought-forward action earns is not what this share measures.
        if (not self.one_off or self.write_off or self.lifetime is None
                or self.catch_up is None or self.direction() <= 0):
            return 1.0
        cu = self.catch_up.get(scenario)
        if cu >= UNBOUNDED_YEAR:
            return 1.0
        years = cu + 1 - self.ramp.start_year
        return min(1.0, max(0.0, years / self.lifetime.get(scenario)))

    def orient_attribution(self) -> None:
        """Turn the attribution band of a driver that lowers emissions so that
        min has the lowest share.

        min is the cautious scenario. For a driver that raises emissions the
        cautious case is the highest share, and the prompt said so; but the
        extraction carried the inverted band over to drivers that lower them
        (klimatkrav i anläggning, run 1: "15 % (30 till 5)" on drivmedel and
        transporter), which pulls the scenarios together or out of order. The
        values are kept; only which scenario gets which is corrected, and the
        band as written is kept for the warning. A driver that raises
        emissions is left as written: its band may be its own (inverted) or
        the same as the benefit it follows from. So is one that raises them
        in one scenario and lowers them in another: two one-offs in run 2 (a
        study trip, cargo bikes) were costs whose ΔEF shrank them into a
        "reduction" in medel, and which way their band should go cannot be
        read off them."""
        a = self.attribution
        if all(self.direction(sc) < 0 for sc in ('min', 'med', 'max')) and a.min > a.max:
            self.attribution_given = a
            self.attribution = Triple(a.max, a.med, a.min)

    def unflip_cost(self) -> None:
        """Count a one-off that adds a quantity as that quantity at its own
        factor, never as more of the post at a lower factor.

        A one-off's a0 is the quantity bought or made. Written as ΔA > 0 with
        ΔEF < 0, the lower factor falls on the whole post, BAU's part
        included, so (1 + ΔA)(1 + ΔEF) − 1 shrinks the cost and can turn it
        into a benefit. The review of driftsmedel omgång 3 (2026-10-22): the
        återbrukscontainer's own containers counted as 3,4 ton saved, and the
        energivisualisering's screens the same way on a smaller scale. A cost
        never becomes a benefit: the added part, ΔA × (1 + ΔEF), is the
        quantity, at the factor ef0, per scenario. An attribution band the
        engine turned for a benefit goes back as written, since the post is a
        cost."""
        if not self.one_off:
            return
        da, de = self.delta_a, self.delta_ef
        a_new, e_new = [], []
        for sc in ('min', 'med', 'max'):
            a, e = da.get(sc), de.get(sc)
            if a > 0 and e < 0:
                a, e = a * (1.0 + e), 0.0
            a_new.append(a)
            e_new.append(e)
        if a_new == [da.min, da.med, da.max] and e_new == [de.min, de.med, de.max]:
            return
        self.flip_given = (da, de)
        self.delta_a, self.delta_ef = Triple(*a_new), Triple(*e_new)
        if self.attribution_given is not None:
            self.attribution, self.attribution_given = self.attribution_given, None

    @classmethod
    def from_dict(cls, d: dict) -> Driver:
        """Build a driver from extracted JSON.

        Missing fields used to default to zero and the result was still handed
        back labelled `deterministic: True`. That is the worst combination the
        tool can produce: a confident zero. The extraction prompt itself says
        never to set a0 or ef0 to zero, so a zero here means extraction failed,
        not that the activity is zero.

        terr and cons are required rather than defaulted for the same reason.
        The old defaults (terr=1.0, cons=0.0) quietly declared every measure
        purely territorial, which zeroes the consumption column in a report
        that is supposed to show territorial, consumption and net side by side.

        Raising is the intended behaviour: /api/kalkyl catches it and falls
        back to the LLM math path, which reports deterministic: False.

        Overlap is required for the same reason as terr and cons: defaulting
        it to 0 counted a car measure (terr = cons = 1) twice.

        The range checks catch unit slips, not method choices. A delta of
        -10 is "-10 %" written as a number: it made the activity negative
        and the headline a hundred times too large, with no warning. The
        bounds are wide on purpose (the method's own ranges, such as terr and
        cons in [0, 1], are the prompts' business, and the evidens prompt
        allows cons 1.2); only values no reading of the method allows fail.
        """
        name = plain(d.get('name', 'drivare'))
        for key in ('a0', 'ef0'):
            if d.get(key) is None:
                raise ValueError(f"Drivare {name!r} saknar {key}")
            if not (math.isfinite(float(d[key])) and float(d[key]) > 0):
                raise ValueError(f"Drivare {name!r} har {key}={d[key]}, måste vara > 0")
        for key in ('terr', 'cons', 'overlap'):
            if d.get(key) is None:
                raise ValueError(
                    f"Drivare {name!r} saknar klimatfaktorn {key}; "
                    "den får inte gissas åt analysen")

        r = d.get('ramp') or {}
        kind = kind_of(d.get('kind', d.get('typ')))
        start = int(r.get('start_year', d.get('baseline_year', 2023)))
        full = int(r.get('full_effect_year', d.get('target_year', 2030)))
        if kind == "engång":
            # One year, whole: the event year is the start year, nothing ramps.
            start = full = int(d.get('year', d.get('ar', start)))
        # The start year (a one-off's year) is where the engine starts
        # walking. The full-effect year has no upper bound: the engine never
        # walks to it, and "9999" there is an extraction saying full effect
        # never comes, which is computed and noted (test_calc_golden).
        start = in_years(start, f"Drivare {name!r}: "
                         + ("year" if kind == "engång" else "ramp.start_year"))
        if kind == "engång":
            full = start
        half_life = r.get('half_life', r.get('halveringstid'))
        share = r.get('first_year_share', r.get('andel_forsta_aret'))
        last_share = r.get('last_year_share', r.get('andel_sista_aret'))
        grant_year = d.get('grant_year', d.get('bidragsar'))
        # The catch-up year belongs to a one-off (equipment): an annual
        # driver's is ramp.end_year. The lifetime is read for both, as an
        # annual driver that manufactures equipment is written off over it
        # in potential mode; a follow-up drops it there again
        # (CalcModel.from_dict), as its end year is the lifetime.
        lifetime = catch_up = None
        # Optional, so a value that cannot be read ("5 år", [5]) is dropped
        # rather than refused: refusing sends the whole kalkyl to the language
        # model's fallback. The warning about a one-off without a lifetime
        # then says what is missing.
        try:
            lifetime = d.get('lifetime', d.get('livslangd', d.get('livslängd')))
            lifetime = None if lifetime is None else Triple.of(lifetime)
        except (TypeError, ValueError):
            lifetime = None
        if (kind != "engång" and lifetime is not None
                and not all(math.isfinite(v) and v > 0 for v in (lifetime.min, lifetime.med, lifetime.max))):
            # A one-off's lifetime has been checked since 2026-10; on an annual
            # driver it is new in 1.1 and only spreads a charge, so a value
            # that is no number of years is dropped, not refused.
            lifetime = None
        if kind == "engång":
            try:
                catch_up = end_year_of(r.get('end_year', d.get('end_year')))
            except (TypeError, ValueError):
                catch_up = None
        drv = cls(
            name=name,
            baseline_year=in_years(int(d.get('baseline_year', 2023)),
                                   f"Drivare {name!r}: baseline_year"),
            a0=float(d['a0']),
            ef0=float(d['ef0']),
            a0_unit=plain(d.get('a0_unit', '')),
            ef0_unit=plain(d.get('ef0_unit', 'kg CO2e/enhet')),
            ramp=Ramp(
                start_year=start,
                full_effect_year=full,
                profile=plain(r.get('profile', 'linjär')),
                end_year=None if kind == "engång" else end_year_of(r.get('end_year')),
                half_life=(None if kind == "engång" or half_life is None
                           else Triple.of(half_life)),
                first_year_share=1.0 if kind == "engång" or share is None else float(share),
                last_year_share=(None if kind == "engång" or last_share is None
                                 else Triple.of(last_share)),
            ),
            g_a=Triple.of(d.get('g_a', 0.0)),
            g_ef=Triple.of(d.get('g_ef', 0.0)),
            delta_a=Triple.of(d.get('delta_a', 0.0)),
            delta_ef=Triple.of(d.get('delta_ef', 0.0)),
            terr=float(d['terr']),
            cons=float(d['cons']),
            overlap=float(d['overlap']),
            kallor=kallor_of(d.get('kallor')),
            # null is absent, as for every other optional field.
            attribution=Triple.of(1.0 if d.get('attribution') is None else d['attribution']),
            kind=kind,
            grant_year=(None if grant_year in (None, "")
                        else in_years(int(grant_year), f"Drivare {name!r}: grant_year")),
            pot=pot_id_of(d.get('pot', d.get('pott'))),
            lifetime=lifetime,
            catch_up=catch_up,
        )
        drv._check_ranges()
        # A fault in the unit reading must not cost the calculation: the
        # warning step reports the same check failing (engine.sanity_warnings).
        try:
            conv = units.conversion(drv.a0_unit, drv.ef0_unit)
        except Exception:  # noqa: BLE001
            conv = None
        if conv is not None:
            if conv['a0_factor'] != 1.0:
                drv.a0_scale, drv.a0_scale_unit = conv['a0_factor'], conv['a0_to']
                drv.a0_scale_from = conv['a0_from']
            if conv['ef0_factor'] != 1.0:
                drv.ef0_scale, drv.ef0_scale_unit = conv['ef0_factor'], conv['ef0_to']
        drv.orient_attribution()
        return drv

    def _check_ranges(self) -> None:
        def bad(what: str) -> ValueError:
            return ValueError(f"Drivare {self.name!r}: {what}")

        for key in ('delta_a', 'delta_ef'):
            band = getattr(self, key)
            for sc in ('min', 'med', 'max'):
                v = band.get(sc)
                if not (math.isfinite(v) and v >= -1.0):
                    raise bad(f"{key}.{sc}={v} är mindre än -1 (mer än -100 %). "
                              "Andelar skrivs som -0.10, inte -10.")
        for key in ('g_a', 'g_ef'):
            band = getattr(self, key)
            for sc in ('min', 'med', 'max'):
                v = band.get(sc)
                if not -1.0 < v <= 1.0:
                    raise bad(f"{key}.{sc}={v} ligger utanför (-1, 1] per år. "
                              "Årlig förändring skrivs som 0.02, inte 2.")
        for key in ('terr', 'cons', 'overlap'):
            v = getattr(self, key)
            if not 0.0 <= v <= 2.0:
                raise bad(f"{key}={v} ligger utanför [0, 2]; klimatfaktorer är andelar.")
        if self.ramp.full_effect_year < self.ramp.start_year:
            raise bad(f"rampen når full effekt {self.ramp.full_effect_year}, "
                      f"före start {self.ramp.start_year}.")
        for sc in ('min', 'med', 'max'):
            v = self.attribution.get(sc)
            if not 0.0 <= v <= 1.0:
                raise bad(f"attribution.{sc}={v} ligger utanför [0, 1]; den är en andel, "
                          "0.6 och inte 60.")
        if self.ramp.half_life is not None:
            for sc in ('min', 'med', 'max'):
                v = self.ramp.half_life.get(sc)
                if not (math.isfinite(v) and v > 0):
                    raise bad(f"ramp.half_life.{sc}={v}; halveringstiden är ett antal år > 0.")
        if not 0.0 < self.ramp.first_year_share <= 1.0:
            raise bad(f"ramp.first_year_share={self.ramp.first_year_share} ligger utanför "
                      "(0, 1]; den är andelen av startåret som åtgärden verkar.")
        if self.ramp.last_year_share is not None:
            for sc in ('min', 'med', 'max'):
                v = self.ramp.last_year_share.get(sc)
                if not (math.isfinite(v) and 0.0 < v <= 1.0):
                    raise bad(f"ramp.last_year_share.{sc}={v} ligger utanför (0, 1]; den är "
                              "andelen av slutåret (ramp.end_year) som åtgärden verkar.")
        if self.lifetime is not None:
            for sc in ('min', 'med', 'max'):
                v = self.lifetime.get(sc)
                if not (math.isfinite(v) and v > 0):
                    raise bad(f"lifetime.{sc}={v}; livslängden är ett antal år > 0.")


@dataclass
class CalcModel:
    action_name: str
    drivers: list[Driver]
    target_year: int = 2030
    key_years: list[int] = field(default_factory=lambda: [2026, 2030])
    # Set by the caller from the request, never by the extraction: the mode
    # decides which years the engine sums, so it must not be a model's guess.
    mode: str = POTENTIAL
    # Follow-up: the last year counted as realised. Later years are what the
    # measure is still expected to give. None = the last start year.
    followup_year: int | None = None
    # Follow-up of a measure funded over several years: what each year used.
    grants: list[Grant] = field(default_factory=list)
    # Follow-up: posts that count the grant's own emissions (an amount in
    # kronor × kg CO2e per krona). They are not part of the result; the
    # kalkyl shows them on their own row (see spend_post_of).
    spend_posts: list[Driver] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict, mode: str = POTENTIAL) -> CalcModel:
        target = in_years(int(d.get('target_year', 2030)), "target_year")
        for drv in d.get('drivers', []):
            drv.setdefault('target_year', target)
        fy = d.get('followup_year', d.get('uppfoljningsar'))
        mode = mode_of(mode)
        drivers = [Driver.from_dict(x) for x in d.get('drivers', [])]
        spend: list[Driver] = []
        if mode == UPPFOLJNING:
            for x in drivers:
                x.unflip_cost()
            spend = [x for x in drivers if is_spend_post(x)]
            drivers = [x for x in drivers if not is_spend_post(x)]
            for x in drivers:
                # An annual driver's lifetime in a follow-up is its end year.
                if not x.one_off:
                    x.lifetime = None
        else:
            drop_same_year_catch_up(drivers)
        infer_catch_up(drivers)
        if mode == UPPFOLJNING:
            write_off_to(drivers, target)
        else:
            write_off_in_potential(drivers)
        return cls(
            action_name=plain(d.get('action_name', 'Namnlös åtgärd')),
            target_year=target,
            key_years=[in_years(int(y), "key_years") for y in d.get('key_years', [2026, target])],
            drivers=drivers,
            mode=mode,
            followup_year=None if fy in (None, "") else in_years(int(fy), "followup_year"),
            grants=grants_of(d.get('grants', d.get('bidrag'))),
            spend_posts=spend,
        )


# "Pengarnas egna utsläpp": the grant amount × kg CO2e per krona, counted as
# an emission the action caused. It turned up in 4-5 of about 20 driftsmedel
# analyses and differently between the two runs (krisberedskap 204 935 kr ×
# 0,04 = −4,1 ton). The money would have been spent by the municipality
# anyway, so in a follow-up such a post is not a driver: the engine takes it
# out of the result, and shows it on its own row with at most this factor, a
# service-heavy spend factor (the review of 2026-10-22).
SPEND_EF_PER_KR = 0.012


def is_spend_post(drv: Driver) -> bool:
    """A driver that counts money as the activity and raises emissions in
    some scenario. Not only medel: Testcyklisterna's gift cards (run 2) were
    a cost whose ΔEF shrank it into a "reduction" in medel."""
    return units.is_money(drv.a0_unit) and any(
        drv.direction(sc) > 0 for sc in ('min', 'med', 'max'))


def spend_post_of(drv: Driver) -> dict:
    """The row a spend post is shown as: kronor, the factor the analysis gave
    and the one used (per krona), and tons. Per year for an annual post."""
    kr = drv.a0 * (units.kronor_per_unit(drv.a0_unit) or 1.0)
    # The factor per krona from its own unit ("kg CO2e/kr" next to an amount
    # in tkr), else assumed per the activity's unit, as the engine reads it.
    given = drv.ef0 / (units.ef0_kronor(drv.ef0_unit)
                       or units.kronor_per_unit(drv.a0_unit) or 1.0)
    used = min(given, SPEND_EF_PER_KR)
    return {'name': drv.name, 'kronor': kr, 'ef_given': given, 'ef_used': used,
            'ton': kr * used / 1000.0, 'year': drv.ramp.start_year, 'one_off': drv.one_off}


def infer_catch_up(drivers: list[Driver]) -> None:
    """Give a one-off with a lifetime but no catch-up year of its own the
    latest end year among the annual drivers that lower emissions, per
    scenario: the benefit stops when BAU catches up, and the equipment that
    delivered it was brought forward by the same years. Left unset when no
    such driver ends in any scenario, or when there is none."""
    benefits = [x for x in drivers if not x.one_off and x.direction() < 0]
    if not benefits:
        return
    ends = []
    for sc in ('min', 'med', 'max'):
        ends.append(max(b.ramp.end_year.get(sc) if b.ramp.end_year is not None
                        else UNBOUNDED_YEAR for b in benefits))
    if all(e >= UNBOUNDED_YEAR for e in ends):
        return
    for x in drivers:
        if x.one_off and x.lifetime is not None and x.catch_up is None and x.direction() > 0:
            x.catch_up = Triple(*ends)
            x.catch_up_from = "nyttan"


def drop_same_year_catch_up(drivers: list[Driver]) -> None:
    """In a potential analysis, forget a one-off's catch-up year when it is
    not later than the purchase year (medel). The forecast prompt does not
    ask for one there, and an end year equal to the purchase year has meant
    "the post exists that year only" (lövblåsare, 2026-11-09: 2026 / 2026 /
    2026). Read as a catch-up year it would charge a written-off purchase
    with one year of its lifetime. infer_catch_up may then give it the
    benefit's end instead."""
    for x in drivers:
        if x.one_off and x.catch_up is not None and x.catch_up.med <= x.ramp.start_year:
            x.catch_up = None
            x.catch_up_from = ""


def write_off_in_potential(drivers: list[Driver]) -> None:
    """Mark the drivers a potential analysis writes off: those with a
    lifetime that raise emissions (medel), annual or one-off. The
    manufacture of equipment is then spread evenly over its lifetime, and a
    one-off only up to its catch-up year, so the target year carries a
    yearly share of it (Henric 2026-11-10). A follow-up keeps its own rule
    (write_off_to): its result is the whole window, not one year."""
    for x in drivers:
        x.write_off = x.lifetime is not None and x.direction() > 0


def write_off_to(drivers: list[Driver], target_year: int) -> None:
    """In a follow-up, charge equipment only for the years of its lifetime
    that fall within the window, as its benefit is only counted to the target
    year: the catch-up year is capped at the target year, and a piece of
    equipment without one gets the target year. 2026-10-22, after the
    review of omgång 3: the battery store was charged with the whole battery
    against a benefit counted to 2030 (−4,9 ton). catch_up_from becomes
    "målåret" when the cap set medel."""
    for x in drivers:
        if not (x.one_off and x.lifetime is not None and x.direction() > 0):
            continue
        given = x.catch_up or Triple(UNBOUNDED_YEAR, UNBOUNDED_YEAR, UNBOUNDED_YEAR)
        capped = Triple(*(min(given.get(sc), target_year) for sc in ('min', 'med', 'max')))
        if capped == given:
            continue
        if given.med > target_year:
            x.catch_up_from = "målåret"
        x.catch_up = capped


@dataclass(frozen=True)
class Grant:
    """One year's money for a measure funded over several years."""
    year: int
    amount: float  # kronor used that year (granted, when nothing was reported used)


def grants_of(v) -> list[Grant]:
    """Parse the extraction's grant list. Raises on a negative amount or a
    list that sums to zero, since either would divide the benefit wrongly.
    Two rows for the same year (two decisions in one year) become one."""
    if not v:
        return []
    if not isinstance(v, list):
        raise ValueError("grants ska vara en lista med {year, amount}.")
    out: list[Grant] = []
    for g in v:
        if not isinstance(g, dict):
            raise ValueError(f"Bidragsrad {g!r} ska vara {{year, amount}}.")
        year = g.get('year', g.get('ar'))
        amount = g.get('amount', g.get('belopp'))
        if year is None or amount is None:
            raise ValueError(f"Bidragsrad {g!r} saknar year eller amount.")
        amount = float(amount)
        if not (math.isfinite(amount) and amount >= 0):
            raise ValueError(f"Bidragsrad {g!r}: beloppet måste vara >= 0.")
        out.append(Grant(in_years(int(year), "Bidragsrad: year"), amount))
    if sum(g.amount for g in out) <= 0:
        raise ValueError("Bidragsraderna summerar till 0 kr; fördelningen går inte att räkna.")
    per_year: dict[int, float] = {}
    for g in out:
        per_year[g.year] = per_year.get(g.year, 0.0) + g.amount
    return [Grant(y, a) for y, a in sorted(per_year.items())]
