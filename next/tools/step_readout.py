"""Read a step's own answer, and a run's time, answer length and cost, from
saved runs. No model calls: everything comes from files run_batch.py and
replay_step.py already write. The command line is tools/compare_runs.py
(--step, --tid); this module holds the reading.

Step readout (compare_runs.py --step intake|emap|baslinje <dir> ...): when
replay_step.py runs a step with --through the same step there is no headline
number, so the spread has to be read from the step's own answer.

  intake    the questions the intake asks before the profile (history.json),
            and the numbers in each profile's *Omfattning:* with the word
            after them ("120 laddpunkter", "9 Mkr").
  emap      the emission sources (drivers): how many, which, and per source
            its mechanism, emission type, locus and sector. Step 2 sets no
            numbers (its prompt says "utan siffror"); the amounts per source
            are the baseline's.
  baslinje  per source: the baseline year, A0 and EF0 with their units, the
            BAU trends g_A and g_EF (låg, medel, hög, in %/år as written),
            and from them E0 = A0 x EF0 and E 2030 on the medel trends
            (the engine's formula, docs/METOD.md), in the step's own units.

Sources and questions are matched between runs by name (shared words),
not by number: two runs number the same source differently. A source only
some runs have is listed as coming and going, with the runs it is in. A field
a run does not have is shown as "-" and counted, never dropped: the min,
median and max say over how many runs they are.

Time, length and cost (compare_runs.py --tid <dir> ...): per analysis, from
the run.log beside it and its usage.jsonl.

  - Every request to the page: intake (one per round), emap, baslinje, each
    evidens part and the merge (separate requests, so separate limits; the
    "evidens" line after them is the wall time of the step, not a request),
    kalkyl, qa, rapport. The longest per step, flagged at WARN_S, at our own
    timeout (api_client.REQUEST_TIMEOUT_S) and at Vercel's (maxDuration in
    vercel.json).
  - Kalkyl: the model calls inside its one request, from usage.jsonl. When
    the engine cannot compute, a second call (the language model's own
    calc) runs after the extraction in the same request (security review
    S29), and the two together are what has to fit.
  - The evidens merge's answer length in tokens against its cap
    (MERGE_MAX_OUTPUT plus the thinking headroom of its effort), and its
    stop_reason.
  - USD per analysis at list price (the sum of usage.jsonl), against
    WORKSHOP_MEDIAN_USD.

run.log is appended to, so a directory used twice holds two runs of a
package; only the last one is read (usage.jsonl holds only the last one too),
and the readout says how many earlier ones it skipped.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from caia import api_client  # noqa: E402
from caia.agents.evidens_split import MERGE_MAX_OUTPUT  # noqa: E402
from caia.godkant import _SLOT, Block, blocks, numbers  # noqa: E402  (the S21 check's own reading)
from caia.pipeline import BRIDGE, STEPS  # noqa: E402

_REPEAT = re.compile(r"-r\d+$")

# A request this long is close to the limits below: flagged so it is looked
# at before it becomes a timeout. The plan for the next paid run sets it.
WARN_S = 240.0
OUR_LIMIT_S = api_client.REQUEST_TIMEOUT_S
VERCEL_JSON = Path(__file__).resolve().parent.parent / "vercel.json"

# Median cost of an analysis that ran straight through, from the TLF
# workshop's 334 model calls, 2026-10-14 (list price).
WORKSHOP_MEDIAN_USD = 3.9

# The share of the merge's cap from which its length is flagged as near.
NEAR_CAP = 0.8


def vercel_limit_s(path: Path = VERCEL_JSON) -> float | None:
    """maxDuration in vercel.json, wherever in the file it is set."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    found: list[float] = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "maxDuration" and isinstance(v, (int, float)):
                    found.append(float(v))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return min(found) if found else None


def merge_cap() -> int:
    """What the merge may answer before it is cut off: its max_output plus
    the thinking headroom api_client adds for its effort."""
    effort = api_client.AGENT_MODELS["evidens_merge"][1]
    return MERGE_MAX_OUTPUT + api_client.THINKING_HEADROOM.get(effort, 0)


# --- finding runs ---------------------------------------------------------------

@dataclass(frozen=True)
class Run:
    label: str     # "efter2/02-aterbruk": the directory it was given in, and its own
    package: str   # "02-aterbruk": the name without a trailing -rN
    path: Path


def package_of(name: str) -> str:
    return _REPEAT.sub("", name)


def find_runs(dirs: list[Path], marker: str) -> dict[str, list[Run]]:
    """Every directory under `dirs` (or `dirs` themselves) that holds
    `marker`, by package, in the order given."""
    out: dict[str, list[Run]] = {}
    for d in dirs:
        if (d / marker).is_file():
            found = [(d, f"{d.parent.name}/{d.name}")]
        elif d.is_dir():
            found = [(p, f"{d.name}/{p.name}") for p in sorted(d.iterdir())
                     if p.is_dir() and (p / marker).is_file()]
        else:
            found = []
        for path, label in found:
            out.setdefault(package_of(path.name), []).append(Run(label, package_of(path.name), path))
    # The same run directory name under two parents ("fore" in two scratch
    # directories): say which parent, for every package, so one name means
    # one directory all through a readout.
    parents: dict[str, set[Path]] = {}
    for runs in out.values():
        for r in runs:
            parents.setdefault(r.path.parent.name, set()).add(r.path.parent.resolve())
    for runs in out.values():
        runs[:] = [Run(f"{r.path.parent.parent.name}/{r.label}", r.package, r.path)
                   if len(parents[r.path.parent.name]) > 1 else r for r in runs]
    return out


# --- reading numbers --------------------------------------------------------------

_FIRST_DIGIT = re.compile(r"[+\-−–]?\s?\d")
_ZERO = re.compile(r"[+\-−–]?\s?0(?:[.,]0+)?(?![\d.,]|[  ]\d{3}(?!\d))")


def lead(text: str) -> float | None:
    """The first number in `text`, signed. godkant.numbers skips zeros, so a
    leading 0 ("0 %/år", "A0: 0") is read here; without this a zero would
    vanish and the next number in the line would take its place."""
    m = _FIRST_DIGIT.search(text or "")
    if not m:
        return None
    rest = text[m.start():]
    if _ZERO.match(rest):
        return 0.0
    nums = numbers(rest)
    if not nums:
        return None
    return -nums[0].value if nums[0].neg else nums[0].value


