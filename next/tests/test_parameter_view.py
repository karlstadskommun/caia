"""The parameter view: what a reader sees in the name and value columns.

The library names a parameter by an ID (BASE_pop) and gives the value of a
data-file row as an expression (LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp",
2023) / BASE_pop). Neither reads as a name or as a value. The view shows the
description as the name, and for a data-file row the number in the file with a
line saying where it came from.

A number on that page is a claim about the data file, so the expected values
below are read by hand from the files, not through the loader under test.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_parameter_view.py -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from caia import kommun  # noqa: E402
from caia.data import parameters as P  # noqa: E402
from caia.web import app as A  # noqa: E402
from test_client_ui import _between, _node  # noqa: E402
from test_report_row import _inline_script  # noqa: E402
from conftest import HAS_KK  # noqa: E402

# Read by hand in kommuner/karlstad/data/ on 2026-10-13:
#   Kommunrapport_karlstad_vaxthusgaser_totalt.csv, row Alla;Alla, column 2023: 224950,7472
#   energianvandning_bostader_karlstad.csv, row "Per person": 6.67 (MWh)
#   BASE_pop in the library: 97 233, so 224950.7472 / 97233 = 2.3135
ONE_CELL = {
    'BASE_co2_total_territorial': '224 951',
    'BASE_co2_percap_territorial': '2,31',
    'HEAT_energy_use_percap_res': '6 670',
}
# The CONS_ rows point at one cell each in Konsumtionskompassen's export
# (fotavtryck-per-konsumtionskategori.json): (coicop, column). Its numbers are
# not written here. The file's licence (CC BY-NC-ND 4.0) keeps it out of the
# public release, so the expected value is read from the file with json, not
# through the loader under test; without the file these rows are standard
# values (conftest.KK_FILES).
FROM_KK = {
    'CONS_dir_vehicle_CO2e_pc_Karlstad': ('07.D', 'Karlstad'),
    'CONS_air_travel_CO2e_pc_Karlstad': ('07.3.3', 'Karlstad'),
    'CONS_district_heat_CO2e_pc_Karlstad': ('04.5.5', 'Karlstad'),
    'CONS_dairy_eggs_CO2e_pc_Karlstad': ('01.1.4', 'Karlstad'),
    'CONS_housing_imputed_rent_CO2e_pc_Karlstad': ('04.2.1', 'Karlstad'),
    'CONS_dir_vehicle_intensity_CO2e_per100sek': ('07.D', 'per100sek'),
    'CONS_air_travel_intensity_CO2e_per100sek': ('07.3.3', 'per100sek'),
    'CONS_district_heat_intensity_CO2e_per100sek': ('04.5.5', 'per100sek'),
    'CONS_dairy_eggs_intensity_CO2e_per100sek': ('01.1.4', 'per100sek'),
    'CONS_housing_imputed_rent_intensity_CO2e_per100sek': ('04.2.1', 'per100sek'),
}
FOOTPRINT = kommun.BUNDLED_DIR / 'karlstad' / 'data' / 'fotavtryck-per-konsumtionskategori.json'


def _export_cell(code: str, column: str) -> float:
    rows = [r for r in json.loads(FOOTPRINT.read_text(encoding='utf-8')) if r['coicop'] == code]
    assert len(rows) == 1, code
    return rows[0][column]
# A share of floor area out of two MWh totals, and two survey distributions:
# none of them is one cell in a file. The municipal construction row is one
# category in the municipal-org file, which has no cell reader (_CELL_READERS).
NOT_ONE_CELL = ('HEAT_share_district_heating_res', 'GOODS_secondhand_share',
                'MAT_meat_total_kg_percap_SE', 'BYGG_municipal_husbyggande_CO2e')
TECHNICAL = re.compile(r'LOOKUP|DATA_[A-Z]')
KK = pytest.mark.konsumtionskompassen


def _view() -> dict[str, dict]:
    return {r['id']: r for s in P.parameter_view() for r in s['rows']}


@pytest.fixture
def use_kommun():
    before = kommun._active

    def use(profile):
        kommun.set_active(kommun.bundled(profile) if isinstance(profile, str) else profile)
        return kommun.active()

    yield use
    kommun.set_active(before)


# ---------- the number shown is the number in the file ----------

@pytest.mark.karlstad
@KK
def test_every_data_file_row_is_accounted_for():
    """The two lists above are the whole set, counted from the library itself."""
    datafil = {r['id'] for s in P.parse_parameter_library() for r in s['rows']
               if r['provenance'] == 'datafil'}
    assert datafil == set(ONE_CELL) | set(FROM_KK) | set(NOT_ONE_CELL)
    assert not set(ONE_CELL) & set(NOT_ONE_CELL) and not set(FROM_KK) & (set(ONE_CELL) | set(NOT_ONE_CELL))


@pytest.mark.karlstad
@pytest.mark.parametrize('pid,expected', sorted(ONE_CELL.items()))
def test_a_row_that_points_at_one_cell_shows_that_number(pid, expected):
    row = _view()[pid]
    assert row['value_display'] == expected
    assert row['value_note'].endswith('.') and 'Datafil: ' in row['value_note']


@pytest.mark.karlstad
@KK
@pytest.mark.parametrize('pid', sorted(FROM_KK))
def test_a_consumption_row_shows_the_number_in_the_export(pid):
    row = _view()[pid]
    assert row['value_display'] == P._display_number(_export_cell(*FROM_KK[pid]))
    assert row['value_note'].endswith('.') and 'Datafil: ' in row['value_note']


@pytest.mark.karlstad
@pytest.mark.parametrize('pid', NOT_ONE_CELL)
def test_a_row_that_is_not_one_cell_gets_words_and_no_number(pid):
    row = _view()[pid]
    assert row['value_display'] == 'Läses ur datafilen vid varje analys'
    assert not re.search(r'\d', row['value_display'])
    assert 'Datafil: ' in row['value_note']


@pytest.mark.karlstad
def test_no_expression_reaches_the_reader():
    rows = _view().values()
    leaked = [(r['id'], r[k]) for r in rows for k in ('value_display', 'value_note')
              if TECHNICAL.search(r[k])]
    assert not leaked
    # Control: the expressions are there to leak, in the field the view no longer prints.
    expressions = len(ONE_CELL) + len(NOT_ONE_CELL) + (len(FROM_KK) if HAS_KK else 0)
    assert sum(1 for r in rows if TECHNICAL.search(r['value_used'])) == expressions


@pytest.mark.karlstad
def test_the_note_says_what_was_read_and_from_where():
    view = _view()
    assert view['BASE_co2_total_territorial']['value_note'] == (
        'Totala utsläpp, 2023. Datafil: Totala utsläpp per sektor och år (SMHI/RUS).')
    assert view['BASE_co2_percap_territorial']['value_note'] == (
        'Totala utsläpp, 2023, delat med Kommunbefolkning. '
        'Datafil: Totala utsläpp per sektor och år (SMHI/RUS).')
    assert view['HEAT_energy_use_percap_res']['value_note'].startswith('MWh, Per person, gånger 1 000. ')
    assert view['GOODS_secondhand_share']['value_note'].startswith('Secondhand_Frequency. ')
    assert view['HEAT_share_district_heating_res']['value_note'].startswith('Småhus vs Flerbostadshus. ')


@pytest.mark.karlstad
@KK
def test_the_note_names_the_consumption_category():
    assert _view()['CONS_air_travel_CO2e_pc_Karlstad']['value_note'].startswith(
        'Flygresor (COICOP 07.3.3), Karlstad. ')


@pytest.mark.karlstad
def test_the_view_shows_the_number_the_agents_read():
    """Agreement, not correctness: the agents get the file as a summary, and the
    view must not show another number than they read. Both go through
    _emissions_table, so that the number is the file's is what ONE_CELL checks."""
    total = _view()['BASE_co2_total_territorial']['value_display']
    line = next(l for l in P.load_emissions_data().splitlines() if l.startswith('- Alla sektorer'))
    assert line.endswith(f'2023: {total}')


