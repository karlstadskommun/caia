Baslinje & BAU-analys för åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

**Kort om detta steg**
Jag utgår från de fyra godkända EMAP-drivarna och sätter en nulägesbaslinje (aktivitet A0 och emissionsfaktor EF0) för varje drivare. Därefter definierar jag ett BAU-scenario utan åtgärden till 2026 och 2030, med trendspann för aktivitet (g_A) och emissionsfaktor (g_EF). Inga åtgärdseffekter beräknas i detta steg. Resultatet används av Evidens & Antaganden-agenten för att koppla på åtgärdens påverkan.

**Underlag från EMAP**
Fyra drivare ingår. Tre gäller konsumtionsbaserade utsläpp från nyproducerat byggmaterial (betong och stomme, stål och metall, byggskivor/isolering/inredning), och en gäller territoriella utsläpp från transport och bearbetning av återbrukat material. Huvudsektorer är byggnader och transport. Alla tre materialdrivare har medelhög överlapp_risk mot generella klimatkrav i byggprojekt, minskat byggavfall och en eventuell återbrukscentral. Omfattningen (cirka 15 000–30 000 m² per år, viktbaserat 20 %-mått) är antagen i profilen, så alla baslinjer är grova.

**Nulägesbaslinje per drivare**

Drivare 1: Nyproducerat betong- och stommaterial i renoveringar
  Nuläge_år: 2023 (referensår i parameterbiblioteket; ingen renoveringsspecifik data finns)
  A0: 3,4e3 (cirka 3 400 ton nyproducerat betong-, tegel- och stommaterial)
  A0_enhet: ton/år
  EF0: 180
  EF0_enhet: kg CO2e/ton
  Källor_nuläge: Beräknat som 22 500 m² renoverad yta per år (mitt i antagandet 15 000–30 000 m²) × 0,3 ton nytt material per m² × cirka 50 % viktandel. EF0 är ett schablonvärde för blandad betong, tegel och lättbetong enligt generella typvärden från Boverkets klimatdatabas/EPD (ingen parameter i biblioteket). Kontroll mot DATA_MUNICIPAL_ORG (2022): Husbyggande 37 749 ton CO2e och Icke-metalliska mineraliska produkter 3 110 ton CO2e för hela kommunkoncernen. Biblioteksparametern EF_el_SE_consumption_2020s är relevant bara som bakgrund för elanvändningen vid tillverkning.
  Kommentar_nuläge: Datakvalitet låg. Materialintensiteten (0,3 ton/m², spann 0,15–0,5) och EF0 (spann 120–250) är antaganden. A0 avser inköpt nytt material efter dagens återbruk, som antas vara cirka 2–5 % av vikten. Samma renoveringsvolym som 2027–2030 antas redan i dag. Motsvarande utsläpp är cirka 600 ton CO2e/år.

Drivare 2: Nyproducerat stål, metall och installationsmaterial i renoveringar
  Nuläge_år: 2023
  A0: 4,5e2 (cirka 450 ton)
  A0_enhet: ton/år
  EF0: 2 500
  EF0_enhet: kg CO2e/ton
  Källor_nuläge: Beräknat som cirka 6 750 ton nytt material per år × cirka 7 % viktandel. EF0 är ett schablonvärde för en blandning av konstruktionsstål, galvaniserad plåt/ventilation, koppar, aluminium och armaturer enligt generella typvärden från Boverkets klimatdatabas/EPD (ingen parameter i biblioteket). Kontroll mot DATA_MUNICIPAL_ORG (2022): Metallvaror 110 ton CO2e och Stål och metall 6 ton CO2e. Dessa avser kommunens direkta inköp, och installationsmaterial ingår troligen i entreprenadkostnaderna under Husbyggande.
  Kommentar_nuläge: Datakvalitet låg. Viktandelen är liten, men EF är hög, så drivaren ger cirka 1 100 ton CO2e/år. EF0 varierar kraftigt mellan materialslag (1 000–8 000 kg/ton).

