"""S21: the numbers the calculation runs on are compared with what the user
approved in steps 3 and 4 (caia.godkant), and a number that departs from it
is marked "behöver kontrolleras" under Talens ursprung.

Before the comparison, the extraction could read -0.84 where the user had
approved -0.38, or a baseline ten times the approved one, and the report
showed the result as calculated by the program without a word (the
reviewer's probe, docs/security-review-2026-10.md, S21). Every test here
that expects a mark fails with the comparison removed.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia import godkant as G  # noqa: E402
from caia import kallmarkering as KM  # noqa: E402
from caia import kommun  # noqa: E402
from caia.calc import CalcModel  # noqa: E402
from caia.pipeline import BRIDGE  # noqa: E402
from caia.web import app as A  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture(autouse=True)
def karlstad():
    before = kommun._active
    kommun.set_active(kommun.bundled('karlstad'))
    yield
    kommun.set_active(before)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'run_kalkyl', lambda h, data_context=None, **_: 'LLM-FALLBACK')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


# ---------- the reviewer's three cases ----------

# The reviewer's approved evidens turn, as written in the probe.
EVIDENS = ('Evidens & antaganden för åtgärd: Elbilar\n\nDrivare 1: Tjänstebilar\n'
           '  Mekanism: byte till elbil\n'
           '  Parameter: ΔEF\n    Antagande_min: -0.15\n    Antagande_med: -0.38\n'
           '    Antagande_max: -0.85\n')
# Every real analysis approves a baseline before the evidens step; the probe
# left it out. This is the one its driver would have had.
BASLINJE = ('Baslinje & BAU\n\nDrivare 1: Tjänstebilar\n  A0: 3 000 000\n  A0_enhet: km/år\n'
            '  EF0: 0,15\n  EF0_enhet: kg CO2e/km\n')


def _history(*, baslinje=True):
    h = [{'role': 'user', 'content': 'Elbilar'}]
    if baslinje:
        h += [{'role': 'assistant', 'content': BASLINJE},
              {'role': 'user', 'content': BRIDGE['baslinje']}]
    return h + [{'role': 'assistant', 'content': EVIDENS},
                {'role': 'user', 'content': BRIDGE['evidens']}]


def _driver(delta_med=-0.38, **over):
    d = {'name': 'Tjänstebilar', 'baseline_year': 2023, 'a0': 3_000_000.0, 'a0_unit': 'km/år',
         'ef0': 0.15, 'ef0_unit': 'kg CO2e/km', 'g_a': 0.0, 'g_ef': 0.0, 'delta_a': 0.0,
         'delta_ef': {'min': -0.15, 'med': delta_med, 'max': -0.85},
         'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
         'ramp': {'start_year': 2026, 'full_effect_year': 2030},
         'kallor': {k: {'ursprung': 'antagande', 'not': 'enligt evidenssteget'}
                    for k in ('a0', 'ef0', 'g_a', 'g_ef', 'delta_a', 'delta_ef')}}
    d.update(over)
    return d


def _kalkyl(client, monkeypatch, driver, history):
    extracted = {'action_name': 'Elbilar', 'target_year': 2030, 'drivers': [driver]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    body = client.post('/api/kalkyl', json={'history': history}).get_json()
    assert body['deterministic'] is True
    rows = {r['falt']: r for r in body['kallmarkering']}
    return body, rows


def test_the_approved_number_is_not_marked(client, monkeypatch):
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.38), _history())
    assert all(not r['godkant'] for r in rows.values())
    assert not any('avviker' in w for w in body['warnings'])
    assert KM.JAMFORT['ja'] in body['kallmarkering_md']
    assert 'behöver kontrolleras' not in body['kallmarkering_md']


def test_a_different_number_is_marked(client, monkeypatch):
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.84), _history())
    assert rows['delta_ef']['godkant'] and not rows['delta_ef']['ok']
    assert '−0,38' in rows['delta_ef']['godkant']
    assert [k for k, r in rows.items() if r['godkant']] == ['delta_ef']
    assert 'Ett tal i beräkningen avviker' in ' '.join(body['warnings'])
    md = body['kallmarkering_md']
    assert '1 behöver kontrolleras' in md and '### Kontrollera först' in md


def test_ten_times_the_baseline_is_marked(client, monkeypatch):
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.38, a0=30_000_000.0), _history())
    assert rows['a0']['godkant'] and '3 000 000' in rows['a0']['godkant']
    assert [k for k, r in rows.items() if r['godkant']] == ['a0']
    assert 'behöver kontrolleras' in body['kallmarkering_md']


def test_the_probe_as_written_marks_the_effect_but_has_no_baseline_to_compare(client, monkeypatch):
    """The probe approved no baseline step, so there is no A0 the user
    approved: a0 has nothing to be compared with. The effect still is."""
    _, rows = _kalkyl(client, monkeypatch, _driver(-0.84), _history(baslinje=False))
    assert rows['delta_ef']['godkant']
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.38, a0=30_000_000.0),
                         _history(baslinje=False))
    assert not rows['a0']['godkant']
    # ... and the section does not claim the baseline was compared.
    assert KM.JAMFORT['utan_baslinje'] in body['kallmarkering_md']
    assert KM.JAMFORT['ja'] not in body['kallmarkering_md']


def test_two_marks_are_counted_in_the_warning(client, monkeypatch):
    body, _ = _kalkyl(client, monkeypatch, _driver(-0.84, a0=30_000_000.0), _history())
    assert '2 tal i beräkningen avviker' in ' '.join(body['warnings'])


# ---------- a real analysis ----------

def _fixture_history():
    """The four approved steps of the fixture analysis, as the client sends them."""
    h = [{'role': 'user', 'content': 'Krav på laddbara tjänstebilar och laddinfrastruktur '
                                     'vid kommunala arbetsplatser.'}]
    for step in ('intake', 'emap', 'baslinje', 'evidens'):
        h += [{'role': 'assistant', 'content': (FIXTURES / f'{step}.md').read_text(encoding='utf-8')},
              {'role': 'user', 'content': BRIDGE[step]}]
    return h


def _fixture_extract():
    """What the extraction model read from that history (a live run): it
    derives delta_ef as adoption × ΔEF/EF0, 0,25 × 0,08/0,13 = 0,154."""
    return json.loads((FIXTURES / 'kalkyl_extract.json').read_text(encoding='utf-8'))


def test_a_real_extraction_is_not_marked():
    model = CalcModel.from_dict(_fixture_extract())
    assert G.granska(model, _fixture_history()) == []


@pytest.mark.parametrize('field,change', [
    ('delta_ef', lambda d: d['delta_ef'].update(med=-0.84)),
    ('a0', lambda d: d.update(a0=d['a0'] * 10)),
    ('ef0', lambda d: d.update(ef0=d['ef0'] * 10)),
    # A trend is only asked to appear somewhere in the driver's approved
    # blocks or the profile, so -0,20 passes here ("1 bil per 20 anställda").
    ('g_a', lambda d: d['g_a'].update(med=-0.33)),
])
def test_a_changed_number_in_a_real_extraction_is_marked(field, change):
    d = _fixture_extract()
    change(d['drivers'][0])
    found = G.granska(CalcModel.from_dict(d), _fixture_history())
    assert [(a.nr, a.falt) for a in found] == [(0, field)]


def test_only_the_medel_trend_is_compared():
    """The engine runs BAU on the medel trend in every scenario, so min and
    max of a trend change no number. An extraction that weighed two trends
    together for them was marked and the page warned (2026-10-13)."""
    d = _fixture_extract()
    d['drivers'][0]['g_ef'].update(min=-0.0225, max=-0.0075)
    assert G.granska(CalcModel.from_dict(d), _fixture_history()) == []
    d['drivers'][0]['g_ef'].update(med=-0.33)
    found = G.granska(CalcModel.from_dict(d), _fixture_history())
    assert [(a.falt, a.scenario) for a in found] == [('g_ef', 'med')]


# ---------- a scenario that needs more than the whole baseline ----------

# The baseline is the replaced amount itself (30 handlare × 0,72 ton = 21,6),
# and max replaces 50 × 1,2 = 60 ton: 2,8 times the baseline.
FLOOR_BASLINJE = ('Baslinje\n\nDrivare 1: Nyvara som ersätts\n  A0: 21,6\n'
                  '  A0_enhet: ton ersatt nyvara/år\n  EF0: 10\n  EF0_enhet: kg CO2e/kg nyvara\n')
FLOOR_EVIDENS = ('Antaganden\n\nDrivare 1: Nyvara som ersätts\n  Mekanism: Shift\n'
                 '  Parameter: adoption (antal handlare)\n    Antagande_min: 15\n'
                 '    Antagande_med: 30\n    Antagande_max: 50\n    Enhet: handlare\n'
                 '  Parameter: ersatt nyvara per handlare\n    Antagande_min: 0,4\n'
                 '    Antagande_med: 0,72\n    Antagande_max: 1,2\n    Enhet: ton/handlare/år\n'
                 '  Parameter: emissionsfaktor för ersatt nyvara\n    Antagande_min: 8\n'
                 '    Antagande_med: 10\n    Antagande_max: 14\n    Enhet: kg CO2e/kg\n')


def _floor(evidens=FLOOR_EVIDENS, mode='potential', baslinje=FLOOR_BASLINJE, **over):
    """The model the extraction prompt prescribes for that case: a0 and ef0
    at the scenarios' largest values, every scenario a share of them."""
    h = [{'role': 'user', 'content': 'Cirkulära affärsmodeller'},
         {'role': 'assistant', 'content': baslinje}, {'role': 'user', 'content': BRIDGE['baslinje']},
         {'role': 'assistant', 'content': evidens}, {'role': 'user', 'content': BRIDGE['evidens']}]
    d = _driver(name='Nyvara som ersätts', a0=60.0, a0_unit='ton ersatt nyvara/år', ef0=14_000.0,
                ef0_unit='kg CO2e/ton', delta_a={'min': -0.05714, 'med': -0.25714, 'max': -1.0},
                delta_ef=0.0)
    d.update(over)
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [d]}, mode=mode)
    return [(a.falt, a.scenario) for a in G.granska(model, h)]


