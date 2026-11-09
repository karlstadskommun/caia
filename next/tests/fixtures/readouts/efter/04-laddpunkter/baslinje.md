Baslinje & BAU-analys för åtgärd: Publika laddpunkter i flerbostadsområden

**Kort om detta steg**
Jag utgår från de fyra EMAP-drivarna och sätter en nulägesbaslinje (aktivitet A0 och emissionsfaktor EF0) för var och en, med 2023 som basår. Därefter definierar jag ett BAU-scenario utan åtgärden till 2026 och 2030, med trender för aktivitet (g_A) och emissionsfaktor (g_EF). Inga åtgärdseffekter räknas här. Resultatet används av Evidens & Antaganden-agenten för att koppla på åtgärdens påverkan.

**Underlag från EMAP**
Fyra drivare ingår, inom sektorerna transport (drivare 1, 2 och 4) och energi (drivare 3). Åtgärden är indirekt/möjliggörande och gäller cirka 4 000 hushåll och 2 400 bilar i fyra stadsdelar. Drivare 1 och 2 har hög överlapp_risk eftersom de bygger på samma bilbyte, och drivare 3 och 4 har medelhög risk. Baslinjen bygger på flera ANTAGANDEN från profilen och EMAP-steget: 0,6 bilar per hushåll och 5–10 % laddbara bilar.

**Gemensamma antaganden för nuläget (ANTAGANDE)**
- 2 400 bilar, varav cirka 7 % laddbara: 100 elbilar, 70 laddhybrider och 2 230 bensin- och dieselbilar (inklusive vanliga hybrider).
- Körsträcka 10 000 km per bil och år. Det ligger under kommunsnittet på cirka 11 000–12 000 km, som jag härlett ur 79 454 ton för personbilar i localData, EF 0,15 kg/km och en uppskattad flotta på cirka 45 000 bilar. Det ligger också i övre delen av schablonen TR_vkt_percap_passenger_car (7 000–10 000 km per person), som avser per person och inte per bil. Stadsnära flerbostadsboende körs mindre än snittet, därav 10 000 km.
- Cirka 75 % av körningen sker inom kommunen och 25 % utanför.

**Nulägesbaslinje per drivare**

Drivare 1: Körsträcka med fossildrivna personbilar bland boende i de fyra stadsdelarna
  Nuläge_år: 2023
  A0: 1,7e7 (cirka 17 miljoner fordonskilometer i kommunen: 2 230 bilar × 10 000 km × 75 %)
  A0_enhet: km/år
  EF0: 0,17
  EF0_enhet: kg CO2e/km (tank-to-wheel)
  Källor_nuläge: EF_petrol_tank_to_wheel (2,3–2,4 kg/liter) och EF_diesel_tank_to_wheel (2,6–2,7 kg/liter) vid cirka 7 liter/100 km. EF_passenger_car_avg (0,12–0,18, blandad flotta) ger övre delen av intervallet eftersom endast fossilbilar ingår. TR_share_evs_new_sales, TR_share_evs_fleet_2030, TR_vkt_percap_passenger_car, BASE_pop. localData: Transporter/Personbilar 79 454 ton 2023.
  Kommentar_nuläge: Datakvalitet låg. Nivån utan åtgärd blir cirka 2 800 ton CO2e per år. Det motsvarar cirka 0,4 ton per person, ungefär hälften av kommunsnittet (79 454 ton / 97 233 invånare ≈ 0,82 ton). Det är rimligt för boende i flerbostadsområden, men siffran är osäker.

Drivare 2: Konsumtionsbaserade utsläpp från boendes bilresor med fossildrivna bilar
  Nuläge_år: 2023
  A0: 2,2e7 (alla fossila fordonskilometer, 2 230 bilar × 10 000 km, samma kilometer som i drivare 1)
  A0_enhet: km/år
  EF0: 0,083
  EF0_enhet: kg CO2e/km (viktad: 25 % × 0,17 för körning utanför kommunen + 0,04 för upstream på alla km)
  Källor_nuläge: EF_petrol_tank_to_wheel, EF_diesel_tank_to_wheel, EF_passenger_car_avg. Upstream-påslaget 0,04 kg/km är ett generellt typvärde (cirka 20–25 % av tank-to-wheel) som inte finns i biblioteket.
  Kommentar_nuläge: Datakvalitet låg. För att slippa dubbelräkning har jag ändrat formuleringen från EMAP. Aktiviteten är alla fossila km, och drivarens avgränsning (endast upstream och körning utanför kommunen) ligger i den viktade EF0. Drivarens namn är oförändrat. Nivån utan åtgärd blir cirka 1 800 ton CO2e per år. Eftersom drivare 1 och 2 delar samma kilometer får bilbytet inte räknas två gånger. Bara skillnaden i EF (utanför kommun och upstream) får tillräknas i drivare 2.

