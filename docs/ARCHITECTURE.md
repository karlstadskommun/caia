# Arkitektur

CAIA (Climate Action Impact Analysis) är en Flask-app (`next/`) utan egen databas och utan kö. Servern är tillståndslös: webbläsaren håller hela analysen och skickar med den i varje anrop. Allt tungt arbete är anrop till Claude-modellerna via OpenRouter, och själva utsläppsberäkningen är vanlig Python.

## Flödet i en analys

```
användaren beskriver åtgärden
        │
 1 intake      Opus 5.5    frågar tills åtgärdsprofilen är klar          ── grind: godkänn profilen
 2 emap        Sonnet 5.5  pekar ut utsläppskällorna, klassar åtgärden ── grind: godkänn utsläppskällorna
 3 baslinje    Sonnet 5.5  baslinje och BAU per drivare                  ── grind: godkänn baslinjen
 4 evidens     Opus 5.5    antaganden min/med/max + klimatfaktorer       ── grind: godkänn antagandena
     plan      (ingen modell) läser drivarna ur baslinjen, annars ur steg 2 (Utsläppskällor)
     part ×N   Opus 5.5    ett anrop per drivare, parallellt
     merge     Opus 5.5    ser alla drivare, rättar dubbelräkning
 5 kalkyl      Sonnet 5.5  läser ut talen som JSON  →  caia.calc räknar
               (reserv: Sonnet 5.5 räknar själv, märkt deterministic:false)
 6 qa          Opus 5.5    granskar kalkylen (chain-of-verification)
 7 rapport     Sonnet 5.5  beslutsunderlag
               (den tekniska bilagan skrivs inte av modellen: kalkylmotorns
                bilaga ur steg 5 läggs sist, oförändrad; sidan och
                run_batch lägger sedan till avsnittet Talens ursprung
                ur kalkylsvaret)
```

Sidan har fyra grindar, efter steg 1, 2, 3 och 4. När användaren godkänt antagandena körs steg 5, 6 och 7 i en följd utan stopp, och rapporten sparas när den är klar. Grindarna finns på ett ställe i sidans JavaScript (`GATES` i `web/app.py`). De är sidans val: API:t tvingar ingen ordning och inga stopp.

Mellan två steg lägger webbläsaren till en användartur som säger att förra steget är godkänt. De raderna finns på ett ställe, `caia.pipeline.BRIDGE`, och används av sidan, `tools/run_batch.py` och testerna. Vid en grind kan användaren skriva en rättelse i stället för att godkänna; då körs samma steg om med rättelsen i historiken. Misslyckas omkörningen tas rättelsen ur historiken igen, och panelen visar den tidigare versionen med en ruta om vad som gick fel.

Analysen körs i ett av två lägen, som användaren väljer innan första meddelandet och som sedan är låst: *förväntad potential* (standard, en planerad åtgärd) eller *uppföljning* (en genomförd insats). Läget följer med i varje anrop. Stegen och sidan är desamma; i uppföljningsläget får varje steg ett block med metodregler sist i sin systemprompt, och kalkylen redovisar realiserat, återstående och nytta per bidragsår. Potentialläget får exakt samma promptar som innan läget fanns.

Steg 4 är uppdelat så att varje HTTP-anrop rymmer högst ett modellanrop. Ett helt evidenssteg tog 163 till 222 sekunder i ett anrop, nära Vercels gräns på 300. `plan` kostar inget; `part` körs en gång per drivare samtidigt; `merge` fogar ihop och får rätta ett fält i en drivare med en rad på formen `Drivare N | parameter | Fältetikett: nytt värde` (till exempel `Drivare 3 | - | Overlap_faktor: 0.0`), eller skriva om ett helt drivarblock. En rättelse som inte går att läsa fäller steget i stället för att försvinna. `/api/evidens` (ett anrop) finns kvar som reserv när baslinjen inte går att dela i drivare.

## Moduler (`next/src/caia/`)