def test_the_largest_amount_is_the_base_when_a_scenario_takes_everything():
    assert _floor() == []
    assert _floor(a0=60_000.0, a0_unit='kg ersatt nyvara/år', ef0=14.0, ef0_unit='kg CO2e/kg') == []


def test_a_share_written_in_percent_gives_the_same_base():
    """120 ton × 50 % is the same 60 ton as 50 handlare × 1,2 ton."""
    evidens = ('Antaganden\n\nDrivare 1: Nyvara som ersätts\n  Mekanism: Shift\n'
               '  Parameter: andel som genomför\n    Antagande_min: 20 %\n'
               '    Antagande_med: 30 %\n    Antagande_max: 50 %\n    Enhet: andel av handlarna\n'
               '  Parameter: mängd nyvara som kan ersättas\n    Antagande_min: 40\n'
               '    Antagande_med: 72\n    Antagande_max: 120\n    Enhet: ton/år\n')
    assert _floor(evidens=evidens) == []
    # 40 ton × 20 %, the smallest amount, and a number no two lines give.
    assert _floor(evidens=evidens, a0=8.0) == [('a0', '')]
    assert _floor(evidens=evidens, a0=45.0) == [('a0', '')]


@pytest.mark.parametrize('over', [
    # No scenario at -100 %: nothing prescribes another base than the baseline's.
    {'delta_a': {'min': -0.05, 'med': -0.25, 'max': -0.9}},
    # At -100 %, but the base is not what the approved max lines give.
    {'a0': 216.0},
    {'a0': 600.0},
    # The smallest scenario amount (15 × 0,4) is no base: the rule only ever
    # gives the largest, and never one below the baseline's own 21,6.
    {'a0': 6.0},
    # A count times an emission factor (15 × 8, 50 × 14) is not an amount.
    {'a0': 120.0},
    {'a0': 700.0},
    # The emission factor going to zero (fossil-free) moves no base: only an
    # amount taken away whole does.
    {'delta_a': {'min': -0.05, 'med': -0.25, 'max': -0.9}, 'delta_ef': {'min': -0.2, 'med': -0.5, 'max': -1.0}},
    # The follow-up extraction has no rule that moves the base.
    {'mode': 'uppfoljning'},
])
def test_another_base_is_still_marked(over):
    assert ('a0', '') in _floor(**over)


