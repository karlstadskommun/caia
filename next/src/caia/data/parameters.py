"""Load parameter library and data files for context injection into agents.

Both come from the active kommunprofil (caia.kommun): the library is the
profile's parameters_library.md, and the data files are the ones its section-12
register names, read from the profile's data/ folder. Nothing here knows which
municipality it is reading."""

from __future__ import annotations

import csv
import json
import logging
import math
import re
from pathlib import Path

from caia.kommun import KommunProfilError, active

log = logging.getLogger(__name__)


def data_dir() -> Path:
    """The active profile's data folder."""
    return active().data_dir


def params_file() -> Path:
    """The active profile's parameter library."""
    return active().parameters_file


def load_parameter_library() -> str:
    """Return full parameter library markdown."""
    return params_file().read_text(encoding="utf-8")


# The fifth column holds the municipality's own value. Its header in the
# markdown is the profile's business ("Karlstad_specifikt"); the parser reads
# columns by position and calls it `lokalt` whatever the header says.
_COLUMNS = [
    "id", "kategori", "beskrivning", "standard", "lokalt", "enhet",
    "ar", "gas", "use_bau", "use_atgard", "anvandning", "kommentar",
]
_EMPTY = {"", "?", "-", "–", "—"}

# The library holds two kinds of table, told apart by the first header cell.
# Section 12 is a register of data files, not parameters; parsing its rows
# through the parameter columns used to produce nine "parameters" named
# DATA_EMISSIONS_TOTAL etc. with a file name in the category column. Any table
# whose header is neither is skipped rather than guessed at.
_PARAM_HEADER = "Parameter_ID"
_REGISTER_HEADER = "Logiskt_Namn"
_REGISTER_COLUMNS = ["name", "filename", "beskrivning", "variabler", "ar"]

_LOOKUP_RE = re.compile(r"LOOKUP\(\s*([A-Za-z0-9_]+)", re.IGNORECASE)


def _is_separator(cell: str) -> bool:
    return bool(cell) and set(cell) <= {"-", ":"}


def _tables():
    """Yield (section_title, header_first_cell, cells) for every data row in
    the library. Header and separator rows set the table kind and are not
    yielded themselves."""
    section = None
    header = None
    for raw in load_parameter_library().splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line.lstrip("# ").strip()
            header = None
            continue
        if not line.startswith("|") or section is None:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if _is_separator(cells[0]):
            continue
        if cells[0] in (_PARAM_HEADER, _REGISTER_HEADER):
            header = cells[0]
            continue
        yield section, header, cells


# The sources a loader in this module reads into the agents' data context.
# Any other registered source (a report PDF, a helper script) is read by
# nothing, so its file being in data/ does not put a single value in front of
# an agent. Before this list, dropping the travel-survey PDF into data/ turned
# eleven transport rows into "datafil" and the source check certified them as
# the municipality's own data.
READ_SOURCES = ("DATA_EMISSIONS_TOTAL", "DATA_ENERGY_RESIDENTIAL", "DATA_CONSUMPTION_FOOTPRINT",
                "DATA_HOUSEHOLD_TIME_SERIES", "DATA_MUNICIPAL_ORG", "DATA_CITIZEN_SURVEY")


def _is_read(name: str) -> bool:
    return any(name == p or name.startswith(p + "_") for p in READ_SOURCES)


def parse_file_register() -> dict[str, dict]:
    """Section 12: logical data-source name -> {filename, beskrivning, exists, read}.

    `exists` is checked against the profile's data folder at parse time, and
    `read` says whether a loader reads that source at all. A LOOKUP is only
    local data when both hold; otherwise nobody can resolve it, and the
    provenance label must say so instead of calling it a data-file value."""
    register: dict[str, dict] = {}
    for _section, header, cells in _tables():
        if header != _REGISTER_HEADER:
            continue
        entry = dict(zip(_REGISTER_COLUMNS,
                         cells + [""] * (len(_REGISTER_COLUMNS) - len(cells))))
        filename = entry["filename"].strip("`").strip()
        entry["filename"] = filename
        entry["exists"] = _data_path(filename) is not None
        entry["read"] = _is_read(entry["name"])
        register[entry["name"]] = entry
    return register


