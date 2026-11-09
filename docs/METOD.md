# Metod: så räknar CAIA

För dig som ska granska eller använda resultat från CAIA (Climate Action Impact Analysis) utan att läsa kod. Dokumentet beskriver vad som räknas, vilka formler som används, vad språkmodellen gör och vad programkoden gör, och var metoden är svag. Varje påstående om hur något räknas är kontrollerat mot koden i oktober 2026 (`next/src/caia/calc/`, `kallmarkering.py`, `agents/uppfoljning.py`).

**Under avstämning.** Hur de tre scenarierna sätts och hur attributionen hanteras är inte avstämt med dem som ska använda talen i uppföljningen. Avsnitten *Tre scenarier* och *Attribution* beskriver hur CAIA gör i dag. De kan komma att ändras, och då ändras det här dokumentet samtidigt.

## Vad CAIA räknar

CAIA räknar hur mycket en åtgärd ändrar utsläppen av växthusgaser jämfört med om åtgärden inte hade genomförts. Jämförelsen kallas BAU, business as usual. Svaret anges i ton CO2e per år, och ett positivt tal betyder minskade utsläpp.

Varje åtgärd delas upp i en eller flera drivare. En drivare är en aktivitet som ger utsläpp, till exempel körda kilometer med tjänstebil eller kilowattimmar el. För varje drivare behövs två tal: hur stor aktiviteten är per år, och hur stora utsläppen är per enhet av aktiviteten (emissionsfaktorn).

Resultatet redovisas på tre sätt:

- **Territoriellt:** den del av förändringen som sker inom kommunens gränser.
- **Konsumtionsbaserat:** den del som hör till invånarnas och verksamheternas konsumtion, oavsett var i världen utsläppen sker.
- **Netto:** de två tillsammans, med den del som finns i båda räknad en gång.

Allt räknas i tre scenarier, min, medel och max, så att osäkerheten syns som ett spann runt medelvärdet.

## Vad CAIA inte räknar

- **Inget är uppmätt av CAIA.** Alla tal är beräkningar ur antaganden. Det gäller också "realiserat" i en uppföljning, om inte analysen själv bygger på ett uppmätt tal.
- **En åtgärd i taget, utom i portföljen.** Varje analys räknar en åtgärd på dess egen baslinje. Att lägga ihop flera åtgärder görs i portföljen (se *Portföljen* nedan), och den räknar bort överlapp bara inom de utsläppspotter som finns i kommunens register. Inom en analys pekar kvalitetsgranskningen (steg 6) ut risken för dubbelräkning i ord, men ingen siffra justeras.
- **Åtgärdens egna utsläpp ingår bara om de finns som en drivare.** Tillverkning av det som köps in, eller ökad användning någon annanstans, räknas när analysen har en drivare för det. Annars saknas det.
- **Kostnader och kostnadseffektivitet räknas inte.** Rapporten kan nämna kostnader som står i underlaget, men kalkylen innehåller inga kronor utom bidragsbeloppen som fördelar nyttan per år i en uppföljning.
- **Andra effekter än växthusgaser**, som luftkvalitet, buller eller biologisk mångfald, ingår inte.
- **Inget efter målåret i det ackumulerade talet.** Den ackumulerade effekten räknas till och med målåret (2030 om inget annat anges). En åtgärd som fortsätter verka därefter får alltså ett lägre ackumulerat tal än sin verkliga livslängd skulle ge. Rubriktalet i potentialläget är målåret självt, se *Rubriktalet och åren det gäller*.

## De sju stegen

En analys går genom sju steg. Språkmodellen (Claude, två modeller: Opus 5.5 och Sonnet 5.5) läser, bedömer och skriver. Programkoden räknar, kontrollerar och skriver ut räkningen.

| Steg | Språkmodellen | Programkoden |
|---|---|---|
| 1 Åtgärdsprofil | Tolkar beskrivningen, ställer högst fyra följdfrågor och skriver en profil: omfattning i tal, sektor, målgrupp, rådighet, typ av åtgärd, mognad, tidsram. Saknas omfattningen frågar CAIA efter den först, och profilen blir inte färdig förrän användaren svarat. Kan användaren inte svara antar CAIA ett tal och skriver hur det togs fram; det märks som antaget i profilen, i baslinjen, under *Talens ursprung* och i rapporten. Det som modellen själv antagit i övrigt märks också som antagande. | Läser profilen till de fält som sidan visar. |
| 2 Utsläppskällor | Namnger drivarna, alltså de utsläpp åtgärden påverkar, och för varje drivare mekanismen (undvika, byta eller förbättra) och om det är mängden eller utsläppen per enhet som ändras. Avgör typ av effekt, som bestämmer räknesättet: en direkt åtgärd räknas rakt på drivaren, en indirekt eller möjliggörande som en kedja (hur många nås, hur många ändrar sig, hur mycket, och åtgärdens andel utöver det som hade hänt ändå), och en stödjande åtgärd får inget eget tal. Sätter inga tal. Drivarna delas efter en fast regel: en aktivitet är en drivare även när den räknas både territoriellt och konsumtionsbaserat, kategorier delas bara när profilen ger mängd per kategori, och varje livscykelsteg som åtgärden ändrar är en egen drivare. Steget hette EMAP till oktober 2026, och heter så i koden. | |
| 3 Baslinje | Sätter nuläget per drivare (aktivitet och emissionsfaktor) och trenden utan åtgärd, ur parameterbiblioteket och kommunens data. | Lägger parameterbiblioteket och datafilerna i modellens underlag. |
| 4 Evidens | Bedömer hur mycket åtgärden ändrar varje drivare, som försiktigt, troligt och optimistiskt värde med källa. Sätter klimatfaktorerna. För en indirekt eller möjliggörande åtgärd skriver steget först attributet (den mätbara egenskap i kommunen som åtgärden ändrar, som avstånd till närmaste laddpunkt), vilken uppfattning det påverkar och vilket led i kedjan som är osäkrast, som i DIN SPEC 91637; texten räknas inte. Arbetar en drivare i taget och fogar sedan ihop dem, med uppgift att hitta dubbelräkning mellan drivarna. | Delar upp arbetet per drivare och kontrollerar att varje del har rätt form. |
| 5 Kalkyl | Läser ut talen ur steg 1 till 4 och skriver dem i ett formulär. Räknar inte. | Kontrollerar formuläret, räknar alla år och scenarier, skriver tabellerna, varningarna, den tekniska bilagan och avsnittet *Talens ursprung*. |
| 6 Kvalitetsgranskning | Granskar källor, enheter, storleksordning, BAU-hantering och dubbelräkning. Ger status ok eller varning. Ändrar inga tal. | |
| 7 Rapport | Skriver beslutsunderlaget i löptext, och avslutar potentialrapporten med *Följ upp med*: en eller två indikatorer per bärande drivare i begriplig enhet, som DIN SPEC 91637 avsnitt 5.5 begär. | Lägger kalkylmotorns tekniska bilaga sist, oförändrad, och tar bort en bilaga som modellen ändå skrivit. Sidan lägger sedan till *Talens ursprung* ur steg 5, och batchverktyget (`next/tools/run_batch.py`) gör detsamma. |

Det betyder att antagandena är språkmodellens bedömning, och att räkningen från antaganden till resultat är vanlig programkod som ger samma svar varje gång för samma indata. Sidan stannar efter steg 1, 2, 3 och 4 så att användaren kan godkänna eller rätta. Steg 5 till 7 körs sedan i en följd.

## Beräkningen

Formlerna nedan gäller en drivare, ett år och ett scenario. Summan över drivarna är åtgärdens effekt det året.

### Utan åtgärden (BAU)

```
år_sedan_basår = året − basåret
aktivitet_BAU  = aktivitet_basår × (1 + trend_aktivitet) ^ år_sedan_basår
faktor_BAU     = faktor_basår × (1 + trend_faktor) ^ år_sedan_basår
utsläpp_BAU    = aktivitet_BAU × faktor_BAU          (kg, delas med 1 000 till ton)
```

Trenderna är årliga förändringar, till exempel −0,02 för två procent lägre emissionsfaktor per år. Varje trend är en konstant takt från basåret: väntas utvecklingen gå i faser räknar baslinjen om dem till den takt som ger samma nivå vid målåret, och åren däremellan följer då en jämn kurva. BAU räknas med medelvärdet av trenden och är densamma i alla tre scenarier. Scenarierna skiljer sig alltså bara i vad åtgärden gör, inte i hur världen utvecklas utan den.

