"""A comment written in the chat at a gate, and the step's answer to it.

At the EMAP and baslinje gates the user can write in the chat instead of
approving. The page then runs the step again with the comment as the last
turn. Before this module the agent read the comment as an ordinary message
and answered it the way it pleased: often with a few lines about what it had
changed, sometimes with only the answer to a question. Whatever it wrote
replaced the analysis in the panel and went into the history, where the next
step read it as the analysis (Henric 2026-10-13: "analysen togs bort och jag
fick ett svar i resultatfönstret").

So the comment goes to the model inside a frame that asks for two parts: a
short reply to the person, and the whole updated version. The reply goes to
the chat, the version to the panel and the history. Only the model call sees
the frame; the history keeps what the user wrote.

The evidens gate is not framed: its re-run is split per driver and merged
(agents/evidens_split.py), and the parts and the merge have formats of their
own that the merge checks.
"""
from __future__ import annotations

import re

# The steps whose gate re-run is one model call whose answer is the panel.
FRAMED_STEPS = ("emap", "baslinje")

REPLY_OPEN = "[[SVAR]]"
REPLY_CLOSE = "[[/SVAR]]"

FRAME = (
    "Användaren har läst din senaste version och skrivit det här i chatten:\n\n"
    "<<<\n{text}\n>>>\n\n"
    "Svara i två delar, i den här ordningen.\n\n"
    f"1. Ett kort svar till användaren mellan raderna {REPLY_OPEN} och {REPLY_CLOSE}. "
    "Är det en fråga: svara på den. En fråga är ingen begäran om ändring, så ändra "
    "bara om du vid närmare eftertanke ser att något faktiskt var fel, och säg då "
    "varför. Är det en rättelse eller ett önskemål: säg vad "
    "du ändrade och varför, eller varför du inte ändrade något. Högst fem meningar, "
    "vanlig svenska, inga rubriker.\n\n"
    "2. Efter raden " + REPLY_CLOSE + ": hela den uppdaterade versionen av ditt "
    "resultat, i samma format och med samma rubriker som förra gången, med "
    "eventuella ändringar inarbetade. Skriv hela versionen även om ingenting "
    "ändrades. Skriv aldrig bara ändringarna, och nämn inte användarens kommentar "
    "i versionen: nästa steg läser den som analysen."
)

_REPLY_RE = re.compile(re.escape(REPLY_OPEN) + r"(.*?)" + re.escape(REPLY_CLOSE), re.DOTALL)
_STRAY_MARK_RE = re.compile(re.escape(REPLY_OPEN) + "|" + re.escape(REPLY_CLOSE))


def frame_history(history: list[dict]) -> list[dict]:
    """The history as the model sees it on a gate re-run: the last turn, the
    user's comment, put inside FRAME. A history that does not end in a user
    turn is returned as it is; there is no comment to frame."""
    if not history or history[-1].get("role") != "user":
        return history
    last = history[-1]
    return history[:-1] + [{"role": "user", "content": FRAME.format(text=last["content"])}]


# A version is the whole analysis again, so it cannot be a small fraction of
# the one it replaces. Measured 2026-10-13 on the EMAP fixture: two framed
# answers (a question, a correction) gave versions of 114 and 119 percent of
# the previous one, while what slips through without this check is a line
# ("(Versionen är oförändrad.)", a plain answer to a question) of well under
# one percent. A quarter leaves room for a correction that removes half of
# the analysis.
MIN_VERSION_SHARE = 0.25


def split_reply(output: str, previous: str | None = None) -> tuple[str, str]:
    """(reply, version) from a framed answer.

    The version is what follows the reply block; text before it is a
    preamble and is dropped. A model that put the block last instead has its
    version before it, and that is used. An opened block that is never closed
    ends at its first blank line.

    With `previous` (the version on screen) a "version" much shorter than it
    is not one: an answer without the block is then a reply, and a stray line
    after the block is dropped. The page keeps the version on screen when the
    returned version is empty. Without `previous` an answer without the block
    is all version, as a re-run was before the frame.
    """
    reply, version = _split(output)
    if previous and len(version) < MIN_VERSION_SHARE * len(previous.strip()):
        return (reply or version), ""
    return reply, version


def _split(output: str) -> tuple[str, str]:
    m = _REPLY_RE.search(output)
    if m:
        after = _STRAY_MARK_RE.sub("", output[m.end():]).strip()
        before = _STRAY_MARK_RE.sub("", output[:m.start()]).strip()
        return m.group(1).strip(), after or before
    i = output.find(REPLY_OPEN)
    if i >= 0:
        rest = output[i + len(REPLY_OPEN):].strip()
        reply, _, version = rest.partition("\n\n")
        return reply.strip(), _STRAY_MARK_RE.sub("", version).strip()
    return "", _STRAY_MARK_RE.sub("", output).strip()


def previous_version(history: list[dict]) -> str | None:
    """The version the comment is about: the assistant turn before it."""
    if len(history) >= 2 and history[-2].get("role") == "assistant":
        return history[-2]["content"]
    return None
