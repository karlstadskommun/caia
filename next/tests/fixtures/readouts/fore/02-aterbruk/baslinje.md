Baslinje & BAU-analys för åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

## Kort om detta steg
Jag utgår från de fyra EMAP-drivarna och sätter en nulägesbaslinje per drivare med aktivitet (A0) och emissionsfaktor (EF0). Därefter definierar jag ett BAU-scenario utan åtgärden för 2026 och 2030. Parameterbiblioteket saknar byggmaterialspecifika värden, så flera nivåer är grova uppskattningar som skalats från renoveringsvolymen i åtgärdsprofilen (ANTAGANDE: 22 500 m² BTA per år, mitten av 15 000–30 000). Resultatet används i nästa steg för att koppla på åtgärdseffekter och antagandespann. Jag räknar ingen åtgärdseffekt här.

## Underlag från EMAP
Fyra drivare ingår, inom sektorerna byggnader (Drivare 1), avfall (Drivare 2), transport (Drivare 3) och energi (Drivare 4). Drivare 1 och 4 är kommunens egna utsläpp, Drivare 2 och 3 är territoriella. Drivare 1 är huvuddrivaren. Drivare 2 har hög överlapp_risk mot kommunens avfallsåtgärder, och Drivare 1 överlappar med konsumtionsbaserade utsläpp. Drivare 1 och 4 ska därför inte summeras med konsumtionsbaserade utsläpp i senare steg. Åtgärden är mognadsgraden pilot/försök, och BAU-återbruket antas vara 0–5 %.

## Nulägesbaslinje per drivare

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  Nuläge_år: 2023
  A0: 4,5e3 (inköpt nyproducerat byggmaterial inom omfattade produktgrupper, efter dagens återbruk på ca 0–5 %)
  A0_enhet: ton/år
  EF0: 0,8
  EF0_enhet: kg CO2e/kg material (A1–A3, viktat snitt över produktgrupperna)
  Källor_nuläge: Ingen parameter för byggmaterial finns i parameterbiblioteket. Volym från åtgärdsprofilen (ANTAGANDE: 22 500 m² BTA/år). Materialintensitet 200 kg/m² (ANTAGANDE). EF0 är ett generellt typvärde för en blandning av gips, golv, undertak, dörrar, sanitet och armaturer (ANTAGANDE: 0,5–1,2). Kontroll mot DATA_MUNICIPAL_ORG (2022): Fastigheter & Anläggningsarbeten 70 918 ton CO2e, varav Husbyggande 37 749 ton.
  Kommentar_nuläge: Implicerat utsläpp är ca 3 600 ton CO2e/år, vilket är ca 5 % av kommunens utsläpp från fastigheter och anläggning. Det är rimligt eftersom nybyggnad och stomme ligger utanför omfattningen. Datakvaliteten är låg. Osäkerhetsintervall för A0 är 1,5e3–9e3 ton/år (15 000–30 000 m² × 100–300 kg/m²).

Drivare 2: Byggavfall från rivning till förbränning och deponi
  Nuläge_år: 2023
  A0: 5e2 (byggavfall från större renoveringar som går till förbränning eller deponi)
  A0_enhet: ton/år
  EF0: 300
  EF0_enhet: kg CO2e/ton avfall
  Källor_nuläge: Ingen parameter finns i parameterbiblioteket. Rivningsavfall ca 50 kg/m² (ANTAGANDE), vilket ger ca 1 100 ton/år totalt, varav ca 45 % till förbränning/deponi (ANTAGANDE). EF0 är ett typvärde för blandat brännbart byggavfall och deponirest (ANTAGANDE: 150–400). Kontext från localData: Avfallsdeponier 3 159 ton CO2e (2023), Avfall totalt 7 484 ton CO2e (2023).
  Kommentar_nuläge: Implicerat utsläpp är ca 150 ton CO2e/år. Datakvaliteten är låg. Dataluckan är störst för andelen som sorteras ut för materialåtervinning. Hög överlapp_risk mot avfallsåtgärder kvarstår.