def test_a_base_below_the_baseline_is_marked():
    """The rule moves the base up, to an amount the baseline does not hold.
    With 200 ton in the baseline no scenario needs more than all of it."""
    assert _floor(baslinje=FLOOR_BASLINJE.replace('A0: 21,6', 'A0: 200')) == [('a0', '')]


def test_the_smaller_outer_amount_is_no_base():
    """15 handlare × 0,4 ton = 6 ton is above a baseline of 2 ton, and still
    not the base: the rule gives the largest amount, 60."""
    baslinje = FLOOR_BASLINJE.replace('A0: 21,6', 'A0: 2')
    assert _floor(baslinje=baslinje) == []
    assert _floor(baslinje=baslinje, a0=6.0) == [('a0', '')]


def test_a_year_times_a_share_is_no_base():
    """Startår 2028 × attribution 0,8 = 1 622: a number, not an amount."""
    evidens = FLOOR_EVIDENS + ('  Parameter: startår\n    Antagande_min: 2027\n    Antagande_med: 2028\n'
                               '    Antagande_max: 2028\n    Enhet: år\n'
                               '  Parameter: tillskriven andel\n    Antagande_min: 0,5\n'
                               '    Antagande_med: 0,7\n    Antagande_max: 0,8\n    Enhet: andel\n')
    assert _floor(evidens=evidens) == []
    assert _floor(evidens=evidens, a0=1622.4) == [('a0', '')]


