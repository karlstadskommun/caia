# Användarguide: din första analys i CAIA

För dig som är tjänsteperson och ska köra en analys själv i CAIA (Climate Action Impact Analysis). Guiden följer sidan uppifrån och ner: vad du skriver, vad du ser, vad du ska titta efter och vad du gör när något går fel. Hur talen räknas står i [METOD.md](METOD.md).

## Innan du börjar

**Räkna med en halvtimme.** CAIA:s eget arbete tar 10 till 15 minuter för en analys (en körning i oktober 2026 tog knappt nio). Till det kommer din egen tid att läsa och godkänna mellan stegen. Ett enskilt steg kan ta upp till fem minuter. Sidan visar att den arbetar och hur länge steget har hållit på, och det är normalt att det står still länge. Är modelltjänsten tillfälligt upptagen försöker sidan igen av sig själv och skriver "försöker igen" vid steget. Svarar modellen inte alls i tid får du ett fel och kör steget igen själv.

**Håll fliken öppen.** En pågående analys finns bara i den öppna fliken. Stänger du den eller laddar om sidan innan rapporten är klar är analysen borta, och du får börja om.

**Skriv inga personuppgifter.** Allt du skriver, och allt analysen tar fram, skickas till en språkmodell hos en extern leverantör. I Karlstads installation stannar texten i EU: den går via OpenRouters EU-ingång till Google Vertex AI i EU, där modellen körs (detaljerna i [DEPLOY.md](../next/DEPLOY.md)). Startsidan påminner om detta, men skriv ändå inte:

- namn på enskilda personer, till exempel anställda, sökande eller boende,
- personnummer, adresser, telefonnummer eller e-postadresser,
- uppgifter om hälsa, ekonomi eller annat som går att knyta till en person,
- sekretessbelagda uppgifter.

Beskriv åtgärden på gruppnivå: "40 anställda på förvaltningen", inte vilka de är. Klistrar du in text ur en ansökan eller ett tjänsteutlåtande, ta bort namn och kontaktuppgifter först.

**Logga in.** Sidan öppnas med en inloggningsruta för e-post och lösenord. Kontot måste vara godkänt av den som driver CAIA. Saknar du konto finns länken Skapa konto, men ett nytt konto släpps bara in om adressen är tillåten. En installation kan i stället ha ett gemensamt lösenord. Då har rutan bara ett lösenordsfält, och ingenting sparas på servern.

## Välj analystyp

Till höger på stegraden, under rubriken, står Välj analystyp med två val:

- **Prognos** (förvald): för en åtgärd som inte är genomförd än. Frågan är vad den kan ge. I metodbeskrivningen kallas det potentialläget.
- **Uppföljning:** för en insats som redan är gjord. Frågan är vad den faktiskt har gett och vad som återstår. I metodbeskrivningen kallas det uppföljningsläget.

Valet låses när du skickat ditt första meddelande, och sedan står bara det valda kvar på stegraden. Vill du byta får du börja om med Ny analys. Välj Uppföljning för allt som redan har hänt. När Karlstads driftsmedel för 2025 analyserades i potentialläget blev nio av tio medelvärden för höga: effekterna låg kvar på full nivå i åratal, och det som hade hänt ändå räknades inte bort. Uppföljningsläget finns för att rätta det.

## Beskriv åtgärden

Skriv i chattrutan. Allt från en rubrik till en längre beskrivning går, men ju mer du berättar, desto mindre behöver CAIA anta. Det här är vad åtgärdsprofilen ska fyllas med, så det lönar sig att ta med det från början:

- **Vad som ska göras**, konkret. "Byta 12 dieseldrivna tjänstebilar mot elbilar", inte "fossilfri fordonsflotta".
- **Vilka som berörs och hur många:** antal fordon, anställda, hushåll, kvadratmeter, måltider.
- **Tal du redan har:** körsträckor, energianvändning, inköpsvolymer. Skriv var talet kommer ifrån.
- **När:** startår, och när åtgärden väntas ha full effekt.
- **Vad kommunen råder över:** är det kommunens egen verksamhet, eller ska andra förmås att ändra sig?

