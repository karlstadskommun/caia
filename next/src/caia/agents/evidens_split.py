"""Evidens (step 4) split into one call per driver plus a merge.

Why: the single evidens call took 163-222 s on Opus 5/5.5 (2026-09-23), against
Vercel's 300 s function limit. It is the one step whose length grows with the
number of drivers, so a heavier package than the leaf-blower pilot would cross
the limit. Splitting it keeps every model call to one driver's worth of work.

Shape, and why it is client-driven:

    plan   (no model call)  ->  drivers from baslinje/EMAP in the history
    part   x N, in parallel ->  one driver block each
    merge  (one call)       ->  frame sections + consistency check + corrections

Each phase is its own HTTP request (see web/app.py), so one function run never
holds more than one model call. A server-side fan-out would have put the
slowest part *plus* the merge inside a single 300 s function, which is roughly
where the monolithic call already was. The client needs nothing platform
specific (no queue, no background worker), so a self-hosted instance works the
same way.

The merge exists because no part sees the others' numbers. Its job is to catch
what that loses, above all double counting: the same reduction booked on two
drivers, or on one driver through both ΔA and ΔEF. It does not rewrite the
driver blocks. The code assembles the final text from the parts verbatim, and
only swaps in a block the merge explicitly replaced. That keeps the merge's
output short, and it means a number reaches step 5 either exactly as the part
wrote it or as a visible correction, never as a silent copying error.

The assembled text has the same headings and field labels as the monolithic
step, so step 5 (kalkyl_extract) and the panel parser read it unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..api_client import complete
from ..data.parameters import get_data_context, load_parameter_library
from ..evidence import _DRIVER, _LABELLED, _PARAMETER, _norm, _split_param_name
from ..kommun import active
from ..mode import POTENTIAL
from .evidens import SYSTEM_PROMPT
from .uppfoljning import for_mode

PART_MAX_OUTPUT = 5000
# 8000 (20000 with medium headroom) clipped 2 of 3 merges of a four-driver
# follow-up on 2026-09-30 (testcyklisterna, 204-209 s each, corrections to
# every block). The text itself is mostly summaries; the rest is reasoning.
MERGE_MAX_OUTPUT = 14000

# Markers the model is asked to emit. Plain bracketed tokens rather than
# markdown headings, so they cannot collide with anything the evidence parser
# or step 5 treats as structure.
MARK_SCOPE = '[[AVGRÄNSNING]]'
MARK_DRIVERS = '[[DRIVARBLOCK]]'
MARK_CORRECTIONS = '[[KORRIGERINGAR]]'

DRIVER_SECTION_HEADING = '## Antaganden per drivare'


class EvidensSplitError(RuntimeError):
    """A part or the merge returned something the step cannot safely use.

    Raised instead of passing on a partial underlag: step 5 would compute a
    total from whatever drivers reached it, and a missing driver looks exactly
    like a driver with no effect."""


class EditTargetMissing(EvidensSplitError):
    """A field edit names a parameter or field the block does not have.

    apply_field_edit raises it; assemble catches it, leaves the block as the
    part wrote it and says so in the text (SKIPPED_NOTE). One such line used
    to fail the whole step with 422 and stop a paid batch package
    (driftsmedel run 1, 2026-10-21: "Kvalitet" on driver 7's attribution)."""


# No colon anywhere in it: a "Label: value" line right after the last block
# (a merge with an empty tail) would be read as a field of that driver.
SKIPPED_NOTE = ('Programmets anmärkning om rättelserna. {n} av sammanfogningens rättelser '
                'kunde inte föras in, eftersom de gäller något som inte finns i drivarblocket. '
                'Värdena i blocken är alltså inte ändrade på de punkterna, även om '
                'Samstämmighetskontrollen ovan säger det. Övriga rättelser är införda. '
                'De som inte fördes in står här.')


@dataclass(frozen=True)
class Driver:
    number: int
    name: str


# ---------- plan ----------

def _looks_like_evidens(text: str) -> bool:
    """A previous evidens answer also carries 'Drivare N:' blocks, but only for
    the drivers it judged affected. On a feedback re-run it sits later in the
    history than baslinje and must not be mistaken for the driver list."""
    return 'Evidens & antaganden för åtgärd' in text or 'Antagande_med' in text


def _opens_field_block(text: str, pos: int) -> bool:
    """True when the first non-blank line after `pos` is a labelled field
    ("  A0: ...", "aktivitet_matt: ...", "Mekanism: ...").

    Reads a window that grows until it holds that line, never the whole rest
    of the text: this runs once per heading, and splitting the rest each time
    made a turn full of headings cost seconds (re-review 2026-10-07, F4)."""
    size = 400
    while True:
        lines = text[pos:pos + size].splitlines()
        whole = pos + size >= len(text)
        # The window may have cut its last line short, so that line only
        # counts once the window reaches the end of the text.
        for line in lines if whole else lines[:-1]:
            if line.strip():
                return bool(_LABELLED.match(line)) and not _DRIVER.match(line)
        if whole:
            return False
        size *= 4


def drivers_from_history(history: list[dict]) -> list[Driver]:
    """The driver list evidens must cover: the newest earlier step that names
    drivers (baslinje, else EMAP). Numbers are kept as the upstream step wrote
    them, because steps 5-7 refer to drivers by number.

    Returns [] when nothing parses; the caller then uses the monolithic step."""
    for message in reversed(history):
        if message.get('role') != 'assistant':
            continue
        text = message.get('content') or ''
        if not isinstance(text, str) or _looks_like_evidens(text):
            continue
        found: dict[int, str] = {}
        for match in _DRIVER.finditer(text):
            # Only a heading that opens a block of fields counts. A prose line
            # like "Drivare 2: se ovan" would otherwise add a driver that no
            # upstream step defined, and a part would be asked to invent it.
            if not _opens_field_block(text, match.end()):
                continue
            number = int(match.group('number'))
            name = match.group('name').strip().strip('*_ ')
            # Baslinje lists every driver twice (nuläge and BAU); the first
            # occurrence wins.
            found.setdefault(number, name or f'Drivare {number}')
        if found:
            return [Driver(n, found[n]) for n in sorted(found)]
    return []


# ---------- parts ----------

def _context_system(extra: str, data_context: str) -> str:
    system = active().render(SYSTEM_PROMPT)
    system += f"\n\n<parameterbibliotek>\n{load_parameter_library()}\n</parameterbibliotek>"
    if not data_context:
        data_context = get_data_context()
    if data_context:
        system += f"\n\n<localData>\n{data_context}\n</localData>"
    return system + "\n\n" + extra


# The tags the split steps' prompts are framed with, also written with blanks
# ("< /delsteg>"): a model may well read that as the closing tag.
_FRAME_TAG = re.compile(r'<(?=[ \t]*(?:/[ \t]*)?(?:delsteg|delresultat|localData|parameterbibliotek)\b)', re.IGNORECASE)


def _as_data(text: str) -> str:
    """Text from the client or from a model, to be placed inside one of the
    prompt's own tags: it must not close the tag and go on as instructions
    (re-review 2026-10-07). Only the frame's tags are touched, and only in
    the prompt; the blocks the code assembles afterwards are the originals."""
    return _FRAME_TAG.sub('‹', text)


def _driver_list(drivers: list[Driver]) -> str:
    return '\n'.join(f'  - Drivare {d.number}: {_as_data(d.name)}' for d in drivers)


def part_instruction(driver: Driver, drivers: list[Driver]) -> str:
    return f"""<delsteg>
Steget är uppdelat: varje drivare bedöms i ett eget anrop, parallellt, och ett
sista anrop fogar samman delarna. Det här anropet ansvarar ENBART för:

  Drivare {driver.number}: {_as_data(driver.name)}

Alla drivare i analysen (de övriga bedöms i andra anrop, som inte ser ditt svar):
{_driver_list(drivers)}

Detta ersätter textstrukturen i ioContract. Skriv INTE rubrikraden och INTE
avsnitten "Kort om detta steg", "Underlag från tidigare steg", "Påverkade
drivare och parametrar", "Nyckelantaganden – överblick", "Övergripande
antaganden och scenariologik", "Dataluckor för detta steg" eller "Externa
källor och studier". Dem skriver sammanfogningen.

Svara med exakt detta, i denna ordning:

1) Blocket för din drivare i formatet från avsnitt 5 ("Antaganden per drivare"),
   med samma radetiketter, och med första raden exakt:
   Drivare {driver.number}: {_as_data(driver.name)}
   Behåll numret {driver.number}. Påverkas drivaren inte, eller ska den inte
   kvantifieras, skriv ändå blocket: Mekanism säger det och att klimatnyttan inte
   kvantifieras för drivaren.

2) En rad med enbart {MARK_SCOPE}, följd av 1-3 meningar om vilken
   utsläppsförändring ditt block räknar (vilken aktivitet och vilken
   emissionsfaktor, via ΔA, ΔEF eller adoption) och vilka effekter du medvetet
   lämnar till andra drivare. Sammanfogningen använder detta för att hitta
   dubbelräkning, så var konkret.

3) Därefter, under egna rader:
   Nyckelantaganden: 1-3 punkter för din drivare.
   Dataluckor: högst 4 punkter för din drivare.
   Externa källor: högst 4 punkter, eller "Inga".

Räkna bara den effekt som hör till din drivare. Fångas en effekt redan av en
annan drivare i listan ovan, räkna den inte här utan skriv det i avgränsningen.

Det som gäller hela åtgärden (när bytet hade skett i BAU, rampen, antal
effektår, attributionen) tar du från åtgärdsprofilen och baslinjen, så att alla
drivare följer samma förlopp. Anser du att något av det borde ändras, bygg inte
in ändringen i ditt block: skriv förslaget med motivering i avgränsningen, så
avgör sammanfogningen det för alla drivare samtidigt.

Håll blocket lika kort som ett drivarblock i det samlade steget: en eller två
meningar per fält, inga upprepningar av underlaget. Ge varje parameter ett eget
kort namn efter "Parameter:" (ΔA, ΔEF, adoption, effektår, EF_el och så vidare),
aldrig bara "annan", så att en rättelse kan peka ut den.
</delsteg>"""


@dataclass(frozen=True)
class Part:
    driver: Driver
    block: str   # the "Drivare N: ..." block, as it goes into the final text
    notes: str   # scope, key assumptions, data gaps, sources: merge input only
    raw: str


def split_part(driver: Driver, text: str) -> Part:
    """Separate a part answer into its driver block and the notes for the merge.

    Fails loudly when the block is missing or carries another number: a part
    that answered for the wrong driver would otherwise leave its own driver
    uncovered while looking complete."""
    text = (text or '').strip()
    cut = text.find(MARK_SCOPE)
    if cut == -1:
        # The scope statement is what the merge checks for double counting.
        raise EvidensSplitError(
            f'Delsvaret för drivare {driver.number} saknar avgränsningen '
            f'({MARK_SCOPE}), som sammanfogningen behöver för att hitta dubbelräkning.')
    before, notes = text[:cut], text[cut + len(MARK_SCOPE):].strip()
    # Only the block half is checked for headings: the notes may well say
    # "Drivare 1: räknas där" about a neighbour, which is the point of them.
    headings = list(_DRIVER.finditer(before))
    if not headings:
        raise EvidensSplitError(
            f'Delsvaret för drivare {driver.number} saknar ett drivarblock.')
    numbers = {int(m.group('number')) for m in headings}
    if numbers != {driver.number}:
        raise EvidensSplitError(
            f'Delsvaret för drivare {driver.number} innehåller block för drivare '
            f'{", ".join(str(n) for n in sorted(numbers))}.')
    block = before[headings[0].start():].strip()
    if not _is_block(block):
        raise EvidensSplitError(
            f'Drivarblocket för drivare {driver.number} har varken antagandespann '
            f'eller en uttrycklig notering om att effekten inte kvantifieras.')
    return Part(driver=driver, block=block, notes=notes, raw=text)


def run_part(history: list[dict], driver: Driver, drivers: list[Driver],
             data_context: str = '', mode: str = POTENTIAL) -> Part:
    system = _context_system(part_instruction(driver, drivers), data_context)
    text = complete('evidens_part', for_mode(system, 'evidens_part', mode), history,
                    PART_MAX_OUTPUT)
    return split_part(driver, text)


# ---------- merge ----------

def merge_instruction(parts: list[Part]) -> str:
    rendered = '\n\n'.join(
        f'<delresultat drivare="{p.driver.number}">\n{_as_data(p.block)}\n\n'
        f'Avgränsning och noter:\n{_as_data(p.notes)}\n</delresultat>'
        for p in parts)
    return f"""<delsteg>
Steget har delats upp: varje drivare har bedömts i ett eget anrop, parallellt.
Inget av anropen såg de andras antaganden. Delresultaten står nedan. Du är
sammanfogningen, och det är bara du som ser helheten.

{rendered}

Din första uppgift är att granska helheten efter motsägelser som uppstår när
ingen ser mer än en drivare:
- Dubbelräkning: samma utsläppsminskning räknad på två drivare, eller på samma
  drivare via både ΔA och ΔEF för samma effekt. Läs avgränsningarna mot varandra.
- En effekt som alla avgränsningar lämnar till någon annan, så att ingen räknar den.
- Oförenliga antaganden mellan drivare: olika bytesår, adoption eller tidsaspekt
  för samma utrustning, olika tolkning av BAU, eller en kopplad drivare (t.ex.
  tillkommande el) som inte följer huvuddrivarens förlopp.
- Overlap_faktor större än minsta av Territoriell_faktor och Konsumtion_faktor,
  och domänreglerna ovan.
- Enheter som inte går ihop med baslinjens A0 och EF0.
Leta bara efter det som står i listan. Räkna inte om delarnas tal och pröva
inte deras källor: varje del har redan gjort det för sin drivare.

Svara sedan med exakt detta, i denna ordning, och så kort som det går:

1) Rubrikraden "Evidens & antaganden för åtgärd: [ÅTGÄRDENS TITEL]" och
   avsnitten "Kort om detta steg" (1-2 meningar), "Underlag från tidigare steg"
   (2-3 meningar) och "Påverkade drivare och parametrar" (en rad per drivare:
   namn, ΔA eller ΔEF, och kort varför), enligt textstrukturen i ioContract.

2) En rad med enbart {MARK_DRIVERS}. Den ersätter hela avsnittet "Antaganden
   per drivare", även rubriken: skriv inte om drivarblocken här, de sätts in
   ordagrant av programmet.

3) Avsnitten "Nyckelantaganden – överblick" (3-5 punkter, en mening var),
   "Övergripande antaganden och scenariologik" (3-5 meningar), "Dataluckor för
   detta steg" (högst 5 punkter, de viktigaste för helheten) och "Externa källor
   och studier" (högst 8 punkter, en rad var: källa och vad den belägger), för
   helheten. Sammanfatta delarnas noter, räkna inte upp dem alla, och upprepa
   inga tal som redan står i drivarblocken.

4) Avsnittet "Samstämmighetskontroll": högst 4 punkter, en mening var: vad du
   kontrollerade, vad du hittade och vad du ändrade. Hittade du
   inget, skriv vad du kontrollerade och att inga motsägelser hittades. Nämn
   bara de gällande värdena, inte ersatta. Ta här ställning till delarnas
   förslag om åtgärdens gemensamma förlopp (bytesår, ramp, effektår,
   attribution).

5) En rad med enbart {MARK_CORRECTIONS}. Därefter rättelserna, som programmet
   för in i blocken. Ändra bara det som motsägelsen kräver. Ett ändrat fält
   skrivs som en rad:
     Drivare N | parameter | Fältetikett: nytt värde
   där "parameter" är parameterns namn som det står efter "Parameter:" i
   blocket (utan parentesen), eller "-" för fält på drivarnivå (Mekanism,
   Attribut, Uppfattning, Osäkraste_led, Territoriell_faktor, Konsumtion_faktor,
   Overlap_faktor, Motivering_faktorer).
   Fältetiketten är exakt den i blocket, t.ex. Antagande_med eller Tidsaspekt.
   Exempel:
     Drivare 2 | ΔA | Tidsaspekt: per effektår enligt Drivare 1 (bensin), därefter 0
     Drivare 3 | - | Overlap_faktor: 0.0
   Rätta med fältrader, även när flera fält i samma block ändras. Bara om en
   drivare behöver en ny parameter eller byggas om i grunden skriver du i
   stället hela blocket, med första raden "Drivare N: [namn]". Behövs inga
   rättelser, skriv "Inga".

Utanför drivarblocken: börja aldrig en rad med "Drivare N:". Skriv "Drivare N
(kort namn)" när du hänvisar till en drivare i löptext.
</delsteg>"""


def assemble(parts: list[Part], merge_text: str) -> tuple[str, list[int]]:
    """Build the final evidens text from the merge frame and the part blocks.

    Returns (text, numbers of the drivers the merge corrected)."""
    text, corrected, _ = assemble_with_skipped(parts, merge_text)
    return text, corrected


def assemble_with_skipped(parts: list[Part], merge_text: str) -> tuple[str, list[int], list[str]]:
    """assemble, plus the field edits that were skipped because their target
    is not in the block (EditTargetMissing), one message each. The same
    messages stand at the end of the text, under SKIPPED_NOTE, so the QA and
    report steps read them too."""
    text = (merge_text or '').strip()
    if text.count(MARK_DRIVERS) != 1:
        raise EvidensSplitError(
            'Sammanfogningen saknar platsen för drivarblocken '
            f'({MARK_DRIVERS}), så underlaget kan inte sättas ihop.')
    if text.count(MARK_CORRECTIONS) != 1:
        raise EvidensSplitError(
            f'Sammanfogningen saknar avsnittet för korrigeringar ({MARK_CORRECTIONS}).')
    head, rest = text.split(MARK_DRIVERS)
    if rest.find(MARK_CORRECTIONS) == -1:
        raise EvidensSplitError('Korrigeringarna står före drivarblocken i sammanfogningen.')
    tail, corrections = rest.split(MARK_CORRECTIONS)

    by_number = {p.driver.number: p.block for p in parts}
    corrected: list[int] = []

    def mark(number: int) -> None:
        if number not in corrected:
            corrected.append(number)

    # Whole-block replacements first, then field edits on top of whatever
    # block stands, so a merge may rebuild one driver and patch another.
    edits = []
    kept = []
    for line in corrections.splitlines():
        edit = _FIELD_EDIT.match(_edit_shape(line))
        if edit:
            edits.append(edit)
        else:
            kept.append(line)
    corrections = '\n'.join(kept)

    replaced: set[int] = set()
    matches = list(_DRIVER.finditer(corrections))
    # Whatever is left before the first replacement block must not be an edit
    # the parser could not read. The merge's own check says it changed the
    # field; dropping the line quietly would pass the contradiction on.
    labels = {_norm(m.group('label')) for b in by_number.values()
              for m in map(_LABELLED.match, b.splitlines()) if m}
    first = matches[0].start() if matches else len(corrections)
    for line in corrections[:first].splitlines():
        _refuse_unread_edit(line, labels)
    for i, match in enumerate(matches):
        number = int(match.group('number'))
        if number not in by_number:
            raise EvidensSplitError(
                f'Sammanfogningen korrigerar drivare {number}, som inte finns i analysen.')
        end = matches[i + 1].start() if i + 1 < len(matches) else len(corrections)
        block = corrections[match.start():end].strip()
        # A stray sentence starting "Drivare 1:" must never replace a real
        # block, so a replacement has to have a block's shape.
        if not _is_block(block):
            raise EvidensSplitError(
                f'Sammanfogningen har en rad om drivare {number} i rättelserna som varken är '
                f'en fälträttelse eller ett helt drivarblock: "{block.splitlines()[0][:80]}".')
        for line in block.splitlines()[1:]:
            _refuse_unread_edit(line, labels, in_block=True)
        if number in replaced:
            raise EvidensSplitError(
                f'Sammanfogningen skriver om drivare {number} två gånger.')
        replaced.add(number)
        by_number[number] = block
        mark(number)

    skipped: list[str] = []
    for edit in edits:
        number = int(edit.group('number'))
        if number not in by_number:
            raise EvidensSplitError(
                f'Sammanfogningen korrigerar drivare {number}, som inte finns i analysen.')
        try:
            by_number[number] = apply_field_edit(
                by_number[number], number, edit.group('param'), edit.group('label'),
                edit.group('value'))
        except EditTargetMissing as e:
            # Not marked as corrected: nothing in the block changed.
            skipped.append(str(e))
            continue
        mark(number)

    head = _without_trailing_heading(head)

    blocks = '\n\n'.join(by_number[n] for n in sorted(by_number))
    tail = _defuse_driver_lines(tail).strip()
    if skipped:
        # Defused like the tail: a message starts "Rättelsen av drivare N",
        # never "Drivare N:", but the rule holds for every line outside the
        # blocks.
        note = '\n'.join([SKIPPED_NOTE.format(n=len(skipped))]
                         + [f'- {m}' for m in skipped])
        if 'Samstämmighetskontroll' not in tail:
            # The prompt puts that section last; a merge that left it out
            # still gets the note under a heading of its own, not in a card.
            note = f'## Samstämmighetskontroll\n{note}'
        tail = f'{tail}\n\n{_defuse_driver_lines(note)}'.strip()
    final = (f'{_defuse_driver_lines(head).rstrip()}\n\n{DRIVER_SECTION_HEADING}\n\n'
             f'{blocks}\n\n{tail}\n')
    return final, corrected, skipped


_SECTION_HEADING_LINE = re.compile(
    r'[ \t]*+(?:#{1,6}[ \t]*+)?(?:\d\)[ \t]*+)?\**+[ \t]*+'
    r'Antaganden per drivare[ \t]*+:?\**+[ \t]*+', re.IGNORECASE)


def _without_trailing_heading(head: str) -> str:
    """The model sometimes writes the section heading right before the marker
    anyway; the code adds its own, so drop a trailing duplicate.

    Read from the end, a line at a time: as one pattern over the whole text it
    was tried from every line and took seconds on a long head (S3). The first
    line stays whatever it says, as it did under the pattern."""
    lines = head.rstrip().split('\n')
    while len(lines) > 1 and _SECTION_HEADING_LINE.fullmatch(lines[-1]):
        lines.pop()
    return '\n'.join(lines)

# Runs of blanks are possessive and the free-text parts end on a non-blank,
# for the reason given in caia/evidence.py (security review S3): the merge
# reads these lines from text the client sends. One difference from the
# pattern before: a label of nothing but blanks ("Drivare 1 | p |  : x") is no
# longer read as an edit; no block has such a field.
_FIELD_EDIT = re.compile(
    r'^[ \t]*+(?:[-*+][ \t]++)?Drivare[ \t]*+(?P<number>\d+)[ \t]*+\|[ \t]*+'
    r'(?P<param>(?:[ \t]*+[^| \t\n])*?)[ \t]*+\|[ \t]*+'
    r'(?P<label>(?:[ \t]*+[^:| \t\n])+?)[ \t]*+:[ \t]*+'
    r'(?P<value>(?:[ \t]*+[^ \t\n])*?)[ \t]*+$',
    re.IGNORECASE,
)


def _edit_shape(line: str) -> str:
    """A field edit as the prompt asks for it, from the shapes a model slips
    into: a table row with outer pipes, a numbered list marker, a bold driver
    name. Only the frame is touched, never the value."""
    s = line.strip()
    if s.startswith('|') and s.endswith('|') and s.count('|') >= 4:
        s = s[1:-1].strip()
    s = re.sub(r'^(?:[-*+]|\d+[.)])[ \t]+', '', s)
    return re.sub(r'^(\*\*|__)(Drivare[ \t]*\d+)\1', r'\2', s, flags=re.IGNORECASE)


_NAMES_DRIVER = re.compile(r'Drivare[ \t]*\d+', re.IGNORECASE)
_ONE_BLANK = re.compile(r'[ \t]+')

# An edit without its pipes: the driver, maybe "(short name)", then at most a
# parameter name set off by dashes or commas, then a field label and a colon.
# A sentence that merely mentions a field ("Drivare 2 och 3 har samma
# Tidsaspekt: ...") has words between the driver and the label and passes.
# Matched against the line with each run of blanks made one blank (see
# _refuse_unread_edit): the pattern's own runs of blanks sit next to a class
# that also takes blanks, and on a long run that costs seconds (S3). The
# number and the label are possessive for the same reason: a label may hold
# digits, so "Drivare 111…" without a colon was tried at every split between
# the two (17 s at 40 000 digits). No field label is a number, so nothing
# real was read as "driver 1, label 23".
_EDIT_LIKE = re.compile(
    r'^Drivare[ \t]*\d++(?:[ \t]*\([^)\n]*\))?[ \t]*'
    r'(?:[-–—,.][ \t]*(?:[^-–—,.:|\n]{1,80}?[ \t]*[-–—,][ \t]*)?)?'
    r'(?P<label>[^\s:|]++)[ \t]*+:', re.IGNORECASE)


def _refuse_unread_edit(line: str, labels: set[str], in_block: bool = False) -> None:
    """A line that was not read as a correction but is one: it names a
    driver next to the field separator, or it is an edit written without
    the separators (a driver, then one of the blocks' field labels and a
    colon). Prose such as "Drivare 1 och 2 stämmer överens" passes.

    Inside a replacement block, so does one of the block's own fields,
    "Kommentar_antagande: ... | ... Drivare 2 ...": the block is made of such
    lines, and a value may hold a pipe and name another driver (TLF workshop
    2026-10-14, where the step stopped on one). Outside a block the same line
    belongs to no driver, so it is still refused."""
    field = _LABELLED.match(line)
    if in_block and field and _norm(field.group('label')) in labels:
        return
    shaped = _edit_shape(line)
    # The label it reads holds no blanks, so making every run one blank
    # changes nothing it reports, and keeps the match linear (S3).
    edit_like = _EDIT_LIKE.match(_ONE_BLANK.sub(' ', shaped))
    if (('|' in line and _NAMES_DRIVER.search(line))
            or (edit_like and _norm(edit_like.group('label')) in labels)):
        raise EvidensSplitError(
            'Sammanfogningen har en rättelse som programmet inte kan läsa: '
            f'"{line.strip()[:100]}". Formen är "Drivare N | parameter | Fältetikett: nytt värde".')


def apply_field_edit(block: str, number: int, param: str, label: str, value: str) -> str:
    """Replace one field's value in a driver block, keeping label and indent.

    A parameter or field that is not in the block raises EditTargetMissing,
    which assemble turns into a skipped edit with a note in the text: the
    merge decided the block was wrong, so dropping the fix silently would pass
    the contradiction on while the check claims it was fixed, and failing the
    step stopped a whole paid package over one line (2026-10-21). An empty
    value or an ambiguous parameter name still fails the step."""
    lines = block.splitlines()
    param = param.strip().strip('*_ ')
    want = _norm(label)
    if not value.strip():
        raise EvidensSplitError(
            f'Rättelsen av drivare {number} ({label}) saknar ett nytt värde.')

    starts = [i for i, line in enumerate(lines) if _PARAMETER.match(line)]
    if param in ('', '-', '–'):
        lo, hi = 0, (starts[0] if starts else len(lines))
    else:
        found = []
        for k, i in enumerate(starts):
            name, _ = _split_param_name(_PARAMETER.match(lines[i]).group('name').strip().strip('*_ '))
            if name.casefold() == param.casefold():
                found.append((i + 1, starts[k + 1] if k + 1 < len(starts) else len(lines)))
        if not found:
            raise EditTargetMissing(
                f'Rättelsen av drivare {number} gäller parametern "{param}", som inte finns i blocket.')
        if len(found) > 1:
            # Two parameters called "annan" happen; guessing which one the
            # merge meant could change the wrong number.
            raise EvidensSplitError(
                f'Rättelsen av drivare {number} gäller parametern "{param}", men blocket har '
                f'{len(found)} parametrar med det namnet.')
        lo, hi = found[0]

    for i in range(lo, hi):
        m = _LABELLED.match(lines[i])
        if not m or _norm(m.group('label')) != want:
            continue
        indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        lines[i] = f'{indent}{m.group("label").strip()}: {value.strip()}'
        # Drop the old value's continuation lines, or they would be read as
        # the tail of the new one.
        j = i + 1
        while j < hi and lines[j].strip() and not _LABELLED.match(lines[j]) \
                and not _PARAMETER.match(lines[j]):
            j += 1
        del lines[i + 1:j]
        return '\n'.join(lines)
    where = f'parametern "{param}"' if param not in ('', '-', '–') else 'drivarnivån'
    raise EditTargetMissing(
        f'Rättelsen av drivare {number} gäller fältet "{label}" på {where}, som inte finns i blocket.')


def _is_block(block: str) -> bool:
    """A driver block's shape: a Mekanism field, and either a parameter with
    an assumption span or an explicit statement that it is not quantified.
    Keyword presence alone is not enough: "ingen ändring, kvantifieras som
    förut" contains the word and is not a block."""
    labels = []
    has_param = False
    for line in block.splitlines()[1:]:
        if _PARAMETER.match(line):
            has_param = True
            continue
        m = _LABELLED.match(line)
        if m:
            labels.append((_norm(m.group('label')), m.group('value')))
    names = [name for name, _ in labels]
    if 'mekanism' not in names:
        return False
    if has_param and any(n.startswith('antagande_') for n in names):
        return True
    return any('kvantifieras' in value.lower() for _, value in labels)


def _defuse_driver_lines(text: str) -> str:
    """A line like "Drivare 1: påverkas via ΔA" in the overview sections reads
    as a driver heading to the panel parser, which would draw a second, empty
    card for driver 1. Only the assembled blocks may start that way, so any
    such line outside them is rewritten to "Drivare 1 (påverkas via ΔA)"."""
    def repl(match: re.Match) -> str:
        name = match.group('name').strip().strip('*_ ')
        return f"Drivare {match.group('number')} ({name})" if name else f"Drivare {match.group('number')}"
    return _DRIVER.sub(repl, text)


def check_parts_cover(drivers: list[Driver], parts: list[Part]) -> None:
    """Every driver exactly once. Called by the merge endpoint on whatever the
    client sent, so a client that lost a part cannot produce an underlag."""
    want = [d.number for d in drivers]
    got = [p.driver.number for p in parts]
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    dupes = sorted({n for n in got if got.count(n) > 1})
    problems = []
    if missing:
        problems.append('delresultat saknas för drivare ' + ', '.join(map(str, missing)))
    if extra:
        problems.append('delresultat för okända drivare ' + ', '.join(map(str, extra)))
    if dupes:
        problems.append('dubbla delresultat för drivare ' + ', '.join(map(str, dupes)))
    if problems:
        raise EvidensSplitError('Underlaget är ofullständigt: ' + '; '.join(problems) + '.')


def run_merge(history: list[dict], parts: list[Part], data_context: str = '',
              mode: str = POTENTIAL) -> tuple[str, list[int], list[str]]:
    parts = sorted(parts, key=lambda p: p.driver.number)
    system = _context_system(merge_instruction(parts), data_context)
    text = complete('evidens_merge', for_mode(system, 'evidens_merge', mode), history,
                    MERGE_MAX_OUTPUT)
    return assemble_with_skipped(parts, text)
