# Baslinje & BAU-analys för åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

## Kort om detta steg
Jag utgår från de tre EMAP-drivarna och sätter en nulägesbaslinje för varje drivare, med aktivitet (A0) och emissionsfaktor (EF0). Därefter definierar jag ett BAU-scenario utan åtgärden för 2026 och 2030. Inga åtgärdseffekter beräknas här. Nästa agent (Evidens & Antaganden) använder resultatet för att koppla på åtgärdens påverkan (ΔA, ΔEF, adoption). Eftersom det saknas lokala data för renoveringsvolym, materialmängder och avfall bygger baslinjen på antaganden från åtgärdsprofilen och generella typvärden. Kvaliteten är därför låg.

## Underlag från EMAP
EMAP-steget gav tre drivare. Drivare 1 gäller nyproducerat byggmaterial (sektor byggnader, kommunens egna utsläpp, utanför kommunen). Drivare 2 gäller bygg- och rivningsavfall (sektor avfall, territoriella utsläpp). Drivare 3 gäller demontering, rekonditionering och transport av återbrukat material (sektor transport, territoriella utsläpp, motverkande effekt). Drivare 1 har hög överlapp_risk mot generella klimatkrav i byggupphandling och mot kommunens konsumtionsmål. Drivare 2 har medelhög överlapp_risk mot avfallsplanens återbruksmål. Gemensamma antaganden från profilen:
- Renoveringsvolymen är cirka 15 000 m² BTA/år (spann 10 000–20 000).
- Nuvarande återbruksandel är cirka 0–5 % (här 2,5–3 %).
- Måttet för de 20 % är materialvikt, exklusive bärande stomme och mark.

## Nulägesbaslinje per drivare

Drivare 1: Nyproducerat byggmaterial vid kommunens större renoveringar
  Nuläge_år: 2023 (referensår enligt parameterbiblioteket)
  A0: cirka 2 900 (nyproducerat material; totalt materialflöde cirka 3 000 ton/år varav cirka 3 % redan är återbruk)
  A0_enhet: ton/år
  EF0: 0,5 (spann 0,3–0,8)
  EF0_enhet: kg CO2e/kg material (A1–A3)
  Källor_nuläge: Ingen parameter för byggmaterial finns i parameterbiblioteket. Skalning från antagen renoveringsvolym (15 000 m² BTA/år, enligt åtgärdsprofilen) × antagen materialintensitet (cirka 200 kg/m², ombyggnad exklusive stomme) × antagen klimatpåverkan för ombyggnad (cirka 100 kg CO2e/m², A1–A3). Det ger cirka 1 450 ton CO2e/år (spann 700–3 000). Rimlighetskontroll mot DATA_MUNICIPAL_ORG (2022): kommunkoncernens kategori "Fastigheter & Anläggningsarbeten" är 70 918 ton och "Husbyggande" 37 749 ton. Renoveringsmaterialet utgör alltså cirka 2 % av kategorin, vilket är rimligt eftersom bolag, nyproduktion och anläggning dominerar. Kopplad till DATA_MUNICIPAL_ORG.
  Kommentar_nuläge: Mycket grov uppskattning (kvalitet låg). Materialintensitet, klimatpåverkan per m² och volym är antaganden. Spannet är stort, särskilt för klimatpåverkan per m². Utsläppen är kommunens egna indirekta (scope 3) och uppstår utanför kommunen. Nästa agent bör därför undvika att dubbelräkna mot Konsumtionskompassens nivåer eller kommunens samlade bygg-kategori.

Drivare 2: Bygg- och rivningsavfall från kommunens större renoveringar
  Nuläge_år: 2023
  A0: cirka 1 500 (cirka 100 kg avfall per m² renoverad yta)
  A0_enhet: ton/år
  EF0: 50 (spann 20–120)
  EF0_enhet: kg CO2e/ton avfall
  Källor_nuläge: Ingen parameter för byggavfall finns i parameterbiblioteket. Skalning från antagen renoveringsvolym och typvärde för avfall per m² vid ombyggnad. EF0 är en uppskattning med antagen fördelning: cirka 15 % brännbart (fossil andel), cirka 5 % deponi och resten materialåtervinning med transport och bearbetning. Det ger cirka 75 ton CO2e/år. Rimlighetskontroll mot localData: "Avfall (inkl. avlopp)" är 7 484 ton CO2e år 2023, varav "Avfallsdeponier" 3 159 ton. Drivaren är alltså mycket liten i det territoriella sammanhanget.
  Kommentar_nuläge: Kvalitet låg. Avfallsfraktioner och behandlingsväg är antagna. Förbränningsutsläpp kan i den territoriella statistiken redovisas under "El och fjärrvärme" i stället för "Avfall". Det är oklart var avfallet behandlas, och om det sker utanför kommunen flyttas utsläppen dit.

