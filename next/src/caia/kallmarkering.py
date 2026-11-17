"""Källmarkering: check where every input number comes from, and say so.

Göteborg (2026-09-23) asked whether the report can show which numbers
the analysis found itself, outside the parameter library. This module answers
that for every number the deterministic calc rests on (calc.schema.KALLFALT on
every driver).

The extraction agent states an origin per number (calc.schema.Kalla). This
module does not trust the statement; it checks it against the active profile's
parameter library and data register:

  parameterbibliotek  every named Parameter_ID must exist. With one ID the value
                      must be one the library holds (a standard or local cell,
                      within 5 %), after the one unit step the two units call
                      for: g vs kg vs ton, kWh vs MWh, percent vs share. With
                      several IDs the number is derived and the derivation must
                      be written out.
  kommundata          every reference must be a library row with a local value
                      or a data file that is actually on disk.
  extern              a named source must be given.
  antagande           accepted as stated: that is the category Göteborg asked for.

A number with no origin, an unknown label or a claim that fails the check is
never shown as sourced: it goes to the top of the section under "Kontrollera
först". Nothing here can stop the calculation; the caller renders a fallback
note if this module itself fails.

Given the conversation, the same section also says when a number does not
match what the user approved in steps 3 and 4 (caia.godkant, security review
S21). Such a number goes under "Kontrollera först" too, whatever its stated
origin: an assumption the user approved as -0.38 is not sourced at -0.84.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from . import godkant
from .calc import units
from .calc.schema import KALLFALT, VALFRIA_KALLFALT, CalcModel, Kalla, Triple, Ursprung
from .data.parameters import (READS_AT_ANALYSIS, datafil_name, parameter_view,
                              parse_file_register, parse_parameter_library)
from .logsafe import log_failure

log = logging.getLogger(__name__)

RUBRIK = "## Talens ursprung"

FALTNAMN = {
    "a0": "Aktivitet",
    "ef0": "Emissionsfaktor",
    "g_a": "Trend aktivitet (BAU)",
    "g_ef": "Trend emissionsfaktor (BAU)",
    "delta_a": "Åtgärdens effekt på aktiviteten",
    "delta_ef": "Åtgärdens effekt på emissionsfaktorn",
    "attribution": "Andel som insatsen orsakade (attribution)",
    "terr": "Klimatfaktor, territoriell",
    "cons": "Klimatfaktor, konsumtion",
    "overlap": "Klimatfaktor, överlapp",
}
# The climate factors are method choices and have no row of their own. One
# that departs from the evidens step gets one, under Kontrollera först
# (caia.godkant), and is not counted among the input numbers.
KLIMATFALT = ("terr", "cons", "overlap")

URSPRUNG_TEXT = {
    Ursprung.PARAMETERBIBLIOTEK: "Parameterbiblioteket",
    Ursprung.KOMMUNDATA: "Kommunens data",
    Ursprung.EXTERN: "Extern källa",
    Ursprung.ANTAGANDE: "Antagande",
}

_PROV_TEXT = {"lokal": "lokalt värde", "datafil": "ur datafil", "schablon": "schablon"}

# The extraction normalises ef0 to kg CO2e per unit and trends/effects to
# shares, while the library writes g CO2e/kWh, MWh and percent. A value is
# compared after the one step its own unit and the row's unit call for. It
# used to be tried at x1, x100, x0.01, x1000 and x0.001 whatever the units,
# so an emission factor a thousand times too large still matched the library
# and was reported as sourced.
_TOLERANS = 0.05
_ANDELSFALT = ("g_a", "g_ef", "delta_a", "delta_ef", "attribution")
# The unit table lives in calc.units, shared with the calc's own unit warning.
_PREFIX = units.PREFIX
_prefix = units.prefix


def _unit_scale(falt: str, driver, enhet: str) -> float:
    """Row units per calc unit: the factor the calc's value is multiplied by
    before it is compared with the library row. 1 when the units say nothing
    comparable, so an unexplained factor never passes."""
    e = (enhet or "").strip().lower()
    if "%" in e:
        return 100.0  # the calc holds shares, never percent
    if falt in _ANDELSFALT:
        return 1.0
    calc = driver.ef0_unit if falt == "ef0" else driver.a0_unit
    calc_parts, row_parts = (calc or "").split("/", 1), e.split("/", 1)
    scale = 1.0
    for i in range(min(len(calc_parts), len(row_parts))):
        c, r = _prefix(calc_parts[i]), _prefix(row_parts[i])
        if c and r and c[0] == r[0]:
            # numerator: value in the calc's unit -> row's unit; the
            # denominator works the other way round.
            scale *= c[1] / r[1] if i == 0 else r[1] / c[1]
    return scale

_NUM = r"-?\d+(?:\.\d+)?"
_RANGE_RE = re.compile(rf"^({_NUM})(?:[-–]({_NUM}))?$")


@dataclass(frozen=True)
class Bedomning:
    """The check of one number."""
    drivare: str
    falt: str
    varde: str                 # the value as the report shows it
    kalla: Kalla | None        # what the extraction stated
    ursprung: Ursprung | None  # the stated origin, None when there is none
    problem: str               # "" when the statement holds
    underlag: str              # what the check found, for the reader
    godkant: str = ""          # how it departs from what was approved, or ""

    @property
    def ok(self) -> bool:
        return not self.problem

    def as_dict(self) -> dict:
        return {
            "drivare": self.drivare, "falt": self.falt, "varde": self.varde,
            "ursprung": self.ursprung.value if self.ursprung else None,
            "parametrar": list(self.kalla.parametrar) if self.kalla else [],
            "ok": self.ok, "problem": self.problem, "underlag": self.underlag,
            "godkant": self.godkant,
        }


# --- library lookups ---------------------------------------------------------

def _library(view: bool = False) -> dict[str, dict]:
    """The library rows by ID. With `view`, through parameter_view(), so a
    data-file row also carries the number the parameter view prints and the
    line saying where it came from. Only the report section needs that; the
    prompt block below does not read files it does not show."""
    sections = parameter_view() if view else parse_parameter_library()
    return {r["id"]: r for s in sections for r in s["rows"]}


def _register_entry(name: str, register: dict[str, dict]) -> dict | None:
    """A data-register entry by name. DATA_CITIZEN_SURVEY also finds
    DATA_CITIZEN_SURVEY_2024, but only a year may follow: a bare prefix such
    as DATA would otherwise match any file and pass as the municipality's data."""
    for key, entry in register.items():
        if key == name:
            return entry
        rest = key[len(name) + 1:] if key.startswith(name + "_") else ""
        if rest.isdigit():
            return entry
    return None


