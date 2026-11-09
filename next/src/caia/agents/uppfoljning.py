"""What each step is told in follow-up mode (uppföljningsläge).

In potential mode every system prompt is exactly what it was before the mode
existed. In follow-up mode the step's prompt gets one block appended: the
shared method rules, then what this step does differently. The rules came
from the driftsmedel fact packages' reading instructions (läsanvisning, kept
with Karlstad's working material outside this repository) and the
review of the ten 2025 analyses (2026-09-30), which found the same faults in
analysis after analysis: effects that lasted too long, money credited for more
than it bought, discounts applied twice or not at all, and measured data that
never anchored the estimate. A package should carry facts; how to read them
belongs in the tool.
"""
from __future__ import annotations

from ..mode import UPPFOLJNING

KARNA = """<uppfoljningslage>
ANALYSLÄGE: UPPFÖLJNING. Analysen gäller en GENOMFÖRD insats. Frågan är inte vad
åtgärden kan ge, utan vilken klimatnytta just de här pengarna faktiskt har orsakat och
fortfarande orsakar. Allt annat i dina instruktioner gäller, men reglerna här går före
där de krockar.

Metodregler för uppföljning:
1. Jämförelsescenariot (BAU) är "utan just de här pengarna", inte "utan att kommunen gör
   något". Det som redan pågår i kommunen ingår i BAU: mål, beslut, krav, avtal, andra
   åtgärder och andra års pengar.
2. Det som hade hänt ändå räknas bort på ett enda ställe: i BAU, i ett ikapp-år, i en
   avklingning eller i attributionen, aldrig i flera. Gjorde pengarna bara att något kom
   tidigare (tidigareläggning), får de nyttan för de år det kom tidigare, inte för hela
   perioden. Säger underlaget att samma sak hade skett senare (fördröjd av budgeten, del
   av en plan, ett mål med ett årtal), är det en tidigareläggning även när året inte står:
   uppskatta ikapp-året ur planen, målet eller den gamla utrustningens utbytestakt, och säg
   varifrån. Att förvaltningen bara "kunde ha" gjort det ändå, utan stöd i underlaget, är
   däremot inget skäl att räkna bort något.
   Attributionen är pengarnas andel av förändringen. Den bedöms för varje drivare, med ett
   skäl åt båda hållen. Den är 1 bara för det pengarna själva utförde eller köpte och dess
   egen användning: tjänsten som levererades, maskinen som ersatte en annan. Går effekten
   genom andra människors beslut och vanor (kök som ändrar menyn, anställda och besökare
   som ändrar beteende, projektledare och entreprenörer som väljer material, deltagare som
   fortsätter cykla), är attributionen pengarnas del bland alla orsaker till förändringen:
   annat som drar åt samma håll samtidigt (andra insatser, regler, trender, beslut som
   redan fanns), och deltagarnas egen vilja. Den andelen är oftast under 1, och ett värde
   nära 1 kräver lika tydliga skäl som ett lågt. Det som redan räknats bort i BAU räknas
   inte bort en gång till i andelen.
3. Effekter av kampanjer, utbildning, information och beteendeförändring klingar av år för
   år. Låt dem inte ligga kvar på full nivå och sedan falla till noll. Ange hur fort de
   klingar av, som halveringstid i år, och varifrån det kommer. Krav i upphandlingar,
   beslut, avtal, rutiner och köpta saker är inga kampanjer: de klingar inte av, utan
   gäller så länge kravet, beslutet eller saken gäller, och slutar med ett slutår.
4. Uppmätt går före antaget. När uppföljningen redovisar en uppmätt siffra är den ankaret.
   Skilj hela vägen på det som är uppmätt och det som är antaget. Det gäller även hur länge
   effekten håller: visar uppföljningen hur stor andel som fortsatt efter en viss tid, ska
   halveringstiden i medel stämma med mätningen. Andelen r kvar efter t år ger
   halveringstiden t × ln 2 / (−ln r), så 90 procent kvar efter ett år är ungefär 6,6 år.
   Ett kortare antagande hör bara till det försiktiga scenariot. Säger underlaget när
   samma sak hade skett utan pengarna (budget, plan, avtal), är det ankaret för ikapp-året,
   före ett allmänt mål.
5. Max är ett rimligt högt scenario, inte alla ytterlägen samtidigt.
6. Nära noll är ett tillåtet svar, och "går inte att mäta än" likaså. Går effekten inte att
   kvantifiera med försvarbar osäkerhet: säg det, ge en storleksordning och skriv vad som
   skulle behöva mätas.
7. Ansökans förhandsbedömning och uppföljningens redovisade klimatnytta är uppgifter att
   pröva, inte facit.
8. Räkna bara det pengarna köpte. Köpte de ett underlag, en utredning eller ett material,
   är nyttan det som kom till stånd tack vare det, inte hela den framtida effekt underlaget
   handlar om. Har ingen användning av det redovisats än (ett verktyg, en databas, en
   vägledning), är användningen efter uppföljningsåret ett antagande: dess omfattning
   (antal projekt, mängder, användare) ska komma ur underlaget eller en angiven källa och
   aldrig uppskattas fritt, och i det försiktiga scenariot används det inte. Köpte de saker (cyklar, maskiner, utrustning) är nyttan de sakernas
   användning under deras livslängd, inte ett lika stort inköp varje år. Fanns ett krav
   eller en regel redan, och pengarna betalade en kontroll av den (prover, mätningar,
   uppföljning), är nyttan den bättre efterlevnad kontrollen ger, inte hela kravets effekt.
   Det som gjordes utan pengarna (med förvaltningens egen tid eller andra medel) är inte
   pengarnas nytta, även när det hör till samma projekt eller ansökan.
9. En insats som fått pengar flera år analyseras som en helhet. Beskriv vad varje års
   pengar köpte, så att nyttan sedan kan fördelas per bidragsår.
10. Insatsens egna utsläpp och dess nytta behandlas lika. Det som räknas bort från nyttan
   (det som hade hänt ändå, annan finansiering, ett år då BAU kommer ikapp) räknas bort
   från de egna utsläppen på samma sätt. Tidigarelade insatsen bara ett köp av utrustning,
   belastas den bara av de år av utrustningens livslängd som kom tidigare, inte av hela
   tillverkningen.
11. Bidragsbeloppet i sig är ingen utsläppskälla. Pengarna hade använts av kommunen ändå,
   så räkna aldrig "pengarnas egna utsläpp" (beloppet gånger utsläpp per krona). En egen
   utsläppspost ska gälla något fysiskt som köptes: utrustning, material, transporter,
   angivet i fysiska enheter.
12. Gav en pilot upphov till en verksamhet som består efter piloten och som inte hade
   funnits utan insatsen (en butik, en förening, en tjänst), räknas en del av
   verksamhetens effekt även efter piloten. Den delen är insatsens andel i att verksamheten
   finns. Att verksamheten "hade kommit ändå", senare, är en tidigareläggning och kräver
   belägg i underlaget. Utan belägg antas det inte. Undanträngning, att verksamhetens
   försäljning eller tjänst tar kunder från andra aktörer, är en egen andel med egen
   motivering, aldrig något som göms i attributionen.
13. Drivarens aktivitet är det som orsakar utsläppen, aldrig det som minskar dem. Undviker
   insatsen nyproduktion (återbruk, begagnat, reparation, lån), är aktiviteten den
   nyproduktion eller de nyköp som undviks, och insatsen sänker den: en minskning av
   aktiviteten. Den andel av den återbrukade mängden som faktiskt ersätter nytt
   (nettoandelen, ersättningsgraden) bestämmer hur stor minskningen är. Ställ aldrig upp
   den återbrukade mängden som en ökad aktivitet med lägre utsläpp per enhet: kalkylen
   läser mer aktivitet som mer utsläpp, och då vänds tecknet.
14. En drivare som ökar utsläppen (tillverkning, förluster, transporter) har sina värden i
   omvänd ordning mot nyttan: minst och kortast i det höga scenariot, störst och längst i
   det försiktiga. Det gäller mängd, faktor och slutår. Livslängden på köpt utrustning går
   åt andra hållet, kortast i det försiktiga: ju kortare livslängd, desto större del av
   tillverkningen belastar insatsen. Undantaget är en kostnad
   som växer med nyttan, som HVO som ersätter diesel eller laddel till maskiner som ersätter
   bensin: dess mängd och andel följer nyttans i varje scenario, så att ett försiktigt
   scenario med mindre undvikt bränsle också har mindre av det som ersätter det.
15. En kostnad blir aldrig en nytta. Tillverkning, inköp och transport av det pengarna
   köpte ökar utsläppen i alla tre scenarierna. Ställ upp en sådan post som den köpta
   mängden med sin egen faktor, aldrig som en ökning av en större mängd med en lägre faktor:
   då sänks faktorn på hela mängden och tillverkningen kan räknas som en minskning.
16. En följdeffekt som underlaget visar har inträffat räknas, även när underlaget inte säger
   hur stor den är: material som pengarna köpte och som används igen senare år, en senare
   satsning eller ett beslut som bygger på insatsen. Ge den en uttryckligen antagen andel,
   nära noll i det försiktiga scenariot, och märk den som antagande. Noll är rätt bara när
   underlaget inte visar att följdeffekten har inträffat. En följdeffekt som bara är möjlig
   räknas inte.
17. El räknas med 59 g CO2e/kWh i alla tre scenarierna: nordisk elmix, det värde
   Klimatklivet anger för att beräkna utsläppsminskningar (Naturvårdsverket 2026-03-25,
   efter IVL:s emissionsfaktor för nordisk elmix 2021–2023). Använd inte svensk
   genomsnittsmix, och lägg osäkerheten i mängden el, inte i faktorn. Undantaget är en
   drivare där skillnaden mellan timmar är själva effekten (lagring, el som flyttas till
   andra timmar): där får faktorn för de timmar det gäller avvika, med källa.
18. Köpt utrustning belastas bara med den del av sin livslängd som ryms till och med
   målåret, eftersom nyttan bara räknas dit: (målåret + 1 − köpåret) / livslängden av
   tillverkningen, högst hela. Ange därför alltid livslängd för utrustning som pengarna
   köpte, kortast i det försiktiga scenariot (regel 14). Är det okänt om utrustningen
   köptes eller hyrdes, eller om den användes vidare efter den tid nyttan räknas för, säg
   det och låt scenarierna täcka båda: belastningen till målåret i det försiktiga, bara
   de år nyttan räknas för i det höga (end_year = nyttans sista år).
"""

