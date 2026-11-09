# CAIA:s API

För den som vill driva CAIA (Climate Action Impact Analysis) från ett annat system. API:t är detsamma som webbsidan använder; det finns inget separat integrations-API och ingen versionering än. `next/tools/run_batch.py` är en fullständig klient i Python och det bästa exemplet på hur stegen anropas i ordning. Vad talen i svaren betyder och hur de räknas står i [METOD.md](METOD.md).

## Grunder

- **Allt är JSON över HTTPS**, `POST` om inget annat står. Svaret på ett fel är alltid `{"error": "<text på svenska>"}` med en statuskod enligt tabellen längst ner.
- **Servern är tillståndslös.** Klienten håller hela analysen och skickar med den som `history` i varje anrop: en lista med turer `{"role": "user" | "assistant", "content": "<text>"}`. Taken är 120 turer, 100 000 tecken per tur, 400 000 tecken totalt och 2 MB per anrop. Bara `role` och `content` går vidare till modellen; andra fält i en tur kastas.
- **Mellan två steg** lägger klienten till modellens svar som en `assistant`-tur och sedan överlämningsraden för steget som just blev klart som en `user`-tur. Raderna finns i `next/src/caia/pipeline.py` (`BRIDGE`) och måste skickas exakt så; agenterna läser dem. Vill användaren rätta ett steg skickar klienten rättelsen som `user`-tur i stället och kör samma steg igen.
- **Stoppen bestämmer klienten.** API:t tvingar ingen ordning och inga godkännanden. Webbsidan stannar efter steg 1, 2, 3 och 4 och låter användaren godkänna eller rätta, och kör sedan steg 5 till 7 i en följd. En integration bör stanna åtminstone efter steg 4, där antagandena som styr resultatet visas.
- **Inga CORS-huvuden.** Anrop från en webbsida på en annan domän blockeras av webbläsaren. Integrera från en server, eller länka till CAIA som egen sida. CAIA går inte att visa i en ram (iframe) på en annan sida: svaren bär `X-Frame-Options: DENY` och `frame-ancestors 'none'`.
- **Långsamt:** ett steg tar 20 till 280 sekunder. Sätt klientens timeout till minst 300 sekunder. En hel analys tar 10 till 15 minuter.

## Inloggning

Beror på hur installationen är satt upp (se [next/INSTALL.md](../next/INSTALL.md) steg 4):

- **Supabase:** skicka `Authorization: Bearer <access_token>` för en inloggad Supabase-användare som står i `CAIA_ALLOWED_EMAILS`. Listan tar adresser, hela domäner (`@kommun.se`) eller `*`. Ett konto som släpps in via en domän måste ha en bekräftad e-postadress. En integration loggar in ett eget tjänstekonto med e-post och lösenord mot Supabase (`POST <SUPABASE_URL>/auth/v1/token?grant_type=password` med `apikey: <SUPABASE_ANON_KEY>`) och förnyar token när den gått ut (normalt efter en timme). Anonyma konton släpps aldrig in. Ska tjänstekontot spara rapporter måste adressen också stå i databasens egen lista (`caia.allowed`, se `next/deploy/reports.sql`).
- **Gemensamt lösenord:** `POST /login` med formulärfältet `password` ger en sessionskaka; skicka den med i varje anrop. Kakan gäller i tolv timmar, skickas bara över https och slutar gälla när lösenordet byts. Fem fel från samma IP spärrar i tio minuter, och `/login` svarar då `429`.

CAIA kontrollerar Supabase-beviset själv: det ska vara signerat med ES256 av projektets nycklar, ha mottagaren `authenticated`, en utgångstid och ett användar-id, och vara högst 8 192 tecken. Bevis signerade med HS256 godtas bara om installationen har `SUPABASE_JWT_SECRET` satt. Nyckellistan sparas i fem minuter. Går den inte att hämta, och ingen nyckel från den senaste timmen finns kvar, svarar CAIA `503` med `Retry-After: 30`.