def _cell_range(cell: str) -> tuple[float, float] | None:
    """'0,12–0,18' -> (0.12, 0.18); '~30' -> (30, 30); '97 233' -> (97233, 97233).
    None for anything that is not a plain number or range (LOOKUP, formulas)."""
    s = (cell or "").strip().lstrip("~≈").rstrip("%").strip()
    s = re.sub(r"[\s  ]", "", s).replace(",", ".")
    m = _RANGE_RE.match(s)
    if not m:
        return None
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) is not None else lo
    return (min(lo, hi), max(lo, hi))


def _holds(value: float, row: dict, scale: float = 1.0,
           cells=("standard", "lokalt")) -> bool | None:
    """Is `value`, converted to the row's unit by `scale`, one the library
    row holds in `cells`? None when those cells hold no plain number to
    compare with (a LOOKUP into a data file, a formula)."""
    ranges = [r for r in (_cell_range(row.get(c, "")) for c in cells) if r]
    if not ranges:
        return None
    x = abs(value) * scale
    return any(lo * (1 - _TOLERANS) - 1e-12 <= x <= hi * (1 + _TOLERANS) + 1e-12
               for lo, hi in ranges)


def _row_text(pid: str, row: dict) -> str:
    """One library row as the Underlag column shows it.

    A data-file row's value_used is a LOOKUP expression, which reads as
    neither a number nor a source (2026-10-13). It shows what the
    parameter view shows instead, from parameter_view(), so the expression is
    interpreted in one place: the number in the file and the line saying what
    was read from which file, or "Läses ur datafilen vid varje analys" when the
    expression is not one cell. Never the expression, and never a number
    guessed here."""
    prov = _PROV_TEXT.get(row["provenance"], row["provenance"])
    if row["provenance"] != "datafil":
        return f"{pid} ({prov}: {row['value_used']} {row['enhet']})".strip()
    value = row.get("value_display") or READS_AT_ANALYSIS
    if value != READS_AT_ANALYSIS:
        value = f"{value} {row['enhet']}".strip()
    note = (row.get("value_note") or "").strip().rstrip(".")
    return f"{pid} ({prov}: {value}" + (f". {note}" if note else "") + ")"


