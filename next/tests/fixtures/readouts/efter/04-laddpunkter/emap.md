---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Publika laddpunkter i flerbostadsområden

1. Sammanfattning
Åtgärden påverkar utsläppen från personbilstrafik bland boende i fyra stadsdelar (omkring 4 000 hushåll, cirka 2 400 bilar) genom 120 publika laddpunkter. Främst minskar körsträckan med fossildrivna personbilar när fler boende byter till elbil, och i andra hand ökar elandelen hos befintliga laddbara bilar. Elanvändningen för laddning är en motverkande drivare. Effekten räknas som en kedja på drivarna, inte som ett direkt tal på laddpunkterna.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori: indirekt/möjliggörande
- Kort motivering: Laddpunkterna minskar inte utsläpp själva. De gör det enklare att välja elbil för boende utan egen laddplats, och det är de boende (hushåll i de fyra stadsdelarna) som byter bil eller laddar mer. Kedjan är antal berörda bilar, andel som byter, körsträcka per bil och åtgärdens additionalitet. Kommunen gör inget annat för att främja elbil, så hela effekten hänger på att laddtillgången sänker tröskeln. (ANTAGANDE: laddpunkterna är en av flera orsaker till bilbyte, så bara en liten andel av bytena är additionella.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Hur stor andel av bilbytena som beror på laddpunkterna och inte hade skett ändå (nationella styrmedel, EU-krav, privata aktörer och bostadsbolag som bygger laddning).
  - Om boende faktiskt använder publik laddning som sin huvudsakliga laddning, med tanke på pris, tillgänglighet och beläggning.
  - Rekyleffekter: bilfria hushåll kan skaffa bil, eller bilägare kör mer när driftkostnaden sjunker.
  - Elbilsandelen idag (ANTAGANDE: 5–10 %) och körsträcka per bil är inte verifierade.
  - Elmixens utsläppsfaktor för laddning och risk för dubbelräkning mot andra transportåtgärder.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Registerdata om elbilsandel och bilinnehav per stadsdel.
  - Beläggning och användarstatistik från befintliga publika laddare, samt enkäter eller intervjuer med boende om hur laddtillgång påverkar bilvalet.
  - Plan för privata och bostadsbolagens laddutbyggnad i samma områden.
  - Studier av hur laddtillgång påverkar elbilsköp i flerbostadsområden.

4. EMAP-drivare

Drivare 1: Körsträcka med fossildrivna personbilar bland boende i de fyra stadsdelarna
  aktivitet_matt: fordonskilometer med bensin- och dieselbilar, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: territoriella
  locus: inom kommunen
  sektor: transport
  mekanism: Shift, ΔA: körsträckan med fossildrivna bilar minskar när boende byter från fossilbil till elbil tack vare laddmöjligheten nära bostaden. Det är de boende hushållen som ändrar sig. (ANTAGANDE: utsläppen räknas där bilarna kör, huvudsakligen i kommunen. Resor utanför kommunen faller under drivare 2.)
  overlapp_risk: hög, samma bilbyte kan räknas i andra åtgärder för elbilsövergång i klimatplanen och i nationella styrmedel. Det kan också räknas i drivare 2 och 3.

Drivare 2: Konsumtionsbaserade utsläpp från boendes bilresor med fossildrivna bilar
  aktivitet_matt: fordonskilometer med bensin- och dieselbilar utanför kommunen och bränslets upstream-del, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: konsumtionsbaserade
  locus: båda
  sektor: transport
  mekanism: Shift, ΔA: samma bilbyte som i drivare 1 minskar även bränsleförsörjningens utsläpp och resor utanför kommunen. Det är de boende som byter bil. (ANTAGANDE: drivaren används bara för den del som inte redan ligger i drivare 1, annars dubbelräknas den.)
  overlapp_risk: hög, överlappar nästan helt med drivare 1 om den inte avgränsas till upstream och körning utanför kommunen.

Drivare 3: Elanvändning för laddning av elbilar hos boende
  aktivitet_matt: elanvändning för fordonsladdning, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: energi
  mekanism: Shift, ΔA: elanvändningen ökar när fossilbilar ersätts av elbilar och när befintliga elbilsägare laddar mer vid de nya laddpunkterna. Det är en motverkande drivare, där utsläppen ökar. (ANTAGANDE: nordisk eller svensk elmix, i linje med profilens kommentar.)
  overlapp_risk: medel, den ökade elanvändningen följer direkt av bilbytet i drivare 1 och bör nettas mot den minskningen och inte räknas separat som en egen effekt.

Drivare 4: Andel eldrift hos befintliga laddhybrider
  aktivitet_matt: körsträcka med laddhybrider som körs på bensin eller diesel, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: territoriella
  locus: inom kommunen
  sektor: transport
  mekanism: Improve, ΔEF: laddhybridägare bland de boende laddar oftare och kör en större andel av sträckan på el, så utsläppen per km sjunker. Det är befintliga laddhybridägare som ändrar sig. (ANTAGANDE: sekundär effekt som är liten jämfört med drivare 1.)
  overlapp_risk: medel, laddhybridernas elanvändning kan också ingå i drivare 3, och andelen eldrift kan påverkas av andra laddinsatser.

---