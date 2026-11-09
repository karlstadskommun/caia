# Drift av CAIA

För den som driftar CAIA (Climate Action Impact Analysis). Installation på egen server står i [next/INSTALL.md](../next/INSTALL.md), Vercel-uppsättningen i [next/DEPLOY.md](../next/DEPLOY.md). Här står det som händer efteråt.

## Var allt finns

| Del | Var | Anteckning |
|---|---|---|
| Appen | Ett Vercel-projekt ([next/DEPLOY.md](../next/DEPLOY.md)) eller en egen server ([next/INSTALL.md](../next/INSTALL.md)) | Planen avgör tidsgränsen per anrop och hur länge loggarna sparas. |
| Inloggning och sparade rapporter | Ett Supabase-projekt, eller lösenordsläge utan databas | Tabellen `reports` och schemat `caia` är CAIA:s egna. Delar projektet konton med ett annat verktyg slår dess inställningar för inloggning igenom här. |
| Modellanrop | En nyckel hos OpenRouter | Nyckelns månadsgräns och kontots saldo är de enda hårda kostnadsgränserna. |
| Kommunprofil | `next/src/caia/kommuner/<slug>/`, eller en mapp utanför repot | `CAIA_KOMMUN=<slug>` eller `CAIA_KOMMUN_DIR=<sökväg>`. |

Karlstads egen uppsättning (konton, adresser, listan över tillåtna konton) står i ett internt driftdokument hos kommunen.

## Deploy

Produktionen deployas för hand. En push eller merge till `main` deployar ingenting.

1. Se till att `main` är grön i GitHub Actions.
2. Checka ut `main` rent (inga lokala ändringar, de laddas upp också): `git status` ska vara tom.
3. Prova först som förhandsversion: `cd next && vercel` (utan `--prod`). Vercel ger en egen adress. Preview-miljön behöver samma variabler som produktionen, och Supabase behöver förhandsadressen under Redirect URLs om någon ska kunna registrera sig där (inloggning med befintligt konto fungerar ändå). Förhandsadressen kräver inloggning hos Vercel (se nedan): öppna den i en webbläsare där du är inloggad med kontot som äger projektet. Automatiska prov skickar i stället en hemlighet från projektets Deployment Protection (Protection Bypass for Automation) i huvudet `x-vercel-protection-bypass`.
4. Kör en hel analys på förhandsadressen.
5. `cd next && vercel --prod`.
6. Smoke-testa produktionen enligt DEPLOY.md.
7. **Efter en säkerhetsrättning: radera de äldre deployerna** (`vercel ls <projekt>`, sedan `vercel remove <adress>` en i taget). Behåll bara den närmast föregående som återställningspunkt. Varje gammal deploy har en egen adress som fortsätter köra den gamla koden, med samma nycklar och samma inloggning, så länge den finns. Den som behålls är alltså bygget från före rättningen: det är inloggningen hos Vercel i nästa stycke som håller den stängd utåt.

**Varje deploys egen adress kräver inloggning hos Vercel** (Vercel Authentication med Standard Protection). Produktionsadressen är öppen. Utan skyddet svarar varje gammal deploy för vem som helst som har adressen, med den gamla koden: så låg bygget från före säkerhetsrättningarna kvar öppet samma dag som de driftsattes. Stäng inte av skyddet, för då öppnas alla gamla deployer på en gång. Kontroll: `curl -s -o /dev/null -w "%{http_code}\n" https://<en deploys egen adress>/` ska ge `302` eller `401`, inte `200`. Adresserna står i `vercel ls <projekt>`.

**Vercels Hobby-plan har begränsad lagring för deployer.** Samla ändringar och deploya en gång, och ta bort gamla förhandsversioner: `vercel ls <projekt>` listar dem, `vercel remove <adress>` tar bort en.

## Rollback

- Snabbast: `vercel rollback <adress eller id till en tidigare produktionsdeploy>`. `vercel ls <projekt> --prod` listar dem. Tar någon minut.
- Varaktigt: `git revert` på `main`, sedan deploy som vanligt. En rollback i Vercel ändras nämligen tillbaka vid nästa `vercel --prod`.
- En rollback förbi en säkerhetsrättning tar tillbaka bristerna den rättade. Gör det bara i nödfall, och rätta framåt så snart det går. Vilka rättningar som kom när står i `docs/security-review-2026-10.md`.