# --- the check ---------------------------------------------------------------

# Fields where 0 means "no change" (the schema default). a0 and ef0 can never
# be 0: Driver.from_dict refuses them.
_NOLLFALT = ("g_a", "g_ef", "delta_a", "delta_ef")


def _is_zero(v) -> bool:
    if isinstance(v, Triple):
        return v.min == v.med == v.max == 0
    return float(v) == 0


def _is_one(v) -> bool:
    return isinstance(v, Triple) and v.min == v.med == v.max == 1.0


def _value(driver, falt: str) -> float:
    v = getattr(driver, falt)
    return v.med if isinstance(v, Triple) else float(v)


def _check(value: float, kalla: Kalla | None, lib: dict, register: dict,
           scale_for=lambda row: 1.0) -> tuple[Ursprung | None, str, str]:
    """-> (stated origin, problem or "", what the check found). `scale_for`
    gives the unit step from the calc's unit to a library row's unit."""
    if kalla is None:
        return None, "saknar källa", ""
    u = kalla.ursprung
    if u is None:
        if kalla.angivet:
            return None, f"okänt ursprung \"{kalla.angivet}\"", ""
        return None, "saknar källa", ""

    if u is Ursprung.PARAMETERBIBLIOTEK:
        if not kalla.parametrar:
            return u, "anger biblioteket men ingen parameter", ""
        unknown = [p for p in kalla.parametrar if p not in lib]
        if unknown:
            return u, "finns inte i parameterbiblioteket: " + ", ".join(unknown), ""
        rows = [(p, lib[p]) for p in kalla.parametrar]
        underlag = "; ".join(_row_text(p, r) for p, r in rows)
        if len(rows) == 1:
            row = rows[0][1]
            # A data-file row's value is whatever the file says; its standard
            # cell is only the fallback, so a mismatch with it proves nothing.
            held = (None if row["provenance"] == "datafil"
                    else _holds(value, row, scale_for(row)))
            if held is False:
                return u, "värdet står inte i biblioteket", underlag
            if held is None:
                underlag += ". Värdet slås upp eller räknas fram och jämförs inte här"
            if kalla.not_:
                underlag += ". " + kalla.not_
            return u, "", underlag
        if not kalla.not_:
            return u, "uträknat ur flera parametrar men uträkningen saknas", underlag
        return u, "", f"{underlag}. Uträkning: {kalla.not_}"

    if u is Ursprung.KOMMUNDATA:
        if not kalla.parametrar:
            return u, "anger kommunens data men inget lokalt värde eller datafil", ""
        found, texts, missing = [], [], []
        for ref in kalla.parametrar:
            row = lib.get(ref)
            if row is not None:
                if row["provenance"] in ("lokal", "datafil"):
                    found.append((ref, row))
                    texts.append(_row_text(ref, row))
                else:
                    missing.append(f"{ref} har bara ett schablonvärde")
                continue
            entry = _register_entry(ref, register)
            if entry is not None and entry.get("exists") and entry.get("read"):
                found.append((ref, None))
                texts.append(f"Datafil: {datafil_name(ref, entry)}")
            elif entry is not None and not entry.get("read"):
                missing.append(f"{ref} läses inte av CAIA, så inget värde ur den nådde kalkylen")
            elif entry is not None:
                missing.append(f"datafilen för {ref} finns inte")
            else:
                missing.append(f"{ref} finns varken i biblioteket eller bland datafilerna")
        underlag = "; ".join(texts)
        if missing:
            return u, "kommunen har ingen sådan data: " + "; ".join(missing), underlag
        if len(found) == 1 and found[0][1] is not None:
            row = found[0][1]
            if _holds(value, row, scale_for(row), cells=("lokalt",)) is False:
                return u, "värdet står inte i kommunens data", underlag
        if kalla.not_:
            underlag += ". " + kalla.not_
        return u, "", underlag

    if u is Ursprung.EXTERN:
        if not kalla.kalla:
            return u, "extern källa utan namngiven källa", kalla.not_
        return u, "", kalla.kalla + (f". {kalla.not_}" if kalla.not_ else "")

    return u, "", kalla.not_  # ANTAGANDE