Drivare 3: Nyproducerade byggskivor, isolering, dörrar och inredning i renoveringar
  Nuläge_år: 2023
  A0: 2,9e3 (cirka 2 900 ton)
  A0_enhet: ton/år
  EF0: 600
  EF0_enhet: kg CO2e/ton
  Källor_nuläge: Beräknat som cirka 6 750 ton nytt material per år × cirka 43 % viktandel (gips, isolering, innerdörrar, fönster och inredning). EF0 är ett viktat schablonvärde: gips cirka 250–300, mineralull cirka 1 200, trädörrar och inredning cirka 500–2 000 kg CO2e/ton. Det kommer från generella typvärden från Boverkets klimatdatabas/EPD (ingen parameter i biblioteket). Kontroll mot DATA_MUNICIPAL_ORG (2022): Möbler 3 039 ton CO2e (hela kommunkoncernen, inklusive icke-renoveringsrelaterade inköp) och Varor av trä 107 ton CO2e.
  Kommentar_nuläge: Datakvalitet låg. Gips dominerar vikten men har låg EF, medan isolering och inredning har hög EF. Ett viktbaserat mått ger därför stor osäkerhet i EF0 (spann 400–900). Utsläpp cirka 1 700 ton CO2e/år.

Drivare 4: Demontering, transport och bearbetning av återbrukat material
  Nuläge_år: 2023
  A0: 1,0e4 tonkm/år (cirka 200 ton återbrukat material i dag × cirka 50 km sammanlagd transportsträcka, plus cirka 200 maskintimmar/år för hantering)
  A0_enhet: tonkm/år (maskintimmar ingår som påslag i EF0 och kvantifieras inte separat)
  EF0: 0,12
  EF0_enhet: kg CO2e/tonkm
  Källor_nuläge: EF_freight_truck_tonkm (generellt värde 0,06–0,12 kg CO2/tonkm, tung lastbil), med påslag cirka 30 % för små last, lastning, mellanlagring och bearbetning. Referens för drivmedel: EF_diesel_tank_to_wheel (2,6–2,7 kg CO2/liter). Lokalt sammanhang från DATA_EMISSIONS_TOTAL: Transporter/Tunga lastbilar 23 635 ton CO2e (2023).
  Kommentar_nuläge: Datakvalitet låg. Nuvarande volym återbrukat material är okänd, och små partier ger högre EF än den fulla lastbilsfaktorn. Utsläppen i nuläget är mycket små (cirka 1 ton CO2e/år). Drivaren blir betydelsefull först när mängden återbrukat material ökar. Gastypen i biblioteket är CO2, men här används CO2e som approximation.

**BAU-scenario per drivare**

Drivare 1: Nyproducerat betong- och stommaterial i renoveringar
  BAU_Tier: 2
  BAU_motivering: Policy-justerad. EF förväntas sjunka tack vare klimatförbättrad betong, minskad klinkerandel och planerad infångning av koldioxid vid cementtillverkning. För A finns ingen historisk tidsserie, så trenden är en kvalificerad gissning (Tier 0/1-nivå).
  BAU_trend_A (g_A):
    - låg: -2 %/år, renoveringsvolymen minskar något och marknadsdrivet återbruk växer snabbare
    - medel: +0,5 %/år, ökat renoveringsbehov i äldre bestånd, motverkat av att återbruk ökar från dagens nivå
    - hög: +3 %/år, ökad renoveringstakt (miljonprogrammet, energikrav) utan större marknadseffekt
  BAU_trend_EF (g_EF):
    - låg: -1 %/år, långsam teknikspridning
    - medel: -2,5 %/år, klimatförbättrad betong och lägre klinkerandel
    - hög: -4 %/år, tidigare storskalig infångning av koldioxid och fossilfri produktion
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelfallet ger EF cirka 150 kg/ton 2030. Nya nationella klimatgränsvärden gäller bara nybyggnad och är inte antagna för renoveringar. Trenderna räknas från referensåret 2023.

Drivare 2: Nyproducerat stål, metall och installationsmaterial i renoveringar
  BAU_Tier: 2
  BAU_motivering: Policy-justerad. Stålproduktionens omställning (fossilfritt stål, mer skrotbaserat) påverkar EF, men effekten på kommunens inköp är osäker eftersom mycket material importeras.
  BAU_trend_A (g_A):
    - låg: -2 %/år, mindre volym och mer återbruk
    - medel: +0,5 %/år, samma antagande som för drivare 1
    - hög: +3 %/år, ökad renoveringstakt
  BAU_trend_EF (g_EF):
    - låg: -1 %/år, endast små förändringar i globala leveranskedjor
    - medel: -2 %/år, gradvis ökad andel fossilfritt och skrotbaserat stål
    - hög: -4 %/år, snabb marknadsetablering av fossilfritt stål i byggsektorn
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelfallet ger EF cirka 2 200 kg/ton 2030. Blandningen av materialslag (stål, koppar, aluminium) kan förändras mer än den enskilda produktens EF.

