---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

1. Sammanfattning
Åtgärden påverkar utsläppen från tillverkning av nytt byggmaterial, eftersom återbrukat material ersätter nyproducerat i kommunens större renoveringar. Den påverkar också klimatpåverkan från återbruksledet (transport, lagring och rekonditionering) och utsläppen från hantering av byggavfall. Effekten räknas rakt på drivarna och avser cirka 4 projekt och 20 000 m² BTA per år under 2027–2030 (totalt cirka 80 000 m² BTA), med minst 20 % återbruk i vikt.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori: direkt utsläppsminskning
- Kort motivering: Kommunen ändrar själv sina materialval i egna renoveringar genom krav i projektering och upphandling, och därmed ändras aktiviteten direkt hos kommunen. Ingen kedja över andra aktörers beteende behövs. Profilens typ "Organisation/styrning" är en styrform, men effekten uppstår direkt i kommunens egna projekt. (ANTAGANDE: kravet beslutas och följs i alla berörda projekt, utan mellanliggande beteendeförändring hos externa aktörer; entreprenörer följer kravet via avtalsvillkor.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Ett viktbaserat mått kan ge liten klimatnytta om återbruket domineras av tunga material med låg klimatintensitet.
  - Det är oklart hur stor andel av materialet som tekniskt och praktiskt går att återbruka (tillgång, kvalitet, garantier).
  - Återbruksledets utsläpp (transport, rekonditionering) kan i vissa fall minska nettonyttan.
  - Överlapp med andra åtgärder (klimatkrav i byggupphandling, cirkulär upphandling, avfallsminskning) kan ge dubbelräkning.
  - Omfattningen (antal projekt, yta, beloppsgräns) bygger på antaganden.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Fastighetsförvaltningens investerings- och underhållsplan med faktiska projekt, ytor och beloppsgräns.
  - Materialinventeringar och erfarenheter från tidigare återbruksprojekt, till exempel via CCBuild, med återbruksandelar per materialkategori.
  - Klimatdata (EPD eller generiska data) per materialkategori samt uppgifter om transport och rekonditionering av återbrukat material.
  - Uppgift om hur kravet ska följas upp och mätas.

4. EMAP-drivare

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  aktivitet_matt: inköpt mängd nyproducerat byggmaterial, ton/år (kg per m² renoverad yta gånger renoverad yta, per materialkategori)
  EF_enhet: kg CO2e/kg material
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: byggnader
  mekanism: Shift, ΔA: Nyproducerat material ersätts av återbrukat material (minst 20 % av materialvikten), så att mängden inköpt nytt material minskar; kommunen ändrar sina egna materialval.
  overlapp_risk: medel. Samma minskning kan räknas i generella klimatkrav i byggupphandling eller cirkulär upphandling.

Drivare 2: Transport, lagring och rekonditionering av återbrukat material
  aktivitet_matt: mängd återbrukat material som hanteras, ton/år (inklusive transportarbete, tonkm/år, där det är relevant)
  EF_enhet: kg CO2e/kg material (alternativt kg CO2e/tonkm för transport)
  utsläppstyp: konsumtionsbaserade
  locus: båda
  sektor: transport
  mekanism: Avoid, ΔA: Ny aktivitet tillkommer (ökning) genom hantering av återbrukat material, vilket delvis motverkar nyttan i Drivare 1; kommunen och dess entreprenörer ändrar sin materialhantering. (ANTAGANDE: tillkommande utsläpp redovisas som ökning och räknas som negativ del av nettoeffekten.)
  overlapp_risk: låg. Utsläppen är specifika för återbruksledet och räknas inte i andra drivare.

Drivare 3: Byggavfall från renoveringar
  aktivitet_matt: mängd byggavfall som går till avfallshantering (förbränning och deponi), ton/år
  EF_enhet: kg CO2e/kg avfall
  utsläppstyp: territoriella
  locus: inom kommunen
  sektor: avfall
  mekanism: Avoid, ΔA: Mer material återanvänds på plats eller via plattformar i stället för att rivas och bli avfall, så att avfallsmängden minskar. (ANTAGANDE: avfallshanteringen sker i huvudsak inom kommunen eller regionen; effekten är marginell jämfört med Drivare 1.)
  overlapp_risk: medel. Samma minskning kan räknas i åtgärder för avfallsminskning eller cirkulär upphandling.

---