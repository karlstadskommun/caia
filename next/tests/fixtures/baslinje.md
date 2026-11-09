Baslinje & BAU-analys för åtgärd: Krav på laddbara tjänstebilar och utbyggnad av laddinfrastruktur vid kommunala arbetsplatser

---

## Kort om detta steg

Utifrån EMAP-analysen sätter jag nu en nulägesbaslinje (A0 och EF0) per drivare och definierar ett BAU-scenario – det vill säga hur aktivitet och emissionsfaktorer utvecklas fram till 2026 och 2030 utan de aktuella åtgärderna. EMAP identifierade en direkt kvantifierbar drivare (fossildrivna tjänstebilar) och en indirekt/enabler-drivare (laddinfrastruktur). Baslinjen för den direkta drivaren bygger på grova uppskattningar eftersom specifika uppgifter om kommunens fordonsflotta saknas i tillgängligt underlag. Resultatet lämnas vidare till Evidens & Antaganden-agenten som kopplar på åtgärdseffekter och antagandespann.

---

## Underlag från EMAP

EMAP-analysen identifierade två delåtgärder och två drivare. Huvudsektorn är transport, specifikt kommunens egna tjänstebilar (verksamhetsnivå). Den direkt kvantifierbara drivaren är körsträcka och emissionsfaktor för icke-laddbara (fossila/gas) tjänstebilar. Den andra drivaren – laddinfrastruktur – klassades som en indirekt enabler utan egna direkta utsläpp, och behandlas därför som en stöddrivare utan separat utsläppsbaslinje. En viktig notering från EMAP är att åtgärd 2 (infrastruktur) är en funktionell förutsättning för att åtgärd 1 (kravet) ska ge full effekt.

---

## Nulägesbaslinje per drivare

**Drivare 1: Körsträcka med icke-laddbara tjänstebilar i kommunens flotta**
  Nuläge_år: 2023
  A0: 3,0e6
  A0_enhet: km/år
  EF0: 0,13
  EF0_enhet: kg CO2/km
  Källor_nuläge: EF_municipal_cars_avg (parameterbiblioteket anger 0,0–0,05 kg CO2/km som genomsnitt för hela nuvarande kommunflotta, med notering om att flertalet fordon redan är el eller gas). Eftersom åtgärden explicit syftar till att öka andelen laddbara fordon antas en väsentlig andel av flottan fortfarande vara icke-laddbar idag. EF0 = 0,13 kg CO2/km avser den icke-laddbara delflottans genomsnitt (bensin/diesel/gas-körning), baserat på EF_passenger_car_avg (0,12–0,18 kg CO2/km) och EF_petrol_tank_to_wheel. Aktivitetsnivån A0 är estimerad: ~400 tjänstebilar totalt (ANTAGANDE, baserat på 8 000 anställda och typisk kommunal flottakvot om 1 bil per 20 anställda), varav ~50 % bedöms som icke-laddbara idag (ANTAGANDE), med ~15 000 km/fordon/år (ANTAGANDE för tjänstebilar). 200 fordon × 15 000 km = 3,0e6 km/år. Indirekt kontroll: 3,0e6 km × 0,13 kg CO2/km ≈ 390 ton CO2/år. Jämförelsevis redovisar kommunkoncernens konsumtionsbaserade fotavtryck 5 889 ton CO2e för "Bil, buss och tåg" totalt (DATA_MUNICIPAL_ORG) – varav den egna bilflottans fossildel bedöms stå för en mindre del, vilket är i rimlig storleksordning.
  Kommentar_nuläge: Datakvalitet låg. Alla tre ingående faktorer (flottstorlek, icke-laddbar andel, körsträcka per fordon) är antaganden. Parameterbiblioteket indikerar att kommunens flotta redan är till stor del elektrifierad/gasdrivet, men åtgärdens existens bekräftar att omställningen inte är fullständig. Baslinjen avser enbart den icke-laddbara delflottans utsläpp – den del åtgärden riktar sig mot.

---

**Drivare 2: Laddinfrastruktur vid kommunala arbetsplatser (enabler)**
  Nuläge_år: 2023
  A0: 0
  A0_enhet: –
  EF0: 0
  EF0_enhet: –
  Källor_nuläge: Ingen relevant parameter i biblioteket. Infrastrukturen genererar inga direkta utsläpp i nuläget och har ingen kvantifierbar utsläppsbaslinje.
  Kommentar_nuläge: Drivare 2 är en indirekt/enabler-drivare enligt EMAP-klassificeringen. Den har ingen egen utsläppsbaslinje utan möjliggör att Drivare 1 kan ge full effekt. Klimatnyttan för denna drivare kvantifieras inte separat – effekten är inbakad i Drivare 1. Bygg- och installationsutsläpp för laddinfrastrukturen (inbäddad CO2) är inte beaktade här men kan vara relevanta i en fullständig livscykelanalys.

---

## BAU-scenario per drivare