Omfattningen, alltså hur många eller hur mycket åtgärden gäller, är det som påverkar resultatet mest. Saknas tal för den frågar CAIA efter dem innan profilen blir klar, även när beskrivningen är kort. Vet du inte, skriv det. Då antar CAIA ett tal, säger hur det togs fram och märker det som antaget hela vägen till rapporten, i stället för att du gissar ett tal som sedan ser säkert ut. Andra uppgifter som saknas antar CAIA och märker på samma sätt.

För en uppföljning ber sidan om tre saker: vad som gjordes, vad det kostade och vad som har mätts. Lägg till vilka år pengarna betalades ut och vilket år uppföljningen gäller. Skilj på det som är uppmätt och det som är uppskattat. Uppmätta tal väger tyngst i analysen.

CAIA kan ställa upp till fyra följdfrågor innan profilen är klar, och frågan om omfattningen kommer först. Svara i chatten. Innehåller din beskrivning flera olika åtgärder kan CAIA dela upp dem i flera profiler.

## De fyra stoppen

Överst på sidan visas var i analysen du är: Åtgärdsförslag, Utsläppskällor, Baslinje, Evidens, Kalkyl, QA, Rapport. CAIA stannar fyra gånger och väntar på dig. Resultatet av varje steg visas i panelen till höger, och under chatten finns en knapp för att godkänna.

Varje steg i panelen börjar med rutan *Det viktigaste*: vilka utsläpp åtgärden påverkar, nivån i dag och vart den är på väg, antagandena resultatet hänger på, resultatet och vad det motsvarar i verksamheten (till exempel så många km mindre år 2030), och om kvalitetsgranskningen varnar. Rutan läses ur stegets eget innehåll, så den säger inget som inte står längre ner. Läs den först, och läs resten där den pekar.

Vid varje stopp har du två val:

- **Godkänn** med knappen. Då körs nästa steg.
- **Rätta** genom att skriva i chatten vad som är fel. Då görs samma steg om med din rättelse, och du får granska igen. Du kan rätta flera gånger.

Du kan också ställa en fråga i chatten. Vid Utsläppskällor och Baslinje svarar CAIA i chatten, och säger där vad som ändrades eller varför inget ändrades. Den tidigare versionen står kvar i panelen, tonad, medan steget görs om, och byts mot den nya när den är klar. Ändrades ingenting står den gamla kvar och det är den du godkänner. Vid Evidens visas bara den nya versionen i panelen, utan svar i chatten.

En rättelse fungerar bäst när den är konkret och har ett tal: "Körsträckan är 9 000 km per bil och år enligt vår fordonsuppföljning 2025, inte 15 000." Skriv "det här verkar högt" och du får en ny gissning. De senare stegen räknar på den rättade versionen. Varje omkörning tar lika lång tid som steget tog första gången och kostar lika mycket.

Misslyckas en omkörning skriver sidan "Feedbacken kunde inte tillämpas. Den tidigare versionen till höger gäller fortfarande: försök igen, eller godkänn den som den är." Då är din rättelse inte med. Panelen visar den tidigare versionen igen, med en ruta ovanför som säger "Ändringen gick inte igenom. Det här är den tidigare versionen, och det är den du godkänner." och vad som gick fel. Klickar du på godkänn-knappen i det läget godkänner du alltså den version du ser, utan din rättelse. Vill du ha rättelsen med, skicka den en gång till i chatten. Rutan försvinner när en omkörning lyckas eller när du godkänner.

Det du godkänner bygger nästa steg vidare på. Ett fel du släpper igenom tidigt följer med hela vägen.

### 1. Åtgärdsprofilen

Knappen heter **Godkänn profilen och fortsätt**. Panelen visar ett kort med omfattning, sektor, drivare, målgrupp, utsläpp som påverkas, rådighet, nivå, instrumentkategori, mognad, tidsram, verkningstid, kommun och kommentarer. Nivå, instrumentkategori och verkningstid är klasserna i DIN SPEC 91637 (sedan 1.1; en analys från före 1.1 visar i stället typ av åtgärd).

Titta efter märkningen **ANTAGANDE**. Den står vid allt CAIA har antagit utan att du sagt det, och kortet visar hur många antaganden det är. Läs dem. Är omfattningen antagen står det i kommentarerna att resultatet skalar med den, och då är det det antagandet som är viktigast att rätta om du kan. Stämmer de inte, rätta nu. När du rättat visas de ändrade fälten med märkningen ÄNDRAD och det gamla värdet under.

