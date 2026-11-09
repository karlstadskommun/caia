"""The two kinds of analysis CAIA runs.

"potential" (förväntad potential) is what CAIA was built for: what can this
measure achieve? "uppfoljning" (uppföljning) asks what a measure that has been
carried out actually caused, with the money it was given. The questions
differ in their counterfactual, in what anchors the numbers and in what the
report must separate, so every step is told which one it is answering
(agents/uppfoljning.py) and the engine sums the years the follow-up needs
(calc.engine). Potential is the default, and with it every prompt and every
number is exactly what it was before the mode existed.

The mode travels with every request, like the history: the server is
stateless and the client sends both.
"""
from __future__ import annotations

POTENTIAL = "potential"
UPPFOLJNING = "uppfoljning"
MODES = (POTENTIAL, UPPFOLJNING)

_ALIAS = {
    "potential": POTENTIAL, "förväntad potential": POTENTIAL, "forvantad": POTENTIAL,
    "uppfoljning": UPPFOLJNING, "uppföljning": UPPFOLJNING, "followup": UPPFOLJNING,
}


def mode_of(v) -> str:
    """The mode a request names. Missing means potential; an unknown name
    raises, so a typo never runs a follow-up as a potential analysis."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return POTENTIAL
    if not isinstance(v, str):
        raise ValueError("mode ska vara text.")
    mode = _ALIAS.get(v.strip().lower())
    if mode is None:
        raise ValueError(f"Okänt analysläge {v!r}; ska vara {POTENTIAL!r} eller {UPPFOLJNING!r}.")
    return mode