Drivare 3: Demontering, rekonditionering, lagring och transport av återbrukat material (motverkande effekt)
  Nuläge_år: 2023
  A0: cirka 2 000 (cirka 75 ton återbrukat material × cirka 30 km genomsnittlig transportsträcka)
  A0_enhet: tonkm/år
  EF0: 0,15 (spann 0,06–0,25)
  EF0_enhet: kg CO2e/tonkm
  Källor_nuläge: EF_freight_truck_tonkm (standardvärde 0,06–0,12 kg CO2/tonkm, tung lastbil). Jag har valt ett högre värde, 0,15, eftersom återbruksflöden går med små last- och skåpbilar med låg lastfaktor. A0 är skalat från antagen nuvarande återbruksandel (cirka 2,5–3 % av cirka 3 000 ton). Det ger cirka 0,3 ton CO2e/år. Rimlighetskontroll mot localData: "Lätta lastbilar" är 13 409 ton CO2e (2023) och "Tunga lastbilar" 23 635 ton CO2e (2023).
  Kommentar_nuläge: Kvalitet låg, men nivån är i dag försumbar. Energi för rekonditionering och lagring (kWh/år) är inte kvantifierad i baslinjen. Om den behövs kan den skalas med EF_district_heat_Karlstad_2023 (19 g CO2e/kWh) och EF_el_SE_consumption_2020s (40–60 g CO2e/kWh), enligt konsumtionsbaserad hantering av energi. Drivaren kan delvis ingå i kommunens övriga transportbaslinje (överlapp, låg).

## BAU-scenario per drivare
Tolkning av låg/medel/hög för alla drivare: låg är det scenario som ger lägst utsläpp i BAU, det vill säga det lägsta värdet på trenden. Hög ger högst utsläpp. Trenderna gäller årlig procentuell förändring från 2023.

Drivare 1: Nyproducerat byggmaterial vid kommunens större renoveringar
  BAU_Tier: 2
  BAU_motivering: Policy- och teknikdriven utveckling av EF (fossilfritt stål, lägre klinkerandel i cement, elektrifierade byggmaterialprocesser). Historiska tidsserier för A och EF saknas för kommunens renoveringar, så Tier 1 går inte att tillämpa. A hålls nära konstant (Tier 0-lik).
  BAU_trend_A (g_A):
    - låg: -2 %/år, något färre renoveringar och mer spontant återbruk
    - medel: -0,5 %/år, i praktiken stabil volym med liten ökning av spontant återbruk
    - hög: +1,5 %/år, ökat renoveringsbehov i äldre bestånd och högre byggkostnader per m²
  BAU_trend_EF (g_EF):
    - låg: -3 %/år, snabb utfasning av fossila processer i stål och cement
    - medel: -2 %/år, gradvis lägre klimatpåverkan hos standardmaterial
    - hög: -1 %/år, långsam omställning och begränsad leverans av lågklimatmaterial
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Boverkets klimatkrav gäller inte renoveringar, så inget lagkrav påverkar BAU direkt. Medelscenariot ger ungefär 1 350 ton CO2e/år 2026 och cirka 1 200 ton 2030 (A cirka 2 850 respektive 2 800 ton, EF cirka 0,47 respektive 0,43). BAU ska inkludera nuvarande låga återbruksandel (cirka 0–5 %), så att bara ökningen mot 20 % räknas som åtgärdseffekt. Beslutade men ej genomförda kommunala krav i bygg ingår inte.

Drivare 2: Bygg- och rivningsavfall från kommunens större renoveringar
  BAU_Tier: 1
  BAU_motivering: Historiska utsläppsserier för avfall finns i localData. Avfall totalt (inkl. avlopp) minskade från 8 093 till 7 484 ton CO2e 2021–2023 (cirka -4 %/år), och deponier från 3 687 till 3 159 ton (cirka -7 %/år). Dessa används som stöd för EF-trenden. Kommunens egen avfallsmängd per renovering saknar tidsserie, så A hålls nära konstant.
  BAU_trend_A (g_A):
    - låg: -1 %/år, något färre renoveringar eller bättre materialhushållning
    - medel: 0 %/år, stabil mängd avfall
    - hög: +1,5 %/år, ökad renoveringsvolym
  BAU_trend_EF (g_EF):
    - låg: -4 %/år, i linje med historisk minskning i kommunens avfallssektor
    - medel: -2 %/år, lägre fossil andel i brännbart avfall och mindre deponering
    - hög: 0 %/år, ingen förbättring
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger cirka 70 ton CO2e/år 2026 och cirka 65 ton 2030 (A cirka 1 500 ton, EF cirka 47 respektive 43). Utsläppsnivån är liten, så osäkerheten har begränsad betydelse för totalen. Trenden kan överlappa med avfallsplanens mål, vilket nästa agent bör hantera.

