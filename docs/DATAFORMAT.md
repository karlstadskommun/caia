# Kommunens datafiler

CAIA (Climate Action Impact Analysis) läser en kommuns egna data ur mappen `data/` i kommunprofilen (`next/src/caia/kommuner/<slug>/data/`, eller `$CAIA_KOMMUN_DIR/data/`). Vilken fil som är vilken källa står i parameterbibliotekets sektion 12, kolumnen `Filnamn`. Filnamnen får alltså vara vad som helst, men de måste stå i registret.

Varje fil som finns blir ett sammandrag i datakontexten som skickas med till agenterna. En fil som saknas ger inget sammandrag, och parametrar som pekar på den (`LOOKUP(DATA_...)`) använder sitt standardvärde. Kör `python -m caia.kommun` för att se vilka filer som hittas.

Sidans parameterlista (knappen **Parametrar**) visar talet i filen för en parameter vars uttryck pekar på en enda ruta, och skriver under talet vad som lästes. Det gäller tre former: `LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", <år>)`, `LOOKUP(DATA_ENERGY_RESIDENTIAL, "<kolumn>", "<Kategori>")` och `LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "<kolumn>", "coicop=<kod>")`, var och en med ett valfritt `/ <Parameter_ID eller tal>` eller `* <Parameter_ID eller tal>` efter. Kolumnen ska heta som i filen: står det ett annat ortsnamn i uttrycket än i exporten visas inget tal. Faktorn efter `/` eller `*` ska vara ett tal skrivet på ett enda sätt (`1000` eller `97 233`, inte `1.000` eller `97,233`, som kan läsas både som tusental och som decimaler) eller en parameter med kommunens eget värde som inte är en procentsats. En schablon som nämnare ger inget tal, eftersom resultatet annars skulle stå som lokalt. Alla andra uttryck visas som "Läses ur datafilen vid varje analys". Rapportens avsnitt *Talens ursprung* visar samma tal och rad när ett tal hänvisar till parametern. Det här styr bara vad listan och avsnittet visar. Analysen läser filernas sammandrag som förut.

Alla textfiler ska vara UTF-8. Koden läser dem som UTF-8 och stannar med ett fel om de inte är det.

## Källorna CAIA läser

| Källa i registret | Format | Vad CAIA läser |
|---|---|---|
| `DATA_EMISSIONS_TOTAL` | CSV, semikolon | Territoriella utsläpp per sektor och år |
| `DATA_ENERGY_RESIDENTIAL` | CSV, komma | Energianvändning i bostäder per hustyp |
| `DATA_CONSUMPTION_FOOTPRINT` | JSON | Konsumtionsfotavtryck per kategori |
| `DATA_HOUSEHOLD_TIME_SERIES` | JSON | Hushållens konsumtionsutsläpp över tid |
| `DATA_MUNICIPAL_ORG` | JSON | Kommunkoncernens egna konsumtionsbaserade utsläpp |
| `DATA_CITIZEN_SURVEY` (får ha ett år efter sig, `DATA_CITIZEN_SURVEY_2024`) | CSV, komma | Svarsfördelning i en medborgarundersökning |

Listan finns i koden som `READ_SOURCES` i `next/src/caia/data/parameters.py`. En källa som inte står där läses inte, även om filen ligger i `data/`. Så är det med resvaneundersökningen (`DATA_TRAVEL_SURVEY`): den är en PDF, och talen ur den skrivs av i sektion 2 med tabell och sida. Lägg inte PDF:en i `data/`.

### DATA_EMISSIONS_TOTAL

Exporten från Nationella emissionsdatabasen (RUS/SMHI), "Emissioner av växthusgaser totalt", en kommun. Exporten kommer i Latin-1 och måste konverteras till UTF-8 först:

```bash
iconv -f latin1 -t utf-8 export.csv > data/kommunrapport_vaxthusgaser_totalt.csv
```

Layout, semikolonseparerad:

1. Fem rader metadata (rapportnamn, enhet och så vidare). De hoppas över.
2. En rad där de fyra första fälten är tomma och resten är årtal.
3. En rubrikrad som börjar med `Huvudsektor`.
4. En rad per sektor: `Huvudsektor;Undersektor;Län;Kommun;<värde år 1>;<värde år 2>;...`, ton per år med decimalkomma.

