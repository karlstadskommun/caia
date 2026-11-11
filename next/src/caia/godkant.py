"""Bind the calc's inputs to what the user approved (security review S21).

In step 4 the user approves the assumptions per driver, in step 3 the
baseline. Step 5 then has a language model read the numbers back out of the
conversation (agents/kalkyl_extract.py), and the engine computes on what it
read. Nothing compared the two: an extraction that read -0.84 where the user
approved -0.38, or a baseline ten times the one in step 3, was computed and
labelled as calculated by the engine without a word (the reviewer's probe:
85.5, 189.0 and 855.0 ton, all three unmarked).

This module compares them. Approved means an assistant turn the user moved
on from with the step's bridge line (caia.pipeline.BRIDGE), the latest such
turn per step. Each extracted driver is matched by name to an approved
driver, and its numbers are compared with that driver's blocks:

  a0, ef0             the baseline's "A0:" / "EF0:" line for the driver.
  g_a, g_ef           anywhere in the driver's baseline and evidens blocks,
                      or the approved profile. Medel only: the engine runs
                      BAU on the medel trend in every scenario.
  delta_a, delta_ef,  the evidens parameter the extraction read the effect
  attribution         from: one whose lines hold two of the effect's three
                      scenarios. The third must then match that parameter
                      too. The same holds for a recipe: two or three
                      parameters multiplied, or one over the driver's A0 or
                      EF0, that gives two scenarios must give the third
                      (an outer scenario may also mix scenario lines, which
                      evidens blocks tell the extraction to do).

The extraction is allowed to normalise and to combine terms, and on real
runs it does both all the time: a share of a population, a change in kWh
over a level, two cohorts in one driver, a unit of its own. A comparison that
demands every number in the approved text warns on most real analyses, so
this one is narrower on purpose. A number passes when

  - the approved text holds it as written, as a percent, or one unit step
    away (x1000: ton and kg, MWh and kWh), sign ignored, within the precision
    it was written with; or
  - it is within a factor of FACTOR of the approved value for its slot; or
  - it is the a0 of a driver whose activity an outer scenario takes away
    whole (delta_a -100 %), it is larger than the baseline's A0, and it is
    the largest amount two approved amount parameters give multiplied on one
    scenario line (the base the forecast extraction prompt prescribes there;
    not in follow-up mode, whose prompt has no such rule); or
  - there is no approved value to compare it with: a baseline the approved
    text sets to 0 (the extraction is told to assume one), a unit that is per
    year on one side and not on the other, an effect no single approved
    parameter accounts for (the extraction derived it).

Measured against 21 saved real runs (78 drivers, 2026-10-09): two numbers do
not pass, and both are misreadings the extraction's own note gives away
(docs/security-review-2026-10.md, S21). The narrowing has a cost the same
measurement puts a number on: a derived effect nothing anchors, a sign, a
change smaller than FACTOR, a zeroed effect, all three scenarios scaled
together, and terr/cons/overlap outside the driver's own evidens block
are not caught.
tools/check_godkant.py reruns the measurement.

A number that does not pass is marked for checking in *Talens ursprung*
(caia.kallmarkering), the label a reader already knows. The check never stops
or changes the calculation.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .calc.schema import CalcModel, Triple
from .evidence import _DRIVER, _parse_driver_body
from .mode import UPPFOLJNING
from .pipeline import BRIDGE

# How far a number may move from the approved value for its slot before it is
# marked: a rounding, a recomputed "ca" or a scenario rule moves it less, the
# reviewer's -0.38 to -0.84 (x2.2) and a baseline x10 move it more. Below
# this, a changed number is not caught.
FACTOR = 1.5

# Steps whose approved output the extraction reads.
_STEPS = ("intake", "emap", "baslinje", "evidens")
_SCENARIOS = ("min", "med", "max")
_SWAP = {"min": "max", "med": "med", "max": "min"}

# A number as the agents write them: "2,16e6", "1 300 000", "−0,92", "15 %",
# "1,3 miljoner", "3,0 × 10^6", "6,7·10⁻⁶". Thousands are grouped in threes
# with a space (or a no-break or thin space); the decimal mark is a comma or
# a point. "× 10" needs a caret or a superscript: "2 × 100" is a product.
# "milj." ends in its point, so no word boundary is asked after it: with one,
# "1,3 milj. ton" was read as 1,3.
_NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?"
    r"(?:[  ]?[eE]([+\-−]?\d{1,2})(?!\d)"
    r"|[  ]?[×x·][  ]?10(?:\^([+\-−]?\d{1,2})(?!\d)|([⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]{1,2})(?![⁰¹²³⁴⁵⁶⁷⁸⁹])))?"
    r"(?:[  ]?(miljoner\b|miljon\b|milj\.|tusen\b))?",
    re.IGNORECASE)
_SUPERSCRIPT = str.maketrans("⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "+-0123456789")
_MULT = {"miljoner": 1e6, "miljon": 1e6, "milj.": 1e6, "tusen": 1e3}

SHARE = (1.0, 0.01)            # a share, or the same share written in percent
UNIT = (1.0, 1000.0, 0.001)    # one SI step: ton and kg, MWh and kWh, g and kg

# Slack on top of the written precision, for the engine's own rounding. The
# written precision is capped: "0,3" alone would otherwise cover 0.25-0.35.
_SLACK = 0.006
_MAX_TOL = 0.06

# "A0: 2,16e6 (180 bilar × 12 000 km)", "EF0_enhet: kg CO2e/km (TTW)".
_SLOT = re.compile(
    r"^[ \t]*+(?:[-*+][ \t]++)?(?:\*{1,2}|_{1,2})?[ \t]*+(A0|EF0)(_enhet)?"
    r"[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+[:=][ \t]*+(.*)$", re.IGNORECASE)
_PER_YEAR = re.compile(r"/\s*år|per\s+år", re.IGNORECASE)

# The parameter an effect is read from, by its name in the evidens block.
# Other parameters only count when none is named so.
_NAMED = {
    "attribution": re.compile(r"attribution|tillskriv", re.IGNORECASE),
    "delta_a": re.compile(r"(?:Δ|delta_?)\s*A(?![a-zåäö])", re.IGNORECASE),
    "delta_ef": re.compile(r"(?:Δ|delta_?)\s*EF", re.IGNORECASE),
}

FALTNAMN = {"g_a": "trenden för aktiviteten", "g_ef": "trenden för emissionsfaktorn"}

# The climate factors as the evidens block states them ("Territoriell_faktor:
# 0.05"). The forecast extraction is told to use them as they stand
# (agents/kalkyl_extract.py, KLIMATFAKTORER), so another value is a
# misreading. They are written with two decimals at most.
_FACTOR_LINE = re.compile(
    r"^[ \t]*+(?:[-*+][ \t]++)?(?:\*{1,2}|_{1,2})?[ \t]*+"
    r"(Territoriell|Konsumtion|Overlap|Överlapp)_?faktor"
    r"[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+[:=][ \t]*+(?:\*{1,2})?[ \t]*+(\d+(?:[.,]\d+)?)(?!\d|[.,]\d|[ \t]*%)",
    re.IGNORECASE)
_FACTOR_FIELD = {"territoriell": "terr", "konsumtion": "cons", "overlap": "overlap",
                 "överlapp": "overlap"}
FACTOR_LABEL = {"terr": "Territoriell_faktor", "cons": "Konsumtion_faktor",
                "overlap": "Overlap_faktor"}
_FACTOR_TOL = 0.006


def _factors(blocks_: list[Block]) -> dict[str, list[float]]:
    """field -> the values the blocks state for it."""
    out: dict[str, list[float]] = {}
    for b in blocks_:
        for line in b.text.splitlines():
            m = _FACTOR_LINE.match(line)
            if m:
                out.setdefault(_FACTOR_FIELD[m.group(1).lower()], []).append(
                    float(m.group(2).replace(",", ".")))
    return out


def _decimal(x: float) -> str:
    return f"{x:g}".replace(".", ",")


@dataclass(frozen=True)
class Num:
    value: float      # absolute value
    digits: int       # significant digits as written
    neg: bool = False  # written with a minus sign, for display only
    pct: bool = False  # written as a percent, for display only

    @property
    def tol(self) -> float:
        """Relative: half a unit in the last written digit, plus slack."""
        exp = math.floor(math.log10(self.value))
        return min(0.5 * 10 ** (exp - self.digits + 1) / self.value, _MAX_TOL) + _SLACK

    @property
    def text(self) -> str:
        """Swedish, with the digits it was written with: 2,2e5 is 220 000.
        Digits, a sign and a percent only, never the approved text itself:
        this goes into the program's own section (S20)."""
        x = float(f"{self.value:.{self.digits}g}")
        s = (f"{round(x):,}".replace(",", " ") if x >= 1000
             else f"{x:.{self.digits}g}".replace(".", ","))
        return ("−" if self.neg else "") + s + (" %" if self.pct else "")


