# CAIA

CAIA (Climate Action Impact Analysis) räknar ut klimatnyttan av en kommunal åtgärd. Användaren beskriver åtgärden i en chatt, och CAIA tar fram en åtgärdsprofil, en baslinje, antaganden med källor, en beräkning i ton CO2e per år och en rapport. De fyra första stegen visas för användaren, som godkänner eller rättar innan nästa steg körs; beräkningen, kvalitetsgranskningen och rapporten körs sedan i en följd. Själva räkningen görs av vanlig Python-kod, inte av språkmodellen, och rapporten slutar med ett avsnitt som visar var varje tal kommer ifrån.

CAIA har två analystyper, som väljs innan analysen börjar: *prognos* (potentialläget) för en åtgärd som inte är genomförd än, och *uppföljning* (uppföljningsläget) för en insats som redan är gjord, där frågan är vad just de pengarna faktiskt har gett och vad som återstår.

CAIA är utvecklat av Karlstads kommun inom Klimatneutrala Karlstad 2030, som stöds av Viable Cities. Henric Barkman, processledare på Karlstads kommun, tog fram verktyget: han beställde det och fattade metodbesluten. Koden skrevs med AI-assistenten Demi, som bygger på Claude. Det här är version 1.1.0; den första offentliga versionen var 1.0.0. Verktyget hette Zaid till oktober 2026, och det namnet står kvar på några ställen i dokumentationen.

English: [README.md](README.md).

## Licens

Copyright Karlstads kommun. Licensierat enligt EUPL.

CAIA är fri programvara under [European Union Public Licence v. 1.2](LICENSE.sv.txt) (EUPL-1.2), här på svenska; den engelska texten står i [LICENSE](LICENSE). Alla språkversioner som Europeiska kommissionen godkänt gäller lika. Kort sagt: du får använda, granska, ändra och sprida CAIA. Sprider du en ändrad version, eller låter andra använda en ändrad version över nätet, delar du ändringarna under samma licens. Programvaran tillhandahålls i befintligt skick, utan garantier (EUPL artikel 7 och 8).

Licensen gäller koden och dokumentationen i repot. Om kommunernas data, se nästa avsnitt.

## Data