| Modul | Ansvar |
|---|---|
| `web/app.py` | Flask-appen: inloggning, anropsgränser, alla routes, och sidan (HTML, CSS och JavaScript i en mall). Sidan driver pipelinen: den anropar stegen i ordning, visar grindarna och sparar rapporten. |
| `pipeline.py` | Stegens ordning och överlämningsraderna. |
| `mode.py` | Analysläget: `potential` eller `uppfoljning`. Saknat läge är potential, okänt läge vägras. |
| `agents/*.py` | Ett steg var: systemprompt och ett `complete()`-anrop. `evidens_split.py` har uppdelningen i plan/part/merge och läsningen av merge-rättelser. `kalkyl_extract.py` ber modellen om JSON till kalkylen. `uppfoljning.py` har uppföljningslägets metodregler och vad varje steg gör annorlunda; `for_mode` lägger blocket sist i stegets prompt och lämnar potentialpromptarna orörda. |
| `api_client.py` | Modell och resonemangsnivå per steg (`AGENT_MODELS`, och `EFFORT_UPPFOLJNING` för steg som har en annan nivå i uppföljningsläget), tidsgräns (280 s, under Vercels 300), ett omförsök vid snabba fel och bruten anslutning (aldrig efter en timeout), kontroll att ingen prompt skickas med en oifylld platshållare (som `@@ORT@@`) kvar, och en loggrad per anrop med tokens, sekunder och uppskattad kostnad (`PRICES`), som också går till lyssnarna i `USAGE_LISTENERS` (`tools/run_batch.py` skriver dem till `usage.jsonl`). |
| `calc/schema.py` | Datamodellen för kalkylen (`CalcModel`, `Driver`, `Ramp`, `Grant`). Vägrar värden ingen läsning av metoden tillåter (andel under -100 %, faktorer utanför 0–2, attribution utanför 0–1, NaN). Fälten för attribution, avklingning (`ramp.half_life`), andel av startåret, engångsposter (`kind: "engång"`) och bidragsår har neutrala standardvärden, så en kalkyl utan dem räknas som förut. |
| `calc/engine.py` | Den deterministiska beräkningen: utsläppsminskning per drivare, scenario (min/med/max) och år, totaler, medel per år (2026–2030, `AVG_WINDOW`, i potentialläget; startår till målår i uppföljningsläget), ackumulerat till målåret, och varningar. I uppföljningsläget också realiserat och återstående (`followup_year`) och fördelningen per bidragsår (`allocate`). `bearing` prövar varje parameter med spann en i taget och flaggar bärande antaganden utan källa och max-scenarier som kräver alla ytterlägen samtidigt; det ändrar inga tal. `render_appendix` skriver rapportens tekniska bilaga ur samma tal som gav resultatet: indata, en rad per år och scenario med varje mellansteg, och summeringen. Inga modellanrop, ingen I/O. |
| `appendix.py` | Hittar kalkylstegets text i historiken (raden före `BRIDGE['kalkyl']`), kopierar motorns bilaga därifrån till rapporten och klipper bort en bilaga som rapportmodellen ändå skrivit. Räknade språkmodellen kalkylen följer kalkylstegets text med, märkt som okontrollerad. |
| `kallmarkering.py` | Kontrollerar varje indatatal mot parameterbiblioteket och kommunens data, och skriver avsnittet *Talens ursprung*. |
| `godkant.py` | Jämför talen beräkningen fick med baslinjen och antagandena som godkändes i steg 3 och 4 (säkerhetsgranskningen S21). Det som avviker märks i *Talens ursprung*. |
| `data/parameters.py` | Läser kommunprofilens parameterbibliotek och datafiler och bygger datakontexten som agenterna får. Bara sex källor läses (`READ_SOURCES`). |
| `kommun.py` | Kommunprofilen: namn, ort, klimatplan, text om kommunen, bibliotek och data. Byter platshållare som `@@ORT@@` i prompterna. `python -m caia.kommun` skriver ut vad en profil innehåller. |
| `evidence.py`, `profiles.py` | Läser modellens text (evidens, åtgärdsprofiler) till strukturer som sidan visar. |