@pytest.mark.karlstad
def test_other_rows_are_shown_as_before():
    view = _view()
    plain = [r for r in view.values() if r['provenance'] != 'datafil']
    assert len(plain) > 50
    assert all(r['value_display'] == r['value_used'] and r['value_note'] == '' for r in plain)
    assert view['BASE_pop']['value_display'] == '97 233'


@pytest.mark.karlstad
def test_the_library_rows_the_prompts_read_are_untouched():
    """Display only: the source check and the prompts read value_used."""
    parsed = {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}
    assert not any('value_display' in r or 'value_note' in r for r in parsed.values())
    assert parsed['BASE_co2_total_territorial']['value_used'].startswith('LOOKUP(DATA_EMISSIONS_TOTAL')
    assert {i: r['value_used'] for i, r in _view().items()} == {i: r['value_used'] for i, r in parsed.items()}


# ---------- an expression the view cannot read never becomes a wrong number ----------

def _show(expression: str, source: str = 'DATA_EMISSIONS_TOTAL',
          extra_rows: dict | None = None) -> tuple[str, str]:
    rows = {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}
    rows.update(extra_rows or {})
    row = {'id': 'X_test', 'lokalt': expression, 'lookup_source': source}
    return P._lookup_view(row, P.parse_file_register(), rows)