_WORD = re.compile(r"[a-zåäöé0-9]{4,}", re.IGNORECASE)


# Compound tails that say what kind of thing, not which: "Elanvändning" and
# "Bränsleanvändning" share "användning" and are different sources.
_GENERIC_TAILS = ("användning", "förbrukning", "utsläpp", "material", "materialet")

# Words that say nothing about which source a name is.
_STOP = frozenset("från till inom utanför genom efter eller över under samt mellan "
                  "kommunens kommunala kommunen".split())


def words(text: str) -> list[str]:
    return [w for w in (x.lower() for x in _WORD.findall(text or "")) if w not in _STOP]


def _same_word(a: str, b: str) -> bool:
    """Same stem, or the same compound part: one word starts the other
    ("bygg", "byggavfall"), sits inside it ("rivning", "rivningsavfall"), or
    both end the same ("byggavfall", "rivningsavfall"): Swedish compounds put
    what a thing is last."""
    if a[:5] == b[:5]:
        return True
    short, long_ = sorted((a, b), key=len)
    if long_.startswith(short):
        return True
    if len(short) >= 5 and short in long_ and short not in _GENERIC_TAILS:
        return True
    tail = 0
    while tail < len(short) and short[-1 - tail] == long_[-1 - tail]:
        tail += 1
    # A shared generic tail alone ("-användning") is not the same word.
    return tail >= 6 and not any(short.endswith(g) and tail <= len(g) + 1 for g in _GENERIC_TAILS)


def similarity(a: str, b: str) -> float:
    """The share of both names' words that the other name also has. Both
    ways, so a short name ("Byggavfall från renoveringar") does not match a
    long one on a single shared word."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 1.0 if a.strip().lower() == b.strip().lower() else 0.0
    hits = (sum(any(_same_word(x, y) for y in wb) for x in wa)
            + sum(any(_same_word(y, x) for x in wa) for y in wb))
    return hits / (len(wa) + len(wb))


MATCH = 0.5  # similarity from which two names are the same source or question


def _sim(a, b) -> float:
    """similarity of two names, or of two tuples of alternative names (a
    question's lead and its whole text): the best pair."""
    if isinstance(a, tuple):
        return max(similarity(x, y) for x, y in zip(a, b))
    return similarity(a, b)


def align(per_run: list[list]) -> list[dict[int, int]]:
    """Group names across runs: each group maps run index -> position of the
    name in that run's list, at most one per run. A name joins the group it
    is most similar to (at least MATCH), best matches first;
    otherwise it starts a group of its own."""
    groups: list[dict[int, int]] = []
    for r, names in enumerate(per_run):
        pairs = []
        for i, name in enumerate(names):
            for g, members in enumerate(groups):
                score = max(_sim(name, per_run[rr][ii]) for rr, ii in members.items())
                if score >= MATCH:
                    pairs.append((score, -i, i, g))
        pairs.sort(reverse=True)
        taken_names: set[int] = set()
        taken_groups: set[int] = set()
        for _, _, i, g in pairs:
            if i in taken_names or g in taken_groups:
                continue
            groups[g][r] = i
            taken_names.add(i)
            taken_groups.add(g)
        for i in range(len(names)):
            if i not in taken_names:
                groups.append({r: i})
    return groups


# --- the steps' own answers --------------------------------------------------

_FIELD = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?(?:\*{1,2}|_{1,2})?[ \t]*([A-Za-zÅÄÖåäö_0-9]+)"
                    r"(?:[ \t]*\([^)\n]*\))?[ \t]*(?:\*{1,2}|_{1,2})?[ \t]*:[ \t]*(.*)$")


def _fields(text: str) -> dict[str, str]:
    """'  key: value' lines of a driver block, key lowercased, first wins."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _FIELD.match(line)
        if m:
            out.setdefault(m.group(1).lower(), m.group(2).strip())
    return out


_MECH = re.compile(r"\b(Avoid|Shift|Improve)\b", re.IGNORECASE)
_DELTA = re.compile(r"Δ\s*(EF|A)(?![a-zåäö])", re.IGNORECASE)


def _mechanism(text: str) -> str:
    kind = _MECH.search(text or "")
    delta = _DELTA.search(text or "")
    parts = [kind.group(1).capitalize() if kind else "", ("Δ" + delta.group(1).upper()) if delta else ""]
    return " ".join(p for p in parts if p)


def _first_words(text: str, n: int = 4) -> str:
    """The value without its parenthetical asides ("båda (ANTAGANDE: ...)"),
    first n words, lowercased: what a categorical field says."""
    bare = re.sub(r"\([^)]*\)?", " ", text or "").replace(",", " ").replace(".", " ")
    return " ".join(bare.split()[:n]).rstrip(";:").lower()


EMAP_FIELDS = ("mekanism", "utsläppstyp", "locus", "sektor")

# Step 2's split rule (2026-10-15) lets one source carry two types, "territoriella
# och konsumtionsbaserade". Two words of that read "territoriella och", and the
# reverse order would count as a difference.
_EMISSION_TYPES = (("territoriell", "territoriella"),
                   ("konsumtionsbaser", "konsumtionsbaserade"),
                   ("kommunens egn", "kommunens egna"),
                   ("kolsänk", "kolsänka"),
                   ("ingen direkt", "ingen direkt"))


def _emission_type(text: str) -> str:
    """The types the field names, in a fixed order joined by "och". A type
    the field says it is not ("inte territoriella") is not one of them, and
    a value that names none reads as before, its first two words."""
    bare = _first_words(text, 12)
    found = [name for stem, name in _EMISSION_TYPES
             if re.search(r"(?<!inte )(?<!ej )\b" + stem, bare)]
    return " och ".join(found) if found else _first_words(text, 2)


def profiled_blocks(text: str, repeats: int = 1) -> list[tuple[int, Block]]:
    """blocks() with the profile each belongs to, from 1. A measure split in
    two profiles numbers its drivers from 1 in each, so the number alone
    does not tell two sources apart.

    A driver can come back `repeats` times in its profile: once in baslinje
    (the BAU block after the nuläge block), never in emap. The first block
    that comes back must have a name like the first time (sometimes a word
    more or less); once one has, the next ones go by number, so one renamed
    BAU block does not start a profile. Anything else with a number no
    higher than the last new one starts the next profile: the drivers of a
    second profile often differ by one word from the first's."""
    out: list[tuple[int, Block]] = []
    profile, last_new, repeating = 1, 0, False
    seen: dict[int, tuple[str, int]] = {}   # number -> (name, times seen), current profile
    for b in blocks(text):
        name, times = seen.get(b.number, ("", 0))
        if 0 < times <= repeats and (repeating or similarity(name, b.name) >= MATCH):
            seen[b.number] = (name, times + 1)
            repeating = True
            out.append((profile, b))
            continue
        if b.number <= last_new:
            profile += 1
            seen = {}
        last_new, repeating = b.number, False
        seen[b.number] = (b.name, 1)
        out.append((profile, b))
    return out


