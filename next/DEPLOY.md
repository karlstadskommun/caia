# Deploy CAIA till Vercel

Egen server utan Vercel (till exempel en annan kommuns installation): se [INSTALL.md](INSTALL.md). Drift, rollback och nycklar: [docs/RUNBOOK.md](../docs/RUNBOOK.md).

Så här körs CAIA (Climate Action Impact Analysis) på Vercel. `<er-adress>` nedan är produktionsadressen och `<projekt>` Vercel-projektets namn. Karlstads egen uppsättning står i ett internt driftdokument hos kommunen.

## Hur deployen fungerar

- **För hand med Vercels CLI från `next/`**, inte via Vercels git-koppling. En push till `main` deployar alltså ingenting. Den som deployar kör `vercel --prod` i en utcheckning av `main` (se RUNBOOK, "Deploy").
- Vercel-projektets Root Directory är `.`; det är mappen man kör `vercel` i (`next/`) som laddas upp. `next/.vercel/project.json` binder mappen till projektet och skapas av `vercel link`. Den ska inte checkas in.
- `vercel.json` använder `builds` med `@vercel/python` och `maxDuration: 300`. Projektet har Fluid compute påslaget. Modellanropet avbryts efter 280 sekunder (`REQUEST_TIMEOUT_S` i `api_client.py`), så att funktionen hinner svara med ett fel i stället för att dödas. Vi prövade 800 och 760 på Pro 13–15/10, men Vercels logg visade 300 som gräns på varje anrop: `maxDuration` under `builds` togs inte upp. Ska gränsen höjas igen måste den sättas så att loggens `functionMaxDuration` visar det nya värdet.
- Funktionen körs i region **arn1** (Stockholm), satt med `regions` i `vercel.json` sedan 2026-10-08. Tidigare iad1 (USA öst). Supabase-projektet ligger också i Stockholm.
- Modellanropen går till OpenRouters EU-ingång (`CAIA_OPENROUTER_REGION=eu`), som bara låter leverantörer i EU svara. Tillsammans med regionen ovan stannar användarens text och analysen fysiskt i EU hela vägen. Juridiskt är OpenRouter, Vercel och leverantören som kör Claude (Google) amerikanska bolag.
- **Plan:** Vercels villkor tillåter Hobby bara för icke-kommersiellt personligt bruk, och kod skriven av en anställd räknas som kommersiell. En kommun väljer Pro eller kör på egen server.

## Engångs-setup (nytt Vercel-projekt)

1. Installera Vercels CLI och logga in: `npm i -g vercel`, `vercel login`.
2. `cd next && vercel link` och skapa ett nytt projekt. Framework: Flask (eller Other). Root Directory: `.`.
3. Slå på **Fluid compute** under projektets Functions-inställningar om det inte redan är på. Utan det kan Hobby bara köra 60 sekunder och varje analyssteg avbryts.
4. Slå på **Vercel Authentication** med Standard Protection under projektets Deployment Protection. Då kräver varje deploys egen adress och alla förhandsversioner inloggning hos Vercel, medan produktionsadressen är öppen. Utan det ligger varje gammal deploy kvar öppen på sin egen adress, med den gamla koden.
5. **Environment Variables** (Production, och Preview om ni vill prova grenar). Alla variabler beskrivs i [.env.example](.env.example):
   - `OPENROUTER_API_KEY`
   - `CAIA_OPENROUTER_REGION`: `eu` om modellanropen ska gå via OpenRouters EU-ingång. Kontrollera med OpenRouter att ert konto har den.
   - `CAIA_KOMMUN` (namnet på en profil under `src/caia/kommuner/`) eller `CAIA_KOMMUN_DIR`. Krävs: utan den startar appen inte, och Vercels logg säger vilken variabel som saknas.
   - `SUPABASE_URL` och `SUPABASE_ANON_KEY` (den publika nyckeln; appen startar inte med en hemlig). `SUPABASE_JWT_SECRET` bara om projektet signerar inloggningar med delad hemlighet (HS256); Ett projekt som signerar med ES256 behöver den inte.
   - `CAIA_ALLOWED_EMAILS`: vilka konton som släpps in (till exempel `@kommun.se`). Tom betyder att ingen släpps in.
   - `CAIA_SECRET_KEY`: en lång slumpsträng. Krävs i lösenordsläge. Med Supabase är den nyckeln till de hashade adresserna i loggen: utan den får varje instans en egen, och samma besökare ser olika ut från en rad till nästa.