### Med åtgärden

```
ändring_aktivitet = ΔA × infasning
ändring_faktor    = ΔEF × infasning
utsläpp_åtgärd    = aktivitet_BAU × (1 + ändring_aktivitet) × faktor_BAU × (1 + ändring_faktor)
```

ΔA och ΔEF är åtgärdens effekt vid full verkan, som andel. −0,10 betyder tio procent mindre. En åtgärd kan ändra aktiviteten (färre kilometer), emissionsfaktorn (renare kilometer) eller båda.

### Infasning

Infasningen är ett tal mellan 0 och 1 som säger hur stor del av full verkan åtgärden har ett visst år.

- Före startåret är den 0.
- Mellan startåret och året för full effekt växer den från 0 till 1 enligt en av tre profiler: linjär (jämn ökning), s-formad (långsam start, snabb mitt, långsam avslutning) eller stegvis (0 fram till halva tiden, sedan 1).
- Från året för full effekt är den 1.
- Har åtgärden ett slutår är den 0 efter det året.

När full effekt kommer senare än startåret är effekten noll själva startåret, i alla tre profilerna. En åtgärd med linjär infasning som börjar 2026 och når full effekt 2028 räknas med 0, 50 och 100 procent de tre åren.

Två tillägg används främst i uppföljningar:

- **Avklingning.** Har drivaren en halveringstid minskar effekten efter året för full effekt: `infasning = 0,5 ^ (år efter full effekt / halveringstid)`. Med halveringstid två år återstår hälften efter två år och en fjärdedel efter fyra.
- **Andel av startåret.** När åtgärden har full effekt från start men började mitt i året kan startåret räknas med en andel, till exempel 0,5 för ett halvt år.

### Attribution

```
förändring = (utsläpp_BAU − utsläpp_åtgärd) / 1 000 × attribution        (ton, positivt = minskning)
```

Attributionen är ett tal mellan 0 och 1: hur stor del av förändringen som beror på just den här åtgärden och inte hade hänt ändå. Den skalar förändringen, aldrig BAU.

I dag hanteras den olika i de två analyslägena:

- **Förväntad potential:** språkmodellen instrueras att baka in attributionen i ΔA eller ΔEF när talen läses ut. Effekten skrivs som andel som nås × andel som ändrar beteende × minskning per person × attribution. Det egna attributionsfältet ska då stå på 1.
- **Uppföljning:** språkmodellen instrueras att ange attributionen som ett eget tal per scenario och att inte också lägga den i ΔA eller ΔEF. Den syns då som en egen kolumn i bilagans tabeller och som en egen rad i *Talens ursprung*.

Båda är instruktioner till språkmodellen. Koden räknar med den attribution den får, i båda lägena, och kan inte upptäcka om det som hade hänt ändå har räknats bort två gånger eller inte alls. Det är en sak att titta efter vid granskning: läs ΔA, ΔEF och attributionen tillsammans.

En sak rättar koden själv (sedan 2026-10-22): attributionen ska följa scenariot. För en drivare som minskar utsläppen har min den lägsta andelen och max den högsta. Står bandet tvärtom, och drivaren minskar utsläppen i alla tre scenarierna, vänder kalkylen det och skriver det i en OBS-rad. Värdena är desamma, bara vilket scenario som får vilket ändras. Klimatkraven i anläggning hade i körning 1 "15 % (30 till 5)" på drivmedel och transporter. En drivare som ökar utsläppen lämnas som den står: den kan ha en egen andel som är högst i min (det försiktiga scenariot), eller samma andel som nyttan den följer av. Det senare gäller batterilagret, där pengarna betalade konsultstöd och inte batteriet: tillverkningen och förlusterna ska ha samma andel som nyttan. Det är en instruktion, inte en kontroll. En drivare som ökar utsläppen i ett scenario och minskar dem i ett annat lämnas också; det är nästan alltid en kostnad som ΔEF krympt till en minskning, och åt vilket håll bandet ska gå går inte att läsa ut.

Det här är en av de två delar som är under avstämning.

### Tre scenarier

Min är det försiktiga scenariot, medel det troliga och max det optimistiska men rimliga. Fem tal kan skilja mellan scenarierna: ΔA, ΔEF, attributionen, slutåret och halveringstiden. Allt annat är gemensamt: aktivitet och emissionsfaktor basåret, trenderna, klimatfaktorerna, startår och år för full effekt.

Varje scenario räknas för sig med sina egna värden på alla fem. Max är därför fallet där varje osäkert tal samtidigt hamnar i sitt högsta läge, och min där alla hamnar i sitt lägsta. Spannet mellan min och max är inget statistiskt konfidensintervall. När max är större än vad det enskilt viktigaste antagandet kan ge ensamt skriver kalkylen ut det, med rådet att läsa max som ett ytterfall och inte som ett troligt utfall.

Aktiviteten basåret är gemensam för de tre scenarierna, och ingen effekt kan vara större än −100 procent av den. Ibland säger antagandena mer än så. I ett prövat fall anger baslinjen 21,6 ton nya varor som ersätts, medan scenarierna ersätter 6, 21,6 och 60 ton, med 8, 10 och 14 kg CO2e per kilo. I potentialläget sätts aktiviteten då till scenariernas största mängd, 60 ton, och emissionsfaktorn till sitt högsta värde, 14. Varje scenario blir sin andel av produkten: 48, 216 och 840 ton CO2e är −5,7, −25,7 och −100 procent av 840. Minskningen i ton blir den antagandena anger. Nivån utan åtgärden för den drivaren blir däremot den största mängden och inte baslinjens tal, och utläsningens anteckning säger det. Före 2026-10-13 saknades regeln. Av fyra utläsningar av fallet vägrades två av formuläret (se *När kalkylmotorn inte kan läsa talen*), en svarade inte med ett formulär, och en skalade om scenarierna så att det optimistiska blev −100 procent av 21,6 ton, och det troliga resultatet blev då 108 ton i stället för 216. Med regeln gav fyra utläsningar av fyra 216 ton, med spannet 48 till 840.

Det här är den andra delen som är under avstämning.

### Territoriellt, konsumtion, överlapp och netto

Varje drivare har tre klimatfaktorer, satta av språkmodellen i steg 4 och visade för användaren före kalkylen:

```
territoriellt = förändring × territoriell faktor
konsumtion    = förändring × konsumtionsfaktor
överlapp      = förändring × överlappsfaktor, men aldrig större än territoriellt eller konsumtion
netto         = territoriellt + konsumtion − överlapp
```

Faktorerna säger hur stor del av drivarens utsläpp som hör till respektive perspektiv. Biltrafik inom kommunen ligger nära 1 på alla tre: utsläppen sker i kommunen, de hör till invånarnas konsumtion, och det är samma utsläpp. Då blir netto lika med förändringen. Inköpta varor som tillverkas på annat håll ligger nära 0 territoriellt och nära 1 i konsumtion, med litet överlapp.

Överlappet finns för att samma ton inte ska räknas två gånger när de två perspektiven läggs ihop. Koden begränsar överlappet till det mindre av territoriellt och konsumtion, så att netto aldrig blir mindre än det större av dem.

Klimatfaktorerna är metodval. De har ingen källmarkering och kontrolleras inte mot parameterbiblioteket.

### Engångsposter

En drivare kan vara en engångspost i stället för en årlig aktivitet, till exempel tillverkningen av cyklar som köptes ett visst år. Den finns då bara sitt eget år, utan trend och utan infasning. Engångsposter används främst i uppföljningar.

**Utrustning vars köp bara tidigarelades** (sedan 2026-10-22). När nyttan har ett ikapp-år, alltså ett år då det som hade hänt ändå har kommit ikapp, köpte pengarna inte utrustningen utan bara att den kom tidigare. Då belastar tillverkningen insatsen bara för de år av livslängden som kom tidigare:

```
andel = (ikapp-år + 1 − köpår) / livslängd, högst 1 och lägst 0
förändring = (utsläpp_BAU − utsläpp_åtgärd) / 1 000 × attribution × andel
```

