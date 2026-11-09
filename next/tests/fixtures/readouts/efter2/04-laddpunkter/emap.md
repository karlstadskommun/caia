---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Publika laddpunkter i flerbostadsområden

1. Sammanfattning
Åtgärden bygger 120 publika laddpunkter i fyra stadsdelar där cirka 4 000 hushåll bor inom gångavstånd. Den påverkar främst körsträckan med bensin- och dieselbilar bland boende utan egen laddplats, eftersom de byter till elbil när laddning blir tillgänglig. Som en bieffekt tillkommer utsläpp från elen som laddningen använder. Effekten räknas som en kedja på drivarna: hur många som nås, hur stor andel som byter till elbil, hur mycket de kör och hur stor del av bytet som är åtgärdens förtjänst utöver den nationella elektrifieringstrenden.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori: indirekt/möjliggörande
- Kort motivering: Laddpunkterna minskar inga utsläpp själva. De tar bort ett hinder så att boende i flerbostadshus (främst hyresrätter och bostadsrättsföreningar utan egen laddplats) lättare väljer elbil i stället för fossilbil. Kommunen gör inget annat för att få fler att köpa elbil, så effekten är bara det tillskott som laddtillgången utlöser. (ANTAGANDE: Laddpunkterna är i huvudsak normalladdning för nattladdning och används av de boende i närområdet.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Additionalitet: hur stor andel av elbilsbyten som beror på laddpunkterna och hur stor andel som hade skett ändå genom den nationella trenden eller privat utbyggnad.
  - Antal bilar bland de berörda hushållen är okänt (ANTAGANDE: 0,6–0,8 bilar per hushåll).
  - Okänd befintlig och planerad privat laddning i områdena.
  - Okänt hur stor del av laddningen som görs av boende i området jämfört med andra.
  - Elbilar kan ersätta bensin- och dieselbilar olika, och elmixen för laddningen är en metodfråga.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Bilinnehav och bilparkens drivmedelsfördelning per stadsdel.
  - Kartläggning av befintlig och planerad laddning.
  - Erfarenheter och utvärderingar från liknande satsningar i andra kommuner, särskilt om elbilsandel före och efter.
  - Enkät eller intervjuer med boende om laddning som köphinder.
  - Uppgifter om laddpunkternas användning (kWh per laddpunkt och år).

4. EMAP-drivare

Drivare 1: Körsträcka med bensin- och dieselbilar bland boende utan egen laddplats
  aktivitet_matt: fordonskilometer med fossildrivna personbilar, km/år, för bilar som ägs av hushåll inom upptagningsområdet
  EF_enhet: kg CO2e/km
  utsläppstyp: territoriella
  locus: inom kommunen
  sektor: transport
  mekanism: Shift, ΔA: fossilbilar byts mot elbilar och deras körsträcka minskar i motsvarande grad. Det är boende i flerbostadshus utan egen laddplats som byter bil, tidigare eller i stället för en ny fossilbil, tack vare tillgänglig laddning.
  overlapp_risk: hög, samma minskning kan räknas i Drivare 2 (elbilarnas körsträcka och elanvändning) och överlappar den nationella elektrifieringstrenden (EU:s CO2-krav, reduktionsplikt) som ska ligga i BAU.

Drivare 2: Elbilars körsträcka och elanvändning för laddning vid de publika laddpunkterna
  aktivitet_matt: laddad energi, kWh/år, för elbilar som ersätter fossilbilar och laddar vid de nya laddpunkterna
  EF_enhet: kg CO2e/kWh
  utsläppstyp: konsumtionsbaserade
  locus: båda
  sektor: energi
  mekanism: Shift, ΔA: elanvändningen för laddning ökar när boende byter till elbil (ökar utsläppen något). Samma boende som i Drivare 1 ändrar sig. (ANTAGANDE: Elmixen är nordisk eller svensk.)
  overlapp_risk: medel, utsläppen från elen är motposten till minskningen i Drivare 1 och ska räknas på samma byten för att undvika dubbelräkning eller att motposten missas.

---