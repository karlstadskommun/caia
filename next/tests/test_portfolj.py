"""The portfolio: several actions on shared emission pots, without counting the
same ton twice (caia.calc.portfolj).

The facit cases are the inquiry's own: Karlstad's house building 2030, the
Sola follow-up 2024 and the school meals. Every expected number is worked out
in the comment above it.
"""
from __future__ import annotations

import math
import random
import re
from pathlib import Path

import pytest
from caia import kommun
from caia.calc import CalcModel, compute, render_appendix
from caia.calc.engine import _driver_year
from caia.calc.portfolj import (
    SUM_NOTE,
    Del,
    Insats,
    PortfoljError,
    Pott,
    Rad,
    compute_portfolio,
    delar_from_model,
    duplicate_runs,
    load_potter,
    parse_appendix,
    render_portfolio,
)
from caia.mode import POTENTIAL, UPPFOLJNING
from caia.web import app as A

KARLSTAD = Path(kommun.__file__).parent / 'kommuner' / 'karlstad'


# ---------- helpers ----------

def _bygg(name: str, e_bau: float, delta: float, pot: str | None = 'husbyggnad') -> dict:
    """A driver whose baseline is e_bau ton a year (a0 ton × 1000 kg/ton) and
    whose full effect from 2026 is `delta` of it, all climate factors 1, so
    netto = ΔE = -delta × e_bau."""
    d = {'name': name, 'baseline_year': 2022, 'a0': e_bau, 'ef0': 1000.0, 'a0_unit': 'ton',
         'ramp': {'start_year': 2026, 'full_effect_year': 2026, 'profile': 'linjär'},
         'delta_a': 0.0, 'delta_ef': delta, 'terr': 1.0, 'cons': 1.0, 'overlap': 1.0}
    if pot:
        d['pot'] = pot
    return d


def _via_appendix(iid: str, name: str, *drivers: dict, mode: str = POTENTIAL) -> Insats:
    """An action the way production reads it: engine → appendix text → parser."""
    m = CalcModel.from_dict({'action_name': name, 'target_year': 2030, 'drivers': list(drivers)},
                            mode=mode)
    bilaga = parse_appendix('# Rapport\n\ntext\n\n' + render_appendix(m, compute(m)))
    assert bilaga is not None, name
    return Insats(id=iid, namn=name, mode=bilaga.mode, delar=bilaga.delar, skapad='2026-10-09')


def _del(namn: str, pott: str | None, years: dict[int, tuple], spread: float = 0.0) -> Del:
    """A driver built directly: years → (e_bau, basis[, attribution]); netto =
    basis. min/max are basis × (1 ∓ spread)."""
    rader = {}
    for sc, f in (('min', 1 - spread), ('med', 1.0), ('max', 1 + spread)):
        rader[sc] = {}
        for y, t in years.items():
            e, b = t[0], t[1] * f
            att = t[2] if len(t) > 2 else 1.0
            rader[sc][y] = Rad(e_bau=e, basis=b, terr=b, cons=0.0, net=b, attribution=att)
    return Del(namn=namn, rader=rader, pott=pott)


def _y(*t) -> dict[int, tuple]:
    """The same row every year of the potential window, 2026-2030."""
    return {y: t for y in range(2026, 2031)}


def _pott(pid: str, ton: float, ar: int = 2024) -> Pott:
    return Pott(id=pid, namn=pid.capitalize(), baslinje=ton, ar=ar, kalla='test')


def _ins(iid: str, mode: str, *delar: Del, mal_for: tuple = ()) -> Insats:
    return Insats(id=iid, namn=f'Åtgärd {iid}', mode=mode, delar=list(delar), mal_for=mal_for)


@pytest.fixture
def potter():
    return load_potter(KARLSTAD / 'potter.toml')


def _husbygg(mal: bool = False) -> list[Insats]:
    # The inquiry's shares: Halvera 50 %, materialval 6 900 of 25 000 (27,6 %),
    # klimatberäkningar 4 940 of 32 100 (15,4 %).
    out = [_via_appendix('halvera', 'Halvera klimatpåverkan från kommunens byggnationer',
                         _bygg('Byggande', 17200, -0.5)),
           _via_appendix('material', 'Klimatoptimerade materialval och återbruk',
                         _bygg('Material', 25000, -6900 / 25000)),
           _via_appendix('berakning', 'Införa klimatberäkningar i bygg-, VA- och infrastrukturprojekt',
                         _bygg('Projekt', 32100, -4940 / 32100))]
    if mal:
        out[0].mal_for = ('material', 'berakning')
    return out


