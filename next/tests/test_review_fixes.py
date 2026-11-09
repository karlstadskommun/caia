"""Regressions for CODE_REVIEW_2026-07-18 findings V8, S4 and W4.

All three share a shape: a failure that produced a plausible-looking success.
An empty model answer became a saved report, a Supabase error body became the
user's error message, and an unhandled exception became an HTML 500 that the
frontend parsed as JSON.
"""

from __future__ import annotations

import io
import os
import sys
from urllib.error import HTTPError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia import api_client  # noqa: E402
from caia.web import app as A  # noqa: E402


class _Block:
    def __init__(self, type_, text=''):
        self.type = type_
        self.text = text


class _Response:
    def __init__(self, blocks, stop_reason='end_turn'):
        self.content = blocks
        self.stop_reason = stop_reason


# --- V8: extract_text must not return "" -----------------------------------

def test_normal_answer_passes_through():
    resp = _Response([_Block('thinking'), _Block('text', 'Svaret.')])
    assert api_client.extract_text(resp) == 'Svaret.'


def test_truncated_answer_raises():
    """max_tokens is not partial success: downstream steps parse it as a
    complete answer and the report is what the user is shown."""
    resp = _Response([_Block('text', 'Halva rappor')], stop_reason='max_tokens')
    with pytest.raises(api_client.ModelOutputError, match='tokentak'):
        api_client.extract_text(resp)


def test_empty_text_raises():
    resp = _Response([_Block('text', '')])
    with pytest.raises(api_client.ModelOutputError):
        api_client.extract_text(resp)


def test_whitespace_only_text_raises():
    """'\\n  ' is as useless as '' but would pass a falsiness check."""
    resp = _Response([_Block('text', '\n  \t ')])
    with pytest.raises(api_client.ModelOutputError):
        api_client.extract_text(resp)


def test_no_text_block_at_all_raises():
    resp = _Response([_Block('thinking')])
    with pytest.raises(api_client.ModelOutputError):
        api_client.extract_text(resp)


# --- S4: no Supabase response bodies to the client --------------------------

def test_supabase_error_message_carries_no_response_body(monkeypatch):
    # Pinned explicitly: the module-level value depends on ambient env, and a
    # blank one builds an unparseable URL that fails before reaching the code
    # under test.
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    leaked = 'duplicate key value violates unique constraint "reports_pkey"'

    def boom(*a, **k):
        raise HTTPError(
            'https://x.supabase.co/rest/v1/reports', 409, 'Conflict', {},
            io.BytesIO(leaked.encode()),
        )

    monkeypatch.setattr(A, 'urlopen', boom)
    with pytest.raises(A.SupabaseError) as exc:
        A.supabase_request('POST', 'reports', data={'x': 1})

    message = str(exc.value)
    assert '409' in message, 'the status code is useful and safe'
    assert leaked not in message
    assert 'constraint' not in message and 'reports_pkey' not in message


# --- W4: report CRUD answers JSON, not an HTML 500 --------------------------

def test_supabase_failure_returns_json_not_html(monkeypatch):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims',
                        lambda: {'sub': 'user-1', 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})

    def boom(*a, **k):
        raise A.SupabaseError('Supabase svarade 500.')

    monkeypatch.setattr(A, 'supabase_request', boom)

    client = A.app.test_client()
    resp = client.get('/api/reports', headers={'Authorization': 'Bearer t'})

    assert resp.status_code == 502
    assert resp.mimetype == 'application/json', (
        f'frontend does r.jsonSafe() on this; got {resp.mimetype}'
    )
    assert 'error' in resp.get_json()
