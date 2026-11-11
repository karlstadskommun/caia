"""Generate docs/METOD.html, the readable overview of docs/METOD.md.

METOD.md is the source. An AI reads the Markdown; people read the HTML. This
script turns the one into the other, and a test (tests/test_metod_html.py)
fails when the checked-in HTML is not what the script makes of the current
METOD.md, so the two cannot drift apart.

What comes from METOD.md on every run: the title, the introduction, every
heading, the full text of every section (paragraphs, lists, tables), the
formulas, and which sections are "Under avstämning" (the italic section names
in the paragraph that starts with **Under avstämning.**).

What is written by hand lives beside it in docs/METOD-sammanfattningar.toml:
a short summary per section, the seven steps of the flow diagram, the chain of
the calculation and the comparison of the two modes. Each hand-written entry
carries a hash of the METOD.md text it was written from. When that text
changes, the script says so, and the page marks the summary "kan vara
inaktuell" until someone has read the section again and run

    .venv/bin/python tools/metod_html.py --reviewed "<rubrik>"

A new section without a summary is shown with its full text only.

Formulas. A fenced code block in METOD.md is a formula block: one formula per
line, `left = right`, optionally followed by a note, either in parentheses
after two or more spaces or after a top-level ", ". The right-hand side may
use numbers (1 000, 0,5), the operators × − + / ^ and parentheses, and names.
Consecutive words form one name ("territoriell faktor"); a name with exactly
one underscore gets the part after it as a subscript (aktivitet_BAU), a name
with more underscores is read with spaces (år_sedan_basår). `( ... ) / x` is
drawn as a fraction and `x ^ y` as a superscript. A block that does not
follow the form is shown as it stands, in monospace, and the script warns; a
block fenced as ```text is always shown as it stands. Inline code of the form
`name = expression` is drawn the same way.

Only the Markdown METOD.md uses is supported (headings ## and ###,
paragraphs, - and 1. lists, tables, fenced code, **bold**, *italic*, `code`,
[links](url)). Anything else stops the script with the line number, rather
than coming out wrong. The script uses the standard library only, so the
release build can run it too.

Usage (from next/):
    .venv/bin/python tools/metod_html.py              write docs/METOD.html
    .venv/bin/python tools/metod_html.py --check      exit 1 if it is out of date
    .venv/bin/python tools/metod_html.py --reviewed "Attribution" [...]
    .venv/bin/python tools/metod_html.py --reviewed-all
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_PATH = Path('docs/METOD.md')
SIDECAR_PATH = Path('docs/METOD-sammanfattningar.toml')
OUT_PATH = Path('docs/METOD.html')

OPEN_MARK = '**Under avstämning.**'


# Links the page may carry: web and mail addresses, anchors and relative paths
# (which resolve next to METOD.html, as they do next to METOD.md).
SAFE_HREF = re.compile(r'^(https?://[^\s"<>]+|mailto:[^\s"<>]+|#[\w%-]+|[\w%./-]+(#[\w%-]+)?)$')


class MarkdownError(ValueError):
    pass


class FormulaError(ValueError):
    pass


# --- reading METOD.md --------------------------------------------------------

@dataclass
class Section:
    level: int
    title: str
    body: list[str]
    line: int
    children: list[Section] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def text(self) -> str:
        return normalize('\n'.join(self.body))

    @property
    def hash(self) -> str:
        return text_hash(self.text)


@dataclass
class Document:
    title: str
    preamble: list[str]
    sections: list[Section]          # level 2, with level 3 as children

    def all_sections(self) -> list[Section]:
        out = []
        for s in self.sections:
            out.append(s)
            out.extend(s.children)
        return out

    def by_title(self) -> dict[str, Section]:
        return {s.title: s for s in self.all_sections()}


def normalize(text: str) -> str:
    lines = [l.rstrip() for l in text.strip().split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def slugify(title: str) -> str:
    t = unicodedata.normalize('NFKD', title.lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t or 'avsnitt'


def parse_document(md: str) -> Document:
    lines = md.split('\n')
    title = None
    preamble: list[str] = []
    sections: list[Section] = []
    cur: Section | None = None
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.startswith('```'):
            in_fence = not in_fence
        if not in_fence:
            m = re.match(r'^(#{1,6}) (.+)$', ln)
            if m:
                level = len(m.group(1))
                if level == 1:
                    if title is not None or sections:
                        raise MarkdownError(f'rad {i}: bara en rubrik på nivå 1, först i filen')
                    title = m.group(2).strip()
                    continue
                if level > 3:
                    raise MarkdownError(f'rad {i}: rubriker på nivå {level} stöds inte (bara ## och ###)')
                sec = Section(level, m.group(2).strip(), [], i)
                if level == 2:
                    sections.append(sec)
                else:
                    if not sections:
                        raise MarkdownError(f'rad {i}: ### före första ##')
                    sections[-1].children.append(sec)
                cur = sec
                continue
        if cur is None:
            preamble.append(ln)
        else:
            cur.body.append(ln)
    if in_fence:
        raise MarkdownError('ett kodblock stängs aldrig')
    if title is None:
        raise MarkdownError('rubrik på nivå 1 saknas')
    titles = [s.title for s in Document(title, [], sections).all_sections()]
    dup = {t for t in titles if titles.count(t) > 1}
    if dup:
        raise MarkdownError(f'samma rubrik två gånger: {", ".join(sorted(dup))}')
    slugs = [slugify(t) for t in titles]
    dup = {s for s in slugs if slugs.count(s) > 1}
    if dup:
        raise MarkdownError(f'två rubriker ger samma ankare: {", ".join(sorted(dup))}')
    return Document(title, preamble, sections)


def paragraphs(lines: list[str]) -> list[str]:
    return [p for p in normalize('\n'.join(lines)).split('\n\n') if p.strip()]


def open_titles(doc: Document) -> tuple[str | None, list[str]]:
    """The "Under avstämning" paragraph and the section titles it names."""
    for p in paragraphs(doc.preamble):
        if p.startswith(OPEN_MARK):
            known = doc.by_title()
            names = re.findall(r'(?<!\*)\*([^*]+)\*(?!\*)', p)
            missing = [n for n in names if n not in known]
            if missing:
                raise MarkdownError('stycket Under avstämning nämner avsnitt som inte finns: '
                                    + ', '.join(missing))
            return p, names
    return None, []


# --- Markdown to HTML --------------------------------------------------------

def esc(s: str) -> str:
    return html.escape(s, quote=False)


def attr(s: str) -> str:
    return html.escape(s, quote=True)


class Renderer:
    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.titles = {s.title.lower(): s.slug for s in doc.all_sections()}
        self.warnings: list[str] = []

    # inline ---------------------------------------------------------------
    def xref(self, text: str) -> str | None:
        """Section anchor for an italic mention such as *Portföljen*."""
        t = text.strip().lower()
        if t in self.titles:
            return self.titles[t]
        hits = [slug for title, slug in self.titles.items()
                if title.startswith(t) and not title[len(t)].isalnum()]
        return hits[0] if len(hits) == 1 else None

    def inline(self, text: str) -> str:
        codes: list[str] = []

        def keep(m: re.Match) -> str:
            codes.append(self.inline_code(m.group(1)))
            return f'\x00{len(codes) - 1}\x00'

        text = re.sub(r'`([^`]+)`', keep, text)
        links: list[str] = []

        def link(m: re.Match) -> str:
            href = m.group(2)
            if not SAFE_HREF.match(href):
                raise MarkdownError(f'en länk med en adress som sidan inte tar med: {href[:80]}')
            links.append(f'<a href="{attr(href)}">{self.text_part(m.group(1))}</a>')
            return f'\x01{len(links) - 1}\x01'

        if '![' in text:
            raise MarkdownError(f'bilder stöds inte: {text[:80]}')
        text = re.sub(r'\[([^\]]+)\]\(([^()\s]+)\)', link, text)
        if '](' in text:
            raise MarkdownError(f'en länk som inte går att läsa: {text[:80]}')
        out = self.text_part(text)
        out = re.sub(r'\x01(\d+)\x01', lambda m: links[int(m.group(1))], out)
        return re.sub(r'\x00(\d+)\x00', lambda m: codes[int(m.group(1))], out)

    def text_part(self, text: str) -> str:
        if '***' in text:
            raise MarkdownError(f'*** (fet och kursiv på en gång) stöds inte: {text[:80]}')
        s = esc(text)
        s = re.sub(r'"([^"\n]*)"', '”\\1”', s)
        if '"' in s:
            raise MarkdownError(f'ett citattecken utan sin like: {text[:80]}')
        s = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'<strong>\1</strong>', s)

        def em(m: re.Match) -> str:
            inner = m.group(1)
            slug = self.xref(html.unescape(re.sub('<[^>]+>', '', inner)).replace('”', '"'))
            if slug:
                return f'<a class="xref" href="#{slug}"><em>{inner}</em></a>'
            return f'<em>{inner}</em>'

        s = re.sub(r'(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])', em, s)
        if '*' in re.sub(r'<[^>]+>', '', s):
            raise MarkdownError(f'en asterisk som inte blev fet eller kursiv: {text[:80]}')
        return s

    def inline_code(self, code: str) -> str:
        if ' = ' in code:
            try:
                return f'<span class="f-inline" role="math">{formula_line(code, inline=True)}</span>'
            except FormulaError:
                pass
        return f'<code>{esc(code)}</code>'

    # blocks ---------------------------------------------------------------
    def blocks(self, lines: list[str], start: int) -> str:
        out: list[str] = []
        i = 0
        n = len(lines)
        while i < n:
            ln = lines[i]
            lineno = start + i
            if not ln.strip():
                i += 1
                continue
            if ln.startswith('```'):
                info = ln[3:].strip()
                j = i + 1
                while j < n and not lines[j].startswith('```'):
                    j += 1
                out.append(self.code_block(lines[i + 1:j], info, lineno))
                i = j + 1
                continue
            if ln.startswith('|'):
                j = i
                while j < n and lines[j].startswith('|'):
                    j += 1
                out.append(self.table(lines[i:j], lineno))
                i = j
                continue
            if re.match(r'^- ', ln) or re.match(r'^\d+\. ', ln):
                ordered = not ln.startswith('- ')
                mark = r'^\d+\. ' if ordered else r'^- '
                items: list[str] = []
                j = i
                while j < n and lines[j].strip():
                    if re.match(mark, lines[j]):
                        items.append(re.sub(mark, '', lines[j]))
                    elif re.match(r'^\s+(- |\d+\. )', lines[j]):
                        raise MarkdownError(f'rad {start + j}: listor i listor stöds inte')
                    elif lines[j].startswith('  ') and items:
                        items[-1] += ' ' + lines[j].strip()
                    else:
                        raise MarkdownError(f'rad {start + j}: en rad i en lista som inte är en punkt')
                    j += 1
                first = int(re.match(r'^(\d+)\.', ln).group(1)) if ordered else 1
                tag = 'ol' if ordered else 'ul'
                start_attr = f' start="{first}"' if ordered and first != 1 else ''
                out.append(f'<{tag}{start_attr}>' + ''.join(
                    f'<li>{self.inline(it)}</li>' for it in items) + f'</{tag}>')
                i = j
                continue
            if re.match(r'^(#|>|\s{4}|<|\* |\+ |---)', ln):
                raise MarkdownError(f'rad {lineno}: Markdown som generatorn inte känner: {ln[:60]}')
            j = i
            para = []
            while j < n and lines[j].strip() and not re.match(r'^(```|\||- |\d+\. )', lines[j]):
                para.append(lines[j].strip())
                j += 1
            out.append(f'<p>{self.inline(" ".join(para))}</p>')
            i = j
        return '\n'.join(out)

    def code_block(self, lines: list[str], info: str, lineno: int) -> str:
        if info not in ('', 'text'):
            raise MarkdownError(f'rad {lineno}: kodblock med språket {info!r} stöds inte (bara ``` och ```text)')
        if info == '':
            try:
                rows = [formula_row(l) for l in lines if l.strip()]
                return f'<div class="formel" role="math">{"".join(rows)}</div>'
            except FormulaError as e:
                self.warnings.append(
                    f'METOD.md rad {lineno}: formeln går inte att läsa ({e}) och visas som den står. '
                    'Skriv den i formelformen (se tools/metod_html.py) eller märk blocket ```text.')
        return f'<pre class="verbatim"><code>{esc(chr(10).join(lines))}</code></pre>'

    def table(self, lines: list[str], lineno: int) -> str:
        def cells(l: str) -> list[str]:
            if not l.rstrip().endswith('|'):
                raise MarkdownError(f'rad {lineno}: tabellrad utan avslutande |')
            return [c.strip() for c in l.strip()[1:-1].split('|')]

        if len(lines) < 2 or not re.match(r'^\|(\s*:?-+:?\s*\|)+\s*$', lines[1]):
            raise MarkdownError(f'rad {lineno}: tabell utan avgränsningsrad')
        head = cells(lines[0])
        rows = [cells(l) for l in lines[2:]]
        for r in rows:
            if len(r) != len(head):
                raise MarkdownError(f'rad {lineno}: tabellrad med {len(r)} celler, rubriken har {len(head)}')
        prose = any(len(c) > 70 for r in rows for c in r)
        cls = 'stack' if prose else 'nums'
        th = ''.join(f'<th scope="col">{self.inline(h)}</th>' for h in head)
        body = []
        for r in rows:
            tds = ''.join(f'<td data-label="{attr(re.sub(r"[*`]", "", head[k]))}">{self.inline(c)}</td>'
                          for k, c in enumerate(r))
            body.append(f'<tr>{tds}</tr>')
        return (f'<div class="table-wrap {cls}"><table class="{cls}"><thead><tr>{th}</tr></thead>'
                f'<tbody>{"".join(body)}</tbody></table></div>')


# --- formulas ----------------------------------------------------------------

TOKEN = re.compile(r'''
   (?P<ws>\s+)
 | (?P<num>\d+(?:\ \d{3})*(?:,\d+)?(?![\w]))
 | (?P<op>[×−+/^()])
 | (?P<word>[^\W\d_][\w\-]*)
''', re.X)


def tokenize(expr: str) -> list[tuple[str, str]]:
    toks = []
    pos = 0
    while pos < len(expr):
        m = TOKEN.match(expr, pos)
        if not m:
            raise FormulaError(f'okänt tecken {expr[pos]!r}')
        kind = m.lastgroup
        if kind != 'ws':
            toks.append((kind, m.group()))
        pos = m.end()
    return toks


def group(toks: list[tuple[str, str]]) -> list:
    """Nest parentheses: ('group', [...]) items; join consecutive words."""
    stack: list[list] = [[]]
    for kind, val in toks:
        if val == '(':
            stack.append([])
        elif val == ')':
            if len(stack) == 1:
                raise FormulaError('en parentes stängs som aldrig öppnats')
            inner = stack.pop()
            stack[-1].append(('group', inner))
        elif kind == 'word' and stack[-1] and stack[-1][-1][0] == 'word':
            stack[-1][-1] = ('word', stack[-1][-1][1] + ' ' + val)
        else:
            stack[-1].append((kind, val))
    if len(stack) != 1:
        raise FormulaError('en parentes stängs aldrig')
    return stack[0]


def render_name(name: str) -> str:
    if name.count('_') == 1:
        base, sub = name.split('_')
        if not base or not sub:
            raise FormulaError(f'namnet {name!r}')
        return f'<var>{esc(base)}</var><sub>{esc(sub)}</sub>'
    return f'<var>{esc(name.replace("_", " "))}</var>'


def render_items(items: list) -> str:
    out: list[str] = []
    i = 0
    prev_is_operand = False
    while i < len(items):
        kind, val = items[i]
        if kind == 'op' and val == '^':
            if not out or i + 1 >= len(items):
                raise FormulaError('^ utan bas eller exponent')
            nk, nv = items[i + 1]
            exp = render_items(nv) if nk == 'group' else render_items([items[i + 1]])
            out[-1] += f'<sup>{exp}</sup>'
            i += 2
            prev_is_operand = True
            continue
        if kind == 'op' and val == '/' and out and items[i - 1][0] == 'group':
            if i + 1 >= len(items) or items[i + 1][0] == 'op':
                raise FormulaError('/ utan nämnare')
            num = render_items(items[i - 1][1])
            nk, nv = items[i + 1]
            den = render_items(nv) if nk == 'group' else render_items([items[i + 1]])
            if i + 2 < len(items) and items[i + 2] == ('op', '^'):
                raise FormulaError('^ direkt efter ett bråk: skriv nämnaren inom parentes')
            out[-1] = f'<span class="frac"><span class="num">{num}</span><span class="den">{den}</span></span>'
            i += 2
            prev_is_operand = True
            continue
        if kind == 'op':
            if val == '−' and not prev_is_operand:
                out.append('<span class="op op--unary">−</span>')
            elif not prev_is_operand:
                raise FormulaError(f'operatorn {val} saknar vänsterled')
            else:
                out.append(f'<span class="op">{esc(val)}</span>')
            prev_is_operand = False
        elif kind == 'group':
            out.append(f'({render_items(val)})')
            prev_is_operand = True
        elif kind == 'num':
            out.append(f'<span class="n">{esc(val)}</span>')
            prev_is_operand = True
        else:
            out.append(render_name(val))
            prev_is_operand = True
        i += 1
    if items and items[-1][0] == 'op':
        raise FormulaError('uttrycket slutar med en operator')
    return ' '.join(out).replace('<span class="op op--unary">−</span> ', '<span class="op op--unary">−</span>')


def split_top_level_comma(rhs: str) -> tuple[str, str | None]:
    depth = 0
    for k, c in enumerate(rhs):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth == 0 and rhs[k + 1:k + 2] == ' ':
            return rhs[:k], rhs[k + 2:]
    return rhs, None


def split_formula(line: str) -> tuple[str, str, str | None]:
    if ' = ' not in line:
        raise FormulaError('raden har inget " = "')
    lhs, rhs = line.split(' = ', 1)
    note = None
    m = re.search(r'\s{2,}\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$', rhs)
    if m:
        note, rhs = m.group(1), rhs[:m.start()]
    else:
        rhs, note = split_top_level_comma(rhs)
    lhs, rhs = lhs.strip(), rhs.strip()
    if not lhs or not rhs:
        raise FormulaError('tomt led')
    return lhs, rhs, note


def formula_line(line: str, inline: bool = False) -> str:
    lhs, rhs, note = split_formula(line)
    left = render_items(group(tokenize(lhs)))
    right = render_items(group(tokenize(rhs)))
    if inline:
        if note:
            raise FormulaError('en anteckning i en formel i löptext')
        return f'{left} <span class="op">=</span> {right}'
    return left, right, note


def formula_row(line: str) -> str:
    left, right, note = formula_line(line)
    n = f'<span class="f-note">{esc(note)}</span>' if note else ''
    return (f'<div class="f-row"><span class="f-lhs">{left}</span><span class="f-eq">=</span>'
            f'<span class="f-rhs">{right}{n}</span></div>')


# --- the hand-written side file ----------------------------------------------

@dataclass
class Entry:
    key: str            # section title, or "flode", "kedja", "lagen"
    sources: list[str]
    stored: str
    current: str | None = None   # None when a source is missing

    @property
    def stale(self) -> bool:
        return self.current is not None and self.current != self.stored


def combined_hash(doc: Document, sources: list[str]) -> str | None:
    known = doc.by_title()
    if any(s not in known for s in sources):
        return None
    if len(sources) == 1:
        return known[sources[0]].hash
    return text_hash('\n'.join(known[s].hash for s in sources))


def load_sidecar(text: str) -> dict:
    data = tomllib.loads(text)
    for k in data:
        if k not in ('avsnitt', 'flode', 'kedja', 'lagen'):
            raise ValueError(f'okänd nyckel i sidofilen: {k}')
    titles = [a['rubrik'] for a in data.get('avsnitt', [])]
    dup = sorted({x for x in titles if titles.count(x) > 1})
    if dup:
        raise ValueError(f'samma rubrik två gånger i sidofilen: {", ".join(dup)}')
    return data


def entries(doc: Document, side: dict) -> list[Entry]:
    out = []
    for a in side.get('avsnitt', []):
        out.append(Entry(a['rubrik'], [a['rubrik']], a.get('hash', ''),
                         combined_hash(doc, [a['rubrik']])))
    for k in ('flode', 'kedja', 'lagen'):
        if k in side:
            srcs = side[k]['kallor']
            out.append(Entry(k, srcs, side[k].get('hash', ''), combined_hash(doc, srcs)))
    return out


def status(doc: Document, side: dict) -> list[str]:
    msgs = []
    known = doc.by_title()
    have = {a['rubrik'] for a in side.get('avsnitt', [])}
    for e in entries(doc, side):
        if e.current is None:
            missing = [s for s in e.sources if s not in known]
            msgs.append(f'Sammanfattning utan avsnitt: "{e.key}" pekar på {", ".join(missing)}, '
                        'som inte finns i METOD.md. Byt rubriken i sidofilen eller ta bort posten.')
        elif e.stale:
            msgs.append(f'Kan vara inaktuell: "{e.key}". METOD.md har ändrats sedan den skrevs '
                        f'({", ".join(e.sources)}). Läs avsnittet, rätta texten i '
                        f'{SIDECAR_PATH.name} och kör med --reviewed "{e.key}".')
    for s in doc.all_sections():
        if s.title not in have and not lead_only(s):
            msgs.append(f'Utan sammanfattning: "{s.title}" (visas med bara fulltext).')
    return msgs


def restamp(side_text: str, doc: Document, keys: set[str]) -> str:
    """Write the current hash for the given entries, keeping the file as it is."""
    side = load_sidecar(side_text)
    current = {e.key: e.current for e in entries(doc, side)}
    unknown = keys - set(current)
    if unknown:
        raise ValueError(f'finns inte i sidofilen: {", ".join(sorted(unknown))}')
    gone = [k for k in keys if current[k] is None]
    if gone:
        raise ValueError(f'källan finns inte längre i METOD.md: {", ".join(sorted(gone))}')
    lines = side_text.split('\n')
    block_key: str | None = None
    avsnitt_titles = iter(a['rubrik'] for a in side.get('avsnitt', []))
    hash_line: dict[str, int] = {}
    in_string = False
    for i, ln in enumerate(lines):
        quotes = ln.count('"""') + ln.count("'''")
        if in_string:
            in_string = quotes % 2 == 0
            continue
        if quotes % 2:
            in_string = True
        if ln.startswith('[[avsnitt]]'):
            block_key = next(avsnitt_titles)
        elif re.match(r'^\[(flode|kedja|lagen)\]\s*$', ln):
            block_key = ln.strip()[1:-1]
        elif ln.startswith('['):
            block_key = None
        elif block_key and re.match(r'^hash\s*=', ln):
            hash_line[block_key] = i
    for k in keys:
        if k not in hash_line:
            raise ValueError(f'posten "{k}" har ingen rad hash = "..." att skriva i')
        lines[hash_line[k]] = f'hash = "{current[k]}"'
    return '\n'.join(lines)


