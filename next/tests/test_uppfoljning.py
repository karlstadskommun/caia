"""Follow-up mode (uppföljningsläge): the engine's new inputs, the sums a
follow-up needs, the flags on bearing assumptions, and the mode reaching every
step.

Hand-computed cases, in the style of test_calc_golden. The base driver is the
one test_appendix uses: E_BAU = 1000 km × 2 kg = 2,00 t every year, ΔA −20 %
(−10 / −30 %), terr 1, cons 0,5, overlap 0,5, so net = ΔE in every year
(terr + cons − overlap = 1 + 0,5 − 0,5).
"""
from __future__ import annotations

import caia.web.app as A
import pytest
from caia.agents.uppfoljning import KARNA, STEG, for_mode
from caia.calc import CalcModel, compute, render_appendix, render_markdown
from caia.calc.engine import _driver_year, bearing, sanity_warnings
from caia.calc.schema import Driver, grants_of
from caia.kallmarkering import granska
from caia.mode import POTENTIAL, UPPFOLJNING, mode_of
from pytest import approx


def _drv(**over) -> dict:
    d = {
        'name': 'Bilresor', 'baseline_year': 2024, 'a0': 1000.0, 'ef0': 2.0, 'a0_unit': 'km/år',
        'ramp': {'start_year': 2025, 'full_effect_year': 2025, 'profile': 'linjär'},
        'g_a': 0.0, 'g_ef': 0.0,
        'delta_a': {'min': -0.1, 'med': -0.2, 'max': -0.3}, 'delta_ef': 0.0,
        'terr': 1.0, 'cons': 0.5, 'overlap': 0.5,
    }
    d.update(over)
    return d


def _model(*drivers, mode=UPPFOLJNING, **top) -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                'drivers': list(drivers) or [_drv()], **top}, mode=mode)


def _net(model, year, sc='med', i=0):
    return _driver_year(model.drivers[i], sc, year).net


# ---------- the mode itself ----------

def test_mode_defaults_to_potential_and_refuses_unknown_names():
    assert mode_of(None) == POTENTIAL
    assert mode_of('') == POTENTIAL
    assert mode_of('Uppföljning') == UPPFOLJNING
    with pytest.raises(ValueError):
        mode_of('uppfölning')


def test_potential_prompts_are_untouched_and_follow_up_adds_the_rules():
    for step in STEG:
        assert for_mode('SYS', step, POTENTIAL) == 'SYS'
        text = for_mode('SYS', step, UPPFOLJNING)
        assert text.startswith('SYS\n\n') and KARNA in text and STEG[step] in text


# ---------- attribution ----------

def test_attribution_scales_the_change_per_scenario():
    m = _model(_drv(attribution={'min': 0.3, 'med': 0.5, 'max': 0.7}))
    # Full effect from 2025: ΔE = 2,00 × 20 % = 0,40 t; × 0,5 = 0,20.
    assert _net(m, 2026) == approx(0.20)
    # min: 2,00 × 10 % × 0,3 = 0,06; max: 2,00 × 30 % × 0,7 = 0,42.
    assert _net(m, 2026, 'min') == approx(0.06)
    assert _net(m, 2026, 'max') == approx(0.42)


def test_default_attribution_changes_nothing():
    plain = compute(_model(mode=POTENTIAL))
    one = compute(_model(_drv(attribution=1.0), mode=POTENTIAL))
    assert one['med']['total']['cumulative_net'] == plain['med']['total']['cumulative_net']


@pytest.mark.parametrize('bad', [1.5, -0.1, {'min': 0.2, 'med': 60, 'max': 0.9}])
def test_attribution_outside_zero_one_is_refused(bad):
    with pytest.raises(ValueError, match='attribution'):
        Driver.from_dict(_drv(attribution=bad))


def test_a_null_attribution_is_absent_not_a_crash():
    # A crash here sends the whole calculation to the LLM fallback.
    assert Driver.from_dict(_drv(attribution=None)).attribution.med == 1.0


# ---------- decay and the partial first year ----------

def test_decay_halves_the_effect_each_half_life_after_full_effect():
    m = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025,
                          'half_life': {'min': 0.5, 'med': 1, 'max': 2}}))
    assert _net(m, 2025) == approx(0.40)        # full effect year, no decay yet
    assert _net(m, 2026) == approx(0.20)        # one half-life
    assert _net(m, 2027) == approx(0.10)        # two
    assert _net(m, 2026, 'max') == approx(0.60 * 0.5 ** 0.5)  # 30 %, half-life 2 years
    assert _net(m, 2026, 'min') == approx(0.20 * 0.25)        # 10 %, half-life ½ year