Drivare 3: Elanvändning för laddning av elbilar hos boende
  Nuläge_år: 2023
  A0: 2,5e5 (100 elbilar × 10 000 km × 0,20 kWh/km ≈ 200 000 kWh, plus 70 laddhybrider × 10 000 km × 35 % eldrift × 0,22 kWh/km ≈ 54 000 kWh)
  A0_enhet: kWh/år
  EF0: 0,050
  EF0_enhet: kg CO2e/kWh (svensk konsumtionsmix)
  Källor_nuläge: EF_el_SE_consumption_2020s (40–60 g CO2e/kWh, mittpunkt 50). Svensk mix används enligt domänregeln för energi, inte EF_el_Karlstad_product_guaranteed (0 g) och inte residualmix. EF_ev_per_km (0,02–0,05 kg/km) används som kontroll. Mitt värde, cirka 0,01 kg/km, ligger lägre eftersom det avser ren elbil med låg förbrukning.
  Kommentar_nuläge: Datakvalitet låg. Nivån är cirka 13 ton CO2e per år, så drivaren är liten. Den är en motverkande faktor i åtgärdsberäkningen. A0 avser all laddning av de boendes laddbara bilar, oavsett var de laddar. Hur stor del som sker publikt är okänt.

Drivare 4: Andel eldrift hos befintliga laddhybrider
  Nuläge_år: 2023
  A0: 3,4e5 (cirka 70 laddhybrider × 10 000 km × 65 % körning på bensin × 75 % inom kommunen)
  A0_enhet: km/år
  EF0: 0,15
  EF0_enhet: kg CO2e/km (när bilen körs på bensin)
  Källor_nuläge: EF_petrol_tank_to_wheel (2,3–2,4 kg/liter) vid cirka 6,5 liter/100 km. EF_passenger_car_avg som jämförelse. TR_share_evs_new_sales.
  Kommentar_nuläge: Datakvalitet mycket låg. Elandelen på 35 % är ett generellt typvärde för verklig användning av laddhybrider. Nivån är cirka 50 ton CO2e per år, så drivaren är liten.

**BAU-scenario per drivare**
Konvention för låg/medel/hög: *låg* är den svagaste förändringen och *hög* den starkaste, i den riktning trenden går. Basår är 2023, så 2026 motsvarar 3 år och 2030 motsvarar 7 år.

Drivare 1: Körsträcka med fossildrivna personbilar bland boende i de fyra stadsdelarna
  BAU_Tier: 2
  BAU_motivering: Elbilsandelen i flottan växer genom EU:s CO2-krav för nya bilar, nationella styrmedel och teknikutveckling. Därför används en policyjusterad trend och inte en historisk linjär trend.
  BAU_trend_A (g_A):
    - låg: -1,5 %/år. Boende utan egen laddplats halkar efter, så fossilandelen faller långsamt (cirka 85 % av körsträckan 2030).
    - medel: -3 %/år. Elektrifieringen följer TR_share_evs_fleet_2030 (20–40 %), men med viss eftersläpning i flerbostadsområden (cirka 75 % fossilandel 2030).
    - hög: -4,5 %/år. Snabb nationell elektrifiering (cirka 67 % fossilandel 2030).
  BAU_trend_EF (g_EF):
    - låg: -0,5 %/år. Svagare reduktionsplikt, bara marginell effektivisering i fossilflottan.
    - medel: -1,5 %/år. Effektivare nya bilar och reduktionsplikt (inblandning av biodrivmedel).
    - hög: -2,5 %/år. Snabbare utbyte av äldre fossilbilar och högre inblandning.
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger A ≈ 1,5e7 km 2026 och ≈ 1,35e7 km 2030, och EF ≈ 0,153 kg/km 2030. Aktivitetstrenden g_A gäller de fossila kilometerna i området, och den kan inte särskiljas från det som hade hänt ändå. Observerad trend 2021–2023 för personbilar i Karlstad (90 709 → 79 454 ton) är kraftig men påverkad av prisspikar och inte säker att extrapolera. Alla trender är ANTAGANDEN.

Drivare 2: Konsumtionsbaserade utsläpp från boendes bilresor med fossildrivna bilar
  BAU_Tier: 2
  BAU_motivering: Samma elektrifiering av flottan som i drivare 1.
  BAU_trend_A (g_A):
    - låg: -1,5 %/år, samma som drivare 1.
    - medel: -3 %/år, samma som drivare 1.
    - hög: -4,5 %/år, samma som drivare 1.
  BAU_trend_EF (g_EF):
    - låg: -0,5 %/år. Upstream-utsläppen är i stort sett konstanta.
    - medel: -1,5 %/år. Tank-to-wheel-delen sjunker, upstream ligger kvar.
    - hög: -2,5 %/år. Snabbare effektivisering och mer biodrivmedel.
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: A ska följa drivare 1 exakt. Medelscenariot ger A ≈ 1,8e7 km 2030. Ändra inte trenderna separat från drivare 1.