Utan giltig inloggning svarar varje `/api`-route `401` (inte inloggad) eller `403` (kontot finns men är inte tillåtet, eller adressen är inte bekräftad).

## Anropsgränser

Varje route som anropar en modell räknas: högst 20 anrop per minut och 150 per dygn, ändringsbart med `CAIA_RATE_LIMIT_PER_MIN` och `CAIA_RATE_LIMIT_PER_DAY`. Gränsen gäller per användare med Supabase och per IP-adress i lösenordsläge. IP-adressen läses ur `X-Forwarded-For` enligt `CAIA_TRUSTED_PROXIES` (antal proxyservrar framför appen, 1 om inget anges).

`/api/evidens/plan`, `/api/parameters` och de tre rapportvägarna anropar ingen modell och har en egen gräns med egen räknare: 30 per minut och 600 per dygn. Den går inte att ändra med en miljövariabel.

Över en gräns: `429` med huvudet `Retry-After: <sekunder>`. Räknarna finns i varje serverprocess för sig.

## Stegen i ordning

| # | Route | Modell | Tar | Svar |
|---|---|---|---|---|
| 1 | `/api/intake` | Opus 5.5 | 20–60 s | `{"status": "clarifying", "message"}` eller `{"status": "complete", "message", "profile_text", "profiles", "preamble"}` |
| 2 | `/api/emap` | Sonnet 5.5 | 30–90 s | `{"output"}`; med `"feedback": true` även `"reply"` |
| 3 | `/api/baslinje` | Sonnet 5.5 | 60–150 s | `{"output"}`; med `"feedback": true` även `"reply"` |
| 4a | `/api/evidens/plan` | ingen | direkt | `{"drivers": [{"number", "name"}]}` |
| 4b | `/api/evidens/part` | Opus 5.5 | 100–220 s | `{"number", "name", "text"}` |
| 4c | `/api/evidens/merge` | Opus 5.5 | 60–150 s | `{"output", "evidence", "corrected"}` |
| 4 | `/api/evidens` | Opus 5.5 | 160–280 s | `{"output", "evidence"}` (reserv när 4a ger noll drivare) |
| 5 | `/api/kalkyl` | Sonnet 5.5 | 60–180 s | se nedan |
| 6 | `/api/qa` | Opus 5.5 | 60–150 s | `{"output"}` |
| 7 | `/api/rapport` | Sonnet 5.5 | 60–180 s | `{"output"}` (markdown, slutar med kalkylmotorns tekniska bilaga) |

`"feedback": true` skickar sidan när användaren skriver i chatten vid stegets eget stopp. Servern lägger då kommentaren i en ram som ber modellen om ett kort svar och hela den uppdaterade versionen (`caia/feedback.py`), och delar svaret: `reply` går till chatten, `output` (bara versionen) till panelen och historiken. Är `output` tom står den tidigare versionen kvar. Utan flaggan svarar stegen som förut.

Tiderna är ungefärliga, uppmätta på referenspaketen i september 2026.

Alla stegen tar `{"history": [...]}`, och valfritt `"mode"`. Skillnaderna:

**Analysläge.** `"mode": "potential"` (standard, även när fältet saknas) bedömer vad en planerad åtgärd kan ge. `"mode": "uppfoljning"` följer upp en genomförd insats: varje steg får metodreglerna för uppföljning, och kalkylen redovisar vad som redan realiserats, vad som återstår och nyttan per bidragsår. Skicka samma läge i varje anrop i en analys, `evidens/plan`, `part` och `merge` inräknade; servern minns inget mellan anropen. Ett okänt läge ger `400`.

**1. intake.** Första anropet har användarens beskrivning som enda tur. Så länge `status` är `clarifying` ställer modellen följdfrågor: lägg `message` som `assistant`-tur och svaret som `user`-tur, och anropa igen. När `status` är `complete` finns åtgärdsprofilen i `profile_text` (text) och `profiles` (tolkad, kan vara tom om modellen avvek från mallen). Webbsidan stannar här och låter användaren godkänna profilen, och på samma sätt efter steg 2 och 3.