def _data_path(filename: str) -> Path | None:
    """The file in the profile's data folder, or None when it is not there.

    A register entry may not point outside the folder: the register is text a
    municipality edits, and "../" in it should not read the server's files."""
    if not filename:
        return None
    base = data_dir().resolve()
    path = (base / filename).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


def _source_file(prefix: str) -> tuple[Path | None, dict]:
    """Resolve a data source by its logical register name.

    Matched on prefix so a name that carries a year (DATA_CITIZEN_SURVEY_2024)
    keeps working when a municipality registers another year."""
    for name, entry in parse_file_register().items():
        if name == prefix or name.startswith(prefix + "_"):
            return _data_path(entry["filename"]), entry
    return None, {}


def lookup_source(lokalt: str) -> str | None:
    """The logical source name a LOOKUP(...) cell refers to, or None."""
    m = _LOOKUP_RE.search(lokalt or "")
    return m.group(1) if m else None


def _provenance(lokalt: str, register: dict[str, dict] | None = None) -> str:
    """How trustworthy is the value used? lokal = verified local data,
    datafil = looked up from a local data file that is actually on disk,
    schablon = national/EU default (NOT locally verified — the integrity risk
    to surface).

    A LOOKUP whose source file does not exist is a schablon with extra steps:
    nothing can resolve it, so the standard value is what is used in practice.
    Labelling it "datafil" claimed a local grounding that was never there."""
    k = (lokalt or "").strip()
    if k in _EMPTY:
        return "schablon"
    source = lookup_source(k)
    if source is not None:
        if register is None:
            register = parse_file_register()
        entry = register.get(source, {})
        if entry.get("exists") and entry.get("read"):
            return "datafil"
        return "schablon"
    return "lokal"


def parse_parameter_library() -> list[dict]:
    """Parse the markdown library into sections of structured rows with provenance.

    Only tables headed by Parameter_ID are parameters. Every row carries
    `provenance`, `value_used`, and for LOOKUP rows `lookup_source` plus
    `lookup_resolved`. Unresolvable LOOKUPs are logged once per source,
    because a value that quietly falls back to the standard column is exactly
    the kind of drop that later reads as "the local data was used".

    Forward-compatible source for an /api/parameters view: if the library later
    moves to a DB for editing, this function is what changes — not the callers."""
    register = parse_file_register()
    sections: list[dict] = []
    by_title: dict[str, dict] = {}
    unresolved: dict[str, list[str]] = {}
    for title, header, cells in _tables():
        if header != _PARAM_HEADER:
            continue
        current = by_title.get(title)
        if current is None:
            current = by_title[title] = {"title": title, "rows": []}
            sections.append(current)
        row = dict(zip(_COLUMNS, cells + [""] * (len(_COLUMNS) - len(cells))))
        row["provenance"] = _provenance(row["lokalt"], register)
        source = lookup_source(row["lokalt"])
        if source is not None:
            row["lookup_source"] = source
            row["lookup_resolved"] = row["provenance"] == "datafil"
            if not row["lookup_resolved"]:
                unresolved.setdefault(source, []).append(row["id"])
        row["value_used"] = (row["lokalt"] if row["provenance"] != "schablon"
                             else row["standard"])
        current["rows"].append(row)
    for source, ids in unresolved.items():
        entry = register.get(source)
        if not entry:
            where = "not in the section-12 register"
        elif not entry["read"]:
            where = f"CAIA reads no {entry['filename']}; transcribe its values into the library"
        else:
            where = f"file '{entry['filename']}' not in {data_dir()}"
        log.warning("LOOKUP source %s is unresolvable (%s); %d parameter(s) "
                    "fall back to their standard value: %s",
                    source, where, len(ids), ", ".join(ids))
    return [s for s in sections if s.get("rows")]