Repot har två kommunprofiler i `next/src/caia/kommuner/`. Den ena är `exempel`: en mall med nationella schablonvärden och utan lokala datafiler. En kommun fyller i egna värden och datafiler och får då en egen profil (se [Installera för en kommun](#installera-för-en-kommun)).

Den andra, sedan 1.1, är Karlstads egen profil (`karlstad`): parameterbibliotek, utsläppspotter och datafiler, som ett exempel på en ifylld profil. Fem datafiler från Konsumtionskompassen är utelämnade, eftersom deras licens (CC BY-NC-ND 4.0) inte går att förena med EUPL. Utan dem får profilens konsumtionsrader (`CONS_*`) sina standardvärden, så en analys på den här profilen kan skilja sig från en i Karlstads egen installation. Testerna som läser de filerna hoppas över med ett besked, så testsammanfattningen visar ett antal överhoppade tester. Källor och villkor för varje datafil står i [NOTICE](NOTICE).

`next/tests/fixtures/` har sparade svar från analyser av Karlstads åtgärder. Testerna och utvecklingsservern använder dem. De innehåller inga personuppgifter.

## Vad som finns i repot

| Mapp | Vad |
|---|---|
| [`next/`](next/) | Appen. Flask-app med en pipeline i sju steg mot Claude-modellerna via OpenRouter. |
| `next/src/caia/kommuner/` | Kommunprofiler. `exempel` är mallen för en ny kommun. |
| [`docs/`](docs/) | Metod, användarguide, arkitektur, API, drift, beslut, dataformat och en sammanfattning av säkerhetsgranskningen. |
| `clientlibs/` | Versionerna av de tre bibliotek sidan laddar, listade för Dependabot. Ingenting installeras härifrån. |

## Snabbstart på egen dator

Kräver Python 3.11 eller senare och git. Node.js 18 eller senare behövs bara för de tester som kör sidans JavaScript; utan node hoppas de över med ett besked.

```
git clone https://github.com/karlstadskommun/caia.git caia
cd caia/next
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

**Prova gränssnittet utan modellanrop.** Utvecklingsservern svarar varje steg med sparade exempelsvar, så inget kostar något:

```
CAIA_KOMMUN=exempel CAIA_DEV_OPEN=1 CAIA_INSECURE_COOKIE=1 .venv/bin/python tools/devserver.py
```

Öppna http://127.0.0.1:5055. Visar sidan en inloggningsruta har skalet `SUPABASE_URL` satt sedan tidigare; ta bort den variabeln (`unset SUPABASE_URL`) och starta om.

**Kör en riktig analys.** Kräver en API-nyckel från [OpenRouter](https://openrouter.ai). En analys kostar några dollar (2 till 5 USD hösten 2026). Räkna med 7 till 30 minuter, som startsidan säger: det beror mest på hur noga man läser vid de fyra stoppen, och modellstegen själva tog 9 till 12 minuter i referenskörningarna 2026-11-10:

```
cp .env.example .env        # fyll i OPENROUTER_API_KEY, låt CAIA_KOMMUN=exempel stå
echo 'CAIA_DEV_OPEN=1' >> .env
set -a; . ./.env; set +a
PYTHONPATH=src .venv/bin/flask --app caia.web.app run --port 5000
```

Öppna http://127.0.0.1:5000. `CAIA_DEV_OPEN=1` stänger av inloggningen och får bara användas på egen dator.

Samma analys utan webbläsare, på ett av referenspaketen:

```
.venv/bin/python tools/run_batch.py tests/reference/02-aterbruk.md --out /tmp/caia-run --env .env
```

## Installera för en kommun

- **Egen server** (Linux, gunicorn, nginx): [next/INSTALL.md](next/INSTALL.md).
- **Vercel**: [next/DEPLOY.md](next/DEPLOY.md).
- **Ny kommunprofil**: kopiera `next/src/caia/kommuner/exempel/`, fyll i den och peka ut den med `CAIA_KOMMUN` eller `CAIA_KOMMUN_DIR`. INSTALL.md steg 2, och datafilernas format i [docs/DATAFORMAT.md](docs/DATAFORMAT.md).

Innan en installation öppnas för de anställda: det användarna skriver skickas till en leverantör av språkmodeller utanför kommunen, via ert eget OpenRouter-konto. Som standard kan OpenRouter skicka anropen till leverantörer utanför EU. Ska de stanna i EU krävs OpenRouters Business-plan och `CAIA_OPENROUTER_REGION=eu`, och servern måste också stå i EU ([next/INSTALL.md](next/INSTALL.md)). Det dokumentationen säger om att Karlstads installation håller texten i EU beskriver Karlstads inställningar, inte koden. Säg till användarna att inte skriva personuppgifter, som användarguiden gör.

## Dokumentation

- [docs/METOD.md](docs/METOD.md): vad CAIA räknar och inte räknar, formlerna, källmarkeringen och kända begränsningar. För den som granskar resultaten utan att läsa kod.
- [docs/METOD.html](docs/METOD.html): samma metod som en översikt att läsa i webbläsaren, med en sammanfattning per avsnitt och hela texten utfällbar. Den genereras ur METOD.md med `next/tools/metod_html.py`. METOD.md är källan; ändra aldrig html:en för hand.
- [docs/ANVANDARGUIDE.md](docs/ANVANDARGUIDE.md): så kör du en första analys och läser rapporten. För tjänstepersoner.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): moduler, dataflöde, externa tjänster och vad de kostar.
- [docs/API.md](docs/API.md): alla endpoints med indata, utdata, fel och kostnad. För den som vill integrera.
- [docs/RUNBOOK.md](docs/RUNBOOK.md): drift, deploy, rollback, nycklar, loggar, gränser, ändra en prompt.
- [docs/DECISIONS.md](docs/DECISIONS.md): de viktiga designbesluten och varför.
- [docs/DATAFORMAT.md](docs/DATAFORMAT.md): kommunens datafiler.
- [docs/security-review-2026-10.md](docs/security-review-2026-10.md): sammanfattning av säkerhetsgranskningen från oktober 2026.

## Kända begränsningar

Metodens begränsningar, med den uppmätta spridningen mellan körningar, står i [docs/METOD.md](docs/METOD.md#kända-begränsningar). Det viktigaste:

- **Språkmodellen sätter antagandena.** Beräkningen är deterministisk, men indata till den (andelar, faktorer, tidsramar) tas fram av Claude från användarens beskrivning, parameterbiblioteket och kommunens data. Två körningar av samma åtgärd ger inte exakt samma tal. Varje antagande visas och kan rättas vid godkännandet.
- **Tecknet kan bli fel för åtgärder som undviker utsläpp.** Positivt tal är minskning. En åtgärd som återbruk kan av språkmodellen räknas som ökad aktivitet och få minus. Kalkylen varnar då för ökade utsläpp, och kvalitetsgranskningen pekar ut felet. Ett sådant resultat ska inte användas förrän antagandet är rättat.
- **Medelvärdet per år gäller 2026 till 2030**, oavsett målår. En åtgärd som verkar sent i de åren får ett lågt tal, och en som verkar först efteråt får noll. Kalkylen varnar i båda fallen.
- **Om CAIA:s egen kalkyl inte kan läsa modellens tal** räknar språkmodellen själv. Resultatet märks då `deterministic: false` och rapporten säger det.
- **Modellstegen i en analys tar omkring tio minuter sammanlagt**, varje steg upp till knappt fem. Avbryter användaren mitt i ett steg fortsätter anropet på servern och kostar ändå.
- **Anropsgränserna räknas per serverprocess.** På Vercel har varje instans sin egen räknare. Det stoppar en klient som loopar, inte ett bestämt missbruk; den hårda gränsen är kreditgränsen på OpenRouter-nyckeln.
- **API:t har ingen versionering** utöver versionsnumren i [CHANGELOG.md](CHANGELOG.md).
- **Öppet efter överlämningsgranskningen (september 2026):** jämförelsen av kalkylens indata med de godkända antagandena fångar inte varje felläsning ([docs/METOD.md](docs/METOD.md#jämförelsen-med-det-som-godkändes)); utläsningen tar första JSON-objektet med drivare i ett modellsvar; sidan hämtar typsnitt och bibliotek från Google och jsDelivr; spridningen mellan körningar visas inte för användaren.

## Säkerhet

Rapportera sårbarheter enligt [SECURITY.md](SECURITY.md), inte i ett öppet ärende.

## Bidra

Se [CONTRIBUTING.md](CONTRIBUTING.md). Ändringar skrivs i [CHANGELOG.md](CHANGELOG.md).

## Kontakt

henric.barkman@karlstad.se