def numbers(text: str) -> list[Num]:
    out = []
    for m in _NUMBER.finditer(text or ""):
        whole = re.sub(r"[   ]", "", m.group(1))
        frac = m.group(2) or ""
        try:
            x = float(whole + ("." + frac if frac else ""))
            exp = m.group(3) or m.group(4) or (m.group(5) or "").translate(_SUPERSCRIPT)
            if exp:
                x *= 10 ** int(exp.replace("−", "-"))
            if m.group(6):
                x *= _MULT[m.group(6).lower()]
        except (ValueError, OverflowError):
            continue
        if x and math.isfinite(x):
            before = text[max(0, m.start() - 2):m.start()].rstrip()
            neg = before[-1:] in ("-", "−", "–") and not before[-2:-1].isdigit()
            pct = text[m.end():m.end() + 2].lstrip().startswith("%")
            out.append(Num(abs(x), len((whole + frac).lstrip("0")) or 1, neg, pct))
    return out


def approved(history: list[dict]) -> dict[str, str]:
    """step -> the latest assistant turn the user approved with that step's
    bridge line. A turn the user gave feedback on instead is not approved."""
    out: dict[str, str] = {}
    lines = {BRIDGE[s]: s for s in _STEPS}
    for prev, turn in zip(history, history[1:]):
        if not (isinstance(turn, dict) and isinstance(prev, dict)):
            continue
        content = turn.get("content")
        step = lines.get(content.strip()) if isinstance(content, str) else None
        if (step and turn.get("role") == "user" and prev.get("role") == "assistant"
                and isinstance(prev.get("content"), str)):
            out[step] = prev["content"]
    return out