Drivare 3: Elanvändning för laddning av elbilar hos boende
  BAU_Tier: 2
  BAU_motivering: Elanvändningen växer snabbt när elbilsflottan växer. Elmixen blir renare enligt nationella scenarier (EF_el_SE_consumption_2030_BAU, 20–40 g CO2e/kWh).
  BAU_trend_A (g_A):
    - låg: +10 %/år. Cirka 14 % laddbara bilar bland de boende 2030.
    - medel: +13 %/år. Cirka 17 % laddbara bilar 2030.
    - hög: +18 %/år. Cirka 22 % laddbara bilar 2030.
  BAU_trend_EF (g_EF):
    - låg: -3 %/år (50 → cirka 40 g/kWh 2030).
    - medel: -7 %/år (50 → cirka 30 g/kWh 2030).
    - hög: -12 %/år (50 → cirka 20 g/kWh 2030).
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger A ≈ 3,7e5 kWh 2026 och ≈ 5,9e5 kWh 2030, och EF ≈ 0,030 kg/kWh 2030. Elmixen varierar mellan år (till exempel 2021–2023 för El och fjärrvärme: 26 598 → 22 202 → 25 259 ton), så trenden är en grov riktning. Ingen särskild laddutbyggnad av privata aktörer eller bostadsbolag ingår i trenden. Om sådan utbyggnad är planerad bör den ligga i BAU, vilket är viktigt för additionaliteten.

Drivare 4: Andel eldrift hos befintliga laddhybrider
  BAU_Tier: 2
  BAU_motivering: Laddhybridflottan växer långsamt, men nybilsförsäljningen skiftar mot rena elbilar. Underlaget är svagt och ingen historisk serie finns för området.
  BAU_trend_A (g_A):
    - låg: 0 %/år. Laddhybridflottan stagnerar.
    - medel: +3 %/år. Flottan växer långsamt medan den totala körsträckan ligger kvar.
    - hög: +6 %/år. Fortsatt tillväxt för laddhybrider.
  BAU_trend_EF (g_EF):
    - låg: -0,5 %/år
    - medel: -1 %/år. Effektivare bensinmotorer och reduktionsplikt.
    - hög: -2 %/år
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger A ≈ 4,2e5 km 2030 och EF ≈ 0,14 kg/km. En ökande elandel hos befintliga laddhybrider ingår inte i BAU-trenden. Den är en möjlig åtgärdseffekt och hanteras i nästa steg.

**Dataluckor för detta steg**
- Saknar bilinnehav, elbilsandel och laddhybridandel för de fyra berörda stadsdelarna. Andelen laddbara bilar (5–10 %) och 0,6 bilar per hushåll är antaganden.
- Saknar körsträcka per bil för området. 10 000 km är en schablon, och Trafikanalys körsträckor per kommun har inte använts.
- Saknar uppgift om fördelningen mellan körning inom och utanför kommunen. 75/25 är ett antagande.
- Saknar upstream-emissionsfaktor för bensin och diesel i parameterbiblioteket. 0,04 kg CO2e/km är ett typvärde.
- Saknar verklig elandel för laddhybrider (35 % är ett typvärde) samt elförbrukning per km för laddbara bilar.
- Saknar uppgift om hur stor del av laddningen som sker publikt, hemma eller på arbetsplatsen.
- Saknar uppgift om planerad privat eller bostadsbolagsdriven laddutbyggnad i samma områden, vilket påverkar BAU för drivare 3 och additionaliteten.
- Elmixens utveckling till 2030 bygger på ett intervall (20–40 g CO2e/kWh) och inte på en lokal prognos.
- Trenderna för g_A och g_EF är expertbedömningar utan lokal historisk serie, förutom att personbilsutsläppen i localData (2021–2023) använts som kontroll.

**Frågor till miljöstrateg för detta steg**
- Finns registerdata om bilinnehav och elbilsandel per stadsdel, så att antagandena om 2 400 bilar och 5–10 % laddbara kan ersättas?
- Ska BAU utgå från nationella prognoser för elbilsandel och elmix, eller finns lokala scenarier för Karlstad?
- Ska BAU inkludera laddutbyggnad som hyresvärdar, bostadsrättsföreningar och privata operatörer redan planerar i de fyra stadsdelarna?
- Är det rimligt att avgränsa drivare 2 med en viktad EF och samma aktivitet som drivare 1, eller ska drivare 2 slås ihop med drivare 1?
- Ska upstream-utsläpp från bränsle ingå i konsumtionsbaserade utsläpp, och vilken upstream-faktor ska i så fall användas?
- Ska 2023 vara basår, eller finns tillförlitliga data för 2024 för bilinnehav och körsträckor?