def test_first_year_share_applies_to_the_start_year_only():
    m = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025,
                          'first_year_share': 0.75}))
    assert _net(m, 2025) == approx(0.30)
    assert _net(m, 2026) == approx(0.40)


def test_a_first_year_share_on_a_ramp_is_not_claimed_and_is_warned_about():
    # A ramp is already 0 in its start year, so the share changes nothing; the
    # text must not say it was applied, and the page must say why.
    m = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2027,
                          'first_year_share': 0.75}))
    r = compute(m)
    assert 'verkar 75 %' not in render_markdown(m, r)
    assert any('andelen av startåret (75 %) används inte' in w for w in sanity_warnings(r, m))
    direct = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025,
                               'first_year_share': 0.75}))
    rd = compute(direct)
    assert 'verkar 75 % av 2025' in render_markdown(direct, rd)
    assert not any('andelen av startåret' in w for w in sanity_warnings(rd, direct))


def test_end_year_still_cuts_a_decaying_effect():
    m = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025, 'half_life': 1,
                          'end_year': 2026}))
    assert _net(m, 2026) == approx(0.20)
    assert _net(m, 2027) == 0


def test_last_year_share_applies_to_each_scenarios_end_year_only():
    # Klimatmånaden 2026-10-23: the campaign stops when next year's starts on
    # 13 May (0.36 of the year) in min and medel, in 2026 (0.32) in max.
    m = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025,
                          'end_year': {'min': 2026, 'med': 2026, 'max': 2027},
                          'last_year_share': {'min': 0.36, 'med': 0.36, 'max': 0.32}}))
    assert _net(m, 2025) == approx(0.40)
    assert _net(m, 2026) == approx(0.40 * 0.36)
    assert _net(m, 2027) == 0
    assert _net(m, 2026, 'max') == approx(0.60)
    assert _net(m, 2027, 'max') == approx(0.60 * 0.32)
    r = compute(m)
    assert 'sista året verkar 36 % av 2026 / 36 % av 2026 / 32 % av 2027' in render_markdown(m, r)
    assert 'Under slutåret multipliceras' in render_appendix(m, r)
    assert not any('andelen av slutåret' in w for w in sanity_warnings(r, m))


def test_last_year_share_is_not_applied_without_an_end_year_or_in_the_start_year():
    none = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025,
                             'last_year_share': 0.5}))
    assert _net(none, 2030) == approx(0.40)
    r = compute(none)
    assert any('andelen av slutåret används inte' in w for w in sanity_warnings(r, none))
    # Same start and end year: first_year_share carries the whole share.
    same = _model(_drv(ramp={'start_year': 2025, 'full_effect_year': 2025, 'end_year': 2025,
                             'first_year_share': 0.5, 'last_year_share': 0.5}))
    assert _net(same, 2025) == approx(0.20)


@pytest.mark.parametrize('ramp, match', [
    ({'start_year': 2025, 'full_effect_year': 2025, 'end_year': 2026, 'last_year_share': 0},
     'last_year_share'),
    ({'start_year': 2025, 'full_effect_year': 2025, 'end_year': 2026, 'last_year_share': 36},
     'last_year_share'),
    ({'start_year': 2025, 'full_effect_year': 2025, 'half_life': 0}, 'half_life'),
    ({'start_year': 2025, 'full_effect_year': 2025, 'first_year_share': 0}, 'first_year_share'),
    ({'start_year': 2025, 'full_effect_year': 2025, 'first_year_share': 75}, 'first_year_share'),
])
def test_impossible_timing_is_refused(ramp, match):
    with pytest.raises(ValueError, match=match):
        Driver.from_dict(_drv(ramp=ramp))


# ---------- one-off items ----------

def test_a_one_off_exists_in_its_own_year_only():
    # Manufacturing: 10 units × 100 kg = 1,00 t, added (ΔA +1), territorial only.
    m = _model(_drv(name='Tillverkning', kind='engång', year=2025, a0=10, ef0=100,
                    delta_a=1.0, g_a=0.5, terr=1.0, cons=0.0, overlap=0.0))
    assert _net(m, 2025) == approx(-1.0)
    assert all(_net(m, y) == 0 for y in range(2026, 2031))
    assert compute(m)['med']['total']['cumulative_net'] == approx(-1.0)