def _label(profile: int, number: int) -> str:
    return f"P{profile} nr {number}" if profile > 1 else f"nr {number}"


def read_emap(text: str) -> list[dict]:
    """Step 2's sources: profile, number, name, and the categorical fields."""
    out = []
    pb = profiled_blocks(text, repeats=0)
    many = len({p for p, _ in pb}) > 1
    for profile, b in pb:
        f = _fields(b.text)
        out.append({"number": b.number, "name": b.name, "profile": profile,
                    "label": _label(profile, b.number) if many else f"nr {b.number}",
                    "mekanism": _mechanism(f.get("mekanism", "")),
                    "utsläppstyp": _emission_type(f.get("utsläppstyp", "")),
                    "locus": _first_words(f.get("locus", ""), 3),
                    "sektor": _first_words(f.get("sektor", ""), 3)})
    return out


_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d|2100)\b")
# "- medel: -0,5 %/år (...)", "låg (konservativ): -1 %/år", or several on one
# line: "låg: -2 %/år, medel: 0 %/år" or "låg -2 %/år, medel -1 %/år". Without
# a colon the level word must be followed by the number, so prose ("hög andel")
# is not read as a level. The value runs to the next level, not to the next
# comma: "-0,5" has one.
_LEVEL_WORD = r"\**(låg|medel|hög)\**(?:[ \t]*\([^)\n]{0,40}\))?"
_LEVEL = re.compile(rf"(?:^|[\s(,;*]){_LEVEL_WORD}[ \t]*(?:[:=][ \t]*|(?=[+\-−–]?[ \t]?\d))"
                    rf"(.*?)(?=[\s(,;*]{_LEVEL_WORD}[ \t]*(?:[:=]|[+\-−–]?[ \t]?\d)|$)",
                    re.IGNORECASE)
# A percent in a trend: "-0,5 %/år", "+3 %", "3-5 %/år", "-2 till -4 %/år".
_PNUM = r"(?<![\d.,])[+\-−–]?[ \t]?\d+(?:[.,]\d+)?"
_PCT = re.compile(rf"({_PNUM})(?:[ \t]*(?:–|-|till)[ \t]*({_PNUM}))?[ \t]*%[ \t]*(/[ \t]*år|per[ \t]+år)?",
                  re.IGNORECASE)


def _num(text: str) -> float:
    return float(re.sub(r"[ \t]", "", text).replace(",", ".").replace("−", "-").replace("–", "-"))


def trend_value(text: str) -> tuple[float | None, str | None]:
    """The %/år a level line gives, and a note when the line needs one. The
    first percent written per year wins, else the first percent at all. No
    percent: None, never a year or a level ("2023–2026 0 %/år" is 0, not
    2023; "+34 MWh/år" is not a trend)."""
    found = [(m, bool(m.group(3))) for m in _PCT.finditer(text or "")]
    if not found:
        return None, "ingen %-trend på raden" if (text or "").strip() else None
    per_year = [m for m, y in found if y]
    m = (per_year or [f for f, _ in found])[0]
    value = _num(m.group(1))
    notes = []
    if m.group(2):
        notes.append(f"spann {m.group(1).strip()} till {m.group(2).strip()} %")
    # Other trends: another per-year percent, or a plain percent before the
    # one read ("0 % till 2026, sedan -10 %/år"). A share after it ("-2 %/år
    # (fossil andel 82 %)") is not a trend.
    others = {_num(x.group(1)) for x, y in found if y or x.start() < m.start()} - {value}
    if others:
        notes.append("flera trender på raden (" + ", ".join(num(v) for v in [value, *sorted(others)])
                     + f"); läst {num(value)}")
    return value, "; ".join(notes) or None


_TREND = re.compile(r"BAU_trend_(EF|A)\b", re.IGNORECASE)
_NEXT_KEY = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?\**(?:BAU_|Kommentar|Nuläge|Källor|A0|EF0)",
                       re.IGNORECASE)

BASLINJE_FIELDS = ("nuläge_år", "a0", "ef0", "g_a_låg", "g_a_medel", "g_a_hög",
                   "g_ef_låg", "g_ef_medel", "g_ef_hög", "e0_ton", "e2030_ton")
UNIT_FIELDS = ("a0_enhet", "ef0_enhet")
TARGET_YEAR = 2030


# Units as the baseline writes them, to the base of their kind. Enough to
# turn A0 x EF0 into ton CO2e when the two units are of the same kind; any
# other pair gives no e0, and the readout says so.
_UNITS = {
    "g": ("massa", 1e-3), "kg": ("massa", 1.0), "t": ("massa", 1e3), "ton": ("massa", 1e3),
    "wh": ("energi", 1e-3), "kwh": ("energi", 1.0), "mwh": ("energi", 1e3), "gwh": ("energi", 1e6),
    "km": ("sträcka", 1.0), "fordonskilometer": ("sträcka", 1.0), "fordonskm": ("sträcka", 1.0),
    "mil": ("sträcka", 10.0), "tonkm": ("tonkm", 1.0),
    "liter": ("volym", 1.0), "l": ("volym", 1.0), "m3": ("volym", 1e3), "m³": ("volym", 1e3),
    "m²": ("yta", 1.0), "m2": ("yta", 1.0), "kvm": ("yta", 1.0),
    "st": ("antal", 1.0), "styck": ("antal", 1.0), "fordon": ("antal", 1.0),
    "laddpunkt": ("antal", 1.0), "laddpunkter": ("antal", 1.0),
    "maskin": ("antal", 1.0), "maskiner": ("antal", 1.0), "bilar": ("antal", 1.0),
    "bil": ("antal", 1.0),
}
_CO2_MASS = {"g": 1e-6, "kg": 1e-3, "t": 1.0, "ton": 1.0}
_EF_UNIT = re.compile(r"^\s*(g|kg|t|ton)\s*CO[2₂]e?(?![a-z])[^/]*/\s*([^\s(/,.;]+)", re.IGNORECASE)
# "A0: 2 Mkm", "1,5 GWh": a prefix glued to the unit, which lead() does not scale.
_PREFIXED = re.compile(r"^\D{0,12}?\d[\d  ]*(?:[.,]\d+)?[ \t]?((?:M|G|k)(?:km|kr|Wh|ton|t\b|l\b))")
_A0_UNIT = re.compile(r"^\s*(?:antal\s+)?([^\s(/,.;]+)")


