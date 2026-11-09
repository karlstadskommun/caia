"""Unit words the calc can reason about, shared by the source check
(caia.kallmarkering) and the calc's own warnings (calc.engine).

Units are free text written by the extraction model ("ton nyvara/år",
"kg CO2e/kWh el"). Only the first word of a unit part is read, and only the
words in PREFIX are understood. Everything else is treated as a count word
(handlare, resor, fordonskm) that this module cannot convert.
"""
from __future__ import annotations

import re

# word -> (quantity, size in the quantity's base unit: kg or kWh)
PREFIX = {
    "g": ("massa", 1e-3), "kg": ("massa", 1.0), "t": ("massa", 1e3), "ton": ("massa", 1e3),
    "wh": ("energi", 1e-3), "kwh": ("energi", 1.0), "mwh": ("energi", 1e3),
    "gwh": ("energi", 1e6),
}

QUANTITY_TEXT = {"massa": "vikt", "energi": "energi"}


def prefix(part: str) -> tuple[str, float] | None:
    """The quantity and size of the first word of `part`, or None."""
    words = part.replace("(", " ").split()
    return PREFIX.get(words[0].lower()) if words else None


# "/" or the word "per" separates a quantity from what it is per.
_PER = re.compile(r"\s*/\s*|\s+per\s+", re.IGNORECASE)
# Ton-kilometres in any spelling ("ton km", "ton-km", "t·km", "tkm") are one
# count word, never ton.
_TONKM = re.compile(r"(?<![a-zåäö])(?:ton|t)\s*[-·*×.]?\s*km(?![a-zåäö])", re.IGNORECASE)
# A unit word: a letter, then letters (Swedish included), digits and ²/³.
# Hyphens and underscores end it, so "kWh-el" and "kWh_el" read as kWh. A
# part that starts with a number ("1000 kg") has no leading unit word.
_WORD = re.compile(r"[a-zåäöéü][0-9a-zåäöéü²³₂]*", re.IGNORECASE)
_FIRST = re.compile(r"\s*\(?\s*([a-zåäöéü][0-9a-zåäöéü²³₂]*)", re.IGNORECASE)
# Other spellings of the words in PREFIX, and the CO2e glued to a mass
# ("tCO2e", "kgCO2e"). Read only here: the source check's table is PREFIX.
_ALIAS = {
    "gram": "g", "kilo": "kg", "kilogram": "kg", "tonne": "ton", "tonnes": "ton",
    "wattimme": "wh", "wattimmar": "wh",
    "kilowattimme": "kwh", "kilowattimmar": "kwh", "megawattimme": "mwh",
    "megawattimmar": "mwh", "gigawattimme": "gwh", "gigawattimmar": "gwh",
}
_CO2 = re.compile(r"co(?:2|₂)(?:e|ekv|-?ekv)?$", re.IGNORECASE)


def _known(word: str) -> tuple[str, float] | None:
    w = word.lower()
    if w not in PREFIX and w not in _ALIAS and _CO2.search(w):
        w = _CO2.sub("", w)
    return PREFIX.get(_ALIAS.get(w, w))


# A bare t or g joined to a word by a hyphen ("T-shirts", "t-bana") is part
# of that word, not a ton or a gram.
_BARE_HYPHEN = re.compile(r"(?<![0-9a-zåäöéü])([tg])-(?=[a-zåäöéü])", re.IGNORECASE)


def _norm(part: str) -> str:
    return _BARE_HYPHEN.sub(r"\1", _TONKM.sub("tonkm", part or ""))


def _word(part: str) -> str:
    m = _FIRST.match(_norm(part))
    return m.group(1) if m else ""


def _known_anywhere(part: str) -> str:
    """The first mass or energy word anywhere in `part`, or ""."""
    for w in _WORD.findall(_norm(part)):
        if _known(w):
            return w
    return ""


# Words that name no unit: "kg CO2e/enhet" is the schema's default when the
# extraction gives no unit, and says nothing about which unit is meant.
_GENERIC = {"enhet", "enheten", "enheter", "unit"}


def _a0_part(a0_unit: str) -> str:
    return _PER.split(_norm(a0_unit), maxsplit=1)[0]


def a0_word(a0_unit: str) -> str:
    """The unit the activity is counted in: the first word before '/år'."""
    return _word(_a0_part(a0_unit))


def _ef0_split(ef0_unit: str) -> list[str]:
    return _PER.split(_norm(ef0_unit), maxsplit=1)


def ef0_parts(ef0_unit: str) -> tuple[str, str] | None:
    """(numerator word, denominator word) of an emission factor unit, or None
    when the unit has no denominator to compare."""
    parts = _ef0_split(ef0_unit)
    if len(parts) < 2:
        return None
    num, den = _word(parts[0]), _word(parts[1])
    return (num, den) if den else None


def _compare(a_word: str, den: str) -> dict | None:
    a, e = _known(a_word), _known(den)
    if a[0] != e[0]:
        return {"kind": "quantity", "a0": a_word, "ef0": den, "factor": None}
    if a[1] != e[1]:
        return {"kind": "prefix", "a0": a_word, "ef0": den,
                "factor": max(a[1], e[1]) / min(a[1], e[1])}
    return None