**4a till 4c. evidens.** `plan` läser drivarna ur det senaste steg i historiken som namnger dem: baslinjen, annars steg 2 (`emap`, på sidan Utsläppskällor). Kör sedan `part` en gång per drivare, gärna samtidigt, med `{"history", "driver": <number>}`. Skicka sist alla delar till `merge` med `{"history", "parts": [{"number", "text"}]}`. Varje drivare måste finnas med exakt en gång, högst tolv delar, och delarna får tillsammans vara högst 100 000 tecken. `merge` returnerar hela evidenssteget som `output` (det är den texten som går in i historiken), `evidence` (tolkad för visning: `drivers`, `sections`, `title`) och `corrected` (en lista med numren på de drivare merge rättade, till exempel `[2]`, tom om inget ändrades). Webbsidan stannar här en fjärde och sista gång: användaren godkänner antagandena. Ger `plan` en tom lista, kör `/api/evidens` i stället.

**5. kalkyl.** Svaret när CAIA:s egen beräkning gick igenom:

```json
{
  "deterministic": true,
  "output": "<markdown med tabeller och indata per drivare>",
  "headline": {"terr": 12.5, "cons": 3.1, "net": 14.2, "year": 2030},
  "span": {"net_lo": 8.0, "net_hi": 21.3, "avg_net": 9.6, "headline_year": 2030, "cum_net": 140, "target_year": 2030, "window": [2026, 2030], "mode": "potential"},
  "warnings": ["<text>", "..."],
  "kallmarkering": [{"drivare", "falt", "varde", "ursprung", "parametrar", "ok", "problem", "underlag", "godkant"}],
  "kallmarkering_md": "<avsnittet Talens ursprung>"
}
```

- `output` slutar med rubriken `**Teknisk bilaga: Beräkningssteg**`: motorns egen redovisning av varje mellansteg per år och scenario. `/api/rapport` letar upp den här texten i historiken och lägger bilagan sist i rapporten, ordagrant, så historiken som skickas till steg 7 måste innehålla kalkylsvaret följt av överlämningsraden ur `BRIDGE['kalkyl']`. Saknas den säger rapporten att ingen bilaga kunde bifogas.
- `headline` är medelscenariot i ton CO2e per år: i potentialläget målåret (`year` anger vilket, sedan 2026-10-13), i uppföljningsläget medelvärdet per år under `span.window` (utan `year`). Positivt tal betyder minskade utsläpp. `terr` är territoriella utsläpp, `cons` konsumtionsbaserade, `net` totalen med överlappet mellan dem avdraget.
- `span.net_lo`/`net_hi` är samma tal som `headline` (målåret eller medlet) i min- och maxscenariot. `avg_net` är medel per år under `window` i medelscenariot, `headline_year` är `headline.year` eller `null`. `cum_net` är ackumulerat till `target_year` i medelscenariot. `window` är de år medlet gäller: 2026–2030 i potentialläget, startår till målår i uppföljningsläget.
- I uppföljningsläget har `span` också `followup`:

  ```json
  "followup": {
    "year": 2025,
    "realised": {"min": 0.2, "med": 0.4, "max": 0.6},
    "remaining": {"min": 1.1, "med": 2.3, "max": 3.0},
    "allocation": [{"year": 2024, "amount": 150000.0, "share": 0.6, "min": 0.8, "med": 1.6, "max": 2.2}]
  }
  ```

  `year` är uppföljningsåret. `realised` är nettot till och med det året, `remaining` resten fram till målåret; tillsammans är de det ackumulerade nettot. `allocation` fördelar det ackumulerade nettot per bidragsår (`amount` i kronor, `share` årets andel av beloppet); en rad med `year: null` är nytta som inte gått att fördela. Listan är tom när kalkylen inte har några bidragsår.