# "A0: 1 500-3 000 ton": a range where one number is asked for.
_RANGE_FIRST = re.compile(r"^\D{0,12}?\d[\d   ]*(?:[.,]\d+)?(?:e\d+)?\s*[–-]\s*\d")


def to_ton(a0: float | None, a0_unit: str | None, ef0: float | None,
           ef0_unit: str | None) -> float | None:
    """A0 x EF0 in ton CO2e, when EF0's unit is mass of CO2(e) per a unit of
    the same kind as A0's. None otherwise."""
    if None in (a0, ef0) or not a0_unit or not ef0_unit:
        return None
    ef = _EF_UNIT.match(ef0_unit)
    a = _A0_UNIT.match(a0_unit)
    if not ef or not a:
        return None
    den = _UNITS.get(ef.group(2).lower())
    act = _UNITS.get(a.group(1).lower())
    if den is None or act is None or den[0] != act[0]:
        return None
    return a0 * act[1] / den[1] * ef0 * _CO2_MASS[ef.group(1).lower()]


def _trends(text: str) -> tuple[dict[str, float | None], list[str]]:
    """g_A and g_EF per level, from the lines under BAU_trend_A / _EF, or
    the same line ("BAU_trend_A (g_A): låg -2 %/år, medel ..."), and notes
    on lines that were not one plain percent."""
    out: dict[str, float | None] = {}
    notes: list[str] = []
    current = None
    for line in text.splitlines():
        t = _TREND.search(line)
        if t and line.lstrip(" -*").upper().startswith("BAU_TREND"):
            current = "g_a" if t.group(1).upper() == "A" else "g_ef"
            line = line[t.end():]
        elif _NEXT_KEY.match(line):
            current = None
            continue
        if current is None:
            continue
        for m in _LEVEL.finditer(line):
            key = f"{current}_{m.group(1).lower()}"
            if out.get(key) is not None:
                continue
            value, note = trend_value(m.group(2))
            out[key] = value
            if note:
                notes.append(f"{key}: {note}")
    return out, notes


def read_baslinje(text: str) -> list[dict]:
    """Step 3 per source. The answer lists every source twice, nuläge and
    BAU, under the same number; the two blocks are read as one."""
    by_number: dict[tuple[int, int], dict] = {}
    pb = profiled_blocks(text)
    many = len({p for p, _ in pb}) > 1
    for profile, b in pb:
        d = by_number.setdefault((profile, b.number), {
            "number": b.number, "name": b.name, "profile": profile,
            "label": _label(profile, b.number) if many else f"nr {b.number}", "_text": ""})
        d["_text"] += "\n" + b.text
    out = []
    for d in by_number.values():
        text_ = d.pop("_text")
        row: dict = {**d}
        prefixed: list[tuple[str, str, str]] = []
        for line in text_.splitlines():
            m = _SLOT.match(line)
            if m:
                key = m.group(1).lower() + ("_enhet" if m.group(2) else "")
                if key in row:
                    continue
                row[key] = m.group(3).strip() if m.group(2) else lead(m.group(3))
                if not m.group(2) and _RANGE_FIRST.match(m.group(3)):
                    row.setdefault("notes", []).append(
                        f"{key} står som spann ({m.group(3).strip()[:40]}); läst som första talet")
                p = None if m.group(2) else _PREFIXED.match(m.group(3))
                if p:
                    prefixed.append((key, p.group(1), m.group(3).strip()[:30]))
            f = _FIELD.match(line)
            if f and f.group(1).lower() == "nuläge_år" and "nuläge_år" not in row:
                y = _YEAR.search(f.group(2))
                row["nuläge_år"] = float(y.group(1)) if y else None
        for key, unit, written in prefixed:
            # "2 Mkm" where the unit field says km: the number is a million
            # times too small for e0. "40 000 kWh" under "kWh/år" is fine.
            stated = _A0_UNIT.match(row.get(f"{key}_enhet") or "")
            if not stated or stated.group(1).lower() != unit.lower():
                row.setdefault("notes", []).append(
                    f"{key} står med prefix på enheten ({written}); talet är inte omräknat, "
                    "e0 kan vara fel")
        trends, trend_notes = _trends(text_)
        row.update(trends)
        if trend_notes:
            row.setdefault("notes", []).extend(trend_notes)
        row["e0_ton"] = to_ton(row.get("a0"), row.get("a0_enhet"), row.get("ef0"),
                               row.get("ef0_enhet"))
        y0, ga, gef = row.get("nuläge_år"), row.get("g_a_medel"), row.get("g_ef_medel")
        if None not in (row["e0_ton"], y0, ga, gef):
            n = TARGET_YEAR - y0
            row["e2030_ton"] = row["e0_ton"] * (1 + ga / 100) ** n * (1 + gef / 100) ** n
        else:
            row["e2030_ton"] = None
        for k in BASLINJE_FIELDS + UNIT_FIELDS:
            row.setdefault(k, None)
        out.append(row)
    return out


# Numbered items in the intake's question turn: "1. **Hur mäts 20 %?** ...".
_ITEM = re.compile(r"^[ \t]*\d+[.)][ \t]+(.*)$", re.MULTILINE)
_BOLD = re.compile(r"^\*\*(.+?)\*\*")
# Bulleted questions, when none are numbered: "- Hur mäts 20 %?".
_ASKED = re.compile(r"^[ \t]*[-*•][ \t]+(.*\?.*)$", re.MULTILINE)
_QUESTIONS = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*|\*\*)?[^\n]{0,40}\bfrågor\b[^\n]*$",
                        re.IGNORECASE | re.MULTILINE)