Det gäller bara en engångspost som ökar utsläppen; ett undvikt köp räknas som förut. Livslängden anges av analysen per scenario. Ikapp-året anger analysen, eller så tar kalkylen det senaste slutåret bland de drivare som minskar utsläppen, per scenario. Har någon av dem inget slutår i ett scenario belastas hela posten i det scenariot, utom i en uppföljning (nästa stycke). Saknas livslängd för en engångspost som ökar utsläppen medan nyttan har ett slutår, skriver kalkylen en OBS-rad. Bakgrunden var energivisualiseringen i storköken: 1,25 ton för skärmar och mätare stod fullt mot en nytta som upphör 2027. Med 8 till 12 års livslängd blir det kumulativa medelresultatet i körning 1 −0,5 ton i stället för −1,1. Andelen syns som en egen kolumn i bilagan, och livslängd och ikapp-år prövas bland de bärande antagandena.

**Utrustning skrivs av till målåret i en uppföljning** (2026-10-22). Nyttan räknas bara till och med målåret, så utrustningen belastar insatsen bara för de år av livslängden som ryms dit: ikapp-året sätts till målåret när det saknas eller ligger senare, och andelen blir (målåret + 1 − köpår) / livslängd. Batterilagret hade belastats med hela batteriet mot en nytta räknad till 2030 (−4,9 ton till 2030). Utan livslängd belastas posten fullt som förut, och utläsningen ber därför alltid om livslängd för köpt utrustning. I potentialläget gäller det inte.

**En kostnad blir aldrig en nytta** (sedan 2026-10-22, i uppföljningsläget). En engångspost är den köpta mängden. Skrevs den som ΔA > 0 med ΔEF < 0 sänktes faktorn på hela posten, och (1 + ΔA)(1 + ΔEF) − 1 kunde bli negativt, så att tillverkningen räknades som en minskning. Återbrukscontainern fick så 3,4 ton "nytta" av sina egna containrar, och energivisualiseringens skärmar samma sak i mindre skala. Kalkylen räknar nu en sådan post som den tillkomna mängden, ΔA × (1 + ΔEF), med postens egen faktor (ΔEF 0), per scenario, och skriver en OBS-rad. Ett attributionsband som kalkylen vänt för en nytta går då tillbaka som det skrevs.

**Pengarnas egna utsläpp** (sedan 2026-10-22, bara i uppföljningsläget). En drivare vars aktivitet räknas i kronor och som ökar utsläppen i något scenario, alltså bidragsbeloppet gånger utsläpp per krona, ingår inte i resultatet. Pengarna hade använts av kommunen ändå. Den står i stället på en egen rad, "Pengarnas egna utsläpp", med högst 0,012 kg CO2e per krona, en tjänstetung faktor. Gav analysen en högre faktor står den i raden. Postens år räknas fortfarande till insatsens år, så medelfönstret flyttas inte. I driftsmedlens två körningar fanns sådana poster i sju analyser, olika i de två körningarna (krisberedskapen: 204 935 kr × 0,04 = −4,1 ton). Det som köptes och är fysiskt (utrustning, material, transporter) ska vara egna drivare i fysiska enheter. I potentialläget är posten en vanlig drivare som förut. Vändningen av attributionen, omräkningen mellan ton och kg och livslängdsandelen gäller däremot i båda lägena: de slår bara till när talen de behöver finns, och potentiallägets utläsning ber inte om livslängd eller attribution.

### Rubriktalet och åren det gäller

I potentialläget är rubriktalet **netto i medelscenariot under målåret**, 2030 om inget annat anges. I uppföljningsläget är det **netto i medelscenariot, som medelvärde per år** över insatsens egna år. Bredvid står samma tal territoriellt och konsumtionsbaserat. Beslutet att låta målåret vara rubriktal i potentialläget togs 2026-10-13 (se DECISIONS.md); före det var rubriktalet medel per år 2026 till 2030 även där. Sparade analyser bär med sig vilket år talet gäller, och en sparad analys utan år är ett medelvärde.

| | Förväntad potential | Uppföljning |
|---|---|---|
| Rubriktalet | målåret | medel per år |
| Spannet (låg och hög) | målåret i min och max | medel per år i min och max |
| Medel per år gäller åren (mindre rad) | 2026 till 2030, alltid | från åtgärdens första startår till målåret |
| Ackumulerat | summan från första startåret till målåret, medelscenariot | samma |

Medel per år står kvar under rubriktalet. I potentialläget delas summan för 2026 till 2030 alltid med fem, oavsett målår. Tre följder är värda att känna till:

- En åtgärd som startar sent i fönstret, till exempel 2029, får ett lågt medelvärde: två år med effekt delas på fem. Har åtgärden effekt färre än hälften av åren, alltså två eller ett av de fem, skriver kalkylen en varning med vilka år det gäller.
- En åtgärd som verkar först efter 2030 får noll i medel per år. Är målåret satt senare än 2030 syns effekten i rubriktalet och i det ackumulerade talet. Är målåret 2030 blir också det ackumulerade talet noll. Då säger varningen vilket år effekten börjar och att nollan beror på åren som räknas.
- Är målåret tidigare än 2030 slutar det ackumulerade talet vid målåret, medan medel per år fortfarande räknar med åren fram till 2030.

Varningarna ändrar inga tal. Medel per år för en åtgärd som startar 2029 är lika lågt som förut. Skillnaden är att kalkylen säger varför.

Fönstret är ett metodval som följer planperioden.

Rubriktalet avrundas till en decimal. Alla summor räknas på oavrundade tal. Olika delar av utskriften avrundar olika: den tekniska bilagan visar en decimal, medan kalkyltexten och sidan visar tal från tio och uppåt som hela ton.

### Ett räkneexempel

Talen är påhittade och räknade med CAIA:s kalkylmotor. En åtgärd ska minska tjänsteresor med bil.

- Aktivitet basåret 2024: 1 000 000 km per år. Ingen trend.
- Emissionsfaktor: 0,15 kg CO2e per km, som sjunker 2 procent per år utan åtgärd.
- Åtgärdens effekt på körsträckan: −5 procent (min), −10 procent (medel), −20 procent (max).
- Start 2026, full effekt 2028, linjär infasning.
- Klimatfaktorer 1, 1 och 1.

År 2029 i medelscenariot: emissionsfaktorn har sjunkit till 0,15 × 0,98⁵ = 0,1356 kg per km. Utan åtgärden blir utsläppen 135,6 ton. Med åtgärden körs 900 000 km, vilket ger 122,0 ton. Förändringen är 13,6 ton. Territoriellt 13,6, konsumtion 13,6, överlapp 13,6, netto 13,6.

| År | Infasning | Netto, medel (ton) |
|---|---|---|
| 2026 | 0 % | 0 |
| 2027 | 50 % | 7,1 |
| 2028 | 100 % | 13,8 |
| 2029 | 100 % | 13,6 |
| 2030 | 100 % | 13,3 |

Rubriktalet är målåret 2030: 13,3 ton CO2e, med spannet 6,6 (min) till 26,6 (max) samma år. Summan är 47,7 ton ackumulerat till 2030, och medel per år 2026 till 2030 blir 47,7 / 5 = 9,5 ton. Effekten sjunker något efter 2028 eftersom bilarna ändå blir renare för varje år: det åtgärden tar bort är värt mindre ju lägre emissionsfaktorn är.

### Bärande antaganden

Efter räkningen prövar koden varje osäkert tal för sig, i båda analyslägena. Talet flyttas från sitt min till sitt max medan allt annat står på medel, och koden mäter hur mycket det ackumulerade resultatet rör sig. De fem antaganden som flyttar resultatet mest skrivs ut i kalkylen, med ursprung.

Två saker flaggas med "OBS: bärande antagande utan källa":

- ett antagande som ensamt flyttar resultatet med minst en fjärdedel av drivarnas sammanlagda effekt, och som saknar källa eller är märkt som antagande,
- aktiviteten eller emissionsfaktorn hos en drivare som står för minst hälften av effekten, om talet saknar källa eller är märkt som antagande.

Flaggan utgår från det ursprung språkmodellen angav, inte från utfallet av källkontrollen. Ett bärande tal som påstås komma ur biblioteket men som föll i kontrollen står under *Kontrollera först* utan att få den här flaggan. Läs därför de två tillsammans.

Prövningen ändrar inga tal. Den pekar ut vilka antaganden resultatet står och faller med, så att granskningen kan börja där.

### Varningar från kalkylen

Koden skriver en varning bredvid resultatet när:

- enheterna för en drivares aktivitet och utsläppsfaktor inte går ihop (se *Enhetskontrollen* nedan). Den varningen står först, eftersom ett enhetsfel gör alla andra tal fel också,
- ingen drivare har någon effekt i medelscenariot,
- medelscenariot ger ökade utsläpp (målåret, medel per år eller ackumulerat är negativt),
- medel per år är noll trots att det ackumulerade talet inte är det, eftersom effekten ligger efter 2030 och målåret är senare (bara potentialläget),
- både medel per år och det ackumulerade talet är noll, eftersom åtgärden har effekt först efter målåret (i potentialläget dessutom utanför 2026 till 2030). Varningen anger första året med effekt. Ger startår, år för full effekt och slutår tillsammans ingen effekt något år säger varningen det i stället,
- åtgärden har effekt färre än hälften av åren 2026 till 2030, så att medel per år till största delen är ett medel av nollor (bara potentialläget),
- min och max ger samma ackumulerade tal, eller scenarierna ligger i fel ordning. Vid fel ordning namnger varningen de antaganden som drar åt fel håll: de som ger ett lägre ackumulerat tal vid sitt maxvärde än vid sitt minvärde när de prövas ett i taget med övriga på medel (samma prövning som under *Bärande antaganden*). Vanliga orsaker är att drivarens aktivitet är något som minskar utsläppen, till exempel en återbrukad mängd, och höjs med ΔA, vilket kalkylen läser som mer utsläpp, eller att en drivare som ökar utsläppen har värden i nyttans ordning, till exempel längst effekt i max,
- en engångspost ligger efter målåret, en andel av startåret är angiven men aldrig används, eller ett bidragsår saknas bland bidragsraderna.

Ett år räknas som ett år med effekt när åtgärden ändrar aktiviteten eller emissionsfaktorn det året i medelscenariot, också under infasningen. Startåret i en infasning är noll och räknas inte.

En varning ändrar inga tal. Den säger att talet inte ska användas förrän orsaken är förstådd.

### Enhetskontrollen

Kalkylen multiplicerar aktiviteten (A0) med utsläppsfaktorn (EF0) och läser produkten som kg CO2e. Det stämmer bara när utsläppsfaktorn är i kg CO2e per samma enhet som aktiviteten räknas i. En körning i oktober 2026 hade aktiviteten i ton och utsläppsfaktorn per kg, och visade 0,1 ton CO2e per år där 86 var rätt. Ingen av de andra kontrollerna jämför de två enheterna med varandra.

Koden läser därför första ordet i aktivitetens enhet (före "/år" eller "per") och första ordet efter snedstrecket eller "per" i utsläppsfaktorns enhet, och varnar när:

- båda är vikt eller båda energi men i olika storlek, till exempel ton mot kg eller MWh mot kWh. Sedan 2026-10-22 räknar kalkylen då om aktiviteten till utsläppsfaktorns enhet (210 ton blir 210 000 kg) och skriver i varningen att den gjort det, och hur stort felet blir om enheten var fel angiven men talet redan omräknat. Förut varnade den bara, och resultatet stod kvar: krisberedskapen i driftsmedlens körning 2 räknade 210 ton gånger 2,1 kg CO2e per kg som 0,44 ton i stället för 441, trots varningen. Båda gångerna felet setts var enheterna rätt och omräkningen glömd,
- den ena är vikt och den andra energi,
- den ena är vikt eller energi och den andra något annat, till exempel aktiviteten räknad i handlare och utsläppsfaktorn per kg,
- utsläppsfaktorn är angiven i ton eller gram CO2e i stället för kg.

Koden känner bara till g, kg, t, ton, Wh, kWh, MWh och GWh, samma tabell som källkontrollen under *Talens ursprung* använder, och samma ord utskrivna (kilogram, tonne, kilowattimme och liknande). Ett tillägg efter bindestreck räknas inte (kWh-el läses som kWh), och ton-km i alla stavningar (ton km, t·km, tkm) läses som ett eget ord, aldrig som ton. Är det första ordet på ena sidan inget av de kända orden, till exempel "el (kWh/år)" eller "Antal ton/år", letar koden efter ett känt ord längre fram på samma sida innan den varnar.

Två andra ord jämförs aldrig med varandra: personer mot invånare, km mot fordonskm och cyklar mot cykel kan betyda samma sak, och en gissning där skulle varna på riktiga analyser. Ordet "enhet", som står när analysen inte angett någon enhet, jämförs inte heller. Kontrollen missar alltså till exempel km mot mil (en faktor 10), handlare mot hushåll och GJ mot MJ.

Prövat 2026-10-13 mot de sparade riktiga analyserna på disk (referenspaketen, uppföljningen av driftsmedlen och provkörningar, 72 drivare i omkring 20 analyser): ingen drivare fick varningen. I 20 av drivarna var minst en av enheterna vikt eller energi, så att kontrollen faktiskt jämförde något; resten räknas i km, liter, kronor, fordon och liknande. Båda de felaktiga utläsningarna från oktober fick varningen.

Kontrollen säger inte om ett tal som påstås vara en andel egentligen är något annat. I oktoberkörningen lästes 0,72 ton per handlare som en minskning på 72 procent. Där syns felet bara för att aktiviteten räknades i handlare och utsläppsfaktorn per kg. Hade båda varit per handlare hade kontrollen inte märkt något.

## Talens ursprung och "Kontrollera först"

Varje rapport, från webbsidan och från batchverktyget, slutar med avsnittet *Talens ursprung*: en tabell med en rad per indatatal och var talet kommer ifrån. Sex tal per drivare redovisas: aktivitet och emissionsfaktor basåret, de två trenderna och de två effekterna. Attributionen redovisas också när den skiljer sig från 1 i något scenario.

Språkmodellen anger ett ursprung för varje tal när den fyller i formuläret i steg 5. Koden kontrollerar sedan påståendet:

| Ursprung | Vad koden kontrollerar | Vad koden inte kontrollerar |
|---|---|---|
| Parameterbiblioteket | Att varje angiven parameter finns i biblioteket. Pekar talet på en enda parameter med ett fast värde jämförs talet med bibliotekets, med fem procents marginal och efter ett enhetsbyte om enheterna kräver det (till exempel gram till kilo). | Pekar parametern på en datafil jämförs inget värde. Bygger talet på flera parametrar krävs att en uträkning är utskriven, men uträkningen räknas inte efter. |
| Kommunens data | Att hänvisningen går till en biblioteksrad med ett lokalt värde, eller till en datafil som finns och som CAIA läser. En rad som bara har en nationell schablon godtas inte. Pekar talet på en enda rad med ett lokalt värde jämförs talet med det. | Pekar hänvisningen på en datafil slås talet inte upp i filen. |
| Extern källa | Att en källa är namngiven. | Koden läser inte källan och kan inte avgöra om talet står där. |
| Antagande | Ingenting. Talet redovisas som antagande. | |

Tre saker om själva jämförelsen:

- Bara medelvärdet jämförs. Min och max kan ligga var som helst utan att kontrollen märker det.
- Tecknet räknas inte. En effekt på −53 procent passerar mot ett biblioteksvärde på 53.
- Har biblioteksraden ett intervall godtas varje tal inom intervallet, med fem procents marginal i ändarna.

Ett tal som saknar ursprung, eller vars påstående inte höll i kontrollen, hamnar under rubriken **Kontrollera först** överst i avsnittet, med skälet utskrivet. I tabellen står då "Kontrollera" eller "Saknas" i kolumnen för ursprung.

"Kontrollera först" betyder att CAIA inte har kunnat belägga talet där det sades komma ifrån. Talet kan vara rätt ändå, men en människa behöver slå upp det innan resultatet används.

Ett tal som passerat kontrollen är inte därmed belagt. Kontrollen fångar hänvisningar till parametrar och filer som inte finns, schabloner som kallas lokala data, och enstaka biblioteksvärden som inte stämmer. Den fångar inte ett felaktigt tal som hänvisar till en datafil, en felräknad härledning eller ett tal som inte står i den externa källan. Tabellen skriver ut när ett värde inte har jämförts ("Värdet slås upp eller räknas fram och jämförs inte här"). I Karlstads bibliotek gäller det 17 av 103 parametrar. Om ett belagt tal är rätt tal för just den här åtgärden prövar kontrollen aldrig.

En trend eller effekt som är exakt noll, utan att analysen sagt något om den, redovisas som antagande med texten att ingen förändring är angiven.

