# Installera CAIA på egen server

För kommunens IT, som ska köra CAIA (Climate Action Impact Analysis) på en egen server. Beskrivningen gäller en Linuxserver (Debian eller Ubuntu) med nginx framför. Karlstads egen installation körs på Vercel och beskrivs i [DEPLOY.md](DEPLOY.md). Den här vägen kräver ingen Vercel.

## Vad CAIA är, tekniskt

CAIA är en Python-app (Flask) som körs med gunicorn. Den har ingen egen databas och ingen kö. Tre saker utanför servern behövs:

- **OpenRouter**, som förmedlar anropen till AI-modellerna (Anthropics Claude Opus 5.5 och Claude Sonnet 5.5). Det är den enda kostnaden som växer med användningen.
- **Supabase** för inloggning och sparade analyser. Det går att klara sig utan Supabase med ett gemensamt lösenord, men då sparas inga analyser (se steg 4).
- **En kommunprofil**: kommunens namn, parameterbibliotek och egna datafiler. Koden är densamma för alla kommuner.

En analys går i sju steg. Varje steg är ett eget anrop till servern och kan ta upp till knappt fem minuter, eftersom AI-modellen tänker länge. Därför måste både gunicorn och nginx tillåta långa anrop (steg 6 och 7). I steg 4 skickar webbläsaren ett anrop per drivare samtidigt, så servern behöver hantera några parallella anrop per användare.

## Vad ni behöver

- En server med Python 3.11 eller senare (vi har provat 3.12), git och nginx. På Ubuntu: `sudo apt install python3-venv git nginx`
- Ett domännamn och ett certifikat för HTTPS.
- Utgående trafik från servern till `openrouter.ai` och till ert Supabase-projekt (`<projekt>.supabase.co`).
- Användarnas webbläsare hämtar typsnittet Roboto från `fonts.googleapis.com` och `fonts.gstatic.com`, och tre små bibliotek (marked, DOMPurify, supabase-js) från `cdn.jsdelivr.net`. De måste gå att nå från kommunens nät.
- Koden, från det publika repot `https://github.com/karlstadskommun/caia`.

## 1. Hämta koden och installera

```
sudo useradd --system --home-dir /opt/caia --shell /usr/sbin/nologin caia
sudo mkdir -p /opt/caia /etc/caia
sudo chown caia:caia /opt/caia
sudo -u caia git clone https://github.com/karlstadskommun/caia.git /opt/caia/app
sudo -u caia python3 -m venv /opt/caia/venv
sudo -u caia /opt/caia/venv/bin/pip install -U pip
sudo -u caia /opt/caia/venv/bin/pip install -r /opt/caia/app/next/requirements-server.txt
```

## 2. Kommunprofil

Lägg profilen utanför repot, så att en uppdatering av koden aldrig rör den:

```
sudo cp -r /opt/caia/app/next/src/caia/kommuner/exempel /etc/caia/kommun
sudo chown -R root:caia /etc/caia/kommun
sudo chmod -R g+rX /etc/caia/kommun
```

Fyll sedan i:

- `kommun.toml`: kommunens namn, ort, län, namnet på klimatplanen, ett kort stycke om kommunen som AI-stegen får läsa, och `slug` (ett kort namn med små bokstäver).
- `parameters_library.md`: kolumnen `Lokalt_värde` där kommunen har egna värden. Tomma rader betyder att nationella schablonvärden används.
- `potter.toml` (valfri): kommunens utsläppspotter för portföljen, med baslinje och källa. Formatet står i [docs/DATAFORMAT.md](../docs/DATAFORMAT.md). Utan filen räknar portföljen varje åtgärd för sig.
- `data/`: kommunens datafiler, med de filnamn som står i bibliotekets sektion 12. CAIA läser sex av källorna (utsläpp, kommunkoncernens utsläpp, konsumtionsfotavtryck, hushållens tidsserie, energi i bostäder, medborgarundersökning); formaten står i [docs/DATAFORMAT.md](../docs/DATAFORMAT.md). Resvaneundersökningen läses inte: skriv av talen i sektion 2 med tabell och sida, och lägg inte PDF:en i `data/`.