@dataclass(frozen=True)
class Block:
    number: int
    name: str
    text: str


def blocks(text: str) -> list[Block]:
    """The 'Drivare N: name' blocks of one step's text, each to the next
    driver heading. Baslinje lists every driver twice (nuläge and BAU)."""
    found = list(_DRIVER.finditer(text or ""))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append(Block(int(m.group("number")), m.group("name").strip().strip("*_ "),
                         text[m.end():end]))
    return out


_WORD = re.compile(r"[a-zåäöé0-9]{4,}", re.IGNORECASE)


def _stems(name: str) -> set[str]:
    return {w.lower()[:5] for w in _WORD.findall(name or "")}


def _plain(name: str) -> str:
    return " ".join(re.findall(r"[a-zåäöé0-9]+", (name or "").lower()))


_DRIVER_PREFIX = re.compile(r"\s*Drivare\s+(\d+)\s*:")


def match_driver(name: str, named: list[Block]) -> int | None:
    """The approved driver number with the same name, or else the one whose
    name shares the largest part of its words with the extraction's name.
    None when no name shares any, or when two drivers share as much
    ("Personbilar el" and "Personbilar diesel" are the same to the word
    overlap, which drops short words): then the driver is compared with all
    approved drivers, which can miss a deviation but never invents one."""
    exact = {b.number for b in named if _plain(b.name) == _plain(name)}
    if len(exact) == 1:
        return exact.pop()
    want = _stems(name)
    scores: dict[int, float] = {}
    for b in named:
        have = _stems(b.name)
        if want and have:
            score = len(want & have) / min(len(want), len(have))
            scores[b.number] = max(score, scores.get(b.number, 0.0))
    if not scores:
        return None
    top = max(scores.values())
    best = [n for n, sc in scores.items() if sc == top]
    return best[0] if top > 0 and len(best) == 1 else None


