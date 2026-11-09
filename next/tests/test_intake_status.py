"""Intake completion is a signal the agent sends, not a substring guess.

The old rule was "the answer mentions ÅTGÄRDSPROFIL and *Namn:*". A draft
that shows a profile and then asks three questions matches it too, and the
approve button appeared in the middle of the dialogue. The agent now ends a
finished answer with a line "STATUS: KLAR" and is told never to write it in
an answer that still asks something. Without the line, a trailing question
means the agent is still asking. (V9)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia.agents import intake  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

PROFILE = """ÅTGÄRDSPROFIL
*Namn:* Bilpool för anställda
*Beskrivning:* Kommunen inför en bilpool för tjänsteresor.
*Sektor:* transporter
*Drivare:* körsträcka med tjänstebil
*Målgrupp:* kommunens anställda
*Utsläpp som påverkas:* kommunens egna utsläpp
*Rådighet:* direkt
*Typ av åtgärd:* organisation/styrning
*Tidsram:* 2026–2030 (ANTAGANDE: Tidsram 2026–2030)
*Kommun:* Karlstads kommun
*Kommentarer:* -"""


def _run(text: str, monkeypatch) -> dict:
    monkeypatch.setattr(intake, 'complete', lambda *a, **k: text)
    return intake.run_intake([{'role': 'user', 'content': 'x'}])


def test_recorded_clarifying_answer_is_not_complete(monkeypatch):
    with open(os.path.join(FIXTURES, 'intake.md'), encoding='utf-8') as f:
        text = f.read()
    assert _run(text, monkeypatch)['status'] == 'clarifying'


def test_profile_with_sentinel_is_complete_and_sentinel_is_stripped(monkeypatch):
    out = _run(PROFILE + '\n\nSTATUS: KLAR\n', monkeypatch)
    assert out['status'] == 'complete'
    assert 'STATUS' not in out['message'] and 'STATUS' not in out['profile_text']
    assert out['profiles'] and out['profiles'][0]['name'] == 'Bilpool för anställda'


def test_bold_sentinel_still_counts(monkeypatch):
    # Models decorate. "**STATUS: KLAR**" is the same signal.
    assert _run(PROFILE + '\n**STATUS: KLAR**', monkeypatch)['status'] == 'complete'


def test_draft_profile_followed_by_questions_is_still_clarifying(monkeypatch):
    # The exact case the old rule got wrong: a profile in the answer, but the
    # agent is checking it with the user before committing.
    text = ('Här är ett utkast:\n\n' + PROFILE +
            '\n\nInnan jag går vidare:\n1. Stämmer målgruppen?\n2. Finns ett mål för 2030?')
    out = _run(text, monkeypatch)
    assert out['status'] == 'clarifying'
    assert 'profiles' not in out


def test_profile_without_sentinel_or_questions_falls_back_and_logs(monkeypatch, caplog):
    with caplog.at_level('WARNING', logger='caia.agents.intake'):
        out = _run(PROFILE, monkeypatch)
    assert out['status'] == 'complete'
    assert 'STATUS: KLAR' in caplog.text


def _with_scope(scope: str) -> str:
    return PROFILE.replace('*Sektor:*', f'*Omfattning:* {scope}\n*Sektor:*', 1)


def test_draft_without_a_number_for_the_scope_is_still_clarifying(monkeypatch):
    # Henric 2026-10-15: a missing scope is asked for before the profile is
    # finished. A request without a question mark must not get the button.
    text = _with_scope('okänt') + '\n\nAnge hur många tjänstebilar som berörs.'
    out = _run(text, monkeypatch)
    assert out['status'] == 'clarifying'
    assert 'profiles' not in out


def test_draft_with_an_assumed_number_for_the_scope_falls_back_to_complete(monkeypatch):
    text = _with_scope('40 bilar (ANTAGANDE: omfattningen är inte angiven av användaren; '
                       'storleksordning för en kommun av Karlstads storlek)')
    assert _run(text, monkeypatch)['status'] == 'complete'


def test_sentinel_wins_over_a_scope_without_a_number(monkeypatch):
    # The scope check is for a model that dropped the sentinel. With the
    # sentinel the agent has said it is done, and nothing would ask instead.
    text = _with_scope('alla tjänstebilar') + '\nSTATUS: KLAR'
    assert _run(text, monkeypatch)['status'] == 'complete'


def test_sentinel_wins_over_a_question_mark_inside_a_field(monkeypatch):
    # A "?" inside a field value is not the agent asking the user something.
    text = PROFILE.replace('*Kommentarer:* -', '*Kommentarer:* Målår 2030?') + '\nSTATUS: KLAR'
    assert _run(text, monkeypatch)['status'] == 'complete'


def test_prompt_asks_for_the_sentinel_and_forbids_it_in_questions():
    assert 'STATUS: KLAR' in intake.SYSTEM_PROMPT
    assert 'ALDRIG' in intake.SYSTEM_PROMPT.split('STATUS: KLAR', 1)[1][:400]