Drivare 3: Demontering, rekonditionering, lagring och transport av återbrukat material
  BAU_Tier: 2
  BAU_motivering: Policy- och teknikdriven EF-minskning för lastbilstransporter (elektrifiering, reduktionsplikt, biodrivmedel). Stöd i localData: tunga lastbilar 27 182 → 23 635 ton CO2e (cirka -7 %/år 2021–2023), lätta lastbilar 15 096 → 13 409 ton (cirka -6 %/år). A utvecklas långsamt med nuvarande återbruksnivå.
  BAU_trend_A (g_A):
    - låg: 0 %/år, ingen ökning av återbruk utan krav
    - medel: +3 %/år, långsamt ökande återbruksintresse
    - hög: +6 %/år, tydligare marknad för återbruk
  BAU_trend_EF (g_EF):
    - låg: -6 %/år, snabb elektrifiering av distributionsfordon
    - medel: -4 %/år, stadig minskning med biodrivmedel och fler elfordon
    - hög: -2 %/år, långsam fordonsomställning
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger cirka 2 200 tonkm/år 2026 och cirka 2 500 tonkm 2030, med EF på cirka 0,13 respektive 0,11 kg CO2e/tonkm. Utsläppen är därmed omkring 0,3 ton CO2e/år i hela perioden. Den motverkande effekten blir viktig först när åtgärden ökar mängden återbrukat material, vilket behandlas i nästa steg. Rekonditionering och lagring ingår inte i BAU-trenden.

## Dataluckor för detta steg
- Saknar uppgifter om planerade renoveringsprojekt per år (antal, m² BTA, budget) för 2026–2030. Volymen 15 000 m²/år är ett antagande (spann 10 000–20 000).
- Saknar materialintensitet per m² (kg/m²) och klimatpåverkan per m² (kg CO2e/m²) för kommunens renoveringar. Båda är generella typvärden. Klimatpåverkan per m² är störst osäkerhet (spann cirka 50–200 kg CO2e/m²).
- Saknar avgränsning av "större renovering" och exakt definition av hur de 20 % mäts, vilket påverkar vilket material som ingår i A0.
- Saknar uppgifter om nuvarande återbruksandel och materialflöden via internt lager eller plattform. 0–5 % är ett antagande.
- Saknar uppgifter om mängd, fraktioner och behandling av bygg- och rivningsavfall från kommunens renoveringar, och var avfallet behandlas (inom eller utanför kommunen).
- Saknar lokal transportdata (avstånd, fordonstyp, lastfaktor) för återbruksmaterial, samt energidata för rekonditionering och lagring.
- Parameterbiblioteket saknar parametrar för byggmaterial och byggavfall. Underlag från Boverkets klimatdatabas, Naturvårdsverket och IVL är inte inlagda.
- Oklart hur de territoriella utsläppen från avfallsförbränning allokeras i SMHI/RUS-statistiken (sektor avfall eller el och fjärrvärme).
- Trenderna för EF i byggmaterial bygger på generella branschtrender och inte på kommunspecifika data.

## Frågor till miljöstrateg för detta steg
- Finns investeringsplan eller lokalförsörjningsplan med planerade renoveringar 2026–2030 (antal, m², Mkr) som kan ersätta volymantagandet?
- Finns klimatberäkningar eller materialinventeringar från tidigare renoveringar i kommunen som kan ge kg/m² och kg CO2e/m²?
- Finns det i dag uppgifter om hur mycket material som återbrukas (internt lager, plattform) och i så fall hur mycket?
- Ska utsläppen från drivare 1 redovisas som en del av kommunkoncernens egna konsumtionsbaserade utsläpp (DATA_MUNICIPAL_ORG, kategori Fastigheter & Anläggningsarbeten) och undantas från den territoriella kalkylen för att undvika dubbelräkning?
- Ska BAU för drivare 2 följa nationella eller lokala prognoser för behandling av byggavfall, och var behandlas kommunens byggavfall i dag?
- Vilket basår ska användas om kommunens egna data finns för 2022 men antagandena här är satta till 2023?