`next/tools/` har sju verktyg: `devserver.py` (sidan med låtsassvar, inga modellanrop), `run_batch.py` (kör hela pipelinen utan webbläsare på ett eller flera paket, `--mode uppfoljning` för uppföljning, `--parallel N` för flera paket samtidigt), `replay_step.py` (kör ett steg i en sparad analys om flera gånger på exakt samma underlag, för att se vilket steg som gör att två körningar skiljer sig), `compare_runs.py` (jämför två körningar; `--step` och `--tid` läser stegens egna svar, tid och kostnad med hjälp av modulen `step_readout.py`), `check_godkant.py` (kör jämförelsen med det som godkändes på sparade körningar), `metod_html.py` (gör `docs/METOD.html` ur METOD.md) och `credit_routes.py` (låter batchkörningarna använda flera Anthropic-nycklar i tur och ordning, med OpenRouter sist; webbappen använder den aldrig). `next/api/index.py` är Vercels ingång.

## Kommunprofilen

Allt som gör en installation till en viss kommun ligger i en mapp: `kommun.toml`, `parameters_library.md` och `data/`. Koden innehåller inget kommunnamn utom ursprungsraden på startsidan. `tests/test_kommunprofil.py` kör hela kedjan på exempelprofilen och fäller om ordet Karlstad når en modell eller sidan. Profilen väljs med `CAIA_KOMMUN` (en profil i repot) eller `CAIA_KOMMUN_DIR` (en mapp utanför). Utan någon av dem startar appen inte. Ny kommun: [next/INSTALL.md](../next/INSTALL.md) steg 2 och [DATAFORMAT.md](DATAFORMAT.md).

## Externa tjänster

| Tjänst | Används till | Kostnad |
|---|---|---|
| **OpenRouter** → Claude Opus 5.5 och Claude Sonnet 5.5 (i Karlstads installation via OpenRouters EU-ingång till Google Vertex AI i EU) | Alla modellanrop | Per token. Listpris hos Anthropic: Opus 5.5 4 USD per miljon tokens in och 20 USD ut, Sonnet 5.5 2 respektive 10 USD. En analys med två drivare är nio anrop och kostar typiskt 2–3 USD, tak omkring 4 USD. Varje extra drivare lägger till ett Opus-anrop (omkring 0,5 USD), och varje omkörning vid en grind kostar steget en gång till. |
| **Supabase** | Inloggning (e-post och lösenord) och tabellen `reports` för sparade analyser | Gratisnivån räcker för en kommun. Karlstad delar projekt med AIda. |
| **Vercel** | Hosting, Python-funktion med 300 s tak (Fluid compute), region arn1 (Stockholm) | Beror på planen. Gratisplanen Hobby gäller bara icke-kommersiellt personligt bruk, så en kommun i drift behöver en betald plan eller egen server, se [next/DEPLOY.md](../next/DEPLOY.md) och [next/INSTALL.md](../next/INSTALL.md). |
| **jsDelivr, Google Fonts** | Webbläsaren hämtar marked, DOMPurify, supabase-js och typsnittet Roboto | Gratis. Användarens IP-adress når dessa tjänster. |

Allt användaren skriver och allt analysen tar fram går via OpenRouter till leverantören som kör modellerna. Med `CAIA_OPENROUTER_REGION=eu` går anropen via OpenRouters EU-ingång, och i Karlstads installation körs modellerna då hos Google Vertex AI i EU ([next/DEPLOY.md](../next/DEPLOY.md)). Startsidan säger att texten går till en extern leverantör och ber om inga personuppgifter; vad det betyder i praktiken står i [ANVANDARGUIDE.md](ANVANDARGUIDE.md).

Hur talen räknas, steg för steg och utan kod, står i [METOD.md](METOD.md).

## Säkerhet i korthet