- `warnings` ska visas bredvid talet. Listan kan innehålla: ökade utsläpp i medelscenariot, inga effekter alls, min och max lika, scenarier i fel ordning, en engångspost efter målåret, en angiven andel av startåret som aldrig används, och ett bidragsår som saknas bland bidragsraderna. Den kan också säga att åtgärden har effekt först efter målåret, så att både medel och ackumulerat är noll, med första året med effekt angivet. Bara i potentialläget: effekt som ligger utanför medelfönstret, effekt färre än hälften av fönstrets år, och målår efter fönstret. Sist kan den säga att ett eller flera tal avviker från baslinjen eller antagandena som godkändes. Vad varje varning betyder står i [METOD.md](METOD.md).
- `kallmarkering_md` är avsnittet *Talens ursprung* som färdig markdown. `/api/rapport` lägger inte in det i rapporten: klienten ska själv lägga det sist i rapporten, efter den tekniska bilagan. Webbsidan gör det, och `next/tools/run_batch.py` gör det med `caia.pipeline.with_kallmarkering`: rapporten utan avslutande blanktecken, en tom rad, avsnittet och en radbrytning. Finns inget avsnitt lämnas rapporten som den är.
- `ursprung` i `kallmarkering` är ett av `parameterbibliotek`, `kommundata`, `extern`, `antagande`, eller `null`. `ok: false` betyder att talet inte gick att belägga där det påstods komma ifrån, eller att det avviker från det som godkändes; `problem` säger varför. `godkant` är tom, eller säger hur talet avviker från baslinjen eller antagandena som godkändes i steg 3 och 4. Jämförelsen görs mot `history`: det senaste svaret i varje steg som följs av stegets överlämningsrad ur `BRIDGE`. En klient som inte skickar överlämningsraderna får ingen jämförelse, och avsnittet säger det.

Kunde modellens tal inte läsas eller inte godtas räknar språkmodellen själv, och svaret är `{"deterministic": false, "output", "kallmarkering": null, "kallmarkering_md"}` utan `headline`. Ett sådant resultat går inte att jämföra med ett deterministiskt och ska märkas för användaren. Webbsidan stannar inte efter kalkylen: steg 6 och 7 körs direkt.

## Övriga routes

| Route | Metod | Inloggning | Vad |
|---|---|---|---|
| `/api/parameters` | GET | ja | Parameterbiblioteket: `{"sections": [{"title", "rows": [...]}], "counts": {"lokal", "datafil", "schablon"}, "total", "editable": false}`. Varje rad har bland annat `id`, `beskrivning`, `enhet`, `value_used` och `provenance`, samt det sidan skriver ut i värdekolumnen: `value_display` (för en rad som läser en datafil talet i filen i stället för `LOOKUP`-uttrycket i `value_used`) och `value_note` (vad som lästes och ur vilken fil, annars tom). |
| `/api/reports` | POST | Supabase | Spara en rapport: `{"formatted_report": "<markdown, högst 300 000 tecken>", "action_name": "<högst 300>", "intake_summary": "<högst 50 000>", "key_metric": {"terr", "cons", "net", "year"}}`. `key_metric` ska vara kalkylens `headline`: bara `terr`, `cons` och `net` som ändliga tal och `year` som årtal godtas, annat ger `400`. En rad utan `year` är ett medelvärde per år. Utelämnas det läses talen ur rapporttexten och raden märks `source: "rapport"`. En tom rapport ger `400`. Svar: den sparade raden. |
| `/api/reports` | GET | Supabase | De 30 senaste egna rapporterna: `[{"id", "action_name", "key_metric", "created_at"}]`. |
| `/api/reports/<id>` | GET | Supabase | En egen rapport, hela raden. Okänt eller främmande id: `404`. |
| `/api/portfolj/atgarder` | POST | Supabase | Portföljens första steg: `{"ids": ["<rapport-id>", ...]}` (2 till 20 egna rapporter). Svar: `{"potter": [{"id", "namn", "baslinje", "ar", "kalla", "trend", "perspektiv", "anmarkning"}], "atgarder": [{"id", "namn", "skapad", "mode", "delar": [{"namn", "pott"}]}]}`. En rapport utan kalkylmotorns bilaga har `fel` i stället för `delar`. Två körningar av samma åtgärd ger `422`. |
| `/api/portfolj` | POST | Supabase | Räkna portföljen: `{"ids": [...], "potter": {"<id>": ["<pott-id>" eller null, en per del]}, "mal_for": {"<id>": ["<id för åtgärder som är verktyg för målet>"]}}`. Svar: `{"markdown", "warnings"}`. Okänd pott, en rapport utan bilaga, blandade lägen eller en målrelation som inte går att räkna ger `422` med förklaring. |
| `/login`, `/logout`, `/` | | | Webbsidan. |