WORDS = 'Läses ur datafilen vid varje analys'


@pytest.mark.parametrize('expression,source,shown', [
    # control: the readers do read these
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2022)', 'DATA_EMISSIONS_TOTAL', '224 496'),
    ('LOOKUP(DATA_ENERGY_RESIDENTIAL, "MWh", "Totalt")', 'DATA_ENERGY_RESIDENTIAL', '643 851'),
    # a year, a sector, a column or a category that is not there
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 1989)', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Transporter", 2023)', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Norge", "coicop=07.D")', 'DATA_CONSUMPTION_FOOTPRINT', WORDS),
    ('LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=99.9")', 'DATA_CONSUMPTION_FOOTPRINT', WORDS),
    ('LOOKUP(DATA_ENERGY_RESIDENTIAL, "MWh", "Radhus")', 'DATA_ENERGY_RESIDENTIAL', WORDS),
    # a factor that is a range, zero, or unknown
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / BASE_ghg_percap_territorial',
     'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / 0', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / NO_SUCH_ID', 'DATA_EMISSIONS_TOTAL', WORDS),
    # arithmetic the view does not know
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) + 5', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / BASE_pop * 1000', 'DATA_EMISSIONS_TOTAL', WORDS),
    # a factor written so it can be read two ways, or not a number at all
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) * 1000', 'DATA_EMISSIONS_TOTAL', '224 950 747'),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) * 1.000', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) * 1,000', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) * inf', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / nan', 'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) * 1e3', 'DATA_EMISSIONS_TOTAL', WORDS),
    # a second LOOKUP, or a parenthesis that makes a fragment look like an argument
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2022)',
     'DATA_EMISSIONS_TOTAL', WORDS),
    ('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023)*(BASE_pop)', 'DATA_EMISSIONS_TOTAL', WORDS),
    # a source no reader knows
    ('LOOKUP(DATA_CITIZEN_SURVEY_2024, "Meat_Frequency")', 'DATA_CITIZEN_SURVEY_2024', WORDS),
])
@pytest.mark.karlstad
def test_what_an_expression_shows(expression, source, shown):
    text, note = _show(expression, source)
    assert text == shown
    assert 'Datafil: ' in note and not TECHNICAL.search(note)


@pytest.mark.karlstad
@KK
def test_the_footprint_reader_reads_another_column():
    # control for the WORDS rows below it: the reader does read the export
    text, note = _show('LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Sverige", "coicop=07.D")',
                       'DATA_CONSUMPTION_FOOTPRINT')
    assert text == P._display_number(_export_cell('07.D', 'Sverige'))
    assert 'Datafil: ' in note and not TECHNICAL.search(note)


