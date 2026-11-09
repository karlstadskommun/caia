"""What the models write in their working vocabulary (field names, parameter
codes, BAU, A0, ΔA, 7,8e7) is put in words on the page and in the download
(Henric 2026-10-13, after a run as a miljöstrateg). The fixtures are the report
and evidens text of a real run on the workshop address that evening."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from test_key_points import _run

pytestmark = pytest.mark.node

FIX = Path(__file__).parent / 'fixtures'


def _plain(text: str) -> str:
    return _run(f'plainTerms({json.dumps(text)})')


@pytest.mark.parametrize('raw, shown', [
    ('ΔE_2030_total (Netto): 129 ton CO2e/år', 'Effekt 2030 (Netto): 129 ton CO2e/år'),
    ('ΔE_kumulativt_till_malår_total (Netto): [1 255 ton CO2e]', 'Sammanlagd effekt till målåret (Netto): 1 255 ton CO2e'),
    ('### Scenario_medel (mest sannolikt)', '### Medelscenariot (mest sannolikt)'),
    ('Kort tolkning_medel: liten effekt.', 'Kort tolkning: liten effekt.'),
    ('Nyckelår: [2026, 2030]', 'Nyckelår: 2026, 2030'),
    ('Enligt TR_mode_share_car är det 53 %.', 'Enligt andel resor med bil är det 53 %.'),
    ('EF_passenger_car_avg (schablon: 0,12–0,18 kg CO2/km)', 'Genomsnittlig utsläppsfaktor för personbilar (schablon: 0,12–0,18 kg CO2/km)'),
    ('Jämfört med BAU minskar det.', 'Jämfört med läget utan åtgärden minskar det.'),
    ('BAU-trenden är svag.', 'Trenden utan åtgärden är svag.'),
    ('A0 75 000 000 fordonskm/år och EF0 0,14.', 'Nulägesaktivitet 75 000 000 fordonskm/år och utsläppsfaktor i nuläget 0,14.'),
    ('en baslinje med aktivitet (A0) och emissionsfaktor (EF0)', 'en baslinje med aktivitet och emissionsfaktor'),
    # The same sentence without the brackets (the demo morning, 2026-10-14).
    ('en nulägesbaslinje (aktivitet A0 och emissionsfaktor EF0) för varje drivare',
     'en nulägesbaslinje (aktivitet och emissionsfaktor) för varje drivare'),
    ('Shift via ΔA, inte ΔEF.', 'Shift via ändrad aktivitet, inte ändrad utsläppsfaktor.'),
    ('Från 2,0e7 till 1,55e7 km/år.', 'Från 20 miljoner till 15,5 miljoner km/år.'),
    ('CoVe QA varnar.', 'Kvalitetsgranskningen varnar.'),
    ('adoption_nådda × andel_utanför', 'adoption nådda × andel utanför'),
    ('Baslinje & BAU-analys för åtgärd: X', 'Baslinje-analys för åtgärd: X'),
    # Left alone: links, a code the library does not know, ordinary words.
    ('Se https://example.se/rvu_2023/TR_mode_share_car.pdf för BAU.',
     'Se https://example.se/rvu_2023/TR_mode_share_car.pdf för läget utan åtgärden.'),
    ('DATA_MUNICIPAL_ORG anger det.', 'Kommunens egna organisationsutsläpp anger det.'),
    ('enligt DATA_CITIZEN_SURVEY_2024 och DATA_CITIZEN_SURVEY', 'enligt medborgarundersökning 2024 och medborgarundersökning 2024'),
    ('Enligt TR_MODE_SHARE_CAR', 'Enligt andel resor med bil'),
    ('DATA_XYZ rörs inte.', 'DATA_XYZ rörs inte.'),
    # What broke the first time (the review in the browser, 2026-10-13).
    ('ett BAU-scenario utan åtgärden till 2030', 'ett scenario utan åtgärden till 2030'),
    ('undvikta utsläpp mot ett BAU där fler väljer bil', 'undvikta utsläpp mot ett läge utan åtgärden där fler väljer bil'),
    ('skillnaden mellan BAU (utan åtgärden) och scenariot', 'skillnaden mellan läget utan åtgärden och scenariot'),
    ('Scenario_min (försiktigt): 42 ton', 'Det försiktiga scenariot: 42 ton'),
    ('Eftersom bilarna har låg EF faller det viktade EF via pendlingen.',
     'Eftersom bilarna har låg utsläppsfaktor faller den viktade utsläppsfaktorn via pendlingen.'),
    ('EF följer BAU.', 'Utsläppsfaktorn följer läget utan åtgärden.'),
    ('inte privatbilens EF', 'inte privatbilens utsläppsfaktor'),
    ('Nu används tailpipe och BAU-EF med Konsumtion_faktor', 'Nu används utsläpp från avgasröret och utsläppsfaktorn utan åtgärden med konsumtionsfaktor'),
    ('### BAU- och effektlogik', '### Baslinje- och effektlogik'),
    ('Underlaget är de godkända EMAP- och Baslinje & BAU-analyserna.', 'Underlaget är de godkända analyserna av utsläppskällor och baslinje.'),
    ('med ΔE:s tecken', 'med effektens tecken'),
    ('A_BAU(t) = A0 × (1 + g_A)^(t − nulägesår)', 'Aktiviteten utan åtgärden år t = nulägesaktivitet × (1 + aktivitetens trend)^(t − nulägesår)'),
    ('| A_BAU (fordonskm/år) | EF_BAU |', '| Aktiviteten utan åtgärden (fordonskm/år) | Utsläppsfaktorn utan åtgärden |'),
    ('Kommentar: g_A gäller 2023–2028. g_A-spannet är brett.', 'Kommentar: Aktivitetens trend gäller 2023–2028. Spannet för aktivitetens trend är brett.'),
    ('spannen för andel_utanför, A_tjänst och EF_tjänst', 'spannen för andel utanför, aktivitet (tjänst) och utsläppsfaktor (tjänst)'),
    ('Se ΔA_bland_nådda och Short_Car_Trips', 'Se ändrad aktivitet (bland nådda) och Short Car Trips'),
    ('Konsumtion_faktor 0.6, Overlap_faktor 0.6 (0.0/1.0/0.0)', 'Konsumtionsfaktor 0,6, överlappsfaktor 0,6 (0,0/1,0/0,0)'),
    ('överlappet är 0.6. Se avsnitt 2.1 och steg 1.2.', 'överlappet är 0,6. Se avsnitt 2.1 och steg 1.2.'),
    ('### 1.1 Kort om detta steg', '### 1.1 Kort om detta steg'),
    ('Drivare 1: Drivare 1: Personbilar', 'Drivare 1: Personbilar'),
    ('Drivare 3: Drivare 4: Pendling', 'Drivare 4: Pendling'),
    # The second browser review (2026-10-13).
    ('Ett ΔA på −21,6 % är missvisande.', 'En ändrad aktivitet på −21,6 % är missvisande.'),
    ('BAU-trendernas låga och höga värden förs inte vidare.', 'Baslinjetrendernas låga och höga värden förs inte vidare.'),
    ('Det ger samma ΔE och något högre ΔE under bygget.', 'Det ger samma effekt och något högre effekt under bygget.'),
    ('det redovisade ΔA-spannet', 'det redovisade spannet för ändrad aktivitet'),
    ('Ungefär 60 % av A0 ingår inte i EF0.', 'Ungefär 60 % av nulägesaktiviteten ingår inte i utsläppsfaktorn i nuläget.'),
    ('Med det låga EF-värdet blir det litet.', 'Med det låga värdet på utsläppsfaktorn blir det litet.'),
    ('har Gas_typ CO2 med Ar_galler 2023', 'har gastyp CO2 med giltighetsår 2023'),
    ('medel ca 0,02 tailpipe', 'medel ca 0,02 utsläpp från avgasröret'),
    ('Det stämmer med KOMM-intervallet (reach 0,45).', 'Det stämmer med intervallet för kommunikationsinsatser (räckvidd 0,45).'),
    ('Blocket räknar bara inpendlare, från localContext.', 'Drivaren räknar bara inpendlare, från kommunens data.'),
    ('2 407 ton CO2e ANTAGANDE. Kontrollera (ANTAGANDE)', '2 407 ton CO2e (antagande). Kontrollera (antagande)'),
    ('(ANTAGANDE: marginell drivare) och 30 km, ANTAGANDE), mot aktivitet ANTAGANDE och EF0',
     '(antagande: marginell drivare) och 30 km, antagande), mot aktivitet (antagande) och utsläppsfaktor i nuläget'),
    ('följer baslinjens BAU-trend (g_A) för Drivare 6', 'följer baslinjens trend utan åtgärden för Drivare 6'),
    ('Indikativ medelnivå: A ≈ 78 miljoner', 'Indikativ medelnivå: aktivitet ≈ 78 miljoner'),
    ('En BAUTA och en EFTA rörs inte.', 'En BAUTA och en EFTA rörs inte.'),
])
def test_the_working_vocabulary_is_put_in_words(raw, shown):
    assert _plain(raw) == shown


@pytest.mark.parametrize('name', ['rapport.resecentrum.md', 'evidens.resecentrum.md'])
def test_a_real_run_shows_none_of_it(name):
    raw = (FIX / name).read_text(encoding='utf-8')
    shown = _plain(raw)
    pattern = (r'\bBAU\b|ΔA\b|ΔEF\b|\bA0\b|\bEF0\b|\bEF\b|Scenario_|ΔE_|\b\d+(?:,\d+)?e\d+\b|\bCoVe\b|\bg_(?:A|EF)\b'
               r'|_BAU\b|tailpipe|utan åtgärden utan åtgärd|ett läget|åtgärden-')
    # Control: the run had them.
    assert len(re.findall(pattern, raw)) > 20
    assert not re.findall(pattern, shown), re.findall(r'.{0,25}(?:' + pattern + r').{0,25}', shown)[:5]
    # Every library code the run cites is shown by name.
    for code in ('EF_passenger_car_avg', 'TR_mode_share_car', 'KOMM_typical_reach_share_general'):
        if code in raw:
            assert code not in shown


def test_the_mechanism_is_read_from_the_worded_line():
    out = _run('emapMechanism("Shift, ändrad aktivitet: färre bilresor.")')
    assert out == {'name': 'Byta (Shift)', 'what': 'mängden', 'rest': 'färre bilresor.'}
    out = _run('emapMechanism("Improve, ändrad utsläppsfaktor: elbilar.")')
    assert out['what'] == 'utsläppen per enhet'


def test_the_card_shows_each_number_with_its_range():
    from test_key_points import _inline_script
    js = _inline_script()
    i, j = js.index('function rangeText('), js.index('function renderKalkylHero(')
    helpers = ('function fmt(n){return String(n).replace(".", ",");}'
               'function yearSpan(a,b){return a===b?String(a):a+"–"+b;}')
    import os
    import subprocess
    import tempfile
    prog = helpers + js[i:j] + """