## Loggar

- Vercel: `vercel logs <produktionsadressen>`, eller projektets Logs-flik. Hobby sparar loggar en kort tid; det som ska finnas kvar måste sparas direkt.
- Egen server: `journalctl -u caia -f`.

Loggen har inga adresser, lösenord eller inloggningsbevis: användare står med sitt id och besökare med en hashad adress. Hashen är en pseudonym, inte en anonymisering: den som har `CAIA_SECRET_KEY` kan räkna fram vilken adress den står för. Vid fel kan loggen innehålla stycken ur en analys (ett drivarnamn i ett kalkylfel, modelltjänstens felsvar, Supabases felsvar), så behandla den som analyserna.

Det som är värt att leta efter:

| Rad | Betyder |
|---|---|
| `CAIA: kommunprofil <slug> (<namn>), <sökväg>` | Uppstart. Fel kommun här betyder fel `CAIA_KOMMUN`. |
| `CAIA_ALLOWED_EMAILS är inte satt` | Ingen släpps in. |
| `Refused account <användar-id> (domain '<domän>'): ...` | Någon loggade in men står inte i listan, är ett anonymt konto, eller har en obekräftad adress i en tillåten domän. Hela adressen loggas inte. |
| `Refused token from ip <hash>: <skäl>` | Ett anrop med ett inloggningsbevis som inte godtogs: utgånget, fel signatur, fel algoritm eller inget alls. Adressen är hashad. Många från samma hash på kort tid är någon som provar. |
| `Model call <väg> by user <id>` / `by ip <hash>` | Ett anrop till ett modellsteg som släpptes förbi anropsgränsen. Det är den här raden som visar vilket konto som har förbrukat vad; id:t slås upp i Supabase under Authentication, Users. Raden skrivs innan innehållet granskas, så ett anrop som sedan avvisas för sin form (svarskod 400 på raden intill) står med utan att ha kostat något. |
| `Rate limit hit on '<väg>' by user <id>` / `by ip <hash>` | Någon nådde anropsgränsen. |
| `model usage {"step": ..., "usd": ...}` | Ett modellanrop: steg, modell, resonemangsnivå, tokens in, ut och i cache, sekunder, stop_reason och uppskattad kostnad i USD till listpris (`PRICES` i `api_client.py`). En rad per anrop, även när steget sedan fallerar. Raden `Model call` intill säger vem som körde. |
| `Key list could not be fetched` / `Token from ip <hash> not checked` | Supabases lista över signeringsnycklar gick inte att hämta. Inloggningar kontrolleras under tiden med de nycklar CAIA läst den senaste timmen; övriga får beskedet att inloggningen inte kan kontrolleras just nu. Går över av sig självt när Supabase svarar. |
| `Wrong password, ip <hash>` / `Login blocked after repeated wrong passwords` | Lösenordsläget: fel lösenord, och spärren efter fem fel. |
| `CAIA: VARNING: CAIA_DEV_OPEN=1` eller `CAIA_INSECURE_COOKIE=1` | En inställning för lokal provkörning står kvar. Ska aldrig synas i produktionen. |
| `CAIA: VARNING: SUPABASE_URL börjar med http://` / `CAIA_PASSWORD är kortare än 12 tecken` | En inställning som försvagar skyddet. Rätta den. |
| `kommunprofil error [<fel-id>] on <route>` | En fil i kommunprofilen gick inte att läsa; sökvägen står här, användaren ser bara fel-id:t. |
| `step failed [<fel-id>] on <route>` | Oväntat fel; fel-id:t är det användaren ser. Stacktrace följer. |
| `step failed on <route>: ...` | Känt fel: modelltjänsten, nyckeln, krediterna, kommunprofilen. |
| `deterministic kalkyl failed, falling back to LLM` / `kalkyl extraction found no JSON` | CAIA:s beräkning kunde inte köras; språkmodellen räknade. Resultatet är märkt, men är det vanligt har något ändrats i en prompt eller i modellens beteende. |
| `evidens plan: no drivers parsed` | Baslinjen gick inte att dela per drivare; steg 4 kördes som ett anrop (långsammare, nära tidsgränsen). |
| `källmarkering failed` | Källkontrollen kraschade; kalkylen gäller ändå, avsnittet Talens ursprung säger att kontrollen fallerade. |