### 2. Utsläppskällorna

Knappen heter **Godkänn utsläppskällorna och fortsätt**. Här har CAIA namngett drivarna, alltså de aktiviteter vars utsläpp åtgärden påverkar, och sagt hur effekten ska räknas. Inga tal är satta än.

Panelen visar först en sammanfattning och sedan utsläppen som åtgärden påverkar. Varje drivare står som en uträkning: aktiviteten som mäts, gånger utsläppen per enhet, ger utsläpp av ett visst slag och på en viss plats. Under det står hur åtgärden påverkar drivaren (undvika, byta eller förbättra), vilken av DIN SPEC 91637:s sex aktivitetsförändringar drivaren hör till (sedan 1.1), och hur stor risken är att samma minskning räknas två gånger. Därefter kommer **Så räknas effekten**: rakt på drivaren, som en kedja av antaganden om hur många som ändrar sig, eller inget eget tal för en åtgärd som bara stödjer andra; klicka på **Varför?** för att läsa motiveringen. (Analyser från före 2026-10-14 visar i stället sex rutor under **Så klassas åtgärden**.) Sist står det som är osäkert. Underlag som skulle göra bedömningen säkrare frågar CAIA efter i chatten.

Kontrollera att drivarna är de rätta och att ingen saknas. Det är drivarna som räknas i resten av analysen. Uppdelningen följer en fast regel, så att två körningar av samma åtgärd får samma drivare: en aktivitet är en drivare även när den ger både territoriella och konsumtionsbaserade utsläpp, och en aktivitet delas bara upp om det finns ett eget tal för varje del eller om åtgärden ändrar delarna olika. Saknas till exempel tillverkningen av det som ska köpas in kommer den inte med i resultatet.

### 3. Baslinjen

Knappen heter **Godkänn baslinjen och fortsätt**. Baslinjen är nuläget för varje drivare: hur stor aktiviteten är per år, vilka utsläpp den ger per enhet, och hur det väntas utvecklas utan åtgärden.

Panelen visar talen per drivare. I chatten säger CAIA vad steget gör, vilka data som saknas och vilka frågor den har till dig. Svara på frågorna i chatten om du kan; då görs baslinjen om med dina svar.

Kontrollera storleksordning och enheter. Är det rätt antal fordon, rätt antal kilometer, rätt år? Har du egna tal som är bättre än de CAIA hittat, skriv in dem med källa.

Står **(antaget)** efter nivån i dag i rutan *Det viktigaste* bygger nivån på ett antagande, oftast en omfattning som CAIA antog i profilen. Vilket står vid talet längre ner. Utvecklingen utan åtgärden räknas med en enda årlig takt från i dag till målåret. Väntas utvecklingen gå i faser, till exempel snabbt de första åren och sedan långsammare, räknar CAIA om faserna till en takt som ger samma nivå målåret och skriver faserna i kommentaren.

### 4. Antagandena

Knappen heter **Godkänn antagandena och beräkna**. Det här är det viktigaste stoppet. Panelen visar för varje drivare:

- tre klimatfaktorer (territoriell, konsumtion och överlapp) i procent av effekten, med motivering,
- åtgärdens effekt som tre värden: försiktigt, troligt och optimistiskt,
- en bedömning av underlagets kvalitet och av hur väl talet gäller lokalt,
- hänvisningar till parameterbiblioteket och andra källor.

Läs de troliga värdena och fråga dig om du skulle kunna försvara dem inför en kollega. Titta särskilt på hur stor andel av målgruppen som antas ändra sig. Det talet är oftast det som resultatet hänger på, och det som oftast saknar källa.

När du godkänner här räknar CAIA kalkylen, kvalitetsgranskar den och skriver rapporten i en följd, utan fler stopp. Det tar några minuter.

## Läs rapporten

Rapporten visas i tre lager, så att det viktigaste står överst och resten finns ett klick bort:

1. Åtgärdens namn och den stora siffran, med spannet, grafen och varningarna.
2. Rutan **Bedömning**: rapportens samlade rekommendation och tre nivåer under den.
3. **Rapportens delar**: resten av rapporten som rader du fäller ut, en i taget eller alla på en gång.