def intake_questions(history: list[dict]) -> list[list[tuple[str, str]]]:
    """The questions per clarifying round: every assistant turn before the
    intake's bridge line that the user answered with something else than
    the bridge line. Each question is (its bold lead, else its first
    sentence; the whole numbered item). The item is what runs are matched
    on: two runs can head the same question differently."""
    bridge = BRIDGE["intake"]
    rounds = []
    for turn, nxt in zip(history, history[1:]):
        if not (isinstance(turn, dict) and isinstance(nxt, dict)):
            continue
        content = nxt.get("content") if isinstance(nxt.get("content"), str) else ""
        if content.strip() == bridge:
            break
        if turn.get("role") == "assistant" and nxt.get("role") == "user":
            qs = []
            text = turn.get("content") or ""
            head = _QUESTIONS.search(text)
            # The turn can number other things first (the profiles of a split
            # measure); the questions are what follows their heading.
            section = text[head.end():] if head else text
            items = _ITEM.findall(section) or _ASKED.findall(section)
            for item in items:
                b = _BOLD.match(item.strip())
                q = b.group(1) if b else re.split(r"(?<=[?.])\s", item.strip(), maxsplit=1)[0]
                qs.append((q.strip().rstrip(":").strip(), item.strip()))
            rounds.append(qs)
    return rounds


_PROFILE = re.compile(r"^\s*ÅTGÄRDSPROFIL\b", re.MULTILINE)
_OMF = re.compile(r"^\*Omfattning:\*(.*?)(?=^\*[A-ZÅÄÖ][^*\n]{0,40}:\*|^\s*ÅTGÄRDSPROFIL|\Z)",
                  re.MULTILINE | re.DOTALL)
_AMOUNT = re.compile(r"(\d[\d   ]*(?:[.,]\d+)?)(?:[ \t]*[–-][ \t]*(\d[\d   ]*(?:[.,]\d+)?))?[ \t]*(%?)[ \t]*"
                     r"([A-Za-zÅÄÖåäö²]+((?:[ \t]+[A-Za-zÅÄÖåäö²]+){0,2}))")


# Words after a number that say nothing about what it counts.
_OMF_SKIP = frozenset("av i på per och till om med för än de den det dem alla våra deras".split())


def _span(v: tuple[float, float | None]) -> str:
    return num(v[0]) if v[1] is None else f"{num(v[0])}-{num(v[1])}"


def omfattning(intake_md: str) -> list[tuple[bool, list[tuple[str, tuple[float, float | None]]]]]:
    """Per profile: whether it has *Omfattning:*, and (word after the
    number, (number, upper end of a range or None)) for every number in it.
    A profile without the field (the profiles before 2026-10-13 had none)
    gives (False, []): numbers from the rest of the profile are not scope."""
    parts = _PROFILE.split(intake_md)
    parts = [p for p in parts if p.strip()] or [intake_md]
    out = []
    for p in parts:
        m = _OMF.search(p)
        pairs = []
        for a in _AMOUNT.finditer(m.group(1) if m else ""):
            lo = lead(a.group(1))
            hi = lead(a.group(2)) if a.group(2) else None
            # "30 % av de boende": the number counts the first word after it
            # that is not a small word.
            word = next((w for w in a.group(4).lower().split() if w not in _OMF_SKIP), "-")
            if a.group(3):
                # A share is not a count: "5-10 % av bilarna" is not 5 cars.
                word = f"% {word}"
            if lo is not None and not _YEAR.fullmatch(a.group(1).strip()):
                # A range is kept whole: "0,6-0,8 bilar" is not "0,6 bilar".
                pairs.append((word, (lo, hi)))
        out.append((m is not None, pairs))
    return out


# --- formatting ----------------------------------------------------------------

def num(v: float | None) -> str:
    if v is None:
        return "-"
    a = abs(v)
    if a >= 1000:
        s = f"{round(v):,}".replace(",", " ")
    elif a >= 100 or v == int(v):
        s = f"{v:.0f}"
    elif a >= 1:
        s = f"{v:.2f}".rstrip("0").rstrip(".")
    else:
        s = f"{v:.3g}"
    return s


def stats(values: list[float | None]) -> dict:
    """min, median, max over the runs that have the value, and how many
    do not. max/min only when every value is above zero."""
    have = [v for v in values if v is not None]
    out = {"n": len(have), "saknas": len(values) - len(have)}
    if have:
        lo, hi = min(have), max(have)
        out.update(min=lo, median=statistics.median(have), max=hi,
                   ratio=hi / lo if lo > 0 else None)
    return out


def _run_header(runs: list[Run]) -> list[str]:
    return [f"  [{i + 1}] {r.label}" for i, r in enumerate(runs)]


def _presence(group: dict[int, int], n: int) -> str:
    if len(group) == n:
        return f"i alla {n}"
    return "i " + ", ".join(f"[{r + 1}]" for r in sorted(group)) + f" av {n}"


def _name_of(group: dict[int, int], names: list[list[str]]) -> str:
    r = min(group)
    return names[r][group[r]]


NEAR = 0.35  # similarity below MATCH worth pointing out as a possible same source


def _near_misses(groups: list[dict[int, int]], names: list[list[str]], come_go: list[int],
                 prefix: str) -> list[str]:
    """For two groups that never share a run, and whose names are close
    without being MATCH: a line saying so, so a renamed source is not read
    as one that came and went without a look."""
    out = []
    for a_i, a in enumerate(come_go):
        for b in come_go[a_i + 1:]:
            ga, gb = groups[a], groups[b]
            if set(ga) & set(gb):
                continue
            score = max(_sim(names[ra][ia], names[rb][ib])
                        for ra, ia in ga.items() for rb, ib in gb.items())
            if score >= NEAR:
                out.append(f"  {prefix}{a + 1} och {prefix}{b + 1} är aldrig med samtidigt och liknar "
                           f"varandra (likhet {score:.2f}): kanske samma, läs namnen.")
    return out