def test_an_unknown_kind_is_refused_rather_than_summed_every_year():
    with pytest.raises(ValueError, match='drivartyp'):
        Driver.from_dict(_drv(kind='en gång'))


def test_a_one_off_after_the_target_year_is_warned_about():
    m = _model(_drv(), _drv(name='Batteri', kind='engång', year=2032, a0=1, ef0=1000,
                            delta_a=1.0, cons=0.0, overlap=0.0))
    assert any('engångsposten Batteri (2032) ligger efter målåret 2030' in w
               for w in sanity_warnings(compute(m), m))


# ---------- the follow-up sums ----------

def test_follow_up_averages_over_the_cumulative_years():
    r = compute(_model())  # 2025-2030, 0,40 every year
    t = r['med']['total']
    assert t['avg_window'] == (2025, 2030)
    assert t['avg_net'] == approx(t['cumulative_net'] / 6)
    assert r['headline']['net'] == approx(0.4)


def test_potential_keeps_the_plan_window():
    r = compute(_model(mode=POTENTIAL))
    t = r['med']['total']
    assert t['avg_window'] == (2026, 2030)
    assert t['avg_net'] == t['avg_2026_2030_net']
    assert 'realised_net' not in t and 'allocation' not in r


def test_realised_and_remaining_add_up_and_split_at_the_follow_up_year():
    r = compute(_model(followup_year=2026))
    for sc in ('min', 'med', 'max'):
        t = r[sc]['total']
        assert t['realised_net'] + t['remaining_net'] == approx(t['cumulative_net'])
    assert r['med']['total']['realised_net'] == approx(0.80)   # 2025 + 2026
    assert r['med']['total']['remaining_net'] == approx(1.60)  # 2027-2030


def test_follow_up_year_defaults_to_the_last_start_year():
    late = _drv(name='Senare', ramp={'start_year': 2026, 'full_effect_year': 2026})
    assert compute(_model(_drv(), late))['followup_year'] == 2026


def test_follow_up_year_defaults_to_the_last_grant_year_and_skips_planned_one_offs():
    planned = _drv(name='Planerad', kind='engång', year=2029, delta_a=1.0)
    assert compute(_model(_drv(), planned))['followup_year'] == 2025
    m = _model(_drv(), grants=[{'year': 2024, 'amount': 1}, {'year': 2026, 'amount': 1}])
    assert compute(m)['followup_year'] == 2026


def test_grants_share_untagged_drivers_by_money_and_tagged_ones_go_whole():
    tagged = _drv(name='Köpt 2025', grant_year=2025)
    m = _model(_drv(), tagged, grants=[{'year': 2024, 'amount': 100},
                                       {'year': 2025, 'amount': 300}])
    r = compute(m)
    rows = {row['year']: row for row in r['allocation']}
    one = r['med']['per_driver'][0]['cumulative_net']   # 2,40 each
    assert rows[2024]['share'] == approx(0.25)
    assert rows[2024]['med'] == approx(one * 0.25)
    assert rows[2025]['med'] == approx(one * 0.75 + one)
    for sc in ('min', 'med', 'max'):
        assert sum(row[sc] for row in r['allocation']) == approx(r[sc]['total']['cumulative_net'])


def test_without_grants_untagged_benefit_is_left_unallocated():
    m = _model(_drv(), _drv(name='Köpt 2024', grant_year=2024),
               _drv(name='Köpt 2025', grant_year=2025))
    rows = {row['year']: row for row in compute(m)['allocation']}
    assert set(rows) == {2024, 2025, None}


def test_one_grant_year_and_no_grant_rows_is_no_allocation():
    m = _model(_drv(), _drv(name='Köpt 2025', grant_year=2025))
    assert compute(m)['allocation'] == []


@pytest.mark.parametrize('bad', [[{'year': 2024, 'amount': -1}],
                                 [{'year': 2024, 'amount': 0}],
                                 [{'year': 2024}]])
def test_grant_rows_that_cannot_divide_the_benefit_are_refused(bad):
    with pytest.raises(ValueError):
        grants_of(bad)