### Den stora siffran

När rapporten är klar står åtgärdens namn överst. Under det står rubriktalet, till exempel "216 ton CO₂e/år", under rubriken *Förväntad klimatnytta år 2030*. Det är hur mycket utsläppen minskar under målåret, 2030 om inget annat har valts, i det troliga scenariot. Positivt tal betyder minskade utsläpp. Under talet står samma år uppdelat på territoriell, konsumtion och netto.

När rapporten är klar står rapportens korta tolkning av talet under det: vad minskningen motsvarar och vad som driver den, i några meningar. Den är hämtad ur rapportens medelscenario och står inte en gång till längre ner. Tolkningarna av det försiktiga och det optimistiska scenariot står kvar i rapportens avsnitt *Beräknad klimatnytta*.

I en uppföljning heter rubriken *Beräknad klimatnytta av insatsen* och rubriktalet är i stället ett medelvärde per år över insatsens egna år. Sist i rutan, under skalan och det ackumulerade talet, står hur mycket som är realiserat och hur mycket som återstår.

### Spannet

Under siffran finns en skala med Låg, Mellanscenario och Hög. Låg och hög är samma år i det försiktiga och det optimistiska scenariot. Sedan följer medel per år för 2026 till 2030 och det ackumulerade talet fram till målåret.

### Grafen år för år

När kalkylen är klar visar en graf hur nyttan byggs upp år för år, från det år åtgärden börjar till målåret. Den orange linjen är det troliga scenariot, det ljusa bandet går från det försiktiga till det optimistiska. Punkten är målåret, och dess värde är rubriktalet. Det grå fältet är åren 2026 till 2030, och den streckade linjen är medelvärdet för dem.

Grafen visar varför medelvärdet är lägre än rubriktalet för en åtgärd som växer fram: åren innan den är fullt utbyggd drar ner medlet. Texten under grafen säger båda talen. Citera rubriktalet som målårets minskning, och medelvärdet som medel för 2026 till 2030.

Läs alltid spannet tillsammans med siffran. Är spannet brett, eller går det från minus till plus, är resultatet osäkert, och rubriktalet ska inte citeras ensamt. Det höga värdet är fallet där varje osäkert antagande slår in åt det bästa hållet samtidigt.

### Varningarna

Direkt under siffran visas kalkylens varningar när det finns några. De vanligaste:

- **Ökade utsläpp.** Det troliga scenariot ger minus. Antingen ökar åtgärden verkligen utsläppen, eller så har ett antagande fått fel tecken. Det senare händer för åtgärder som undviker utsläpp, som återbruk. Använd inte resultatet förrän du vet vilket.
- **Effekten ligger utanför 2026 till 2030.** Medelvärdet per år räknas över de åren. En åtgärd som verkar senare får noll. Titta på det ackumulerade talet i stället.
- **Åtgärden har effekt bara ett eller två av åren 2026 till 2030.** Summan delas ändå på fem år, så medelvärdet blir lågt jämfört med effekten de år åtgärden verkar. Varningen säger vilka år det gäller. Läs siffran tillsammans med startåret och det ackumulerade talet.
- **Åtgärden har effekt först efter målåret och efter 2030.** Då är både medelvärdet och det ackumulerade talet noll. Varningen säger vilket år effekten börjar. Nollan beror på vilka år som räknas och säger inget om åtgärdens effekt.
- **Ingen effekt.** Ingen drivare har fått någon effekt i det troliga scenariot.
- **Kvalitetsgranskningen varnar.** QA-steget har satt status varning. Rutan visar en kort rad, med granskningens första anmärkning om den ryms i en mening. *Läs mer* fäller ut alla anmärkningar, det granskningen föreslår och vad omräkningen kan rätta. *Öppna hela kvalitetsgranskningen* tar dig till steget i analysunderlaget.
- **Ett tal avviker från det du godkände.** Ett tal som beräkningen fick stämmer inte med baslinjen eller antagandena du godkände i steg 3 och 4. Talet och skälet står under Kontrollera först i *Talens ursprung*. Jämför med det du godkände innan du använder resultatet.

En varning betyder att talet inte ska användas förrän du förstår orsaken.

