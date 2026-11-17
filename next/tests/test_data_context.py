"""Tests for the data layer that feeds agent context.

None of these bugs crash anything — that is exactly why they need tests. They
change which numbers the agents reason about, and a tool whose whole point is
quantification integrity cannot have a data loader that silently drops a third
of its rows.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_data_context.py -v
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
from conftest import HAS_KK  # noqa: E402

REPLACEMENT = '�'


def _csv_data_rows() -> int:
    """Row count straight from the file, independent of the loader."""
    path = P.data_dir() / "Kommunrapport_karlstad_vaxthusgaser_totalt.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    return len([l for l in lines[5:]
                if l.split(';')[0].strip() and l.split(';')[0].strip() != 'Huvudsektor'])


# ---------- C1: no silent row truncation ----------

@pytest.mark.karlstad
def test_every_csv_row_reaches_the_summary():
    summary = P.load_emissions_data()
    emitted = [l for l in summary.splitlines() if l.startswith('- ')]
    assert len(emitted) == _csv_data_rows() == 62, (len(emitted), _csv_data_rows())


@pytest.mark.karlstad
def test_sectors_that_used_to_be_truncated_are_present():
    # These sat past row 30 and vanished entirely from the agent context.
    summary = P.load_emissions_data()
    for sector in ("Egen uppvärmning av bostäder och lokaler", "Arbetsmaskiner",
                   "Produktanvändning", "Avfall", "Utrikes transporter"):
        assert sector in summary, sector


# ---------- C2: label repair ----------

def test_no_replacement_characters_survive_into_context():
    assert REPLACEMENT not in P.get_data_context()
    assert 'ï¿½' not in P.get_data_context()  # the latin-1 double-mangling


def test_repair_restores_swedish_letters():
    assert P.repair_label('Egen uppv' + REPLACEMENT + 'rmning av bost'
                          + REPLACEMENT + 'der och lokaler') \
        == 'Egen uppvärmning av bostäder och lokaler'
    assert P.repair_label('J' + REPLACEMENT + 'rnv' + REPLACEMENT + 'g') == 'Järnväg'


def test_repair_handles_letters_folded_to_ascii():
    # Some labels lost å/ä to a bare 'a' instead of the replacement char.
    assert P.repair_label('Slitage fran d' + REPLACEMENT + 'ck och bromsar') \
        == 'Slitage från däck och bromsar'


def test_repair_leaves_clean_and_unknown_labels_alone():
    assert P.repair_label('Personbilar') == 'Personbilar'
    unknown = 'Helt ok' + REPLACEMENT + 'nd sektor som inte finns i listan'
    assert P.repair_label(unknown) == unknown


@pytest.mark.karlstad
def test_repair_fires_when_the_diacritic_left_no_residue():
    # The first version of this fix gated on "contains U+FFFD", which skipped
    # the labels that lost their diacritic entirely. Those are the worst kind:
    # they read as an ordinary typo, not as a parsing artifact, so nobody
    # reports them. Asserting absence of U+FFFD cannot catch this class.
    assert P.repair_label('Urea for katalysatorer') == 'Urea för katalysatorer'
    assert 'Urea för katalysatorer' in P.load_emissions_data()
    assert 'Urea for katalysatorer' not in P.load_emissions_data()


# Every label in the source file that is already correct Swedish without any
# diacritic. Widening the matcher to run on clean labels must not "repair" one
# of these into a different word.
_ALREADY_CORRECT = (
    'Alla', 'Arbetsmaskiner', 'Avfall (inkl.avlopp)', 'Avfallsdeponier',
    'Behandling av avloppsvatten', 'Biologisk behandling av avfall', 'Bussar',
    'Industri (energi + processer)', 'Inrikes flygtrafik', 'Jordbruk',
    'Jordbruk och skogsbruk', 'Jordbruks- och skogsbrukslokaler',
    'Kommersiella och offentliga lokaler', 'Kommersiella och offentliga verksamheter',
    'Mopeder och Motorcyklar', 'Odling av mineraljordar', 'Odling av organogena jordar',
    'Paraffinvax', 'Personbilar', 'Skotrar och fyrhjulingar', 'Transporter',
    'Tunga lastbilar', 'Utrikes transporter',
)


def test_correct_labels_are_never_rewritten():
    for label in _ALREADY_CORRECT:
        assert P.repair_label(label) == label, label


@pytest.mark.karlstad
def test_no_label_in_the_file_is_repaired_into_a_different_word():
    """Structural guard: a repair may only change positions where the canonical
    holds a Swedish letter, and may never change the length."""
    path = P.data_dir() / "Kommunrapport_karlstad_vaxthusgaser_totalt.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[7:]:
        for cell in line.split(';')[:2]:
            observed = cell.strip()
            if not observed:
                continue
            repaired = P.repair_label(observed)
            if repaired == observed:
                continue
            assert len(repaired) == len(observed), (observed, repaired)
            for a, b in zip(observed, repaired):
                assert a == b or b in 'åäöÅÄÖ', (observed, repaired)


# ---------- V4: year labels and sub-sectors ----------

@pytest.mark.karlstad
def test_values_carry_their_year():
    summary = P.load_emissions_data()
    assert '2023:' in summary and '2021:' in summary


@pytest.mark.karlstad
def test_subsectors_are_not_collapsed_into_identical_rows():
    summary = P.load_emissions_data()
    transport_rows = [l for l in summary.splitlines() if l.startswith('- Transporter')]
    assert len(transport_rows) > 1
    assert len(set(transport_rows)) == len(transport_rows), "duplicate Transporter rows"
    assert '- Transporter / Personbilar:' in summary


def test_swedish_decimal_comma_is_parsed_not_concatenated():
    assert P._to_number('224950,7472') == 224950.7472
    assert P._to_number('1 234,5') == 1234.5          # ordinary space
    assert P._to_number('1 234,5') == 1234.5      # non-breaking space
    assert P._to_number('') is None
    assert P._to_number('ej tillämpligt') is None


# ---------- C3: municipal group emissions ----------

@pytest.mark.karlstad
def test_municipal_section_is_not_empty():
    summary = P.load_consumption_data()
    assert '### Kommunkoncernens' in summary
    idx = summary.index('### Kommunkoncernens')
    rows = [l for l in summary[idx:].splitlines() if l.startswith('- ')]
    assert len(rows) == 77, len(rows)
    assert 'El: 10 218 ton' in summary


@pytest.mark.karlstad
def test_thousands_grouping_does_not_eat_commas_in_names():
    # The first attempt at this fix ran .replace(',', ' ') over the whole line.
    summary = P.load_consumption_data()
    assert 'El, gas, värme och kyla' in summary


@pytest.mark.karlstad
def test_municipal_total_matches_the_source_file():
    path = P.data_dir() / "Kommunkoncernens_egna_konsumtionsbaserade_CO2e-utsläpp.json"
    items = json.loads(path.read_text(encoding='utf-8'))['data']
    expected = round(sum(i['Kg CO2e'] for i in items) / 1000)
    assert f"totalt {P._thousands(expected)}" in P.load_consumption_data()


# ---------- T2: region labels on the household series ----------

@pytest.mark.karlstad
@pytest.mark.konsumtionskompassen
def test_household_series_are_distinguishable_by_region():
    summary = P.load_consumption_data()
    for region in ('Karlstad', 'Värmlands län', 'Sverige'):
        assert f'- {region}:' in summary, region


# ---------- T4a: the section-12 file register is not a parameter table ----------

def _library_lines():
    return P.params_file().read_text(encoding='utf-8').splitlines()


def _data_rows_before_and_after_register():
    """Independent count of table data rows: `after` is the section-12
    register, `before` every other section (13, building materials, comes
    after the register in the file).

    Deliberately a cruder expression than the parser's: any table line whose
    first cell is not a header word and not a separator. If the parser and
    this disagree, one of them is wrong about what a row is."""
    before, after, in_register = [], [], False
    for line in _library_lines():
        if line.startswith('## '):
            in_register = line.startswith('## 12')
            continue
        if not line.startswith('|'):
            continue
        first = line.strip('|').split('|')[0].strip()
        if not first or first in ('Parameter_ID', 'Logiskt_Namn') or set(first) <= {'-', ':'}:
            continue
        (after if in_register else before).append(first)
    return before, after


def test_every_parameter_row_is_parsed_and_no_register_row_is():
    before, after = _data_rows_before_and_after_register()
    parsed_ids = [r['id'] for s in P.parse_parameter_library() for r in s['rows']]
    assert parsed_ids == before, (len(parsed_ids), len(before))
    assert not set(parsed_ids) & set(after), set(parsed_ids) & set(after)
    # Seven sources: the SCB helper-script row went with the handover review
    # (nothing ever ran it; the prompts say no code is run).
    assert len(after) == 7 and all(a.startswith('DATA_') for a in after), after


def test_register_rows_used_to_leak_in_as_parameters():
    # Concrete old symptom: /api/parameters listed DATA_EMISSIONS_TOTAL as a
    # parameter with the CSV file name in its category column, plus the
    # header word "Logiskt_Namn" as a parameter id.
    ids = {r['id'] for s in P.parse_parameter_library() for r in s['rows']}
    assert 'Logiskt_Namn' not in ids
    assert not any(i.startswith('DATA_') for i in ids)
    titles = [s['title'] for s in P.parse_parameter_library()]
    assert not any(t.startswith('12.') for t in titles), titles


@pytest.mark.karlstad
def test_file_register_reports_which_sources_are_on_disk():
    _before, after = _data_rows_before_and_after_register()
    reg = P.parse_file_register()
    assert set(reg) == set(after)
    # Ground truth straight from the file system, not from the parser.
    for name, entry in reg.items():
        assert entry['exists'] == (P.data_dir() / entry['filename']).exists(), name
    assert reg['DATA_EMISSIONS_TOTAL']['exists'] is True
    # The RVU report is registered as the source of section 2's travel numbers,
    # which are transcribed with page references. The PDF itself is not in
    # data/: no loader reads it, and on disk it would let an agent cite the
    # whole file as kommundata without any value check.
    assert reg['DATA_TRAVEL_SURVEY']['exists'] is False


# ---------- T1: a LOOKUP into a missing file is a schablon, not "datafil" ----------
#
# Karlstad's own library no longer has such a LOOKUP (T1 closed 2026-09-28:
# the travel numbers are filled from RVU 2023). The branch still matters for
# any profile that writes one, so these tests run on a copy of the Karlstad
# profile with one row turned back into the old unresolvable LOOKUP.

_OLD_CAR_LOOKUP = 'LOOKUP(DATA_TRAVEL_SURVEY, "Färdmedelsfördelning", "Bil")'


@pytest.fixture
def missing_lookup_profile(tmp_path):
    src = kommun.bundled('karlstad')
    root = tmp_path / 'karlstad-kopia'
    shutil.copytree(src.root, root)
    lib = root / 'parameters_library.md'
    text = lib.read_text(encoding='utf-8')
    row = next(l for l in text.splitlines() if l.startswith('| TR_mode_share_car |'))
    cells = row.split('|')
    cells[5] = f' {_OLD_CAR_LOOKUP} '
    lib.write_text(text.replace(row, '|'.join(cells)), encoding='utf-8')
    before = kommun._active
    kommun.set_active(kommun.load(root))
    yield
    kommun.set_active(before)


def _register_from_file() -> dict[str, bool]:
    """Source name -> file-on-disk, read from section 12 without the parser."""
    out = {}
    in_register = False
    for line in _library_lines():
        if line.startswith('## 12'):
            in_register = True
            continue
        if not in_register or not line.startswith('| DATA_'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        out[cells[0]] = (P.data_dir() / cells[1].strip('`')).exists()
    return out


@pytest.mark.karlstad
def test_lookup_provenance_is_datafil_exactly_when_the_file_exists(missing_lookup_profile):
    on_disk = _register_from_file()
    lookups = [r for s in P.parse_parameter_library() for r in s['rows']
               if 'LOOKUP(' in r["lokalt"].upper()]
    assert lookups, "no LOOKUP rows found; the fixture changed under the test"
    seen_missing = seen_present = False
    for r in lookups:
        src = r['lookup_source']
        assert src in on_disk, (r['id'], src)
        expected = 'datafil' if on_disk[src] else 'schablon'
        assert r['provenance'] == expected, (r['id'], src, r['provenance'])
        assert r['lookup_resolved'] is on_disk[src]
        seen_missing |= not on_disk[src]
        seen_present |= on_disk[src]
    # Both sides of the branch must be exercised or the assert above is vacuous.
    assert seen_missing and seen_present


@pytest.mark.karlstad
def test_unresolvable_lookup_uses_the_standard_value(missing_lookup_profile):
    rows = {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}
    car = rows['TR_mode_share_car']
    assert car['lookup_source'] == 'DATA_TRAVEL_SURVEY'
    assert car['provenance'] == 'schablon'
    assert car['value_used'] == car['standard'] == '50–60'
    total = rows['BASE_co2_total_territorial']
    assert total['provenance'] == 'datafil'
    assert total['value_used'].startswith('LOOKUP(DATA_EMISSIONS_TOTAL')


@pytest.mark.karlstad
def test_unresolvable_lookup_is_logged_not_silent(missing_lookup_profile, caplog):
    with caplog.at_level('WARNING', logger='caia.data.parameters'):
        P.parse_parameter_library()
    msgs = [r.getMessage() for r in caplog.records if 'DATA_TRAVEL_SURVEY' in r.getMessage()]
    assert len(msgs) == 1, caplog.text
    assert 'TR_mode_share_car' in msgs[0]
    assert 'DATA_EMISSIONS_TOTAL' not in caplog.text  # resolvable sources are not noise


# ---------- T1 closed: Karlstad's travel numbers come from RVU 2023 ----------
#
# Expected values are read by hand from the report (Resvaneundersökning Region
# Värmland 2023, kommunrapport Karlstad), the same readings Karlstad's plan-analysis tool uses, not from
# the library under test.

RVU_KOMMUN = {
    'TR_mode_share_car': (53.0, 'figur 18 s. 25'),
    'TR_mode_share_bike': (20.0, 'figur 18 s. 25'),
    'TR_mode_share_bus': (11.0, 'figur 18 s. 25'),
    'TR_mode_share_train': (1.0, 'figur 18 s. 25'),
    'TR_mode_share_walk': (13.0, 'figur 18 s. 25'),
    'TR_mode_share_other': (2.0, 'figur 18 s. 25'),
    'TR_mode_share_non_car': (47.0, 'figur 18 s. 25'),
    'TR_trips_percap_perday': (2.2, 'figur 14 s. 20'),
    'TR_median_trip_length_km': (5.0, 's. 23'),
}
NOT_IN_RVU = ('TR_vkt_percap_passenger_car', 'TR_public_transport_km_percap',
              'TR_cycling_km_percap')


def _karlstad_rows() -> dict[str, dict]:
    return {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}


def _num(cell: str) -> float:
    return float(cell.replace(',', '.'))


@pytest.mark.karlstad
def test_karlstad_has_no_lookup_into_a_missing_file():
    # Every unresolvable LOOKUP claimed local data that was never there. The
    # public release leaves Konsumtionskompassen's files out by licence, and
    # its rows then use the standard value, as the library tells the agents to.
    rows = _karlstad_rows().values()
    left_out = set() if HAS_KK else {'DATA_CONSUMPTION_FOOTPRINT', 'DATA_HOUSEHOLD_TIME_SERIES'}
    bad = [(r['id'], r['lookup_source']) for r in rows
           if r.get('lookup_source') and not r['lookup_resolved']
           and r['lookup_source'] not in left_out]
    assert not bad, bad
    for r in rows:
        if r.get('lookup_source') in left_out:
            assert r['provenance'] == 'schablon', r
            assert r['value_used'] == r['standard'], r


@pytest.mark.karlstad
@pytest.mark.parametrize('pid', sorted(RVU_KOMMUN))
def test_rvu_numbers_are_local_with_figure_and_page(pid):
    value, where = RVU_KOMMUN[pid]
    row = _karlstad_rows()[pid]
    assert row['provenance'] == 'lokal', row
    assert _num(row['lokalt']) == value
    assert row['value_used'] == row['lokalt']
    assert 'RVU 2023' in row['kommentar']
    assert where in row['kommentar'], row['kommentar']


@pytest.mark.karlstad
def test_rvu_mode_shares_add_up_to_the_whole():
    rows = _karlstad_rows()
    parts = [_num(rows[p]['lokalt']) for p in (
        'TR_mode_share_car', 'TR_mode_share_bike', 'TR_mode_share_bus',
        'TR_mode_share_train', 'TR_mode_share_walk', 'TR_mode_share_other')]
    assert sum(parts) == 100
    assert _num(rows['TR_mode_share_non_car']['lokalt']) == 100 - parts[0]


@pytest.mark.karlstad
def test_median_trip_length_says_it_is_not_a_mean():
    note = _karlstad_rows()['TR_median_trip_length_km']['kommentar']
    assert 'median, inte ett medelvärde' in note
    assert 'medelreslängden är efterfrågad' in note


@pytest.mark.karlstad
@pytest.mark.parametrize('pid', NOT_IN_RVU)
def test_numbers_the_report_lacks_stay_schablon_and_say_so(pid):
    row = _karlstad_rows()[pid]
    assert row['provenance'] == 'schablon'
    assert row['value_used'] == row['standard']
    assert row['kommentar'].startswith('Schablon. Finns inte i RVU 2023')


# ---------- whole-context smoke ----------

@pytest.mark.karlstad
def test_context_contains_all_four_sections():
    ctx = P.get_data_context()
    for heading in ('## Territoriella växthusgasutsläpp Karlstad',
                    '## Energianvandning bostader Karlstad',
                    '## Konsumtionsbaserade utslapp Karlstad',
                    '## Medborgarundersokning Karlstad 2024'):
        assert heading in ctx, heading


# ---------- F18: a file on disk is local data only when CAIA reads it ----------

@pytest.fixture
def travel_pdf_on_disk(missing_lookup_profile):
    """The Karlstad copy with TR_mode_share_car as a LOOKUP into the travel
    survey, and the survey PDF dropped into data/ as INSTALL once told a new
    municipality to do."""
    register = P.parse_file_register()
    pdf = P.data_dir() / register['DATA_TRAVEL_SURVEY']['filename']
    pdf.write_bytes(b'%PDF-1.4 not read by anything\n')
    yield
    pdf.unlink()


@pytest.mark.karlstad
def test_a_registered_file_nothing_reads_is_not_datafil(travel_pdf_on_disk):
    entry = P.parse_file_register()['DATA_TRAVEL_SURVEY']
    assert entry['exists'] is True and entry['read'] is False
    car = {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}['TR_mode_share_car']
    assert car['provenance'] == 'schablon'
    assert car['value_used'] == car['standard']


@pytest.mark.karlstad
def test_source_check_does_not_certify_an_unread_file_as_kommundata(travel_pdf_on_disk):
    from caia import kallmarkering as KM
    assert 'DATA_TRAVEL_SURVEY' not in KM.kommundata_block()
    register = P.parse_file_register()
    lib = {r['id']: r for s in P.parse_parameter_library() for r in s['rows']}
    kalla = KM.Kalla(ursprung=KM.Ursprung.KOMMUNDATA, parametrar=('DATA_TRAVEL_SURVEY',))
    _u, problem, _underlag = KM._check(53.0, kalla, lib, register)
    assert 'läses inte' in problem


def test_every_source_a_loader_reads_is_in_read_sources():
    """READ_SOURCES is a hand-kept list; a new loader that is not on it would
    have its rows labelled schablon. Tie the list to the loaders' code."""
    import inspect
    src = inspect.getsource(P)
    loaded = set(re.findall(r'_source_file\("(DATA_[A-Z_]+)"\)', src))
    assert loaded == set(P.READ_SOURCES)


@pytest.mark.karlstad
@pytest.mark.parametrize('slug', ['karlstad', 'exempel'])
def test_the_library_the_agents_get_asks_for_no_code(slug):
    before = kommun._active
    kommun.set_active(kommun.bundled(slug))
    try:
        text = P.load_parameter_library()
    finally:
        kommun.set_active(before)
    for word in ('Code Interpreter', 'pandas', 'scb_connector', 'get_table('):
        assert word not in text, (slug, word)


# ---------- E17: a data file in the wrong encoding says which and how to fix it ----------

@pytest.mark.karlstad
def test_a_latin1_data_file_names_itself_and_the_fix(tmp_path):
    src = kommun.bundled('karlstad')
    root = tmp_path / 'latin1'
    shutil.copytree(src.root, root)
    energy = P.parse_file_register()['DATA_ENERGY_RESIDENTIAL']['filename']
    path = root / 'data' / energy
    path.write_bytes(path.read_text(encoding='utf-8').encode('latin-1'))
    before = kommun._active
    kommun.set_active(kommun.load(root))
    try:
        with pytest.raises(kommun.KommunProfilError, match=re.escape(energy) + '.*iconv'):
            P.get_data_context()
    finally:
        kommun.set_active(before)