# ---------- facit: Karlstad's house building 2030 ----------

# Pot P = 17 200. Shares on the pot: s = ΔE / max(E_BAU, P):
#   Halvera 8 600 / 17 200 = 0,5; materialval 6 900 / 25 000 = 0,276;
#   klimatberäkningar 4 940 / 32 100 = 0,15389.
# Sum of the parts on the pot: 17 200 × (0,5 + 0,276 + 0,15389) = 15 994 ≈ 16 000.
# Common baseline: 17 200 × (1 - 0,5 × 0,724 × 0,84611) = 11 932 ≈ 11 900.
# Halvera as the target for the other two: the target's 50 % = 8 600.

@pytest.mark.karlstad
def test_house_building_sum_of_parts_is_16_000(potter):
    pot = compute_portfolio(_husbygg(), potter)['pots']['husbyggnad']
    assert round(pot['claims']['med'][2030], -2) == 16000
    assert pot['claims']['med'][2030] == pytest.approx(15994.2, abs=0.6)


@pytest.mark.karlstad
def test_house_building_on_a_common_baseline_is_11_900(potter):
    pot = compute_portfolio(_husbygg(), potter)['pots']['husbyggnad']
    assert round(pot['reduction']['med'][2030], -2) == 11900
    assert pot['reduction']['med'][2030] == pytest.approx(11931.8, abs=0.6)


@pytest.mark.karlstad
def test_house_building_with_halvera_as_the_target_is_8_600(potter):
    res = compute_portfolio(_husbygg(mal=True), potter)
    pot = res['pots']['husbyggnad']
    assert pot['reduction']['med'][2030] == pytest.approx(8600, abs=0.5)
    # The tools are how the target is reached: nothing of their own on the pot.
    for tool in ('material', 'berakning'):
        assert pot['alloc_std'][tool]['med'][2030] == 0
        assert pot['alloc_alt'][tool]['med'][2030] == 0
    assert any('målet «Halvera' in w and '39 %' in w for w in res['warnings'])


@pytest.mark.karlstad
def test_an_action_computed_on_more_than_the_pot_keeps_the_rest_outside(potter):
    # Materialval: 6 900 of its own, 0,276 × 17 200 = 4 747 of it on the pot,
    # 2 153 outside. Alone on the pot it keeps all 6 900.
    ins = _husbygg()[1]
    other = _via_appendix('annan', 'Något annat', _bygg('Annat', 100, -0.1, pot=None))
    res = compute_portfolio([ins, other], potter)
    a = res['actions']['material']
    assert a['outside']['husbyggnad']['med'][2030] == pytest.approx(2153.2, abs=0.6)
    assert a['std_net']['med'][2030] == pytest.approx(6900, abs=0.6)
    assert any('mer än hela Kommunens husbyggnad' in w for w in res['warnings'])


# ---------- facit: Sola 2024, follow-up ----------

# BUF's furniture purchase, 100 ton, and Sola's furniture part, 31 ton, on the
# same furniture flow; Sola's building part, 33 ton, on its own flow.
# With the flow P = 100: BUF takes it all (s = 1), so the flow gives 100 and
# with the building part 133. As P grows the overlap vanishes: 100 + 31 + 33 = 164.

def _sola(p_mobel: float) -> tuple[list[Insats], dict]:
    buf = _ins('buf', UPPFOLJNING, _del('Möbelinköp', 'mobel', {2024: (100, 100)}))
    sola = _ins('sola', UPPFOLJNING, _del('Möbler', 'mobel', {2024: (31, 31)}),
                _del('Bygg', 'bygg', {2024: (33, 33)}))
    return [buf, sola], {'mobel': _pott('mobel', p_mobel), 'bygg': _pott('bygg', 33)}


def test_sola_with_the_flow_equal_to_buf_is_133():
    ins, potter = _sola(100)
    res = compute_portfolio(ins, potter)
    assert res['total']['std_net']['med'][2024] == pytest.approx(133)
    assert res['total']['own_net']['med'][2024] == pytest.approx(164)


def test_sola_with_a_large_flow_approaches_164():
    ins, potter = _sola(1e7)
    assert compute_portfolio(ins, potter)['total']['std_net']['med'][2024] == pytest.approx(164, abs=0.01)


