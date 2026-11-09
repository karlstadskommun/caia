# Baslinje & BAU-analys för åtgärd: Publika laddpunkter i flerbostadsområden

## Kort om detta steg
Jag utgår från de två EMAP-drivarna. För varje drivare sätter jag en nulägesbaslinje med aktivitet (A0) och emissionsfaktor (EF0) samt ett BAU-scenario utan åtgärden till 2026 och 2030. Inga åtgärdseffekter beräknas här. Resultatet används i nästa steg för att koppla på åtgärdens effekter och antaganden.

Konvention för BAU-intervallen: "låg" betyder långsam utveckling, alltså svag elektrifiering och långsam avkarbonisering. "Hög" betyder snabb utveckling. Procentsatserna gäller per år från 2023.

## Underlag från EMAP
Två drivare ingår. Drivare 1 är transport (territoriella utsläpp, fossil bilkörning). Drivare 2 är energi (konsumtionsbaserade utsläpp från el till laddning). Drivare 1 har hög överlapp_risk, eftersom minskningen överlappar den nationella elektrifieringstrenden (EU:s CO2-krav, reduktionsplikt), som därför ska ligga i BAU. Drivare 2 har medelhög överlapp_risk, eftersom den är motposten till Drivare 1 och bygger på samma bilbyten. Målgruppen är cirka 4 000 hushåll, och antalet bilar bland dem är ett ANTAGANDE (0,7 bilar per hushåll, alltså cirka 2 800 bilar).

## Nulägesbaslinje per drivare

Drivare 1: Körsträcka med bensin- och dieselbilar bland boende utan egen laddplats
  Nuläge_år: 2023
  A0: 2,4e7 (cirka 24 miljoner fordonskilometer per år med fossildrivna personbilar hos målgruppen). Uppskattningen är 2 800 bilar × 97 % fossildrivna × 9 000 km per bil, avrundat. Det motsvarar cirka 3 900 ton CO2e per år.
  A0_enhet: km/år
  EF0: 0,16
  EF0_enhet: kg CO2e/km
  Källor_nuläge: EF_passenger_car_avg (0,12–0,18 kg CO2/km, flottsnitt). Jag använder 0,16 för enbart fossildrivna bilar, som ligger något över flottsnittet eftersom elbilarna är borttagna ur snittet. Kontroll mot EF_petrol_tank_to_wheel och EF_diesel_tank_to_wheel: cirka 6,8 l/100 km × 2,3–2,6 kg/l ger 0,16 kg/km. TR_share_evs_fleet_2030 och lokal uppgift om cirka 3–4 % elbilar i trafiken 2023 ger fossilandelen 97 %. Territoriella utsläpp från personbilar 2023 var 79 454 ton (localData). TR_vkt_percap_passenger_car används bara som kontroll.
  Kommentar_nuläge: Kvalitet låg. Antalet bilar (0,7 per hushåll, intervall 0,6–0,8), körsträckan per bil (ANTAGANDE: 9 000 km, intervall 7 500–11 000, lägre än riksgenomsnittet för bilar i flerbostadsområden) och fossilandelen (ANTAGANDE: 97 %, något lägre elbilsandel än kommunsnittet eftersom laddhinder finns) är alla antaganden. Sanity check: 3 900 ton är cirka 5 % av kommunens personbilsutsläpp 2023, vilket är rimligt för cirka 7–8 % av invånarna med lägre bilinnehav och körsträcka. Basåret är 2023, medan åtgärden genomförs 2027–2028. EF0 avser TTW-CO2, och övriga växthusgaser är försumbara (cirka 1–2 %).

Drivare 2: Elbilars körsträcka och elanvändning för laddning vid de publika laddpunkterna
  Nuläge_år: 2023
  A0: 1,5e5 (cirka 150 MWh per år). Det är elanvändningen för elbilar i målgruppen, alltså 2 800 bilar × 3 % elbilar × 9 000 km × 0,2 kWh/km. Det är all laddning för dessa bilar, oavsett var de laddar.
  A0_enhet: kWh/år
  EF0: 0,05
  EF0_enhet: kg CO2e/kWh
  Källor_nuläge: EF_el_SE_consumption_2020s (40–60 g CO2e/kWh, mittvärde 50 g, svensk konsumtionsmix enligt domänregeln för energi). Elbilars förbrukning 0,2 kWh/km inklusive laddförluster är ett ANTAGANDE (intervall 0,17–0,22). Elbilsandelen 3 % bygger på uppgiften om 3–4 % elbilar i Karlstad 2023 (TR_share_evs_fleet_2030, kommentarsfältet).
  Kommentar_nuläge: Kvalitet låg. Den del av laddningen som sker vid de nya laddpunkterna är per definition 0 i BAU, eftersom de inte finns utan åtgärden. Därför beskriver A0 all laddning hos målgruppen, och nästa steg lägger till åtgärdens laddning. EF_el_Karlstad_product_guaranteed (0 g) används inte, eftersom ursprungsgarantier inte ska tillgodoräknas. Den implicita utsläppsfaktorn per kilometer (0,2 × 0,05 = 0,01 kg/km) ligger under intervallet i EF_ev_per_km (0,02–0,05), som verkar utgå från en högre elmix. Det noterar jag som en metodfråga.

## BAU-scenario per drivare