Drivare 3: Transporter av byggmaterial och återbrukat material
  Nuläge_år: 2023
  A0: 5e5 (material till projekt ca 4 500 ton × 100 km plus avfall ca 1 100 ton × 30 km, avrundat)
  A0_enhet: tonkm/år
  EF0: 0,09
  EF0_enhet: kg CO2e/tonkm (kg CO2 enligt parameterbiblioteket, tung lastbil)
  Källor_nuläge: EF_freight_truck_tonkm (standardvärde 0,06–0,12, Karlstad-specifikt saknas, mittvärde valt). Transportavstånd är ANTAGANDE. Kontext från localData: Tunga lastbilar 23 635 ton CO2e (2023).
  Kommentar_nuläge: Implicerat utsläpp är ca 45 ton CO2e/år, ungefär 0,2 % av Karlstads tunga lastbilstrafik. Datakvaliteten är låg. Transporter för leverantörskedjans material överlappar med Drivare 1.

Drivare 4: Inventering, mellanlagring och kvalitetssäkring av återbrukat material
  Nuläge_år: 2023
  A0: 2e4 (liten ad hoc-hantering i dagens återbruk: lagringsyta, inventering, intern transport)
  A0_enhet: kWh/år (el, värme och drivmedel omräknat)
  EF0: 0,10
  EF0_enhet: kg CO2e/kWh (viktat: ca 70 % el/fjärrvärme och ca 30 % drivmedel)
  Källor_nuläge: EF_el_SE_consumption_2020s (40–60 g CO2e/kWh), EF_district_heat_Karlstad_2023 (19 g CO2e/kWh), EF_diesel_tank_to_wheel (2,6–2,7 kg CO2/liter, ca 0,26 kg/kWh). Energidomänregeln tillämpas: svensk elmix och konsumtionsbaserad hantering. Aktivitetsnivån är ANTAGANDE.
  Kommentar_nuläge: Implicerat utsläpp är ca 2 ton CO2e/år, alltså försumbart. Datakvaliteten är mycket låg. Drivaren blir relevant först när ett systematiskt flöde byggs upp.

## BAU-scenario per drivare

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  BAU_Tier: 2
  BAU_motivering: Aktiviteten saknar historisk tidsserie och hålls nära konstant. Emissionsfaktorn väntas falla på grund av pågående avkarbonisering av byggmaterialtillverkning (t.ex. renare cement och stål, krav på klimatdeklarationer).
  BAU_trend_A (g_A):
    - låg: -2 %/år, mindre renoveringsvolym vid stram investeringsbudget
    - medel: 0 %/år, oförändrad renoveringsvolym enligt underhållsplan
    - hög: +2 %/år, växande renoveringsbehov i äldre fastighetsbestånd
  BAU_trend_EF (g_EF):
    - låg: -1 %/år, långsam teknikutveckling
    - medel: -2,5 %/år, gradvis lägre klimatintensitet i materialtillverkningen
    - hög: -4 %/år, snabb avkarbonisering av byggmaterial
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger EF ca 0,74 kg CO2e/kg 2026 och ca 0,67 2030, med A oförändrad vid 4,5e3 ton/år. Utsläppsnivån blir då ca 3 300 respektive 3 000 ton CO2e/år utan åtgärden. BAU-återbruket antas ligga kvar på 0–5 % och räknas inte som åtgärdseffekt. Överlapp mot konsumtionsbaserade utsläpp ska hanteras i senare steg.

Drivare 2: Byggavfall från rivning till förbränning och deponi
  BAU_Tier: 1
  BAU_motivering: Karlstads deponiutsläpp har minskat med ca 7 %/år 2021–2023 (3 687 till 3 159 ton CO2e). Trenden används som stöd för en minskande avfallsmängd till förbränning och deponi.
  BAU_trend_A (g_A):
    - låg: -1 %/år, långsam förbättring av källsortering på byggarbetsplatser
    - medel: -3 %/år, successivt bättre sortering och minskad deponering
    - hög: -6 %/år, i linje med den senaste deponitrenden
  BAU_trend_EF (g_EF):
    - låg: 0 %/år, oförändrad avfallsbehandling
    - medel: -1 %/år, lägre fossilandel vid förbränning genom bättre plastsortering
    - hög: -2 %/år, tydligare förbättring av avfallsbehandlingen
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger A ca 4,6e2 ton/år 2026 och ca 4,1e2 2030. EF0 antas ändras bara marginellt. Överlappsrisken mot avfallsåtgärder måste hanteras i senare steg.