# --- the page ----------------------------------------------------------------

def lead_only(s: Section) -> bool:
    """A parent section whose own text is one short paragraph: shown as a lead."""
    ps = paragraphs(s.body)
    return bool(s.children) and len(ps) <= 1 and (not ps or (len(ps[0]) < 300 and not re.match(
        r'^(\||- |\d+\. |```)', ps[0])))


def nbsp_numbers(s: str) -> str:
    """Keep "12 345" together, in running text only (not in tags, code or pre)."""
    parts = re.split(r'(<pre\b.*?</pre>|<code>.*?</code>|<[^>]+>)', s, flags=re.S)
    return ''.join(x if i % 2 else re.sub(r'(?<=\d) (?=\d{3}(?!\d))', ' ', x)
                   for i, x in enumerate(parts))


@dataclass
class Page:
    html: str
    warnings: list[str]


def build(md: str, side_text: str, template: str) -> Page:
    doc = parse_document(md)
    side = load_sidecar(side_text)
    r = Renderer(doc)
    open_par, open_names = open_titles(doc)
    open_set = set(open_names)
    ents = {e.key: e for e in entries(doc, side)}
    summaries = {a['rubrik']: a for a in side.get('avsnitt', [])}
    stale_note = ('<span class="stale-note">Avsnittet har ändrats sedan sammanfattningen skrevs. '
                  'Fulltexten gäller.</span>')
    stale_badge = '<span class="badge badge--stale">Sammanfattningen kan vara inaktuell</span>'

    def body_html(s: Section) -> str:
        return r.blocks(s.body, s.line + 1)

    def card(s: Section) -> str:
        sm = summaries.get(s.title)
        is_open = s.title in open_set
        e = ents.get(s.title)
        stale = bool(e and e.stale)
        badges = ''
        if is_open:
            badges += '<span class="badge badge--open">Under avstämning</span>'
        if stale:
            badges += stale_badge
        cls = 'card' + (' card--open-issue' if is_open else '') + (' card--stale' if stale else '')
        if sm:
            summ = f'<span class="card-sum">{r.inline(sm["sammanfattning"].strip())}</span>'
            if stale:
                summ += stale_note
        else:
            summ = '<span class="card-sum card-sum--none">Ingen sammanfattning än, bara hela texten.</span>'
        return (f'<details class="{cls}" id="{s.slug}">\n<summary>\n'
                f'  <span class="card-title"><span class="card-h">{r.inline(s.title)}</span>{badges}</span>\n'
                f'  {summ}\n  <span class="card-toggle" aria-hidden="true"></span>\n</summary>\n'
                f'<div class="card-body">{body_html(s)}</div>\n</details>')

    parts: list[str] = []
    toc: list[str] = ['<ol class="toc-list">', '<li><a href="#flodet">Flödet i en analys</a></li>']
    if open_par:
        toc.append('<li><a href="#oppet">Under avstämning</a></li>')
    if 'lagen' in side:
        toc.append('<li><a href="#tva-lagen">Prognos och uppföljning</a></li>')

    def toc_item(s: Section) -> str:
        dot = '<span class="toc-dot" title="Under avstämning"></span>' if s.title in open_set else ''
        return f'<li><a href="#{s.slug}">{r.inline(s.title)}{dot}</a></li>'

    loose: list[Section] = []

    def flush_loose() -> None:
        if loose:
            parts.append('<div class="cards">' + '\n'.join(card(s) for s in loose) + '</div>')
            loose.clear()

    for s in doc.sections:
        if not s.children:
            loose.append(s)
            toc.append(toc_item(s))
            continue
        flush_loose()
        if lead_only(s):
            if s.title in summaries:
                r.warnings.append(f'Sammanfattningen för "{s.title}" visas inte: avsnittet är en kort '
                                  'ingress till sina underavsnitt. Ta bort posten.')
            lead = f'<div class="group-lead">{body_html(s)}</div>'
            inner = '\n'.join(card(c) for c in s.children)
            gid = s.slug
        else:
            lead = ''
            inner = '\n'.join(card(c) for c in [s] + s.children)
            gid = s.slug + '-grupp'
        parts.append(f'<section class="group" id="{gid}" aria-labelledby="{gid}-h">'
                     f'<h2 id="{gid}-h">{r.inline(s.title)}</h2>{lead}<div class="cards">{inner}</div></section>')
        toc.append(f'<li class="toc-group"><a href="#{gid}">{r.inline(s.title)}</a><ol>')
        if not lead_only(s):
            toc.append(toc_item(s))
        toc.extend(toc_item(c) for c in s.children)
        toc.append('</ol></li>')
    flush_loose()
    toc.append('</ol>')

    # preamble: everything before the first section except the open paragraph
    pre = '\n'.join(doc.preamble)
    if open_par:
        pre = normalize(pre).replace(open_par, '')
    intro = r.blocks(pre.split('\n'), 2)

    def slug_of(title: str) -> str | None:
        sec = doc.by_title().get(title)
        if not sec:
            r.warnings.append(f'Sidofilen pekar på ett avsnitt som inte finns: "{title}"')
            return None
        return sec.slug

    def hand_stale(key: str) -> str:
        e = ents.get(key)
        if e and e.stale:
            return (f'<p class="stale-block">{stale_badge} Avsnitten det bygger på '
                    f'({", ".join(esc(x) for x in e.sources)}) har ändrats sedan det skrevs.</p>')
        return ''

    # the flow
    flow = ''
    if 'flode' in side:
        f = side['flode']
        items = []
        for n, st in enumerate(f['steg'], 1):
            ror = st.get('ror')
            hot = bool(ror and ror in open_set)
            gate = st.get('grind', False)
            cls = 'step' + (' step--hot' if hot else '') + (' step--gate' if gate else '')
            code = f'<p>{r.inline(st["kod"])}</p>' if st.get('kod') else '<p class="none">Inget</p>'
            hot_html = f'<span class="hot-mark">{r.inline(st["markering"])}</span>' if hot and st.get('markering') else ''
            gate_html = '<span class="gate">du godkänner eller rättar</span>' if gate else ''
            items.append(
                f'<li class="{cls}">\n  <div class="step-head"><span class="step-n">{n}</span>'
                f'<span class="step-name">{r.inline(st["namn"])}</span></div>\n'
                f'  <div class="lane lane--model"><span class="lane-label">Språkmodellen</span>'
                f'<p>{r.inline(st["modell"])}</p></div>\n'
                f'  <div class="lane lane--code"><span class="lane-label">Koden</span>{code}</div>\n'
                f'  <div class="step-foot">{gate_html}{hot_html}</div>\n</li>')
        n_gate = sum(1 for st in f['steg'] if st.get('grind'))
        legend_hot = ('<span><i class="la"></i>Rör det som är under avstämning</span>'
                      if any(st.get('ror') in open_set for st in f['steg']) else '')
        flow = (f'<p class="section-lead">{r.inline(f["ingress"].strip())}</p>{hand_stale("flode")}'
                f'<div class="flow-wrap" style="--steps:{len(f["steg"])};--gates:{n_gate}">'
                '<div class="legend" aria-hidden="true">'
                '<span><i class="lm"></i>Språkmodellen</span><span><i class="lc"></i>Koden</span>'
                f'{legend_hot}</div>'
                f'<ol class="flow" aria-label="Stegen i en analys">{"".join(items)}</ol>'
                '<div class="phases" aria-hidden="true">'
                f'<span class="phase phase--gate">{r.inline(f["fas_grind"])}</span>'
                f'<span class="phase phase--run">{r.inline(f["fas_kor"])}</span></div></div>')
    chain = ''
    if 'kedja' in side:
        k = side['kedja']
        lis = []
        for led in k['led']:
            slug = slug_of(led['avsnitt'])
            hot = led['avsnitt'] in open_set
            c = 'chain-item chain-item--hot' if hot else 'chain-item'
            inner = (f'<span class="chain-name">{r.inline(led["namn"])}</span>'
                     f'<span class="chain-what">{r.inline(led["vad"])}</span>')
            lis.append(f'<li><a class="{c}" href="#{slug}">{inner}</a></li>' if slug
                       else f'<li><span class="{c}">{inner}</span></li>')
        chain = (f'<p class="chain-intro">{r.inline(k["ingress"].strip())}</p>{hand_stale("kedja")}'
                 f'<ol class="chain" aria-label="Räknekedjan i koden">{"".join(lis)}</ol>')

    open_box = ''
    if open_par:
        links = ''.join(f'<li><a href="#{doc.by_title()[t].slug}">{r.inline(t)}</a></li>' for t in open_names)
        open_box = (f'<section class="open-box" id="oppet" aria-labelledby="oppet-h">'
                    f'<h2 id="oppet-h">Under avstämning</h2>'
                    f'<p>{r.inline(open_par[len(OPEN_MARK):].strip())}</p>'
                    f'<ul class="open-links">{links}</ul></section>')

    modes = ''
    if 'lagen' in side:
        lg = side['lagen']
        cols = []
        for m in lg['lage']:
            rows = []
            for row in m['rader']:
                label, text = row[0], row[1]
                dot = ('<span class="dot-open" title="Under avstämning"></span>'
                       if label in open_set else '')
                rows.append(f'<dt>{r.inline(label)}{dot}</dt><dd>{r.inline(text)}</dd>')
            cols.append(f'<section class="mode"><h3>{r.inline(m["namn"])} '
                        f'<span class="mode-alt">{r.inline(m["alt"])}</span></h3>'
                        f'<p class="mode-q">{r.inline(m["fraga"])}</p><dl>{"".join(rows)}</dl></section>')
        foot_slug = slug_of(lg['avsnitt'])
        foot_link = f' <a class="xref" href="#{foot_slug}">Hela avsnittet om lägena</a>' if foot_slug else ''
        modes = (f'<section id="tva-lagen" aria-labelledby="tva-lagen-h">'
                 f'<h2 class="section-h" id="tva-lagen-h">{r.inline(lg["rubrik"])}</h2>'
                 f'<p class="section-lead">{r.inline(lg["ingress"].strip())}</p>{hand_stale("lagen")}'
                 f'<div class="modes">{"".join(cols)}</div>'
                 f'<p class="modes-foot">{r.inline(lg["fot"].strip())}{foot_link}</p></section>')

    fill = {'TITLE': esc(doc.title), 'INTRO': intro, 'FLOW': flow, 'CHAIN': chain,
            'OPEN': open_box, 'MODES': modes, 'CARDS': '\n'.join(parts),
            'TOC': '\n'.join(toc), 'MDHASH': text_hash(md)}
    holes = set(re.findall(r'\{\{([A-Z]+)\}\}', template))
    if holes != set(fill):
        raise ValueError(f'mallens platshållare stämmer inte: {sorted(holes ^ set(fill))}')
    page = re.sub(r'\{\{([A-Z]+)\}\}', lambda m: nbsp_numbers(fill[m.group(1)]), template)
    ids = re.findall(r'\sid="([^"]+)"', page)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        raise MarkdownError(f'två delar av sidan får samma ankare: {", ".join(dup)} (byt en rubrik)')
    return Page(page, r.warnings + status(doc, side))


