"""The order of the analysis steps and the line that hands one to the next.

The server is stateless: the client sends the whole conversation to every
step, and between two steps it adds a user turn saying the previous one is
approved. The next agent reads that line, so every driver of the pipeline has
to write the same one. There were four copies (the web page, run_batch, the
fixture capture and the e2e test) and three of them had drifted, which made
the offline runs histories production never produces.
"""
from __future__ import annotations

import re

STEPS = ("intake", "emap", "baslinje", "evidens", "kalkyl", "qa", "rapport")

# Keyed by the step that just finished.
BRIDGE = {
    "intake": "Profilen är godkänd. Fortsätt med EMAP-analysen.",
    "emap": "EMAP-analysen är godkänd. Fortsätt med baslinje och BAU.",
    "baslinje": "Baslinjen är godkänd. Fortsätt med evidens och antaganden.",
    "evidens": "Antagandena är godkända. Fortsätt med kalkyl och tidsprofil.",
    "kalkyl": "Kalkylen är klar. Fortsätt med QA-granskning.",
    "qa": "QA är klar. Skriv slutrapporten (åtgärdskort).",
}


# What JavaScript's \\s matches, spelled out: str.rstrip() also takes U+0085
# and U+001C-1F and leaves U+FEFF, so the two joins would differ on a report
# that ends in one of those.
_TRAILING_BLANKS = re.compile(
    '[\\t\\n\\v\\f\\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+\\Z')


def with_kallmarkering(report_md: str, kallmarkering_md: str | None) -> str:
    """The report with *Talens ursprung* last, after the technical appendix.

    /api/kalkyl returns the section beside its output (`kallmarkering_md`) and
    /api/rapport does not put it in the report: whoever drives the pipeline
    does. The page does it in the browser (withKallmarkering in the page
    script) and run_batch does it here. They are two functions in two
    languages, so test_pipeline runs both on the same cases and requires the
    same text. A report without a section (an old run) is returned as it is."""
    if not kallmarkering_md:
        return report_md
    return _TRAILING_BLANKS.sub('', report_md or '') + '\n\n' + kallmarkering_md + '\n'