def test_the_note_names_a_factor_even_when_it_gives_no_number():
    _text, note = _show('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / BASE_ghg_percap_territorial',
                        'DATA_EMISSIONS_TOTAL')
    assert note.startswith('Totala utsläpp, 2023, delat med Territoriella utsläpp per capita')


def test_a_fragment_of_an_expression_is_never_printed_as_the_note():
    _text, note = _show('LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / '
                        'LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2022)')
    assert note == 'Datafil: Totala utsläpp per sektor och år (SMHI/RUS).'


# ---------- the factor after a LOOKUP ----------

def _factor(**row) -> dict:
    return {'F': {'id': 'F', 'beskrivning': 'Faktorn', 'provenance': 'lokal',
                  'enhet': 'personer', 'value_used': '100 000', **row}}


TOTAL_2023 = 'LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023)'


@pytest.mark.karlstad
def test_control_a_local_plain_number_divides():
    assert _show(TOTAL_2023 + ' / F', extra_rows=_factor())[0] == '2,25'  # 224950,7472 / 100 000


@pytest.mark.parametrize('row', [
    {'provenance': 'schablon'},              # a national default under "Ur lokal datafil"
    {'provenance': 'datafil'},
    {'value_used': '97.233'},                # 97 233 or 97,233?
    {'value_used': '97,233'},
    {'value_used': '90 000–110 000'},
    {'value_used': '55', 'enhet': '% av bostadsarea'},   # would multiply as 55, not 0,55
])
def test_a_factor_that_could_mislead_gives_no_number(row):
    for op in ('/', '*'):
        text, note = _show(f'{TOTAL_2023} {op} F', extra_rows=_factor(**row))
        assert text == WORDS
        assert 'Faktorn' in note  # the note still says what the library asks for


@pytest.mark.parametrize('text,number', [
    ('97 233', 97233.0), ('97\u00a0233', 97233.0), ('1000', 1000.0), ('6.67', 6.67),
    ('0,828', 0.828), ('0.500', 0.5), ('1 234,5', 1234.5), ('-2,31', -2.31),
    ('224950,7472', 224950.7472), ('1234,567', 1234.567),
])
def test_a_number_written_one_way_is_read(text, number):
    assert P._plain_number(text) == number


@pytest.mark.parametrize('text', ['97.233', '97,233', '1.000', '12,345', '2–3', '55 %', '~30',
                                  'inf', 'nan', '1e5', '1.2.3', '', '?', 'LOOKUP(X, "y")'])
def test_a_number_that_can_be_read_two_ways_is_not_a_number(text):
    assert P._plain_number(text) is None


# ---------- the readers refuse a file that does not name exactly one cell ----------

EMISSIONS_HEAD = 'Rapportnamn:;x\nEmissioner;\nEnhet: ton/år;\nCO2-ekv;\n;\n'
EMISSIONS_COLS = 'Huvudsektor;Undersektor;Län;Kommun;CO2;CO2;CO2\n'
TOTAL_ROW = 'Alla;Alla;Län;Ort;100;200;300\n'


def _emissions(tmp_path, years: str, rows: str, year: str):
    path = tmp_path / 'e.csv'
    path.write_text(EMISSIONS_HEAD + years + EMISSIONS_COLS + rows, encoding='utf-8')
    return P._cell_emissions(path, ['Totala utsläpp', year])[0]


def test_control_the_emissions_reader_reads_the_year_asked_for(tmp_path):
    assert _emissions(tmp_path, ';;;;2021;2022;2023\n', TOTAL_ROW, '2022') == 200.0
    assert _emissions(tmp_path, ';;;;2021;2022;2023\n', TOTAL_ROW + 'Transporter;Alla;Län;Ort;1;2;3\n',
                      '2023') == 300.0
    # trailing empty cells, as an export pads its lines, do not count as values
    assert _emissions(tmp_path, ';;;;2021;2022;2023;;\n', 'Alla;Alla;Län;Ort;100;200;300;;\n', '2021') == 100.0