SLUT = "</uppfoljningslage>"

STEG = {
    "intake": """
I det här steget:
- Fråga, inom ramen för högst fyra frågor, efter det som saknas av: vad som planerades och
  vad som faktiskt genomfördes (kvantiteter och datum), beviljat och använt belopp per år,
  uppmätta utfall och hur de mättes, annan finansiering eller parallella insatser, och
  vilket år uppföljningen gäller. "Inga mätningar" är ett giltigt svar.
- Står omfattningen inte i underlaget (antal projekt, mängder, användare), skriv att den
  saknas. Hitta inte på den.
- Skapa EN profil för hela insatsen, även när den fått pengar flera år, om den inte
  uppenbart består av skilda åtgärder.
- Tidsram: från första bidragsåret till målåret.
- Lägg till dessa fält i profilen, efter *Kommun:* och före *Kommentarer:*, med samma
  skrivsätt som övriga fält:
*Analysläge:* uppföljning
*Bidragsår och belopp:* [per år: beviljat och använt belopp i kr]
*Planerat:* [vad pengarna skulle gå till enligt ansökan]
*Genomfört:* [vad som faktiskt gjordes, med kvantiteter och datum]
*Uppmätt utfall:* [mätningar och hur de gjordes, eller "inga"]
*Annan finansiering och parallella insatser:* [eller "inga kända"]
*Uppföljningsår:* [sista året som räknas som genomfört]
""",
    "emap": """
I det här steget:
- Kartlägg drivare för det pengarna faktiskt köpte och det som faktiskt genomfördes, inte för
  det ansökan planerade.
- En engångspost (tillverkning av utrustning, ett enstaka inköp, en enstaka händelse) är en
  egen drivare. Skriv "engångspost" i dess beskrivning.
- Har insatsen fått pengar flera år och köpte ett visst års pengar en avgränsad del, säg
  vilket år som köpte vilken drivare.
- Ingen drivare för pengarnas egna utsläpp (beloppet gånger utsläpp per krona). Köptes
  utrustning, material eller transporter är det den fysiska saken som är drivaren.
- Ledde en pilot till en bestående verksamhet: verksamheten efter piloten är en egen
  drivare, och undanträngning av andra aktörers försäljning är en egen drivare.
""",
    "baslinje": """
I det här steget:
- BAU är "utan just de här pengarna". Lista det som redan pågår och påverkar samma utsläpp
  (klimatkontrakt, fossilfrimål, upphandlingskrav, andra åtgärder, andra års pengar), med
  källa, och låt det gälla i BAU.
- Hade samma sak skett ändå, men senare: ange per scenario (min/medel/max) det år BAU hade
  hunnit ikapp, och varifrån bedömningen kommer. Det är tidigareläggningens slut. Ett
  ikapp-år kräver belägg i underlaget (ett beslut, ett mål, en plan, en annan aktör som
  var på väg). Saknas belägg finns inget ikapp-år; skriv det.
- Nulägesår är året före första bidragsåret.
""",
    "evidens": """
I det här steget:
- Ankra i uppmätta värden när de finns, och skriv för varje antagande om det är uppmätt,
  omräknat ur en mätning eller antaget.
- Ange attribution som ett eget tal per drivare (min/medel/max, 0–1): den andel av
  förändringen som just de här pengarna orsakade. Lägg den inte i ΔA eller ΔEF. Skriv vad
  den bygger på: andra orsaker som drar åt samma håll, deltagarnas egen vilja, annan
  finansiering, det som hade hänt ändå. Går effekten genom andra människors beslut och
  vanor, är andelen pengarnas del bland orsakerna och oftast under 1 (regel 2). Har BAU eller
  tidigareläggningens slutår redan räknat bort det som hade hänt ändå, ska attributionen
  inte räkna bort det en gång till. Innan du lämnar steget: räkna upp varje avdrag för det
  som hade hänt ändå (BAU-trend, ikapp-år, avklingning, attribution) och var det görs.
  Samma skäl får stå på ett ställe.
- Attributionen följer scenariot: för en drivare som minskar utsläppen har min den lägsta
  andelen och max den högsta. Bara en drivare som ökar utsläppen och har en egen andel får
  den högsta andelen i min. En kostnad som följer av samma sak som en nytta (förluster och
  tillverkning av något pengarna bara bidrog till) får samma andel som nyttan i varje
  scenario.
- Ange avklingning som halveringstid i år (min/medel/max) för effekter som klingar av, med
  källa eller som antagande. Köpta saker får i stället sin livslängd som sista år med effekt.
- Utrustning som pengarna köpte: ange alltid utrustningens livslängd i år (min/medel/max)
  med källa. Kalkylen belastar insatsen med de år av livslängden som ryms före ikapp-året,
  när köpet bara tidigarelades, och annars till och med målåret.
- El: 59 g CO2e/kWh i alla tre scenarierna (regel 17).
- Har underlaget en mätning av hur länge effekten höll, härled halveringstiden ur den
  (regel 4) och visa uträkningen.
- Började insatsen mitt i ett år: ange hur stor andel av startåret den verkade.
- Kalkylens max sätter alla antaganden på sitt maxvärde samtidigt. Välj därför maxvärden så
  att kombinationen blir ett rimligt högt utfall, inte varje parameters ytterläge.
- Kontrollera tecknet per drivare innan du lämnar steget: en drivare som ska minska
  utsläppen ska ge lägre utsläpp än BAU i alla tre scenarierna, och ett högre scenario ska
  aldrig ge ett sämre resultat. Undviken nyproduktion: aktiviteten är det nya som undviks,
  och ΔA är negativt (regel 13).
""",
    "kalkyl_extract": """
I det här steget gäller ytterligare fält i JSON-objektet. Använd dem när analysen ger
underlag för dem:
- "followup_year": sista året som räknas som genomfört (profilens Uppföljningsår).
- "grants": [{"year": <år>, "amount": <kr>}, ...]: ett per bidragsår, använt belopp i kronor
  (beviljat om använt saknas). Utelämna vid ett enda bidragsår.
- Per drivare:
  - "attribution": {"min", "med", "max"}: andelen av förändringen som just de här pengarna
    orsakade, 0–1. Den läggs HÄR och inte i delta. Regeln i RÄCKVIDD OCH KEDJOR om att
    attribution ingår i delta gäller inte i uppföljningsläget: delta är förändringen,
    attribution är hur stor del av den pengarna orsakade. Är det som hade hänt ändå redan
    borträknat i BAU eller med ramp.end_year, räkna inte bort det igen i attributionen.
    Ange källan i "kallor"."attribution" på samma sätt som för övriga tal. Attributionen
    följer scenariot: för en drivare som MINSKAR utsläppen har min den LÄGSTA andelen och
    max den högsta. Bara en drivare som ökar utsläppen och har en egen andel får den högsta
    andelen i min; en kostnad som följer av samma sak som en nytta får samma andel som
    nyttan i varje scenario. Kalkylen vänder ett band som står i fel ordning på en drivare
    som minskar utsläppen, och säger det. Det pengarna själva köpte och dess egen
    användning har attribution 1; en effekt som går genom andra människors beslut har
    pengarnas andel bland orsakerna (regel 2).
  - "ramp"."half_life": {"min", "med", "max"} i år, för effekter som klingar av efter året
    för full effekt. min = kortast halveringstid. Utelämna när effekten inte klingar av.
    Källan anges i "kallor"."half_life", och för ramp.end_year i "kallor"."end_year".
  - "ramp"."first_year_share": andelen av startåret som insatsen verkade (start i april =
    0.75). Sätt full_effect_year = start_year när effekten kommer direkt.
  - "ramp"."last_year_share": {"min", "med", "max"}, andelen av slutåret (ramp.end_year)
    som insatsen fortfarande verkade, när effekten slutar mitt i året (nästa kampanj startar
    13 maj = 0.36). Ange den alltid när analysen anger en slutårsandel, annars räknas hela
    slutåret. Gäller inte när slutåret är startåret; då bär first_year_share hela andelen.
  - "kind": "engång" för en engångspost, med "year" = året den inträffade, a0 = mängden och
    ef0 = kg CO2e per enhet. delta_a = 1 när posten ökar utsläppen (tillverkning), -1 när
    den undviker dem. Är mängden eller faktorn osäker: sätt a0 och ef0 till de HÖGSTA
    värdena och låt delta_a bära spannet som andelar av dem, aldrig utanför -1 till 1 (4, 6
    eller 7 undvikta inköp: a0 = 7, delta_a min -0.571, med -0.857, max -1). Utelämna "kind"
    för årliga drivare.
  - "lifetime": {"min", "med", "max"} i år, för varje engångspost som är utrustning som
    pengarna köpte. "end_year": {"min", "med", "max"} när insatsen bara tidigarelade köpet:
    samma ikapp-år som nyttans ramp.end_year. Kalkylen belastar insatsen med (end_year + 1 −
    year) / lifetime av posten, högst hela, och använder målåret när end_year saknas eller
    ligger senare. Utelämnas end_year tar kalkylen först det senaste slutåret bland
    drivarna som minskar utsläppen. Källan i "kallor"."lifetime".
  - En engångspost för tillverkning, inköp eller transport har delta_a > 0 och delta_ef = 0:
    a0 och ef0 är den köpta mängden och dess egen faktor. Skriv aldrig delta_ef < 0 på en
    sådan post. Kalkylen räknar annars om den till den tillkomna mängden och säger det.
  - "grant_year": bidragsåret vars pengar köpte just den här drivaren. Utelämna när
    drivaren betalades av alla år tillsammans.
- Köpta saker: a0 är de köpta sakernas användning, inte ett årligt inköp. Är livslängden
  kortare än målåret, sätt ramp.end_year till sista året de används.
- En begränsad mängd: köpte pengarna en viss volym (ett års merkostnad för bränsle, en
  kampanjperiod), sätt ramp.end_year till sista året volymen räcker. Säger analysen att
  effekten bara gäller ett år, är end_year det året i alla tre scenarierna. Utan end_year
  räknar kalkylen effekten varje år till målåret.
- a0 är aldrig en summa över flera år. En total för perioden (all yta som byggs med kraven
  till 2030, alla projekt under perioden) delas med antalet år den fördelas på, och rampen
  börjar det första av dem. Annars räknar kalkylen hela totalen en gång per år.
- Undviken nyproduktion (återbruk, begagnat, reparation, lån): a0 är den mängd nytt som
  hade köpts eller tillverkats, ef0 utsläppen per enhet nytt, och delta_a är negativt, med
  nettoandelen (den del som faktiskt ersätter nytt) som storlek. Skriv aldrig nettoandelen
  som delta_ef på hela mängden, och höj aldrig a0 med den återbrukade mängden.
- En drivare som ökar utsläppen har min och max i omvänd ordning mot nyttan: störst
  mängd, högst faktor, senast end_year och längst lifetime i min; minst och kortast i max.
  Växer kostnaden med nyttan (ersättningsbränsle, laddel), följer dess mängd och
  attribution nyttans ordning; bara faktorn står i omvänd ordning.
- Ingen drivare med a0 i kronor för pengarnas egna utsläpp. Kalkylen tar en sådan post ur
  resultatet och visar den på egen rad med högst 0,012 kg CO2e per krona.
- a0 i samma enhet som ef0 gäller per: 210 ton med en faktor per kg är a0 = 210000 och
  a0_unit "kg". Kalkylen räknar om ton mot kg och MWh mot kWh, men skriv rätt från början.
""",
    "kalkyl": """
I det här steget: redovisa netto per år, och skilj det realiserade (till och med
uppföljningsåret) från det som återstår. Räkna attribution, avklingning och delår så som
evidenssteget anger dem.
""",
    "qa": """
I det här steget, granska särskilt:
- Att BAU är "utan just de här pengarna" och att det som redan pågår ingår i BAU.
- Att det som hade hänt ändå räknas bort exakt en gång: inte i flera av BAU, ikapp-år,
  avklingning och attribution, och inte någonstans alls. Att ett underlag som säger att
  samma sak hade kommit senare ger ett ikapp-år. Att varje attribution har ett skäl: 1 för
  det pengarna själva köpte och dess användning, och för effekter som går genom andra
  människors beslut en andel bland orsakerna, där ett värde nära 1 är lika väl motiverat
  som ett lågt.
- Att nyttan bara gäller det pengarna betalade, inte det som gjordes med förvaltningens
  egen tid eller andra medel.
- Att användningen av ett verktyg, en databas eller en vägledning som ingen redovisat
  användning av har en omfattning ur underlaget eller en angiven källa, inte en fri
  uppskattning, och att den är noll i det försiktiga scenariot.
- Att effekter varken varar för länge eller för kort: avklingning för mjuka åtgärder,
  ingen avklingning för krav, beslut och köpta saker, livslängd för köpta saker, slutår
  för tidigareläggning, och en halveringstid som stämmer med en uppmätt varaktighet.
- Att ingen kostnad har blivit en nytta, att köpt utrustning har en livslängd, och att
  el räknas med 59 g CO2e/kWh.
- Att följdeffekter som underlaget visar har inträffat finns med, med en antagen andel.
- Att pengarna bara får nyttan av det de köpte, till exempel inte ett återkommande inköp av
  något som köptes en gång.
- Att insatsens egna utsläpp och nyttan behandlas lika: samma avdrag för det som hade hänt
  ändå, och för utrustning vars köp bara tidigarelades bara de tidigarelagda åren av
  livslängden. Pengarnas egna utsläpp (belopp gånger utsläpp per krona) ingår inte.
- Att en verksamhet som piloten gav upphov till räknas efter piloten om den inte hade
  funnits utan insatsen, att ett ikapp-år för den har belägg, och att undanträngning är en
  egen andel med motivering och inte gömd i attributionen.
- Att uppmätta värden används som ankare där de finns, och att resten är märkt som antaget.
- Kalkylens avsnitt "Bärande antaganden": varje rad som börjar med "OBS: bärande antagande
  utan källa" ska antingen få en källa eller redovisas öppet som antagande i rapporten. Ta
  ställning till om max-scenariot är ett rimligt högt utfall eller bara alla ytterlägen.
""",
    "rapport": """
I det här steget gäller följande ändringar av strukturen:
- Direkt under rubrikraden: en rad "Analysläge: uppföljning av genomförd insats", med
  bidragsåren.
- I "Beräknad klimatnytta" är huvudtalet klimatnyttan till och med målåret, inte per år.
  Första raden under "Huvudresultat (Scenario Medel):" är "  Till och med <målår>
  (Netto/Total): <kalkylens kumulativa netto i medel> ton CO2e (försiktigt <min> till högt
  <max>)", med talen ur kalkylen. Den korta tolkningen börjar med samma tal. Medel per år är
  ett andra mått: behåll raderna "Medel effekt/år" exakt som de står, efter den raden. Lägg till
  "Realiserat" och "Återstår" ur kalkylens avsnitt Uppföljning, och fördelningen per
  bidragsår när kalkylen har en. Kalla max-scenariot "högt", inte "full potential" eller
  "rimligt högt": kalkylens max sätter varje antagande på sitt höga värde samtidigt.
- Lägg till ett avsnitt "**Uppmätt och antaget**" efter "Beräknad klimatnytta": en lista med
  det som bygger på mätningar och en med det som är antaget, där kalkylens bärande
  antaganden står först.
- Avsluta "Rekommendation och nästa steg" med "Vad som behöver mätas:", en punktlista med
  konkreta mätningar som skulle göra de bärande antagandena till mätta värden.
- Är resultatet nära noll eller inte mätbart än, säg det rakt ut i den korta tolkningen.
  Det är ett giltigt utfall, inte ett misslyckande.
- Har kalkylen en rad "Pengarnas egna utsläpp": nämn den på egen rad under "Beräknad
  klimatnytta" och säg att den inte ingår i resultatet.
""",
}
# The evidens split sends the same judgment as evidens, one driver at a time,
# and merges what the parts set.
STEG["evidens_part"] = STEG["evidens"]
STEG["evidens_merge"] = STEG["evidens"]


def block(step: str) -> str:
    """The follow-up block for one step."""
    return KARNA + STEG.get(step, "") + SLUT


def for_mode(system: str, step: str, mode: str) -> str:
    """The step's system prompt for this mode: unchanged for potential, with
    the follow-up block appended for uppföljning."""
    if mode != UPPFOLJNING:
        return system
    return f"{system}\n\n{block(step)}"