### Räkna om kalkylen med anmärkningarna

Varnar kvalitetsgranskningen eller kalkylens egna kontroller visas knappen *Räkna om kalkylen med anmärkningarna* under varningarna. Den räknar om kalkylen, granskningen och rapporten på samma antaganden som du godkände, med anmärkningarna som rättelse. Den kan rätta hur antagandena har lästs in i beräkningen, till exempel ton som blivit kilo eller ett tal på fel ställe. Den ändrar inte antagandena själva: tycker du att ett antagande är fel, gör en ny analys med det ändrat.

Efteråt står det i chatten vad siffran var och vad den blev. Blev den densamma gällde anmärkningarna inte inläsningen. Går omräkningen inte igenom gäller den förra beräkningen. Den omräknade rapporten sparas som en ny rad i listan, och den gamla ligger kvar.

### Bedömningen

Under siffran står rutan **Bedömning**. Överst i den står rapportens samlade rekommendation: om åtgärden är värd att genomföra och på vilka villkor, i några meningar. Under den står tre nivåer:

- **Osäkerhet**: rapportens egen bedömning av hur osäkert resultatet är, till exempel Medel eller Medel till hög.
- **Kvalitetsgranskning**: Godkänd eller Varning. Under en pågående analys är det samma besked som varningen under siffran.
- **Risk för dubbelräkning**: hur troligt det är att samma minskning också räknas i en annan åtgärd.

Behöver tal i kalkylen kontrolleras står knappen **Kontrollera först**, med antalet tal, sist i rutan. Den fäller ut *Talens ursprung* och tar dig dit.

Nivåerna är hämtade ur rapportens del om osäkerhet, QA och beroenden, och motiveringen står kvar där. En nivå som rapporten inte anger visas inte.

### Rapportens delar

Resten av rapporten står under **Rapportens delar**, en rad per avsnitt. Varje rad har avsnittets namn och en rad om vad det innehåller, till exempel scenariernas tal under *Beräknad klimatnytta* eller hur många källor *Källor och underlag* har. Klicka på raden för att fälla ut avsnittet, och en gång till för att fälla ihop det. **Visa alla delar** fäller ut allt på en gång, och **Fäll ihop alla** stänger det igen. Visas ingen stor siffra överst är *Beräknad klimatnytta* utfälld från början.

Delarna är, i rapportens ordning: kort beskrivning av åtgärden, beräknad klimatnytta, *Vad åtgärden ändrar i verksamheten* (samma förändring som tonnen, i km, liter, m² eller den enhet drivaren räknas i, för målåret och som snitt per år; skrivet av kalkylmotorn), hur åtgärden minskar utsläppen, nyckelantaganden och beräkningsgrund, tidsprofil (när effekten kommer), osäkerhet, QA och beroenden, nästa steg, *Följ upp med* (en eller två indikatorer per bärande drivare, i enheter som antal elbilar eller m² renoverad yta, med dagens värde om underlaget har det och var det hämtas; finns inte i en uppföljning, där *Vad som behöver mätas* står under nästa steg), källor och underlag, den tekniska bilagan och *Talens ursprung*. Löptexten är skriven av språkmodellen. Läs delen om osäkerhet, QA och beroenden: där står varför nivåerna i bedömningen blev som de blev och vad kvalitetsgranskningen anmärkt på.

I den nedladdade texten heter *Nästa steg* *Rekommendation och nästa steg* och börjar med den samlade rekommendationen. På sidan står rekommendationen i bedömningen och inte en gång till i delen.

En uppföljningsrapport har dessutom raden "Analysläge: uppföljning av genomförd insats" över bedömningen, delen *Uppmätt och antaget*, och sist i nästa steg en lista över vad som behöver mätas.

### Talens ursprung

Sista delen är *Talens ursprung*: en tabell med varje tal kalkylen bygger på, dess värde och var det kommer ifrån (parameterbiblioteket, kommunens data, en extern källa eller ett antagande). Raden säger hur många tal kalkylen bygger på och hur många av dem som behöver kontrolleras.