@pytest.mark.parametrize('p', [100, 120, 160, 250, 1000, 10000])
def test_sola_stays_between_133_and_164(p):
    ins, potter = _sola(p)
    v = compute_portfolio(ins, potter)['total']['std_net']['med'][2024]
    assert 133 - 1e-9 <= v <= 164 + 1e-9


def test_the_building_flow_claimed_three_times_counts_once_and_warns():
    # Three actions each attribute the whole 33-ton building flow to themselves.
    ins = [_ins(i, UPPFOLJNING, _del('Bygg', 'bygg', {2024: (33, 33, 1.0)})) for i in 'abc']
    ins[1].namn, ins[2].namn = 'Åtgärd b2', 'Åtgärd c3'
    res = compute_portfolio(ins, {'bygg': _pott('bygg', 33)})
    assert res['pots']['bygg']['reduction']['med'][2024] == pytest.approx(33)
    assert res['total']['own_net']['med'][2024] == pytest.approx(99)
    warn = [w for w in res['warnings'] if 'tillskriver sig' in w]
    assert warn and '300 %' in warn[0]


# ---------- facit: school meals ----------

def test_school_meals_are_24_percent_not_25():
    # 5 % and 20 % of the same 1 000 ton: 1 000 × (1 - 0,95 × 0,80) = 240.
    a = _ins('a', POTENTIAL, _del('Mat', 'mat', _y(1000, 50)))
    b = _ins('b', POTENTIAL, _del('Mat', 'mat', _y(1000, 200)))
    res = compute_portfolio([a, b], {'mat': _pott('mat', 1000)})
    assert res['pots']['mat']['reduction']['med'][2030] == pytest.approx(240)


# ---------- the rule: a pot never gives more than itself ----------

def test_the_sum_over_a_pot_is_never_larger_than_the_pot():
    rnd = random.Random(20261009)
    for _ in range(300):
        p = rnd.uniform(10, 5000)
        n = rnd.randint(2, 7)
        ins = []
        for i in range(n):
            e = rnd.choice([p, rnd.uniform(1, p), rnd.uniform(p, 4 * p)])
            ins.append(_ins(f'x{i}', POTENTIAL, _del('d', 'pot', _y(e, e * rnd.uniform(0, 1)))))
        if rnd.random() < 0.3:
            ins[0].mal_for = (ins[1].id,)
        pot = compute_portfolio(ins, {'pot': _pott('pot', p)})['pots']['pot']
        red = pot['reduction']['med'][2030]
        assert red <= p + 1e-6
        assert red <= pot['claims']['med'][2030] + 1e-6
        for rule in ('alloc_std', 'alloc_alt'):
            assert sum(pot[rule][i.id]['med'][2030] for i in ins) == pytest.approx(red, rel=1e-9, abs=1e-6)


def test_the_two_rules_agree_when_actions_do_not_overlap_and_differ_when_they_do():
    # Two equal actions on a pot share it equally under both rules.
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(100, 50)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(100, 50)))
    pot = compute_portfolio([a, b], {'p': _pott('p', 100)})['pots']['p']
    assert pot['alloc_std']['a']['med'][2030] == pytest.approx(37.5)
    assert pot['alloc_alt']['a']['med'][2030] == pytest.approx(37.5)
    # 80 % and 10 %: the pot gives 100 × (1 - 0,2 × 0,9) = 82. Proportional:
    # 82 × 8/9 = 72,9 and 9,1. Shapley: a = (80 + 72)/2 = 76, b = (10 + 2)/2 = 6.
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(100, 80)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(100, 10)))
    pot = compute_portfolio([a, b], {'p': _pott('p', 100)})['pots']['p']
    assert pot['alloc_std']['a']['med'][2030] == pytest.approx(82 * 8 / 9)
    assert pot['alloc_alt']['a']['med'][2030] == pytest.approx(76)
    assert pot['alloc_alt']['b']['med'][2030] == pytest.approx(6)


def test_a_driver_without_a_pot_counts_as_before_and_is_named():
    a = _ins('a', POTENTIAL, _del('Utan', None, _y(100, 40)))
    b = _ins('b', POTENTIAL, _del('Utan', None, _y(100, 40)))
    res = compute_portfolio([a, b], {})
    assert res['total']['std_net']['med'][2030] == pytest.approx(80)
    assert any('utan utsläppspott räknas som i dag' in w for w in res['warnings'])


# ---------- one run per action, and what the portfolio refuses ----------