# --- formatting --------------------------------------------------------------

def _num(x: float) -> str:
    """Swedish number: space thousands, decimal comma, three significant
    digits below 10 so an emission factor of 0.012 is not shown as 0."""
    if x == 0:
        return "0"
    a = abs(x)
    if a >= 1000:
        s = f"{round(x):,}".replace(",", " ")
    elif a >= 10:
        s = f"{x:.1f}".rstrip("0").rstrip(".")
    else:
        s = f"{x:.3g}"
        if "e" in s:
            s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _pct(x: float) -> str:
    return _num(x * 100) + " %"


def _value_text(driver, falt: str) -> str:
    v = getattr(driver, falt)
    if falt == "a0":
        return f"{_num(v)} {driver.a0_unit}".strip()
    if falt == "ef0":
        return f"{_num(v)} {driver.ef0_unit}".strip()
    if isinstance(v, Triple) and not (v.min == v.med == v.max):
        return f"{_pct(v.med)} ({_pct(v.min)} till {_pct(v.max)})"
    return _pct(v.med if isinstance(v, Triple) else v)


def _cell(s: str) -> str:
    """Safe inside a markdown table cell. The backslash first, or one
    already standing before a "|" undoes the escape."""
    return " ".join((s or "").split()).replace("\\", "\\\\").replace("|", "\\|")


# --- public API --------------------------------------------------------------

def _bindning(model: CalcModel, history: list[dict] | None) -> dict | None:
    """(driver index, field) -> how the number departs from what the user
    approved. {} when nothing departs or there is nothing to compare with;
    None when the comparison itself failed, so the section can say so."""
    if history is None:
        return {}
    try:
        found = godkant.granska(model, history)
    except Exception as e:  # noqa: BLE001 - the comparison must not take the section down
        log_failure(log, "comparison with the approved assumptions failed", e)
        return None
    out: dict[tuple[int, str], list[str]] = {}
    for a in found:
        out.setdefault((a.nr, a.falt), []).append(a.problem)
    return {k: "; ".join(v) for k, v in out.items()}


def granska(model: CalcModel, history: list[dict] | None = None) -> list[Bedomning]:
    """One assessment per input number per driver, in driver order. With the
    conversation, each number is also compared with what the user approved."""
    return _granska(model, _bindning(model, history) or {})