# --- comparing one number -------------------------------------------------------

def _held(x: float, pool: list[Num], scales) -> bool:
    """The pool holds x, after one of `scales`, within its written precision."""
    return any(abs(x - n.value * s) <= n.tol * n.value * s + 1e-12
               for n in pool for s in scales)


def _near(x: float, refs: list[Num], scales) -> bool:
    """x is within FACTOR of one of `refs`, after one of `scales`."""
    return any(n.value * s / FACTOR <= x <= n.value * s * FACTOR
               for n in refs for s in scales)


def _slot(blocks_: list[Block], label: str) -> tuple[list[list[Num]], list[str]]:
    """The numbers on each line labelled `label` ("A0", "EF0"), and the
    units its _enhet lines give."""
    lines, units = [], []
    for b in blocks_:
        for line in b.text.splitlines():
            m = _SLOT.match(line)
            if m and m.group(1).upper() == label:
                if m.group(2):
                    units.append(m.group(3))
                else:
                    lines.append(numbers(m.group(3)))
    return lines, units


def _params(blocks_: list[Block]) -> list[dict]:
    """The driver's approved parameters: name, and per scenario the numbers
    on that scenario's line, the leading one first."""
    out = []
    for b in blocks_:
        for p in _parse_driver_body(b.text)["parameters"]:
            nums = {sc: numbers(p.get(sc, "")) for sc in _SCENARIOS}
            if any(nums.values()):
                label = f"{p.get('name', '')} {p.get('enhet', '')}"
                out.append({"name": p.get("name", ""),
                            "tid": _TIMING.search(label) is not None,
                            "mangd": _NOT_AMOUNT.search(label) is None and not _is_year(nums),
                            **nums})
    return out


# A parameter about when, not how much: a half-life, a start-year share, a
# catch-up year. The extraction puts those on the ramp, never in an effect.
_TIMING = re.compile(r"halveringstid|startår|ikapp|end_year|half_life|^\s*år\b|\bår\s*$",
                     re.IGNORECASE)
# A parameter that cannot be one of the two an amount is multiplied from: an
# emission factor, or a point in time. Narrower than _TIMING on purpose: that
# one takes every unit ending in "/år", which is how an amount per year is
# written.
_NOT_AMOUNT = re.compile(
    r"co2|koldioxid|(?<![a-zåäö])EF(?![a-zåäö])|emissionsfaktor|utsläppsfaktor"
    r"|halveringstid|startår|slutår|målår|årtal|ikapp|end_year|half_life", re.IGNORECASE)


def _is_year(nums: dict) -> bool:
    """Every scenario's leading number is a calendar year (2027, 2028, 2030)."""
    lead = [n[0].value for n in nums.values() if n]
    return bool(lead) and all(v == int(v) and 1990 <= v <= 2100 for v in lead)


_MAX_RECIPE_TOL = 0.08
# Recipes are tried over this many of a driver's parameters at most. Real
# blocks have two to six; the cap keeps a block of a hundred (pasted text, a
# drifting model) from costing seconds per driver (security review S19).
_RECIPE_PARAMS = 8