@pytest.mark.parametrize('years,rows', [
    (';;;;2021;2022;2023\n', TOTAL_ROW + TOTAL_ROW),                    # two total rows
    (';;;;2021;2022;2023\n', 'Alla;Alla;Län;Ort;100;200\n'),            # a row shorter than the years
    (';;;;2021;2022*;2023\n', TOTAL_ROW),                               # a year header the table drops
    (';;;;2021;2022;2023\n', 'Transporter;Alla;Län;Ort;100;200;300\n'),  # no total row
])
def test_the_emissions_reader_gives_nothing_when_the_cell_is_not_certain(tmp_path, years, rows):
    for year in ('2021', '2022', '2023'):
        assert _emissions(tmp_path, years, rows, year) is None


def test_a_year_that_stands_twice_is_not_read(tmp_path):
    twice = ';;;;2021;2022;2022\n'
    assert _emissions(tmp_path, twice, TOTAL_ROW, '2022') is None
    assert _emissions(tmp_path, twice, TOTAL_ROW, '2021') == 100.0  # the columns still line up


def _energy(tmp_path, body: str, kategori: str = 'Per person'):
    path = tmp_path / 'en.csv'
    path.write_text('Kategori,MWh\n' + body, encoding='utf-8')
    return P._cell_energy(path, ['MWh', kategori])[0]


def test_the_energy_reader_wants_one_category_and_one_plain_number(tmp_path):
    assert _energy(tmp_path, 'Småhus,318462\nPer person,6.67\n') == 6.67
    assert _energy(tmp_path, 'Per person,6.67\nPer person,7.01\n') is None
    assert _energy(tmp_path, 'Per person,6.670\n') is None   # 6,67 or 6 670?
    assert _energy(tmp_path, 'Per person,inf\n') is None
    assert _energy(tmp_path, 'Per person,\n') is None


def _footprint(tmp_path, content: str, column: str = 'Ort'):
    path = tmp_path / 'f.json'
    path.write_text(content, encoding='utf-8')
    return P._cell_footprint(path, [column, 'coicop=07.D'])[0]


def test_the_footprint_reader_wants_one_category_and_a_real_number(tmp_path):
    item = {'coicop': '07.D', 'label': 'fordon', 'Ort': 512.4}
    assert _footprint(tmp_path, json.dumps([item])) == 512.4
    assert _footprint(tmp_path, json.dumps([item, item])) is None
    assert _footprint(tmp_path, json.dumps([{**item, 'Ort': True}])) is None
    assert _footprint(tmp_path, json.dumps([{**item, 'Ort': '512.4'}])) is None
    assert _footprint(tmp_path, json.dumps({'data': [item]})) is None
    assert _footprint(tmp_path, json.dumps([item]), column='Sverige') is None


@pytest.mark.parametrize('x,shown', [
    (224950.7472, '224 951'), (6670.0, '6 670'), (999.6, '1 000'), (999.4, '999'),
    (512.44, '512'), (99.96, '100'), (31.8985, '31,9'), (7.2407, '7,24'), (3.6002, '3,60'),
    (2.3135, '2,31'), (0.61797, '0,618'), (0.0015004, '0,00150'), (1.2345e-7, '0,000000123'),
    (-2.3135, '-2,31'), (-224950.7472, '-224 951'), (0.0, '0'),
])
def test_numbers_are_written_with_three_significant_figures(x, shown):
    assert P._display_number(x) == shown


# ---------- another municipality ----------