def mismatch(a0_unit: str, ef0_unit: str) -> dict | None:
    """Why the activity's unit and the emission factor's unit do not fit
    together, or None.

    The engine multiplies A0 by EF0 and reads the product as kg CO2e. That is
    only right when EF0 is in kg CO2e per the unit A0 is counted in. Three
    cases are reported, all of them only between words this module knows:

      prefix    both are mass or both energy, at different sizes (ton vs kg,
                MWh vs kWh): the result is off by a known factor.
      quantity  both are known, of different quantities (kg vs kWh).
      count     one is a known mass or energy word and the other side holds
                none anywhere (handlare vs kg): the activity is a count and
                the factor is per a weight, or the other way round.

    The first word of each side is read. When only one of them is a mass or
    energy word, the other side is searched for one before it is called a
    count: "el (kWh/år)" and "Antal ton/år" are compared as kWh and ton.
    Two count words are never compared (personer vs invånare, km vs
    fordonskm): they are free text, and a guess there would warn on correct
    analyses. Returns {'kind', 'a0', 'ef0', 'factor'}: the two words as
    written, and the size of the error when it is known, else None."""
    split = _ef0_split(ef0_unit)
    parts = ef0_parts(ef0_unit)
    a_word = a0_word(a0_unit)
    if parts is None or not a_word:
        return None
    den = parts[1]
    if a_word.lower() in _GENERIC or den.lower() in _GENERIC:
        return None
    a, e = _known(a_word), _known(den)
    if a is None and e is None:
        return None
    if a is None:
        a_word = _known_anywhere(_a0_part(a0_unit)) or a_word
    elif e is None:
        den = _known_anywhere(split[1]) or den
    if _known(a_word) and _known(den):
        return _compare(a_word, den)
    return {"kind": "count", "a0": a_word, "ef0": den, "factor": None}


def a0_scale(a0_unit: str, ef0_unit: str) -> dict | None:
    """What A0 must be multiplied by to be counted in the unit EF0 is per,
    when the two are the same quantity at different sizes (ton against kg,
    MWh against kWh), or None.

    The warning alone did not help: krisberedskap (driftsmedel run 2,
    2026-10-21) had 210 ton/år against 2,1 kg CO2e/kg, the warning was
    written, and the result still counted 0,44 ton instead of 441. Both
    times this has been seen, the units were right and the conversion was
    missing, so the engine converts on the units as written and says so.
    Returns {'factor', 'a0', 'ef0'}: the multiplier and the two words."""
    m = mismatch(a0_unit, ef0_unit)
    if m is None or m['kind'] != 'prefix':
        return None
    a, e = _known(m['a0']), _known(m['ef0'])
    return {'factor': a[1] / e[1], 'a0': m['a0'], 'ef0': m['ef0']}


# Money as an activity: "kr", "kronor", "SEK", "tkr". An emission post counted
# in kronor is the grant's "own emissions" (amount × kg per krona), which the
# follow-up keeps out of the result (calc.schema.CalcModel.from_dict).
_MONEY = {"kr": 1.0, "kronor": 1.0, "krona": 1.0, "sek": 1.0,
          "tkr": 1e3, "ksek": 1e3, "mkr": 1e6, "mnkr": 1e6, "msek": 1e6}
# A count before the money word: "100 kr", "1 000 kr", "tusen kronor".
_COUNT_OF = re.compile(r"^\s*(\d+(?:[ \u00a0]\d{3})*|tusen|miljon|miljoner)\s+([a-zåäö]+)",
                       re.IGNORECASE)
_COUNT_WORD = {"tusen": 1e3, "miljon": 1e6, "miljoner": 1e6}


def _kronor_of(part: str) -> float | None:
    """Kronor per unit of one unit part ("kr", "tkr", "100 kr"), or None."""
    per = _MONEY.get(_word(part).lower())
    if per is not None:
        return per
    m = _COUNT_OF.match(_norm(part))
    if m and m[2].lower() in _MONEY:
        count = _COUNT_WORD.get(m[1].lower()) or float(re.sub(r"\D", "", m[1]))
        return count * _MONEY[m[2].lower()]
    return None


def kronor_per_unit(a0_unit: str) -> float | None:
    """Kronor per unit when the activity is counted in money, else None. A
    unit of "100 kr" is 100 (Testcyklisterna, run 2: 600 × 100 kr of gift
    cards against 3 kg CO2e per 100 kr)."""
    return _kronor_of(_a0_part(a0_unit))


def ef0_kronor(ef0_unit: str) -> float | None:
    """Kronor per unit of what an emission factor is per ("kg CO2e/tkr":
    1000), or None when it is not per an amount of money."""
    parts = _ef0_split(ef0_unit)
    return _kronor_of(parts[1]) if len(parts) > 1 else None


def is_money(a0_unit: str) -> bool:
    """Whether the activity is counted in money."""
    return kronor_per_unit(a0_unit) is not None


def numerator_mismatch(ef0_unit: str) -> dict | None:
    """The emission factor's numerator when it is a mass other than kg
    (g CO2e/kWh, ton CO2e/MWh, tCO2e/MWh). The engine reads EF0 as kg CO2e
    per unit."""
    parts = ef0_parts(ef0_unit)
    if parts is None:
        return None
    n = _known(parts[0])
    if n is None or n[0] != "massa" or n[1] == 1.0:
        return None
    word = _CO2.sub("", parts[0]) or parts[0]
    return {"kind": "numerator", "ef0": word, "factor": max(n[1], 1 / n[1])}
