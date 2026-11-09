"""Källmarkering: every input number carries a typed origin, checked against
the parameter library, and shown as its own section in the report.

The two failures this suite exists to catch:
  * a number with no source that the report shows as if it had one, and
  * a number that claims the parameter library for a value the library does
    not hold.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia import kallmarkering as KM  # noqa: E402
from caia import kommun  # noqa: E402
from caia.calc import CalcModel  # noqa: E402
from caia.calc.schema import KALLFALT, Ursprung, kallor_of  # noqa: E402
from caia.web import app as A  # noqa: E402

pytestmark = pytest.mark.karlstad  # reads Karlstad's kommunprofil


@pytest.fixture(autouse=True)
def karlstad():
    """Every test runs on a known profile and leaves the previous one in place."""
    before = kommun._active
    kommun.set_active(kommun.bundled('karlstad'))
    yield
    kommun.set_active(before)


def _driver(**over) -> dict:
    d = {
        'name': 'Tjänstebilar', 'baseline_year': 2023,
        'a0': 3_000_000.0, 'a0_unit': 'km/år', 'ef0': 0.15, 'ef0_unit': 'kg CO2e/km',
        'g_a': {'min': -0.02, 'med': -0.05, 'max': -0.08}, 'g_ef': 0.0,
        'delta_a': 0.0, 'delta_ef': {'min': -0.15, 'med': -0.38, 'max': -0.85},
        'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
        'ramp': {'start_year': 2026, 'full_effect_year': 2030},
        'kallor': {
            'a0': {'ursprung': 'antagande', 'not': '200 bilar × 15 000 km'},
            'ef0': {'ursprung': 'parameterbibliotek', 'parametrar': ['EF_passenger_car_avg']},
            'g_a': {'ursprung': 'extern', 'kalla': 'Trafikverket 2024'},
            'g_ef': {'ursprung': 'antagande', 'not': 'ingen trend'},
            'delta_a': {'ursprung': 'antagande', 'not': 'effekten ligger i delta_ef'},
            'delta_ef': {'ursprung': 'antagande', 'not': 'adoption × EF-skillnad'},
        },
    }
    for k, v in over.items():
        if k == 'kallor':
            d['kallor'] = {**d['kallor'], **v}
        else:
            d[k] = v
    return d


def _model(*drivers) -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                'drivers': list(drivers) or [_driver()]})


def _one(falt: str, **over) -> KM.Bedomning:
    return next(b for b in KM.granska(_model(_driver(**over))) if b.falt == falt)


# ---------- the typed field ----------

def test_every_input_number_gets_exactly_one_assessment():
    b = KM.granska(_model(_driver(), _driver(name='Laddplatser')))
    assert [x.falt for x in b] == list(KALLFALT) * 2
    assert [x.drivare for x in b] == ['Tjänstebilar'] * 6 + ['Laddplatser'] * 6


def test_a_fully_sourced_driver_has_nothing_to_check():
    b = KM.granska(_model())
    assert all(x.ok for x in b), [(x.falt, x.problem) for x in b if not x.ok]
    assert {x.ursprung for x in b} == {Ursprung.ANTAGANDE, Ursprung.PARAMETERBIBLIOTEK,
                                       Ursprung.EXTERN}


def test_origin_is_an_enum_not_a_string_match():
    k = kallor_of({'a0': {'ursprung': 'Parameterbiblioteket', 'parametrar': 'A, B'}})['a0']
    assert k.ursprung is Ursprung.PARAMETERBIBLIOTEK
    assert k.parametrar == ('A', 'B')
    # A label that is none of the four is kept as written but has no origin.
    k = kallor_of({'a0': {'ursprung': 'typ biblioteket kanske'}})['a0']
    assert k.ursprung is None and k.angivet == 'typ biblioteket kanske'
    assert kallor_of({'a0': 'antagande'})['a0'].ursprung is Ursprung.ANTAGANDE


@pytest.mark.parametrize('junk', [None, 'antagande', [1, 2], 42,
                                  {'a0': 17}, {'a0': [None]}, {'ef0': {'parametrar': 5}}])
def test_malformed_sources_never_stop_the_calc(junk):
    d = _driver()
    d['kallor'] = junk
    m = CalcModel.from_dict({'action_name': 'x', 'drivers': [d]})
    assert len(KM.granska(m)) == 6


# ---------- a number without a source ----------

@pytest.mark.parametrize('falt', ['a0', 'ef0', 'g_a', 'delta_ef'])
def test_a_number_without_a_source_is_flagged(falt):
    d = _driver()
    del d['kallor'][falt]
    b = next(x for x in KM.granska(_model(d)) if x.falt == falt)
    assert not b.ok and b.ursprung is None and 'saknar källa' in b.problem
    md = KM.render(KM.granska(_model(d)))
    assert '### Kontrollera först' in md
    row = next(line for line in md.splitlines()
               if line.startswith('| Tjänstebilar | ' + KM.FALTNAMN[falt] + ' |'))
    assert '| Saknas |' in row


def test_a_driver_with_no_sources_at_all_is_six_flags():
    d = _driver()
    del d['kallor']
    b = KM.granska(_model(d))
    # g_ef and delta_a are 0 in this driver: the schema's no-change default.
    flagged = {x.falt for x in b if not x.ok}
    assert flagged == {'a0', 'ef0', 'g_a', 'delta_ef'}


def test_an_unsourced_zero_is_labelled_as_the_default_it_is():
    d = _driver()
    del d['kallor']['g_ef']
    b = next(x for x in KM.granska(_model(d)) if x.falt == 'g_ef')
    assert b.ok and b.ursprung is Ursprung.ANTAGANDE
    assert 'räknar med 0' in b.underlag


def test_an_unknown_origin_label_is_flagged_and_shown():
    b = _one('ef0', kallor={'ef0': {'ursprung': 'intuition'}})
    assert not b.ok and 'intuition' in b.problem


# ---------- a library claim for a value the library does not hold ----------

def test_library_claim_for_an_id_that_does_not_exist_is_flagged():
    b = _one('ef0', kallor={'ef0': {'ursprung': 'parameterbibliotek',
                                    'parametrar': ['EF_passenger_car_average']}})
    assert not b.ok and 'finns inte i parameterbiblioteket' in b.problem


def test_library_claim_without_an_id_is_flagged():
    b = _one('ef0', kallor={'ef0': {'ursprung': 'parameterbibliotek'}})
    assert not b.ok


@pytest.mark.parametrize('ef0,ok', [(0.15, True), (0.12, True), (0.18, True),
                                    (0.5, False), (0.05, False)])
def test_library_claim_must_hold_the_value(ef0, ok):
    # EF_passenger_car_avg is 0,12–0,18 kg CO2/km in the library.
    b = _one('ef0', ef0=ef0)
    assert b.ok is ok, b.problem
    if not ok:
        assert 'står inte i biblioteket' in b.problem


@pytest.mark.parametrize('ef0,ok', [(0.010, True), (0.05, False)])
def test_library_value_is_compared_across_a_unit_step(ef0, ok):
    # 10 g CO2e/kWh in the library, kg CO2e/kWh in the calc.
    b = _one('ef0', ef0=ef0, ef0_unit='kg CO2e/kWh', kallor={'ef0': {
        'ursprung': 'parameterbibliotek', 'parametrar': ['EF_district_heat_Karlstad_2024']}})
    assert b.ok is ok, b.problem


@pytest.mark.parametrize('ef0,unit,ok', [
    (150.0, 'kg CO2e/km', False),   # x1000 slip: 150 kg/km is a lorry fleet, not a car
    (0.00015, 'kg CO2e/km', False),  # /1000 slip
    (15.0, 'kg CO2e/km', False),    # x100 slip
    (0.15, 'kg CO2e/km', True),
    (150.0, 'g CO2e/km', True),     # the same value, written in grams
])
def test_a_unit_slip_is_not_certified_as_the_library_value(ef0, unit, ok):
    """The check used to try x1, x100, x0.01, x1000 and x0.001 on every row,
    so an emission factor a thousand times too large "held" the library row
    EF_passenger_car_avg (0,12–0,18 kg CO2/km) and was reported as sourced."""
    b = _one('ef0', ef0=ef0, ef0_unit=unit)
    assert b.ok is ok, (ef0, unit, b.problem)


@pytest.mark.parametrize('ef0,unit,ok', [
    (0.05, 'kg CO2e/kWh', True),    # 50 g/kWh, inside 40–60
    (50.0, 'kg CO2e/MWh', True),    # the same per MWh
    (50.0, 'kg CO2e/kWh', False),   # a thousand times the library value
])
def test_energy_denominators_are_converted(ef0, unit, ok):
    b = _one('ef0', ef0=ef0, ef0_unit=unit, kallor={'ef0': {
        'ursprung': 'parameterbibliotek', 'parametrar': ['EF_el_SE_consumption_2020s']}})
    assert b.ok is ok, (ef0, unit, b.problem)


@pytest.mark.parametrize('delta,ok', [(-0.12, True), (-0.30, False)])
def test_library_percent_is_compared_as_a_share(delta, ok):
    # KOMM_soft_max_effect_car_km is 10–15 % in the library.
    b = _one('delta_a', delta_a=delta, kallor={'delta_a': {
        'ursprung': 'parameterbibliotek', 'parametrar': ['KOMM_soft_max_effect_car_km']}})
    assert b.ok is ok, b.problem


def test_a_data_file_row_is_not_compared_with_its_fallback_range():
    # HEAT_energy_use_percap_res reads its value from a data file; 8000–12000
    # is only the standard it falls back on.
    b = _one('a0', a0=20000.0, kallor={'a0': {
        'ursprung': 'parameterbibliotek', 'parametrar': ['HEAT_energy_use_percap_res']}})
    assert b.ok and 'jämförs inte' in b.underlag


# ---------- a data-file row shows a number and plain words, never LOOKUP ----------

TECHNICAL = re.compile(r'LOOKUP|DATA_[A-Z]')


def _datafil_rows() -> dict[str, dict]:
    from caia.data.parameters import parameter_view
    return {r['id']: r for s in parameter_view() for r in s['rows']
            if r['provenance'] == 'datafil'}


def _table_cells(md: str) -> list[str]:
    rows = [line for line in md.splitlines() if line.startswith('| ') and '---' not in line]
    return [c for line in rows[1:] for c in re.split(r'(?<!\\)\|', line)[1:-1]]


def test_every_data_file_row_shows_what_the_parameter_view_shows():
    """Henric 2026-10-13: Talens ursprung printed the LOOKUP expression in the
    Underlag column. It now prints the parameter view's number and line, read
    through parameter_view(), so the expression is interpreted in one place."""
    rows = _datafil_rows()
    assert len(rows) >= 10
    for pid, row in rows.items():
        b = _one('a0', kallor={'a0': {'ursprung': 'parameterbibliotek', 'parametrar': [pid]}})
        assert b.ok, (pid, b.problem)
        assert not TECHNICAL.search(b.underlag), b.underlag
        assert row['value_display'] in b.underlag
        assert row['value_note'].rstrip('.') in b.underlag
        # The expression itself stays what the source check and prompts read.
        assert row['value_used'].lstrip().upper().startswith('LOOKUP')


def test_a_data_file_number_is_the_one_in_the_file():
    # Read by hand: Alla;Alla, 2023 = 224950,7472 in the emissions export.
    b = _one('a0', kallor={'a0': {'ursprung': 'parameterbibliotek',
                                  'parametrar': ['BASE_co2_total_territorial']}})
    assert '224 951 ton CO2e/år' in b.underlag
    assert 'Totala utsläpp per sektor och år' in b.underlag


@pytest.mark.parametrize('pid', ['HEAT_share_district_heating_res', 'GOODS_secondhand_share',
                                 'MAT_meat_total_kg_percap_SE'])
def test_an_expression_that_is_no_single_cell_gets_words_not_a_number(pid):
    b = _one('a0', kallor={'a0': {'ursprung': 'kommundata', 'parametrar': [pid]}})
    assert b.ok, b.problem
    assert f'{pid} (ur datafil: Läses ur datafilen vid varje analys.' in b.underlag
    assert not TECHNICAL.search(b.underlag), b.underlag
    # No unit after the words: there is no number for it to belong to.
    assert _datafil_rows()[pid]['enhet'] not in b.underlag.split('analys', 1)[0]


def test_a_reference_to_a_data_file_names_the_file_not_the_register_key():
    b = _one('a0', kallor={'a0': {'ursprung': 'kommundata',
                                  'parametrar': ['DATA_EMISSIONS_TOTAL']}})
    assert b.ok and b.underlag == 'Datafil: Totala utsläpp per sektor och år (SMHI/RUS)'


def test_a_row_without_the_view_keys_never_falls_back_to_the_expression():
    from caia.data.parameters import parse_parameter_library
    plain = {r['id']: r for s in parse_parameter_library() for r in s['rows']}
    text = KM._row_text('BASE_co2_total_territorial', plain['BASE_co2_total_territorial'])
    assert not TECHNICAL.search(text)
    assert 'Läses ur datafilen vid varje analys' in text


def test_no_cell_of_the_section_holds_an_expression():
    """A report whose numbers refer to data-file parameters, every way the
    extraction can name them: one library row, several, kommundata."""
    rows = sorted(_datafil_rows())
    d = _driver(kallor={
        'a0': {'ursprung': 'parameterbibliotek', 'parametrar': rows[:1]},
        'ef0': {'ursprung': 'kommundata', 'parametrar': rows[1:3] + ['DATA_CITIZEN_SURVEY']},
        'g_a': {'ursprung': 'parameterbibliotek', 'parametrar': rows[3:6],
                'not': 'summa av tre kategorier'},
    })
    md = KM.render(KM.granska(_model(d)))
    cells = _table_cells(md)
    assert len(cells) == 6 * 5
    bad = [c for c in cells if TECHNICAL.search(c)]
    assert not bad, bad


def test_a_derived_number_must_show_its_derivation():
    two = ['BASE_pop', 'TR_vkt_percap_passenger_car']
    b = _one('a0', kallor={'a0': {'ursprung': 'parameterbibliotek', 'parametrar': two}})
    assert not b.ok and 'uträkningen saknas' in b.problem
    b = _one('a0', kallor={'a0': {'ursprung': 'parameterbibliotek', 'parametrar': two,
                                  'not': 'invånare × km per person'}})
    assert b.ok and 'invånare × km per person' in b.underlag


# ---------- kommundata ----------

@pytest.mark.parametrize('refs,a0,ok,why', [
    (['BASE_pop'], 97233.0, True, ''),
    (['BASE_pop'], 150000.0, False, 'står inte i kommunens data'),
    (['EF_passenger_car_avg'], 97233.0, False, 'bara ett schablonvärde'),
    (['DATA_EMISSIONS_TOTAL'], 97233.0, True, ''),
    (['DATA_CITIZEN_SURVEY'], 97233.0, True, ''),       # prefix of ..._2024
    (['DATA_TRAVEL_SURVEY'], 97233.0, False, 'läses inte'),  # registered, never read
    (['DATA_NOPE'], 97233.0, False, 'varken i biblioteket'),
    (['DATA'], 97233.0, False, 'varken i biblioteket'),        # a bare prefix is no file
    (['DATA_CITIZEN'], 97233.0, False, 'varken i biblioteket'),
    ([], 97233.0, False, 'inget lokalt värde'),
])
def test_kommundata_must_exist_in_the_profile(refs, a0, ok, why):
    b = _one('a0', a0=a0, kallor={'a0': {'ursprung': 'kommundata', 'parametrar': refs}})
    assert b.ok is ok, b.problem
    assert why in b.problem


def test_kommundata_is_compared_with_the_local_value_not_the_national_range():
    # TR_share_evs_new_sales: national 30–40 %, Karlstad ~30 %. 38 % is in the
    # library, but not as the municipality's own number.
    claim = {'a0': {'ursprung': 'kommundata', 'parametrar': ['TR_share_evs_new_sales']}}
    assert not _one('a0', a0=0.38, kallor=claim).ok
    assert _one('a0', a0=0.30, kallor=claim).ok
    lib_claim = {'a0': {'ursprung': 'parameterbibliotek',
                        'parametrar': ['TR_share_evs_new_sales']}}
    assert _one('a0', a0=0.38, kallor=lib_claim).ok


def test_rvu_car_share_is_kommundata_at_the_municipal_level():
    # RVU 2023: 53 % for the municipality (figur 18), 47 % for the tätort
    # (tabell 14, what PAC uses for a plan). CAIA's library holds the first.
    claim = {'a0': {'ursprung': 'kommundata', 'parametrar': ['TR_mode_share_car']}}
    assert _one('a0', a0=0.53, kallor=claim).ok
    b = _one('a0', a0=0.47, kallor=claim)
    assert not b.ok and 'står inte i kommunens data' in b.problem


def test_rvu_gap_is_not_kommundata():
    claim = {'a0': {'ursprung': 'kommundata',
                    'parametrar': ['TR_vkt_percap_passenger_car']}}
    b = _one('a0', a0=8000.0, kallor=claim)
    assert not b.ok and 'bara ett schablonvärde' in b.problem


def test_kommundata_in_a_profile_without_local_data_is_flagged():
    kommun.set_active(kommun.bundled('exempel'))
    b = _one('a0', a0=97233.0,
             kallor={'a0': {'ursprung': 'kommundata', 'parametrar': ['BASE_pop']}})
    assert not b.ok


# ---------- extern ----------

def test_extern_needs_a_named_source():
    assert not _one('g_a', kallor={'g_a': {'ursprung': 'extern'}}).ok
    b = _one('g_a', kallor={'g_a': {'ursprung': 'extern', 'kalla': 'SCB 2024'}})
    assert b.ok and 'SCB 2024' in b.underlag


# ---------- the report section ----------

def test_section_counts_add_up_and_problems_come_first():
    d = _driver(ef0=0.5)  # claims EF_passenger_car_avg, holds 0.5
    md = KM.render(KM.granska(_model(d)))
    assert md.startswith(KM.RUBRIK)
    c = KM.summera(KM.granska(_model(d)))
    assert c['kontrollera'] == 1
    assert sum(c[u.value] for u in Ursprung) + c['kontrollera'] == c['totalt'] == 6
    assert md.index('### Kontrollera först') < md.index('| Drivare |')
    assert 'Kontrollera (parameterbiblioteket)' in md


def test_section_without_problems_has_no_check_list():
    md = KM.render(KM.granska(_model()))
    assert '### Kontrollera först' not in md
    assert 'behöver kontrolleras' not in md


def test_a_pipe_in_model_text_cannot_break_the_table():
    d = _driver(kallor={'g_a': {'ursprung': 'extern', 'kalla': 'A | B\nC'}})
    md = KM.render(KM.granska(_model(d)))
    row = next(line for line in md.splitlines() if 'Trend aktivitet' in line)
    assert 'A \\| B C' in row
    assert len(re.findall(r'(?<!\\)\|', row)) == 6


def test_small_emission_factors_keep_their_digits():
    assert KM._num(0.012) == '0,012'
    assert KM._num(3_000_000) == '3 000 000'
    assert KM._num(-0.385 * 100) == '-38,5'


# ---------- extraction prompt ----------

def _captured_extract_system(monkeypatch) -> str:
    from caia.agents import kalkyl_extract as K
    seen = {}

    def fake(step, system, messages, max_output, mode=None, timeout_s=None):
        seen['system'] = system
        return json.dumps({'drivers': [_driver()]})
    monkeypatch.setattr(K, 'complete', fake)
    K.run_kalkyl_extract([{'role': 'user', 'content': 'x'}])
    return seen['system']


def test_extraction_asks_for_a_typed_origin_per_number(monkeypatch):
    system = _captured_extract_system(monkeypatch)
    assert '"kallor"' in system
    for u in Ursprung:
        assert f'"{u.value}"' in system
    for falt in KALLFALT:
        assert falt in system.split('KÄLLOR', 1)[1]
    assert '<parameter_ids>' in system and '- EF_passenger_car_avg (' in system
    assert '- BASE_pop:' in system.split('<kommundata>', 1)[1].split('</kommundata>')[0]


def test_extraction_in_a_profile_without_data_is_told_so(monkeypatch):
    kommun.set_active(kommun.bundled('exempel'))
    system = _captured_extract_system(monkeypatch)
    block = system.split('<kommundata>', 1)[1].split('</kommundata>')[0]
    assert 'ingen egen data' in block
    assert 'Karlstad' not in system


# ---------- /api/kalkyl ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'run_kalkyl', lambda h, data_context=None, **_: 'LLM-FALLBACK')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    return A.app.test_client()


def test_kalkyl_returns_the_section_and_the_typed_rows(client, monkeypatch):
    extracted = {'action_name': 'x', 'target_year': 2030, 'drivers': [_driver(ef0=0.5)]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True
    assert body['kallmarkering_md'].startswith(KM.RUBRIK)
    rows = body['kallmarkering']
    assert len(rows) == 6
    ef0 = next(r for r in rows if r['falt'] == 'ef0')
    assert ef0['ok'] is False and ef0['ursprung'] == 'parameterbibliotek'
    # The calc output itself is unchanged: the section travels beside it.
    assert KM.RUBRIK not in body['output']


def test_a_fault_in_the_source_check_keeps_the_computed_result(client, monkeypatch):
    extracted = {'action_name': 'x', 'target_year': 2030, 'drivers': [_driver()]}
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: extracted)

    def boom(model, history=None):
        raise RuntimeError('library unreadable')
    monkeypatch.setattr(A, 'kallmarkering', boom)
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True and 'LLM-FALLBACK' not in body['output']
    # Not SAKNAS: that text says the language model did the math, which it
    # did not here, and the note is saved into the report.
    assert body['kallmarkering_md'] == KM.KONTROLL_FEL
    assert 'språkmodellen' not in body['kallmarkering_md']


def test_the_llm_fallback_says_the_sources_are_missing(client, monkeypatch):
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda h, **_: None)
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is False
    assert body['kallmarkering_md'] == KM.SAKNAS and body['kallmarkering'] is None


# ---------- the page: the section reaches the report ----------

def _inline_script() -> str:
    from flask import render_template_string
    with A.app.test_request_context('/'):
        html = render_template_string(
            A.HTML_TEMPLATE, has_supabase=False, supabase_url='', supabase_anon_key='',
            **A._page_context())
    return re.findall(r'<script>(.*?)</script>', html, re.DOTALL)[-1]


def _js_function(js: str, name: str) -> str:
    start = js.index(f'function {name}(')
    return js[start:js.index('\n}\n', start) + 2]


@pytest.mark.node
def test_report_gets_the_section_appended_and_kept_without_one():
    fn = _js_function(_inline_script(), 'withKallmarkering')
    probe = fn + (
        "\nconsole.log(JSON.stringify(["
        "withKallmarkering('# Rapport\\n\\ntext\\n\\n', '## Talens ursprung\\n\\nx'),"
        "withKallmarkering('# Rapport', null),"
        "withKallmarkering('# Rapport', '')]));")
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(probe)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    joined, none, empty = json.loads(out.stdout)
    assert joined == '# Rapport\n\ntext\n\n## Talens ursprung\n\nx\n'
    assert none == '# Rapport' and empty == '# Rapport'


def test_report_saves_and_downloads_with_the_section():
    js = _inline_script()
    assert 'state.kallmarkeringMd = data.kallmarkering_md' in js
    stages = _js_function(js, 'runStages')
    block = stages[stages.index("if (step === 'rapport')"):]
    block = block[:block.index('}\n')]
    # The appended report is what is stored, shown and saved; downloadReport
    # and finishReport both read state.reportMarkdown / their argument.
    assert 'withKallmarkering(data.output, state.kallmarkeringMd)' in block
    assert 'state.reportMarkdown = report' in block
    assert 'finishReport(report)' in block
    reset = _js_function(js, 'resetAll')
    assert 'kallmarkeringMd:null' in reset
