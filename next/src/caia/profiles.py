"""Parse the intake agent's åtgärdsprofil text into structured profiles.

The intake agent emits one or more profiles as markdown following a fixed
template (see agents/intake.py):

    ÅTGÄRDSPROFIL 1
    *Namn:* Bilpool för anställda
    *Beskrivning:* ...
    *Sektor:* transporter
    *Rådighet:* direkt (ANTAGANDE: kommunen äger fordonen)

The web UI renders these as cards in the results panel instead of dumping the
raw markdown into the chat. Parsing lives here, in Python, so it can be tested
against real agent output rather than guessed at in the browser.

The parser is deliberately forgiving: the source is a language model, so
anything it does not recognise is preserved rather than dropped. A caller that
gets an empty profile list should fall back to showing the raw text.
"""
from __future__ import annotations

import re

# Runs of blanks are possessive and the free-text title ends on a non-blank,
# for the reason given in caia/evidence.py (security review S3): two runs of
# blanks next to each other made one long line of blanks cost seconds.
_TEXT = r'(?:[ \t]*+[^ \t\n])*?'

# "ÅTGÄRDSPROFIL", "ÅTGÄRDSPROFIL 2", "**ÅTGÄRDSPROFIL 2**", "## ÅTGÄRDSPROFIL 2:",
# and "ÅTGÄRDSPROFIL 1: Bilpool för anställda", where the model puts the title on
# the heading line. `title` keeps that text so it can stand in for a missing Namn.
_HEADING = re.compile(
    r'^[ \t]*+(?:#{1,6}[ \t]*+)?(?:\*{1,2}|_{1,2})?[ \t]*+'
    r'ÅTGÄRDSPROFIL'
    r'(?:[ \t]*+(?P<number>\d+))?'
    rf'[ \t]*+(?:[:\-–][ \t]*+(?P<title>{_TEXT}))?'
    r'[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+$',
    re.MULTILINE | re.IGNORECASE,
)

# "*Namn:* value", "**Namn:** value", "- **Namn:** value", "Namn: value".
# `marked` records whether the line carried a bullet or emphasis: an unmarked
# "Label: value" line is only trusted when the label is one the template defines.
_FIELD = re.compile(
    r'^[ \t]*+(?P<marked>(?:[-*+][ \t]++)?(?:\*{1,2}|_{1,2})?)[ \t]*+'
    r'(?P<label>[A-Za-zÅÄÖåäö][^:*_\n]{0,60}?)'
    r'[ \t]*+:?[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+:[ \t]*+'
    r'(?P<value>.*)$'
)

# Start of "(ANTAGANDE: tidsram 2026-2030)". Also accepts "ANTAGANDEN" and a
# missing colon. Where the marker *ends* is found by scanning, not by regex: a
# note may quote a decision reference "(KF 2019:44)", and a non-greedy match
# would stop at that inner parenthesis and leave a stray ")" in the value.
_ASSUMPTION_START = re.compile(r'\(\s*ANTAGANDEN?\s*[:.]?\s*', re.IGNORECASE)

# Fields the template defines, in template order. Used for ordering only:
# unknown fields are kept and appended, never discarded.
FIELD_ORDER = [
    'Namn',
    'Beskrivning',
    'Omfattning',
    'Sektor',
    'Drivare',
    'Målgrupp',
    'Utsläpp som påverkas',
    'Rådighet',
    'Typ av åtgärd',
    'Mognad',
    'Tidsram',
    'Kommun',
    'Kommentarer',
]
_ORDER_INDEX = {label.casefold(): i for i, label in enumerate(FIELD_ORDER)}


def _split_assumptions(value: str) -> tuple[str, list[str]]:
    """Lift "(ANTAGANDE: ...)" markers out of a field value.

    Returns the value with the markers removed and the assumption texts. An
    empty marker "(ANTAGANDE)" still counts as an assumption: the agent flagged
    the field even when it did not say why.

    A marker that is never closed (the model was cut off mid-sentence) runs to
    the end of the value rather than being ignored. Dropping it would leave the
    field looking like a stated fact, which is the one thing the chip exists to
    prevent.
    """
    notes: list[str] = []
    out: list[str] = []
    pos = 0
    while True:
        match = _ASSUMPTION_START.search(value, pos)
        if not match:
            out.append(value[pos:])
            break
        out.append(value[pos:match.start()])
        depth = 1
        i = match.end()
        while i < len(value) and depth:
            if value[i] == '(':
                depth += 1
            elif value[i] == ')':
                depth -= 1
                if not depth:
                    break
            i += 1
        notes.append(' '.join(value[match.end():i].split()))
        pos = i + 1 if i < len(value) else len(value)

    cleaned = ''.join(out)
    # Collapse the whitespace and dangling punctuation the removal leaves behind.
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()
    cleaned = re.sub(r'[ \t]*([,;])[ \t]*$', '', cleaned).strip()
    return cleaned, notes