Kolumnen Underlag visar för varje parameter talet som används och dess enhet. För en parameter som hämtar sitt värde ur en datafil står samma sak som i sidans parameterlista: talet i filen och en rad om vad som lästes ur vilken fil, till exempel "224 951 ton CO2e/år. Totala utsläpp, 2023. Datafil: Totala utsläpp per sektor och år (SMHI/RUS)". Pekar parameterns uttryck inte på en enda ruta i filen (en fördelning ur en enkät, en jämförelse mellan två kategorier) står "Läses ur datafilen vid varje analys" i stället för ett tal. Koden gissar aldrig ett tal där. En hänvisning direkt till en datafil visar filens beskrivning ur dataregistret. Bibliotekets uttryck (`LOOKUP(...)`) och registrets namn (`DATA_...`) skrivs inte ut för en hänvisning som håller. Håller den inte, till exempel en datafil som inte finns, står hänvisningen som analysen skrev den i skälet under Kontrollera först, så att den går att slå upp. Uttrycket tolkas på ett enda ställe i koden, samma som parameterlistan använder, och det som jämförs och det som språkmodellen läser är fortfarande själva uttrycket. Visningen ändrar alltså ingen kontroll. Talet i Underlag är bibliotekets värde, inte talet analysen räknade med; det senare står i kolumnen Värde.

### Jämförelsen med det som godkändes

Användaren godkänner baslinjen i steg 3 och antagandena i steg 4 som text. I steg 5 läser språkmodellen ut talen ur texten igen. Koden jämför sedan de utlästa talen med de godkända stegen, och ett tal som avviker tydligt hamnar under **Kontrollera först** med skälet utskrivet, oavsett vilket ursprung det har angetts ha. Avsnittet säger i en mening vad som jämfördes: baslinjen och antagandena, bara antagandena (när samtalet saknar en godkänd baslinje), eller ingenting (när det saknar ett godkänt evidenssteg). Sidan visar dessutom en varning vid den stora siffran när något tal avviker. Jämförelsen ändrar inga tal och stoppar inte kalkylen.

Godkänt betyder det senaste svaret i steget som användaren gick vidare från med grindens knapp. Ett svar som användaren i stället bad om ändringar i räknas inte. Varje drivare i formuläret paras ihop med en godkänd drivare på namnet. Går namnet inte att para ihop med en enda drivare jämförs talen med alla godkända drivare, vilket kan missa en avvikelse men aldrig hittar på en.

| Tal | Jämförs med | Markeras när |
|---|---|---|
| Aktivitet och emissionsfaktor basåret | Raden A0 eller EF0 för drivaren i den godkända baslinjen | Talet varken står i drivarens godkända text eller ligger inom en faktor 1,5 från baslinjens värde (efter ett enhetssteg, till exempel ton och kilo). Undantag för aktiviteten, bara i potentialläget: tar ett scenario bort hela aktiviteten (effekten på aktiviteten är exakt −100 procent) och talet är större än baslinjens, godtas också scenariernas största mängd. Den räknas som den största produkten av två av drivarens mängdantaganden på den försiktiga eller den optimistiska raden. Emissionsfaktorer, årtal och tider räknas inte som mängder (se *Tre scenarier*) |
| Trenderna | All godkänd text för drivaren, och profilen | Medelvärdet inte står någonstans i den texten, som andel eller procent. Trendens värden för min och max jämförs inte, eftersom motorn bara räknar med medelvärdet |
| Effekterna och attributionen | Antagandet i steg 4 som effekten lästs ur | Två av de tre scenarierna stämmer med ett godkänt antagande (eller med en produkt av två eller tre antaganden, eller ett antagande delat med basårets värde), och det tredje ligger mer än en faktor 1,5 från vad samma antagande ger |

Jämförelsen är smal med flit. Språkmodellen har rätt att räkna om och kombinera de godkända talen: en andel gånger en minskning, en förändring i kilowattimmar delad med nivån, två grupper i samma drivare. Kräver man att varje tal ska stå i den godkända texten varnar kontrollen på nästan varje riktig analys. Därför markeras bara ett tal som motsäger något godkänt, inte ett tal som bara inte går att hitta.

Prövad mot 21 sparade riktiga körningar med 78 drivare (oktober 2026). Två tal markerades, och båda var felläsningar som utläsningens egen anteckning avslöjar. Ett tal i taget ändrades sedan i körningarna för att se hur mycket kontrollen fångar:

| Ändring | Fångad |
|---|---|
| Aktiviteten basåret gånger tio | 50 av 78 |
| Emissionsfaktorn basåret gånger tio | 47 av 78 |
| En effekts medelvärde gånger 2,2 (granskarens fall, −0,38 till −0,84) | 35 av 73 |
| En effekts medelvärde halverat | 31 av 73 |
| En effekts medelvärde gånger tio | 32 av 73 |
| En effekts medelvärde gånger 1,5 | 7 av 73 |
| En effekts medelvärde satt till max | 16 av 60 |
| En effekts alla tre scenarier gånger 2,2 | 0 av 73 |

Kontrollen mättes om 2026-10-13, när trenderna började jämföras på medelvärdet och undantaget för den största mängden lades till. Underlaget var 71 körningar med 214 drivare, de flesta upprepade utläsningar av fyra godkända analyser, så talen går inte att jämföra med tabellen ovan. Före och efter ändringen fångade kontrollen lika många av de inlagda felen på varje rad utom en: aktiviteten gånger tio, 130 före och 134 efter av 214. Skillnaden kommer av hur mätningen räknar: ett inlagt fel räknas som fångat bara om talet inte redan var markerat. De fyra är den största mängden i fallet under *Tre scenarier*. Förut var den markerad redan utan fel, nu godtas den, och samma tal gånger tio blir en ny markering. Antalet markerade tal i körningarna, utan inlagda fel, gick från 22 till 5. Ingen av de 22 hörde till en utläsning med fel resultat. Tretton var trender för min och max, som motorn inte räknar med. Fyra var den största mängden i fallet under *Tre scenarier*. Fem var utläsningar som räknat på en annan bas än den godkända, eller vägt ihop en egen trend, och ändå hamnat inom tre procent från de andra utläsningarna av samma analys. De fem markeras fortfarande, med rätta, eftersom talen inte är de godkända. De slutade uppstå när utläsningen fick regeln att hålla sig till baslinjens värden: 0 markerade tal i tolv utläsningar (se DECISIONS.md).

De 71 körningarna är till största delen de analyser som ändringarna gjordes på. Samma dag prövades kontrollen därför på äldre sparade analyser som inte användes då (mätningen står under *Kända begränsningar*). Där markerade den nio tal i 35 utläsningar, och alla nio satt i utläsningar med rätt resultat. Sex gällde en bas som utläsningen flyttat för en tillkommande utsläppskälla (elen till nya elbilar, tillverkningen av nya maskiner), två en trend som vägts ihop av två godkända trender, och en ett engångsköp. De fem utläsningar som hamnade mer än fem procent från vad antagandena ger fick ingen markering. Felen där var av slag som kontrollen inte ser: ett slutår som föll bort, en känslighetspost som räknades in i summan, en trend på två motverkande poster, och en andel som räknades på en annan nivå än antagandena avsåg. En markering betyder alltså att ett tal inte är det godkända. Om resultatet är rätt eller fel säger den inget om, åt något håll.

Det kontrollen inte fångar: ett bytt tecken, en ändring under en faktor 1,5, en effekt som är härledd utan att något godkänt antagande förankrar den, alla tre scenarier ändrade lika mycket, och en baslinje som den godkända texten sätter till noll eller anger per år på ena sidan och inte den andra. En effekt som är 0 i alla tre scenarier markeras bara när drivarens egna godkända antaganden anger en effekt. Klimatfaktorerna jämförs bara med drivarens eget block i evidenssteget, och i uppföljningsläget markeras inte en konsumtionsfaktor över 1 som lästs ut som 1. Det har hänt: en godkänd konsumtionsfaktor på 1,15 lästes ut som 1,0 i åtta utläsningar av åtta (2026-10-13, innan utläsningen fick en regel om det och innan faktorerna jämfördes), resultatet blev 74 ton i stället för 88, och ingenting markerades. En trend jämförs bara med om talet står någonstans i texten, så en trend på −20 procent passerar om "20" står i drivarens text. Ett tal som inte markerats är alltså inte därmed det godkända.

`next/tools/check_godkant.py` kör jämförelsen mot sparade körningar och skriver ut både markerade tal och tabellen ovan.