**Drivare 1: Körsträcka med icke-laddbara tjänstebilar i kommunens flotta**
  BAU_Tier: 2
  BAU_motivering: Naturlig flottomsättning sker kontinuerligt och påverkas av nationella styrmedel (bonus-malus, upphandlingsregler, EU-krav på nybilsförsäljning). Utan det specifika kommunala mandatet antas en gradvis men långsammare elektrifiering av kommunens fordon, driven av nationella trender snarare än ett lokalt krav. Tier 2 väljs eftersom redan beslutade nationella policies (EU:s krav på nollutsläpp i nybilsförsäljning 2035, nationellt bonus-malus-system) skapar en nedåtgående trend i fossil körsträcka även utan denna åtgärd.
  BAU_trend_A (g_A):
    - låg: -2 %/år. Flottan förnyas i långsam takt och en del fordon ersätts med laddbara vid naturlig utrangering. Konservativt scenario där inköpsbeslut inte drivs aktivt mot laddbara alternativ.
    - medel: -5 %/år. Kombinerat tryck från nationella styrmedel och interna miljömål leder till att en större andel nyanskaffningar är laddbara, men utan specifikt lokalt krav är takten måttlig.
    - hög: -8 %/år. Nationella upphandlingskrav och internt hållbarhetstryck gör att majoriteten av nyanskaffningar är laddbara redan utan det formella lokala mandatet. Snabbare naturlig utfasning av fossil delflotta.
  BAU_trend_EF (g_EF):
    - låg: -1 %/år. Marginell förbättring i de kvarvarande fossila fordonens bränsleeffektivitet vid naturlig flottaomsättning.
    - medel: -2 %/år. Nyare bensin/dieselbilar och ökande gasblandning ger något lägre EF för de icke-laddbara fordon som faktiskt köps in under BAU.
    - hög: -3 %/år. Snabbare skifte mot t.ex. HVO/biodrivmedel i de kvarvarande fossila fordonen, vilket pressar ner EF.
  BAU_årpunkter: 2026, 2030
  Kommentar_BAU: I BAU-scenariot minskar A (icke-laddbar körsträcka) successivt i takt med att fordon byts ut, men utan det formella kravet är takten lägre än i åtgärdsscenariot. EF-trenden är svag eftersom det primärt är andelen laddbara (A-sidan) snarare än effektivisering av kvarvarande fossila fordon (EF-sidan) som driver utsläppsminskningen. Den sammantagna BAU-trenden för utsläpp (A × EF) beräknas i nästa steg, men är i storleksordningen -3 till -11 %/år beroende på scenario. BAU 2026 och 2030 är relevanta kontrollpunkter eftersom åtgärden genomförs 2027–2030 och effekten ska mätas mot BAU-banan för dessa år.

---

**Drivare 2: Laddinfrastruktur vid kommunala arbetsplatser (enabler)**
  BAU_Tier: 0
  BAU_motivering: Drivaren saknar kvantifierbar utsläppsbaslinje och BAU-trend. Tier 0 väljs som en formell markering att inga trendantaganden tillämpas. Klimateffekten av denna drivare är helt beroende av i vilken mån infrastrukturen faktiskt möjliggör användning av laddbara fordon, vilket hanteras inom Drivare 1.
  BAU_trend_A (g_A):
    - låg: 0 %/år
    - medel: 0 %/år
    - hög: 0 %/år
  BAU_trend_EF (g_EF):
    - låg: 0 %/år
    - medel: 0 %/år
    - hög: 0 %/år
  BAU_årpunkter: 2026, 2030
  Kommentar_BAU: Drivare 2 är en enabler vars effekt hanteras samlat inom Drivare 1. Inga separata BAU-trender tillämpas. Om laddinfrastrukturens kvantitativa dimension (antal laddpunkter, investeringskostnad) ska redovisas sker det i Evidens & Antaganden-steget som ett antagande om adoptionsgrad snarare än som en separat utsläppsdrivare.

---

## Dataluckor för detta steg

- Saknar uppgift om exakt antal tjänstebilar i Karlstads kommunkoncern. Flottstorlek ~400 fordon är ett antagande baserat på personalstorlek och typisk kommunal kvot.
- Saknar uppgift om nuvarande andel laddbara vs icke-laddbara fordon i kommunens flotta. Parameterbiblioteket indikerar att flottan är till stor del elektrifierad/gasdrivet (EF_municipal_cars_avg), men hur stor andel som kvarstår som icke-laddbar är okänt. Andelen ~50 % icke-laddbar är ett antagande.
- Saknar uppgift om genomsnittlig körsträcka per tjänstebil och år. 15 000 km/fordon/år är ett schablonvärde.
- Oklart om "laddbara" i kravet avser enbart BEV eller även PHEV – avgörande för EF-effekten per fordon i åtgärdsscenariot (hanteras i nästa steg).
- Saknar tidsserie för kommunens egna fordonsflotta och dess drivmedelsmix, vilket gör det svårt att sätta en historisk trend för g_A.
- EF0 för den icke-laddbara delflottan är baserad på generell genomsnittsbil (EF_passenger_car_avg) – okänt om kommunens icke-laddbara fordon avviker (t.ex. om de inkluderar tyngre tjänstefordon med högre EF).
- Oklart om kommunkoncernens konsumtionsbaserade transportutsläpp (5 889 ton CO2e för "Bil, buss och tåg" i DATA_MUNICIPAL_ORG) inkluderar köpta transporttjänster, egna fordon eller båda – försvårar kalibrering av A0.

---

## Frågor till miljöstrateg för detta steg

- Hur många tjänstebilar har kommunkoncernen idag, och hur stor andel är redan laddbara (BEV eller PHEV)?
- Gäller kravet enbart helt eldrivna bilar (BEV) eller räknas även laddhybrider (PHEV) som uppfyllnad?
- Är laddinfrastrukturen avsedd enbart för kommunens egna tjänstebilar, eller ska anställda även kunna ladda sina privata fordon? (Påverkar om en ytterligare drivare för anställdas pendling bör läggas till i nästa steg.)
- Finns ett internt mål för andel laddbara tjänstebilar till 2030, t.ex. 100 %?
- Vilket basår för kommunens fordonsflotta är mest tillförlitligt – finns fordonsregister eller miljöredovisning att tillgå?