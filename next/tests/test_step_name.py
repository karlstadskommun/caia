"""Step 2 is called Utsläppskällor on the page. The prompts and the model's
text still say EMAP; plainTerms puts what the person reads in words. Run in
node against the page's own functions.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_key_points import _run
from test_report_row import _inline_script

pytestmark = pytest.mark.node

FIX = Path(__file__).parent / 'fixtures'


def _plain(text: str) -> str:
    import json
    return _run(f'plainTerms({json.dumps(text)})')


@pytest.mark.parametrize('raw, shown', [
    ('Jag utgår från EMAP och Baslinje & BAU.', 'Jag utgår från analysen av utsläppskällor och Baslinje.'),
    ('EMAP-analysen är godkänd.', 'Analysen av utsläppskällor är godkänd.'),
    ('Det följer av EMAP-analysen.', 'Det följer av analysen av utsläppskällor.'),
    ('EMAP-ANALYS (FÖRENKLAD VARIANT)', 'Utsläppskällor'),
    ('EMAP-analys av åtgärd: Cykelbana', 'Utsläppskällor för åtgärd: Cykelbana'),
    ('## 4. EMAP-drivare', '## 4. Drivare'),
    ('per drivare från EMAP-drivarna', 'per drivare från drivarna'),
    ('2.1 EMAP_Åtgärdstyp', '2.1 Åtgärdstyp'),
    ('**2. EMAP-kategorisering**', '**2. Klassning**'),
    ('Underlag från EMAP', 'Underlag från analysen av utsläppskällor'),
    ('I EMAP-termer är det främst styrning.', 'I analysen av utsläppskällor är det främst styrning.'),
    ('Enligt EMAP-steget gäller det.', 'Enligt steget Utsläppskällor gäller det.'),
    ('Se drivarna (EMAP).', 'Se drivarna (analysen av utsläppskällor).'),
    ('Viktigaste osäkerheter i denna EMAP-bedömning:', 'Viktigaste osäkerheter i denna bedömning:'),
    ('EMAP-underlaget är tunt.', 'Underlaget är tunt.'),
    ('EMAP-analysens drivare', 'Utsläppsanalysens drivare'),
    ('Ingen ändring här.', 'Ingen ändring här.'),
    ('En REMAP eller EMAPS rörs inte.', 'En REMAP eller EMAPS rörs inte.'),
])
def test_the_old_name_is_put_in_words(raw, shown):
    assert _plain(raw) == shown


@pytest.mark.parametrize('name', ['emap.md', 'emap.dev.md', 'baslinje.md', 'evidens.md'])
def test_no_fixture_text_shows_the_old_name(name):
    raw = (FIX / name).read_text(encoding='utf-8')
    shown = _plain(raw)
    assert not re.search(r'emap', shown, re.I), re.findall(r'.{0,30}emap.{0,30}', shown, re.I)[:3]
    # Control: the name was there to begin with, where the step is named at all.
    if name.startswith('emap'):
        assert 'EMAP' in raw


def test_the_view_is_read_from_the_raw_text_and_shown_without_the_name():
    import json
    raw = (FIX / 'emap.dev.md').read_text(encoding='utf-8')
    view = _run(f'parseEmap({json.dumps(raw)})')
    assert view and view['profiles'] and view['profiles'][0]['drivers']
    assert 'EMAP' not in json.dumps(view, ensure_ascii=False)


def test_the_page_names_the_step_utslappskallor():
    js = _inline_script()
    assert "emap: 'Utsläppskällor'" in js
    assert "button: 'Godkänn utsläppskällorna och fortsätt'" in js
    assert "agentTag === 'emap' ? 'utsläppskällor'" in js  # the chat's step tag
    # Only code and comments still carry the old name; nothing in a string the page shows.
    shown = re.findall(r"'[^'\n]*EMAP[^'\n]*'", js)
    assert all(re.search(r'FÖRENKLAD|EMAP_|\^|\\b', s) for s in shown), shown


def test_no_earlier_name_is_left_anywhere_on_the_page():
    """The step row and the Om box are written with character references
    ("Kartl&#xE4;ggning"), which a search for the word itself walks past."""
    import html
    from caia.web import app as A
    page = html.unescape(A.HTML_TEMPLATE)
    assert 'Utsläppskällor</div>' in page  # control: the step row is in this text
    assert not re.search(r'kartläggning', page, re.I), re.findall(r'.{0,40}kartläggning.{0,40}', page, re.I)[:3]
