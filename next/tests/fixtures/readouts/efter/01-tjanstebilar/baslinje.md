---
Baslinje & BAU-analys för åtgärd: Krav på laddbara tjänstebilar

**Kort om detta steg**
Jag utgår från de tre godkända EMAP-drivarna och sätter en nulägesbaslinje (aktivitet A0 och emissionsfaktor EF0) för varje drivare. Därefter definierar jag ett BAU-scenario utan åtgärden till 2026 och 2030. Inga åtgärdseffekter beräknas här. Resultatet används i nästa steg för att koppla på åtgärdens effekter och antaganden. Referensår för parametrarna är 2023. Procentsatserna för trend gäller från nuläget (2023) till 2026 och 2030, om inget annat anges.

**Underlag från EMAP**
Tre drivare ingår: fossil körsträcka med tjänstebilar (transport, kommunens egna utsläpp), elanvändning för laddning (energi, konsumtionsbaserat) och fordons- och batteritillverkning (konsumtion, konsumtionsbaserat). Overlapp_risk är medel för drivare 1 och 2, eftersom samma minskning kan räknas som territoriellt och konsumtionsbaserat, och låg för drivare 3. Elanvändningen för tjänstebilarna ska räknas bara här och inte i Åtgärdsprofil 2.

**Nulägesbaslinje per drivare**

Drivare 1: Körsträcka med fossildrivna tjänstebilar (bensin/diesel)
  Nuläge_år: 2023 (referensår, flottan antas oförändrad fram till 2026)
  A0: 2,16e6 fordonskilometer (180 bilar × 12 000 km/bil, år)
  A0_enhet: km/år
  EF0: 0,13
  EF0_enhet: kg CO2e/km
  Källor_nuläge: EF_passenger_car_avg (0,12–0,18 kg CO2/km, nedre delen eftersom tjänstebilar är nyare än snittflottan), EF_petrol_tank_to_wheel (2,3–2,4 kg CO2/liter), EF_diesel_tank_to_wheel (2,6–2,7 kg CO2/liter). Kontroll: cirka 5–6 liter/100 km ger 0,13–0,14 kg/km. Körsträcka 1 200 mil/år och 180 bilar kommer från godkänd åtgärdsprofil.
  Kommentar_nuläge: Antagandet är att de 180 bilarna är fossildrivna vid start. Den uppskattade nivån är cirka 280 ton CO2/år, vilket är ungefär 0,35 % av personbilarnas territoriella utsläpp (79 454 ton, 2023). Ingen avdragen inblandning av biodrivmedel, så EF0 är fossil tank-to-wheel. Kvalitet: låg till medel. Parametern EF_municipal_cars_avg (0–0,05) anger att kommunens bilar är el eller gas, vilket strider mot antagandet om fossilflotta. Se dataluckor.

Drivare 2: Elanvändning för laddning av tjänstebilar
  Nuläge_år: 2023 (referensår)
  A0: cirka 0 kWh/år i nuläget (inga av de 180 bilarna är laddbara, ANTAGANDE). Referensnivå vid full eldrift av samma körsträcka: 4,1e5 kWh/år (2,16e6 km × 0,19 kWh/km)
  A0_enhet: kWh/år
  EF0: 0,050 (intervall 0,040–0,060)
  EF0_enhet: kg CO2e/kWh
  Källor_nuläge: EF_el_SE_consumption_2020s (40–60 g CO2e/kWh, nationell konsumtionsmix enligt energiregeln). EF_el_Karlstad_product_guaranteed (0 g) används inte, eftersom andelen ursprungsmärkt el (EL_share_customers_guaranteed) är okänd och konsumtionsbaserad mix är huvudspår. 0,19 kWh/km inklusive laddförluster är ett ANTAGANDE (intervall 0,17–0,22). EF_ev_per_km (0,02–0,05 kg CO2/km) används som rimlighetskontroll.
  Kommentar_nuläge: Faktisk A0 är cirka noll och referensnivån är bara en storleksordning för nästa steg. Biblioteksvärdet EF_ev_per_km (0,02–0,05 kg/km) är högre än elmix × kWh/km (cirka 0,01 kg/km). Jag använder elmix per kWh, i linje med EMAP-enheten. Kvalitet: låg till medel.