Drivare 3: Nyproducerade byggskivor, isolering, dörrar och inredning i renoveringar
  BAU_Tier: 2
  BAU_motivering: Policy-justerad men med svagare trendunderlag än drivare 1 och 2. Tillverkningen är mindre energiintensiv och mer diversifierad, så förbättringar sker långsammare.
  BAU_trend_A (g_A):
    - låg: -2 %/år, återbruk av inredning och dörrar växer snabbt
    - medel: +0,5 %/år, samma antagande som för drivare 1
    - hög: +3 %/år, ökad renoveringstakt och högre standard
  BAU_trend_EF (g_EF):
    - låg: -0,5 %/år, nästan ingen förändring
    - medel: -1,5 %/år, renare energi i tillverkningen och bättre isolermaterial
    - hög: -3 %/år, snabb övergång till lågutsläppsprodukter
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelfallet ger EF cirka 540 kg/ton 2030. Marknaden för återbrukade dörrar och inredning växer, vilket ingår i g_A. Där finns risk för överlapp med andra åtgärder (återbrukscentral, minskat byggavfall).

Drivare 4: Demontering, transport och bearbetning av återbrukat material
  BAU_Tier: 2
  BAU_motivering: Policy-justerad för EF, där drivmedelsmixen förbättras tack vare reduktionsplikt och elektrifiering av lätta lastbilar. Karlstads tunga lastbilar minskade från 27 182 ton (2021) till 23 635 ton (2023), men tvåårsserien är för kort för att extrapolera. För A finns ingen historik.
  BAU_trend_A (g_A):
    - låg: 0 %/år, återbruksmarknaden växer inte märkbart
    - medel: +3 %/år, mer frivilligt återbruk från en låg nivå
    - hög: +8 %/år, snabbt växande marknad för återbrukat byggmaterial
  BAU_trend_EF (g_EF):
    - låg: -1 %/år, långsam flottomställning
    - medel: -3 %/år, högre inblandning av förnybara drivmedel och fler elektriska transporter
    - hög: -5 %/år, snabb elektrifiering av regionala transporter
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelfallet ger EF cirka 0,10 kg/tonkm 2030. BAU-nivån är låg i absoluta tal. Åtgärden förväntas öka mängden hanterat material kraftigt, men det hör till nästa steg.

**Dataluckor för detta steg**
- Saknar lista över planerade större renoveringar 2027–2030 (yta, typ av ingrepp, investeringsbelopp) för både förvaltningar och bolag. Ytan 22 500 m²/år är en antagen mittpunkt.
- Saknar materialintensitet (ton per m² renoverad yta) och viktfördelning mellan materialslag. Värdena 0,3 ton/m² och 50/7/43 % är grova antaganden.
- Saknar emissionsfaktorer för byggmaterial i parameterbiblioteket. EF0 bygger på egna typvärden från Boverkets klimatdatabas/EPD och bör ersättas av verifierade värden.
- Okänd nuvarande återbruksandel i kommunens renoveringsprojekt (antaget 2–5 % av vikten) och hur den rapporteras.
- Okända mängder, transportavstånd och hanteringsutsläpp för nuvarande återbruksmaterial (drivare 4). Maskintimmarna är en grov gissning.
- Ingen historisk tidsserie för renoveringsvolym eller inköp av byggmaterial, så g_A kan inte beläggas med trenddata.
- Osäkert hur snabbt EF faktiskt sjunker för inköpta produkter (särskilt stål och betong), eftersom produktval styrs av entreprenörer och leverantörer.
- Kontrollsiffrorna från DATA_MUNICIPAL_ORG avser 2022 och hela kommunkoncernens inköp, inte bara renoveringar. Summan i drivare 1–3 (cirka 3 500 ton CO2e/år) motsvarar cirka 9 % av Husbyggande och bör verifieras.

**Frågor till miljöstrateg för detta steg**
- Finns uppgifter om renoveringsvolym (m² eller Mkr per år) från lokalförsörjningsplanen, investeringsbudgeten eller bostadsbolagets underhållsplan som kan ersätta 22 500 m²?
- Ska BAU utgå från nationella prognoser för klimatförbättrat material (t.ex. Boverkets och branschens färdplaner) eller från kommunens egna upphandlingskrav?
- Finns det i dag någon uppföljning av återbruk eller klimatpåverkan i kommunens renoveringsprojekt som kan ge en riktig nuläges-nivå?
- Ska hänsyn tas i BAU till andra beslutade eller planerade krav (t.ex. klimatdeklaration vid renovering), så att dubbelräkning undviks?