def _goteborg(tmp_path, population: str = '600 000', column: str = 'Göteborg'):
    root = tmp_path / 'goteborg'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    toml = (root / 'kommun.toml').read_text(encoding='utf-8')
    (root / 'kommun.toml').write_text(
        toml.replace('ort = "Exempelstad"', 'ort = "Göteborg"'), encoding='utf-8')
    lib = (root / 'parameters_library.md').read_text(encoding='utf-8')
    assert '| BASE_pop | Bas | Kommunbefolkning | ? | ? |' in lib
    lib = lib.replace('| BASE_pop | Bas | Kommunbefolkning | ? | ? |',
                      f'| BASE_pop | Bas | Kommunbefolkning | ? | {population} |')
    assert '"Exempelstad", "coicop=07.D"' in lib
    lib = lib.replace('"Exempelstad", "coicop=', f'"{column}", "coicop=')
    (root / 'parameters_library.md').write_text(lib, encoding='utf-8')
    (root / 'data' / 'fotavtryck-per-konsumtionskategori.json').write_text(json.dumps([
        {'coicop': '07.D', 'label': 'fordon', 'per100sek': 9.2, 'Göteborg': 512.4,
         'Sverige': 640.0}]), encoding='utf-8')
    (root / 'data' / 'kommunrapport_vaxthusgaser_totalt.csv').write_text(
        'Rapportnamn:;x\nEmissioner;\nEnhet: ton/år;\nCO2-ekv;\n;\n'
        ';;;;2022;2023\n'
        'Huvudsektor;Undersektor;Län;Kommun;CO2;CO2\n'
        'Alla;Alla;Västra Götalands län;Göteborg;1000,5;900,25\n', encoding='utf-8')
    return root


def test_another_municipality_gets_its_own_numbers(tmp_path, use_kommun):
    use_kommun(kommun.load(_goteborg(tmp_path)))
    view = _view()
    assert view['BASE_co2_total_territorial']['value_display'] == '900'
    assert view['BASE_co2_percap_territorial']['value_display'] == '0,00150'  # 900,25 / 600 000
    assert view['CONS_dir_vehicle_CO2e_pc_lokal']['value_display'] == '512'
    assert view['CONS_dir_vehicle_CO2e_pc_lokal']['value_note'].startswith('Fordon (COICOP 07.D), Göteborg. ')
    # A source whose file is not there is a schablon, shown as before.
    energy = view['HEAT_energy_use_percap_res']
    assert energy['provenance'] == 'schablon'
    assert (energy['value_display'], energy['value_note']) == (energy['standard'], '')


def test_a_population_that_is_not_filled_in_gives_no_per_capita_number(tmp_path, use_kommun):
    use_kommun(kommun.load(_goteborg(tmp_path, population='?')))
    view = _view()
    assert view['BASE_co2_total_territorial']['value_display'] == '900'
    assert view['BASE_co2_percap_territorial']['value_display'] == WORDS


def test_a_column_the_file_does_not_have_is_not_read_from_another(tmp_path, use_kommun):
    """The library still says "Exempelstad" but the export's column is Göteborg:
    the view must not fall back to Sverige or to the first number it finds."""
    use_kommun(kommun.load(_goteborg(tmp_path, column='Exempelstad')))
    row = _view()['CONS_dir_vehicle_CO2e_pc_lokal']
    assert row['provenance'] == 'datafil'
    assert row['value_display'] == WORDS


@pytest.mark.parametrize('content', [
    '{not json',
    # a number no float can hold: OverflowError, not a ValueError
    '[{"coicop": "07.D", "label": "fordon", "Göteborg": 1' + '0' * 400 + '}]',
    '[' * 100_000,   # nested past the recursion limit
])
def test_a_file_that_cannot_be_read_costs_one_row_its_number_not_the_list(tmp_path, use_kommun, caplog,
                                                                         content):
    root = _goteborg(tmp_path)
    (root / 'data' / 'fotavtryck-per-konsumtionskategori.json').write_text(content, encoding='utf-8')
    use_kommun(kommun.load(root))
    with caplog.at_level('WARNING', logger='caia.data.parameters'):
        view = _view()
    assert view['CONS_dir_vehicle_CO2e_pc_lokal']['value_display'] == WORDS
    assert view['BASE_co2_total_territorial']['value_display'] == '900'  # the other rows are there
    assert any('CONS_dir_vehicle_CO2e_pc_lokal' in r.getMessage() for r in caplog.records)