Drivare 3: Fordons- och batteritillverkning för nyanskaffade elbilar
  Nuläge_år: 2022 (kommunkoncernens inköpsdata) och 2023 (referensår)
  A0: 60 fordon/år (ersättningstakt enligt profilen, motsvarar cirka 3 års leasingcykel för 180 bilar)
  A0_enhet: fordon/år
  EF0: 7 000 (intervall 6 000–8 000) för en fossildriven personbil. Referensvärde för elbil: cirka 11 000 kg (intervall 9 000–14 000).
  EF0_enhet: kg CO2e/fordon
  Källor_nuläge: DATA_MUNICIPAL_ORG (Motorfordon, släpfordon och påhängsvagnar: 1 665 ton CO2e, hela koncernen 2022). Generella LCA-typvärden för livscykelutsläpp vid tillverkning, ingen parameter i biblioteket.
  Kommentar_nuläge: Parameterbiblioteket saknar tillverkningsfaktorer, så värdena är schabloner. Kontroll: 60 bilar × 7 ton är cirka 420 ton, ungefär 25 % av koncernens 1 665 ton, vilket är rimligt eftersom även lastbilar och specialfordon ingår där. Kvalitet: låg.

**BAU-scenario per drivare**

Drivare 1: Körsträcka med fossildrivna tjänstebilar (bensin/diesel)
  BAU_Tier: 2
  BAU_motivering: Policy- och marknadsjusterad. Kommunens miljöambitioner och elbilsutvecklingen (TR_share_evs_new_sales cirka 30 % BEV 2023) gör att en del av de naturliga leasingbytena blir elbilar även utan kravet.
  BAU_trend_A (g_A):
    - låg: −8 %/år för 2026→2030 (30 % av bytena 2027–2029 blir el, fossil körsträcka −30 % till 2030)
    - medel: −18 %/år (55 % el, fossil körsträcka −55 %)
    - hög: −33 %/år (80 % el, fossil körsträcka −80 %)
    - Perioden 2023→2026 sätts till 0 %/år, eftersom gruppen definieras som fossildrivna bilar vid start 2027. Total körsträcka per bil hålls konstant (±1 %/år).
  BAU_trend_EF (g_EF):
    - låg: −0,5 %/år, begränsad teknikförbättring och svag biodrivmedelsinblandning
    - medel: −1,5 %/år, effektivare nya bensin- och dieselbilar samt reduktionsplikt
    - hög: −3 %/år, mer hybridisering och högre inblandning av biodrivmedel
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: BAU-andelen el är det viktigaste antagandet och ett ANTAGANDE. Det saknas lokal leasinghistorik. Efter 2029 byts de nya bilarna inte ut under BAU-perioden.

Drivare 2: Elanvändning för laddning av tjänstebilar
  BAU_Tier: 2
  BAU_motivering: Följer drivare 1 (naturlig elektrifiering) och renare svensk elmix (EF_el_SE_consumption_2030_BAU, 20–40 g).
  BAU_trend_A (g_A):
    - låg: ökning från noll går inte att uttrycka som %/år. Anges i stället som andel av referensnivån 4,1e5 kWh/år: ca 0 % 2026 och 30 % 2030 (cirka 1,2e5 kWh/år)
    - medel: ca 0 % 2026 och 55 % 2030 (cirka 2,3e5 kWh/år)
    - hög: ca 0 % 2026 och 80 % 2030 (cirka 3,3e5 kWh/år)
  BAU_trend_EF (g_EF):
    - låg: −3 %/år (mot cirka 40 g/kWh 2030)
    - medel: −7 %/år (mot cirka 30 g/kWh 2030)
    - hög: −12 %/år (mot cirka 20 g/kWh 2030)
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: A kopplas direkt till bortfallen fossil körsträcka i drivare 1 (BAU-elandelen × 2,16e6 km × 0,19 kWh/km). Elmixen är nationell konsumtionsbaserad mix, inte Karlstads ursprungsmärkta produkt.