- Varje route som når en modell kräver inloggning (Supabase-JWT eller lösenordssession) och räknas mot en gräns: 20 per minut och 150 per dygn, ungefär tio analyser. Gränsen gäller per användare med Supabase och per IP-adress i lösenordsläge. Rapportvägarna, parameterbiblioteket och `evidens/plan` har en egen, rymligare gräns (30 per minut, 600 per dygn). Räknarna finns i processens minne.
- Supabase-bevis kontrolleras i appen: signatur med ES256 mot projektets publika nycklar, utgångstid, mottagare (`authenticated`) och användar-id. Andra algoritmer vägras. HS256 godtas bara om `SUPABASE_JWT_SECRET` är satt. Nyckellistan hämtas om efter fem minuter, och går den inte att hämta svarar appen 503 i stället för att släppa in någon.
- Supabase-konton släpps bara in om adressen står i `CAIA_ALLOWED_EMAILS`, som tar adresser, hela domäner (`@kommun.se`) eller `*`. Ett konto som släpps in via en domän måste ha en bekräftad adress. Anonyma konton släpps aldrig in.
- Varje sparad rapport läses och skrivs med användarens egen token, och radnivåskydd i Supabase gör att man bara ser sina egna (`next/deploy/reports.sql`). Tabellen har dessutom en egen lista över vilka som får spara (`caia.allowed`) och kräver bekräftad adress, så en adress måste stå i båda listorna. Ändringarna från oktober 2026 ligger som migreringar i `next/deploy/migrations/`.
- Anropen har tak: 2 MB per anrop, 120 turer i historiken, 200 000 tecken per tur och 400 000 tecken totalt, 12 drivare per analys.
- Modellens text renderas med marked och rensas med DOMPurify mot en lista över tillåtna element (rubriker, stycken, listor, tabeller, länkar, fetstil och kursiv, kod och citat). Av attributen släpps bara `href`, `align` och `start` igenom, och en länk får bara gå till `https:` eller `mailto:`.
- Sidan skickar en Content-Security-Policy som utgår från att inget är tillåtet. Skriptfiler får bara hämtas från den egna servern och som de tre namngivna biblioteksfilerna från jsDelivr, var och en låst till en version med kontrollsumma (`PAGE_LIBS`: marked 14.1.3, DOMPurify 3.4.17, supabase-js 2.45.4). Skript inne i sidan är tillåtna, eftersom sidans egen kod ligger så; det som hindrar modellens text från att köras är DOMPurify. Sidan får inte visas i en ram på en annan sida, och svar från `/api/` får inte sparas i cache.
- Text från modellen behandlas som data när den går vidare till nästa steg i koden (`calc/schema.py`, `agents/evidens_split.py`), och historikens turer byggs om med bara roll och innehåll innan de når modellen.
- Appen vägrar starta om `SUPABASE_ANON_KEY` är en hemlig nyckel eller om `CAIA_SECRET_KEY` är installationsguidens platshållare, och varnar vid start för öppet utvecklingsläge, osäker kaka, `SUPABASE_URL` utan https och för kort lösenord.
- I lösenordsläge gäller kakan i tolv timmar och slutar gälla när lösenordet byts.
- Dependabot bevakar Python-paketen och sidans bibliotek varje vecka (`.github/dependabot.yml`, `clientlibs/package.json`).

Säkerhetsgranskningen från oktober 2026 och vad som står öppet efter den finns i [security-review-2026-10.md](security-review-2026-10.md).

## Tester

`cd next && .venv/bin/python -m pytest -q` kör omkring 1 950 tester på under en minut utan nätverk (2026-11-10). De täcker kalkylen med handräknade facit, läsningen av modellens text, inloggning och gränser, kommunprofilen, sidans JavaScript (kört i node) och ett fingeravtryck av varje systemprompt i båda analyslägena. Fingeravtrycket fäller testet när en prompt, parameterbiblioteket eller en datafil ändras, så att ingen ändring av vad agenterna får når produktion utan att referensanalyserna körts om. GitHub Actions kör sviten vid varje push till `main` och i varje pull request (`.github/workflows/tests.yml`). `tests/test_e2e.py` kör en riktig analys och är avstängd om inte `RUN_E2E=1`.