## Förväntad potential och uppföljning

CAIA har två analyslägen. Användaren väljer läge innan första meddelandet, och det går inte att byta under analysen. På sidan heter de *Prognos* och *Uppföljning* (valet Välj analystyp på stegraden); här kallas de potentialläget och uppföljningsläget.

**Förväntad potential** bedömer vad en planerad åtgärd kan ge. Det är standardläget och det CAIA först byggdes för.

**Uppföljning** bedömer vad en genomförd insats faktiskt har gett och vad som återstår. Läget kom till hösten 2026, efter att granskningen av Karlstads driftsmedel 2025 visat att potentialläget gav för höga tal för genomförda insatser.

Stegen och formlerna är desamma. Skillnaden är att språkmodellen i varje steg får arton metodregler till, och dessutom egna anvisningar för steget (till exempel att basåret är året före första bidragsåret):

1. Jämförelsen är vad som hade hänt utan just de här pengarna, inte utan att kommunen gör något. Det som redan pågår, som mål, beslut, avtal och andra års pengar, hör till jämförelsen.
2. Det som hade hänt ändå räknas bort på ett enda ställe: antingen i jämförelsen (BAU) eller i attributionen, aldrig i båda. Fick pengarna bara något att hända tidigare får de nyttan för de år det kom tidigare. Attributionen är pengarnas andel av förändringen och bedöms med skäl åt båda hållen: 1 för det pengarna själva köpte eller utförde och dess egen användning, och för en effekt som går genom andra människors beslut och vanor pengarnas del bland orsakerna, oftast under 1.
3. Effekter av kampanjer, utbildning, information och ändrat beteende klingar av år för år, med en halveringstid.
4. Uppmätta tal går före antagna.
5. Max är ett rimligt högt scenario, inte alla ytterlägen samtidigt.
6. Nära noll, och "går inte att mäta än", är giltiga svar.
7. Ansökans förhandsbedömning och uppföljningens egen redovisade klimatnytta är uppgifter att pröva, inte facit.
8. Bara det som pengarna köpte räknas.
9. En insats som fått pengar flera år analyseras som en helhet.
10. Insatsens egna utsläpp och nyttan behandlas lika: det som räknas bort från nyttan räknas bort från de egna utsläppen på samma sätt, och utrustning vars köp bara tidigarelades belastar insatsen bara för de tidigarelagda åren av livslängden.
11. Bidragsbeloppet är ingen utsläppskälla. Pengarna hade använts av kommunen ändå. En egen utsläppspost ska gälla något fysiskt som köptes.
12. Gav en pilot upphov till en verksamhet som består och inte hade funnits utan insatsen, räknas en del av dess effekt även efter piloten. Att den "hade kommit ändå" senare kräver belägg i underlaget. Undanträngning av andra aktörers försäljning är en egen, motiverad andel, inte en del av attributionen.
13. Drivarens aktivitet är det som orsakar utsläppen. Undviker insatsen nyproduktion är aktiviteten det nya som undviks, och insatsen sänker den; nettoandelen bestämmer hur mycket. Den återbrukade mängden ställs aldrig upp som ökad aktivitet med lägre utsläpp per enhet, för kalkylen läser mer aktivitet som mer utsläpp. (Sola, driftsmedel körning 1, kom ut 13 / 15 / −30 ton av det skälet.)
14. En drivare som ökar utsläppen har sina värden i omvänd ordning mot nyttan, minst och kortast i det höga scenariot, och det gäller mängd, faktor och slutår. Livslängden på köpt utrustning står tvärtom, kortast i det försiktiga, eftersom en kortare livslängd gör att en större del av tillverkningen belastar insatsen. Undantaget är en kostnad som växer med nyttan, som HVO som ersätter diesel: dess mängd och andel följer nyttans i varje scenario, och bara faktorn står i omvänd ordning.
15. En kostnad blir aldrig en nytta: tillverkning, inköp och transport av det som köptes ökar utsläppen i alla tre scenarierna och ställs upp som den köpta mängden med sin egen faktor.
16. En följdeffekt som underlaget visar har inträffat räknas med en uttryckligen antagen andel, nära noll i det försiktiga scenariot. Noll är rätt bara när underlaget inte visar att den har inträffat.
17. El räknas med 59 g CO2e/kWh i alla tre scenarierna, det värde Klimatklivet anger för nordisk elmix (Naturvårdsverket 2026-03-25, efter IVL:s faktor för 2021–2023). Där skillnaden mellan timmar är själva effekten (lagring, el som flyttas till andra timmar) får faktorn för de timmarna avvika, med källa: batterilagrets nytta är just att köpa mindre el när utsläppen är höga, och ett platt medelvärde gör den till noll.
18. Köpt utrustning belastas bara med den del av livslängden som ryms till och med målåret.

Regel 2, 3, 4 och 8 skärptes samma dag som regel 15 till 18 kom: ett avdrag för det som hade hänt ändå görs på ett ställe av BAU, ikapp-år, avklingning och attribution, och en attribution under 1 kräver belägg ("kunde ha gjort det ändå" räcker inte); krav, beslut och köpta saker klingar inte av; en uppmätt varaktighet bestämmer halveringstiden; och betalade pengarna bara en kontroll av ett befintligt krav är nyttan den bättre efterlevnaden. Lydelsen av regel 2 blev först för bred: "det pengarna själva betalade har attribution 1" lästes som att andelen är 1 tills annat är visat, och de omkörda insatserna fick andelar på 0,85 till 0,9 även för beteendeeffekter. Den skrevs om samma kväll till lydelsen ovan (se DECISIONS). Koden håller i två av de nya: en kostnad som skrivits som mer mängd med lägre faktor räknas om, och utrustning skrivs av till målåret (se *Engångsposter*).

Regel 10 till 12 kom 2026-10-22, efter granskningen av driftsmedlens två körningar. Regel 13 och 14 kom samma kväll, med promptsvepet, och är bara instruktioner; kalkylen varnar redan när medelscenariot ger ökade utsläpp eller scenarierna står i fel ordning. Koden håller själv i tre delar av dem: attributionens ordning, pengarnas egna utsläpp och livslängdsandelen (se *Attribution* och *Engångsposter*). Resten är instruktioner.

Regel 2 betyder att en granskare ska leta efter avdraget på två ställen. Står attributionen på 1 i en uppföljning kan avdraget ligga i jämförelsen eller i ett slutår.

I kalkylen tillkommer tre saker.

**Medelfönstret följer insatsen.** Medel per år räknas från första startåret till målåret i stället för 2026 till 2030.

**Realiserat och återstående.** Det ackumulerade nettot delas vid uppföljningsåret. Realiserat är summan till och med det året, återstående är resten fram till målåret. Uppföljningsåret är det som analysen anger. Saknas det används i tur och ordning sista bidragsåret, det sista startåret bland de årliga drivarna, det sista startåret bland alla drivare och till sist målåret. Även realiserat är en beräkning ur antaganden, om inte analysen säger att talet är uppmätt.

**Nytta per bidragsår.** Har insatsen fått pengar flera år fördelas den ackumulerade nyttan på åren. En drivare som hör till ett visst bidragsår läggs helt på det året. Övriga drivare fördelas i proportion till årens belopp. Det som inte går att fördela redovisas som "Ej fördelat". Raderna summerar till det ackumulerade talet i varje scenario.

Prövningen av bärande antaganden (se ovan) väger tyngre i en uppföljning, eftersom halveringstid och slutår ofta är rena antaganden och ofta är de tal resultatet hänger på. De prövas på samma sätt som effekterna och attributionen.

Rapporten i uppföljningsläget har dessutom raden "Analysläge: uppföljning av genomförd insats" under rubriken, avsnittet *Uppmätt och antaget*, och en lista sist i rekommendationen över vad som behöver mätas för att de bärande antagandena ska bli mätta värden.

## När kalkylmotorn inte kan läsa talen

I steg 5 fyller språkmodellen i ett formulär, och koden vägrar formuläret om något tal är omöjligt. Det gäller bland annat när aktivitet eller emissionsfaktor saknas eller inte är större än noll, när en klimatfaktor saknas eller ligger utanför 0 till 2, när en minskning är större än 100 procent, när en trend ligger utanför −100 till +100 procent per år, när attributionen ligger utanför 0 till 1, när året för full effekt ligger före startåret, eller när en halveringstid inte är större än noll.