def test_similar_driver_names_are_not_confused():
    """"Personbilar el" and "Personbilar diesel" share every word the
    overlap counts. The exact name wins; a tie compares with all drivers
    rather than with the first one."""
    bas = ('Drivare 1: Personbilar diesel\n  A0: 1 000\n  EF0: 0,2\n'
           'Drivare 2: Personbilar el\n  A0: 50 000\n  EF0: 0,02\n')
    blocks_ = G.blocks(bas)
    assert G.match_driver('Personbilar el', blocks_) == 2
    assert G.match_driver('personbilar, el', blocks_) == 2
    assert G.match_driver('Personbilarna', blocks_) is None
    h = [{'role': 'assistant', 'content': bas}, {'role': 'user', 'content': BRIDGE['baslinje']},
         {'role': 'assistant', 'content': EVIDENS.replace('Drivare 1: Tjänstebilar', 'Drivare 2: Personbilar el')},
         {'role': 'user', 'content': BRIDGE['evidens']}]
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [
        _driver(name='Personbilar el', a0=50_000.0, ef0=0.02)]})
    assert G.granska(model, h) == []


def test_a_turn_the_user_gave_feedback_on_is_not_the_approved_one():
    """The user asked for a change; the approved turn is the one after it."""
    first = EVIDENS.replace('-0.38', '-0.84')
    h = [{'role': 'user', 'content': 'Elbilar'},
         {'role': 'assistant', 'content': BASLINJE}, {'role': 'user', 'content': BRIDGE['baslinje']},
         {'role': 'assistant', 'content': first}, {'role': 'user', 'content': 'Medel ska vara -0,38.'},
         {'role': 'assistant', 'content': EVIDENS}, {'role': 'user', 'content': BRIDGE['evidens']}]
    assert G.approved(h)['evidens'] == EVIDENS
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                 'drivers': [_driver(-0.84)]})
    assert [a.falt for a in G.granska(model, h)] == ['delta_ef']


# ---------- what the section says when it cannot compare ----------

def test_no_approved_evidens_says_so_and_marks_nothing(client, monkeypatch):
    h = [{'role': 'user', 'content': 'Elbilar'}, {'role': 'assistant', 'content': EVIDENS}]
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.84), h)
    assert not any(r['godkant'] for r in rows.values())
    assert KM.JAMFORT['inget'] in body['kallmarkering_md']


def test_a_fault_in_the_comparison_keeps_the_section(client, monkeypatch):
    def boom(model, history):
        raise RuntimeError('broken')
    monkeypatch.setattr(G, 'granska', boom)
    body, rows = _kalkyl(client, monkeypatch, _driver(-0.84), _history())
    assert body['kallmarkering'] is not None
    assert KM.JAMFORT['fel'] in body['kallmarkering_md']


def test_without_a_conversation_the_section_is_unchanged():
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [_driver()]})
    _, md = KM.kallmarkering(model)
    assert not any(t in md for t in KM.JAMFORT.values())


# ---------- reading numbers ----------

@pytest.mark.parametrize('text,value,neg,pct', [
    ('1 300 000', 1_300_000, False, False),
    ('2,16e6', 2_160_000, False, False),
    ('−0,92', 0.92, True, False),
    ('15 %', 15, False, True),
    ('1,3 miljoner', 1_300_000, False, False),
    ('3,0 × 10^6', 3_000_000, False, False),
    ('6,7·10⁻⁶', 6.7e-6, False, False),
])
def test_numbers_as_the_agents_write_them(text, value, neg, pct):
    [n] = G.numbers(text)
    assert n.value == pytest.approx(value) and n.neg is neg and n.pct is pct