def paths(root: Path) -> tuple[Path, Path, Path, Path]:
    return (root / MD_PATH, root / SIDECAR_PATH, root / OUT_PATH,
            Path(__file__).with_name('metod_html.template.html'))


def generate(root: Path = ROOT) -> Page:
    md, side, _, tpl = paths(root)
    return build(md.read_text(encoding='utf-8'), side.read_text(encoding='utf-8'),
                 tpl.read_text(encoding='utf-8'))


def fresh_keys(root: Path) -> set[str]:
    """Entries whose hash matches METOD.md now (used by the release build)."""
    md, side, _, _ = paths(root)
    doc = parse_document(md.read_text(encoding='utf-8'))
    return {e.key for e in entries(doc, load_sidecar(side.read_text(encoding='utf-8')))
            if e.current is not None and not e.stale}


def reviewed(root: Path, keys: set[str] | None) -> None:
    """Record that the hand-written text has been read against METOD.md now."""
    md, side, _, _ = paths(root)
    doc = parse_document(md.read_text(encoding='utf-8'))
    text = side.read_text(encoding='utf-8')
    if keys is None:
        keys = {e.key for e in entries(doc, load_sidecar(text)) if e.current is not None}
    side.write_text(restamp(text, doc, keys), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--root', type=Path, default=ROOT, help='repots rot (förval: det här repot)')
    ap.add_argument('--check', action='store_true', help='skriv inget, exit 1 om METOD.html är inaktuell')
    ap.add_argument('--reviewed', action='append', metavar='RUBRIK',
                    help='sammanfattningen för RUBRIK är läst mot METOD.md (flode, kedja, lagen för de andra)')
    ap.add_argument('--reviewed-all', action='store_true',
                    help='alla sammanfattningar är lästa mot METOD.md')
    args = ap.parse_args(argv)
    root = args.root.resolve()
    try:
        page = generate(root)
        if args.reviewed or args.reviewed_all:
            reviewed(root, None if args.reviewed_all else set(args.reviewed))
            page = generate(root)
    except (MarkdownError, ValueError) as e:
        print(f'metod_html: {e}', file=sys.stderr)
        return 2
    for w in page.warnings:
        print(w, file=sys.stderr)
    out = paths(root)[2]
    current = out.read_text(encoding='utf-8') if out.exists() else None
    if args.check:
        if current != page.html:
            print(f'{OUT_PATH} är inte det generatorn ger ur {MD_PATH}. '
                  'Kör: cd next && .venv/bin/python tools/metod_html.py', file=sys.stderr)
            return 1
        return 0
    if current != page.html:
        out.write_text(page.html, encoding='utf-8')
        print(f'Skrev {OUT_PATH} ({len(page.html.encode("utf-8")) // 1024} kB)')
    else:
        print(f'{OUT_PATH} är redan aktuell')
    return 0


if __name__ == '__main__':
    sys.exit(main())