def _anchors(v: Triple, params: list[dict]) -> dict[str, list[Num]]:
    """scenario -> the approved numbers it must match. A parameter whose
    lines hold two of the effect's three scenarios is the one the effect was
    read from; the third scenario must match that parameter's line too.
    Nothing when a parameter holds all three, or none holds two."""
    vals = {sc: abs(v.get(sc)) for sc in _SCENARIOS}
    out: dict[str, list[Num]] = {}
    for p in params:
        for mapping in (_SCENARIOS, tuple(_SWAP[s] for s in _SCENARIOS)):
            lines = dict(zip(_SCENARIOS, mapping))
            hits = {sc for sc in _SCENARIOS if vals[sc] and _held(vals[sc], p[lines[sc]], SHARE)}
            if len(hits) == 3:
                return {}
            if len(hits) == 2:
                for sc in _SCENARIOS:
                    if sc not in hits and vals[sc] and p[lines[sc]]:
                        out.setdefault(sc, []).extend(p[lines[sc]])
    return out


# How a parameter's number is read as a factor: as written, a percent as a
# share, or the complement of either ("60 % kvar" is a 40 % cut). A recipe
# reads a parameter the same way in every scenario.
_KINDS = ("x", "pct", "c", "pct_c")


def _variants(n: Num) -> dict[str, tuple[float, float]]:
    """kind -> (factor, relative tolerance) for a parameter's leading number."""
    out = {"x": (n.value, n.tol)}
    if n.value >= 1:
        out["pct"] = (n.value / 100, n.tol)
    for kind, comp in (("x", "c"), ("pct", "pct_c")):
        if kind in out and 0 < out[kind][0] < 1:
            v, t = out[kind]
            out[comp] = (1 - v, t * v / (1 - v))
    return out


def _recipe_table(params: list[dict], levels: list[float]) -> list[dict]:
    """The ways the extraction combines approved parameters into an effect,
    each as scenario line -> (value, tolerance) or None: one parameter's
    leading number, or two or three multiplied, any of them over the
    driver's own level (a change in kWh over A0, in kg/km over EF0). A
    recipe is the same in every scenario, which is what lets two scenarios
    vouch for the third. Built once per driver."""
    from itertools import combinations, product
    params = [p for p in params if not p["tid"]][:_RECIPE_PARAMS]
    var = [{sc: (_variants(p[sc][0]) if p[sc] else {}) for sc in _SCENARIOS} for p in params]
    table = []
    for size in (1, 2, 3):
        for picked in combinations(range(len(params)), size):
            for which in product(_KINDS, repeat=size):
                base = {}
                for sc in _SCENARIOS:
                    v, t = 1.0, 0.0
                    for k, w in zip(picked, which):
                        vs = var[k][sc]
                        if w not in vs:
                            v = None
                            break
                        v, t = v * vs[w][0], t + vs[w][1]
                    base[sc] = None if v is None or not v else (v, t)
                if sum(b is not None for b in base.values()) < 2:
                    continue
                for lv in [None] + levels:
                    table.append({
                        sc: None if b is None else
                        (b[0] / lv if lv else b[0], min(b[1] + (_SLACK if lv else 0), _MAX_RECIPE_TOL))
                        for sc, b in base.items()})
    return table


def _mixed(x: float, params: list[dict], levels: list[float]) -> bool:
    """x as two parameters multiplied, each from any scenario's line, either
    one over the driver's level. Evidens blocks tell the extraction to do
    this in the outer scenarios ("i max-scenariot används medelvärdet
    tillsammans med max-adoption"; a cost driver takes Antagande_max in the
    min scenario), so it explains a min or max value, never a med."""
    from itertools import combinations, product
    params = [p for p in params if not p["tid"]][:_RECIPE_PARAMS]
    for p, q in combinations(params, 2):
        for s1, s2 in product(_SCENARIOS, repeat=2):
            if not (p[s1] and q[s2]):
                continue
            for (va, ta), (vb, tb) in product(_variants(p[s1][0]).values(),
                                              _variants(q[s2][0]).values()):
                for lv in [None] + levels:
                    c = va * vb / lv if lv else va * vb
                    t = min(ta + tb + (_SLACK if lv else 0), _MAX_RECIPE_TOL)
                    if c and abs(x - c) <= t * c + 1e-12:
                        return True
    return False