def test_five_runs_of_the_logistics_support_are_refused():
    names = ['Logistikstöd 40.2', 'logistikstöd 40.2', 'Logistikstöd 40.2 ', 'LOGISTIKSTÖD 40.2',
             'Logistikstöd, 40.2']
    ins = [_ins(f'r{i}', POTENTIAL, _del('d', None, _y(1000, v)))
           for i, v in enumerate([131, 900, 2400, 4100, 5815])]
    for i, n in zip(ins, names):
        i.namn = n
    assert len(duplicate_runs(ins)[0]) == 5
    with pytest.raises(PortfoljError, match='en körning per åtgärd'):
        compute_portfolio(ins, {})


def test_mixed_modes_and_too_few_actions_are_refused():
    a = _ins('a', POTENTIAL, _del('d', None, _y(1, 1)))
    b = _ins('b', UPPFOLJNING, _del('d', None, _y(1, 1)))
    with pytest.raises(PortfoljError, match='blandar'):
        compute_portfolio([a, b], {})
    with pytest.raises(PortfoljError, match='minst två'):
        compute_portfolio([a], {})


@pytest.mark.parametrize('setup,match', [
    (lambda a, b, c: setattr(a, 'mal_for', ('a',)), 'sig själv'),
    (lambda a, b, c: (setattr(a, 'mal_for', ('c',)), setattr(b, 'mal_for', ('c',))), 'två mål'),
    (lambda a, b, c: (setattr(a, 'mal_for', ('b',)), setattr(b, 'mal_for', ('c',))), 'både ett mål'),
    (lambda a, b, c: setattr(a, 'mal_for', ('zz',)), 'inte finns'),
])
def test_a_target_relation_that_cannot_be_counted_is_refused(setup, match):
    ins = [_ins(i, POTENTIAL, _del('d', 'p', _y(100, 10))) for i in 'abc']
    setup(*ins)
    with pytest.raises(PortfoljError, match=match):
        compute_portfolio(ins, {'p': _pott('p', 100)})


def test_an_unknown_pot_is_refused():
    ins = [_ins(i, POTENTIAL, _del('d', 'okand', _y(100, 10))) for i in 'ab']
    with pytest.raises(PortfoljError, match='okand'):
        compute_portfolio(ins, {})


# ---------- the text never shows a bare sum ----------

def _sum_lines(text: str) -> list[str]:
    """Every line that shows the actions' own numbers added together: a table
    row or header that says Summa, adds them ("adderade") or totals their own
    figures, and the warning that names their sum on a pot."""
    out = []
    for ln in text.splitlines():
        if ln.startswith(('| Åtgärd |', '| Portföljen')):  # column header; the portfolio row
            continue
        if (ln.startswith('| Summa') or 'adderade' in ln
                or ln.startswith('| Summa av åtgärdernas egna tal')
                or 'räknar var för sig med' in ln):
            out.append(ln)
    return out


@pytest.mark.karlstad
def test_every_sum_of_the_actions_own_numbers_says_it_counts_tons_twice(potter):
    for mal in (False, True):
        text = render_portfolio(compute_portfolio(_husbygg(mal=mal), potter))
        lines = _sum_lines(text)
        # The total row, the per-action sum row, the pot table header and the
        # overlap warning.
        assert len(lines) >= 4, lines
        for ln in lines:
            assert SUM_NOTE in ln or re.search(r'ton\b.{0,30}flera gånger', ln), ln


@pytest.mark.karlstad
def test_the_text_has_no_internal_words(potter):
    text = render_portfolio(compute_portfolio(_husbygg(mal=True), potter))
    for word in ('basis', 'claim', 'alloc', 'Shapley', 'e_bau', 'None', 'pott_id', 'nan', 'inf'):
        assert not re.search(rf'\b{word}\b', text), word


# ---------- reading the appendix back ----------