def test_a_product_is_two_numbers():
    """"× 10" is an exponent only with a caret or a superscript."""
    assert [n.value for n in G.numbers('2 × 100 bilar')] == [2, 100]
    assert [n.value for n in G.numbers('2 x 1000 km')] == [2, 1000]


def test_the_message_shows_digits_not_approved_text():
    """The problem text goes into the program's own section, so it carries
    a number and never a string from the conversation (S20)."""
    assert G.Num(220_000, 2).text == '220 000'
    assert G.Num(0.38, 2, neg=True).text == '−0,38'


# ---------- cost ----------

def test_a_large_analysis_is_compared_quickly():
    """Twelve drivers (the most the evidens step takes) with forty parameters
    each, the recipe search capped per driver (S19)."""
    lines = ''.join(f'  Parameter: p{i}\n    Antagande_min: 0,{i + 10}\n'
                    f'    Antagande_med: 0,{i + 30}\n    Antagande_max: 0,{i + 50}\n'
                    for i in range(40))
    ev = ''.join(f'Drivare {n}: Kategori {n:04d}\n{lines}' for n in range(1, 13))
    bas = ''.join(f'Drivare {n}: Kategori {n:04d}\n  A0: 1000\n  EF0: 0,1\n' for n in range(1, 13))
    h = [{'role': 'assistant', 'content': bas}, {'role': 'user', 'content': BRIDGE['baslinje']},
         {'role': 'assistant', 'content': ev}, {'role': 'user', 'content': BRIDGE['evidens']}]
    drivers = [_driver(-0.7, name=f'Kategori {n:04d}', a0=1000.0, ef0=0.1) for n in range(1, 13)]
    assert [G.match_driver(d['name'], G.blocks(ev)) for d in drivers] == list(range(1, 13))
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': drivers})
    t = time.perf_counter()
    G.granska(model, h)
    assert time.perf_counter() - t < 3.0


# ---------- a driver the calculation renamed ----------

# The boendeladdning run of 2026-10-14, shortened: the calculation called the
# third driver "Tillkommande laddel, KBAB:s egen mark". The word overlap put
# it on Drivare 1 ("... KBAB:s mark"), and its kWh were marked against the
# fossil kilometres.
RENAMED_BASLINJE = (
    'Baslinje\n\n'
    'Drivare 1: Körsträcka med fossildrivna personbilar hos hyresgäster med boendeparkering på KBAB:s mark\n'
    '  A0: 2,7e7 (cirka 3 005 bilar × 9 000 km)\n  A0_enhet: km/år\n  EF0: 0,17\n  EF0_enhet: kg CO2e/km\n'
    'Drivare 2: Körsträcka med fossildrivna personbilar, konsumtionsbaserad avgränsning\n'
    '  A0: 2,7e7\n  A0_enhet: km/år\n  EF0: 0,21\n  EF0_enhet: kg CO2e/km\n'
    'Drivare 3: Elanvändning för laddning av elbilar hos hyresgäster\n'
    '  A0: 1,7e5 (cirka 95 elbilar × 9 000 km × 0,2 kWh/km)\n  A0_enhet: kWh/år\n'
    '  EF0: 0,05\n  EF0_enhet: kg CO2e/kWh\n  BAU_trend_EF (g_EF):\n    - medel: -7 %/år\n')
RENAMED_EVIDENS = (
    'Antaganden\n\n'
    'Drivare 1: Körsträcka med fossildrivna personbilar hos hyresgäster med boendeparkering på KBAB:s mark\n'
    '  Mekanism: Shift\n  Parameter: ΔA\n    Antagande_min: -0,02\n    Antagande_med: -0,04\n    Antagande_max: -0,09\n'
    'Drivare 2: Körsträcka med fossildrivna personbilar, konsumtionsbaserad avgränsning\n'
    '  Mekanism: Shift\n  Parameter: ΔA\n    Antagande_min: -0,02\n    Antagande_med: -0,04\n    Antagande_max: -0,09\n'
    'Drivare 3: Elanvändning för laddning av elbilar hos hyresgäster\n'
    '  Mekanism: Shift\n  Parameter: ΔA\n    Antagande_min: 0,109\n    Antagande_med: 0,176\n    Antagande_max: 0,299\n')