def format_sources(package: str, runs: list[Run], rows: list[list[dict]], step: str,
                   numeric: tuple[str, ...], categorical: tuple[str, ...],
                   units: tuple[str, ...] = ()) -> str:
    n = len(runs)
    names = [[d["name"] for d in r] for r in rows]
    groups = align(names)
    title = {"emap": "utsläppskällor (steg 2)", "baslinje": "baslinje (steg 3)"}[step]
    counts = [len(r) for r in rows]
    lines = [f"== {package}: {title}, {n} körningar", *_run_header(runs),
             "Antal källor: " + ", ".join(f"[{i + 1}] {c}" for i, c in enumerate(counts))
             + f"  (min {min(counts)}, max {max(counts)})" if counts else "Antal källor: -"]
    lines.append("Källor (matchade på namn, inte nummer):")
    for k, g in enumerate(groups):
        nums = ", ".join(f"[{r + 1}] {rows[r][i]['label']}" for r, i in sorted(g.items()))
        lines.append(f"  K{k + 1} {_name_of(g, names)[:70]}  ({_presence(g, n)}; {nums})")
    come_go = [k for k, g in enumerate(groups) if len(g) < n]
    lines.append("Kommer och går: " + (", ".join(f"K{k + 1}" for k in come_go) if come_go
                                       else "inga, samma källor varje gång"))
    lines += _near_misses(groups, names, come_go, "K")
    for k, g in enumerate(groups):
        cells = {r: rows[r][i] for r, i in g.items()}
        sub = []
        for f in categorical:
            vals = {r: (cells[r].get(f) or "-") for r in cells}
            if len(set(vals.values())) > 1:
                sub.append(f"    {f}: " + "  ".join(f"[{r + 1}] {v}" for r, v in sorted(vals.items()))
                           + "  SKILJER")
        for f in units:
            vals = {r: (cells[r].get(f) or "-") for r in cells}
            short = {r: _first_words(v, 3) for r, v in vals.items()}
            if len(set(short.values())) > 1:
                sub.append(f"    {f}: " + "  ".join(f"[{r + 1}] {v[:40]}" for r, v in sorted(vals.items()))
                           + "  SKILJER")
        for f in numeric:
            show = (lambda v: "-" if v is None else str(int(v))) if f.endswith("_år") else num
            vals = [cells[r].get(f) if r in cells else None for r in range(n)]
            present = [vals[r] for r in cells]
            s = stats(present)
            per = "  ".join(f"[{r + 1}] {show(vals[r])}" for r in sorted(cells))
            if s["n"] == 0:
                sub.append(f"    {f:10} {per}  (saknas i alla)")
                continue
            miss = f"  saknas i {s['saknas']}" if s["saknas"] else ""
            if len(cells) == 1:
                sub.append(f"    {f:10} {per}{miss}")
                continue
            if s["min"] == s["max"]:
                sub.append(f"    {f:10} {per}   lika{miss}")
                continue
            ratio = f"  max/min {num(s['ratio'])}" if s.get("ratio") and not f.endswith("_år") else ""
            sub.append(f"    {f:10} {per}   min {show(s['min'])}  median {show(s['median'])}  "
                       f"max {show(s['max'])}{ratio}{miss}")
        for r in sorted(cells):
            for note in cells[r].get("notes") or []:
                sub.append(f"    [{r + 1}] {note}")
        if "e0_ton" in numeric:
            unread = [r for r in sorted(cells) if cells[r].get("e0_ton") is None
                      and cells[r].get("a0") is not None and cells[r].get("ef0") is not None]
            for r in unread:
                sub.append(f"    e0 går inte att räkna i [{r + 1}]: enheterna "
                           f"{(cells[r].get('a0_enhet') or '-')[:30]!r} och "
                           f"{(cells[r].get('ef0_enhet') or '-')[:30]!r} går inte ihop")
        if sub:
            lines.append(f"  K{k + 1} {_name_of(g, names)[:60]}")
            lines += sub
    return "\n".join(lines)


def readout_emap(runs: list[Run]) -> tuple[list[list[dict]], str]:
    rows = [read_emap((r.path / "emap.md").read_text(encoding="utf-8")) for r in runs]
    return rows, format_sources(runs[0].package, runs, rows, "emap", (), EMAP_FIELDS)


def readout_baslinje(runs: list[Run]) -> tuple[list[list[dict]], str]:
    rows = [read_baslinje((r.path / "baslinje.md").read_text(encoding="utf-8")) for r in runs]
    text = format_sources(runs[0].package, runs, rows, "baslinje", BASLINJE_FIELDS, (), UNIT_FIELDS)
    sums = []
    for i, r in enumerate(rows):
        known = [d["e0_ton"] for d in r if d["e0_ton"] is not None]
        left = len(r) - len(known)
        sums.append(f"[{i + 1}] {num(sum(known)) if known else '-'} över {len(known)} källor"
                    + (f" ({left} gick inte att räkna)" if left else ""))
    text += ("\nSumma e0_ton per körning: " + ", ".join(sums)
             + "\n  (summan av källorna, inte en baslinje: källor kan överlappa, till exempel samma "
             "kilometer territoriellt och i konsumtionen, och antalet källor skiljer. Jämför "
             "källa mot källa.)")
    note = (f"  (e0_ton = a0 x ef0 i ton CO2e/år, e2030_ton = e0 framskrivet med "
            f"medeltrenderna till {TARGET_YEAR}; a0 och ef0 i stegets egna enheter, "
            "trender i %/år som de står)")
    return rows, text + "\n" + note