def test_the_appendix_reads_back_to_the_engines_numbers():
    # Two drivers, a ramp, growth and climate factors below one: every number
    # read back is within the appendix's rounding of what the engine computed.
    d1 = {'name': 'Bilresor | pendling', 'baseline_year': 2023, 'a0': 123456.0, 'ef0': 0.17,
          'a0_unit': 'km/år', 'ramp': {'start_year': 2025, 'full_effect_year': 2028, 'profile': 'linjär'},
          'g_a': 0.01, 'g_ef': -0.02, 'delta_a': {'min': -0.05, 'med': -0.1, 'max': -0.2},
          'delta_ef': 0.0, 'terr': 1.0, 'cons': 0.4, 'overlap': 0.4, 'pot': 'personbilstrafik'}
    d2 = dict(d1, name='Värme', a0=5.0e6, ef0=0.05, a0_unit='kWh', cons=1.0, overlap=0.0, terr=0.0)
    del d2['pot']
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [d1, d2]})
    b = parse_appendix(render_appendix(m, compute(m)))
    assert b is not None and b.mode == POTENTIAL
    assert [d.pott for d in b.delar] == ['personbilstrafik', None]
    assert b.delar[0].namn == 'Bilresor | pendling'
    direct = delar_from_model(m)
    for got, want in zip(b.delar, direct):
        assert got.rader.keys() == want.rader.keys()
        for sc in ('min', 'med', 'max'):
            assert got.rader[sc].keys() == want.rader[sc].keys()
            for y, r in want.rader[sc].items():
                g = got.rader[sc][y]
                for f in ('e_bau', 'basis', 'terr', 'cons', 'net'):
                    w = getattr(r, f)
                    tol = 0.005 if abs(w) < 10 else 0.05 if abs(w) < 1000 else 0.5
                    assert getattr(g, f) == pytest.approx(w, abs=tol + 1e-9), (sc, y, f)
    assert direct[0].rader['med'][2030] == pytest.approx(direct[0].rader['med'][2030])
    r = _driver_year(m.drivers[0], 'med', 2030)
    assert b.delar[0].rader['med'][2030].net == pytest.approx(r.net, abs=0.5)


def test_a_follow_up_appendix_reads_back_with_its_mode_and_attribution():
    d = _bygg('Möbler', 100, -0.31, pot=None)
    d['ramp'] = {'start_year': 2024, 'full_effect_year': 2024, 'profile': 'linjär'}
    d['attribution'] = {'min': 0.5, 'med': 0.7, 'max': 0.9}
    m = CalcModel.from_dict({'action_name': 'Sola', 'target_year': 2024, 'followup_year': 2024,
                             'drivers': [d]}, mode=UPPFOLJNING)
    b = parse_appendix(render_appendix(m, compute(m)))
    assert b is not None and b.mode == UPPFOLJNING
    assert b.delar[0].rader['med'][2024].attribution == pytest.approx(0.7)
    assert b.delar[0].rader['med'][2024].basis == pytest.approx(31 * 0.7, abs=0.05)


@pytest.mark.parametrize('text', [
    '',
    '# Rapport\n\nInget här.',
    # A hand-written appendix (before 2026-09-30) has the heading but not the stamp.
    '**Teknisk bilaga: Beräkningssteg**\n\nSpråkmodellen skrev den här.\n\nDrivare 1: x\n',
])
def test_a_report_without_the_engines_appendix_is_not_read(text):
    assert parse_appendix(text) is None


def test_an_appendix_from_before_the_rename_is_read():
    # Saved before 2026-10-08 the stamp said "Zaids kalkylmotor".
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                             'drivers': [_bygg('Bygg', 100, -0.1)]})
    text = render_appendix(m, compute(m)).replace('CAIA:s kalkylmotor', 'Zaids kalkylmotor')
    assert 'Zaids kalkylmotor' in text
    assert parse_appendix(text) is not None
    assert parse_appendix(text.replace('Zaids kalkylmotor', 'Någons kalkylmotor')) is None


def test_a_damaged_table_is_not_read_as_numbers():
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                             'drivers': [_bygg('Bygg', 100, -0.1)]})
    text = render_appendix(m, compute(m))
    assert parse_appendix(text) is not None
    assert parse_appendix(text.replace('| 2028 |', '| 2028 | x |', 1)) is None
    cut = text[:text.index('Scenario max:')]
    assert parse_appendix(cut) is None


# ---------- the register of pots ----------

@pytest.mark.karlstad
def test_the_car_traffic_pot_is_the_emission_databases_number(potter):
    # Nationella emissionsdatabasen, Transporter;Personbilar, last column (2023).
    path = KARLSTAD / 'data' / 'Kommunrapport_karlstad_vaxthusgaser_totalt.csv'
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    years = next(ln for ln in lines if ln.startswith(';;;;1990')).split(';')
    row = next(ln for ln in lines if ln.startswith('Transporter;Personbilar;')).split(';')
    value = float(row[years.index('2023')].replace(',', '.'))
    pot = next(p for p in potter if p.id == 'personbilstrafik')
    assert pot.ar == 2023
    assert pot.baslinje == round(value)