console.log(JSON.stringify([
  heroFigures({net: 42, year: 2030}, {avg_net: 37, avg_lo: 5, avg_hi: 99, cum_net: 187, cum_lo: 26, cum_hi: 496,
               target_year: 2030}, 7.6, 120, [2026, 2030]),
  heroFigures({net: 42, year: 2030}, {avg_net: 37, cum_net: 187, target_year: 2030}, 7.6, 120, [2026, 2030]),
  heroFigures({net: -3, year: 2030}, {cum_net: -10, cum_lo: -20, cum_hi: 4, target_year: 2030}, -8, 2, []),
]));"""
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(prog)
    try:
        out = json.loads(subprocess.run(['node', f.name], check=True, capture_output=True, text=True).stdout)
    finally:
        os.unlink(f.name)
    full, old, negative = out
    for text in ('Spann 2030', '7,6–120', 'Snitt per år 2026–2030', '>37 <', 'spann 5–99',
                 'Sammanlagt till 2030', '>187 <', 'spann 26–496'):
        assert text in full, text
    # A saved analysis without the two new ranges: the numbers, no empty "spann".
    assert 'Snitt per år' in old and 'spann' not in old
    # Negative ranges read in words, low first.
    assert '-8 till 2' in negative and 'spann -20 till 4' in negative