def test_a_cell_that_is_not_a_finite_number_gives_no_number(tmp_path, use_kommun):
    root = _goteborg(tmp_path)
    (root / 'data' / 'fotavtryck-per-konsumtionskategori.json').write_text(
        '[{"coicop": "07.D", "label": "fordon", "Göteborg": Infinity}]', encoding='utf-8')
    use_kommun(kommun.load(root))
    assert _view()['CONS_dir_vehicle_CO2e_pc_lokal']['value_display'] == WORDS


def test_the_example_profile_has_no_data_files_and_no_notes(use_kommun):
    use_kommun('exempel')
    rows = _view().values()
    assert all(r['value_note'] == '' and r['value_display'] == r['value_used'] for r in rows)


# ---------- the route and the page ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    return A.app.test_client()


@pytest.mark.karlstad
def test_the_route_carries_the_display_fields(client):
    body = client.get('/api/parameters').get_json()
    rows = {r['id']: r for s in body['sections'] for r in s['rows']}
    assert rows['BASE_co2_total_territorial']['value_display'] == '224 951'
    assert rows['BASE_co2_total_territorial']['value_note'].startswith('Totala utsläpp, 2023.')
    assert rows['BASE_co2_total_territorial']['value_used'].startswith('LOOKUP(')  # contract kept
    # Without Konsumtionskompassen's files (the public release) its ten rows
    # are standard values.
    assert body['counts'] == ({'lokal': 17, 'datafil': 17, 'schablon': 69} if HAS_KK
                              else {'lokal': 17, 'datafil': 7, 'schablon': 79})


RENDER = """
const out = {};
const document = {getElementById: () => out};
const KOMMUN = {ort: 'Karlstad'};
function escapeHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
const PROV = {lokal: ['Lokalt verifierad', 'prov-lokal'], datafil: ['Ur lokal datafil', 'prov-datafil'],
              schablon: ['Nationell schablon', 'prov-schablon']};
"""


def _rendered(rows: list[dict]) -> str:
    render = _between(_inline_script(), 'function renderParams(d)', '\n}\n') + '\n}\n'
    data = {'total': len(rows), 'counts': {}, 'sections': [{'title': 'S', 'rows': rows}]}
    return _node(RENDER + render + f'renderParams({json.dumps(data)});'
                 'console.log(JSON.stringify({html: out.innerHTML}));')['html']


@pytest.mark.node
def test_the_page_names_a_parameter_by_its_description_with_the_id_under():
    html = _rendered([{'id': 'BASE_pop', 'beskrivning': 'Kommunbefolkning', 'enhet': 'personer',
                       'provenance': 'lokal', 'value_used': '97 233', 'value_display': '97 233',
                       'value_note': ''}])
    assert '<div class="param-name">Kommunbefolkning</div><div class="param-id">BASE_pop</div>' in html
    assert '<div class="param-val">97 233</div></td>' in html
    assert 'param-note' not in html


@pytest.mark.node
def test_the_page_puts_the_note_under_the_value_and_never_the_expression():
    html = _rendered([{'id': 'BASE_co2_total_territorial', 'beskrivning': 'Totala utsläpp',
                       'enhet': 'ton CO2e/år', 'provenance': 'datafil',
                       'value_used': 'LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023)',
                       'value_display': '224 951', 'value_note': 'Totala utsläpp, 2023. Datafil: <x>.'}])
    assert ('<div class="param-val">224 951</div>'
            '<div class="param-note">Totala utsläpp, 2023. Datafil: &lt;x&gt;.</div>') in html
    assert 'LOOKUP' not in html


@pytest.mark.node
def test_a_parameter_without_a_description_is_named_by_its_id():
    html = _rendered([{'id': 'X_new', 'beskrivning': '', 'enhet': '', 'provenance': 'schablon',
                       'value_used': '1', 'value_display': '1', 'value_note': ''}])
    assert '<div class="param-name">X_new</div></td>' in html
    assert 'param-id' not in html