Drivare 3: Transporter av byggmaterial och återbrukat material
  BAU_Tier: 2
  BAU_motivering: Emissionsfaktorn väntas falla med ökad andel biodrivmedel, eldrivna lastbilar och beslutade styrmedel. Aktiviteten följer renoveringsvolymen.
  BAU_trend_A (g_A):
    - låg: -1 %/år, något kortare transportavstånd eller lägre volym
    - medel: 0 %/år, oförändrat transportarbete
    - hög: +1 %/år, något ökat transportarbete
  BAU_trend_EF (g_EF):
    - låg: -2 %/år, långsam fordonsomställning
    - medel: -4 %/år, ökad andel förnybara drivmedel och elektrifiering av tunga transporter
    - hög: -7 %/år, snabb elektrifiering av lastbilsflottan
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger EF ca 0,080 kg CO2e/tonkm 2026 och ca 0,068 2030. Karlstads tunga lastbilar visade ingen tydlig trend 2022–2023 (23 529 till 23 635 ton CO2e), vilket motiverar försiktighet. Överlapp mot leverantörskedjans transporter i Drivare 1 gäller.

Drivare 4: Inventering, mellanlagring och kvalitetssäkring av återbrukat material
  BAU_Tier: 2
  BAU_motivering: Aktiviteten hålls konstant eftersom ingen systematisk hantering finns i BAU. Emissionsfaktorn påverkas av renare el och värme.
  BAU_trend_A (g_A):
    - låg: 0 %/år, ingen förändring
    - medel: 0 %/år, ad hoc-hantering oförändrad
    - hög: +2 %/år, något ökad frivillig återbruksverksamhet
  BAU_trend_EF (g_EF):
    - låg: -1 %/år, långsam förändring
    - medel: -2 %/år, lägre elmix och fortsatt låg fjärrvärmeintensitet (EF_el_SE_consumption_2030_BAU: 20–40 g CO2e/kWh)
    - hög: -4 %/år, snabbare fossilfri omställning, även för drivmedel
  BAU_årpunkter: [2026, 2030]
  Kommentar_BAU: Medelscenariot ger EF ca 0,094 kg CO2e/kWh 2026 och ca 0,087 2030. Storleken är försumbar (ca 2 ton CO2e/år), så osäkerheten i trenden har låg betydelse.

## Dataluckor för detta steg
- Saknar renoveringsvolym per år (antal projekt, m² BTA, entreprenadkostnad) från fastighetsförvaltningens investerings- och underhållsplan.
- Saknar materialmängd per m² och fördelning mellan produktgrupper i kommunens renoveringar. A0 för Drivare 1 bygger på en schablon.
- Saknar emissionsfaktorer per produktgrupp (A1–A3) i parameterbiblioteket. EF0 för Drivare 1 är ett viktat typvärde.
- Saknar nuvarande återbruksandel (0–5 % är en ANTAGANDE) och definition av vad som räknas som återbruk i dag.
- Saknar uppgifter om rivningsavfall från kommunens renoveringar: mängd, sorteringsgrad och behandlingsväg.
- Saknar emissionsfaktor för byggavfall till förbränning och deponi i parameterbiblioteket.
- Saknar transportavstånd och fordonstyper för materialleveranser och avfallstransporter.
- Saknar uppgifter om energianvändning och drivmedel för dagens lagring och hantering av återbrukat material (A0 för Drivare 4 är ett grovt antagande).
- Saknar Karlstad-specifika trender för emissionsfaktorer i byggmaterial och transporter. Policybaserade trender är uppskattningar.
- Oklart hur stor del av emissionerna i Drivare 1 som redan ingår i DATA_MUNICIPAL_ORG (konsumtionsbaserade utsläpp), vilket påverkar dubbelräkningen.

## Frågor till miljöstrateg för detta steg
- Vilket basår ska användas för renoveringsvolymen, och finns en planerad investeringsnivå för 2027–2030?
- Ska kravet på 20 % mätas i vikt, kostnad eller klimatpåverkan, och vilka produktgrupper undantas? Svaret påverkar hur A0 i Drivare 1 ska definieras.
- Finns klimatdeklarationer, LCA eller materialinventeringar från tidigare renoveringsprojekt som kan ersätta schablonerna?
- Ska BAU för emissionsfaktorer följa nationella prognoser för byggmaterial och transporter, eller finns lokala mål?
- Ska Drivare 2 (byggavfall) behållas i analysen, eller ska den hanteras av avfallsåtgärderna för att undvika dubbelräkning?