Raden `Alla;Alla` blir "Alla sektorer (totalt)". Agenterna får de tre senaste åren per sektor.

### DATA_ENERGY_RESIDENTIAL

```
Kategori,MWh
Småhus,318462
Flerbostadshus,323555
```

Källa: SCB, Kommunal och regional energistatistik, tabellen *Slutanvändning (MWh), efter län och kommun, förbrukarkategori samt bränsletyp* (EN0203A, `SlutAnvSektor`), förbrukarkategorierna småhus, flerbostadshus och fritidshus, alla bränsletyper. Raden `Totalt` är summan av de tre, och `Per person` är summan delad med folkmängden samma år i MWh. Karlstads fil har året 2022 (folkmängd 96 466); avstämt mot SCB:s öppna API 2026-11-05. Parameterbibliotekets rad `HEAT_energy_use_percap_res` anger året 2022 (rättat 2026-11-08; den sa 2023). 2023 års tal är 322 455, 342 008 och 1 854 MWh.

### DATA_CONSUMPTION_FOOTPRINT

En JSON-lista, ett objekt per konsumtionskategori, som exporten från Konsumtionskompassen:

```json
[{"coicop": "07.D", "label": "direkta utsläpp från fordonsanvändning", "per100sek": 9.24, "Karlstad": 666.4, "Värmlands län": 842.9, "Sverige": 658.6}]
```

Kommunens egen kolumn hittas på `ort` i `kommun.toml`: för `ort = "Göteborg"` måste nyckeln heta `"Göteborg"`. Värdet är kg CO2e per person och år.

### DATA_HOUSEHOLD_TIME_SERIES

En JSON-lista, ett objekt per region, årtal som nycklar:

```json
[{"2019": 5887.6, "2020": 4752.5, "region": "Karlstad", "code": "1780"}]
```

Agenterna får de tre senaste åren per region, kg CO2e per person och år.

### DATA_MUNICIPAL_ORG

En JSON-lista, eller ett objekt med listan under `"data"`, ett objekt per kategori:

```json
[{"Huvudkategori": "Energi", "Kategori": "El", "Kg CO2e": 10217811}]
```

Rader utan `Kategori` eller utan ett tal i `Kg CO2e` hoppas över. Agenterna får tonnen grupperade per huvudkategori.

### DATA_CITIZEN_SURVEY

```
Question,Response_Option,Percentage
Meat_Frequency,Flera gånger i veckan,52.0
```

Året i rubriken som agenterna ser kommer ur registrets kolumn `År`.

## Utsläppspotter (`potter.toml`)

Portföljen räknar åtgärder som verkar på samma utsläpp tillsammans, per utsläppspott. Potterna står i profilens `potter.toml`, bredvid `kommun.toml`. Filen är valfri: utan den räknar portföljen varje åtgärd för sig. `python -m caia.kommun` listar potterna.

```toml
[[pott]]
id = "husbyggnad"                 # små bokstäver, siffror, - och _; byt aldrig id på en befintlig pott
namn = "Kommunens husbyggnad"
baslinje = 17200                  # ton CO2e per år det år som står i ar
ar = 2022
trend = 0                         # valfri: förändring per år utan nya åtgärder, -0.02 = två procent mindre
perspektiv = "konsumtionsbaserat" # valfri
kalla = "Var talet kommer ifrån"
anmarkning = "Valfri: osäkerheter i källan"
```

Potterna får inte överlappa varandra: en pott inuti en annan räknar samma ton två gånger. En fil med fel (saknad källa, en baslinje som inte är ett tal större än noll, ett id som finns två gånger) gör att portföljen säger att registret inte går att läsa.

## Karlstads övriga filer

Tre filer i Karlstads `data/` står inte i registret och läses inte: `fördelning-av-utsläpp-per-konsumtionskategori.json`, `sammanräknade-utsläpp-i-valda-konsumtionskategorier.json` och `utsläpp-och-befolkning-i-karlstads-deso.json`. De ligger kvar som rådata från Konsumtionskompassen.