6. **Supabase:** kör [`deploy/reports.sql`](deploy/reports.sql) en gång, lägg in samma poster som i `CAIA_ALLOWED_EMAILS` i databasens lista (`insert into caia.allowed (entry) values ('@kommun.se');`, filens sista steg), och lägg till CAIA:s adress (`https://<er-adress>`) under Authentication, URL Configuration, **Redirect URLs**. Annars pekar länken i bekräftelsemejlet till projektets Site URL, som kan vara ett annat verktygs adress om projektet delas. Låt **Confirm email** vara påslaget: med en domän i listan är det bekräftelsen som visar att den som loggar in äger adressen (kontrollen står under smoke-testet).
7. `vercel --prod` från `next/`.

## Kommunprofil (ny kommun)

Allt som gör en installation till en viss kommun ligger i dess profil, `src/caia/kommuner/<slug>/`: `kommun.toml` (namn, ort, län, plan, stycket agenterna får om kommunen), `parameters_library.md` och `data/`. Koden är densamma för alla kommuner.

En ny kommun kopierar `src/caia/kommuner/exempel/` till `src/caia/kommuner/<slug>/`, fyller i `kommun.toml`, fyller i kolumnen `Lokalt_värde` i parameterbiblioteket där det finns egen data, lägger datafilerna i `data/` med de filnamn som står i bibliotekets sektion 12 (format: [docs/DATAFORMAT.md](../docs/DATAFORMAT.md)), och sätter `CAIA_KOMMUN=<slug>`. Kontrollera med:
```
cd next/src && CAIA_KOMMUN=<slug> python -m caia.kommun
```
Den skriver ut vilken profil som är aktiv, hur många parametrar som är lokala eller schabloner, och vilka datafiler som hittas. `tests/test_kommunprofil.py` kör hela kedjan på exempelprofilen och fäller om ordet Karlstad når en modell eller sidan (utom ursprungsraden, som säger att verktyget kommer från Karlstads kommun).

## Smoke-test efter deploy

1. Öppna adressen: inloggningsrutan ska visas.
2. `curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d "{}" https://<er-adress>/api/kalkyl` ska ge `401`.
3. Logga in med ett konto som står i `CAIA_ALLOWED_EMAILS`, skriv en åtgärd, godkänn stegen (10 till 15 minuter): rapport och siffra till höger.
4. Ladda om: "Sparade analyser" ska lista körningen. Säger CAIA att databasen inte släpper in kontot saknas posten i `caia.allowed` (RUNBOOK, "Användare").
5. Vercels logg (`vercel logs <er-adress>`) ska ha raden `CAIA: kommunprofil <slug> (...)` från uppstarten, och ingen rad som börjar med `CAIA: VARNING`.
6. Supabase kräver fortfarande bekräftelse via e-post: `curl -s https://<projekt>.supabase.co/auth/v1/settings -H "apikey: <SUPABASE_ANON_KEY>"` ska innehålla `"mailer_autoconfirm":false`. Delas projektet med ett annat verktyg slår en ändring där igenom här.
7. En deploys egen adress ska kräva inloggning hos Vercel: `curl -s -o /dev/null -w "%{http_code}\n" https://<adress ur vercel ls <projekt>>/` ska ge `302` eller `401`, inte `200`.
8. Radera de äldre deploymenterna efter en säkerhetsrättning (RUNBOOK, "Deploy"): en gammal deployment har sin egen adress och kör den gamla koden så länge den finns.

## Struktur (självständig under next/)
- `api/index.py`: Vercels ingång (`from caia.web.app import app`)
- `vercel.json`: `builds` med `maxDuration: 300`, alla adresser till `api/index.py`
- `requirements.txt`: flask, anthropic, PyJWT[crypto] och deras beroenden, alla med exakt version (Vercel installerar den här filen)
- `src/caia/`: agenter, webbapp, kalkyl, datalager
- `src/caia/kommuner/<slug>/`: kommunprofiler, en mapp per kommun (`exempel` är mallen)