@pytest.mark.karlstad
def test_karlstads_register_holds_the_two_starting_pots(potter):
    assert {p.id: p.baslinje for p in potter} == {'husbyggnad': 17200, 'personbilstrafik': 79454}
    assert all(p.kalla for p in potter)


def test_a_profile_without_a_register_has_no_pots(tmp_path):
    assert load_potter(tmp_path / 'potter.toml') == []
    exempel = Path(kommun.__file__).parent / 'kommuner' / 'exempel'
    assert not (exempel / 'potter.toml').exists()


@pytest.mark.parametrize('body,match', [
    ('[[pott]]\nid = "A B"\nnamn = "x"\nkalla = "y"\nbaslinje = 1\nar = 2020\n', 'id'),
    ('[[pott]]\nid = "a"\nnamn = "x"\nkalla = "y"\nbaslinje = 0\nar = 2020\n', 'större än 0'),
    ('[[pott]]\nid = "a"\nnamn = "x"\nbaslinje = 1\nar = 2020\n', 'kalla'),
    ('[[pott]]\nid = "a"\nnamn = "x"\nkalla = "y"\nbaslinje = 1\nar = 2020\n' * 2, 'två gånger'),
    ('[[pott]]\nid = "a"\nnamn = "x"\nkalla = "y"\nbaslinje = "många"\nar = 2020\n', 'tal'),
])
def test_a_wrong_register_says_what_is_wrong(tmp_path, body, match):
    f = tmp_path / 'potter.toml'
    f.write_text(body, encoding='utf-8')
    with pytest.raises(PortfoljError, match=match):
        load_potter(f)


def test_a_trend_moves_the_pot():
    p = Pott(id='p', namn='P', baslinje=1000, ar=2020, kalla='k', trend=-0.1)
    assert p.ton(2022) == pytest.approx(810)


# ---------- the API ----------

UID = 'user-1'
IDS = ['11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
       '33333333-3333-3333-3333-333333333333']


def _report(name: str, *drivers: dict) -> str:
    m = CalcModel.from_dict({'action_name': name, 'target_year': 2030, 'drivers': list(drivers)})
    return f'## {name}\n\nText.\n\n' + render_appendix(m, compute(m))


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: {'sub': UID, 'email': 'user@kommun.se'})
    monkeypatch.setattr(A, 'ALLOWED_EMAILS', {'@kommun.se'})
    monkeypatch.setattr(A, '_report_hits', {})
    rows = {
        IDS[0]: {'id': IDS[0], 'action_name': 'Halvera klimatpåverkan', 'created_at': '2026-10-01T10:00:00Z',
                 'formatted_report': _report('Halvera', _bygg('Byggande', 17200, -0.5))},
        IDS[1]: {'id': IDS[1], 'action_name': 'Klimatoptimerade materialval', 'created_at': '2026-10-02T10:00:00Z',
                 'formatted_report': _report('Material', _bygg('Material', 25000, -0.276, pot=None))},
        IDS[2]: {'id': IDS[2], 'action_name': 'Gammal analys', 'created_at': '2026-09-01T10:00:00Z',
                 'formatted_report': '## Gammal\n\n**Teknisk bilaga: Beräkningssteg**\n\nSkriven av modellen.'},
    }
    calls = []

    def fake(method, table, data=None, token=None, params=None):
        calls.append(params)
        assert method == 'GET' and table == 'reports'
        assert params['user_id'] == f'eq.{UID}'
        wanted = params['id'][len('in.('):-1].split(',')
        return [rows[i] for i in wanted if i in rows]

    monkeypatch.setattr(A, 'supabase_request', fake)
    client = A.app.test_client()

    def post(path, body):
        return client.post(path, json=body, headers={'Authorization': 'Bearer t'})
    post.rows, post.calls = rows, calls
    return post


@pytest.mark.karlstad
def test_step_one_lists_parts_pots_and_a_report_that_cannot_be_used(api):
    r = api('/api/portfolj/atgarder', {'ids': IDS})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert {p['id'] for p in d['potter']} == {'husbyggnad', 'personbilstrafik'}
    a = {x['id']: x for x in d['atgarder']}
    assert a[IDS[0]]['delar'] == [{'namn': 'Byggande', 'pott': 'husbyggnad'}]
    assert a[IDS[1]]['delar'] == [{'namn': 'Material', 'pott': None}]
    assert 'tekniska bilaga' in a[IDS[2]]['fel']


