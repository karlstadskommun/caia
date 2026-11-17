"""docs/METOD.html is generated from docs/METOD.md (tools/metod_html.py).

METOD.md is the source and is what an AI reads; people read the HTML. The
first test fails when the checked-in HTML is not what the generator makes of
the current METOD.md, so the two cannot drift apart. The rest pin down that
the parts which must follow the Markdown really do: the full text, a changed
formula, a changed section (its summary is marked as possibly out of date), a
new section without a summary, and the "Under avstämning" marking.
"""
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import metod_html as mh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MD = (ROOT / 'docs' / 'METOD.md').read_text(encoding='utf-8')
SIDE = (ROOT / 'docs' / 'METOD-sammanfattningar.toml').read_text(encoding='utf-8')
TPL = (ROOT / 'next' / 'tools' / 'metod_html.template.html').read_text(encoding='utf-8')


def build(md: str = MD, side: str = SIDE) -> mh.Page:
    return mh.build(md, side, TPL)


def body(page: str) -> str:
    """The page without its style sheet, which names every class."""
    return page.split('</style>', 1)[1]


def card(page: str, slug: str) -> str:
    m = re.search(rf'<details class="[^"]*" id="{slug}">.*?</details>', page, re.S)
    assert m, f'no card {slug}'
    return m.group(0)


def test_checked_in_html_is_what_the_generator_makes():
    checked_in = (ROOT / 'docs' / 'METOD.html').read_text(encoding='utf-8')
    assert checked_in == build().html, (
        'docs/METOD.html är inte det generatorn ger ur docs/METOD.md. '
        'Kör: cd next && .venv/bin/python tools/metod_html.py, läs vad den skriver om '
        'sammanfattningar, och checka in METOD.html tillsammans med METOD.md.')


def test_every_formula_block_is_drawn_not_left_as_code():
    page = build()
    openers = re.findall(r'^```(\w*)$', MD, re.M)[0::2]
    assert page.html.count('class="formel"') == openers.count('')
    assert '<pre class="verbatim">' not in page.html
    assert not [w for w in page.warnings if 'formeln' in w]


def test_every_heading_and_paragraph_reaches_the_page():
    page = build().html
    doc = mh.parse_document(MD)
    for s in doc.all_sections():
        assert f'id="{s.slug}"' in page
    # Every prose paragraph of METOD.md shows up as text (tags and the
    # typographic changes removed).
    text = html.unescape(re.sub(r'<[^>]+>', '', page)).replace(' ', ' ').replace('”', '"')
    text = ' '.join(text.split())

    def plain(md_text: str) -> str:
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md_text)
        s = ' '.join(re.sub(r'[*`]', '', s).split())
        return s.split(':')[0] if ' = ' in s else s     # inline formula, drawn differently

    for s in doc.all_sections():
        for p in mh.paragraphs(s.body):
            if p.startswith('```'):
                continue
            if p.startswith('|'):           # every cell
                pieces = [c for row in p.split('\n') if not re.match(r'^\|[\s:|-]+\|$', row)
                          for c in row.strip('|').split('|')]
            elif p.startswith('- ') or re.match(r'\d+\. ', p):      # every item
                pieces = re.split(r'\n(?:- |\d+\. )', re.sub(r'^(- |\d+\. )', '', p))
            else:
                pieces = [p]
            for piece in pieces:
                assert plain(piece) in text, plain(piece)[:80]


def test_a_changed_formula_changes_the_page():
    old = 'netto         = territoriellt + konsumtion − överlapp'
    assert old in MD
    page = build(MD.replace(old, 'netto         = territoriellt + konsumtion − överlapp × halva')).html
    assert '<var>överlapp</var> <span class="op">×</span> <var>halva</var>' in page


def test_formula_forms():
    row = mh.formula_row('andel = (ikapp-år + 1 − köpår) / livslängd, högst 1 och lägst 0')
    assert '<span class="frac"><span class="num"><var>ikapp-år</var>' in row
    assert '<span class="den"><var>livslängd</var></span>' in row
    assert '<span class="f-note">högst 1 och lägst 0</span>' in row
    row = mh.formula_row('x = a_BAU × −ΔEF ^ (b / c)  (ton, positivt = minskning)')
    assert '<var>a</var><sub>BAU</sub>' in row
    assert '<span class="op op--unary">−</span><var>ΔEF</var><sup>' in row
    assert 'ton, positivt = minskning' in row
    assert '<var>år sedan basår</var>' in mh.formula_row('år_sedan_basår = året − basåret')
    with pytest.raises(mh.FormulaError):
        mh.formula_row('x = (a + b')
    with pytest.raises(mh.FormulaError):
        mh.formula_row('no equals sign here')