def readout_intake(runs: list[Run]) -> tuple[list[dict], str]:
    n = len(runs)
    data = []
    for r in runs:
        hist_path = r.path / "history.json"
        try:
            history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.is_file() else None
        except ValueError:
            history = None
        rounds = intake_questions(history) if isinstance(history, list) else None
        md = (r.path / "intake.md").read_text(encoding="utf-8")
        data.append({"rounds": rounds, "profiles": len(_PROFILE.findall(md)) or 1,
                     "omfattning": omfattning(md)})
    lines = [f"== {runs[0].package}: intag (steg 1), {n} körningar", *_run_header(runs)]
    lines.append("Frågerundor: " + ", ".join(
        f"[{i + 1}] {len(d['rounds']) if d['rounds'] is not None else '- (ingen läsbar history.json)'}"
        for i, d in enumerate(data)))
    for i, d in enumerate(data):
        for k, rnd in enumerate(d["rounds"] or []):
            if not rnd:
                lines.append(f"  [{i + 1}] runda {k + 1}: inga frågor gick att läsa (varken numrerade "
                             "eller punkter med frågetecken)")
    lines.append("Profiler: " + ", ".join(f"[{i + 1}] {d['profiles']}" for i, d in enumerate(data)))
    qs = [[q for rnd in (d["rounds"] or []) for q in rnd] for d in data]
    known = [i for i, d in enumerate(data) if d["rounds"] is not None]
    groups = align([qs[i] for i in known])
    lines.append("Frågor (matchade på ord):")
    for k, g in enumerate(groups):
        g_runs = {known[r]: i for r, i in g.items()}
        first = min(g_runs)
        pres = ("i alla " + str(len(known)) if len(g_runs) == len(known)
                else "i " + ", ".join(f"[{r + 1}]" for r in sorted(g_runs)) + f" av {len(known)}")
        lines.append(f"  F{k + 1} {qs[first][g_runs[first]][0][:80]}  ({pres})")
    come_go = [k for k, g in enumerate(groups) if len(g) < len(known)]
    lines.append("Kommer och går: " + (", ".join(f"F{k + 1}" for k in come_go) if come_go else "inga"))
    lines += _near_misses(groups, [qs[i] for i in known], come_go, "F")
    lines.append("Omfattning i profilen (tal och ordet efter):")
    max_p = max(len(d["omfattning"]) for d in data)
    for p in range(max_p):
        per_run = []
        whole = []
        for i, d in enumerate(data):
            prof = d["omfattning"][p] if p < len(d["omfattning"]) else None
            if prof is not None and not prof[0]:
                whole.append(f"[{i + 1}]")
            per_run.append(prof[1] if prof is not None else None)
        words: list[str] = []
        for prof in per_run:
            for w, _ in prof or []:
                if w[:5] not in [x[:5] for x in words]:
                    words.append(w)
        label = f"  profil {p + 1}:" if max_p > 1 else ""
        if label:
            lines.append(label)
        if whole:
            lines.append(f"    ingen Omfattning i {', '.join(whole)}")
        if not words:
            lines.append("    (inga tal)")
        for w in words:
            cells = []
            for i, prof in enumerate(per_run):
                if prof is None:
                    cells.append(f"[{i + 1}] (ingen profil)")
                    continue
                vals = sorted({v for ww, v in prof if ww[:5] == w[:5]}, key=lambda v: (v[0], v[1] or 0))
                cells.append(f"[{i + 1}] " + ("/".join(_span(v) for v in vals) if vals else "-"))
            # The same numbers once or twice are the same: "180/180" is "180".
            sets = {frozenset(v for ww, v in (prof or []) if ww[:5] == w[:5]) for prof in per_run}
            flag = "  SKILJER" if len(sets) > 1 else ""
            lines.append(f"    {w[:14]:14} " + "  ".join(cells) + flag)
    return data, "\n".join(lines)


READOUTS = {"intake": ("intake.md", readout_intake),
            "emap": ("emap.md", readout_emap),
            "baslinje": ("baslinje.md", readout_baslinje)}


def step_readout(step: str, dirs: list[Path], package: str | None = None) -> str | None:
    marker, fn = READOUTS[step]
    runs = find_runs(dirs, marker)
    if package:
        runs = {k: v for k, v in runs.items() if k == package}
    if not runs:
        return None
    return "\n\n".join(fn(rs)[1] for _, rs in sorted(runs.items()))


# --- time, length and cost ---------------------------------------------------

_LOG = re.compile(r"^\[(\d\d:\d\d:\d\d)\] (\S+): (.*)$")
_REQ = re.compile(r"^(?:(evidens) (part \d+|merge)|(\w+))\s+([\d.]+)s\b")


@dataclass
class Request:
    step: str        # intake, emap, baslinje, evidens_part, evidens_merge, evidens, kalkyl, qa, rapport
    what: str        # "part 3", "merge", "" ...
    seconds: float


@dataclass
class RunTiming:
    requests: list[Request] = field(default_factory=list)
    skipped: int = 0        # earlier runs of the same label in run.log
    log: bool = False       # a run.log line was found at all


def _order(step: str) -> int:
    base = step.split("_")[0]
    return STEPS.index(base) if base in STEPS else -1


def parse_run_log(text: str, label: str) -> RunTiming:
    """The page requests of `label`'s last run in a run.log. A new run starts
    when a step comes back that is earlier in the chain than the last one
    (a second intake round is not a new run, a second intake after emap is),
    or after a DONE line."""
    segments: list[list[Request]] = [[]]
    last = -1
    done = False
    split_mode = False  # evidens parts seen since the last evidens line
    found = False
    for line in text.splitlines():
        m = _LOG.match(line)
        if not m or m.group(2) != label:
            continue
        found = True
        msg = m.group(3).strip()
        if msg.startswith("DONE"):
            done = True
            continue
        if " failed" in msg or msg.startswith("evidens: no drivers"):
            # A failed or fallen-back split: an evidens line after this is a
            # call of its own, not the wall time of parts and merge.
            split_mode = False
        r = _REQ.match(msg)
        if not r:
            continue
        if r.group(1):
            step, what = ("evidens_part" if r.group(2).startswith("part") else "evidens_merge"), r.group(2)
        else:
            step, what = r.group(3), ""
            if step not in STEPS:
                continue
        o = _order(step)
        if done or (segments[-1] and o < last):
            segments.append([])
            split_mode = False
        done = False
        last = o
        if step in ("evidens_part", "evidens_merge"):
            split_mode = True
        if step == "evidens" and split_mode:
            # The step's wall time after its parts and merge: not a request.
            split_mode = False
            continue
        segments[-1].append(Request(step, what, float(r.group(4))))
    segments = [s for s in segments if s] or [[]]
    return RunTiming(segments[-1], len(segments) - 1, found)


def read_usage(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"step": "?", "unreadable": True})
    return out


def flag_seconds(s: float, vercel: float | None) -> str:
    if vercel is not None and s >= vercel:
        return "ÖVER VERCELS GRÄNS"
    if s >= OUR_LIMIT_S:
        return "ÖVER VÅR GRÄNS"
    if s >= WARN_S:
        return "NÄRA"
    return ""


