"""What "Det viktigaste" says when the number is not the usual one: a result
that is an increase, and a baseline value that already carries its percent
sign. Run in node, like test_key_points.
"""
from __future__ import annotations

import json

import pytest
from test_key_points import _run, _texts

pytestmark = pytest.mark.node

HEADLINE = {'net': 61.4, 'cons': 61.4, 'terr': 1.2, 'year': 2030}
SPAN = {'net_lo': 7.8, 'net_hi': 487.9, 'avg_net': 46.7, 'cum_net': 234,
        'window': [2026, 2030], 'target_year': 2030}


def _kalkyl(headline, span) -> list[str]:
    return _texts(_run(f'kalkylKeyPoints({json.dumps(headline)}, {json.dumps(span)}, [])'))


def test_a_reduction_reads_as_before():
    assert _kalkyl(HEADLINE, SPAN) == [
        'Troligt resultat: utsläppen minskar med 61 ton CO₂e år 2030.',
        'Med försiktiga och optimistiska antaganden: 7,8 till 488 ton samma år.',
        'I snitt per år 2026–2030: 47 ton CO₂e.',
        'Sammanlagt till 2030: 234 ton CO₂e.',
    ]


def test_a_negative_result_is_called_an_increase():
    """The tjänstebilar package gave -49,5 ton on 2026-10-13, and the box said
    "utsläppen minskar med -50 ton"."""
    points = _kalkyl({'net': -49.6, 'year': 2030},
                     {'net_lo': -208.8, 'net_hi': 36.6, 'avg_net': -30.2, 'cum_net': -151,
                      'window': [2026, 2030], 'target_year': 2030})
    assert points == [
        'Troligt resultat: utsläppen ökar med 50 ton CO₂e år 2030.',
        'Med försiktiga och optimistiska antaganden: från en ökning på 209 ton till en minskning på 37 ton samma år.',
        'I snitt per år 2026–2030: en ökning på 30 ton CO₂e.',
        'Sammanlagt till 2030: en ökning på 151 ton CO₂e.',
    ]
    assert not any('-' in p or '−' in p for p in points)


def test_a_reduction_with_a_cautious_scenario_that_increases():
    points = _kalkyl({'net': 11.4, 'year': 2030},
                     {'net_lo': -57.5, 'net_hi': 72.4, 'avg_net': 4.6, 'cum_net': 23,
                      'window': [2026, 2030], 'target_year': 2030})
    assert points[0] == 'Troligt resultat: utsläppen minskar med 11 ton CO₂e år 2030.'
    assert points[1] == ('Med försiktiga och optimistiska antaganden: från en ökning på 58 ton '
                         'till en minskning på 72 ton samma år.')
    assert points[2:] == ['I snitt per år 2026–2030: 4,6 ton CO₂e.', 'Sammanlagt till 2030: 23 ton CO₂e.']


BASLINJE = """Drivare 1: Substitutionsgrad mellan cirkulära köp och köp av nya varor
  A0: ca 40 % (spann 20–60 %), vilket motsvarar faktorn 0,4
  A0_enhet: % av cirkulära köp som ersätter köp av nya varor
  EF0: 1,0 (neutral skalfaktor, drivaren har ingen egen emissionsfaktor)
  EF0_enhet: dimensionslös justeringsfaktor
Drivare 2: Reparationer
  A0: ca 18 000 (ca 12 reparationsföretag)
  A0_enhet: antal reparationer/år
  EF0: ca 15 (intervall 5–30)
  EF0_enhet: kg CO2e/reparation
"""


def test_a_percent_value_with_a_percent_unit_has_one_percent_sign():
    """A workshop run on 2026-10-13 read "ca 40 % % av cirkulära köp"."""
    points = _texts(_run(f'baselineKeyPoints({json.dumps(BASLINJE)}, "")'))
    assert points[0].startswith('Substitutionsgrad mellan cirkulära köp och köp av nya varor: '
                                'i dag ca 40 % av cirkulära köp'), points[0]
    assert '% %' not in points[0]
    # A value without a percent sign keeps its unit as written.
    assert 'i dag ca 18 000 antal reparationer/år med ca 15 kg CO2e/reparation.' in points[1], points[1]


PROCENTENHETER = """Drivare 1: Andel som byter
  A0: 40 %
  A0_enhet: %/år
  EF0: ca 4 % (spann 2–6 %)
  EF0_enhet: %-enheter per år
"""


def test_a_unit_that_starts_with_the_percent_sign_keeps_it():
    """Stripping the unit's sign left "40 % /år" and "ca 4 % -enheter per år"."""
    points = _texts(_run(f'baselineKeyPoints({json.dumps(PROCENTENHETER)}, "")'))
    assert points[0].startswith('Andel som byter: i dag 40 %/år med ca 4 %-enheter per år.'), points[0]