def _granska(model: CalcModel, bind: dict) -> list[Bedomning]:
    lib = _library(view=True)
    register = parse_file_register()
    out: list[Bedomning] = []
    for nr, d in enumerate(model.drivers):
        # An optional input is checked only when the analysis set it: an
        # attribution of 1 is the default, not a number anyone produced.
        valfria = tuple(f for f in VALFRIA_KALLFALT if not _is_one(getattr(d, f)))
        for falt in KALLFALT + valfria:
            kalla = d.kallor.get(falt)
            avvikelse = bind.get((nr, falt), "")
            if kalla is None and falt in _NOLLFALT and _is_zero(getattr(d, falt)):
                # A trend or effect of exactly 0 with nothing stated is the
                # schema's own "no change" default, not a number the analysis
                # produced. It is labelled as the assumption it is, in the open,
                # unless the approved assumptions say the effect is not 0.
                out.append(Bedomning(
                    drivare=d.name, falt=falt, varde=_value_text(d, falt), kalla=None,
                    ursprung=Ursprung.ANTAGANDE, problem=avvikelse,
                    underlag="Ingen förändring angiven i analysen, kalkylen räknar med 0",
                    godkant=avvikelse,
                ))
                continue
            ursprung, problem, underlag = _check(
                _value(d, falt), kalla, lib, register,
                lambda row, d=d, falt=falt: _unit_scale(falt, d, row["enhet"]))
            if avvikelse:
                problem = f"{problem}; {avvikelse}" if problem else avvikelse
            out.append(Bedomning(
                drivare=d.name, falt=falt, varde=_value_text(d, falt), kalla=kalla,
                ursprung=ursprung, problem=problem, underlag=underlag, godkant=avvikelse,
            ))
        for falt in KLIMATFALT:
            avvikelse = bind.get((nr, falt), "")
            if avvikelse:
                out.append(Bedomning(
                    drivare=d.name, falt=falt, varde=_num(getattr(d, falt)), kalla=None,
                    ursprung=None, problem=avvikelse, underlag="", godkant=avvikelse,
                ))
    return out


def summera(bedomningar: list[Bedomning]) -> dict:
    counts = {u.value: 0 for u in Ursprung}
    for b in bedomningar:
        if b.ok and b.ursprung is not None:
            counts[b.ursprung.value] += 1
    counts["kontrollera"] = sum(1 for b in bedomningar if not b.ok)
    counts["totalt"] = sum(1 for b in bedomningar if b.falt not in KLIMATFALT)
    return counts


# What the section says about the comparison with the approved steps
# (caia.godkant), by its outcome. None: no conversation was given.
JAMFORT = {
    "ja": ("Talen är också jämförda med baslinjen och antagandena som godkändes i "
           "steg 3 och 4. Ett tal som avviker tydligt från dem står under Kontrollera först."),
    "utan_baslinje": ("Antagandena är jämförda med dem som godkändes i steg 4. Ett tal som "
                      "avviker tydligt står under Kontrollera först. Aktiviteten och "
                      "emissionsfaktorn basåret kunde inte jämföras, eftersom samtalet saknar en "
                      "godkänd baslinje."),
    "inget": ("Talen kunde inte jämföras med de godkända antagandena, eftersom samtalet "
              "saknar ett godkänt evidenssteg."),
    "fel": ("Talen kunde inte jämföras med de godkända antagandena, på grund av ett fel "
            "i kontrollen."),
}


