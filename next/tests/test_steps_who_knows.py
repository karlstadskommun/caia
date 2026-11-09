"""Step 1 holds what the user knows (scale, maturity), step 2 what CAIA
concludes about the emissions: the drivers, a mechanism per driver, and the
kind of effect that decides how it is counted (2026-10-13). An enabling
measure is counted as a chain, not left without effect.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_key_points import _run, _texts

from caia.agents import cove_qa, emap, evidens, intake, kalkyl, baslinje_bau
from caia.profiles import parse_profiles

FIX = Path(__file__).parent / 'fixtures'


def test_the_profile_asks_for_scale_and_maturity():
    p = intake.SYSTEM_PROMPT
    assert '*Omfattning:*' in p and '*Mognad:*' in p
    assert p.index('*Beskrivning:*') < p.index('*Omfattning:*') < p.index('*Sektor:*')
    # Scale is asked for before the other fields.
    assert 'frågar efter omfattningen i tal om den saknas' in p


def test_a_profile_with_scale_keeps_it_in_order():
    text = """ÅTGÄRDSPROFIL
*Namn:* Laddpunkter
*Beskrivning:* Publika laddpunkter.
*Sektor:* transporter
*Omfattning:* 120 laddpunkter, cirka 4 000 hushåll
*Mognad:* uppskalning
*Typ av åtgärd:* infrastruktur
"""
    labels = [f['label'] for f in parse_profiles(text)['profiles'][0]['fields']]
    assert labels.index('Omfattning') == labels.index('Beskrivning') + 1
    assert labels.index('Mognad') == labels.index('Typ av åtgärd') + 1


def test_step_2_no_longer_reclassifies_what_the_profile_says():
    p = emap.SYSTEM_PROMPT
    for gone in ('EMAP_Åtgärdstyp', 'EMAP_Nivå', 'EMAP_Tidsprofil', 'EMAP_Mognad', '2.2 EMAP_Mekanism'):
        assert gone not in p, gone
    assert '2.1 EMAP_Effektkategori' in p
    assert 'mekanism: [Avoid / Shift / Improve], [ΔA eller ΔEF]' in p


def test_an_enabling_measure_is_counted_as_a_chain_everywhere():
    assert 'Möjliggörande åtgärder har nästan alltid en egen effekt' in emap.SYSTEM_PROMPT
    for prompt in (baslinje_bau.SYSTEM_PROMPT, evidens.SYSTEM_PROMPT, kalkyl.SYSTEM_PROMPT):
        assert 'i stället för att sätta effekten till 0' in prompt
        # The old rule that let an enabler go unquantified is gone.
        assert 'att effekten är\n    indirekt/enabler' not in prompt
    assert 'En indirekt eller möjliggörande åtgärd ska ha antaganden för kedjan' in evidens.SYSTEM_PROMPT
    assert '"Mekanism_och_kedja:"' in cove_qa.SYSTEM_PROMPT


def test_the_page_reads_a_mechanism_per_driver():
    md = (FIX / 'emap.v2.md').read_text(encoding='utf-8')
    view = _run(f'parseEmap({json.dumps(md)})')
    d1 = view['profiles'][0]['drivers'][0]
    assert d1['fields']['mekanism'].startswith('Shift, ändrad aktivitet')
    assert [c['label'] for c in view['profiles'][0]['classes']] == ['Typ av effekt']


def test_the_summary_says_how_the_effect_is_counted():
    md = (FIX / 'emap.v2.md').read_text(encoding='utf-8')
    points = _texts(_run(f'emapKeyPoints(parseEmap({json.dumps(md)}))'))
    assert 'Sätt att minska utsläppen: Byta (Shift).' in points
    assert any(p.startswith('Effekten räknas som en kedja') for p in points), points


def test_an_old_report_still_shows_its_one_mechanism():
    md = (FIX / 'emap.dev.md').read_text(encoding='utf-8')
    points = _texts(_run(f'emapKeyPoints(parseEmap({json.dumps(md)}))'))
    assert any(p.startswith('Sätt att minska utsläppen:') for p in points)


@pytest.mark.parametrize('raw, name, what', [
    ('Shift, ΔA: färre km', 'Byta (Shift)', 'mängden'),
    ('Improve, ΔEF: renare el', 'Förbättra (Improve)', 'utsläppen per enhet'),
    ('Avoid: mindre inköp', 'Undvika (Avoid)', ''),
    ('beteendeförändring', '', ''),
])
def test_a_mechanism_is_put_in_words(raw, name, what):
    m = _run(f'emapMechanism({json.dumps(raw)})')
    assert (m['name'], m['what']) == (name, what)


# ---------- running driver numbers across profiles ----------

def test_step_2_asks_for_running_numbers():
    assert 'Numrera drivarna löpande genom hela svaret' in emap.SYSTEM_PROMPT
