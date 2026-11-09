"""A split measure's drivers get one running number across its profiles, so
that evidens keeps them all (reference run 2026-10-13, tjänstebilar)."""
from __future__ import annotations

from pathlib import Path

from caia.agents.emap import number_drivers_through
from caia.agents.evidens_split import drivers_from_history

FIX = Path(__file__).parent / 'fixtures'


def test_a_split_measure_keeps_every_driver_into_evidens():
    raw = (FIX / 'emap.two-profiles.md').read_text(encoding='utf-8')
    # Control: as the model wrote it, evidens finds three of the six.
    assert len(drivers_from_history([{'role': 'assistant', 'content': raw}])) == 3
    found = drivers_from_history([{'role': 'assistant', 'content': number_drivers_through(raw)}])
    assert [d.number for d in found] == [1, 2, 3, 4, 5, 6]
    assert 'privatbilar' in found[3].name


def test_running_numbers_are_left_alone():
    text = (FIX / 'emap.md').read_text(encoding='utf-8')
    assert number_drivers_through(text) == text


def test_only_headings_are_renumbered():
    text = ("Drivare 1: A\n  aktivitet_matt: km/år\n\n---\n"
            "Drivare 1: B\n  aktivitet_matt: kWh/år\n  overlapp_risk: hög, räknas i Drivare 1.\n")
    out = number_drivers_through(text)
    assert 'Drivare 2: B' in out and 'räknas i Drivare 1.' in out