@pytest.mark.karlstad
def test_step_two_counts_the_portfolio_with_the_users_pots(api):
    r = api('/api/portfolj', {'ids': IDS[:2], 'potter': {IDS[1]: ['husbyggnad']}, 'mal_for': {}})
    assert r.status_code == 200, r.get_data(as_text=True)
    md = r.get_json()['markdown']
    assert SUM_NOTE in md
    # 17 200 × (1 - 0,5 × 0,724) = 10 973,6 on the pot.
    assert '10 974' in md
    assert 'Kommunens husbyggnad' in md


def test_step_two_refuses_a_report_without_the_appendix_and_a_foreign_pot(api):
    r = api('/api/portfolj', {'ids': IDS, 'potter': {}, 'mal_for': {}})
    assert r.status_code == 422 and 'tekniska bilaga' in r.get_json()['error']
    r = api('/api/portfolj', {'ids': IDS[:2], 'potter': {IDS[1]: ['hela-sverige']}, 'mal_for': {}})
    assert r.status_code == 422
    r = api('/api/portfolj', {'ids': IDS[:2], 'potter': {IDS[1]: ['husbyggnad', None]}, 'mal_for': {}})
    assert r.status_code == 400


def test_two_runs_of_the_same_action_are_refused_at_step_one(api):
    api.rows[IDS[1]]['action_name'] = 'halvera klimatpåverkan.'
    r = api('/api/portfolj/atgarder', {'ids': IDS[:2]})
    assert r.status_code == 422
    assert 'en körning per åtgärd' in r.get_json()['error']
    assert '2026-10-01' in r.get_json()['error']


@pytest.mark.parametrize('ids', [[], 'x', ['not-a-uuid', IDS[0]], [IDS[0], IDS[0]]])
def test_ids_must_be_the_users_report_ids(api, ids):
    r = api('/api/portfolj/atgarder', {'ids': ids})
    assert r.status_code in (400, 422)


def test_another_users_report_is_not_found(api):
    del api.rows[IDS[1]]
    r = api('/api/portfolj', {'ids': IDS[:2], 'potter': {}, 'mal_for': {}})
    assert r.status_code == 422
    assert 'finns inte bland dina' in r.get_json()['error']


def test_the_routes_need_a_signed_in_user_and_are_rate_limited(monkeypatch):
    for name in ('portfolj_atgarder', 'portfolj_berakna'):
        assert getattr(A.app.view_functions[name], 'rate_limited', False), name
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(A, 'get_user_claims', lambda: None)
    reads = []
    monkeypatch.setattr(A, 'supabase_request', lambda *a, **k: reads.append(a) or [])
    for path in ('/api/portfolj', '/api/portfolj/atgarder'):
        r = A.app.test_client().post(path, json={'ids': IDS[:2]})
        assert r.status_code == 401, (path, r.status_code)
    assert reads == []


def test_the_page_offers_the_portfolio_only_with_saved_analyses(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'SUPABASE_URL', 'https://example.supabase.co')
    html = A.app.test_client().get('/').get_data(as_text=True)
    assert 'id="portfolioModal"' in html and 'onclick="openPortfolio()"' in html
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    html = A.app.test_client().get('/').get_data(as_text=True)
    assert 'id="portfolioModal"' not in html and 'onclick="openPortfolio()"' not in html


def test_shares_never_turn_a_pot_negative():
    # Even a share read as above 1 (rounding at the edge) is held at 1.
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(100, 100.4)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(100, 50)))
    pot = compute_portfolio([a, b], {'p': _pott('p', 100)})['pots']['p']
    assert 0 <= pot['reduction']['med'][2030] <= 100
    assert math.isfinite(pot['alloc_alt']['b']['med'][2030])


# ---------- review 2026-10-09: what the first version got wrong ----------

def test_a_cut_and_a_rise_on_one_pot_are_not_shared_as_shares_of_a_sum():
    # Pot 1 000, A cuts 50 % (+500), B raises 30 % (-300). The pot gives
    # 1 000 × (1 - 0,5 × 1,3) = 350. Proportional to claims would give A
    # 350 × 500/200 = 875, more than it did. Shapley: A = (500 + 650)/2 = 575,
    # B = (-300 - 150)/2 = -225.
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(1000, 500)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(1000, -300)))
    res = compute_portfolio([a, b], {'p': _pott('p', 1000)})
    pot = res['pots']['p']
    assert pot['reduction']['med'][2030] == pytest.approx(350)
    assert pot['alloc_std']['a']['med'][2030] == pytest.approx(575)
    assert pot['alloc_std']['b']['med'][2030] == pytest.approx(-225)
    assert any('både åtgärder som minskar och åtgärder som ökar' in w for w in res['warnings'])
    assert not any('räknas flera gånger' in w for w in res['warnings'])