Kontrollera profilen:

```
cd /opt/caia/app/next/src && sudo -u caia env CAIA_KOMMUN_DIR=/etc/caia/kommun /opt/caia/venv/bin/python -m caia.kommun
```

Den skriver ut vilken profil som är aktiv, hur många parametrar som är lokala eller schabloner, och vilka datafiler som hittas. Varningar om `LOOKUP source ... is unresolvable` betyder att en datafil saknas, eller att källan är en som CAIA inte läser, och att schablonvärdet används i stället. `läses ej` i listan betyder det senare.

Vill ni prova innan profilen är ifylld går det att köra mallen som den är. Då räknar CAIA bara med nationella schabloner.

## 3. OpenRouter

1. Skapa ett konto på [openrouter.ai](https://openrouter.ai) och fyll på krediter.
2. Skapa en API-nyckel för CAIA och sätt en kreditgräns på nyckeln, så att en felkonfiguration inte kan kosta mer än ni bestämt. Tar krediterna slut svarar OpenRouter med fel och analysen stannar.
3. Kontrollera OpenRouters villkor och inställningar för datahantering mot kommunens krav innan skarp användning. Allt användaren skriver och allt analysen tar fram skickas via OpenRouter till en leverantör som kör Claude. Be användarna att inte skriva in personuppgifter.
4. Under Settings, Privacy hos OpenRouter: slå på **Zero Data Retention** för Anthropic och för övriga modeller, så går anropen bara till leverantörer som inte sparar något, och slå av alla fyra reglagen under **Data Training**.
5. Ska anropen stanna i EU: uppgradera kontot till OpenRouters Business-plan och sätt `CAIA_OPENROUTER_REGION=eu`. Servern måste då också stå i EU, annars passerar texten ett annat land innan den når OpenRouter.

Vilken modell varje steg använder står i `next/src/caia/api_client.py` (`AGENT_MODELS`). En analys kostar typiskt 2–3 USD i modellanrop och tar 10 till 15 minuter; varje drivare utöver två och varje omkörning vid en grind kostar mer. Detaljer i [docs/API.md](../docs/API.md#kostnad).

## 4. Inloggning

Det finns två sätt. Supabase är det vi rekommenderar.

### A. Supabase: personliga konton och sparade analyser

1. Skapa ett projekt på [supabase.com](https://supabase.com). Välj en region i EU.
2. Öppna SQL Editor och kör innehållet i [`deploy/reports.sql`](deploy/reports.sql). Det skapar tabellen för sparade analyser, där varje användare bara ser, sparar och raderar sina egna, och listan `caia.allowed` över vilka konton som får spara:

```sql
-- CAIA: tabellen för sparade analyser. Kör en gång i Supabase (SQL Editor).
-- Koden skriver user_id, action_name, key_metric, intake_summary och
-- formatted_report, och läser id, action_name, key_metric, created_at och
-- formatted_report. Varje användare ser, sparar och raderar bara sina egna
-- rader. Anonyma konton (Supabase "anonymous sign-in") får ingenting, och
-- bara konton i listan caia.allowed får spara (se längre ner, och sista
-- steget i filen som ni skriver själva).
-- Längdgränserna är desamma som appens (REPORT_MAX_CHARS i app.py), så en
-- rad som går förbi appen direkt mot API:t kan inte bli större. Tecken och
-- byte räknas var för sig: 300 000 tecken kan annars vara 1,2 MB.

create table public.reports (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at       timestamptz not null default now(),
  action_name      text check (char_length(action_name) <= 300),
  key_metric       jsonb check (octet_length(key_metric::text) <= 1000),
  intake_summary   text check (char_length(intake_summary) <= 50000),
  formatted_report text check (char_length(formatted_report) <= 300000),
  constraint reports_intake_summary_bytes_check check (octet_length(intake_summary) <= 100000),
  constraint reports_formatted_report_bytes_check check (octet_length(formatted_report) <= 600000)
);

create index reports_user_created_idx on public.reports (user_id, created_at desc);

-- Vilka konton som får spara, i databasen själv. Appen släpper bara in konton
-- som står i CAIA_ALLOWED_EMAILS, men tabellen nås också direkt genom
-- Supabases API med projektets publika nyckel, förbi appen. Utan det här kan
-- varje konto i projektet lägga rader i tabellen, och i ett projekt med öppen
-- registrering är det vem som helst (omgranskningen 7 oktober 2026, F2).
--
-- Listan ligger i ett eget schema som API:t inte visar. Den ska ha samma
-- poster som CAIA_ALLOWED_EMAILS: hela adresser, domäner skrivna som
-- @kommun.se, eller * för alla inloggade. Små bokstäver.
create schema if not exists caia;
grant usage on schema caia to authenticated;

create table if not exists caia.allowed (
  entry text primary key
    check (entry = lower(entry) and (entry = '*' or position('@' in entry) > 0))
);
alter table caia.allowed enable row level security;
revoke all on caia.allowed from anon, authenticated;

-- Läser kontots adress ur Supabases egen användartabell, inte ur
-- inloggningsbeviset, och kräver att adressen är bekräftad. collate "C" gör
-- att bara A-Z görs till små bokstäver: annars blir Kelvin-tecknet (U+212A)
-- ett vanligt k, och en domän skriven med det läses som @kommun.se.
create or replace function caia.account_allowed() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from caia.allowed where entry = '*')
      or exists (
        select 1
        from auth.users u
        join caia.allowed a
          on a.entry = lower(u.email collate "C")
          or a.entry = substring(lower(u.email collate "C") from '@[^@]*$')
        where u.id = (select auth.uid())
          and u.email_confirmed_at is not null
          and position('@' in u.email) > 1
      );
$$;
revoke all on function caia.account_allowed() from public, anon;
grant execute on function caia.account_allowed() to authenticated;

alter table public.reports enable row level security;

create policy "reports: läsa egna" on public.reports
  for select to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

create policy "reports: spara egna" on public.reports
  for insert to authenticated
  with check ((select auth.uid()) = user_id
              and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
              and (select caia.account_allowed()));

create policy "reports: radera egna" on public.reports
  for delete to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

-- Nya Supabase-projekt (från 30 maj 2026) exponerar inte tabeller mot API:t
-- av sig själva. Utan raden nedan svarar sparandet med ett behörighetsfel.
-- Ingen update: en sparad rapport ändras aldrig.
grant select, insert, delete on public.reports to authenticated;

-- SISTA STEGET, som ni skriver själva: lägg in era poster, samma som i
-- CAIA_ALLOWED_EMAILS. Tom lista betyder att ingen kan spara en analys.
--
--   insert into caia.allowed (entry) values ('@kommun.se'), ('anna.andersson@konsult.se');
--
-- Ändrar ni CAIA_ALLOWED_EMAILS senare, ändra här också (RUNBOOK, "Vem som
-- släpps in"). Se vad som står i listan: select entry from caia.allowed;
```

3. Lägg in vilka som får spara, i samma SQL Editor. Det är filens sista steg, som ni skriver själva. Använd samma poster som ni sätter i `CAIA_ALLOWED_EMAILS` i steg 5, med små bokstäver:

```
insert into caia.allowed (entry) values ('@kommun.se');
```

   Listan finns på två ställen med flit. `CAIA_ALLOWED_EMAILS` styr vem appen släpper in. Tabellen nås också direkt genom Supabases API med den publika nyckeln, förbi appen, och där är det `caia.allowed` som gäller. Skiljer de sig åt kan ett konto köra analyser men inte spara dem, och CAIA säger då att databasen inte släpper in kontot.
4. Stäng av att vem som helst kan skapa ett konto. Inloggningssidan har en knapp för att skapa konto, och varje konto kan köra analyser på er OpenRouter-nyckel. Under Authentication, slå av **Allow new users to sign up**.
   Låt **Confirm email** vara påslaget (Authentication, Sign In / Providers, Email). Släpper ni in en hel domän (`@kommun.se`) är det bekräftelsen som visar att den som loggar in äger adressen. Med den avslagen markerar Supabase varje adress som bekräftad, och då kan den som får skapa ett konto skriva in en kollegas adress. Kontrollen står i steg 8.
5. Lägg upp användarna själva: Authentication, Users, **Add user**, **Create new user**, med e-post och lösenord. Kryssa i att användaren ska bekräftas direkt.
6. Hämta två värden under projektets API-inställningar: projektets adress (`SUPABASE_URL`) och den publika nyckeln (`SUPABASE_ANON_KEY`). Supabase kallar den publika nyckeln antingen *anon* (äldre projekt) eller *publishable* (`sb_publishable_...`). CAIA skickar den bara som `apikey`, vilket är så Supabase säger att båda ska användas ([Supabase om nycklarna](https://supabase.com/docs/guides/getting-started/api-keys)).
7. Under Authentication, URL Configuration: sätt **Site URL** till CAIA:s adress (`https://caia.exempel.se`). Länkarna i Supabases mejl (bekräftelse, nytt lösenord) går dit.

### B. Gemensamt lösenord, utan Supabase

Sätt `CAIA_PASSWORD` och `CAIA_SECRET_KEY` (steg 5) och lämna `SUPABASE_URL` tom. Alla loggar in med samma lösenord. Analyser sparas inte, men varje rapport kan laddas ner som fil.

## 5. Inställningar

Skapa `/etc/caia/caia.env` skyddad från början, så att nycklarna aldrig ligger i en fil som alla på servern kan läsa, och öppna den sedan:

```
sudo install -m 640 -o root -g caia /dev/null /etc/caia/caia.env
sudoedit /etc/caia/caia.env
```

Skriv in:

```
OPENROUTER_API_KEY=sk-or-...
CAIA_KOMMUN_DIR=/etc/caia/kommun
CAIA_SECRET_KEY=<lång slumpsträng>
SUPABASE_URL=https://<projekt>.supabase.co
SUPABASE_ANON_KEY=<publik nyckel>
CAIA_ALLOWED_EMAILS=@kommun.se
```

Slumpsträngen tar ni fram med `python3 -c "import secrets; print(secrets.token_hex(32))"`. CAIA startar inte med platshållaren `<lång slumpsträng>` kvar.

Alla inställningar CAIA läser:

| Variabel | Behövs | Vad den gör |
|---|---|---|
| `OPENROUTER_API_KEY` | Alltid | Nyckeln från steg 3. |
| `CAIA_OPENROUTER_REGION` | Nej | `eu` skickar anropen till OpenRouters EU-ingång (kräver Business-plan). Tom betyder den globala. Ett annat värde stoppar analysen med ett fel. |
| `CAIA_ANTHROPIC_API_KEY` | Nej | Bara för batchkörningar med `tools/run_batch.py`, aldrig i webbappen. Satt skickas alla anrop direkt till Anthropics API i stället för via OpenRouter, till exempel för API-krediter som ingår i ett Claude-abonnemang. Den vägen har ingen EU-ingång, så `CAIA_OPENROUTER_REGION` gäller inte. |
| `CAIA_KOMMUN_DIR` | Ja, med profil utanför repot | Sökväg till kommunprofilen. Vinner över `CAIA_KOMMUN`. |
| `CAIA_KOMMUN` | Ja, om inte `CAIA_KOMMUN_DIR` är satt | Namnet på en profil som ligger i repot (i det publika repot finns bara `exempel`). Utan någon av de två startar appen inte: den gissar inte vilken kommun den är. |
| `CAIA_SECRET_KEY` | Ja med lösenord, rekommenderas alltid | Signerar inloggningskakan. Samma värde i alla serverprocesser, annars loggas användare ut slumpvis. Appen startar inte i lösenordsläge utan den. Den är också nyckeln till de hashade adresserna i loggen: utan den får varje process en egen, och samma besökare ser olika ut efter en omstart. |
| `SUPABASE_URL` | Med Supabase | Projektets adress. När den är satt gäller Supabase-inloggning. |
| `SUPABASE_ANON_KEY` | Med Supabase | Den publika nyckeln från steg 4. Sidan skickar den till varje besökare, så CAIA startar inte om en hemlig nyckel (`service_role` eller `sb_secret_...`) står här. |
| `SUPABASE_JWT_SECRET` | Nej | Behövs bara för äldre Supabase-projekt som signerar inloggningar med en delad hemlighet (HS256). Nya projekt signerar med ES256 och kontrolleras mot Supabases publika nycklar utan den. |
| `CAIA_AUTH_FALLBACK` | Nej | `1` låter Supabase avgöra inloggningar som CAIA inte kan kontrollera själv, till exempel ett HS256-projekt utan `SUPABASE_JWT_SECRET`. Varje sådan inloggning kostar då ett anrop till Supabase, och det gör även en påhittad inloggning som bara ser rätt ut, så slå inte på den i onödan. Utan den nekas de. Det gäller också när Supabases lista över signeringsnycklar inte går att hämta: då kontrollerar CAIA inloggningar med de nycklar den läst den senaste timmen, och svarar andra att inloggningen inte kan kontrolleras just nu. |
| `CAIA_ALLOWED_EMAILS` | Ja med Supabase | Vilka konton som får använda CAIA: hela adresser och/eller domäner skrivna som `@kommun.se`, kommaseparerade. `*` släpper in alla inloggade. Tom betyder att ingen släpps in, eftersom vem som helst kan skapa ett konto i ett Supabase-projekt med öppen registrering. Samma poster ska stå i databasens lista `caia.allowed` (steg 4). |
| `CAIA_CONTACT` | Nej | Den adress som ett konto utanför `CAIA_ALLOWED_EMAILS` ska skriva till, till exempel `klimat@kommun.se`. Står i meddelandet som visas när kontot nekas. Tom betyder att meddelandet bara säger att adressen behöver läggas till. |
| `CAIA_PASSWORD` | Bara i lösenordsläge | Det gemensamma lösenordet. Används bara när `SUPABASE_URL` är tom. Byter ni lösenord loggas alla ut. Fem felaktiga försök från samma adress spärrar inloggningen i tio minuter (`CAIA_LOGIN_FAILURES_PER_WINDOW`). Är det kortare än 12 tecken skriver CAIA en varning i loggen vid varje start. |
| `CAIA_RATE_LIMIT_PER_MIN` | Nej | Högsta antal modellanrop per minut. Med Supabase räknas de per användare. I lösenordsläge delar alla inloggning, och då räknas de per adress som anropen kommer från: kollegor bakom samma nät delar på gränsen. Standard 20. |
| `CAIA_RATE_LIMIT_PER_DAY` | Nej | Högsta antal modellanrop per dygn, räknat på samma sätt. Standard 150, ungefär tio analyser. |
| `CAIA_LOGIN_FAILURES_PER_WINDOW` | Nej | Hur många felaktiga lösenord från samma adress som får komma inom tio minuter innan inloggningen spärras. Standard 5. Gäller lösenordsläget. En workshop där alla sitter bakom samma nät delar räkningen, så höj den då, till exempel till 50. |
| `CAIA_TRUSTED_PROXIES` | Nej | Hur många proxyer framför CAIA som lägger till en adress i `X-Forwarded-For`. Standard 1 (nginx). Se steg 7. |
| `CAIA_INSECURE_COOKIE` | Bara för test | `1` låter inloggningskakan gå över vanlig http. Utan den kräver lösenordsläget https (eller `localhost`). CAIA skriver en varning i loggen vid varje start när den är satt. |
| `CAIA_DEV_OPEN` | **Aldrig i drift** | `1` stänger av inloggningen helt. Bara för utveckling på egen dator. CAIA skriver en varning i loggen vid varje start när den är satt. |

Utan både Supabase och lösenord vägrar CAIA att köra analyser, i stället för att bli öppen för alla.

## 6. Kör CAIA som tjänst

Skapa `/etc/systemd/system/caia.service`:

```
[Unit]
Description=CAIA klimatkalkyl
After=network-online.target
Wants=network-online.target

[Service]
User=caia
Group=caia
WorkingDirectory=/opt/caia/app/next
EnvironmentFile=/etc/caia/caia.env
ExecStart=/opt/caia/venv/bin/gunicorn --pythonpath src --workers 1 --threads 16 --timeout 310 --no-control-socket --access-logfile - --bind 127.0.0.1:8000 caia.web.app:app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

En process med 16 trådar klarar 16 samtidiga anrop. En användare har oftast ett anrop igång, men i steg 4 ett per drivare samtidigt (upp till tolv), så 16 trådar räcker för ett par användare som är i steg 4 på en gång och fler som är i andra steg. Höj `--threads` om fler ska köra analyser samtidigt; när alla trådar är upptagna väntar nästa anrop i kö tills en blir ledig. AI-anropen väntar mest på svar, så trådar räcker. Håll `--workers 1`: gränserna för anrop och inloggningsförsök räknas i processens minne, och med två processer räknar var och en för sig, så att gränserna i praktiken fördubblas. `--timeout 310` ger ett steg tid att bli klart: själva modellanropet avbryts efter 280 sekunder (`REQUEST_TIMEOUT_S` i `api_client.py`).

Starta:

```
sudo systemctl daemon-reload
sudo systemctl enable --now caia
systemctl status caia
```

Loggarna läser ni med `journalctl -u caia -f`. `--access-logfile -` skriver varje anrop dit med väg och svarskod; adressen på de raderna är nginx egen, inte besökarens. CAIA själv skriver en rad för varje modellanrop den släpper igenom, med användarens id (med Supabase) eller en hashad adress (i lösenordsläge), så att det går att se vilket konto som har förbrukat vad. Id:t slår ni upp i Supabase under Authentication, Users. Nekade inloggningar, fel lösenord och nådda anropsgränser loggas som `WARNING`, på samma sätt, aldrig med lösenord eller inloggningsbevis. Det är de raderna ni larmar på om någon gissar lösenord eller belastar tjänsten.

Två saker att bestämma själva. Loggen kan vid fel innehålla stycken ur en analys (ett drivarnamn, ett felmeddelande från modelltjänsten), så den ska behandlas som analyserna. Och nginx egen logg (`/var/log/nginx/access.log`) har besökarnas adresser i klartext: bestäm hur länge loggarna sparas.

## 7. nginx och HTTPS

Exempel på `/etc/nginx/sites-available/caia` (byt domän och certifikatets sökvägar):

```
server {
    listen 80;
    server_name caia.exempel.se;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name caia.exempel.se;

    ssl_certificate     /etc/ssl/certs/caia.crt;
    ssl_certificate_key /etc/ssl/private/caia.key;

    add_header Strict-Transport-Security "max-age=31536000" always;

    client_max_body_size 5m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 310s;
        proxy_read_timeout 310s;
    }
}
```

Det första blocket skickar den som skriver adressen utan `https://` vidare till krypterad anslutning. `Strict-Transport-Security` får webbläsaren att i ett år bara använda https mot adressen, även om någon länkar till http.

CAIA räknar med att nginx är den enda proxyn framför gunicorn: gränserna för inloggningsförsök och anrop utan inloggning räknas på den sista adressen i `X-Forwarded-For`, den som nginx lägger till. Står en till proxy framför nginx, till exempel kommunens lastbalanserare, sätt `CAIA_TRUSTED_PROXIES` till antalet proxyer (då 2). Annars räknas alla användare på den proxyns adress och delar en gräns. Sätt aldrig ett högre tal än det verkliga: då kan klienten själv välja vilken adress som räknas.

Två rader är viktiga. `proxy_read_timeout 310s`: nginx standard är 60 sekunder, och då bryts de flesta analyssteg mitt i. `client_max_body_size 5m`: varje steg skickar med hela analysen hittills, och nginx standard (1 MB) kan bli för litet i långa analyser. CAIA själv tar emot högst 2 MB per anrop (`MAX_CONTENT_LENGTH` i `app.py`) och svarar 413 över det, så nginx-gränsen behöver bara ligga över den.

```
sudo ln -s /etc/nginx/sites-available/caia /etc/nginx/sites-enabled/caia
sudo nginx -t && sudo systemctl reload nginx
```

## 8. Kontrollera installationen

```
curl -s -o /dev/null -w "%{http_code}\n" https://caia.exempel.se/
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d "{}" https://caia.exempel.se/api/kalkyl
```

Den första ska svara `200` med Supabase (`302` till inloggningen med gemensamt lösenord). Den andra ska svara `401`: analyserna kräver inloggning. Svarar den `503` saknas både Supabase och lösenord i inställningarna.

Med Supabase, kontrollera också att projektet kräver bekräftelse via e-post (steg 4):

```
curl -s https://<projekt>.supabase.co/auth/v1/settings -H "apikey: <publik nyckel>"
```

Svaret ska innehålla `"mailer_autoconfirm":false`. Står det `true` kan vem som helst som får skapa ett konto logga in med en adress i er domän utan att äga den.

Logga sedan in och kör en hel analys. Den tar 10 till 15 minuter. Med Supabase ska den dyka upp under Sparade analyser när du laddar om sidan. Sist i rapporten står avsnittet *Talens ursprung*, som visar vilka tal som kommer ur parameterbiblioteket, ur kommunens egen data, från externa källor eller är analysens egna antaganden.

## Uppdatera

```
sudo -u caia git -C /opt/caia/app pull
sudo -u caia /opt/caia/venv/bin/pip install -r /opt/caia/app/next/requirements-server.txt
sudo systemctl restart caia
```

`git pull` hämtar det senaste på `main`. Läs vad som ändrats innan ni startar om (`sudo -u caia git -C /opt/caia/app log --oneline ORIG_HEAD..HEAD`), kör testerna nedan, och anteckna vilken version ni kör (`git -C /opt/caia/app rev-parse --short HEAD`). Säger ändringarna att en fil under `deploy/migrations/` har tillkommit ska den köras i Supabase.

Kommunprofilen i `/etc/caia/kommun` rörs inte av en uppdatering. Ändrar ni i den räcker `sudo systemctl restart caia`, eftersom profilen läses när CAIA startar.

## Testerna

Testsviten kör utan nätverk och utan kostnad på några sekunder. Den behöver `requirements-dev.txt` och Node.js 18 eller senare (för testerna av sidans JavaScript; utan node hoppas de över med ett besked):

```
cd /opt/caia/app/next
sudo -u caia /opt/caia/venv/bin/pip install -r requirements-dev.txt
sudo -u caia /opt/caia/venv/bin/python -m pytest -q
```

Kör den efter en uppdatering, före omstarten. Ändrar ni i kommunprofilen, läs "Ändra en prompt, parameterbiblioteket eller en datafil" i [docs/RUNBOOK.md](../docs/RUNBOOK.md): sviten fäller med flit tills ni kört referensanalyserna och uppdaterat fingeravtrycken.

## Om något går fel

Vanliga fel och vad de betyder står under Felsökning i [docs/RUNBOOK.md](../docs/RUNBOOK.md#felsökning). Loggen (`journalctl -u caia`) säger nästan alltid vilken inställning som saknas.