def test_an_unreadable_formula_is_shown_as_it_stands_with_a_warning():
    md = MD.replace('netto         = territoriellt + konsumtion − överlapp',
                    'netto         = territoriellt + konsumtion − överlapp [sic]', 1)
    page = build(md)
    assert '<pre class="verbatim"><code>' in page.html
    assert '[sic]' in page.html
    assert any('formeln går inte att läsa' in w for w in page.warnings)


def test_a_changed_section_marks_its_summary_as_possibly_out_of_date():
    page = build()
    assert not [w for w in page.warnings if w.startswith('Kan vara inaktuell')], page.warnings
    assert 'badge--stale' not in body(page.html)
    md = MD.replace('Tre tillägg används främst i uppföljningar:',
                    'Tre tillägg används främst i uppföljningar, och ett i båda lägena:')
    page = build(md)
    assert 'Sammanfattningen kan vara inaktuell' in card(page.html, 'infasning')
    assert 'badge--stale' not in card(page.html, 'attribution')
    assert any(w.startswith('Kan vara inaktuell: "Infasning"') for w in page.warnings)
    # And --reviewed clears it.
    side = mh.restamp(SIDE, mh.parse_document(md), {'Infasning'})
    assert 'badge--stale' not in card(build(md, side).html, 'infasning')


def test_a_changed_step_table_marks_the_flow_as_possibly_out_of_date():
    md = MD.replace('| 6 Kvalitetsgranskning | Granskar källor,', '| 6 Kvalitetsgranskning | Granskar noga källor,')
    page = build(md)
    assert 'Avsnitten det bygger på (De sju stegen) har ändrats' in page.html
    assert any(w.startswith('Kan vara inaktuell: "flode"') for w in page.warnings)


def test_a_new_section_without_summary_is_shown_with_full_text():
    md = MD.replace('## Kända begränsningar',
                    '## Ett nytt avsnitt\n\nHelt ny text om något.\n\n## Kända begränsningar')
    page = build(md)
    c = card(page.html, 'ett-nytt-avsnitt')
    assert 'Helt ny text om något.' in c
    assert 'Ingen sammanfattning än' in c
    assert any(w.startswith('Utan sammanfattning: "Ett nytt avsnitt"') for w in page.warnings)
    assert '<a href="#ett-nytt-avsnitt">' in page.html     # in the table of contents


def test_a_renamed_heading_leaves_an_orphan_and_says_so():
    md = MD.replace('### Infasning', '### Infasningen')
    page = build(md)
    assert 'Ingen sammanfattning än' in card(page.html, 'infasningen')
    assert any(w.startswith('Sammanfattning utan avsnitt: "Infasning"') for w in page.warnings)


def test_under_avstamning_follows_the_markdown():
    page = build().html
    assert 'Under avstämning</span>' in card(page, 'attribution')
    assert 'Under avstämning</span>' in card(page, 'tre-scenarier')
    assert 'Under avstämning</span>' not in card(page, 'infasning')
    assert 'id="oppet"' in page
    assert 'scenariovärdena sätts här' in page
    # Take the paragraph away and every mark goes with it.
    para = next(p for p in mh.paragraphs(mh.parse_document(MD).preamble) if p.startswith(mh.OPEN_MARK))
    page = body(build(MD.replace(para + '\n', '')).html)
    assert 'badge--open' not in page
    assert 'id="oppet"' not in page
    assert 'scenariovärdena sätts här' not in page
    assert 'dot-open' not in page
    assert 'chain-item--hot' not in page
    # Naming a section that does not exist stops the build.
    with pytest.raises(mh.MarkdownError):
        build(MD.replace('*Attribution* beskriver', '*Attributionen* beskriver'))


def test_unknown_markdown_stops_the_build_with_a_line_number():
    with pytest.raises(mh.MarkdownError, match='rad'):
        build(MD.replace('## Kända begränsningar\n', '## Kända begränsningar\n\n> ett citat\n'))
    with pytest.raises(mh.MarkdownError):
        build(MD.replace('### Infasning', '#### Infasning'))


def test_italic_section_names_link_to_the_section():
    page = build().html
    assert '<a class="xref" href="#portfoljen-flera-atgarder-tillsammans"><em>Portföljen</em></a>' in page
    assert '<a class="xref" href="#talens-ursprung-och-kontrollera-forst"><em>Talens ursprung</em></a>' in page
    assert '<em>Följ upp med</em>' in page          # not a section: stays plain


def test_the_page_needs_nothing_from_the_network():
    page = build().html
    assert not re.search(r'(src|href)="(https?:)?//', page)
    assert '@import' not in page and 'url(http' not in page