def _floor_base(x: float, params: list[dict], refs: list[Num]) -> bool:
    """x as the largest amount the scenarios give: two amount parameters
    multiplied on one outer scenario line (50 handlare × 1,2 ton, or 120 ton
    × 50 %), after one unit step. The forecast extraction prompt puts a0
    there when a scenario takes more than the whole baseline away, and counts
    all three scenarios as shares of it (agents/kalkyl_extract.py, the rule
    on a delta below -1).

    Kept narrow, because every value let through here is one the comparison
    no longer marks. The base is larger than the baseline's own A0, or the
    rule had no reason to move it. It is the larger of the pair's two outer
    products, never the smaller: the smallest scenario amount is no base. And
    neither factor is an emission factor or a year (a count times an EF, or
    a start year times a share, is not an amount)."""
    from itertools import combinations
    if not refs or not all(x > r.value for r in refs):
        return False
    # Not the "tid" mark: it takes any unit that ends in "/år".
    amounts = [p for p in params if p["mangd"]][:_RECIPE_PARAMS]

    def factor(n: Num) -> float:
        # One reading per number: a percent is a share, anything else is as
        # written. Trying both let 50 "handlare" pass as 50 % (0,5 × 1,2 ton,
        # one unit step up: 600).
        return n.value / 100 if n.pct else n.value

    for p, q in combinations(amounts, 2):
        # Both outer lines, or there is no telling which product is the larger.
        if not all(p[ln] and q[ln] for ln in ("min", "max")):
            continue
        c, t = max((factor(p[ln][0]) * factor(q[ln][0]),
                    min(p[ln][0].tol + q[ln][0].tol, _MAX_RECIPE_TOL)) for ln in ("min", "max"))
        if any(abs(x - c * s) <= t * c * s + 1e-12 for s in UNIT):
            return True
    return False


def _recipe_anchors(v: Triple, table: list[dict]) -> dict[str, list[float]] | None:
    """scenario -> what a recipe that gives the other two scenarios gives
    for it. None when one recipe gives all three: the effect is accounted for."""
    vals = {sc: abs(v.get(sc)) for sc in _SCENARIOS}
    if len({x for x in vals.values() if x}) < 2:
        return {}
    out: dict[str, list[float]] = {}
    swapped = dict(zip(_SCENARIOS, (_SWAP[s] for s in _SCENARIOS)))
    for row in table:
        for mapping in (None, swapped):
            got = {sc: row[mapping[sc] if mapping else sc] for sc in _SCENARIOS}
            hits = [sc for sc in _SCENARIOS
                    if vals[sc] and got[sc] and abs(vals[sc] - got[sc][0]) <= got[sc][1] * got[sc][0]]
            if len(hits) == 3:
                return None
            if len(hits) == 2:
                for sc in _SCENARIOS:
                    if sc not in hits and vals[sc] and got[sc]:
                        out.setdefault(sc, []).append(got[sc][0])
    return out


# --- the check -------------------------------------------------------------------

@dataclass(frozen=True)
class Avvikelse:
    """One input number that does not match what the user approved."""
    nr: int            # the driver's index in the model
    drivare: str
    falt: str
    scenario: str      # "min"/"med"/"max", "" for a single value
    varde: float
    problem: str       # for the reader, Swedish


def _scen(sc: str) -> str:
    return {"min": "min", "med": "medel", "max": "max"}.get(sc, sc)


def omfang(history: list[dict]) -> str:
    """What the comparison could compare with: "ja" (baseline and
    assumptions), "utan_baslinje" (assumptions only: no approved baseline
    with driver blocks, so A0 and EF0 are not compared), "inget" (no
    approved evidens turn with driver blocks: nothing is compared)."""
    steps = approved(history or [])
    if not blocks(steps.get("evidens", "")):
        return "inget"
    if not blocks(steps.get("baslinje", "")):
        return "utan_baslinje"
    return "ja"