def test_two_grant_rows_for_one_year_become_one():
    # Shown otherwise as the first row's kronor next to the last row's share.
    assert grants_of([{'year': 2025, 'amount': 100}, {'year': 2025, 'amount': 300},
                      {'year': 2026, 'amount': 100}]) == grants_of(
        [{'year': 2025, 'amount': 400}, {'year': 2026, 'amount': 100}])


def test_a_grant_year_tag_with_no_grant_row_is_warned_about():
    m = _model(_drv(), _drv(name='Köpt 2022', grant_year=2022),
               grants=[{'year': 2024, 'amount': 100}])
    assert any('bidragsår 2022, men det året finns inte' in w
               for w in sanity_warnings(compute(m), m))


def test_follow_up_text_says_realised_remaining_and_per_grant_year():
    m = _model(followup_year=2026, grants=[{'year': 2024, 'amount': 100},
                                           {'year': 2025, 'amount': 300}])
    text = render_markdown(m, compute(m))
    assert 'Realiserat 2025–2026: 0,4 / 0,8 / 1,2' in text
    assert 'Återstår 2027–2030:' in text
    assert 'Bidragsår 2024 (100 kr, 25 % av beloppet):' in text
    assert 'samma år som det kumulativa talet' in text


def test_no_window_note_in_follow_up_even_past_2030():
    m = _model(_drv(), target_year=2033)
    m.target_year = 2033
    assert not any('medel effekt/år räknas över' in w for w in sanity_warnings(compute(m), m))


# ---------- bearing assumptions ----------

def _kallor(origin):
    return {k: {'ursprung': origin, 'kalla': 'Rapport X' if origin == 'extern' else '',
                'not': 'skäl'}
            for k in ('a0', 'ef0', 'g_a', 'g_ef', 'delta_a', 'delta_ef', 'attribution')}


def test_an_unsourced_bearing_assumption_is_flagged_and_a_sourced_one_is_not():
    for origin, flagged in (('antagande', True), ('extern', False)):
        m = _model(_drv(kallor=_kallor(origin)))
        b = bearing(m, compute(m))
        hit = [u for u in b['unsourced'] if u['field'] == 'delta_a']
        assert bool(hit) is flagged, origin
        text = render_markdown(m, compute(m))
        assert ('OBS: bärande antagande utan källa: Bilresor, ΔA' in text) is flagged


def test_the_joint_extremes_flag_names_what_one_assumption_gives_alone():
    m = _model(_drv(attribution={'min': 0.5, 'med': 0.7, 'max': 0.9}, kallor=_kallor('extern')))
    r = compute(m)
    b = bearing(m, r)
    j = b['joint_extremes']
    assert j['n'] == 2
    assert j['max'] == approx(r['max']['total']['cumulative_net'])
    # ΔA alone at max: 6 years × 2,00 × 30 % × 0,7 = 2,52; attribution alone:
    # 6 × 0,40 × 0,9 = 2,16.
    assert j['best_single'] == approx(2.52)
    assert 'förutsätter att alla 2 antaganden med spann' in render_markdown(m, r)


def test_a_single_band_has_no_joint_extremes():
    m = _model(_drv(kallor=_kallor('extern')))
    assert bearing(m, compute(m))['joint_extremes'] is None


def test_bearing_is_measured_against_the_gross_effect_not_a_near_zero_net():
    # Gain 6 × 0,40 = 2,40 t against a 2,30 t purchase: net 0,10. A quarter of
    # the net (0,025) would flag the attribution's 0,24 swing; a quarter of the
    # gross 4,70 (1,175) flags only ΔA, whose swing is 6 × 2,00 × 20 % = 2,40.
    gain = _drv(attribution={'min': 0.9, 'med': 0.95, 'max': 1.0}, kallor=_kallor('antagande'))
    cost = _drv(name='Inköp', kind='engång', year=2025, a0=23, ef0=100, delta_a=1.0,
                cons=0.0, overlap=0.0, kallor=_kallor('extern'))
    m = _model(gain, cost)
    flagged = {u['field'] for u in bearing(m, compute(m))['unsourced'] if 'swing' in u}
    assert flagged == {'delta_a'}