Då räknar språkmodellen själv. Detsamma händer när formuläret inte går att läsa alls, när utläsningen avbryts eller när något annat fel uppstår på vägen genom motorn. Ett fel hos modelltjänsten hör inte dit (bruten anslutning, överbelastning, en tidsgräns som löper ut). Då svarar steget med felet och användaren kör det igen; efter en bruten anslutning gör sidan ett nytt försök själv. Skälet är att reserven är ett nytt anrop till samma tjänst, med den tid som är kvar av stegets fem minuter (sedan 2026-10-13).

Reserven finns för att användaren ska få ett svar, och det resultatet har lägre status:

- Kalkylen är inte kontrollerad av koden och kan innehålla räknefel.
- Rapporten säger att kalkylen räknades av språkmodellen och bifogar modellens kalkyltext oförändrad i stället för motorns bilaga.
- *Talens ursprung* ersätts av en text om att källmarkering saknas för körningen.
- Sidan visar ingen stor siffra, skala eller varning från kalkylen. I en installation med konton läses ett tal ur rapportens text när rapporten sparas, och visas märkt "ur rapportens text, inte programmets kalkyl".
- I API:t är svaret märkt `deterministic: false`.

Ett sådant resultat ska inte jämföras med ett som motorn räknat, och det bör köras om innan det används.

Två mindre fel fäller inte kalkylen. Går källkontrollen sönder är talen ändå räknade av motorn, och *Talens ursprung* ersätts av en text om att källmarkeringen inte kunde tas fram. Går prövningen av bärande antaganden sönder utelämnas den ur kalkyltexten utan besked. Raden "Bärande antaganden" skrivs annars alltid, också när inget antagande har ett spann att pröva. Saknas den har prövningen gått sönder.

## Portföljen: flera åtgärder tillsammans

Varje analys räknar sin åtgärd på en egen baslinje. Lägger man ihop analyserna räknas samma ton flera gånger där åtgärderna verkar på samma utsläpp. I Karlstads energi- och klimatplan gör tre åtgärder tillsammans anspråk på 93 procent av kommunens husbyggnad. Portföljen räknar sparade analyser tillsammans så att det inte händer inom en utsläppspott.

**Utsläppspotter.** En pott är en avgränsad del av kommunens utsläpp med ett känt utsläpp per år, en källa och ett perspektiv. Potterna står i kommunprofilens `potter.toml` och får inte överlappa varandra. Karlstad har två: kommunens husbyggnad, 17 200 ton per år 2022 (kommunens interna uppgifter i analysen av åtgärden Halvera klimatpåverkan från kommunens byggnationer; Svalna anger 37 749 ton för kommunkoncernens husbyggande och skillnaden är inte utredd), och personbilstrafiken, 79 454 ton per år 2023 (Nationella emissionsdatabasen). Potterna har ingen trend än, så samma utsläpp räknas alla år.

**Vad portföljen läser.** Talen per drivare, scenario och år ur den tekniska bilagan i varje sparad rapport. Bara bilagor som kalkylmotorn skrivit läses, alltså rapporter sparade från 30 september 2026. Användaren väljer för varje del av en analys vilken pott den verkar på, eller ingen. En portfölj tar en körning per åtgärd, för två körningar av samma åtgärd kan skilja sig mer än allt överlapp (Logistikstödet räknades fem gånger med 131 till 5 815 ton per år). Potential och uppföljning blandas inte.

**Räkningen, per pott, scenario och år.** P är pottens utsläpp. En åtgärds delar på potten läggs ihop till dess förändring ΔE (före klimatfaktorerna, efter attribution) och dess egna utsläpp E.

- Åtgärdens andel av potten är s = ΔE / största av E och P. Har analysen räknat på mer än potten (allt byggande, märkt på husbyggnad) tar den sin andel av sina egna utsläpp; resten av effekten, ΔE − s × P, ligger utanför potten och räknas som i analysen.
- Kvar i potten blir P × (1 − s₁) × (1 − s₂) × …, och portföljen på potten är P minus det. Eftersom varje s är högst 1 blir den aldrig större än potten.
- Ett mål och de åtgärder som är verktyg för det räknas som målets andel. Målet är taket, och verktygen står med 0 på potten. Ger verktygen tillsammans mindre eller mer än målet säger portföljen det.
- Portföljens tal på potten fördelas tillbaka på åtgärderna i proportion till var och ens andel. Den andra regeln, genomsnittligt tillskott i alla ordningar, visas bredvid. Finns både minskningar och ökningar på samma pott används den andra regeln i båda kolumnerna.
- Åtgärdens netto i portföljen är dess netto skalat med (fördelat på potten + delen utanför) / ΔE, så klimatfaktorerna behåller sina proportioner. Delar utan pott räknas som i analysen.

Medel per år räknas över 2026–2030 i potentialläget och över de år alla analyser har i uppföljningsläget.

**Facit.** Husbyggnaden 2030 med P = 17 200 och andelarna 50, 27,6 och 15,4 procent: summan av delarna blir 16 000 ton, gemensam baslinje 11 900 och Halvera som mål 8 600. Sola 2024: 133 ton när möbelflödet är lika stort som BUF:s inköp, mot 164 ton när flödet är mycket större. Skolmåltider på 5 och 20 procent av samma utsläpp: 24 procent, inte 25. Talen kommer från `tests/test_portfolj.py`.

**Varningar.**

- Åtgärderna gör tillsammans anspråk på mer än hela potten.
- Åtgärderna överlappar inom potten, med hur många ton summan räknar för mycket.
- En analys har räknat på mer än potten.
- Flera åtgärders delar utanför potten kan vara samma ton.
- Attributionerna på en pott i uppföljningsläget är tillsammans över 100 procent.
- Fönstret är kortare än en analys egna år.
- Det finns delar utan pott.

Varje summa av åtgärdernas egna tal säger att den räknar samma ton flera gånger.

## Kända begränsningar

**Två körningar av samma åtgärd ger olika tal.** Det här är metodens största svaghet. Räkningen i steg 5 är densamma varje gång, men antagandena i steg 1 till 4 sätts av språkmodellen och varierar mellan körningar. Uppmätt på tre referensåtgärder i potentialläget, medel netto per år, samma indata varje gång:

| Referensåtgärd | Körningar (ton CO2e per år) |
|---|---|
| Tjänstebilar | 16,6, sedan 24,9, sedan −17,7 |
| Återbruk | 84,3, sedan 41,9 (en avbruten körning gav 27,6) |
| Lövblåsare | 3,1, sedan 2,2 (tidigare körningar 1,4 och 2,1) |

Tjänstebilarna bytte alltså tecken mellan två körningar. Det minustalet låg inom den föregående körningens eget spann, som gick från −13,2 till 51,8, så spannet varnade för det. Mätningarna är få, två eller tre körningar per åtgärd, och säger inget om hur spridningen ser ut för andra åtgärder. Slutsatsen är att ett enskilt medelvärde från en körning inte ska läsas som åtgärdens effekt. Läs spannet, kör åtgärden två gånger och jämför. Skiljer körningarna mycket behöver åtgärden bättre underlag snarare än en tredje körning.

Var spridningen uppstår är delvis mätt. Utläsningen av talen i steg 5 görs också av språkmodellen och kan variera: innan steg 4 delades upp per drivare gav fyra utläsningar av en och samma evidenstext 1,4, 1,4, 0,7 och 3,8 ton per år. Efter uppdelningen gav åtta utläsningar av samma text samma tal alla åtta gånger. Det gällde lövblåsarna, och slutsatsen att resten av spridningen uppstår i steg 1 till 4 höll inte för de andra åtgärderna. En mätning 2026-10-13 körde bara steg 5 om, på samma godkända steg 1 till 4, och läste av minskningen 2030:

| Godkänd analys | Utläsningar före (ton CO2e 2030) | Efter ändringen |
|---|---|---|
| Tjänstebilar | −49,5, 8,0, 11,4 och 111,2 | 88,5, 88,5, 88,7 och 88,7 |
| Återbruk | 135 till 138 i fyra, 248 till 252 i fyra | 137,4 i tre av tre |
| Lövblåsare | 3,3 i fyra av fyra | 3,3 i två av två |
| En analys från workshopadressen | 61,4 i två av två | 60,1, 61,3 och 61,3 |