`/api/reports` och `/api/portfolj` finns bara med Supabase; i lösenordsläge svarar de `501`.

## Statuskoder

| Kod | Betyder | Gör så här |
|---|---|---|
| 200 | Klart | |
| 400 | Anropet har fel form (inte JSON-objekt, fel i `history`, okänd drivare, okänt läge, för lång tur eller historik, för många eller för långa delar till merge) | Rätta anropet; `error` säger vad. |
| 401 | Inte inloggad, eller token har gått ut | Logga in eller förnya token. |
| 403 | Kontot är inte tillåtet (`CAIA_ALLOWED_EMAILS`), eller adressen är inte bekräftad | Be den som driftar CAIA lägga till adressen, eller bekräfta kontot via länken i mejlet. |
| 404 | Okänd route eller rapport | |
| 405 | Fel metod | |
| 413 | Anropet är större än 2 MB | |
| 422 | Portföljen går inte att räkna (`error` säger varför). `evidens/plan` och `evidens/merge`: fler än 12 drivare, en del som saknas eller finns två gånger, eller en rättelse i merge som inte går att läsa. (`evidens/part` svarar `502` för motsvarande fel.) | Dela åtgärden eller kör steget igen. |
| 429 | Över en anropsgräns, eller för många felaktiga lösenord mot `/login` | Vänta `Retry-After` sekunder. |
| 500 | Oväntat fel, eller en kommunprofil som inte går att läsa. `error` har ett fel-id som står i serverloggen. | Kör steget igen; ge fel-id:t till driften om det återkommer. |
| 501 | Rapportroutes utan Supabase | |
| 502 | Modelltjänsten svarade fel, fel nyckel, slut på krediter, modellens svar gick inte att använda, eller Supabase gick inte att nå. Vid sparande också: databasen godtog inte kontot (adressen saknas i `caia.allowed` eller är inte bekräftad). | `error` säger vilket. Oftast: kör steget igen. Nekar databasen kontot hjälper inget omförsök; driften lägger till adressen. |
| 503 | Installationen saknar inloggning (varken Supabase eller lösenord), eller inloggningen kan inte kontrolleras just nu (Supabases nyckellista går inte att hämta; svaret har `Retry-After: 30`) | Det första är ett konfigurationsfel hos driften. Det andra går över: vänta och försök igen. |
| 504 | Plattformens tidsgräns (Vercel 300 s) | Kör steget igen. |

CAIA gör själv ett omförsök när modelltjänsten svarar med 429 eller 5xx inom en minut, och när anslutningen bryts, men aldrig efter en timeout.

Alla svar bär `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` och en Content-Security-Policy. Svar från `/api/` bär dessutom `Cache-Control: no-store`.

## Kostnad

Kostnaden är modellanropen hos OpenRouter. Listpris: Opus 5.5 4 USD per miljon tokens in och 20 ut, Sonnet 5.5 2 respektive 10.

- En analys med två drivare är nio modellanrop och kostar typiskt 2–3 USD. Taket, om varje steg använder hela sin gräns, är omkring 4 USD.
- Varje drivare utöver två lägger till ett Opus-anrop, omkring 0,5 USD.
- Varje rättelse vid en grind kör steget en gång till och kostar därefter.
- Gränsen 150 anrop per dygn motsvarar ungefär tio analyser, alltså i storleksordningen 25–30 USD per användare och dygn som mest.

Sätt en kreditgräns på OpenRouter-nyckeln; det är den enda hårda gränsen.
