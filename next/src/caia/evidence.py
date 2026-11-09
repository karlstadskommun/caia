"""Parse the evidens agent's output into drivers, factors and assumption spans.

The evidens step is the second approval gate: what the user says yes to here
becomes the numbers the calculation runs on. The agent is asked for prose with
fixed field labels (see agents/evidens.py), which means the decision content
(a span of min/med/max per parameter, three climate factors per driver, a
quality grade per source) arrives as an indented wall of text.

This turns that wall back into the table it always was. Everything the parser
does not recognise is kept as a prose section rather than dropped, so a model
that drifts from the template loses formatting, never content.
"""
from __future__ import annotations

import re

# How these patterns stay linear (security review S3). A run of blanks
# written `[ \t]*` next to another such run, with only optional tokens
# between, can split the same blanks between them in every possible way, and
# a long line of blanks then costs seconds per line. So every run of blanks
# is possessive (`*+`, `++`: once taken, never handed back; Python 3.11+),
# which changes nothing that matches, because what follows a run is never a
# blank. A free-text tail ("name", then optional bold, then end of line) is
# `_TEXT`: words separated by blanks, ending on a non-blank, so the end of a
# long run of blanks is only looked for once per word instead of once per
# blank. It captures exactly what the lazy `.*?` before it captured.
_TEXT = r'(?:[ \t]*+[^ \t\n])*?'

# "Drivare 1: Kvarvarande fossila uppvärmningssystem", with optional markdown.
_DRIVER = re.compile(
    r'^[ \t]*+(?:#{1,6}[ \t]*+)?(?:\*{1,2}|_{1,2})?[ \t]*+'
    r'Drivare[ \t]*+(?P<number>\d+)[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+[:\-–][ \t]*+'
    rf'(?P<name>{_TEXT})[ \t]*+(?:\*{{1,2}}|_{{1,2}})?[ \t]*+$',
    re.MULTILINE | re.IGNORECASE,
)

# "  Parameter: ΔA" starts a parameter block inside a driver.
_PARAMETER = re.compile(
    r'^[ \t]*+(?:[-*+][ \t]++)?(?:\*{1,2}|_{1,2})?[ \t]*+'
    r'Parameter[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+:[ \t]*+'
    rf'(?P<name>{_TEXT})[ \t]*+$',
    re.IGNORECASE,
)

# "    Antagande_min: -0,05 (5 % minskning)" and friends.
_LABELLED = re.compile(
    r'^[ \t]*+(?:[-*+][ \t]++)?(?:\*{1,2}|_{1,2})?[ \t]*+'
    r'(?P<label>[A-Za-zÅÄÖåäö_][A-Za-zÅÄÖåäö_ ]{0,40}?)'
    r'[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+:[ \t]*+'
    r'(?P<value>.*)$',
)

# Section headings the template asks for, used to keep leftover prose readable.
_SECTION = re.compile(
    r'^[ \t]*+(?:#{1,6}[ \t]*+)?(?:\d\)[ \t]*+)?(?:\*{1,2}|_{1,2})?[ \t]*+'
    r'(?P<title>Kort om detta steg|Underlag från tidigare steg|'
    r'Påverkade drivare och parametrar|Antaganden per drivare|'
    r'Nyckelantaganden[ \t]*+[–\-][ \t]*+överblick|Nyckelantaganden|'
    r'Övergripande antaganden och scenariologik|Dataluckor för detta steg|'
    r'Externa källor och studier|Samstämmighetskontroll)'
    r'[ \t]*+:?[ \t]*+(?:\*{1,2}|_{1,2})?[ \t]*+$',
    re.MULTILINE | re.IGNORECASE,
)

_FACTOR_LABELS = {
    'territoriell_faktor': 'territoriell',
    'konsumtion_faktor': 'konsumtion',
    'overlap_faktor': 'overlap',
    'överlapp_faktor': 'overlap',
}
_SPAN_LABELS = {
    'antagande_min': 'min',
    'antagande_med': 'med',
    'antagande_medel': 'med',
    'antagande_max': 'max',
}
_PARAM_LABELS = {
    'enhet': 'enhet',
    'tidsaspekt': 'tidsaspekt',
    'källor': 'kallor',
    'kallor': 'kallor',
    'kvalitet': 'kvalitet',
    'lokaliserbarhet': 'lokaliserbarhet',
    'kommentar_antagande': 'kommentar',
    'kommentar': 'kommentar',
}


def _norm(label: str) -> str:
    return ' '.join(label.split()).strip('*_ ').casefold()


def _number(value: str):
    """Pull a leading number out of "0,9 (90 % av territoriell effekt)"."""
    match = re.match(r'[ \t]*(-?\d+(?:[.,]\d+)?)', value or '')
    if not match:
        return None
    try:
        return float(match.group(1).replace(',', '.'))
    except ValueError:
        return None


def _split_sources(value: str) -> list[str]:
    """Sources arrive as a comma or semicolon separated run of names.

    A separator inside parentheses does not split: the next parenthesis after
    it is a closing one. That used to be a lookahead reading to the end of the
    line from every separator, so a long run of commas cost time that grew
    with its square (security review S3). The next parenthesis is now worked
    out once, from the right.
    """
    value = value or ''
    next_paren = [''] * len(value)
    seen = ''
    for i in range(len(value) - 1, -1, -1):
        next_paren[i] = seen
        if value[i] in '()':
            seen = value[i]
    parts, start = [], 0
    for i, ch in enumerate(value):
        if ch in ';,' and next_paren[i] != ')':
            parts.append(value[start:i])
            start = i + 1
    parts.append(value[start:])
    return [' '.join(p.split()) for p in parts if p and p.strip()]


