"""Every driver of the pipeline sends the same hand-off lines (caia.pipeline).

The page, the batch runner and the e2e test each had their own copy, and
three had drifted from the page's: the offline runs and the fixtures they
captured were histories production never produces.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from test_report_row import _inline_script
from caia import kallmarkering as KM
from caia import kommun
from caia.calc.engine import APPENDIX_HEADING
from caia.pipeline import BRIDGE, STEPS, with_kallmarkering

NEXT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEXT / 'tools'))


def test_the_page_sends_the_shared_bridge_lines():
    m = re.search(r'const BRIDGE = (\{.*?\});', _inline_script())
    assert m, 'the page no longer defines BRIDGE on one line'
    assert json.loads(m.group(1)) == BRIDGE


def test_the_gates_use_bridge_keys_that_exist():
    js = _inline_script()
    used = set(re.findall(r'bridge: BRIDGE\.(\w+)', js))
    assert used and used <= set(BRIDGE), used - set(BRIDGE)


def test_the_batch_runner_uses_the_shared_lines_and_order():
    import run_batch
    assert run_batch.BRIDGE is BRIDGE
    assert run_batch.PIPELINE == list(STEPS[1:])


def test_no_other_copy_of_the_bridge_lines_is_left():
    line = BRIDGE['kalkyl']
    holders = [p.relative_to(NEXT) for p in NEXT.rglob('*.py')
               if '.venv' not in p.parts and line in p.read_text(encoding='utf-8')]
    assert holders == [Path('src/caia/pipeline.py')], holders


# ---------- the report ends with Talens ursprung, whoever drove the run ----------
#
# /api/rapport does not put the section in the report: the driver does. The
# page did and run_batch did not, so a report from a batch run had no source
# table at all.

SECTION = '## Talens ursprung\n\n| Tal | Ursprung |\n|---|---|\n| a0 | Antagande |'
JOIN_CASES = [
    ('# Rapport\n\ntext', SECTION),
    ('# Rapport\n\ntext\n\n\n', SECTION),
    ('# Rapport\n\ntext \t \n', SECTION),
    ('  inledande blanktecken står kvar\n', SECTION),
    ('', SECTION),
    # Blanks where JavaScript's \\s and Python's rstrip() disagree.
    ('# Rapport\ufeff', SECTION),
    ('# Rapport\u00a0\u2028\n', SECTION),
    ('# Rapport\x85', SECTION),
    ('# Rapport\x1c\n', SECTION),
    ('# Rapport\n', KM.SAKNAS),
    ('# Rapport\n\n', None),
    ('# Rapport\n\n', ''),
]


def test_the_section_goes_last_after_one_blank_line():
    assert with_kallmarkering('# Rapport\n\ntext\n\n', '## Talens ursprung\n\nx') == \
        '# Rapport\n\ntext\n\n## Talens ursprung\n\nx\n'
    # Without a section the report is returned untouched, trailing blanks and all.
    assert with_kallmarkering('# Rapport\n\n', None) == '# Rapport\n\n'
    assert with_kallmarkering('# Rapport\n\n', '') == '# Rapport\n\n'


@pytest.mark.node
def test_the_page_and_the_batch_runner_join_the_report_the_same_way():
    js = _inline_script()
    start = js.index('function withKallmarkering(')
    fn = js[start:js.index('\n}\n', start) + 2]
    program = fn + '\nconst cases = ' + json.dumps(JOIN_CASES) + ';\n' \
        'console.log(JSON.stringify(cases.map(c => withKallmarkering(c[0], c[1]))));'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    page = json.loads(out.stdout)
    assert page == [with_kallmarkering(md, section) for md, section in JOIN_CASES]
    # The cases are not all the same answer: some end with the section, two do not.
    assert sum(1 for text in page if text.endswith('Antagande |\n')) == 9
    assert page[5] == '# Rapport\n\n' + SECTION + '\n'      # U+FEFF is a blank to both
    assert page[7] == '# Rapport\x85\n\n' + SECTION + '\n'  # U+0085 is a blank to neither


CALC_DRIVER = {
    'name': 'Tjänstebilar', 'baseline_year': 2023,
    'a0': 3_000_000.0, 'a0_unit': 'km/år', 'ef0': 0.15, 'ef0_unit': 'kg CO2e/km',
    'g_a': 0.0, 'g_ef': 0.0, 'delta_a': {'min': -0.05, 'med': -0.1, 'max': -0.2}, 'delta_ef': 0.0,
    'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
    'ramp': {'start_year': 2026, 'full_effect_year': 2028},
    'kallor': {'a0': {'ursprung': 'antagande', 'not': '200 bilar × 15 000 km'},
               'ef0': {'ursprung': 'parameterbibliotek', 'parametrar': ['EF_passenger_car_avg']}},
}


@pytest.fixture
def batch(monkeypatch, tmp_path):
    """run_batch's own driver against the real app, with the model steps
    answered by stand-ins. The kalkyl step runs the real engine and the real
    source check, and the rapport step the real appendix code, so the section
    and the report it is appended to are the ones production produces."""
    import run_batch
    from caia.web import app as A
    before = kommun.active()
    kommun.set_active(kommun.bundled('karlstad'))
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    monkeypatch.setattr(A, 'run_intake', lambda h, **_: {
        'status': 'complete', 'message': 'ÅTGÄRDSPROFIL\n*Namn:* Bilpool', 'profiles': []})
    monkeypatch.setattr(A, 'run_emap', lambda h, **_: 'EMAP')
    monkeypatch.setattr(A, 'run_baslinje_bau', lambda h, **_: 'BASLINJE')
    monkeypatch.setattr(A, 'run_evidens', lambda h, **_: 'EVIDENS')
    monkeypatch.setattr(A, 'run_kalkyl', lambda h, **_: 'Kalkyl räknad av språkmodellen: 12 ton.')
    monkeypatch.setattr(A, 'run_cove_qa', lambda h, **_: 'QA ok')
    monkeypatch.setattr(A, 'run_rapport', lambda h, **_: '# Åtgärdskort\n\nRapportens löptext.\n')
    pkg = tmp_path / 'bilpool.md'
    pkg.write_text('Kommunen inför en bilpool.', encoding='utf-8')

    def run(extracted):
        monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
        out = tmp_path / 'out'
        assert run_batch.run_package(A.app.test_client(), pkg, out, io.StringIO(),
                                     evidens_mode='single')
        return out
    yield run
    kommun.set_active(before)


@pytest.mark.karlstad
def test_a_batch_report_ends_with_the_section_from_the_kalkyl_step(batch):
    out = batch({'action_name': 'Bilpool', 'target_year': 2030, 'drivers': [CALC_DRIVER]})
    meta = json.loads((out / 'kalkyl_meta.json').read_text(encoding='utf-8'))
    section = meta['kallmarkering_md']
    assert meta['deterministic'] is True
    assert section.startswith(KM.RUBRIK) and 'Tjänstebilar' in section
    report = (out / 'rapport.md').read_text(encoding='utf-8')
    assert report.endswith('\n\n' + section + '\n')
    assert report.count(KM.RUBRIK) == 1
    # Last means after the technical appendix, which /api/rapport already added.
    assert 0 < report.index('Rapportens löptext') < report.index(APPENDIX_HEADING) \
        < report.index(KM.RUBRIK)
    # The other files are what the steps returned: the section is the report's.
    for step in STEPS[:-1]:
        assert KM.RUBRIK not in (out / f'{step}.md').read_text(encoding='utf-8'), step
    history = json.loads((out / 'history.json').read_text(encoding='utf-8'))
    assert history[-1]['role'] == 'assistant' and 'Rapportens löptext' in history[-1]['content']
    assert KM.RUBRIK not in history[-1]['content']


@pytest.mark.karlstad
def test_a_batch_report_the_model_calculated_says_the_sources_are_missing(batch):
    out = batch(None)  # the extraction gave nothing: the language model did the math
    meta = json.loads((out / 'kalkyl_meta.json').read_text(encoding='utf-8'))
    assert meta['deterministic'] is False
    report = (out / 'rapport.md').read_text(encoding='utf-8')
    assert report.endswith('\n\n' + KM.SAKNAS + '\n')
    assert report.index(APPENDIX_HEADING) < report.index(KM.SAKNAS)