Drivare 3: Fordons- och batteritillverkning för nyanskaffade elbilar
  BAU_Tier: 1
  BAU_motivering: Enkel trend. Bytestakten är stabil (leasingcykel), men tillverkningsutsläppen per fordon sjunker med renare batteriproduktion. Någon lokal tidsserie finns inte, så trenden bygger på generella antaganden.
  BAU_trend_A (g_A):
    - låg: −2 %/år, förlängda leasingperioder
    - medel: 0 %/år, 60 fordon/år i konstant takt
    - hög: +2 %/år, kortare leasingperioder
  BAU_trend_EF (g_EF):
    - låg: 0 %/år, ingen förbättring av tillverkningsutsläppen per fordonstyp
    - medel: −1 %/år, renare stål- och batteriproduktion
    - hög: −2 %/år, snabbare avkarbonisering av batteritillverkning
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Trenden gäller per fordonstyp. Effekten av att andelen elbilar ökar i BAU hanteras via elandelen (drivare 1) och bör läggas på i nästa steg.

**Dataluckor för detta steg**
- Saknar fordonsregister eller fleet management-data för de 180 bilarna (drivmedel, faktisk körsträcka, leasingperioder). Körsträcka 12 000 km/år och fossilflotta är antaganden.
- Parametern EF_municipal_cars_avg (kommunens bilar är el eller gas) strider mot antagandet att de 180 bilarna är fossildrivna. Faktisk flottsammansättning behöver verifieras.
- Andelen biodrivmedel i drivmedel och därmed fossil EF0 är okänd. Reduktionspliktens nivå efter 2026 är osäker.
- Saknar lokal historik över andelen elbilar vid leasingbyten, vilket avgör BAU-elandelen (30/55/80 %).
- Elförbrukning per km (0,19 kWh/km) och elmixens lokala andel ursprungsmärkt el (EL_share_customers_guaranteed) är okända.
- Biblioteket saknar tillverkningsfaktorer per fordon. EF0 för drivare 3 är en schablon med låg kvalitet.
- Biblioteksvärdet EF_ev_per_km är inkonsekvent med elmixparametrarna (se drivare 2).

**Frågor till miljöstrateg för detta steg**
- Stämmer det att de 180 tjänstebilarna idag är fossildrivna, trots att biblioteket anger att kommunens bilar är el eller gas?
- Vilken BAU-andel el vid leasingbyten ska användas (30, 55 eller 80 %)?
- Ska nationell konsumtionsbaserad elmix eller kommunens ursprungsmärkta el användas för laddningen?
- Ska tillverkningsutsläpp (drivare 3) ingå i huvudberäkningen eller redovisas separat?

---
Baslinje & BAU-analys för åtgärd: Laddinfrastruktur vid kommunala arbetsplatser

**Kort om detta steg**
Jag utgår från de tre godkända EMAP-drivarna och sätter en nulägesbaslinje (A0 och EF0) för varje drivare. Därefter definierar jag ett BAU-scenario utan åtgärden till 2026 och 2030. Inga åtgärdseffekter beräknas. Resultatet används i nästa steg för att koppla på åtgärdens effekter och antaganden. Referensår är 2023, och trenderna gäller från 2023 till 2026 och 2030.

**Underlag från EMAP**
Tre drivare ingår: fossil pendling med privata bilar (transport, territoriellt), elanvändning för anställdas laddning (energi, konsumtionsbaserat) och elanvändning för tjänstebilars laddning (energi, enabler). Drivare 3 har hög overlapp_risk och räknas bara i Åtgärdsprofil 1. Den redovisas här endast som referens så att den inte dubbelräknas.