Finns rubriken **Kontrollera först** överst i delen, börja där. Den listar tal som saknar ursprung, där CAIA inte kunde hitta talet på det ställe det sades komma ifrån, eller som avviker tydligt från det du godkände i steg 3 och 4. Talen kan vara rätt, men någon behöver slå upp dem innan rapporten används som underlag. Lägg också märke till hur många tal som är märkta antagande, och om de stora talen hör dit.

Jämförelsen med det du godkände fångar inte allt, till exempel inte ett bytt tecken eller en liten ändring. Läs därför också tabellen mot antagandena i steg 4.

### Den tekniska bilagan

*Teknisk bilaga: Beräkningssteg* är skriven av kalkylprogrammet, inte av språkmodellen. Den visar indata per drivare och en tabell per scenario med varje mellansteg för varje år. Du behöver inte läsa den för att använda rapporten. Den finns för att en granskare ska kunna räkna efter.

### Analysunderlaget

Länken **Visa analysunderlag (alla steg)** visar allt som togs fram på vägen: profilen, utsläppskällorna, baslinjen, antagandena, kalkylen och kvalitetsgranskningen. Använd den när en siffra i rapporten väcker frågor.

### Parametrarna

Knappen **Parametrar** överst visar parameterbiblioteket: vilka klimatfaktorer CAIA använder, och om varje värde är lokalt verifierat, hämtat ur en lokal datafil eller en nationell schablon. Bygger analysen på schabloner där du har lokala tal, säg det i en rättelse.

Varje parameter står med sin beskrivning, och under den det id som rapportens *Talens ursprung* hänvisar till (till exempel `BASE_pop`). Ett värde som hämtas ur en lokal datafil visas som talet i filen, med en rad under om vad som lästes och ur vilken fil. Några parametrar pekar på något som inte är ett enda tal i en fil, till exempel svaren i medborgarundersökningen. Där står i stället att värdet läses ur datafilen vid varje analys.

## Spara och ta med rapporten

När du loggat in med eget konto sparas rapporten automatiskt när den är klar. Sidan visar "Sparar..." och sedan "Sparat". Står det "Sparfel - rapporten är inte sparad", ladda ner rapporten innan du gör något annat. Dina sparade rapporter finns under **Sparade analyser** överst. Du ser bara dina egna, och bara de 30 senaste. I en installation med gemensamt lösenord i stället för konton sparas ingenting: ladda ner rapporten.

Det som sparas och laddas ner är rapporttexten med den tekniska bilagan och *Talens ursprung*. Analysunderlaget, grafen, skalan med låg och hög och varningarna under siffran följer inte med. De finns bara så länge den färdiga analysen är öppen i fliken, och de visas inte när du öppnar en sparad rapport. Vill du ha dem kvar, skriv ut eller spara som PDF medan analysen är öppen.

**Skriv ut eller spara som PDF** öppnar webbläsarens utskrift med siffran, grafen och rapporten, utan chatten och knapparna. Utskriften har alla delar utfällda, och de du hade ihopfällda fälls ihop igen efteråt. Välj "Spara som PDF" som skrivare för att få en fil att skicka vidare. Sist står att rapporten är framtagen med CAIA och att siffrorna är estimat.

**Ladda ner som text (.md)** ger rapporten som en textfil i formatet Markdown, med samma rad sist. Filen går att öppna i en textredigerare.

**Ny analys** frågar först om en analys pågår, eftersom den annars försvinner. Samma fråga kommer om du laddar om sidan eller stänger fliken mitt i. När rapporten är klar nollställs sidan utan fråga, så kontrollera att rapporten är sparad, utskriven eller nedladdad först.

När analysen är klar går den inte att ändra genom att skriva i chatten. Vill du pröva en justerad version av åtgärden, klicka Ny analys och beskriv den på nytt.

## Räkna flera åtgärder tillsammans

Varje analys räknar sin åtgärd för sig. Verkar flera åtgärder på samma utsläpp, till exempel två åtgärder för kommunens byggande, räknar summan av deras tal samma ton flera gånger. **Portfölj** överst räknar sparade analyser tillsammans:

1. Kryssa i minst två sparade analyser, en per åtgärd, och klicka **Fortsätt till utsläppspotterna**.
2. För varje del av en åtgärd väljer du vilken utsläppspott den verkar på, eller Ingen utsläppspott. En utsläppspott är en avgränsad del av kommunens utsläpp med ett känt utsläpp per år, till exempel kommunens husbyggnad.
3. Är en åtgärd ett mål, som Halvera klimatpåverkan från kommunens byggnationer, kryssar du i vilka av de andra som är sätt att nå det. De räknas då inom målet, inte ovanpå det.
4. Klicka **Räkna portföljen**.

Resultatet visar summan av analysernas egna tal och portföljens tal, där åtgärder på samma pott inte räknas två gånger. Läs avsnittet *Att läsa först*. Det säger var åtgärderna överlappar och vad portföljen inte har kunnat kontrollera. Analyser sparade före 30 september 2026 kan inte användas, och två körningar av samma åtgärd kan inte ingå i samma portfölj. Hur portföljen räknar står i [METOD.md](METOD.md), *Portföljen*.

## Kör två gånger

Två körningar av samma åtgärd ger inte samma tal, eftersom språkmodellen sätter antagandena på nytt varje gång. På CAIA:s referensåtgärder har skillnaden mellan två körningar varit allt från en tredjedel till ett byte av tecken (se [METOD.md](METOD.md), Kända begränsningar).

Ska resultatet användas i ett beslut, kör åtgärden två gånger med samma beskrivning och jämför. Hamnar körningarna nära varandra har du ett stadigare underlag. Skiljer de sig mycket, jämför antagandena i de två rapporterna: skillnaden visar vilket tal som behöver ett bättre underlag.

## När något går fel

| Det här händer | Gör så här |
|---|---|
| "Fel i ..." följt av "Analysen stannade. Du kan försöka igen, eller skriva feedback först." | Ett steg misslyckades efter att du godkänt. Klicka på godkänn-knappen igen: sidan står kvar på samma stopp och kör om steget. Feltexten säger vad som hände, till exempel "Modellen svarade inte i tid. Kör steget igen." eller "Steget tog för lång tid. Försök igen." |
| "Feedbacken kunde inte tillämpas ..." | En rättelse du skrev gick inte igenom. Skicka rättelsen en gång till i chatten. Knappen godkänner den gamla versionen utan din rättelse. |
| Ett fel direkt efter ditt första meddelande | Det finns ingen knapp än. Skicka beskrivningen igen. |
| "Steget misslyckades (fel-id ...)" eller "Kommunprofilen går inte att läsa (fel-id ...)" | Kör steget igen. Återkommer det, ge fel-id:t till den som driver CAIA. |
| "Serverfel" med ett nummer | Försök igen. Återkommer det, kontakta den som driver CAIA och ta med numret. |
| "För många anrop. Vänta en stund och försök igen." | Du har nått gränsen för antal anrop. Vänta en minut. Har du kört många analyser samma dag kan det vara dygnsgränsen, omkring tio analyser. |
| Inloggningsrutan visas mitt i en analys (installation med konton) | Logga in igen. Analysen ligger kvar bakom rutan och du kan fortsätta. Ladda inte om sidan, då försvinner den. |
| "Ej inloggad. Ladda om sidan och logga in igen." (installation med gemensamt lösenord) | Inloggningen har gått ut efter tolv timmar. När sidan laddas om försvinner en pågående analys, så den behöver göras om. |
| Rapporten säger att kalkylen räknades av språkmodellen, eller under siffran står "ur rapportens text, inte programmets kalkyl" | Kalkylprogrammet kunde inte läsa talen ur analysen, och språkmodellen räknade själv. Det resultatet är inte kontrollerat och saknar källmarkering. Kör analysen igen. |
| Resultatet är orimligt | Öppna analysunderlaget och leta upp antagandet som sticker ut. Kör sedan en ny analys och rätta det vid rätt stopp. |
| Du stängde fliken mitt i analysen | Analysen är borta. Det steg som pågick slutförs på servern och kostar ändå, men resultatet går inte att hämta. Börja om. |

## Om guiden

Guiden är skriven efter en genomgång av sidan i oktober 2026, steg för steg i potentialläget. Uppföljningslägets rubriker och raden om realiserat och återstående är beskrivna efter sidans kod och en sparad körning, eftersom genomgången gjordes med sparade exempelsvar som saknar dem. Ändras sidan ska guiden ändras samtidigt.
