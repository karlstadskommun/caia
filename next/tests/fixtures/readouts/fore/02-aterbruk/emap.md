---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Krav på minst 20 % återbrukat byggmaterial vid kommunens större renoveringar

1. Sammanfattning
Åtgärden är ett internt krav och en upphandlingsregel, alltså en organisation/styrning-åtgärd (EMAP_Åtgärdstyp: Organisation/styrning). Huvudmekanismen är Avoid, eftersom efterfrågan på nyproducerat byggmaterial minskar när återbrukat material ersätter det. Nivån är verksamhet/organisation, eftersom kravet gäller kommunens egen fastighetsverksamhet. Effektkategorin är direkt utsläppsminskning, eftersom minskad materialtillverkning (A1–A3) ger lägre utsläpp i varje projekt. Den största osäkerheten är hur de 20 procenten mäts och vilka produktgrupper som omfattas.

2. EMAP-kategorisering

2.1 EMAP_Åtgärdstyp
- Vald kategori: Organisation/styrning
- Kort motivering: Åtgärden genomförs genom interna riktlinjer och krav i upphandlingsunderlag, inte genom ny teknik eller ny infrastruktur. Kommunen har direkt rådighet över sina egna fastigheter. (ANTAGANDE: kravet är ett internt styrdokument och inte ett externt regelverk, därför väljs inte Reglering/krav/standard.)

2.2 EMAP_Mekanism (Avoid / Shift / Improve)
- Vald kategori: Avoid
- Kort motivering: Behovet av nytillverkat byggmaterial minskar när befintligt material används igen. Det är ingen flytt till ett annat nyproducerat alternativ och ingen effektivisering av en befintlig process. (ANTAGANDE: återbruk tolkas som undviken nyproduktion, inte som Shift mellan materialslag.)

2.3 EMAP_Nivå
- Vald nivå (individ/hushåll, verksamhet/organisation, system/struktur): verksamhet/organisation
- Kort motivering: Kravet gäller kommunens egen fastighetsförvaltning och dess entreprenörer. Det ändrar inte marknaden i stort, även om det kan stimulera lokal återbruksefterfrågan. (ANTAGANDE: eventuella marknadseffekter utanför kommunens egna projekt ingår inte.)

2.4 EMAP_Tidsprofil för effekt
- Vald kategori (kort / medel / lång / blandad): medel
- Kort motivering: Kravet gäller från 2027 och effekten uppstår projekt för projekt när renoveringar genomförs. Uppbyggnad av inventering, mellanlagring och leverantörsflöden gör att full effekt sannolikt nås först efter några år. (ANTAGANDE: full effekt nås inom 3–10 år.)

2.5 EMAP_Mognad
- Vald kategori (idé/koncept, pilot/försök, uppskalning, etablerad/ordinarie): pilot/försök
- Kort motivering: Återbruk i byggprojekt förekommer men är inte ordinarie praxis, och ett kommunövergripande krav med kvantifierad andel är nytt. (ANTAGANDE: kommunen har begränsad tidigare erfarenhet av ett systematiskt återbruksflöde, och BAU-återbruket antas ligga på cirka 0–5 %.)

2.6 EMAP_Effektkategori
- Vald kategori (direkt utsläppsminskning, indirekt/enabler, stödjande/styrning): direkt utsläppsminskning
- Kort motivering: Varje kilo återbrukat material ersätter nyproducerat material och undviker dess tillverkningsutsläpp. Kravet är i sig styrning, men effekten uppstår direkt i materialflödet. (ANTAGANDE: kravet följs och leder till faktiskt ersatta inköp.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Hur 20 % definieras (vikt, kostnad eller klimatpåverkan) och vilka produktgrupper som undantas.
  - Hur många projekt som faktiskt klassas som större renovering och deras volym.
  - Om kommunen hinner bygga upp tillgången på återbrukat material, vilket påverkar mognad och tidsprofil.
  - Hur stort återbruket redan är i BAU.
  - Om återbruk ersätter nytt material 1:1 och hur transporter, lagring och kvalitetssäkring påverkar nettoeffekten.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Beslutad definition av kravet, med mätmetod och undantag.
  - Investerings- och underhållsplan med projektlista, ytor och budget.
  - Inventering av tidigare återbruksprojekt och eventuella klimatdeklarationer eller LCA från renoveringar.
  - Uppgifter från återbruksplattformar om tillgång, pris och leveranstider.
  - Emissionsfaktorer per produktgrupp för A1–A3.

4. EMAP-drivare

Drivare 1: Tillverkning av nyproducerat byggmaterial i kommunens större renoveringar
  aktivitet_matt: inköpt mängd nyproducerat byggmaterial inom omfattade produktgrupper, ton/år
  EF_enhet: kg CO2e/kg material (A1–A3, per produktgrupp)
  utsläppstyp: kommunens egna
  locus: utanför kommunen
  sektor: byggnader
  overlapp_risk: medel. Samma minskning kan även räknas som konsumtionsbaserade utsläpp för kommunens inköp, och ska då inte summeras.

Drivare 2: Byggavfall från rivning till förbränning och deponi
  aktivitet_matt: mängd byggavfall från renoveringsprojekt som går till förbränning eller deponi, ton/år
  EF_enhet: kg CO2e/ton avfall
  utsläppstyp: territoriella
  locus: båda
  sektor: avfall
  overlapp_risk: hög. Samma avfallsminskning kan räknas i kommunens avfallsrelaterade åtgärder, och risken för dubbelräkning mot dem är hög.

Drivare 3: Transporter av byggmaterial och återbrukat material
  aktivitet_matt: transportarbete för material till och från projekt och mellanlager, tonkilometer/år
  EF_enhet: kg CO2e/tonkm
  utsläppstyp: territoriella
  locus: båda
  sektor: transport
  overlapp_risk: medel. Transportförändringen kan även ingå i kommunens åtgärder för transporter och i leverantörskedjans utsläpp (Drivare 1). (ANTAGANDE: nettoeffekten är liten.)

Drivare 4: Inventering, mellanlagring och kvalitetssäkring av återbrukat material
  aktivitet_matt: energianvändning och drivmedel för hantering och lagring, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: kommunens egna
  locus: inom kommunen
  sektor: energi
  overlapp_risk: låg. Utsläppen är små och uppstår bara i denna åtgärd, men kan ingå i kommunens allmänna energianvändning för fastigheter. (ANTAGANDE: hanteringen ger en liten ökning av utsläppen.)
---