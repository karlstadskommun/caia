---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Krav på laddbara tjänstebilar

1. Sammanfattning
Åtgärden byter ut cirka 180 fossildrivna tjänstebilar mot elbilar i förvaltningarnas flotta (60 per år 2027–2029, full effekt 2030). Den påverkar främst drivmedelsanvändningen (bensin och diesel) som minskar, samt elanvändningen som ökar. Effekten räknas rakt på drivarna: aktiviteten flyttas från fossildrift till eldrift, och den tillkommande elanvändningen dras av.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori: direkt utsläppsminskning
- Kort motivering: Kommunen äger eller leasar bilarna och bestämmer själv vilka fordon som anskaffas, så bytet sker direkt och ingen annan aktör behöver ändra beteende. Profilen anger typ "organisation/styrning", men effekten uppstår när bilarna byts och räknas därför rakt på drivarna. (ANTAGANDE: kravet följs vid varje bytestillfälle och leder till faktiskt fordonsbyte i angiven takt.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Hur stor del av bytena som hade blivit elbilar ändå (BAU), eftersom kommunen har höga miljöambitioner och marknaden utvecklas.
  - Om laddhybrider tillåts i större utsträckning än antaget, vilket ger lägre effekt.
  - Faktisk körsträcka per bil (antagen 1 200 mil/år, intervall 1 000–1 500 mil) och om elbilarna körs lika mycket som de bilar de ersätter.
  - Hur stor del av nuvarande bränsle som är biodrivmedel, vilket styr fossilutsläppen per km.
  - Konsumtionsbaserade utsläpp från fordons- och batteritillverkning är en separat drivare och kan vara svåra att kvantifiera.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Fordonsregister eller fleet management-data med bilar, drivmedel, körsträcka och leasingperioder.
  - Det beslutade kravets exakta text (elbil eller laddhybrid, undantag, bolagens omfattning).
  - Kommunens inköps- eller leasinghistorik för andelen elbilar de senaste åren.
  - Statistik över drivmedelsinköp och biodrivmedelsandel.

4. EMAP-drivare

Drivare 1: Körsträcka med fossildrivna tjänstebilar (bensin/diesel)
  aktivitet_matt: fordonskilometer för de 180 berörda tjänstebilarna som körs på bensin eller diesel, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: kommunens egna
  locus: inom kommunen
  sektor: transport
  mekanism: Shift, ΔA: fossildriven körsträcka minskar när bilarna byts mot elbilar, och kommunen är den som ändrar sig.
  overlapp_risk: medel, samma minskning kan även räknas som territoriella utsläpp inom kommunen och som konsumtionsbaserade utsläpp (drivmedelsproduktion) om kategorierna summeras.

Drivare 2: Elanvändning för laddning av tjänstebilar
  aktivitet_matt: elanvändning för elbilarnas körning, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: energi
  mekanism: Shift, ΔA: tillkommande elanvändning uppstår när körsträckan flyttas från fossildrift till eldrift, och påverkar nettoeffekten negativt. (ANTAGANDE: nationell eller nordisk elmix, eftersom elen främst produceras utanför kommunen.)
  overlapp_risk: medel, samma elanvändning kan räknas i Åtgärdsprofil 2 om laddpunkterna också används för tjänstebilarna, och ska då räknas endast här.

Drivare 3: Fordons- och batteritillverkning för nyanskaffade elbilar
  aktivitet_matt: antal anskaffade fordon, fordon/år
  EF_enhet: kg CO2e/fordon
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: konsumtion
  mekanism: Shift, ΔEF: tillverkningsutsläppen per fordon är högre för elbil än för fossilbil, vilket minskar nettonyttan, och kommunen ändrar sig via inköpet. (ANTAGANDE: tas med som en negativ korrektion eftersom profilen nämner fordons- och batteritillverkning.)
  overlapp_risk: låg, ingen annan drivare i denna eller Åtgärdsprofil 2 omfattar tillverkningsutsläpp för tjänstebilarna.

---
EMAP-ANALYS (FÖRENKLAD VARIANT)
EMAP-analys av åtgärd: Laddinfrastruktur vid kommunala arbetsplatser

1. Sammanfattning
Åtgärden bygger cirka 200 laddpunkter vid 25 arbetsplatser (budget 12 Mkr). Laddpunkterna möjliggör Åtgärdsprofil 1, men den effekten räknas bara där. Här räknas bara den tillkommande effekten av att cirka 1 500 anställda kan ladda privata bilar, vilket ger fler elbilar bland pendlare. Effekten räknas som en kedja på körsträckan med fossildrivna privatbilar vid pendling.

2. EMAP-kategorisering

2.1 EMAP_Effektkategori
- Vald kategori: indirekt/möjliggörande
- Kort motivering: Laddpunkterna ändrar inget beteende själva, men gör det enklare och billigare för anställda att välja och använda elbil. De anställda som pendlar med bil till de 25 arbetsplatserna ändrar sig, och effekten räknas som kedja: nådda anställda, andel som byter eller laddar, körsträcka per person och åtgärdens egen förtjänst utöver det som hade hänt ändå. (ANTAGANDE: anställda får ladda privata bilar mot avgift när laddpunkterna inte används av tjänstebilar.)

3. Osäkerheter
- Viktigaste osäkerheter i denna EMAP-bedömning:
  - Om anställda får ladda och vad det kostar, vilket avgör hela kedjan.
  - Hur stor andel av de 1 500 anställda som pendlar med bil och hur långt.
  - Hur stor del av elbilsbytena som hade skett ändå, eftersom elbilsandelen ökar snabbt i hela landet.
  - Risk att laddning flyttar annan laddning (hemma) snarare än fossil körsträcka, vilket ger liten nettoeffekt.
  - Om laddning på jobbet ökar bilanvändningen (bytt från kollektivtrafik eller cykel) så att nettoeffekten minskar.
- Vilken typ av underlag som skulle minska osäkerheten:
  - Resvaneundersökning eller medarbetarenkät om färdmedel, pendlingsavstånd och bilägande.
  - Erfarenheter från andra arbetsgivare med laddning för anställda.
  - Beslut om tillgång och prissättning för anställdas laddning.
  - Utnyttjandegrad och tidsprofil för laddpunkterna när tjänstebilarna inte laddar.

4. EMAP-drivare

Drivare 1: Körsträcka med fossildrivna privatbilar vid pendling till kommunala arbetsplatser
  aktivitet_matt: fordonskilometer för anställdas bilpendling till de 25 arbetsplatserna med bensin- eller dieselbilar, km/år
  EF_enhet: kg CO2e/km
  utsläppstyp: territoriella
  locus: båda
  sektor: transport
  mekanism: Shift, ΔA: fossildriven pendlingskörsträcka minskar när anställda byter till eller använder elbil tack vare laddmöjligheten, och det är de anställda som ändrar sig. (ANTAGANDE: pendling sker delvis inom och delvis utanför kommunen, och bara andelen inom kommunen räknas som territoriell.)
  overlapp_risk: medel, samma minskning kan även räknas som konsumtionsbaserade utsläpp (drivmedelsproduktion) om kategorierna summeras.

Drivare 2: Elanvändning för anställdas laddning av privata elbilar
  aktivitet_matt: elanvändning för laddning av anställdas privata bilar vid arbetsplatserna, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: konsumtionsbaserade
  locus: utanför kommunen
  sektor: energi
  mekanism: Shift, ΔA: tillkommande elanvändning följer av att pendlingskörsträckan flyttas från fossildrift till eldrift, och påverkar nettoeffekten negativt. (ANTAGANDE: nationell eller nordisk elmix.)
  overlapp_risk: medel, elen kan delvis ersätta laddning som annars skett hemma, och tjänstebilarnas elanvändning ska räknas bara i Åtgärdsprofil 1.

Drivare 3: Elanvändning för laddning av tjänstebilar vid arbetsplatserna
  aktivitet_matt: elanvändning för tjänstebilarnas laddning, kWh/år
  EF_enhet: kg CO2e/kWh
  utsläppstyp: ingen direkt (enabler)
  locus: utanför kommunen
  sektor: energi
  mekanism: Shift, ΔA: laddpunkterna möjliggör att tjänstebilarna kan köras på el, men hela effekten räknas i Åtgärdsprofil 1.
  overlapp_risk: hög, hela effekten räknas i Åtgärdsprofil 1 (Drivare 1 och 2) och får inte räknas här.

---