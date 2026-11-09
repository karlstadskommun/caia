"""The prompt rules of 2026-10-13 reach the forecast mode only.

The extraction's three rules (no delta below -1, the approved baseline as the
base, the climate factors as evidens states them) and the report's target year
first under Huvudresultat were tried on the reference packages
(docs/RUNBOOK.md, "Ändra en prompt"), with the extraction at high effort. No
follow-up package was run with them, so the follow-up mode is sent the prompts
it had before, at the effort it had before. These tests fail if a rule leaks
into the follow-up prompt, or drops out of the forecast one.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia import api_client, kommun  # noqa: E402
from caia.agents import kalkyl_extract as KE  # noqa: E402
from caia.agents import rapport as R  # noqa: E402
from caia.mode import POTENTIAL, UPPFOLJNING  # noqa: E402

pytestmark = pytest.mark.karlstad  # reads Karlstad's kommunprofil

FLOOR = 'Ingen delta får bli mindre än -1'
BASE = 'a0 och ef0 är baslinjens A0 och EF0'
FACTORS = 'Konsumtion_faktor får vara större än 1'
MEDEL = ['Medel effekt/år (Territoriell):', 'Medel effekt/år (Konsumtion):',
         'Medel effekt/år (Netto/Total):']


@pytest.fixture(autouse=True)
def karlstad():
    before = kommun._active
    kommun.set_active(kommun.bundled('karlstad'))
    yield
    kommun.set_active(before)


def _sent(monkeypatch, module, run, mode) -> str:
    """The system prompt `run` sends in `mode`."""
    seen = {}

    def complete(step, system, messages, max_output, mode=None, timeout_s=None):
        seen['system'] = system
        return '{"drivers": []}'
    monkeypatch.setattr(module, 'complete', complete)
    run([{'role': 'user', 'content': 'x'}], mode=mode)
    return seen['system']


def test_the_floor_and_base_rules_are_in_the_forecast_prompt_only(monkeypatch):
    forecast = _sent(monkeypatch, KE, KE.run_kalkyl_extract, POTENTIAL)
    follow_up = _sent(monkeypatch, KE, KE.run_kalkyl_extract, UPPFOLJNING)
    for rule in (FLOOR, BASE, FACTORS):
        assert rule in forecast, rule
    for rule in (FLOOR, BASE):
        assert rule not in follow_up, rule


def test_the_follow_up_extraction_keeps_the_factor_rule(monkeypatch):
    """Without it an approved Konsumtion_faktor 1.1 became 1.0 in every
    follow-up extraction, at medium and at high (2026-11-08)."""
    assert FACTORS in _sent(monkeypatch, KE, KE.run_kalkyl_extract, UPPFOLJNING)


def test_the_follow_up_extraction_prompt_is_the_forecast_one_without_two_rules():
    without = KE.SYSTEM_PROMPT
    for block in (KE._FLOOR, KE._BASE):
        assert block in without
        without = without.replace(block, '')
    assert without == KE.SYSTEM_PROMPT_UPPFOLJNING


def _headline_block(prompt: str) -> list[str]:
    start = prompt.index('"Huvudresultat (Scenario Medel):"')
    return prompt[start:prompt.index('"Scenario_medel (mest sannolikt):"', start)].splitlines()


def test_a_forecast_report_leads_with_the_target_year(monkeypatch):
    lines = _headline_block(_sent(monkeypatch, R, R.run_rapport, POTENTIAL))
    assert 'ΔE_2030_total (Netto)' in lines[1]
    assert all(label in lines[i] for i, label in enumerate(MEDEL, start=2))


def test_a_follow_up_report_keeps_the_average_first(monkeypatch):
    lines = _headline_block(_sent(monkeypatch, R, R.run_rapport, UPPFOLJNING))
    assert all(label in lines[i] for i, label in enumerate(MEDEL, start=1))
    assert 'ΔE_2030_total (Netto)' in lines[4]


def test_both_orders_hold_the_same_lines():
    """The saved report's key numbers are read from the Medel lines
    (web.app.extract_key_metric), so the reorder must not reword them."""
    assert sorted(R._HEADLINE_TARGET_YEAR.splitlines()) == sorted(R._HEADLINE_AVERAGE.splitlines())
    # Apart from the order, the follow-up only lacks "Följ upp med"
    # (docs/DECISIONS.md 2026-11-03).
    assert R._without_folj_upp(R.SYSTEM_PROMPT.replace(R._HEADLINE_TARGET_YEAR, R._HEADLINE_AVERAGE)) \
        == R.SYSTEM_PROMPT_UPPFOLJNING


def test_the_extraction_reads_at_high_effort():
    """At medium the same approved history gave 137 and 250 ton (reference
    package återbruk, 4 wrong of 8); at high 137 in 8 of 8 (2026-10-13)."""
    assert api_client.AGENT_MODELS['kalkyl_extract'] == (api_client.SONNET, api_client.EFFORT_HIGH)


@pytest.mark.parametrize('mode', [POTENTIAL, UPPFOLJNING])
def test_the_extraction_tells_the_model_call_its_mode(monkeypatch, mode):
    """complete() can only know the mode if the step passes it on, and a
    step listed in api_client.EFFORT_UPPFOLJNING needs it."""
    seen = {}

    def complete(step, system, messages, max_output, mode=None):
        seen.update(step=step, mode=mode)
        return '{"drivers": []}'
    monkeypatch.setattr(KE, 'complete', complete)
    KE.run_kalkyl_extract([{'role': 'user', 'content': 'x'}], mode=mode)
    assert seen == {'step': 'kalkyl_extract', 'mode': mode}