**Nulägesbaslinje per drivare**

Drivare 1: Körsträcka med fossildrivna privatbilar vid pendling till kommunala arbetsplatser
  Nuläge_år: 2023
  A0: 4,2e6 fordonskilometer. Härledning: 1 500 anställda × 55 % bilpendling × 12 km enkel väg × 2 × 220 dagar ≈ 4,36e6 km, varav cirka 96 % fossil.
  A0_enhet: km/år
  EF0: 0,15
  EF0_enhet: kg CO2e/km
  Källor_nuläge: EF_passenger_car_avg (0,12–0,18 kg CO2/km), TR_mode_share_car (53 % hela kommunen, 47 % tätort), TR_median_trip_length_km (5 km alla färdmedel, cirka 7,6 km bil), TR_share_evs_fleet_2030 (Karlstad hade cirka 3–4 % elbilar i trafik 2023), antal anställda från godkänd profil.
  Kommentar_nuläge: Andelen bilpendlare på 55 % och 12 km enkel väg är antaganden. Medianen 7,6 km underskattar medelavståndet, därför används 12 km. Av körsträckan antas cirka 75 % ligga inom kommunen, så territoriell A0 är cirka 3,1e6 km/år. Utsläppsnivån blir cirka 630 ton CO2/år. Kontroll: lokal data ger cirka 0,14 kg/km (79 454 ton / cirka 570 Mkm), vilket stämmer med EF0. Kvalitet: låg.

Drivare 2: Elanvändning för anställdas laddning av privata elbilar
  Nuläge_år: 2023
  A0: cirka 0 kWh/år vid arbetsplatserna i nuläget (ingen utbyggd laddning, ANTAGANDE). Referensnivå: elbehov för elbilspendling totalt 3,3e4 kWh/år (4 % av 4,36e6 km × 0,19 kWh/km), där det mesta laddas hemma.
  A0_enhet: kWh/år
  EF0: 0,050 (intervall 0,040–0,060)
  EF0_enhet: kg CO2e/kWh
  Källor_nuläge: EF_el_SE_consumption_2020s (40–60 g CO2e/kWh, nationell mix), TR_share_evs_fleet_2030 (3–4 % elbilar i trafik 2023).
  Kommentar_nuläge: Referensnivån visar vad som kan flyttas till arbetsplatsen. Hur stor andel av laddningen som sker på arbetsplatsen idag är okänt. Kvalitet: låg.

Drivare 3: Elanvändning för laddning av tjänstebilar vid arbetsplatserna (enabler)
  Nuläge_år: 2023
  A0: cirka 0 kWh/år i nuläget. Referensnivå: cirka 3,7e5 kWh/år (cirka 90 % av 4,1e5 kWh/år för 180 bilar, samma beräkning som Åtgärdsprofil 1, drivare 2).
  A0_enhet: kWh/år
  EF0: 0,050 (intervall 0,040–0,060)
  EF0_enhet: kg CO2e/kWh
  Källor_nuläge: Åtgärdsprofil 1 (drivare 2), EF_el_SE_consumption_2020s.
  Kommentar_nuläge: Redovisas endast som referens. Hela effekten räknas i Åtgärdsprofil 1. Andelen på 90 % som laddas på arbetsplatsen är ett antagande. Kvalitet: låg.

**BAU-scenario per drivare**

