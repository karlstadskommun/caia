"""A comment at the EMAP or baslinje gate: framed for the model, and the
answer split into a reply for the chat and a version for the panel."""
from __future__ import annotations

import pytest

from caia.feedback import FRAME, REPLY_CLOSE, REPLY_OPEN, frame_history, split_reply

HISTORY = [
    {'role': 'user', 'content': 'Åtgärd'},
    {'role': 'assistant', 'content': 'EMAP v1'},
    {'role': 'user', 'content': 'Varför är nivån System?'},
]


def test_only_the_last_turn_is_framed_and_the_history_is_left_alone():
    framed = frame_history(HISTORY)
    assert framed[:2] == HISTORY[:2]
    assert framed[-1]['role'] == 'user'
    assert 'Varför är nivån System?' in framed[-1]['content']
    assert REPLY_OPEN in framed[-1]['content'] and REPLY_CLOSE in framed[-1]['content']
    assert HISTORY[-1]['content'] == 'Varför är nivån System?'  # not mutated


def test_a_history_that_does_not_end_in_a_comment_is_not_framed():
    assert frame_history(HISTORY[:2]) == HISTORY[:2]
    assert frame_history([]) == []


def test_the_frame_asks_for_the_whole_version_not_only_the_changes():
    assert 'hela den uppdaterade versionen' in FRAME
    assert 'aldrig bara ändringarna' in FRAME


@pytest.mark.parametrize('output, reply, version', [
    (f'{REPLY_OPEN}\nJag ändrade nivån.\n{REPLY_CLOSE}\n\n## EMAP\nv2', 'Jag ändrade nivån.', '## EMAP\nv2'),
    # A preamble before the block is not analysis.
    (f'Okej!\n{REPLY_OPEN}Svar{REPLY_CLOSE}\n## EMAP\nv2', 'Svar', '## EMAP\nv2'),
    # The block last: the version is what came before it.
    (f'## EMAP\nv2\n\n{REPLY_OPEN}Svar{REPLY_CLOSE}', 'Svar', '## EMAP\nv2'),
    # Only a reply: no version, the page keeps the one on screen.
    (f'{REPLY_OPEN}Nivån är System eftersom ...{REPLY_CLOSE}', 'Nivån är System eftersom ...', ''),
    # No block at all: all version, as before the frame.
    ('## EMAP\nv2', '', '## EMAP\nv2'),
    # A stray marker never reaches the panel.
    (f'## EMAP\nv2 {REPLY_CLOSE}', '', '## EMAP\nv2'),
    # An opened block that is never closed ends at its first blank line.
    (f'{REPLY_OPEN}Jag ändrade X.\n\n## EMAP\nv2', 'Jag ändrade X.', '## EMAP\nv2'),
])
def test_split_reply(output, reply, version):
    assert split_reply(output) == (reply, version)


@pytest.fixture
def client(monkeypatch):
    import caia.agents.baslinje_bau as B
    import caia.agents.emap as E
    import caia.web.app as A
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    sent = {}

    def fake(step, system, messages, max_output):
        sent[step] = messages
        return f'{REPLY_OPEN}Jag ändrade X.{REPLY_CLOSE}\n## {step}\nny version'
    monkeypatch.setattr(E, 'complete', fake)
    monkeypatch.setattr(B, 'complete', fake)
    return A.app.test_client(), sent


@pytest.mark.parametrize('route, step', [('/api/emap', 'emap'), ('/api/baslinje', 'baslinje')])
def test_a_gate_rerun_returns_the_reply_beside_the_version(client, route, step):
    c, sent = client
    body = c.post(route, json={'history': HISTORY, 'feedback': True}).get_json()
    assert body == {'reply': 'Jag ändrade X.', 'output': f'## {step}\nny version'}
    # The model got the comment in the frame; the request's history is not
    # what the page keeps, so nothing is written back.
    assert REPLY_OPEN in sent[step][-1]['content']
    assert 'Varför är nivån System?' in sent[step][-1]['content']


@pytest.mark.parametrize('route, step', [('/api/emap', 'emap'), ('/api/baslinje', 'baslinje')])
@pytest.mark.parametrize('flag', [None, False, 'true', 1])
def test_a_first_run_is_not_framed_and_answers_as_before(client, route, step, flag):
    c, sent = client
    payload = {'history': HISTORY}
    if flag is not None:
        payload['feedback'] = flag
    body = c.post(route, json=payload).get_json()
    assert set(body) == {'output'}
    assert sent[step][-1]['content'] == 'Varför är nivån System?'


PREVIOUS = '## EMAP\n' + 'Rad i analysen.\n' * 40


@pytest.mark.parametrize('output, reply, version', [
    # A line after the block is not the analysis: the one on screen stands.
    (f'{REPLY_OPEN}Hej{REPLY_CLOSE}\n\n(Versionen är oförändrad.)', 'Hej', ''),
    # A plain answer, no block: it is the reply, not the analysis.
    ('Det beror på att nivån gäller systemet.', 'Det beror på att nivån gäller systemet.', ''),
    # A whole version, even a shorter one, still counts.
    (f'{REPLY_OPEN}Strök åtgärd 2.{REPLY_CLOSE}\n' + PREVIOUS[:len(PREVIOUS) // 2],
     'Strök åtgärd 2.', PREVIOUS[:len(PREVIOUS) // 2].strip()),
    (f'{REPLY_OPEN}Ok.{REPLY_CLOSE}\n' + PREVIOUS, 'Ok.', PREVIOUS.strip()),
])
def test_a_short_version_against_the_one_on_screen_is_not_a_version(output, reply, version):
    assert split_reply(output, PREVIOUS) == (reply, version)


def test_the_route_compares_with_the_version_the_comment_is_about(client, monkeypatch):
    import caia.agents.emap as E
    c, _ = client
    monkeypatch.setattr(E, 'complete', lambda *a: 'Nivån gäller systemet, inte hushållen.')
    history = [HISTORY[0], {'role': 'assistant', 'content': PREVIOUS}, HISTORY[2]]
    body = c.post('/api/emap', json={'history': history, 'feedback': True}).get_json()
    assert body == {'reply': 'Nivån gäller systemet, inte hushållen.', 'output': ''}