def test_near_cancellation_does_not_run_off():
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(1000, 500)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(1000, -499.99)))
    pot = compute_portfolio([a, b], {'p': _pott('p', 1000)})['pots']['p']
    assert abs(pot['alloc_std']['a']['med'][2030]) < 1000


def test_outside_parts_of_two_actions_are_named_as_possibly_the_same_tons():
    # Both computed on 50 000 t, both marked on a 1 000 t pot, each -50 %.
    a = _ins('a', POTENTIAL, _del('d', 'p', _y(50000, 25000)))
    b = _ins('b', POTENTIAL, _del('d', 'p', _y(50000, 25000)))
    res = compute_portfolio([a, b], {'p': _pott('p', 1000)})
    assert any('utanför potten' in w and 'kan vara samma ton' in w for w in res['warnings'])
    text = render_portfolio(res)
    assert '| Portföljen, där åtgärder på samma utsläppspott inte räknas två gånger (delar utanför potten är adderade som i analyserna) |' in text


def test_without_pots_the_portfolio_row_claims_nothing():
    a = _ins('a', POTENTIAL, _del('d', None, _y(100, 40)))
    b = _ins('b', POTENTIAL, _del('d', None, _y(100, 40)))
    text = render_portfolio(compute_portfolio([a, b], {}))
    assert '| Portföljen (delar utan utsläppspott är adderade som i analyserna) |' in text
    assert 'inte räknas två gånger' not in text


def test_a_follow_up_window_narrower_than_an_analysis_says_so():
    a = _ins('a', UPPFOLJNING, _del('d', None, {2023: (10, 1), 2024: (10, 2), 2025: (10, 3)}))
    b = _ins('b', UPPFOLJNING, _del('d', None, {2025: (10, 4)}))
    res = compute_portfolio([a, b], {})
    assert res['window'] == [2025]
    warn = [w for w in res['warnings'] if '«Åtgärd a»' in w and 'inte analysens eget medel' in w]
    assert warn and 'åren 2023–2025' in warn[0]
    assert not any('«Åtgärd b»' in w and 'eget medel' in w for w in res['warnings'])


def test_a_renamed_column_header_is_not_a_server_error():
    d = _bygg('Möbler', 100, -0.31, pot=None)
    d['ramp'] = {'start_year': 2024, 'full_effect_year': 2024, 'profile': 'linjär'}
    d['attribution'] = {'min': 0.5, 'med': 0.7, 'max': 0.9}
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2024, 'followup_year': 2024,
                             'drivers': [d]}, mode=UPPFOLJNING)
    text = render_appendix(m, compute(m))
    assert parse_appendix(text) is not None
    assert parse_appendix(text.replace('| Netto |', '| Nett0 |')) is None


def test_a_unit_text_cannot_set_the_pot():
    d = _bygg('Bygg', 100, -0.1, pot='husbyggnad')
    d['a0_unit'] = 'ton; utsläppspott personbilstrafik;'
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [d]})
    assert parse_appendix(render_appendix(m, compute(m))).delar[0].pott == 'husbyggnad'
    del d['pot']
    m = CalcModel.from_dict({'action_name': 'x', 'target_year': 2030, 'drivers': [d]})
    assert parse_appendix(render_appendix(m, compute(m))).delar[0].pott is None


def test_a_pot_choice_that_is_not_text_is_a_400_not_a_500(api):
    r = api('/api/portfolj', {'ids': IDS[:2], 'potter': {IDS[1]: [[1]]}, 'mal_for': {}})
    assert r.status_code == 422


def test_a_broken_register_does_not_show_the_server_path(api, monkeypatch, tmp_path):
    bad = tmp_path / 'potter.toml'
    bad.write_text('[[pott]]\nid = "A B"\n', encoding='utf-8')
    monkeypatch.setattr(A.portfolj, 'load_potter', lambda path: load_potter(bad))
    r = api('/api/portfolj/atgarder', {'ids': IDS[:2]})
    assert r.status_code == 422
    assert str(tmp_path) not in r.get_json()['error']