Drivare 1: Körsträcka med fossildrivna privatbilar vid pendling till kommunala arbetsplatser
  BAU_Tier: 2
  BAU_motivering: Nationellt beslutade och pågående trender: växande elbilsandel i flottan (TR_share_evs_fleet_2030: 20–40 %), ökande nyförsäljning av elbilar och effektivare fossilbilar.
  BAU_trend_A (g_A):
    - låg: −2,5 %/år (elbilar 20 % av flottan 2030, fossil körsträcka från cirka 96 % till cirka 80 %)
    - medel: −4,5 %/år (30 % elbilar, fossil andel cirka 70 %)
    - hög: −6,5 %/år (40 % elbilar, fossil andel cirka 60 %)
    - Total pendlingskörsträcka antas oförändrad (±1 %/år).
  BAU_trend_EF (g_EF):
    - låg: −1 %/år, effektivare nya fossilbilar
    - medel: −2 %/år, effektivare bilar och reduktionsplikt
    - hög: −3 %/år, mer hybridisering och biodrivmedel
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Procenten tillämpas från 2023 (3 år till 2026, 7 år till 2030). Elbilsandelen i km är något högre än i antal bilar, vilket stöder spannet. Några lokala trender för pendling finns inte.

Drivare 2: Elanvändning för anställdas laddning av privata elbilar
  BAU_Tier: 2
  BAU_motivering: Växande elbilsflotta enligt nationella prognoser och renare elmix.
  BAU_trend_A (g_A):
    - låg: +26 %/år (elbilsandel 4 % → 20 %)
    - medel: +33 %/år (4 % → 30 %)
    - hög: +39 %/år (4 % → 40 %)
    - Gäller den totala elbehov för pendling (referensnivån), inte laddning vid arbetsplatserna.
  BAU_trend_EF (g_EF):
    - låg: −3 %/år (mot cirka 40 g/kWh 2030)
    - medel: −7 %/år (mot cirka 30 g/kWh 2030)
    - hög: −12 %/år (mot cirka 20 g/kWh 2030)
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Procentsatserna är höga eftersom basen är liten. Elmix enligt EF_el_SE_consumption_2030_BAU. Hur stor del som laddas på arbetsplatsen utan åtgärden är okänt och antas vara nära noll.

Drivare 3: Elanvändning för laddning av tjänstebilar vid arbetsplatserna (enabler)
  BAU_Tier: 2
  BAU_motivering: Samma utveckling som Åtgärdsprofil 1, drivare 2.
  BAU_trend_A (g_A):
    - låg: ca 0 % 2026, 30 % av referensnivån 2030
    - medel: ca 0 % 2026, 55 % av referensnivån 2030
    - hög: ca 0 % 2026, 80 % av referensnivån 2030
  BAU_trend_EF (g_EF):
    - låg: −3 %/år
    - medel: −7 %/år
    - hög: −12 %/år
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Redovisas endast som referens, och siffrorna ska harmonisera med Åtgärdsprofil 1. Utan laddpunkter laddar BAU-elbilarna någon annanstans (ANTAGANDE).

**Dataluckor för detta steg**
- Saknar medarbetarenkät eller resvaneundersökning om bilandel, pendlingsavstånd och bilägande för de 1 500 anställda. A0 bygger på antagandena 55 % bilpendling och 12 km enkel väg.
- Saknar uppgift om andelen av pendlingen som sker inom kommunen. 75 % är ett antagande som styr den territoriella delen.
- Biblioteket saknar lokal data för elbilsandel i trafik (utöver cirka 3–4 %) och för privat körsträcka per person (TR_vkt_percap_passenger_car).
- Okänt hur mycket laddning som idag sker på arbetsplatserna och i vilken utsträckning den skulle flyttas från hemmet.
- Samma luckor för tjänstebilarnas el som i Åtgärdsprofil 1 (elförbrukning, faktisk flottsammansättning, ursprungsmärkt el).
- Beslut om tillgång och prissättning för anställdas laddning saknas, vilket påverkar framtida adoption men inte BAU-nivån.

**Frågor till miljöstrateg för detta steg**
- Finns uppgifter om anställdas pendlingsavstånd och färdmedel (medarbetarenkät eller resvaneundersökning för arbetsplatserna)?
- Finns det redan laddpunkter vid de 25 arbetsplatserna som anställda kan använda idag?
- Vilken elbilsandel i flottan 2030 bör användas som huvudscenario i BAU (20, 30 eller 40 %)?
- Ska enbart pendling inom kommunen räknas som territoriell, eller hela pendlingssträckan?