def _is_label(candidate: str, marked: bool) -> bool:
    """Guard against a wrapped sentence being read as a new field.

    A field the agent actually emitted carries markup (`*Namn:*`, a bullet).
    A bare "Syfte: minska antalet resor." inside a wrapped Beskrivning does
    not, so bare lines are only accepted for labels the template defines.
    Without this the description silently loses everything before the colon.
    """
    if not candidate or len(candidate) > 40:
        return False
    if candidate.endswith('.'):
        return False
    if not marked:
        return candidate.casefold() in _ORDER_INDEX
    return len(candidate.split()) <= 4


def _parse_fields(body: str) -> list[dict]:
    """Parse "*Label:* value" lines from one profile block.

    Continuation lines (a wrapped Beskrivning) are appended to the field above,
    so a soft-wrapped sentence does not become a field of its own.
    """
    fields: list[dict] = []
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = _FIELD.match(line)
        if match:
            label = ' '.join(match.group('label').split()).strip('*_ ')
            value = match.group('value').strip().strip('*_ ').strip()
            if _is_label(label, bool(match.group('marked').strip())):
                fields.append({'label': label, 'value': value})
                continue
        if fields:
            fields[-1]['value'] = (fields[-1]['value'] + ' ' + line.strip()).strip()

    out: list[dict] = []
    for field in fields:
        value, assumptions = _split_assumptions(field['value'])
        out.append({
            'label': field['label'],
            'value': value,
            'assumptions': assumptions,
        })
    return out


def _sort_key(field: dict, position: int) -> tuple[int, int]:
    known = _ORDER_INDEX.get(field['label'].casefold())
    if known is None:
        return (len(FIELD_ORDER), position)
    return (known, position)


def parse_profiles(text: str) -> dict:
    """Split intake output into a preamble and structured profiles.

    Returns::

        {
          'preamble': str,          # anything before the first profile heading
          'profiles': [
            {
              'index': 1,           # the heading's own number, for identity
              'position': 1,        # 1-based place in this list, for display
              'name': str,          # the Namn field, or a fallback label
              'fields': [{'label', 'value', 'assumptions': [str]}],
              'assumption_count': int,
              'unparsed': str,      # raw body, only when no field was recognised
            },
          ],
        }

    `profiles` is empty when the text holds no recognisable profile. Callers
    must handle that by falling back to the raw text: an empty list means the
    parse failed, never that the agent produced nothing.

    A heading whose body holds text but no recognisable field is kept as an
    `unparsed` profile rather than dropped. Dropping it looked like success:
    the remaining profiles rendered as cards, the raw-text fallback never
    triggered because the list was non-empty, and a whole measure disappeared
    from the panel while still travelling on to the downstream agents.
    """
    text = text or ''
    headings = list(_HEADING.finditer(text))
    if not headings:
        return {'preamble': text.strip(), 'profiles': []}

    preamble = text[:headings[0].start()].strip()

    profiles: list[dict] = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[heading.end():end]
        fields = _parse_fields(body)
        stated_number = heading.group('number')
        heading_title = (heading.group('title') or '').strip().strip('*_ ')

        if not fields:
            leftover = body.strip()
            if not leftover and not heading_title:
                continue  # a bare heading with nothing under it loses nothing
            profiles.append({
                'index': int(stated_number) if stated_number else len(profiles) + 1,
                'position': len(profiles) + 1,
                'name': heading_title or 'Åtgärd utan namn',
                'fields': [],
                'assumption_count': 0,
                'unparsed': leftover,
            })
            continue

        ordered = [f for _, f in sorted(
            ((_sort_key(f, pos), f) for pos, f in enumerate(fields)),
            key=lambda pair: pair[0],
        )]

        name = ''
        for field in ordered:
            if field['label'].casefold() == 'namn':
                name = field['value']
                break

        profiles.append({
            'index': int(stated_number) if stated_number else len(profiles) + 1,
            'position': len(profiles) + 1,
            'name': name or heading_title or 'Åtgärd utan namn',
            'fields': [f for f in ordered if f['label'].casefold() != 'namn'],
            'assumption_count': sum(len(f['assumptions']) for f in ordered),
            'unparsed': '',
        })

    return {'preamble': preamble, 'profiles': profiles}