def granska(model: CalcModel, history: list[dict]) -> list[Avvikelse]:
    """Every input number of `model` that does not match the approved turns
    of `history`. Empty when there is no approved evidens turn (an old
    history, or a client that drives the steps without the bridge lines):
    then there is nothing to compare with."""
    steps = approved(history or [])
    if "evidens" not in steps:
        return []
    ev_blocks = blocks(steps["evidens"])
    if not ev_blocks:
        return []
    bas_blocks = blocks(steps.get("baslinje", ""))
    profile = steps.get("intake", "")
    out: list[Avvikelse] = []
    for nr, d in enumerate(model.drivers):
        n = match_driver(d.name, ev_blocks + bas_blocks)
        # The calculation names a driver in its own words ("Tillkommande
        # laddel, KBAB:s egen mark" for the baseline's "Elanvändning för
        # laddning av elbilar hos hyresgäster"), and the word overlap then
        # lands on another driver: the charging electricity was compared with
        # the fossil kilometres and marked (2026-10-14, boendeladdning, 4 of
        # 4 marks). The drivers keep their order and often their "Drivare N:",
        # so the driver in the same place is the calculation's own as well.
        # A wider pool can miss a deviation but never invents one.
        own = {n, nr + 1} if n is not None else set()
        prefix = _DRIVER_PREFIX.match(d.name or "")
        if own and prefix:
            own.add(int(prefix.group(1)))
        # A name that matches no approved driver is compared with all of them.
        own_ev = [b for b in ev_blocks if b.number in own]
        mine_ev = own_ev or ev_blocks
        mine_bas = [b for b in bas_blocks if b.number in own] or bas_blocks
        # The baseline numbers are compared with the driver's own blocks;
        # the profile holds counts and amounts that a scaled A0 or EF0 would
        # match too easily.
        base_pool = numbers("\n".join(b.text for b in mine_bas + mine_ev))
        pool = base_pool + numbers(profile)
        params = _params(mine_ev)
        # An outer scenario takes the whole amount away. The base is then the
        # scenarios' largest amount and not the baseline's A0: marked, it was
        # a warning on a calculation that had read the assumptions right
        # (2026-10-13, 4 of 4 runs on a case where max needs 2,8 x baseline).
        # The amount only: an emission factor that goes to zero (fossil-free)
        # moves no base. Forecast mode only: the follow-up extraction has no
        # such rule, so there a base like this is a misreading.
        floored = (getattr(model, "mode", None) != UPPFOLJNING
                   and any(abs(d.delta_a.get(sc) + 1.0) < 1e-6 for sc in ("min", "max")))

        for falt, label, unit in (("a0", "A0", d.a0_unit), ("ef0", "EF0", d.ef0_unit)):
            x = abs(getattr(d, falt))
            lines, units = _slot(mine_bas, label)
            if (not x or not lines or any(not ln or not ln[0].value for ln in lines)
                    or any(bool(_PER_YEAR.search(u)) != bool(_PER_YEAR.search(unit or ""))
                           for u in units)):
                continue
            # Only the line's leading number is the approved value: the rest
            # of the line is how it was reached ("138 deltagare × 2 900 km").
            refs = [ln[0] for ln in lines]
            if not (_held(x, base_pool, UNIT) or _near(x, refs, UNIT)
                    or (falt == "a0" and floored and _floor_base(x, params, refs))):
                out.append(Avvikelse(
                    nr, d.name, falt, "", getattr(d, falt),
                    f"avviker från baslinjen, som anger {label} {lines[0][0].text}"))

        # Only the medel trend: the engine runs BAU on it in all three
        # scenarios (calc.engine._driver_year), so min and max of a trend
        # change no number. An extraction that weighed two trends together
        # for them was marked, and the page warned about a result they had
        # not touched (2026-10-13, reference package återbruk, 4 of 8 runs).
        for falt in ("g_a", "g_ef"):
            v = getattr(d, falt)
            x = abs(v.med)
            if x and not _held(x, pool, SHARE):
                out.append(Avvikelse(
                    nr, d.name, falt, "med", v.med,
                    f"{FALTNAMN[falt]} ({_scen('med')}) står inte i baslinjen eller "
                    "evidenssteget"))

        # The two rules below mark what the driver's own block says and the
        # calculation does not, so a wider pool would invent a mark rather than
        # miss one. They use one block: the one with the driver's exact name,
        # else the one its "Drivare N:" names, else the one name and place
        # agree on; none when they disagree.
        exact = {b.number for b in ev_blocks + bas_blocks if _plain(b.name) == _plain(d.name)}
        sure = (exact if len(exact) == 1 else {int(prefix.group(1))} if prefix
                else own if len(own) == 1 else set())
        sure_ev = [b for b in ev_blocks if b.number in sure]

        # The climate factors, against the driver's own block only: another
        # driver's factors are often different on purpose. Both modes: the
        # follow-up extraction has had the rule that keeps a Konsumtion_faktor
        # above 1 since 2026-11-08 (agents/kalkyl_extract.py), so a 1,1 read
        # as 1,0 is a misreading there too. Until 1.1 it was let through, as
        # the follow-up prompt had been the older one.
        stated = _factors(sure_ev)
        for falt, values in stated.items():
            x = getattr(d, falt, None)
            if not isinstance(x, (int, float)) or any(abs(x - v) <= _FACTOR_TOL for v in values):
                continue
            out.append(Avvikelse(
                nr, d.name, falt, "", float(x),
                f"avviker från evidenssteget, som anger {FACTOR_LABEL[falt]} {_decimal(values[0])}"))

        # An effect of 0 in all three scenarios takes the driver out of the
        # result. When the driver's own approved assumptions give an effect
        # that is not 0, that is a misreading: an added electricity use read
        # as no change (4 of 4 such drivers in 141 saved runs, 2026-10-15).
        if sure_ev and all(getattr(d, f).get(sc) == 0
                           for f in ("delta_a", "delta_ef") for sc in _SCENARIOS):
            for p in _params(sure_ev):
                which = [f for f in ("delta_a", "delta_ef") if _NAMED[f].search(p["name"] or "")]
                if which and p["med"] and not p["tid"]:
                    out.append(Avvikelse(
                        nr, d.name, which[0], "med", 0.0,
                        "effekten är 0 i alla tre scenarier, men det godkända antagandet "
                        f"anger {p['med'][0].text} för {_scen('med')}"))
                    break

        levels = [abs(x) for x in (d.a0, d.ef0) if x]
        table = None
        for falt in ("delta_a", "delta_ef", "attribution"):
            v = getattr(d, falt)
            if falt == "attribution" and v.min == v.med == v.max == 1.0:
                continue
            named = [p for p in params if _NAMED[falt].search(p["name"] or "")] or params
            flagged = set()
            for sc, refs in sorted(_anchors(v, named).items(),
                                   key=lambda kv: _SCENARIOS.index(kv[0])):
                x = abs(v.get(sc))
                lines = (sc,) if sc == "med" else ("min", "max")
                if _held(x, [num for p in params for ln in lines for num in p[ln]], SHARE) \
                        or _near(x, refs, SHARE):
                    continue
                flagged.add(sc)
                out.append(Avvikelse(
                    nr, d.name, falt, sc, v.get(sc),
                    f"avviker från det godkända antagandet, som för {_scen(sc)} anger "
                    f"{refs[0].text}"))
            if table is None:
                table = _recipe_table(params, levels)
            ra = _recipe_anchors(v, table)
            for sc in _SCENARIOS:
                if not ra or not ra.get(sc) or sc in flagged:
                    continue
                x = abs(v.get(sc))
                lines = (sc,) if sc == "med" else ("min", "max")
                if _held(x, [num for p in params for ln in lines for num in p[ln]], SHARE) \
                        or any(c / FACTOR <= x <= c * FACTOR for c in ra[sc]) \
                        or (sc != "med" and _mixed(x, params, levels)):
                    continue
                out.append(Avvikelse(
                    nr, d.name, falt, sc, v.get(sc),
                    f"avviker från det de godkända antagandena ger för {_scen(sc)}, "
                    f"omkring {Num(ra[sc][0], 2).text}"))
    return out
