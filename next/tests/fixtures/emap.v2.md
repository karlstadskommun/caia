---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Publika laddpunkter i bostadsområden

1. Sammanfattning
Åtgärden bygger 120 publika laddpunkter i flerbostadsområden där de boende saknar egen laddplats. Den gör det enklare att äga elbil, så fler boende väljer elbil när de byter bil. Effekten räknas som en kedja på de boendes körning med fossildrivna bilar, och elen till laddningen räknas som en egen drivare.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori (direkt utsläppsminskning, indirekt/möjliggörande, stödjande/styrning): indirekt/möjliggörande
- Kort motivering: Laddpunkterna minskar inte utsläpp själva, men de tar bort ett hinder för boende utan egen laddplats. Några av dem väljer elbil tidigare än de annars hade gjort. (ANTAGANDE: Effekten gäller boende inom gångavstånd från laddpunkterna.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Hur stor andel som byter till elbil tack vare laddpunkterna och inte ändå.
  - Hur många hushåll som saknar egen laddplats.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Antal hushåll och bilar inom gångavstånd.
  - Erfarenheter från liknande satsningar i andra kommuner.

4. EMAP-drivare

Drivare 1: Körsträcka med fossildrivna privatbilar hos boende nära laddpunkterna
  aktivitet_matt: fordonskilometer, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: territoriella
  locus: båda
  sektor: transport
  mekanism: Shift, ΔA: boende som väljer elbil tack vare laddpunkterna kör färre km med fossilbil.
  overlapp_risk: hög. Samma byte drivs också av nationella styrmedel och bilparkens naturliga omställning.

Drivare 2: Elanvändning för laddning vid de publika laddpunkterna
  aktivitet_matt: elanvändning, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: energi
  mekanism: Shift, ΔA: elanvändningen ökar när körningen flyttar till el.
  overlapp_risk: medel. Ska nettas mot minskningen i Drivare 1.

---