def test_a_sourced_decay_is_not_flagged_as_unsourced():
    ramp = {'start_year': 2025, 'full_effect_year': 2025,
            'half_life': {'min': 1, 'med': 2, 'max': 4}}
    for extra, flagged in (({}, True),
                           ({'half_life': {'ursprung': 'extern', 'kalla': 'Studie Y'}}, False)):
        m = _model(_drv(ramp=ramp, kallor=_kallor('extern') | extra))
        hit = [u for u in bearing(m, compute(m))['unsourced'] if u['field'] == 'half_life']
        assert bool(hit) is flagged


def test_a_fault_in_the_bearing_check_does_not_lose_the_result(monkeypatch):
    import caia.calc.engine as E

    def boom(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(E, 'bearing', boom)
    m = _model()
    text = render_markdown(m, compute(m))
    assert 'Bärande antaganden' not in text and 'Realiserat' in text


# ---------- källmarkering and the appendix ----------

def test_inputs_never_print_exponent_form():
    m = _model(_drv(delta_a={'min': 15.2, 'med': 6.0, 'max': 2.64}, a0=0.00001))
    text = render_markdown(m, compute(m))
    assert 'e+0' not in text and 'e-0' not in text
    assert 'ΔA 600 % (1 520 till 264)' in text


def test_attribution_is_source_checked_only_when_set():
    plain = granska(_model(_drv(kallor=_kallor('antagande'))))
    assert 'attribution' not in {b.falt for b in plain}
    set_ = granska(_model(_drv(attribution=0.6, kallor=_kallor('antagande'))))
    assert 'attribution' in {b.falt for b in set_}


def test_appendix_shows_attribution_only_when_it_is_used():
    plain = _model()
    assert 'Attribution |' not in render_appendix(plain, compute(plain))
    m = _model(_drv(attribution=0.5))
    text = render_appendix(m, compute(m))
    assert 'ΔE = (E_BAU − E_åtgärd) × attribution' in text
    assert '| 2026 | 1 000 | 2 | 2,00 | 100 % | -20 % | 0 % | 1,60 | 50 % | 0,20 |' in text


def test_appendix_follow_up_sums_realised_and_remaining():
    m = _model(followup_year=2026)
    text = render_appendix(m, compute(m))
    assert '- Scenario medel, realiserat 2025–2026: 0,40 + 0,40 = 0,80 ton CO2e.' in text
    assert '- Scenario medel, återstår 2027–2030:' in text


# ---------- the routes carry the mode ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


@pytest.mark.parametrize('path, name', [
    ('/api/intake', 'run_intake'), ('/api/emap', 'run_emap'),
    ('/api/baslinje', 'run_baslinje_bau'), ('/api/evidens', 'run_evidens'),
    ('/api/qa', 'run_cove_qa'), ('/api/rapport', 'run_rapport'),
])
def test_every_step_gets_the_mode(client, monkeypatch, path, name):
    seen = []
    ret = {'status': 'clarifying', 'message': 'x'} if name == 'run_intake' else 'x'
    monkeypatch.setattr(A, name, lambda *a, mode=None, **k: seen.append(mode) or ret)
    history = [{'role': 'user', 'content': 'Testcyklisterna'}]
    for mode in (None, 'uppfoljning'):
        body = {'history': history} | ({'mode': mode} if mode else {})
        assert client.post(path, json=body).status_code == 200
    assert seen == [POTENTIAL, UPPFOLJNING]


def test_an_unknown_mode_is_a_bad_request(client, monkeypatch):
    monkeypatch.setattr(A, 'run_emap', lambda *a, **k: 'x')
    r = client.post('/api/emap', json={'history': [], 'mode': 'efterhand'})
    assert r.status_code == 400


def test_the_kalkyl_route_reports_the_follow_up(client, monkeypatch):
    seen = []
    extracted = {'action_name': 'x', 'target_year': 2030, 'followup_year': 2025,
                 'drivers': [_drv()]}
    monkeypatch.setattr(A, 'run_kalkyl_extract',
                        lambda h, mode=None, **_: seen.append(mode) or extracted)
    body = client.post('/api/kalkyl', json={'history': [], 'mode': 'uppfoljning'}).get_json()
    assert seen == [UPPFOLJNING]
    assert body['deterministic'] is True
    span = body['span']
    assert span['mode'] == UPPFOLJNING and span['window'] == [2025, 2030]
    assert span['followup']['year'] == 2025
    assert span['followup']['realised']['med'] == approx(0.4)
    assert span['followup']['remaining']['med'] == approx(2.0)
    assert 'Realiserat 2025: 0,2 / 0,4 / 0,6' in body['output']