Drivare 1: Körsträcka med bensin- och dieselbilar bland boende utan egen laddplats
  BAU_Tier: 2
  BAU_motivering: Policystyrd utveckling. EU:s CO2-krav på nya bilar, reduktionsplikten och den växande elbilsandelen i flottan ger en tydlig nedåtgående trend i fossil körsträcka, som inte bygger på åtgärden.
  BAU_trend_A (g_A):
    - låg: -1 %/år. Elbilsandelen i målgruppens flotta når cirka 10 % 2030 (trögt på grund av laddhinder), och körsträckan per bil ligger kvar.
    - medel: -2,5 %/år. Elbilsandelen når cirka 16 % 2030, och körsträckan per bil minskar något (-0,5 %/år).
    - hög: -4,5 %/år. Elbilsandelen når cirka 24 % 2030 (nära nedre delen av TR_share_evs_fleet_2030), och körsträckan per bil minskar med -1 %/år.
  BAU_trend_EF (g_EF):
    - låg: -0,5 %/år. Marginellt effektivare fossilbilar och låg inblandning av biodrivmedel.
    - medel: -1 %/år. Effektivare nya fossilbilar och hybridisering samt viss inblandning av biodrivmedel.
    - hög: -1,5 %/år. Högre inblandning av biodrivmedel och snabbare effektivisering.
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger ungefär 2,3e7 km 2026 och 2,0e7 km 2030, med EF cirka 0,155 respektive 0,149 kg CO2e/km. Elbilsandelen är lägre i målgruppen än nationellt eftersom boende utan egen laddplats har ett hinder. Eftersom åtgärden inte finns i BAU antar jag att privat och annan befintlig laddning ger viss elektrifiering även utan åtgärden. Reduktionspliktens nivå efter 2026 är osäker.

Drivare 2: Elbilars körsträcka och elanvändning för laddning vid de publika laddpunkterna
  BAU_Tier: 2
  BAU_motivering: Policystyrd utveckling. Elbilsandelen växer snabbt på grund av nationella styrmedel och EU:s krav, och den svenska elmixen antas bli renare. Båda trenderna kommer utifrån och inte från åtgärden.
  BAU_trend_A (g_A):
    - låg: +19 %/år. Elbilsandelen i målgruppen växer från 3 % till cirka 10 % 2030.
    - medel: +26 %/år. Från 3 % till cirka 16 % 2030, med något lägre körsträcka per bil.
    - hög: +33 %/år. Från 3 % till cirka 24 % 2030, med lägre körsträcka per bil.
  BAU_trend_EF (g_EF):
    - låg: -3 %/år. Elmixen går mot cirka 40 g CO2e/kWh 2030 (övre delen av EF_el_SE_consumption_2030_BAU).
    - medel: -7 %/år. Elmixen går mot cirka 30 g CO2e/kWh 2030 (mitt i intervallet).
    - hög: -13 %/år. Elmixen går mot cirka 20 g CO2e/kWh 2030 (nedre delen av intervallet).
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Den höga tillväxten utgår från en mycket låg bas (cirka 84 elbilar 2023). Medelscenariot ger ungefär 3,0e5 kWh 2026 och 7,7e5 kWh 2030, med EF cirka 0,040 respektive 0,030 kg CO2e/kWh. Elbilsandelen i A är kopplad till samma andel som i Drivare 1 (elbilsandel 10 / 16 / 24 % 2030 i låg / medel / hög), för att motpostens utsläpp och minskningen ska bygga på samma bilparksutveckling. Elmixen är en nationell, konsumtionsbaserad mix.

## Dataluckor för detta steg
- Saknar antal personbilar och drivmedelsfördelning (bensin, diesel, el, laddhybrid) i de fyra stadsdelarna. A0 bygger på 0,7 bilar per hushåll och 97 % fossildrivna bilar.
- Saknar körsträcka per bil för boende i flerbostadsområden (Trafikanalys, per kommun eller stadsdel). 9 000 km per bil är ett ANTAGANDE.
- Saknar uppgift om hur stor del av elbilsladdningen som idag sker vid publika laddpunkter, och alltså hur stor del av A0 som är relevant för åtgärden.
- Saknar kartläggning av befintlig och planerad privat laddning i områdena, som påverkar BAU-elektrifieringen.
- Saknar lokal prognos för elbilsandelen i Karlstads fordonsflotta 2030. Spannet 10–24 % är en uppskattning från TR_share_evs_fleet_2030 (20–40 % nationellt), med avdrag för laddhindret.
- Oklart vilken nivå reduktionsplikten har efter 2026, vilket påverkar EF0 för fossila bilar.
- Elbilars förbrukning (kWh/km) och elmixens utveckling är schabloner. Sambandet mellan EF_ev_per_km i biblioteket och den härledda 0,01 kg/km är oklart.
- Alla procentsatser för g_A och g_EF är uppskattningar utan lokal tidsserie (kvalitet låg).

## Frågor till miljöstrateg för detta steg
- Ska BAU utgå från nationella prognoser för elbilsandel och elmix, eller finns lokala scenarier i Karlstads klimatplan eller regionen?
- Finns uppgifter om bilinnehav och drivmedelsfördelning per stadsdel, eller ska schablonen 0,7 bilar per hushåll gälla?
- Ska elbilsandelen i målgruppen sättas lägre än kommunsnittet, eftersom boende utan egen laddplats har ett laddhinder?
- Ska all laddning av målgruppens elbilar ingå i A0 för Drivare 2, eller enbart den del som sker vid publika laddpunkter?
- Vilken elmix ska användas för laddningen efter 2025: nationell konsumtionsmix, residualmix eller ursprungsmärkt el?