Ändringen var att potentiallägets utläsning körs med hög resonemangsnivå i stället för medel och fick tre regler (se DECISIONS.md). Uppföljningslägets utläsning mättes 2026-11-08 och läser sedan dess också med hög nivå, med regeln om faktorer över 1 (DECISIONS.md, samma datum). Med medelnivån svarade utläsningen ibland efter en kort titt: på återbruket tog de felaktiga utläsningarna 15 till 18 sekunder och de riktiga 31 till 39, och på tjänstebilarna tog alla fyra 14 till 17 sekunder. Med hög nivå tar en utläsning 40 till 80 sekunder. Inget av de felaktiga talen i kolumnen "före" markerades av jämförelsen med det som godkändes. De fyra felaktiga återbrukstalen fick kalkylens varning om scenarier i fel ordning, och två av tjänstebilstalen (8,0 och 111,2) fick ingen varning alls.

De fyra analyserna i tabellen är de som reglerna skrevs och justerades på. Tabellen visar alltså att reglerna gör det de skrevs för, och säger lite om en analys de inte har sett. Därför räknades steg 5 samma dag om på äldre sparade analyser av de tre referenspaketen: 17 sparade körningar från 28 september till 8 oktober 2026, 14 av dem med olika godkända steg 1 till 4. Ingen användes när reglerna skrevs. Koden före ändringen läste varje körning en gång, koden efter minst två. Där utläsningarna gav olika tal lästes de godkända stegen för hand för att avgöra vilket som är rätt. Där alla var överens är talet inte kontrollerat.

| | Före ändringen | Efter |
|---|---|---|
| Utläsningar som gav ett resultat | 17 av 17 | 36 av 38 |
| Mer än 10 procent från vad de godkända stegen ger år 2030 | 8 av 17 | 2 av 36 |
| 5 till 10 procent ifrån | 0 av 17 | 3 av 36 |
| En godkänd konsumtionsfaktor på 1,15 läst som 1,15 | 1 av 5 | 10 av 10 |
| Utläsningar med ett markerat tal | 2 av 17 | 9 av 36 |
| Tid per utläsning | 13 till 42 sekunder | hälften under 56 sekunder, den längsta 127 |

De åtta felen före ändringen var av fyra slag. Trenden räknades från fel basår (11 ton i stället för 72). Konsumtionsfaktorn 1,15 lästes som 1,0 (fyra körningar, 14 till 21 procent för lågt). En faktor för kvarvarande utsläpp och en konsumtionsfaktor föll bort (sammantaget 24 procent för högt). Ett engångsköp räknades varje år medan ett påslag på 20 procent föll bort (omkring 1,2 ton i stället för 3,3, två körningar). Inget av de åtta fick en markering eller en varning som pekade på felet.

Efter ändringen skilde fem utläsningar mer än fem procent från vad de godkända stegen ger:

- I två räknades en mängd som antagandena anger för ett visst år om till en andel av basårets nivå. Motorn lägger andelen på nivån utan åtgärden det året, och har baslinjen en trend är de två nivåerna olika. Resultatet blev 23 procent för lågt i en analys och 6 procent i en annan.
- I två räknades en känslighetspost in som evidenssteget uttryckligen höll utanför summan (6 procent för högt och 7 procent för lågt, den andra räknade dessutom en motverkande post två gånger).
- I en föll slutåret bort på ett engångsköp (11 procent för lågt).

Därtill kom det ackumulerade talet för en analys ut som 88 ton i en utläsning och 171 i nästa, fast talet för 2030 var detsamma, eftersom tillverkningens utsläpp lades på olika år. Två av 38 utläsningar gav inget resultat: ett svar saknade formulär, och i ett fall bröts anslutningen till modelltjänsten efter 108 sekunder.

Utläsningen läser alltså klart oftare rätt än förut, även på analyser reglerna inte skrevs på, men den är inte stabil. Två utläsningar av samma godkända steg kan fortfarande skilja mer än tio procent. Ungefär var fjärde får dessutom ett markerat tal fast resultatet är rätt, och ingen av de fem som skilde sig fick någon markering (se *Jämförelsen med det som godkändes*). Mätningen gäller tre åtgärder i potentialläget. Uppföljningslägets utläsning mättes för sig 2026-11-08 (DECISIONS.md, samma datum), och spridningen i steg 1 till 4 är kvar och är inte mätt om.

**Antagandena är språkmodellens.** Andelar, effekter och tidsramar tas fram av modellen ur beskrivningen, parameterbiblioteket och kommunens data. De visas för användaren före kalkylen och kan rättas där. Hur bra resultatet blir beror på att någon som kan området läser dem.

**Tecknet kan bli fel.** En åtgärd som undviker utsläpp, till exempel återbruk, kan av modellen beskrivas som ökad aktivitet och få minustecken. Kalkylen varnar för ökade utsläpp och kvalitetsgranskningen brukar peka ut felet, men talet rättas inte av sig självt.

**Källkontrollen är smal.** Den jämför bara ett tals värde när talet pekar på en enda biblioteksrad med ett fast värde. Tal ur datafiler, tal som räknats fram ur flera parametrar och tal ur externa källor jämförs inte. Kontrollen bedömer inte heller om källan är bra eller om talet passar åtgärden. Se *Talens ursprung* ovan.

**Det användaren godkänner och det motorn räknar på är två avläsningar.** Användaren godkänner antagandena som text i steg 4. I steg 5 läser språkmodellen ut talen ur texten till motorns formulär. Sedan oktober 2026 jämför koden de två och markerar ett tal som tydligt avviker (se *Jämförelsen med det som godkändes* ovan), men jämförelsen är smal: av de ändringar den prövats mot fångar den ungefär två av tre i baslinjen och hälften i effekterna. En granskare behöver fortfarande jämföra själv: vilka tal motorn faktiskt fick står i kalkyltextens och bilagans indatarader och i tabellen i *Talens ursprung*, och de ska stämma med antagandena som godkändes i steg 4.

**Parameterbiblioteket är till stor del nationella schabloner.** I Karlstads profil är 17 av 103 parametrar lokalt verifierade, 17 hämtas ur lokala datafiler och 69 är nationella schabloner (oktober 2026). Byggmaterial och byggavfall (sektion 13) kommer ur Boverkets klimatdatabas och en rapport från SKR och Offentliga fastigheter (IVL, 2022). En faktor per kilo byggavfall saknas, eftersom ingen av källorna har en. Knappen Parametrar på sidan visar vilka.

**Klimatfaktorerna är bedömningar.** Hur en drivare fördelas mellan territoriellt och konsumtion sätts av modellen per analys och har ingen källmarkering.

**Spannet är inget konfidensintervall.** Min och max är fallen där alla osäkra tal samtidigt hamnar lågt eller högt. Sannolikheten för det är inte beräknad.

**Medelfönstret 2026 till 2030 är fast i potentialläget.** Åtgärder som verkar sent eller efter 2030 ser små ut i medel per år, som står under rubriktalet. Kalkylen varnar när åtgärden har effekt färre än hälften av åren, eller först efter de år som räknas (se *Rubriktalet och åren det gäller*), men talet är detsamma. En åtgärd med effekt tre av de fem åren får ingen varning, fast medlet är lägre än effekten ett år med full verkan. Läs alltid startåret och det ackumulerade talet tillsammans med rubriktalet.

**Portföljen kontrollerar bara överlapp inom en pott.** Delar utan pott och delar utanför potten läggs ihop som förut. Två åtgärder som verkar på var sin del av samma pott räknas som om de verkade på samma utsläpp, vilket ger ett för lågt tal; då ska potten delas. Pottens tal gäller utsläppen före klimatfaktorerna, och om pottens perspektiv stämmer med delarnas klimatfaktorer prövas inte. Pottvalet görs av användaren, analysen föreslår ingen pott än. Karlstad har två potter, och husbyggnadens baslinje är odokumenterad bortom en tidigare analys.

**Uppföljningsläget är nytt.** Det är prövat på ett fåtal insatser. I provkörningarna gav Testcyklisterna 0,0 och 0,1 ton per år i två körningar, där 2025 års analys i potentialläget hade gett 17. Att talen blev lägre var avsikten med läget, men det finns ännu inget facit att stämma av dem mot.

**Scenarier och attribution är under avstämning**, se början av dokumentet.

Tekniska begränsningar i driften (anropsgränser, tidsgränser, vad som händer vid avbrott) står i [RUNBOOK.md](RUNBOOK.md). Besluten bakom metoden och varför de togs står i [DECISIONS.md](DECISIONS.md).
