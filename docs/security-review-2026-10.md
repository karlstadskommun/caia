# Säkerhetsgranskning av CAIA, oktober 2026 (sammanfattning)

I oktober 2026 granskades CAIA mot alla tio kategorierna i OWASP Top 10:2025: koden, och den installation som Karlstads kommun kör. Granskningen gjordes i två omgångar, 7 och 8 oktober, med riktade prov mot koden och mot den skarpa installationen. Det var en kodgranskning med prov, inget penetrationstest av en fristående part. Det här är en sammanfattning: den fullständiga rapporten stannar hos Karlstads kommun, eftersom den beskriver hur produktionen är uppsatt. Av 44 fynd (1 Hög, 17 Medel, 26 Låg) är 42 stängda, varav 19 med en mindre rest kvar, och två är godtagna som risk. Inget fynd står öppet.

Kod som hänvisar till ett fynd med nummer hänvisar till raden med samma nummer i tabellen nedan.

## Fynden

Allvarlighet: **Hög** betyder att en utomstående kan utnyttja det och att det kostar pengar eller data. **Medel** kräver ett inloggat konto, en lyckad manipulation av språkmodellen eller av en person, eller en ändrad inställning. **Låg** är härdning.

Status: **Stängt** betyder att rättningen är gjord. **Stängt, rest kvar** betyder att det mesta är gjort och att en mindre, känd del återstår; resten står kort i tabellen. **Godtaget som risk** betyder att det är ett medvetet beslut att lämna fyndet.