def _split_param_name(raw: str) -> tuple[str, str]:
    """Separate a parameter's short name from its parenthetical gloss.

    Real output names a parameter "adoption (andel av BAU-2030:s kvarvarande
    icke-laddbara delflotta som ytterligare ställs om ...)". Rendering that
    whole string as a heading buries the one word that identifies the row, so
    the gloss is split off and shown as supporting text.
    """
    raw = ' '.join((raw or '').split())
    if not raw:
        return 'Parameter', ''
    head, sep, tail = raw.partition('(')
    head = head.strip(' :-–')
    if sep and head:
        return head, tail.rstrip(') ').strip()
    return raw, ''


def _parse_driver_body(body: str) -> dict:
    """Read one driver block: mechanism, climate factors, parameter spans."""
    driver = {
        'mekanism': '',
        'factors': {'territoriell': None, 'konsumtion': None, 'overlap': None,
                    'motivering': ''},
        # What the agent literally wrote per factor. It does not always write a
        # number: an enabler whose effect is counted on another driver gets
        # "– (kvantifieras ej separat)", and that reason belongs on the card.
        'factors_text': {'territoriell': '', 'konsumtion': '', 'overlap': ''},
        'parameters': [],
        'extra': [],
    }
    current = None

    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        start = _PARAMETER.match(line)
        if start:
            name, detail = _split_param_name(start.group('name').strip().strip('*_ '))
            current = {
                'name': name, 'detail': detail,
                'min': '', 'med': '', 'max': '', 'enhet': '', 'tidsaspekt': '',
                'kallor': [], 'kvalitet': '', 'lokaliserbarhet': '', 'kommentar': '',
            }
            driver['parameters'].append(current)
            continue

        match = _LABELLED.match(line)
        if not match:
            # Continuation of whatever field came last.
            if current and current.get('_last'):
                current[current['_last']] += ' ' + line.strip()
            continue

        label = _norm(match.group('label'))
        value = match.group('value').strip().strip('*_ ').strip()

        if label == 'mekanism':
            driver['mekanism'] = value
            current = None
            continue
        if label in _FACTOR_LABELS:
            key = _FACTOR_LABELS[label]
            driver['factors'][key] = _number(value)
            # Strip a leading dash placeholder: "– (kvantifieras ej separat)".
            driver['factors_text'][key] = re.sub(r'^[–\-—]\s*', '', value).strip()
            continue
        if label in ('motivering_faktorer', 'motivering'):
            driver['factors']['motivering'] = value
            continue
        if label.startswith('klimatfaktorer'):
            continue

        if current is None:
            driver['extra'].append({'label': match.group('label').strip(), 'value': value})
            continue

        if label in _SPAN_LABELS:
            current[_SPAN_LABELS[label]] = value
            current['_last'] = _SPAN_LABELS[label]
        elif label in _PARAM_LABELS:
            key = _PARAM_LABELS[label]
            if key == 'kallor':
                current['kallor'] = _split_sources(value)
                current['_last'] = None
            else:
                current[key] = value
                current['_last'] = key
        else:
            driver['extra'].append({'label': match.group('label').strip(), 'value': value})

    for parameter in driver['parameters']:
        parameter.pop('_last', None)
    return driver


def parse_evidence(text: str) -> dict:
    """Split evidens output into drivers and the prose around them.

    Returns::

        {
          'title': str,
          'drivers': [{'number', 'name', 'mekanism', 'factors', 'parameters', 'extra'}],
          'sections': [{'title': str, 'body': str}],   # everything that is not a driver
        }

    `drivers` is empty when nothing matched, and the caller falls back to the
    raw markdown. The prose sections are always returned, so the reasoning the
    agent wrote stays available even when the structure parses cleanly.
    """
    text = text or ''
    drivers_found = list(_DRIVER.finditer(text))

    title = ''
    for line in text.splitlines():
        if line.strip():
            title = line.strip().strip('*_# ')
            break

    drivers = []
    for i, match in enumerate(drivers_found):
        end = drivers_found[i + 1].start() if i + 1 < len(drivers_found) else len(text)
        body = text[match.end():end]
        # A driver block ends where the next top-level section begins.
        section = _SECTION.search(body)
        if section:
            body = body[:section.start()]
        parsed = _parse_driver_body(body)
        parsed['number'] = int(match.group('number'))
        parsed['name'] = match.group('name').strip().strip('*_ ') or f"Drivare {parsed['number']}"
        drivers.append(parsed)

    # Prose sections, so nothing the agent wrote is lost when drivers parse.
    sections = []
    headings = list(_SECTION.finditer(text))
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[match.end():end]
        # Strip driver blocks out of the section body; they render as cards.
        for driver in reversed(list(_DRIVER.finditer(body))):
            body = body[:driver.start()]
        body = body.strip()
        if body:
            sections.append({'title': ' '.join(match.group('title').split()), 'body': body})

    return {'title': title, 'drivers': drivers, 'sections': sections}