def test_the_sidecar_has_no_orphans_and_points_at_real_sections():
    page = build()
    assert not [w for w in page.warnings if 'utan avsnitt' in w or 'pekar på ett avsnitt' in w], page.warnings


def test_unsafe_or_unsupported_inline_markdown_stops_the_build():
    for bad in ('[a](javascript:alert(1))', '[a](data:text/html,x)', '![bild](a.png)',
                '***fet och kursiv***'):
        with pytest.raises(mh.MarkdownError):
            build(MD.replace('## Kända begränsningar\n', f'## Kända begränsningar\n\n{bad}\n'))
    with pytest.raises(mh.MarkdownError, match='listor i listor'):
        build(MD.replace('## Kända begränsningar\n', '## Kända begränsningar\n\n- a\n  - b\n- c\n'))
    # The introduction follows the same rules as the sections.
    with pytest.raises(mh.MarkdownError):
        build(MD.replace(mh.OPEN_MARK, '> ett citat\n\n' + mh.OPEN_MARK, 1))


def test_an_exponent_after_a_fraction_is_refused_not_misdrawn():
    with pytest.raises(mh.FormulaError):
        mh.formula_row('x = (a + b) / c ^ 2')
    assert '<sup>' in mh.formula_row('x = (a + b) / (c ^ 2)')


def test_a_heading_that_takes_a_fixed_anchor_stops_the_build():
    with pytest.raises(mh.MarkdownError, match='samma ankare'):
        build(MD.replace('## Kända begränsningar', '## Öppet\n\nText.\n\n## Kända begränsningar'))


def test_restamp_touches_only_hash_lines():
    side = SIDE.replace('sammanfattning = """\n', 'sammanfattning = """\nhash = "inte en hashrad"\n[inte en tabell]\n', 1)
    doc = mh.parse_document(MD)
    out = mh.restamp(side, doc, {e.key for e in mh.entries(doc, mh.load_sidecar(side))})
    assert 'hash = "inte en hashrad"' in out and '[inte en tabell]' in out
    before, after = mh.load_sidecar(side), mh.load_sidecar(out)
    for a, b in zip(before['avsnitt'], after['avsnitt']):
        assert {k: v for k, v in a.items() if k != 'hash'} == {k: v for k, v in b.items() if k != 'hash'}
    with pytest.raises(ValueError, match='två gånger'):
        mh.load_sidecar(SIDE + '\n[[avsnitt]]\nrubrik = "Infasning"\nhash = ""\nsammanfattning = "x"\n')


def test_the_output_does_not_depend_on_hash_seed():
    tool = ROOT / 'next' / 'tools' / 'metod_html.py'
    for seed in ('1', '2'):
        r = subprocess.run([sys.executable, '-I', str(tool), '--check', '--root', str(ROOT)],
                           env={**os.environ, 'PYTHONHASHSEED': seed}, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def _stage(tmp_path: Path) -> Path:
    stage = tmp_path / 'repo'
    for rel in ('docs/METOD.md', 'docs/METOD-sammanfattningar.toml', 'docs/METOD.html',
                'next/tools/metod_html.py', 'next/tools/metod_html.template.html'):
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, stage / rel)
    return stage


def test_the_release_build_regenerates_the_page_from_its_own_metod_md(tmp_path):
    """publicering/bygg_kandidat.py (not in the public release itself)."""
    builder = ROOT / 'publicering' / 'bygg_kandidat.py'
    if not builder.is_file():
        pytest.skip('publicering/ finns bara i förvaltarnas repo')
    import importlib.util
    spec = importlib.util.spec_from_file_location('bygg_kandidat_test', builder)
    bk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bk)
    stage = _stage(tmp_path)
    mod = bk.load_metod_html(stage)
    fresh = bk.metod_fresh_keys(stage, mod)
    md = stage / 'docs' / 'METOD.md'
    old = 'Tre tillägg används främst i uppföljningar:'
    md.write_text(md.read_text(encoding='utf-8').replace(old, 'Tre tillägg används i uppföljningar:'),
                  encoding='utf-8')
    note = bk.regenerate_metod_html(stage, mod, fresh)
    assert note.startswith('docs/METOD.html genererad')
    page = (stage / 'docs' / 'METOD.html').read_text(encoding='utf-8')
    assert 'Tre tillägg används i uppföljningar' in page
    assert 'badge--stale' not in body(page)      # was fresh before the replacement
    # A replacement that removes a heading a summary is written against stops the build.
    md.write_text(md.read_text(encoding='utf-8').replace('### Infasning', '### Infasningen'),
                  encoding='utf-8')
    with pytest.raises(SystemExit, match='rubrik'):
        bk.regenerate_metod_html(stage, mod, fresh)