# --- Label repair for the national emissions export -------------------------
#
# The national emissions export (register name DATA_EMISSIONS_TOTAL; for
# Karlstad Kommunrapport_karlstad_vaxthusgaser_totalt.csv) reaches us with its Swedish
# letters already destroyed upstream: å/ä/ö appear either as U+FFFD (the
# replacement character, baked into the file as real bytes) or folded to bare
# a/o. Reading it as latin-1 turned U+FFFD into "ï¿½" on top of that.
#
# We repair the *labels* at load time rather than rewriting the source file, so
# the downloaded dataset keeps its provenance and a future clean re-download
# passes straight through. Numbers are never touched.
#
# Matching is positional: an observed label matches a canonical one when they
# are the same length and every differing position is a Swedish letter that the
# mangling could have produced. A label that matches zero or several canonicals
# is left exactly as it came in.
#
# The county's own name ("Värmlands län") is a label in the export too; it comes
# from the kommunprofil (`lan`) and is added in repair_label.
_SECTOR_LABELS = (
    "Användning av fluorerade gaser",
    "Användning av konstgödsel",
    "Avdunsting från vägfordon",  # upstream's own typo (Avdunstning) kept as-is
    "Bostäder",
    "Djurs matsmältning",
    "Egen uppvärmning av bostäder och lokaler",
    "El och fjärrvärme",
    "Fiskebåtar",
    "Färg - hushåll",
    "Färg - verksamheter",
    "Fårgödsel m.m. (lagring, användning och bete)",
    "Hästgödsel (lagring, användning och bete)",
    "Hushållens arbetsmaskiner",
    "Hönsgödsel (lagring, användning och bete)",
    "Indirekta utsläpp av lustgas från brukad mark",
    "Industri- och byggsektorns arbetsmaskiner (inkl vägarbeten)",
    "Järnväg",
    "Kalkning av åkermark",
    "Kogödsel (lagring, användning och bete)",
    "Krematorier och förbranning av farligt avfall",  # upstream typo kept
    "Lustgas från produktanvändning",
    "Län",
    "Lösningsmedelsanvändning - hushåll",
    "Lösningsmedelsanvändning - verksamheter",
    "Lätta lastbilar",
    "Oavsiktliga bränder",
    "Produktanvändning (inkl. lösningsmedel)",
    "Skörderester som gödsel",
    "Slitage från däck och bromsar",
    "Slitage från vägbanan",
    "Smörjmedel",
    "Svingödsel (lagring, användning och bete)",
    "Urea för katalysatorer",
    "Utrikes flyg under 1000 m höjd i svenskt luftrum",
    "Utrikes sjöfart inom Sveriges gränser",
    "inrikes civil sjöfart (inkl privata fritidsbåtar)",
    "Övrig avfallshantering",
    "Övrig produktanvändning",
    "Övrigt (flygplatser, hamnar, m.m.)",
    "Övrigt gödselmedel m.m",
)

_REPLACEMENT = "�"
_MANGLED = {
    "å": {_REPLACEMENT, "a"}, "ä": {_REPLACEMENT, "a"}, "ö": {_REPLACEMENT, "o"},
    "Å": {_REPLACEMENT, "A"}, "Ä": {_REPLACEMENT, "A"}, "Ö": {_REPLACEMENT, "O"},
}


def _label_matches(observed: str, canonical: str) -> bool:
    if len(observed) != len(canonical):
        return False
    return all(o == c or o in _MANGLED.get(c, ())
               for o, c in zip(observed, canonical))


def repair_label(label: str) -> str:
    """Restore Swedish letters in a mangled sector label. Unknown or already
    clean labels are returned untouched.

    There is deliberately no "skip if the label still contains U+FFFD" shortcut.
    Some labels lost their diacritic with no residue at all ("Urea for
    katalysatorer"), so gating on the replacement character misses exactly the
    class that is hardest to spot by eye: a label that reads as an ordinary
    typo rather than as a parsing artifact. Every label goes through the
    matcher, and a label that matches zero or several canonicals is returned
    unchanged."""
    hits = [c for c in (*_SECTOR_LABELS, active().lan) if _label_matches(label, c)]
    return hits[0] if len(hits) == 1 else label


