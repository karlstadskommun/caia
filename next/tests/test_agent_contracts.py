"""Contracts between the agent prompts.

The seven prompts hand structured text to each other. Nothing enforces that
what one agent is told to emit is what the next is told to expect, and the
2026-07-18 review found the two drifted apart: baslinje, kalkyl and cove_qa
all required an "EMAP-drivare" section with named fields, and the EMAP prompt
never asked for one. The baslinje agent then invented the driver breakdown
itself, and QA "verified" a list that no step had produced.

These tests read the field names out of the downstream prompts and check the
upstream one, so a rename on either side fails here instead of in production.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from caia.agents import baslinje_bau, cove_qa, emap, evidens, intake, kalkyl, rapport  # noqa: E402

# Pipeline order as the UI runs it (STEPS in web/app.py). kalkyl_extract is a
# helper inside the kalkyl step, not an agent with its own number.
PIPELINE = [intake, emap, baslinje_bau, evidens, kalkyl, cove_qa, rapport]
ORDINALS = {1: 'första', 2: 'andra', 3: 'tredje', 4: 'fjärde', 5: 'femte',
            6: 'sjätte', 7: 'sjunde'}


def _step(mod) -> int:
    m = re.search(r'<step>(\d+)</step>', mod.SYSTEM_PROMPT)
    assert m, f'{mod.__name__} has no <step> tag'
    return int(m.group(1))


def test_step_numbers_follow_pipeline_order():
    got = [_step(m) for m in PIPELINE]
    assert got == list(range(1, len(PIPELINE) + 1)), got


def test_ordinal_in_description_matches_step_number():
    for n, mod in enumerate(PIPELINE, start=1):
        m = re.search(r'Du är den (\w+) agenten', mod.SYSTEM_PROMPT)
        if not m:
            continue
        word = m.group(1)
        expected = {ORDINALS[n]} | ({'sista'} if n == len(PIPELINE) else set())
        assert word in expected, (mod.__name__, word, n)


def _emap_output_block() -> str:
    m = re.search(r'<output>(.*?)</output>', emap.SYSTEM_PROMPT, re.DOTALL)
    assert m
    return m.group(1)


def _fields_required_downstream() -> dict[str, set[str]]:
    """Field names each downstream prompt says the EMAP output must carry."""
    out: dict[str, set[str]] = {}
    # Anchored on the closing tag, not on the first period: "och ev. overlapp_risk"
    # has a period inside it and a lazy match stopped there.
    patterns = {
        baslinje_bau: r'Minst en EMAP-drivare med (.+?)\.\s*</item>',
        kalkyl: r'EMAP-drivare med (.+?)\.\s*</item>',
        cove_qa: r'EMAP-analys med drivare, (.+?)\.\s*</item>',
    }
    for mod, pat in patterns.items():
        m = re.search(pat, mod.SYSTEM_PROMPT)
        assert m, f'{mod.__name__} no longer states its EMAP field requirement'
        tokens = re.split(r',\s*|\s+och\s+(?:ev\.\s+)?', m.group(1))
        out[mod.__name__] = {t.strip() for t in tokens if t.strip()}
    return out


def test_downstream_agents_still_name_the_emap_fields():
    req = _fields_required_downstream()
    # If this shrinks, the contract test below is testing less than it says.
    union = set().union(*req.values())
    assert {'aktivitet_matt', 'EF_enhet', 'utsläppstyp', 'sektor', 'locus',
            'overlapp_risk'} <= union, union


@pytest.mark.parametrize('consumer', ['baslinje_bau', 'kalkyl', 'cove_qa'])
def test_emap_output_format_defines_every_field_a_consumer_requires(consumer):
    block = _emap_output_block()
    for field in _fields_required_downstream()[f'caia.agents.{consumer}']:
        if field == 'namn':
            label = r'\n\s*Drivare \[nummer\]:'
        else:
            label = r'\n\s*' + re.escape(field) + r':'
        assert re.search(label, block), (consumer, field)


def test_emap_output_carries_the_heading_and_section_baslinje_reads():
    block = _emap_output_block()
    assert 'EMAP-analys av åtgärd:' in block
    assert re.search(r'\n\s*\d\. EMAP-drivare\n', block)
    # Numbers belong to baslinje. The section must say so, or the EMAP step
    # starts setting A0/EF0 and baslinje inherits them as given.
    assert 'Inga siffror' in block
