Baslinje & BAU-analys för åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

**Kort om detta steg**
Jag utgår från de tre EMAP-drivarna och sätter en nulägesbaslinje per drivare, med aktivitet (A0) och emissionsfaktor (EF0). Därefter definierar jag ett BAU-scenario utan kravet till 2026 och 2030, med trendintervall för aktivitet (g_A) och emissionsfaktor (g_EF). Inga åtgärdseffekter beräknas här. Resultatet används av Evidens & Antaganden-agenten för att koppla på åtgärdens påverkan. Eftersom parameterbiblioteket saknar byggmaterialfaktorer är baslinjen en grov ordningsnivåuppskattning (kvalitet låg).

**Underlag från EMAP**
Tre drivare ingår: nyproducerat byggmaterial (byggnader, konsumtionsbaserat, utanför kommunen), återbruksledet (transport, lagring och rekonditionering, konsumtionsbaserat) och byggavfall (avfall, territoriellt, inom kommunen). Omfattningen är ANTAGANDE från profilen: cirka 4 projekt och 20 000 m² BTA per år under 2027–2030. Drivare 1 har den klart största utsläppsvolymen. Överlappsrisken är medel för drivare 1 och 3 (generella klimatkrav i byggupphandling, cirkulär upphandling och avfallsminskning) och låg för drivare 2.

**Nulägesbaslinje per drivare**

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  Nuläge_år: 2023 (referensår enligt parameterbiblioteket; volymen är ett ANTAGANDE för projekt som skulle omfattas av kravet)
  A0: cirka 3 900 ton/år nyproducerat material. Det motsvarar 20 000 m² × cirka 200 kg/m² = 4 000 ton totalt materialbehov, minus cirka 3 % redan återbrukat (ANTAGANDE).
  A0_enhet: ton/år
  EF0: 0,6
  EF0_enhet: kg CO2e/kg material (viktat snitt för typisk renoveringsmix: gips, undertak, golv, dörrar, inredning och installationer; ANTAGANDE)
  Källor_nuläge: Ingen parameter i biblioteket för byggmaterial. Omfattningen kommer från åtgärdsprofilen (ANTAGANDE). Rimlighetskontroll mot DATA_MUNICIPAL_ORG (2022): Husbyggande 37 749 ton CO2e och Specialiserade bygg- och anläggningstjänster 14 220 ton CO2e för hela kommunkoncernen. EF0 är ett generellt typvärde för tillverkningsfasen (A1–A3).
  Kommentar_nuläge: Implicerade utsläpp är cirka 2 300 ton CO2e/år (spann cirka 1 500–4 000). Det är cirka 4–5 % av koncernens bygg-relaterade utsläpp, vilket är rimligt för enbart material i renoveringar av förvaltningslokaler. Materialintensiteten (150–300 kg/m²) och EF-spannet (0,3–1,0) är osäkra. Kvalitet: låg.

Drivare 2: Transport, lagring och rekonditionering av återbrukat material
  Nuläge_år: 2023 (ANTAGANDE)
  A0: cirka 120 ton/år hanterat återbrukat material (3 % av 4 000 ton), motsvarande cirka 6 000 tonkm/år vid 50 km snittavstånd (ANTAGANDE)
  A0_enhet: ton/år (tonkm/år där relevant)
  EF0: 0,05
  EF0_enhet: kg CO2e/kg material. Transporten är cirka 0,005 kg/kg (0,09 kg CO2/tonkm × 50 km) och rekonditionering, lagring och hantering cirka 0,045 kg/kg (ANTAGANDE).
  Källor_nuläge: EF_freight_truck_tonkm (0,06–0,12 kg CO2/tonkm; 0,09 använt), EF_diesel_tank_to_wheel (kontroll). Återbruksandel och avstånd är ANTAGANDEN.
  Kommentar_nuläge: Implicerade utsläpp är bara cirka 6 ton CO2e/år, eftersom nuvarande återbruk är litet. Rekonditioneringsdelen saknar källa. Parameterbibliotekets transportfaktor avser CO2, inte CO2e. Skillnaden är liten här. Kvalitet: låg.

Drivare 3: Byggavfall från renoveringar
  Nuläge_år: 2023 (ANTAGANDE)
  A0: cirka 600 ton/år avfall till förbränning och deponi. Det motsvarar cirka 60 kg avfall/m² × 20 000 m² = 1 200 ton, varav cirka 50 % inte går till materialåtervinning (ANTAGANDE).
  A0_enhet: ton/år
  EF0: 0,25
  EF0_enhet: kg CO2e/kg avfall (viktat snitt för brännbart avfall med fossil andel, plast och deponi; ANTAGANDE)
  Källor_nuläge: DATA_EMISSIONS_TOTAL (localData): Avfallsdeponier 3 687 / 3 426 / 3 159 ton CO2e (2021–2023) och Avfall totalt 7 484 ton CO2e 2023, som sanity-check. Mängd och faktor är ANTAGANDEN. Ingen motsvarande parameter i biblioteket.
  Kommentar_nuläge: Implicerade utsläpp är cirka 150 ton CO2e/år. Utsläpp från avfallsförbränning redovisas oftast i sektorn El och fjärrvärme, inte i Avfall, vilket påverkar vad som syns som territoriell effekt. Drivaren är liten jämfört med drivare 1. Kvalitet: låg.