def _to_number(raw: str) -> float | None:
    """Parse a Swedish-decimal value ('224950,7472'). None when not numeric.

    The first replace strips a non-breaking space (U+00A0), the second an
    ordinary one; both show up as thousands separators in the export."""
    try:
        return float(raw.strip().replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


# Ordinary space, stated explicitly. The source files use U+00A0 as thousands
# separator and it travels invisibly through a copy-paste; anything that later
# string-matches this output should not have to guess which space it got.
_THOUSANDS_SEP = " "


def _thousands(n: float) -> str:
    """Swedish thousands grouping. Applied to the number alone, never to a whole
    sentence: doing that eats the commas inside category names."""
    return f"{round(n):,}".replace(",", _THOUSANDS_SEP)


def _emissions_table(path: Path) -> tuple[list[str], list[list[str]]]:
    """The emissions export as (years, sector rows). A row's values start at
    column 4 and line up with `years`.

    Layout: 5 metadata lines, a year row (values start at column 4), a column
    header row, then one row per sector."""
    years: list[str] = []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[5:]:
        parts = line.split(";")
        first = parts[0].strip()
        if not first:
            # the year row is the only leading-blank line that carries years
            candidates = [p.strip() for p in parts if p.strip().isdigit()]
            if candidates and not years:
                years = candidates
            continue
        if first == "Huvudsektor":  # column header
            continue
        if len(parts) >= 2:
            rows.append(parts)
    return years, rows


def load_emissions_data(recent_years: int = 3) -> str:
    """Parse territorial emissions CSV and return summary.

    Every data row is emitted, labelled Huvudsektor/Undersektor, and every value
    carries the year it belongs to. Dropping rows here silently removes whole
    sectors from what the agents can reason about."""
    path, _entry = _source_file("DATA_EMISSIONS_TOTAL")
    if path is None:
        return ""
    years, rows = _emissions_table(path)
    if not rows:
        return ""

    summary = f"## Territoriella växthusgasutsläpp {active().ort} (ton/år)\n"
    for row in rows:
        huvud = repair_label(row[0].strip())
        under = repair_label(row[1].strip()) if len(row) > 1 else ""
        name = huvud if under in ("", "Alla", huvud) else f"{huvud} / {under}"
        if huvud == "Alla" and under == "Alla":
            name = "Alla sektorer (totalt)"

        values = row[4:]
        pairs = []
        for idx, raw in enumerate(values):
            num = _to_number(raw)
            if num is None:
                continue
            year = years[idx] if idx < len(years) else "?"
            pairs.append(f"{year}: {_thousands(num)}")
        if pairs:
            summary += f"- {name}: {', '.join(pairs[-recent_years:])}\n"
    return summary


def load_energy_data() -> str:
    """Parse residential energy CSV and return summary."""
    path, _entry = _source_file("DATA_ENERGY_RESIDENTIAL")
    if path is None:
        return ""
    summary = f"## Energianvandning bostader {active().ort} (MWh)\n"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kategori = row.get("Kategori", "")
            mwh = row.get("MWh", "")
            if kategori and mwh:
                summary += f"- {kategori}: {mwh} MWh\n"
    return summary


def load_consumption_data() -> str:
    """Parse consumption JSON files and return summary.

    Empty when the profile has none of the three files: a heading with nothing
    under it tells the agents there is local consumption data when there is not."""
    ort = active().ort
    heading = f"## Konsumtionsbaserade utslapp {ort}\n"
    summary = heading

    # Footprint per category. The export has one column per region, named
    # after it ("Karlstad", "Värmlands län", "Sverige"); the municipality's
    # own column is the one named like the profile's `ort`.
    path, _entry = _source_file("DATA_CONSUMPTION_FOOTPRINT")
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        summary += "\n### Fotavtryck per konsumtionskategori (kg CO2e/person/ar):\n"
        for item in data:
            label = item.get("label", "")
            lokalt = item.get(ort, "")
            per100 = item.get("per100sek", "")
            if label:
                summary += f"- {label}: {lokalt} kg CO2e/pers/ar"
                if per100:
                    summary += f" ({per100} kg CO2e/100 SEK)"
                summary += "\n"

    # Household emissions over time. The three series are the municipality, the
    # county and Sweden \u2014 without the region label they render identically
    # and the agents cannot tell which benchmark they are looking at.
    path, _entry = _source_file("DATA_HOUSEHOLD_TIME_SERIES")
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        summary += "\n### Hush\u00e5llens totala utsl\u00e4pp \u00f6ver tid (kg CO2e/person/\u00e5r):\n"
        for item in data:
            years = {k: v for k, v in item.items() if k.isdigit()}
            if not years:
                continue
            region = item.get("region") or item.get("code") or "ok\u00e4nd region"
            latest = sorted(years.keys())[-3:]
            vals = ", ".join(f"{y}: {round(float(years[y]))}" for y in latest)
            summary += f"- {region}: {vals}\n"

    # Municipal org emissions. Keys in the file are Huvudkategori / Kategori /
    # "Kg CO2e"; grouped by main category so all 77 rows fit readably.
    path, _entry = _source_file("DATA_MUNICIPAL_ORG")
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("data", []) if isinstance(data, dict) else data
        grouped: dict[str, list[tuple[str, float]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            main = str(item.get("Huvudkategori", "")).strip() or "\u00d6vrigt"
            cat = str(item.get("Kategori", "")).strip()
            kg = item.get("Kg CO2e")
            if not cat or not isinstance(kg, (int, float)):
                continue
            grouped.setdefault(main, []).append((cat, float(kg)))
        if grouped:
            total = sum(v for rows in grouped.values() for _, v in rows)
            summary += ("\n### Kommunkoncernens egna konsumtionsbaserade utsl\u00e4pp "
                        f"(ton CO2e, totalt {_thousands(total / 1000)})\n")
            for main, rows in grouped.items():
                subtotal = sum(v for _, v in rows)
                summary += f"\n**{main}** (totalt {_thousands(subtotal / 1000)} ton):\n"
                for cat, kg in sorted(rows, key=lambda r: -r[1]):
                    summary += f"- {cat}: {_thousands(kg / 1000)} ton\n"

    return "" if summary == heading else summary


def load_citizen_survey() -> str:
    """Parse citizen survey CSV and return summary. The year in the heading is
    the register's year column for the survey."""
    path, entry = _source_file("DATA_CITIZEN_SURVEY")
    if path is None:
        return ""
    year = entry.get("ar", "").strip()
    year = f" {year}" if year and year not in _EMPTY else ""
    summary = f"## Medborgarundersokning {active().ort}{year}\n"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        current_q = ""
        for row in reader:
            q = row.get("Question", "")
            opt = row.get("Response_Option", "")
            pct = row.get("Percentage", "")
            if q != current_q:
                current_q = q
                summary += f"\n### {q}:\n"
            if opt and pct:
                summary += f"- {opt}: {pct}%\n"
    return summary


def _is_utf8(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def get_data_context() -> str:
    """Combine all data summaries into one context string for agent injection.

    A data file that is not UTF-8 (the emissions export arrives as Latin-1)
    stops with a message naming the file and the fix, instead of a codec
    error in the middle of a step."""
    try:
        parts = [
            load_emissions_data(),
            load_energy_data(),
            load_consumption_data(),
            load_citizen_survey(),
        ]
    except UnicodeDecodeError as e:
        name = next((entry["filename"] for entry in parse_file_register().values()
                     if entry["exists"] and not _is_utf8(_data_path(entry["filename"]))),
                    "en av datafilerna")
        raise KommunProfilError(
            f"{name} i {data_dir()} är inte UTF-8. Konvertera den, till exempel med "
            "iconv -f latin1 -t utf-8, se docs/DATAFORMAT.md.") from e
    except (json.JSONDecodeError, csv.Error) as e:
        raise KommunProfilError(f"En datafil i {data_dir()} går inte att läsa: {e}. "
                                "Formaten står i docs/DATAFORMAT.md.") from e
    return "\n\n".join(p for p in parts if p)


# --- What the parameter view prints for a LOOKUP row ------------------------
#
# A row whose local value is LOOKUP(...) holds no number in the library: the
# agents read the data file's summary and take the value from there. The view
# used to print the expression itself. It now prints the number the expression
# points at, when that is one cell in a file this module reads, and says in
# words where it came from. An expression that is not one cell (a survey
# distribution, `"Småhus" vs "Flerbostadshus"`) gets the words and no number:
# a number made up here would be one no analysis uses.
#
# Display only: the parameter view and the report section "Talens ursprung"
# (caia.kallmarkering) both print what parameter_view() gives. `value_used`
# stays the expression, because the source check and the prompts read it.

_LOOKUP_EXPR_RE = re.compile(
    r"^\s*LOOKUP\(\s*([A-Za-z0-9_]+)\s*,(.*)\)\s*(?:([*/])\s*([A-Za-z0-9_.,]+))?\s*$",
    re.IGNORECASE | re.DOTALL)
_ARG_SPLIT_RE = re.compile(r',(?=(?:[^"]*"[^"]*")*[^"]*$)')
_NOT_FOR_READERS_RE = re.compile(r"[()]|LOOKUP|DATA_[A-Z]", re.IGNORECASE)
READS_AT_ANALYSIS = "Läses ur datafilen vid varje analys"


def datafil_name(source: str, entry: dict) -> str:
    """What to call a data file for a reader: its description in the
    register, else its file name. The register name (DATA_...) only when the
    register says nothing else."""
    return entry.get("beskrivning") or entry.get("filename") or source


def _lookup_args(raw: str) -> list[str] | None:
    """The arguments after the source name, quotes stripped. None when the
    text is not a plain comma-separated list (`"Småhus" vs "Flerbostadshus"`)."""
    args: list[str] = []
    for part in _ARG_SPLIT_RE.split(raw):
        part = part.strip()
        quoted = re.fullmatch(r'"([^"]*)"', part)
        if quoted:
            args.append(quoted.group(1).strip())
        elif part and '"' not in part and " " not in part:
            args.append(part)
        else:
            return None
    return args


_PLAIN_NUMBER_RE = re.compile(r"-?(\d+)(?:[.,](\d+))?")


def _plain_number(text: str) -> float | None:
    """A number written so it can be read only one way, else None.

    '97 233', '6.67' and '0,828' are. '97.233', '97,233' and '1.000' are not:
    thousands separator or decimals? Reading them as decimals put a per-capita
    figure a factor 1000 off. A range, a percentage or an expression is not a
    number either."""
    s = re.sub(r"\s", "", text or "")
    m = _PLAIN_NUMBER_RE.fullmatch(s)
    if not m:
        return None
    whole, frac = m.group(1), m.group(2)
    if frac is not None and len(frac) == 3 and len(whole) <= 3 and whole[0] != "0":
        return None
    return float(s.replace(",", "."))


# Each reader takes the file and the arguments and returns (value, spec):
# the cell as a number, or None when the arguments do not name exactly one
# cell, and optionally a more readable wording of the arguments for the note.

def _cell_emissions(path: Path, args: list[str]) -> tuple[float | None, str | None]:
    """("Totala utsläpp", <year>): the all-sectors row for that year."""
    if len(args) != 2 or args[0].casefold() != "totala utsläpp":
        return None, None
    years, rows = _emissions_table(path)
    totals = [r for r in rows if r[0].strip() == "Alla" and r[1].strip() == "Alla"]
    if len(totals) != 1 or years.count(args[1]) != 1:
        return None, None
    values = totals[0][4:]
    while values and not values[-1].strip():
        values.pop()
    # _emissions_table keeps only the year cells that are digits. A header it
    # dropped ("2015*") would shift every later year one column, so the row
    # must have exactly one value per year it kept.
    if len(values) != len(years):
        return None, None
    return _to_number(values[years.index(args[1])]), None


def _cell_energy(path: Path, args: list[str]) -> tuple[float | None, str | None]:
    """("<column>", "<Kategori>"): one cell of the residential energy table."""
    if len(args) != 2:
        return None, None
    column, kategori = args
    with open(path, encoding="utf-8") as f:
        hits = [row.get(column) for row in csv.DictReader(f)
                if (row.get("Kategori") or "").strip() == kategori]
    if len(hits) != 1 or not isinstance(hits[0], str):
        return None, None
    return _plain_number(hits[0]), None


def _cell_footprint(path: Path, args: list[str]) -> tuple[float | None, str | None]:
    """("<column>", "coicop=<code>"): one category's value in one column."""
    if len(args) != 2 or not args[1].casefold().startswith("coicop="):
        return None, None
    column, code = args[0], args[1].split("=", 1)[1].strip()
    data = json.loads(path.read_text(encoding="utf-8"))
    hits = [item for item in data if isinstance(item, dict)
            and str(item.get("coicop", "")).strip() == code] if isinstance(data, list) else []
    if len(hits) != 1:
        return None, None
    label = str(hits[0].get("label", "")).strip()
    spec = f"{label[:1].upper()}{label[1:]} (COICOP {code}), {column}" if label else None
    value = hits[0].get(column)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, spec
    return float(value), spec


_CELL_READERS = (
    ("DATA_EMISSIONS_TOTAL", _cell_emissions),
    ("DATA_ENERGY_RESIDENTIAL", _cell_energy),
    ("DATA_CONSUMPTION_FOOTPRINT", _cell_footprint),
)


def _display_number(x: float) -> str:
    """Three significant figures below a thousand, whole numbers from there
    up, decimal comma: 224 951, 6 670, 666, 19,9, 2,31, 0,828."""
    y = float(f"{x:.3g}")
    if y == 0:
        return "0"
    if abs(y) >= 1000:
        return _thousands(x)
    decimals = max(0, 2 - math.floor(math.log10(abs(y))))
    return f"{y:.{decimals}f}".replace(".", ",")


def _operand(token: str, rows_by_id: dict[str, dict]) -> tuple[float | None, str]:
    """The factor after a LOOKUP: another parameter (when its value is one
    plain number) or a number. Returns (value, what to call it in the note)."""
    row = rows_by_id.get(token)
    if row is None:
        number = _plain_number(token)
        return number, (_display_number(number) if number is not None else token)
    name = row.get("beskrivning") or token
    # The result stands under "from a local data file". A national default as
    # divisor would pass for local there, and a percentage would multiply as a
    # whole number: neither gives a number.
    if row.get("provenance") != "lokal" or "%" in (row.get("enhet") or ""):
        return None, name
    return _plain_number(row.get("value_used", "")), name


def _lookup_view(row: dict, register: dict[str, dict],
                 rows_by_id: dict[str, dict]) -> tuple[str, str]:
    """(value text, note) for a row that takes its value from a data file."""
    source = row["lookup_source"]
    entry = register.get(source, {})
    origin = f"Datafil: {datafil_name(source, entry)}."
    m = _LOOKUP_EXPR_RE.match(row["lokalt"])
    if not m:
        return READS_AT_ANALYSIS, origin
    raw_args, op, token = m.group(2), m.group(3), m.group(4)
    args = _lookup_args(raw_args)
    spec = ", ".join(args) if args is not None else " ".join(raw_args.replace('"', "").split())
    if _NOT_FOR_READERS_RE.search(spec):
        # A second LOOKUP or a parenthesis inside the arguments: what is left
        # is a fragment of an expression, not a description of anything.
        return READS_AT_ANALYSIS, origin
    value = None
    reader = next((r for prefix, r in _CELL_READERS
                   if source == prefix or source.startswith(prefix + "_")), None)
    path = _data_path(entry.get("filename", ""))
    if args is not None and reader is not None and path is not None:
        try:
            value, named = reader(path, args)
        except Exception as e:  # noqa: BLE001
            # Whatever is wrong with the file (a number too large for a float,
            # JSON nested past the recursion limit), this row loses its
            # number. The list of 78 parameters is not lost with it.
            log.warning("Parameter view: %s could not be read for %s (%s: %s); "
                        "the row is shown without a number",
                        entry.get("filename"), row["id"], type(e).__name__, e)
            value, named = None, None
        spec = named or spec
    if op:
        factor, name = _operand(token, rows_by_id)
        spec += f", {'delat med' if op == '/' else 'gånger'} {name}"
        if value is None or factor is None or (op == "/" and factor == 0):
            value = None
        else:
            value = value / factor if op == "/" else value * factor
    note = f"{spec}. {origin}"
    if value is None or not math.isfinite(value):
        return READS_AT_ANALYSIS, note
    return _display_number(value), note


def parameter_view() -> list[dict]:
    """parse_parameter_library() with two more keys per row, for the value
    column of the parameter view: `value_display` (what to print) and
    `value_note` (where a data-file value came from; empty for other rows)."""
    sections = parse_parameter_library()
    register = parse_file_register()
    rows_by_id = {r["id"]: r for s in sections for r in s["rows"]}
    for section in sections:
        for row in section["rows"]:
            row["value_display"], row["value_note"] = row["value_used"], ""
            if row.get("lookup_resolved"):
                row["value_display"], row["value_note"] = _lookup_view(row, register, rows_by_id)
    return sections