| ID | Område | Allvarlighet | Status | Vad det gällde |
|---|---|---|---|---|
| S1 | Driftsättning | Hög | Stängt, rest kvar (2026-10-07). Rest: en intern avstämning hos driftansvarig. | En äldre driftsättning, byggd före e-postspärren och anropsgränserna, låg kvar på en egen publik adress. |
| S2 | Sidans skript | Medel | Stängt (PR #17) | Rensningen av modellens text släppte igenom video- och ljudelement, så att webbläsaren kunde hämta en främmande adress utan klick. |
| S3 | Anropsgränser | Medel | Stängt (PR #17) | Ett reguljärt uttryck med orimlig körtid (ReDoS) gjorde att en sparad rapport kunde uppta en serverprocess länge. |
| S4 | Inloggning | Medel | Stängt (PR #17) | Ett ogiltigt inloggningsbevis kunde få servern att göra ett anrop till inloggningstjänsten utan att avsändaren var inloggad. |
| S5 | Loggning | Medel | Stängt (PR #17) | Nekade inloggningar, fel lösenord och nådda anropsgränser loggades inte. |
| S6 | Anropsgränser | Medel | Stängt, rest kvar (PR #17). Rest: dygnsgränsen räknas per serverinstans, och nyckeln hos modelltjänsten delas med andra verktyg. | Kostnadsgränsen räknade antalet anrop men inte hur stort varje anrop fick vara. |
| S7 | Databas och åtkomst | Medel | Stängt (PR #17) | Tabellen för sparade rapporter saknade storleksgräns och gick att skriva till förbi appen. |
| S8 | Installationsguide | Medel | Stängt, rest kvar (PR #17). Rest: inget tak på samtidiga anrop per användare på egen server. | Guiden för egen server saknade åtkomstlogg och HSTS och räknade fel bakom flera proxyer. |
| S9 | Inloggning | Låg | Stängt (PR #17) | E-postspärren kontrollerade inte själv att e-postadressen var bekräftad. |
| S10 | Beroenden | Låg | Stängt, rest kvar (2026-10-07). Rest: Python-paketen är låsta till version men inte med kontrollsummor. | Varningar för paket med kända sårbarheter var inte påslagna. |
| S11 | Felhantering | Låg | Stängt (PR #17) | Ett felmeddelande visade serverns sökväg för användaren. |
| S12 | Inloggning | Låg | Stängt, rest kvar (PR #17). Rest: i lösenordsläget gäller en kopierad kaka även efter utloggning. | Inloggningsbevis utan utgångstid godtogs. |
| S13 | Inställningar | Låg | Stängt (PR #17) | Ingen varning vid start när inloggningen var avstängd för utveckling. |
| S14 | Sidans skript | Låg | Stängt (PR #17) | Källmarkeringen ändrade HTML efter rensningen, alltså i fel ordning. |
| S15 | Beräkningens integritet | Låg | Godtaget som risk av Karlstads kommun 2026-11-09 (konstruktionsval, lämnat med avsikt 2026-10-08) | Servern sparar inget tillstånd, så en användare kan själv få egna tal märkta som beräknade av räknemotorn. Rapporten ska inte beskrivas som manipulationssäker. |
| S16 | Inloggning | Medel, Hög om e-postfiltret öppnar länkar i inkommande mejl | Godtaget som risk (2026-10-15) | Med öppen registrering och bekräftelse via länk visar bekräftelsen bara att länken öppnats, inte att den som valde lösenordet äger adressen inom den tillåtna e-postdomänen. |
| S17 | Databas och åtkomst | Medel | Stängt, rest kvar (2026-10-07). Rest: antalet rader per konto är inte begränsat. | Varje konto i en delad databas kunde spara rader i rapporttabellen förbi appens lista över tillåtna adresser. |
| S18 | Anropsgränser | Medel | Stängt (PR #27) | Storleksgränsen täckte inte sammanfogningen av delsvaren i evidenssteget. |
| S19 | Anropsgränser | Medel | Stängt (PR #27) | En anropsväg utan anropsgräns läste lång text med onödigt hög körtid. |
| S20 | Sidans skript | Medel | Stängt, rest kvar (PR #27). Rest: en påhittad kopia av bilagan kan stå i modellens del, ovanför den riktiga. | Text från språkmodellen kunde dölja programmets egna avsnitt i rapporten och visa påhittade. |
| S21 | Beräkningens integritet | Medel | Stängt, rest kvar (PR #34, utökad i PR #64 2026-10-15). Rest: små eller likformiga avvikelser märks inte. | Ingen kod jämförde talen som gick in i beräkningen med dem användaren hade godkänt. |
| S22 | Loggning | Medel | Stängt, rest kvar (PR #27). Rest: lösenordsläget och egen server loggar inte allt lika fullständigt. | Godkänd användning lämnade inget spår i loggen. |
| S23 | Driftsättning | Medel | Stängt (2026-10-07) | Den närmast föregående driftsättningen, med felen kvar, låg öppen på sin egen adress. |
| S24 | Inloggning | Medel | Stängt (2026-10-08) | En delad signeringshemlighet som appen inte behövde fanns i driftmiljön, och inloggningar signerade med den godtogs. |
| S25 | Nycklar i historiken | Medel | Stängt (2026-10-08) | En nyckel till en äldre databastjänst fanns i en tidigare incheckad inställningsfil; tjänsten den hörde till är borttagen. |
| S26 | Inloggning | Låg | Stängt (PR #27) | Under ett avbrott hos inloggningstjänsten skickades okontrollerade inloggningsbevis vidare igen. |
| S27 | Inloggning | Låg | Stängt, rest kvar (PR #27). Rest: en nyss indragen nyckel kan godtas under högst en hämtning av nyckellistan. | En signeringsnyckel som dragits in kunde godtas igen under ett avbrott. |
| S28 | Inloggning | Låg | Stängt (PR #27) | E-postspärren hanterade ovanliga tecken och värden för löst. |
| S29 | Felhantering | Låg | Stängt (PR #64, 2026-10-15) | Ett räknat anrop kunde köra två modellsteg som tillsammans tog längre tid än funktionen fick. |
| S30 | Anropsgränser | Låg | Stängt (PR #27) | I lösenordsläget gällde anropsgränsen per nätadress, inte per användare som guiden sa. |
| S31 | Loggning | Låg | Stängt (PR #64, 2026-10-15) | Tre felvägar kunde skriva stycken ur en analys till loggen. |
| S32 | Loggning | Låg | Stängt, rest kvar (PR #27). Rest: hashen är en pseudonym, och lagringstiden för loggar bestäms av den som driftar. | Hashade IP-adresser i loggen går att räkna tillbaka, och var olika per serverinstans utan nyckel. |
| S33 | Beroenden | Låg | Stängt, rest kvar (PR #27). Rest: två av sidans bibliotek är från 2024. | Biblioteken i sidan bevakades inte av något verktyg, och ett av dem var två år gammalt. |
| S34 | Sidans skript | Låg | Stängt, rest kvar (PR #27). Rest: säkerhetspolicyn tillåter skript inbäddat i sidan. | Sidans säkerhetspolicy tillät alla filer hos ett externt CDN och var ingen andra spärr mot skript. |
| S35 | Beroenden | Låg | Stängt (PR #64, 2026-10-15) | Luckor i bevakningen av beroenden och i det automatiska testflödet. |
| S36 | Installationsguide | Låg | Stängt, rest kvar (PR #27). Rest: kodens ägare och versionsmärkning vid uppdatering. | Guiden för egen server lät tjänstekontot äga koden, skapade inställningsfilen oskyddad och uppdaterade utan versionsmärkning. |
| S37 | Inställningar | Låg | Stängt (PR #27) | Appen startade utan varning med farliga inställningar, bland annat en hemlig nyckel på den publika nyckelns plats. |
| S38 | Loggning | Låg | Stängt, rest kvar (PR #27). Rest: en ofullständig kommunprofil ger onödiga varningsrader. | En enda förfrågan kunde skriva en mycket lång loggrad. |
| S39 | Installationsguide | Låg | Stängt, rest kvar (PR #27). Rest: guidens exempel har inga automatiska tester. | Guider och kod sa olika saker. |
| S40 | Sidans skript | Låg | Stängt, rest kvar (PR #27). Rest: ett klick på en länk från modellen kan föra med sig det som står i länken. | Länkar i rapporten öppnades i samma flik och kunde föra data ut med ett klick. |
| S41 | Sidans skript | Låg | Stängt (PR #27) | Viss text fick visningen att krascha, en följd av den skärpta rensningen av modellens text. |
| S42 | Sidans skript | Låg | Stängt, rest kvar (PR #27 och PR #64, 2026-10-15). Rest: viss lång text tar fortfarande ett par sekunder att visa. | Markdown-biblioteket har orimlig körtid på vissa mönster och kunde frysa användarens flik. |
| S43 | Anropsgränser | Låg | Stängt (PR #27) | Två reguljära uttryck i sammanfogningen hade orimlig körtid på viss text. |
| S44 | Prompter | Låg | Stängt, rest kvar (PR #27). Rest: promptarna säger inte uttryckligen att inklistrad text är uppgifter och inte instruktioner. | Inklistrad text gick in i promptarna utan att skiljas från promptens egna markeringar. |

## Det som en ny installation själv ansvarar för

Granskningen rör både koden och en viss installation. En del av skyddet ligger i inställningar som den som driftar CAIA måste sätta själv. Det här är granskningens rekommendationer för en ny installation:

- **Kräv bekräftelse via e-post** i Supabase innan ett konto kan logga in. Appens egen kontroll är bara en andra spärr. DEPLOY.md och INSTALL.md har ett steg som kontrollerar inställningen.
- **Begränsa vilka som släpps in** med `CAIA_ALLOWED_EMAILS`. En hel e-postdomän tillsammans med öppen registrering ger risken att någon registrerar en kollegas adress. Säkrast är kommunens egen inloggning (till exempel Entra ID), en engångskod i bekräftelsemejlet i stället för en länk, eller namngivna adresser.
- **Håll `CAIA_DEV_OPEN` avstängt** i produktion. Det stänger av inloggningen.
- **Sätt `CAIA_SECRET_KEY`**, så att hashade adresser i loggen blir lika i alla serverinstanser. Behandla hashen som en pseudonym.
- **Låt `CAIA_AUTH_FALLBACK` vara avstängt** om det inte behövs.
- **Lägg bara Supabase-projektets publika nyckel i sidans inställningar**, aldrig den hemliga. Lägg inte in projektets delade signeringshemlighet (`SUPABASE_JWT_SECRET`) om projektet signerar inloggningar med publika nycklar.
- **Kör databasmigreringarna för rapporttabellen**, och håll databasens lista över vilka som får spara lika med appens lista. Ett eget Supabase-projekt för CAIA är bättre än ett som delas med andra verktyg, och antalet sparade rader per konto bör följas.
- **Ta bort gamla driftsättningar och kräv inloggning för varje driftsättnings egen adress** hos värdplattformen, så att en äldre version utan rättningarna inte ligger öppen.
- **Använd en egen API-nyckel för CAIA hos modelltjänsten**, med ett kredittak och ett larm på förbrukningen.
- **Bestäm vart loggarna går och hur länge de sparas**, och behandla dem som analyserna, eftersom felvägar och användningsrader rör användarnas arbete.
- **Slå på sårbarhetsvarningar och automatiska uppdateringsförslag** för både Python-paketen och sidans bibliotek, och håll biblioteken uppdaterade.
- **Egen server:** följ INSTALL.md. Det betyder åtkomstlogg, HSTS och omdirigering från port 80, `CAIA_TRUSTED_PROXIES` satt till antalet proxyer framför appen, en skyddad inställningsfil, ett tjänstekonto som inte äger koden, en antecknad version vid varje uppdatering och tillräckligt många trådar för antalet samtidiga analyser. I lösenordsläget delar alla bakom samma nätadress på anropsgränsen, och en kopierad kaka gäller även efter utloggning.