## Gränser

| Gräns | Värde | Var |
|---|---|---|
| Modellanrop | 20 per minut, 150 per dygn, per serverprocess. Per användare med Supabase, per adress i lösenordsläge | `CAIA_RATE_LIMIT_PER_MIN`, `CAIA_RATE_LIMIT_PER_DAY` |
| Tid per modellanrop | 280 s, ett omförsök bara vid snabba fel | `REQUEST_TIMEOUT_S` i `api_client.py` |
| Tid per funktion på Vercel | 300 s (modellanropet själv 280 s, `REQUEST_TIMEOUT_S`) | `vercel.json` |
| Storlek per anrop | 2 MB, 120 turer, 12 drivare | `app.py` |
| Text per analys | 400 000 tecken totalt, 100 000 per tur, och 100 000 för delresultaten i steg 4 tillsammans (drygt dubbla den största riktiga analysen) | `MAX_HISTORY_CHARS`, `MAX_TURN_CHARS`, `MAX_PARTS_CHARS` i `app.py` |
| Anrop som inte når en modell (sparade rapporter, planen för steg 4, parameterlistan) | 30 per minut, 600 per dygn och användare, räknat för sig | `REPORT_RATE_PER_MIN`, `REPORT_RATE_PER_DAY` i `app.py` |
| En sparad rapport | 300 000 tecken och 600 000 byte, i appen och i tabellen | `REPORT_MAX_CHARS` i `app.py`, `deploy/reports.sql` |
| Inloggningsförsök (lösenordsläge) | 5 per IP på tio minuter | `app.py` |
| Kostnad | typiskt 2–3 USD per analys | se [API.md](API.md#kostnad) |

**Var kostnaden syns.** Varje modellanrop mäter sig själv: i produktionen som raden `model usage` i Vercels logg (tabellen under Loggar), och i `tools/run_batch.py` som `usage.jsonl` i varje analys katalog under `--out` plus en summering per steg och totalt i slutet av körningen (även i `run.log`). Mät kostnaden på körningar som ändå görs, referenskörningar, mätningar efter en ändring, workshoppar, och kör inga analyser bara för att mäta den. Beloppen är listpris, inte fakturan; OpenRouters aktivitetssida är facit.

## Nycklar och hemligheter

| Nyckel | Var den bor | Byta |
|---|---|---|
| `OPENROUTER_API_KEY` | Vercel (Production och Preview) | Skapa en ny nyckel hos OpenRouter med samma kreditgräns, byt värdet i Vercel, deploya om, radera den gamla hos OpenRouter. |
| `SUPABASE_ANON_KEY` | Vercel | Publik, syns i sidan. Byts bara om Supabase-projektet byter nycklar, och då för AIda samtidigt. |
| `SUPABASE_JWT_SECRET` | Inte hos CAIA | Borttagen ur CAIA:s Vercel-projekt 2026-10-07. Projektet signerar inloggningar med ES256, som CAIA kontrollerar mot Supabases publika nycklar, så hemligheten behövdes inte och gav bara ett ställe till där den kunde läcka. AIda har den kvar. |
| `CAIA_SECRET_KEY` | Vercel / `caia.env` | Byte loggar ut alla i lösenordsläge, och ger nya hashar för adresserna i loggen. |
| `CAIA_PASSWORD` | `caia.env` | Byte loggar ut alla. |

En variabel som ändras i Vercel gäller först efter nästa deploy. Skriv aldrig ett nyckelvärde i ett ärende, en chatt eller ett commit-meddelande.

## Användare

Med Supabase:

- **Släppa in någon, två ställen:** lägg till adressen (eller hela domänen som `@kommun.se`) i `CAIA_ALLOWED_EMAILS` och deploya om, och lägg samma post i databasens lista, i Supabases SQL Editor: `insert into caia.allowed (entry) values ('anna.andersson@konsult.se');` (små bokstäver). Den första listan avgör vem appen släpper in. Den andra avgör vem som får spara i tabellen, som också nås direkt genom Supabases API, förbi appen. Står kontot bara i den första kan det köra analyser men inte spara dem. Se listan: `select entry from caia.allowed;`. Ta bort någon: stryk posten på båda ställena.
- **Kontot** skapas i Supabase (Authentication, Users, Add user), eller av användaren själv om registrering är på.
- **Har projektet registrering påslagen** (till exempel för ett annat verktyg som delar det) är det listan som avgör vem som kommer in, inte om man kan skapa ett konto.
- **Ett konto utanför listan** får beskedet att be den som driftar CAIA lägga till adressen. Står en adress i `CAIA_CONTACT` säger beskedet vart.
- **Workshop med deltagare utanför listan:** öppna inte listan för deras domäner. Sätt upp en egen instans i lösenordsläge (INSTALL.md, steg 4B) med ett gemensamt lösenord, `CAIA_RATE_LIMIT_PER_MIN` och `_PER_DAY` höjda och `CAIA_LOGIN_FAILURES_PER_WINDOW=50`, eftersom hela rummet delar en nätadress. Byt lösenordet mot ett slumpat när workshoppen är slut. Öppna domäner kräver bekräftelsemejl, och Supabases inbyggda utskick klarar bara några mejl i timmen.
- **Bekräftad adress:** en domän i listan släpper bara in konton vars adress inte är markerad som obekräftad. Det egentliga skyddet är att Supabase-projektet kräver bekräftelse via e-post; kontrollen står i DEPLOY.md under smoke-testet.
- **Vad en domän i listan betyder:** den som kan ta emot mejl på en adress i domänen kan skaffa ett konto och köra analyser. Registreringen är öppen och den som registrerar väljer lösenordet, så ett konto kan också förberedas för en adress man inte äger: det går inte att logga in på förrän någon öppnat länken i bekräftelsemejlet, men då går det. Vill ni inte ha det så, lista namngivna adresser i stället för domänen.
- **Bekräftelsemejlet** pekar tillbaka till sidan där kontot skapades, under förutsättning att adressen finns bland Supabases Redirect URLs (Authentication, URL Configuration). Saknas den hamnar användaren på projektets Site URL, som är AIda.

## Säkerhetskopior

Det enda CAIA lagrar är tabellen `reports` i Supabase: färdiga rapporter per användare. Vilken säkerhetskopiering Supabase själv gör beror på projektets plan; kontrollera den under Database, Backups. En egen kopia tar ni med Table Editor, `reports`, Export to CSV, eller `pg_dump` med projektets anslutningssträng. Förlorade rapporter går att köra om; det som går förlorat är historiken.

## Namnbytet från Zaid (oktober 2026)

Verktyget hette Zaid till 2026-10-08. Det här bytte namn då, och det är vad en installation från tiden före behöver ändra:

| Förut | Nu |
|---|---|
| Paketet `next/src/zaid`, `from zaid...` | `next/src/caia`, `from caia...` |
| Inställningarna `ZAID_*` | `CAIA_*`, samma värden. De gamla namnen läses inte längre. |
| Loggrader som börjar `Zaid:` | `CAIA:` |
| Databasens schema `zaid` (`zaid.allowed`, `zaid.account_allowed()`) | `caia`. Kör `next/deploy/migrations/2026-10-rename-schema-caia.sql` en gång. Tabellen `public.reports` och dess rader rörs inte. |
| Egen server: `/opt/zaid`, `/etc/zaid/zaid.env`, tjänsten `zaid` | `/opt/caia`, `/etc/caia/caia.env`, tjänsten `caia` (INSTALL.md) |

Ordningen spelar roll, eftersom de gamla inställningarna inte läses längre:

1. Lägg in varje `CAIA_*` med samma värde som motsvarande `ZAID_*`, i alla miljöer där den gamla finns. Saknas `CAIA_KOMMUN` startar appen inte, och saknas `CAIA_ALLOWED_EMAILS` släpps ingen in. Gränserna (`CAIA_RATE_LIMIT_PER_MIN`, `CAIA_RATE_LIMIT_PER_DAY`, `CAIA_TRUSTED_PROXIES`) faller däremot tyst tillbaka på sina standardvärden.
2. Kör migreringen. Den kan köras när som helst: appen namnger aldrig schemat, bara databasens egen regel gör det.
3. Driftsätt den nya koden och kör smoke-testet i DEPLOY.md.
4. Ta bort `ZAID_*` först när det är kontrollerat.

Inloggningen sparas per adress i webbläsaren, så den som var inloggad på den gamla adressen loggar in en gång till på den nya. Sparade analyser ligger i databasen och följer med kontot.

Det som står kvar som Zaid är historik: rapporter som sparades före bytet (bilagans rad "skriven av Zaids kalkylmotor"), de daterade granskningarna och de två äldre migreringarna. I Karlstads interna repo gäller det också de första prototyperna och utvecklingsloggen.

## Ändra en prompt, parameterbiblioteket eller en datafil

Agenternas beteende bor i systemprompterna (`next/src/caia/agents/*.py`), i parameterbiblioteket och i datafilerna. Inga enhetstester fångar en ändrad mening där, så sviten har en snubbeltråd: `tests/test_prompt_fingerprints.py` fäller så fort något av det som skickas till en modell ändras. Så gör man:

1. **Före ändringen**, kör referenspaketen och spara resultatet:
   ```
   cd next
   .venv/bin/python tools/run_batch.py tests/reference/*.md --out /tmp/caia-fore --env .env
   ```
   (Fyra paket, omkring 11 USD och en halvtimme. Det fjärde, publika laddpunkter, är en ren möjliggörare och prövar att en sådan räknas som kedja och inte som noll.)
2. Gör ändringen.
3. Kör samma paket igen till `/tmp/caia-efter`.
4. Jämför: `.venv/bin/python tools/compare_runs.py /tmp/caia-fore /tmp/caia-efter`. Den visar nettoeffekten och spannet per paket, och märker körningar där språkmodellen räknade själv. Läs rapporterna där talen flyttat sig; en körning skiljer sig alltid lite från en annan, så leta efter flyttar som ändringen förklarar.
   Rör ändringen steg 3, 4 eller 5, eller `src/caia/godkant.py`: kör också `.venv/bin/python tools/check_godkant.py /tmp/caia-efter`. Den jämför talen beräkningen fick med det som godkändes, som sidan gör, och skriver ut varje märkt tal. Ett märkt tal är en felläsning (utläsningens egen anteckning brukar visa det) eller en falsk varning, och en falsk varning ska rättas innan ändringen går ut. `--power` mäter också hur mycket jämförelsen fångar. Mätningen från oktober 2026 står i METOD.md.
   Skriver du en regel utifrån några få analyser passar den dem. Pröva den också på sparade analyser som inte användes när den skrevs, och läs de godkända stegen för hand där talen skiljer sig. Reglerna för utläsningen i steg 5 gav rätt svar varje gång på de fyra analyser de skrevs på, och 31 av 36 inom fem procent på fjorton andra (2026-10-13, METOD.md under *Kända begränsningar*).
5. Är du nöjd, spara nya fingeravtryck och committa dem med ändringen:
   ```
   UPDATE_PROMPT_FINGERPRINTS=1 .venv/bin/python -m pytest tests/test_prompt_fingerprints.py
   ```

Fingeravtrycken finns för båda analyslägena; nycklar som börjar med `uppfoljning/` gäller uppföljningsläget. Fäller testet bara på sådana nycklar har bara uppföljningsläget ändrats, och då är det uppföljningspaket (nästa avsnitt) som ska köras före och efter, inte referenspaketen.

Samma gäller när en ny kommunprofil tas i drift: kör referenspaketen på den och läs rapporterna innan användarna släpps in.

### Mäta spridningen per steg

Två körningar av samma åtgärd ger olika huvudsiffror. För att se vilket steg spridningen kommer från: håll allt före steget fast och kör bara det steget flera gånger, följt av resten av kedjan till och med kalkylen. `tools/replay_step.py` gör det på en sparad analys från `run_batch` (en paketkatalog med `history.json`):

```
cd next
.venv/bin/python tools/replay_step.py /tmp/caia-fore/01-tjanstebilar evidens --n 5 --estimate
CAIA_KOMMUN=<profil> .venv/bin/python tools/replay_step.py /tmp/caia-fore/01-tjanstebilar evidens --n 5 --parallel 3 --out /tmp/caia-spridning-evidens --env .env
```

Steget är ett av `intake`, `emap`, `baslinje`, `evidens`, `kalkyl` (och `qa`, `rapport` med `--through`). Varje omkörning hamnar i `<out>/<paket>-rN/` i `run_batch`s format, med `usage.jsonl` per omkörning och `summary.jsonl` med huvudsiffra (net, terr, cons) och kostnad. Stegen före klippet är kopior av den sparade analysen, och `replay.json` har en kontrollsumma av samtalet fram till steget. Körningen använder `run_batch`s egna funktioner mot appens adresser, alltså samma anrop som sidan gör. På slutet skrivs spridningen ut; samma tabell går att få för vilka körningar som helst:

```
.venv/bin/python tools/compare_runs.py --spread /tmp/caia-spridning-evidens
```

Den ger min, median, max och max/min per paket. Jämför steg mot steg på samma paket: det steg vars omkörningar sprider mest ska ses över först. Kalkylen ensam (steg 5) gav 135-138 ton på åtta omkörningar i oktober 2026, så den är golvet.

Att köra evidens och kalkyl efter varje omkörning är dyrt, och för steg 1 till 3 behövs det oftast inte: stegets eget svar visar var omkörningarna går isär. Stanna efter steget (`--through baslinje` för intag, utsläppskällor och baslinje; intaget till och med baslinjen så att omfattningen det hittar på syns i ton) och läs svaren med stegjämföraren:

```
.venv/bin/python tools/compare_runs.py --step intake /tmp/caia-spridning-intag
.venv/bin/python tools/compare_runs.py --step emap /tmp/caia-fore /tmp/caia-fore2 --paket 02-aterbruk
.venv/bin/python tools/compare_runs.py --step baslinje /tmp/caia-spridning-baslinje
```

Varje katalog med stegets fil (`intake.md`, `emap.md`, `baslinje.md`) är en körning; `-rN` på slutet räknas som samma paket, och `--paket` väljer ett. Inga modellanrop, koden står i `tools/step_readout.py`.

- **emap** (utsläppskällor): antal källor per körning, källorna matchade på namn och inte nummer (samma källa kan heta drivare 2 ena gången och drivare 4 nästa), vilka som kommer och går, och mekanism, utsläppstyp, locus och sektor där de skiljer. Två källor som aldrig är med samtidigt men liknar varandra pekas ut ("kanske samma, läs namnen"): en samlad materialkälla mot tre materialkategorier jämförs inte tal mot tal.
- **baslinje**: per källa nulägesår, A0, EF0 och trenderna (g_A och g_EF, låg, medel, hög) med min, median, max och max/min, enheterna där de skiljer, och e0 (A0 × EF0) och e2030 (med medeltrenderna, motorns formel) i ton CO2e. Raderna under källorna säger var talet inte är ett rent tal: ett spann där ett tal begärs, en trend i två faser ("0 % till 2026, sedan -17 %/år") som motorn inte kan räkna med, ett prefix på enheten som inte är omräknat. Summan av e0 per körning är ingen baslinje (källor kan överlappa); jämför källa mot källa.
- **intake**: antal frågerundor och profiler, frågorna matchade på ord, och talen i profilens fält *Omfattning:* med ordet efter, spann behållna och andelar på egen rad ("5-10 % av bilarna" är inte 5 bilar). Profiler från före 2026-10-13 har inget sådant fält.
- En åtgärd i två profiler numrerar drivarna från 1 i varje; avläsningen skriver då "P2 nr 1" för profil 2.

Tid, svarslängd och kostnad per analys, likadant i varje körning:

```
.venv/bin/python tools/compare_runs.py --tid /tmp/caia-fore /tmp/caia-efter [--paket 04-laddpunkter]
```

Den läser `run.log` (varje anrop till sidan, intag per runda, evidensdelarna och sammanslagningen var för sig; raden "evidens Xs" efter dem är väggtid och räknas inte) och `usage.jsonl` i analysens katalog. Per analys: längsta anrop per steg, flaggat NÄRA från 240 s, ÖVER VÅR GRÄNS från 280 s (`REQUEST_TIMEOUT_S`) och ÖVER VERCELS GRÄNS från `maxDuration` i `vercel.json`; kalkylens modellanrop summerade (TVÅ MODELLANROP när reserven körde i samma anrop, S29); sammanslagningens `output` mot taket 26 000 (I TAKET vid `stop_reason` max_tokens); kostnaden mot 3,9 USD. Sist längsta anrop per steg och kostnad min, median och max över alla analyser. En `run.log` som återanvänts läses från den sista körningen av analysen. `usage.jsonl` finns bara i körningar från 2026-10-13 kväll och senare.

`--estimate` skriver ut vad omkörningarna kostar enligt analysens egen `usage.jsonl` och stannar där, utan något modellanrop. Ur workshopens 334 anrop (oktober 2026, listpris) kostar en omkörning ungefär: kalkyl 0,20 USD, evidens med kalkyl 2,65 USD (evidensdelarna 0,31 USD per drivare, sammanslagningen 0,56), baslinje med evidens och kalkyl 2,90 USD, intag och allt till kalkylen 3,20 USD. Det är evidenssteget som kostar, även när det är baslinjen som mäts, eftersom huvudsiffran kräver att evidens körs om efter den. Kontrollera potten före en betald mätning.

## Följa upp genomförda insatser

En genomförd insats (till exempel en som fått driftsmedel) analyseras i uppföljningsläget. På sidan väljer användaren *Uppföljning* innan första meddelandet. För många insatser på en gång, skriv ett faktapaket per insats och kör dem utan webbläsare:

```
cd next
CAIA_KOMMUN=<profil> .venv/bin/python tools/run_batch.py paket/*.md --mode uppfoljning --parallel 3 --out /tmp/caia-uppfoljning --env .env
```

- **Ett paket per insats, inte per bidragsår.** En insats som fått pengar flera år analyseras som en helhet; ange belopp per år i paketet, så fördelar kalkylen nyttan per bidragsår.
- **Paketet bär fakta, inte metod.** Vad som planerades, vad som genomfördes, belopp per år, uppmätta utfall och hur de mättes, annan finansiering. Hur det ska läsas (jämförelsen "utan just de här pengarna", avklingning, attribution) står i verktyget, `next/src/caia/agents/uppfoljning.py`. Skriv inte in läsanvisningar i paketet; då testar analysen paketet i stället för insatsen.
- **Kör varje paket två gånger** och jämför med `tools/compare_runs.py`. Två körningar av samma paket skiljer sig, och en insats där de skiljer mycket behöver bättre underlag snarare än en tredje körning.
- Läs kalkylens avsnitt *Bärande antaganden* först. En rad som börjar med "OBS: bärande antagande utan källa" säger vilket tal resultatet hänger på och vad som skulle behöva mätas.

## Byta modell

Modell och resonemangsnivå per steg står i `AGENT_MODELS` i `next/src/caia/api_client.py`. Ett steg som har en annan nivå i uppföljningsläget står dessutom i `EFFORT_UPPFOLJNING` (tom sedan 2026-11-08, då utläsningen i steg 5 fick hög nivå även där). Ett byte är inte bara ett id: kontrollera att den nya modellen tar adaptivt resonemang (`ADAPTIVE_MODELS`) och att `THINKING_HEADROOM` räcker, eftersom tänk-tokens räknas mot taket och en modell som tänker längre annars svarar tomt. Den nya modellen behöver också en rad i `PRICES` med priset från `https://openrouter.ai/api/v1/models`, annars loggas dess anrop utan kostnad. Kör referenspaketen före och efter som ovan. `tests/test_thinking_config.py` kontrollerar formen och `tests/test_usage.py` att varje modell har ett pris.

## Uppdatera beroenden

`next/requirements.txt` har exakta versioner. Så uppdaterar man, i en ny venv:

```
pip install -U flask anthropic 'PyJWT[crypto]'
pip install -r requirements-dev.txt   # för pytest
python -m pytest -q
pip freeze
```

Skriv tillbaka `pip freeze` till `requirements.txt` utan testpaketen (de står i `requirements-dev.txt`). Kör sedan en hel analys på en förhandsversion innan produktionen: anthropic-biblioteket har bytt huvudversion förut utan att testerna märkte det.

### Bibliotek i sidan

Sidan hämtar tre bibliotek från jsDelivr i användarens webbläsare: marked (gör text av modellens markdown), DOMPurify (tar bort allt ur den texten som inte står på sidans lista) och supabase-js (inloggningen). Vilken fil och vilken kontrollsumma står på ett ställe, `PAGE_LIBS` i `next/src/caia/web/app.py`. Sidans skripttaggar och dess säkerhetspolicy skrivs därifrån, och policyn släpper bara in just de tre filerna.

`clientlibs/package.json` räknar upp samma versioner. Ingenting installeras därifrån; filen finns för att Dependabot ska föreslå en uppdatering när ett av biblioteken får en ny version. Förslaget fäller testerna tills `PAGE_LIBS` har samma version. Så uppdaterar man:

1. Byt version i adressen i `PAGE_LIBS` och i `clientlibs/package.json`.
2. Räkna ut filens kontrollsumma och skriv in den: `curl -s <adressen> | openssl dgst -sha384 -binary | openssl base64 -A`, med `sha384-` framför.
3. Kör testerna. Öppna sedan sidan i en webbläsare, kör en analys till en rapport och se att tabeller, listor och länkar ser ut som förut. Ett bibliotek som tolkar text annorlunda märks där, inte i testerna.

DOMPurify är det som håller modellens text från att köra kod i sidan, så ta dess uppdateringar först. Läget 2026-10-07: DOMPurify 3.4.16 (uppdaterad den dagen), marked 14.1.3 och supabase-js 2.45.4 (båda från 2024).

## Felsökning

| Symptom | Trolig orsak |
|---|---|
| Appen startar inte, loggen säger `Ingen kommunprofil vald` | `CAIA_KOMMUN` eller `CAIA_KOMMUN_DIR` saknas. |
| Alla får "Kontot saknar behörighet" | `CAIA_ALLOWED_EMAILS` saknas eller har fel domän. |
| "OpenRouter godtog inte nyckeln" | Fel eller raderad `OPENROUTER_API_KEY`. |
| "slut på krediter eller har nått sin gräns" | Kreditgränsen på nyckeln eller kontot. |
| Steg 4 eller 5 avbryts efter fem minuter med 504 | Modellen var långsam; kör steget igen. Återkommer det, se om `evidens plan: no drivers parsed` står i loggen. |
| "Kommunprofilen går inte att läsa (fel-id ...)" | Sök fel-id:t i loggen; raden säger vilken fil och varför. Vanligast: en datafil sparad som Latin-1. Konvertera enligt [DATAFORMAT.md](DATAFORMAT.md). |
| Sparade analyser syns inte | Supabase nås inte (loggen säger `Supabase ... unreachable`) eller tabellen saknar `grant` (kör `deploy/reports.sql`). |
| "Analysen kunde inte sparas: databasen släpper inte in kontot" | Kontot står i `CAIA_ALLOWED_EMAILS` men inte i `caia.allowed`, eller adressen är inte bekräftad i Supabase. Se Användare ovan. |
| "Inloggningen kan inte kontrolleras just nu" | Supabases nyckellista gick inte att hämta. CAIA försöker igen efter 30 sekunder och det går över av sig självt; håller det i sig, se Supabases driftstatus. Den som redan var inloggad på samma instans märker inget under den första timmen. |
| En rapport, eller en del av den, visas som rå text med tecknen `#` och `*` kvar | Texten gick inte att tolka (till exempel tusentals nästlade citat). Sidan visar den då som den är i stället för att avbryta steget. Rapportens fil är densamma. |
| Appen startar inte, loggen säger `SUPABASE_ANON_KEY är en hemlig nyckel` | Fel nyckel i inställningen. Sätt den publika och byt ut den hemliga i Supabase, eftersom den kan ha hunnit visas. |