**BAU-scenario per drivare**

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  BAU_Tier: 2
  BAU_motivering: Policy-justerad trend för EF: obligatoriska klimatdeklarationer för byggnader, planerade gränsvärden och omställning i stål- och cementindustrin ger lägre klimatintensitet. A hålls i huvudsak konstant, med en liten minskning av nytt material eftersom återbruk ökar även utan kravet.
  BAU_trend_A (g_A):
    - låg: -2 %/år (lägre renoveringstakt vid ansträngd kommunekonomi, och något mer återbruk ändå)
    - medel: -0,5 %/år (konstant yta och återbruk som stiger från cirka 3 % till cirka 5 % till 2030)
    - hög: +1,5 %/år (ökad renoveringstakt på grund av underhållsskuld i beståndet)
  BAU_trend_EF (g_EF):
    - låg: -1 %/år (långsam omställning för inredning och finmaterial)
    - medel: -2 %/år (klimatdeklarationer och gradvis fossilfri stål- och cementproduktion)
    - hög: -3,5 %/år (snabbare introduktion av lågklimatmaterial)
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger cirka 3 840 ton och EF cirka 0,57 kg/kg 2026 (cirka 2 170 ton CO2e). År 2030 ger det cirka 3 770 ton och EF cirka 0,52 kg/kg (cirka 1 960 ton CO2e). Renoveringsvolymen antas inte påverkas av kravet. Elmixen (EF_el_SE_consumption_2030_BAU, 20–40 g CO2e/kWh) bidrar till lägre EF, men effekten ligger i EF-trenden och dubbelräknas inte.

Drivare 2: Transport, lagring och rekonditionering av återbrukat material
  BAU_Tier: 2
  BAU_motivering: A växer långsamt när återbruksmarknaden mognar (plattformar som CCBuild, nationella cirkularitetsmål). EF minskar med elektrifierade tunga transporter och reduktionsplikt för drivmedel.
  BAU_trend_A (g_A):
    - låg: 0 %/år (ingen marknadsutveckling utan krav)
    - medel: +2 %/år (gradvis ökat frivilligt återbruk)
    - hög: +5 %/år (snabbare marknadsutveckling)
  BAU_trend_EF (g_EF):
    - låg: -2 %/år (reduktionsplikt, i huvudsak fossildiesel kvar)
    - medel: -4 %/år (blandning av biodrivmedel och elektrifiering)
    - hög: -7 %/år (snabb elektrifiering av lokala godstransporter)
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger cirka 138 ton och EF cirka 0,038 kg/kg 2030 (cirka 5 ton CO2e). Nivån är så låg att BAU-osäkerheten i absoluta tal är liten. Rekonditioneringsandelen av EF antas följa elmixen och kan sjunka något snabbare. Detta ingår inte i trenden.

Drivare 3: Byggavfall från renoveringar
  BAU_Tier: 1
  BAU_motivering: Enkel trend för EF utifrån lokala deponidata 2021–2023 (cirka -7 %/år för deponiutsläpp). Eftersom drivaren är blandad mellan förbränning och deponi dämpas trenden i det viktade EF. A hålls nära konstant, med viss minskning genom bättre källsortering.
  BAU_trend_A (g_A):
    - låg: -3 %/år (bättre källsortering, mer materialåtervinning)
    - medel: -1 %/år (successivt skärpt avfallshantering)
    - hög: +1 %/år (ökad renoveringstakt)
  BAU_trend_EF (g_EF):
    - låg: -1 %/år (fortsatt hög fossil andel i förbränning)
    - medel: -3 %/år (lägre deponiutsläpp och sjunkande fossil plastandel)
    - hög: -6 %/år (deponi nästan utfasad och mer sortering)
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger cirka 559 ton och EF cirka 0,20 kg/kg 2030 (cirka 113 ton CO2e). Territoriell avfallsprofil begränsas av att förbränningsutsläpp hamnar i El och fjärrvärme (se nuläge). Fjärrvärmens lokala EF (EF_district_heat_Karlstad_2024, 10 g CO2e/kWh) har stor betydelse för hur utsläppen redovisas.

**Dataluckor för detta steg**
- Saknar faktisk renoveringsvolym (antal projekt, m² BTA och investeringsvolym 2019–2024) från fastighetsförvaltningen. Hela baslinjen bygger på antaganden.
- Saknar materialinventeringar och mängd material per m² (kg/m²) och materialkategori för typiska renoveringar.
- Saknar emissionsfaktorer per materialkategori (EPD eller generiska data, till exempel Boverkets klimatdatabas). Parameterbiblioteket innehåller ingen sådan parameter.
- Saknar uppgift om nuvarande återbruksandel (antaget cirka 3 % i vikt) och erfarenheter från CCBuild eller andra plattformar.
- Saknar faktisk avfallsstatistik för kommunens renoveringar (kg/m² och behandlingsväg).
- Saknar data om transportavstånd och rekonditionering för återbrukat material.
- Oklart om kommunens egna konsumtionsbaserade utsläpp (DATA_MUNICIPAL_ORG, 2022) redovisar inköp av byggmaterial på ett sätt som matchar drivarnas systemgräns.
- Parameterbibliotekets EF_freight_truck_tonkm avser CO2, inte CO2e. Skillnaden bedöms som liten här.

**Frågor till miljöstrateg för detta steg**
- Kan fastighetsförvaltningen lämna faktiska uppgifter för renoveringsvolym, materialinventeringar och nuvarande återbruksandel, eller ska vi behålla antagandena?
- Ska BAU utgå från nationella trender (till exempel klimatdeklarationer och material-EF) eller lokala scenarier för byggmaterial?
- Ska utsläpp från avfallsförbränning kopplas till territoriell sektor Avfall eller El och fjärrvärme i klimatplanen?
- Vilket basår ska användas för kommunens egna klimatbokslut, 2022 (DATA_MUNICIPAL_ORG) eller 2023 (parameterbiblioteket)?
- Ska även skärpta klimatkrav i byggupphandling eller annan cirkulär upphandling som redan är beslutad ingå i BAU, för att undvika dubbelräkning?