"""The report's calculation appendix: taken from the kalkyl step, never written
by the rapport agent.

The kalkyl step ends with an appendix the engine wrote (calc.engine.
render_appendix). /api/rapport finds that kalkyl output in the history, copies
the appendix into the report unchanged, and removes any appendix the model
wrote itself. When the kalkyl was the language model's fallback there is no
engine appendix; the report then carries the kalkyl step's own text, labelled
as such, instead of a rewrite of it.
"""
from __future__ import annotations

import re

from .calc.engine import APPENDIX_HEADING, APPENDIX_STAMP
from .pipeline import BRIDGE

FALLBACK_NOTE = ("Kalkylen räknades av språkmodellen, eftersom CAIA:s kalkylmotor inte kunde "
                 "läsa talen ur analysen. Nedan står kalkylstegets text oförändrad. Den är "
                 "inte kontrollerad av motorn.")
MISSING_NOTE = ("Kalkylstegets text fanns inte i analysens historik, så ingen beräkningsbilaga "
                "kunde bifogas.")
# The tool was called Zaid until October 2026, and the engine's stamp said so.
# A kalkyl step that ran before the rename (an analysis open in a browser
# across the deploy, a replayed history) still carries that stamp, and its
# appendix is the engine's all the same.
_STAMPS = (APPENDIX_STAMP, APPENDIX_STAMP.replace("CAIA:s kalkylmotor", "Zaids kalkylmotor"))

# A heading the model writes for its own appendix: "**Teknisk bilaga: ...**",
# "## Teknisk bilaga", "10) Beräkningsbilaga", "Bilaga 1: Beräkningssteg".
# Runs of blanks are possessive and the bold title ends on a non-blank, for
# the reason given in caia/evidence.py (security review S3). One difference
# from the patterns before: a bold line holding nothing but blanks ("** **")
# no longer matches as a bold line with a blank title; it was never an
# appendix heading either way.
_APPENDIX_WORDS = re.compile(
    r'(teknisk\s++bilaga|beräkningsbilaga|bilaga\s*+\d*+\s*+:?\s*+beräkningssteg)', re.IGNORECASE)
# The whole title is the appendix phrase, as in "Teknisk bilaga: Beräkningssteg".
_APPENDIX_TITLE = re.compile(_APPENDIX_WORDS.pattern + r'(\s*+:\s*+beräkningssteg)?\s*+:?\s*+$',
                             re.IGNORECASE)
_PREFIX = re.compile(r'^(?:[-*>]\s++)?(?:\d+\s*+[.)]\s*+)?')
_ATX = re.compile(r'^#{1,6}\s++(?:\d+\s*+[.)]\s*+)?(.*)$')
_BOLD_LINE = re.compile(r'^(?:\*\*|__)\s*+(?:\d+\s*+[.)]\s*+)?((?:[^\S\n]*+\S)+?)\s*+(?:\*\*|__)\s*+:?$')
# The appendix is the report's last section; a real one starts well past the
# middle (85-88 % into the reports measured 2026-09-30). A match earlier than
# this is a table of contents or a reference, not the appendix.
_MIN_START = 0.5


def kalkyl_output(history: list[dict]) -> str | None:
    """The kalkyl step's output: the assistant turn right before the last
    "Kalkylen är klar" bridge. None if the history has no such turn."""
    bridge = BRIDGE["kalkyl"]
    for i in range(len(history) - 1, 0, -1):
        turn = history[i]
        if turn.get("role") == "user" and turn.get("content", "").strip() == bridge:
            prev = history[i - 1]
            return prev.get("content", "") if prev.get("role") == "assistant" else None
    return None


def appendix_for_report(history: list[dict]) -> str:
    """The appendix the report ends with, taken verbatim from the kalkyl step."""
    kalkyl = kalkyl_output(history)
    if kalkyl is None:
        return f"{APPENDIX_HEADING}\n\n{MISSING_NOTE}"
    start = kalkyl.find(APPENDIX_HEADING)
    if start >= 0 and any(stamp in kalkyl[start:] for stamp in _STAMPS):
        return kalkyl[start:].strip()
    return f"{APPENDIX_HEADING}\n\n{FALLBACK_NOTE}\n\n{kalkyl.strip()}"


def _is_appendix_heading(line: str) -> bool:
    """A line that opens an appendix, as opposed to prose that mentions one.

    Three forms count: a # heading, a line that is bold from end to end, and
    a bare line that is nothing but the appendix title. A bullet, quote mark
    or section number may come first. "Se Teknisk bilaga för detaljer." and
    "**Teknisk bilaga:** se sist" are prose and stay."""
    raw = line.strip()
    if not raw:
        return False
    atx = _ATX.match(raw)
    if atx:
        return bool(_APPENDIX_WORDS.match(atx.group(1).strip('*_ ')))
    rest = _PREFIX.sub('', raw, count=1)
    bold = _BOLD_LINE.match(rest)
    if bold and '**' not in bold.group(1) and '__' not in bold.group(1):
        return bool(_APPENDIX_WORDS.match(bold.group(1)))
    return bool(_APPENDIX_TITLE.match(rest))


def strip_handwritten_appendix(text: str) -> tuple[str, bool]:
    """Cut the report at the appendix heading the model wrote.

    The appendix is the report's last section, so everything from its heading
    on is the model's own calculation. Only a heading in the second half of the
    report counts, so a table of contents never cuts the report short.
    Returns (text, whether it cut)."""
    lines = text.splitlines(keepends=True)
    earliest = len(text) * _MIN_START
    offset = 0
    for i, line in enumerate(lines):
        if offset >= earliest and _is_appendix_heading(line):
            return "".join(lines[:i]).rstrip(), True
        offset += len(line)
    return text.rstrip(), False


def with_engine_appendix(report: str, history: list[dict]) -> tuple[str, bool]:
    """The rapport agent's text without its own appendix, followed by the
    kalkyl step's. Returns (report, whether a hand-written appendix was cut)."""
    body, cut = strip_handwritten_appendix(report)
    return f"{body}\n\n{appendix_for_report(history)}\n", cut