def _renamed(**third):
    h = [{'role': 'user', 'content': 'Boendeladdning'},
         {'role': 'assistant', 'content': RENAMED_BASLINJE}, {'role': 'user', 'content': BRIDGE['baslinje']},
         {'role': 'assistant', 'content': RENAMED_EVIDENS}, {'role': 'user', 'content': BRIDGE['evidens']}]
    fossil = dict(a0=27_000_000.0, a0_unit='km/år', delta_ef=0.0, delta_a={'min': -0.02, 'med': -0.04, 'max': -0.09})
    el = dict(name='Tillkommande laddel, KBAB:s egen mark', a0=170_000.0, a0_unit='kWh/år', ef0=0.05,
              ef0_unit='kg CO2e/kWh', g_ef=-0.07, delta_ef=0.0, delta_a={'min': 0.109, 'med': 0.176, 'max': 0.299})
    el.update(third)
    drivers = [_driver(name='Fossil körsträcka, KBAB:s egen mark (territoriell)', ef0=0.17, **fossil),
               _driver(name='Fossil körsträcka, KBAB:s egen mark (konsumtion)', ef0=0.21, **fossil),
               _driver(**el)]
    model = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': drivers})
    return [(a.nr, a.falt) for a in G.granska(model, h)]


def test_a_driver_the_calculation_renamed_is_compared_with_its_own_baseline():
    # Control: the name alone lands on the wrong driver.
    assert G.match_driver('Tillkommande laddel, KBAB:s egen mark', G.blocks(RENAMED_BASLINJE)) == 1
    assert _renamed() == []


def test_a_renamed_driver_is_still_marked_when_its_number_is_wrong():
    assert _renamed(a0=1_700_000.0) == [(2, 'a0')]
    assert _renamed(g_ef=-0.33) == [(2, 'g_ef')]


# ---------- added 2026-10-15: a zeroed effect, and the climate factors ----------

from types import SimpleNamespace  # noqa: E402

from caia.mode import UPPFOLJNING  # noqa: E402

pytestmark = pytest.mark.karlstad  # reads Karlstad's kommunprofil

FAKTORER = ('  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):\n'
            '    Territoriell_faktor: 1.0\n    Konsumtion_faktor: 1.15\n    Overlap_faktor: 1.0\n')


def _with_factors():
    h = _history()
    h[-2] = dict(h[-2], content=h[-2]['content'].replace('  Parameter: ΔEF', FAKTORER + '  Parameter: ΔEF'))
    return h


def test_an_effect_read_as_zero_in_every_scenario_is_marked(client, monkeypatch):
    """The approved assumption gives -0.38; an extraction that reads no change
    at all takes the driver out of the result (four such drivers in 141 saved
    runs, all of them an added electricity use read as nothing)."""
    driver = _driver(delta_ef={'min': 0.0, 'med': 0.0, 'max': 0.0})
    body, rows = _kalkyl(client, monkeypatch, driver, _history())
    assert rows['delta_ef']['godkant'] and 'effekten är 0' in rows['delta_ef']['godkant']
    assert '−0,38' in rows['delta_ef']['godkant']
    assert 'Ett tal i beräkningen avviker' in ' '.join(body['warnings'])


def test_a_zero_effect_with_no_source_stated_is_still_marked(client, monkeypatch):
    """The extraction most often leaves the source out when it reads no change,
    and a 0 without a source is labelled as the schema's default. The mark
    from the comparison must reach that row too, and the headline."""
    driver = _driver(delta_ef={'min': 0.0, 'med': 0.0, 'max': 0.0})
    del driver['kallor']['delta_ef']
    body, rows = _kalkyl(client, monkeypatch, driver, _history())
    assert 'effekten är 0' in rows['delta_ef']['godkant']
    assert 'Ett tal i beräkningen avviker' in ' '.join(body['warnings'])
    assert '1 behöver kontrolleras' in body['kallmarkering_md']


def test_a_zero_effect_the_approved_text_also_gives_is_not_marked(client, monkeypatch):
    h = _history()
    h[-2] = dict(h[-2], content=h[-2]['content'].replace('-0.15', '0').replace('-0.38', '0')
                 .replace('-0.85', '0'))
    _, rows = _kalkyl(client, monkeypatch, _driver(delta_ef={'min': 0.0, 'med': 0.0, 'max': 0.0}), h)
    assert not any(r['godkant'] for r in rows.values())