def timing(run: Run) -> dict:
    """Everything --tid says about one analysis, as data."""
    log_path = run.path.parent / "run.log"
    own = run.path / "run.log"
    text = ""
    for p in (log_path, own):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if run.path.name in text:
                break
    t = parse_run_log(text, run.path.name) if text else RunTiming()
    usage = read_usage(run.path / "usage.jsonl")
    meta_path = run.path / "kalkyl_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    except ValueError:
        meta = None
    longest: dict[str, Request] = {}
    for q in t.requests:
        if q.step not in longest or q.seconds > longest[q.step].seconds:
            longest[q.step] = q
    out = {"run": run, "log": t.log, "skipped": t.skipped, "longest": longest,
           "requests": t.requests, "usage": usage,
           "deterministic": None if meta is None else meta.get("deterministic")}
    if usage is not None:
        kalkyl_calls = [r for r in usage if (r.get("step") or "").split("_")[0] == "kalkyl"]
        merges = [r for r in usage if r.get("step") == "evidens_merge"]
        out["kalkyl_calls"] = kalkyl_calls
        out["merges"] = merges
        out["usd"] = sum(r.get("usd") or 0 for r in usage)
        out["unpriced"] = sum(1 for r in usage if r.get("usd") is None)
        out["errors"] = sum(1 for r in usage if "error" in r or r.get("unreadable"))
    return out


TIME_STEPS = ("intake", "emap", "baslinje", "evidens_part", "evidens_merge", "evidens",
              "kalkyl", "qa", "rapport")


def format_timing(results: list[dict]) -> str:
    vercel = vercel_limit_s()
    cap = merge_cap()
    lines = [f"Tid per anrop till sidan (längsta per steg, sekunder). Flagga från {num(WARN_S)} s; "
             f"vår gräns {num(OUR_LIMIT_S)} s; Vercels {num(vercel) if vercel else '?'} s.",
             f"Sammanslagningens tak: {cap} tokens. Kostnad mot {num(WORKSHOP_MEDIAN_USD)} USD "
             "(workshopens median per analys)."]
    for res in results:
        run: Run = res["run"]
        lines.append(f"\n== {run.label}")
        if res["skipped"]:
            lines.append(f"  run.log har {res['skipped']} tidigare körning(ar) av samma analys; "
                         "bara den sista läses.")
        if not res["log"]:
            lines.append("  ingen rad i run.log för den här analysen: tiden okänd.")
        else:
            for step in TIME_STEPS:
                q = res["longest"].get(step)
                if q is None:
                    continue
                count = sum(1 for r in res["requests"] if r.step == step)
                many = f" (längst av {count})" if count > 1 else ""
                flag = flag_seconds(q.seconds, vercel)
                what = f" {q.what}" if q.what and q.step != "evidens_merge" else ""
                lines.append(f"  {step:14} {q.seconds:6.1f}{many}{what}  {flag}".rstrip())
            missing = [s for s in ("intake", "emap", "baslinje", "kalkyl", "qa", "rapport")
                       if s not in res["longest"]]
            if missing:
                lines.append("  inga anrop i run.log för: " + ", ".join(missing))
        if res["usage"] is None:
            lines.append("  ingen usage.jsonl: kalkylens anrop, sammanslagningens längd och "
                         "kostnaden okända.")
            if res["deterministic"] is False:
                lines.append("  kalkylen föll tillbaka på språkmodellen (deterministic false): "
                             "två modellanrop i samma anrop till sidan.")
            continue
        kc = res["kalkyl_calls"]
        if kc:
            parts = " + ".join(f"{r.get('step')} {r.get('seconds') or 0:.1f}" for r in kc)
            total = sum(r.get("seconds") or 0 for r in kc)
            two = "  TVÅ MODELLANROP" if len(kc) > 1 else ""
            lines.append(f"  kalkyl, modellanropen: {parts} = {total:.1f} s{two}  "
                         f"{flag_seconds(total, vercel)}".rstrip())
        elif res["deterministic"] is not None:
            lines.append("  kalkyl: inga modellanrop i usage.jsonl")
        for r in res["merges"]:
            out_t = r.get("output")
            if out_t is None:
                lines.append(f"  sammanslagning: inga tokens (fel: {r.get('error', '?')})")
                continue
            share = out_t / cap
            flag = "  I TAKET" if r.get("stop_reason") == "max_tokens" else (
                "  NÄRA TAKET" if share >= NEAR_CAP else "")
            lines.append(f"  sammanslagning {out_t} av {cap} tokens ({share:.0%}), "
                         f"{r.get('seconds') or 0:.1f} s, stop_reason {r.get('stop_reason')}{flag}")
        if not res["merges"]:
            lines.append("  sammanslagning: inget anrop i usage.jsonl")
        usd = res["usd"]
        rel = usd / WORKSHOP_MEDIAN_USD
        lines.append(f"  kostnad {usd:.2f} USD ({rel:.0%} av {num(WORKSHOP_MEDIAN_USD)}), "
                     f"{len(res['usage'])} modellanrop")
        if res["unpriced"]:
            lines.append(f"  {res['unpriced']} anrop utan pris räknade som 0: kostnaden är en undre gräns.")
        if res["errors"]:
            lines.append(f"  {res['errors']} modellanrop slutade med fel eller gick inte att läsa.")
    if len(results) > 1:
        lines += ["", f"Över alla {len(results)} analyser:"]
        for step in TIME_STEPS:
            best = max(((res["longest"][step], res["run"]) for res in results if step in res["longest"]),
                       key=lambda x: x[0].seconds, default=None)
            if best:
                q, run = best
                lines.append(f"  {step:14} {q.seconds:6.1f}  {run.label}  "
                             f"{flag_seconds(q.seconds, vercel)}".rstrip())
        costs = [res["usd"] for res in results if res.get("usage") is not None]
        if costs:
            lines.append(f"  kostnad per analys: min {min(costs):.2f}, median "
                         f"{statistics.median(costs):.2f}, max {max(costs):.2f} USD över {len(costs)} "
                         f"(av {len(results)}; resten saknar usage.jsonl)"
                         if len(costs) < len(results) else
                         f"  kostnad per analys: min {min(costs):.2f}, median "
                         f"{statistics.median(costs):.2f}, max {max(costs):.2f} USD över {len(costs)}")
    return "\n".join(lines)


def time_readout(dirs: list[Path], package: str | None = None) -> str | None:
    # An analysis directory has history.json (run_batch and replay write it
    # on success and on failure alike).
    runs = find_runs(dirs, "history.json")
    if package:
        runs = {k: v for k, v in runs.items() if k == package}
    flat = [r for _, rs in sorted(runs.items()) for r in rs]
    if not flat:
        return None
    return format_timing([timing(r) for r in flat])