def render(bedomningar: list[Bedomning], jamfort: str | None = None) -> str:
    """The report section, in markdown. `jamfort` is a key of JAMFORT."""
    c = summera(bedomningar)
    lines = [
        RUBRIK,
        "",
        (f"Kalkylen bygger på {c['totalt']} inmatade tal. "
         f"{c['parameterbibliotek']} kommer ur parameterbiblioteket, "
         f"{c['kommundata']} ur kommunens egen data, "
         f"{c['extern']} från externa källor och "
         f"{c['antagande']} är analysens egna antaganden."
         + (f" {c['kontrollera']} behöver kontrolleras." if c["kontrollera"] else "")),
        "",
        "Resultaten räknas fram av programmet ur de här talen. Klimatfaktorerna "
        "(territoriellt, konsumtion, överlapp) och tidsplanen är metodval och står i kalkylen.",
    ]
    if jamfort in JAMFORT:
        lines += ["", JAMFORT[jamfort]]
    problems = [b for b in bedomningar if not b.ok]
    if problems:
        lines += ["", "### Kontrollera först", ""]
        for b in problems:
            stated = (f" Angivet: {URSPRUNG_TEXT[b.ursprung].lower()}."
                      if b.ursprung is not None else "")
            lines.append(f"- **{b.drivare}, {FALTNAMN[b.falt].lower()}**, värde {b.varde}: "
                         f"{b.problem}.{stated}")
    lines += [
        "",
        "| Drivare | Tal | Värde | Ursprung | Underlag |",
        "|---|---|---|---|---|",
    ]
    for b in bedomningar:
        if b.ok:
            origin = URSPRUNG_TEXT[b.ursprung]
        elif b.falt in KLIMATFALT:
            origin = "Kontrollera (metodval i evidenssteget)"
        elif b.ursprung is not None:
            origin = f"Kontrollera ({URSPRUNG_TEXT[b.ursprung].lower()})"
        else:
            origin = "Saknas"
        underlag = b.underlag if b.ok else "; ".join(x for x in (b.problem, b.underlag) if x)
        lines.append(f"| {_cell(b.drivare)} | {_cell(FALTNAMN[b.falt])} | {_cell(b.varde)} "
                     f"| {_cell(origin)} | {_cell(underlag)} |")
    return "\n".join(lines)


SAKNAS = "\n".join([
    RUBRIK,
    "",
    "Källmarkering saknas för den här körningen. Kalkylen räknades av språkmodellen i "
    "stället för av programmet, så talens ursprung kunde inte kontrolleras mot "
    "parameterbiblioteket. Kör om analysen för att få källmarkeringen.",
])


# For a run where the calc itself worked but this check failed. SAKNAS above
# says the language model did the math, which would then be false.
KONTROLL_FEL = "\n".join([
    RUBRIK,
    "",
    "Källmarkeringen kunde inte tas fram för den här körningen, på grund av ett fel i "
    "kontrollen. Kalkylen är räknad av programmet, men talens ursprung är inte "
    "kontrollerat mot parameterbiblioteket. Kör om analysen för att få källmarkeringen.",
])


def kallmarkering(model: CalcModel, history: list[dict] | None = None
                  ) -> tuple[list[dict], str]:
    """-> (assessments as dicts for the API, the markdown section). With the
    conversation, the numbers are also compared with what was approved."""
    bind = _bindning(model, history)
    if history is None:
        jamfort = None
    elif bind is None:
        jamfort = "fel"
    else:
        jamfort = godkant.omfang(history)
    b = _granska(model, bind or {})
    return [x.as_dict() for x in b], render(b, jamfort)


def kommundata_block() -> str:
    """What the extraction agent may call kommundata, and the library's IDs.

    Built from the active profile, so a profile without local data says so and
    the agent has no local names to borrow."""
    lib = _library()
    lokala = [f"- {pid}: {r['beskrivning']} ({_PROV_TEXT[r['provenance']]}, {r['enhet']})"
              for pid, r in lib.items() if r["provenance"] in ("lokal", "datafil")]
    filer = [f"- {name}: {e.get('beskrivning', '')}"
             for name, e in parse_file_register().items() if e.get("exists") and e.get("read")]
    parts = ["<kommundata>"]
    if lokala or filer:
        parts += ["Kommunens egna värden i parameterbiblioteket:"] + (lokala or ["- (inga)"])
        parts += ["Kommunens datafiler:"] + (filer or ["- (inga)"])
    else:
        parts.append("Kommunen har ingen egen data registrerad. Använd inte ursprung "
                     "\"kommundata\".")
    parts += ["</kommundata>", "", "<parameter_ids>",
              "Parameter_ID som finns i parameterbiblioteket (enhet):"]
    parts += [f"- {pid} ({r['enhet']})" for pid, r in lib.items()]
    parts.append("</parameter_ids>")
    return "\n".join(parts)