def test_a_climate_factor_read_differently_is_marked(client, monkeypatch):
    body, rows = _kalkyl(client, monkeypatch, _driver(cons=1.0), _with_factors())
    assert rows['cons']['godkant'] == 'avviker från evidenssteget, som anger Konsumtion_faktor 1,15'
    assert [k for k, r in rows.items() if r['godkant']] == ['cons']
    md = body['kallmarkering_md']
    assert 'Klimatfaktor, konsumtion' in md and '1 behöver kontrolleras' in md
    # Not counted among the input numbers: the six of the one driver.
    assert 'Kalkylen bygger på 6 inmatade tal' in md


def test_a_climate_factor_as_approved_is_not_marked(client, monkeypatch):
    _, rows = _kalkyl(client, monkeypatch, _driver(cons=1.15), _with_factors())
    assert not any(r['godkant'] for r in rows.values()) and 'cons' not in rows


def test_the_follow_up_prompt_may_keep_consumption_at_one():
    """The follow-up extraction prompt is the one from before the rule that
    lets Konsumtion_faktor stay above 1."""
    model = CalcModel.from_dict({'action_name': 'Elbilar', 'target_year': 2030,
                                 'drivers': [_driver(cons=1.0)]})
    assert [a.falt for a in G.granska(model, _with_factors())] == ['cons']
    follow = SimpleNamespace(mode=UPPFOLJNING, drivers=model.drivers)
    assert G.granska(follow, _with_factors()) == []


def test_factors_of_another_driver_are_not_compared():
    """Only the driver's own block: the numbers of another driver's factors
    are often different on purpose."""
    h = _with_factors()
    h[-2] = dict(h[-2], content=h[-2]['content'] + '\nDrivare 2: Laddel\n' + FAKTORER.replace('1.15', '0.05'))
    model = CalcModel.from_dict({'action_name': 'Elbilar', 'target_year': 2030,
                                 'drivers': [_driver(cons=1.15)]})
    assert G.granska(model, h) == []


def _two_blocks():
    h = _history()
    h[-2] = dict(h[-2], content=h[-2]['content'] + '\nDrivare 2: Laddel\n' + FAKTORER.replace('1.15', '0.05')
                 + '  Parameter: ΔA\n    Antagande_min: 100\n    Antagande_med: 200\n    Antagande_max: 300\n')
    return h


def _second(name):
    return CalcModel.from_dict({'action_name': 'Elbilar', 'target_year': 2030, 'drivers': [
        _driver(name='Övrigt'), _driver(name=name, cons=1.0, delta_ef={'min': 0.0, 'med': 0.0, 'max': 0.0})]})


def _new_rules(found):
    return [a.problem for a in found if a.nr == 1
            and ('faktor' in a.problem or 'effekten är 0' in a.problem)]


def test_factors_are_not_compared_when_name_and_place_point_at_different_blocks():
    """The second driver's name shares words with block 1 and its place is
    block 2, whose factors and effect belong to another driver: neither block
    is used, for a wider pool would invent marks here, not miss them."""
    assert _new_rules(G.granska(_second('Tjänstebilar fossila'), _two_blocks())) == []


def test_an_exact_name_decides_the_block_over_the_place():
    found = _new_rules(G.granska(_second('Tjänstebilar'), _two_blocks()))
    assert len(found) == 1 and '−0,38' in found[0]       # block 1's effect, not block 2's 200


def test_a_factor_given_in_percent_is_not_read_as_the_factor():
    h = _history()
    h[-2] = dict(h[-2], content=h[-2]['content'].replace(
        '  Parameter: ΔEF', '  Konsumtion_faktor: 15 %\n  Parameter: ΔEF'))
    model = CalcModel.from_dict({'action_name': 'Elbilar', 'target_year': 2030, 'drivers': [_driver(cons=1.0)]})
    assert [a.falt for a in G.granska(model, h) if a.falt == 'cons'] == []


def test_a_driver_matched_to_no_block_has_no_factors_to_compare():
    """A name that matches no approved driver is compared with all of them
    for its numbers, but not for its factors: those differ between drivers."""
    model = CalcModel.from_dict({'action_name': 'Elbilar', 'target_year': 2030,
                                 'drivers': [_driver(name='Något helt annat', cons=0.5)]})
    model.drivers.insert(0, CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                                 'drivers': [_driver(name='Övrigt')]}).drivers[0])
    assert [a for a in G.granska(model, _with_factors()) if a.falt in ('terr', 'cons', 'overlap')] == []
