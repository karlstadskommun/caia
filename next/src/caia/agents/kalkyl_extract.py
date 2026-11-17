"""Kalkyl extraction agent.

Instead of doing arithmetic in the prompt, this agent reads the prior Baslinje &
BAU and Evidens & antaganden analysis and emits a STRUCTURED JSON model. The
deterministic engine (caia.calc) then computes the emissions. This is what moves
the math out of the LLM.

Returns a dict (CalcModel-shaped) or None if extraction/parse fails — the caller
falls back to the legacy LLM-math kalkyl on None.
"""
from __future__ import annotations

import json
import re

from ..api_client import complete
from ..kallmarkering import kommundata_block
from ..kommun import active
from ..mode import POTENTIAL, UPPFOLJNING
from .uppfoljning import for_mode

_HEAD = r"""Du är extraktionssteget i en klimatkalkyl. Din ENDA uppgift är att
omvandla den föregående analysen (Baslinje & BAU + Evidens & antaganden) till en
strukturerad numerisk modell som ett Python-program sedan räknar på. Du gör INGEN
egen matematik och skriver ingen prosa.

Svara med ENBART ett JSON-objekt (inga kodfences, ingen text före/efter) med formen:

{
  "action_name": "<åtgärdens namn>",
  "target_year": 2030,
  "key_years": [2026, 2030],
  "drivers": [
    {
      "name": "<drivarens namn>",
      "baseline_year": 2023,
      "a0": <aktivitetsnivå per år, tal>,
      "a0_unit": "<t.ex. km/år, kWh/år, ton/år>",
      "ef0": <emissionsfaktor i kg CO2e per aktivitetsenhet, tal>,
      "ef0_unit": "kg CO2e/<enhet>",
      "g_a":  {"min": <andel/år>, "med": <>, "max": <>},
      "g_ef": {"min": <andel/år>, "med": <>, "max": <>},
      "delta_a":  {"min": <andel>, "med": <>, "max": <>},
      "delta_ef": {"min": <andel>, "med": <>, "max": <>},
      "terr": <0..1>, "cons": <0..1>, "overlap": <0..1>,
      "ramp": {"start_year": 2027, "full_effect_year": 2030, "profile": "linjär",
               "end_year": {"min": 2026, "med": 2028, "max": 2030}},
      "kallor": {
        "a0":       {"ursprung": "<se KÄLLOR>", "parametrar": ["<Parameter_ID>"], "kalla": "", "not": ""},
        "ef0":      {...}, "g_a": {...}, "g_ef": {...}, "delta_a": {...}, "delta_ef": {...}
      }
    }
  ]
}

"ramp.end_year" är valfritt. Utelämna det när effekten består till målåret.

KÄLLOR (obligatoriskt, för varje drivare och vart och ett av a0, ef0, g_a, g_ef, delta_a
och delta_ef): ange var talet kommer ifrån, så som analysen redovisar det. "ursprung" är
exakt ett av:
- "parameterbibliotek": talet står i parameterbiblioteket. Ange dess Parameter_ID i
  "parametrar" (se <parameter_ids>). Är talet uträknat ur flera parametrar, ange alla och
  skriv uträkningen i "not" (t.ex. "invånare × km per person").
- "kommundata": kommunens egna värden eller datafiler, se <kommundata>. Ange namnen därifrån
  i "parametrar".
- "extern": en namngiven källa utanför biblioteket (rapport, studie, webbsida). Skriv källan
  i "kalla".
- "antagande": analysens eget antagande eller uppskattning. Skriv kort varför i "not".
Hitta aldrig på ett Parameter_ID och låna aldrig ett namn för att ett tal ska se förankrat ut.
Vet du inte var talet kommer ifrån, eller står det inte i biblioteket: välj "antagande".
En trend som är 0 för att analysen inte nämner någon trend är ett antagande.
Bygger a0 på en omfattning som är markerad som antagen (ANTAGANDE i åtgärdsprofilens
Omfattning eller i baslinjens A0), är ursprunget "antagande" och "not" börjar med
"Antagen omfattning", även när andra faktorer i uträkningen kommer ur biblioteket.
Varje "not" är högst en mening. Ska en not säga flera saker (att omfattningen är antagen,
uträkningen, att värdet är scenariernas största), skriv alla i samma mening, med
"Antagen omfattning" först; stryk ingen av dem.

ENHETSKONTRAKT (måste följas — normalisera vid behov):
- a0 = aktivitet per år i fysisk enhet. ef0 = kg CO2e PER aktivitetsenhet.
  (Så baslinjeutsläpp = a0 * ef0 i kg/år.) Om analysen anger EF i ton, gång:a med 1000.
- g_a / g_ef = årlig andelsförändring i BAU (0.01 = +1%/år, -0.02 = -2%/år).
- delta_a / delta_ef = åtgärdens andelsförändring vs BAU vid full effekt
  (NEGATIVT = minskning; -0.10 = 10% mindre). min/med/max = försiktigt/troligt/optimistiskt.
- terr/cons/overlap i [0,1]. overlap <= min(terr, cons).
  Regel: hushålls-/verksamhetsenergi => konsumtionsbaserat (terr~0.05, cons~1.0, overlap~0.05).
  Bilar i kommunen => både territoriellt och konsumtion (terr~1.0, cons~1.0, overlap~1.0).
- ramp: när effekten startar och när full effekt nås. profile: "linjär" | "s-formad" | "stegvis".
  Rampen går alltid till full effekt, 100 %. Når adoptionen i analysen inte 100 % (kraven följs
  i 60 % av projekten, hälften av hushållen byter), lägg taket i delta per scenario:
  delta_ef = minskningen × adoptionens tak. Rampen bär bara takten, aldrig taket.
- ramp.end_year (valfritt, min/med/max): sista året åtgärden gör skillnad mot BAU. Används
  vid EFTERHANDSUTVÄRDERING när analysen säger att BAU "ändå hade gjort samma sak, men
  senare" (tidigareläggning: fossilfrimål, utrangering, nationella krav). Lägg det
  kontrafaktiska ikapp-året här, per scenario (ange alla tre; ett scenario som saknas
  tolkas som "BAU hinner aldrig ikapp"), och sätt g_a till den BAU-trend som gäller
  UTÖVER ikapp-bytet (ofta 0). Lägg ALDRIG tidigareläggningen i g_a: motorn använder bara
  g_a.med, så spridningen försvinner och effekten avtar exponentiellt i stället för att upphöra.

RÄCKVIDD OCH KEDJOR (informations-, utbildnings- och möjliggörande åtgärder):
- a0 är HELA den berörda populationens aktivitet i BAU (t.ex. alla nådda personer × 1, alla
  m² som byggs per år). Räckvidd, adoption och attribution är INTE en ökning av aktivitet.
  delta_a > 0 betyder att åtgärden ÖKAR utsläppen; sätt det bara när det är avsikten
  (t.ex. tillkommande el). Uttryck i stället kedjan som delta_ef (eller delta_a < 0):
  delta = -(andel som nås × andel som ändrar × minskning × attribution), per scenario.
- Skiljer sig antalet nådda mellan scenarierna: sätt a0 till medelvärdet och skala
  min/max-delta med kvoten (min-nådda / medel-nådda respektive max / medel).
"""

# The schema refuses a delta below -1, and the rule above produces one as soon
# as the max scenario needs more than the whole medel baseline. On a case where
# the baseline is the replaced amount itself (21,6 ton, max 60), four
# extractions on 2026-10-13 gave delta_a.max = -2,78 in two (refused, so the
# LLM kalkyl took over), no JSON in one, and in one a band rescaled to end at
# -1, which halved the medel result (108 ton). With the rule four of four gave
# the result the assumptions give by hand: 216 ton, 48 to 840.
_FLOOR = r"""- Ingen delta får bli mindre än -1 (-100 %): en aktivitet eller en emissionsfaktor kan inte
  bli mindre än noll.
  Hamnar ett scenario där med regeln ovan (vanligast när mängden som åtgärden ersätter eller
  undviker är hela a0 i medel och större i max), räkna i stället alla tre scenarierna mot den
  största mängden: sätt a0 till scenariernas STÖRSTA mängd och delta till varje scenarios
  andel av den (200, 500 eller 800 ton ersatt: a0 = 800, delta_a min -0.25, med -0.625,
  max -1). Bär scenarierna också ett spann i emissionsfaktorn, sätt även ef0 till sitt högsta
  värde och räkna andelarna mot a0 × ef0. Klipp aldrig ett scenario till -1 för att det ska
  rymmas: då får max-scenariot medelscenariots resultat. Skriv i "not" för a0 (och ef0) att
  värdet är scenariernas största.
"""

# With deeper reasoning the extraction more often picks a base of its own for a
# driver whose assumptions are written in another quantity than its baseline:
# the reuse package's handling driver (approved 2 000 tonkm × 0,15 kg) came out
# as 75 ton × 24 kg, 75 ton × 4,5 kg, or split in two, with trends weighed
# together. The result was the same each time, but the numbers were no longer
# the approved ones, and the comparison in caia.godkant marked them: 11 of 36
# runs on 2026-10-13, none of them a misreading. With the rule: 0 of 12.
_BASE = r"""
BASLINJEN (a0, ef0, g_a, g_ef):
- a0 och ef0 är baslinjens A0 och EF0 för drivaren, och g_a/g_ef dess BAU-trender, så som de
  godkändes. Normalisera bara enheten (t.ex. ton till kg). Beskriver antagandena effekten i en
  annan storhet än baslinjen (t.ex. kg CO2e per ton material när A0 står i tonkm), byt inte bas
  och väg inte ihop egna trender: räkna om effekten till en andel av a0 × ef0 och lägg den i
  delta, även när andelen blir stor (delta_a = 12 betyder +1 200 %).
- Undantag: reglerna om räckvidd och om delta under -1 ovan säger hur a0 sätts i de fallen, och
  en baslinje som anger 0 eller saknar värde följer REGLER nedan.
"""

# The contract above says terr/cons/overlap in [0,1], and the evidens prompt
# lets Konsumtion_faktor be 1.2. With deeper reasoning the extraction took the
# contract at its word: an approved 1.15 (the fuel's upstream part on top of
# the exhaust) became 1.0 in 8 of 8 runs on the tjänstebilar package
# (2026-10-13), 74 ton in 2030. With the rule: 1.15 and 88,5 to 88,7 ton in
# 8 of 8.
_FACTORS = r"""
KLIMATFAKTORER (terr, cons, overlap):
- Anger evidenssteget Territoriell_faktor, Konsumtion_faktor och Overlap_faktor för drivaren,
  använd dem som de står. Konsumtion_faktor får vara större än 1 (t.ex. 1.15 när bränslets
  uppströmsled räknas ovanpå avgasutsläppen): sänk den inte till 1. Intervallet [0,1] och
  tumreglerna i enhetskontraktet gäller när analysen inte anger faktorerna.
"""

# Potential mode only (the follow-up block has its own lifetime rules). Until
# 1.1 a forecast booked the whole manufacture of equipment the year it was
# bought: tjänstebilar's net in 2030 fell from 116 to 15 ton when the
# extraction began to count the cars' manufacture, with the territorial
# benefit unchanged at about 120 (2026-11-09). Henric 2026-11-10: write it
# off over the lifetime, as the follow-up already does. In the 1.1 reference
# run two of five readouts took the fleet's renewal cycle ("förnyelse på cirka
# 3 år") as the cars' lifetime, which put the whole manufacture back in 2030
# (net 15 ton again); hence the sentence on what a lifetime is not.
_LIFETIME = r"""
UTRUSTNING SOM TILLVERKAS (lifetime):
- En drivare som räknar tillverkning eller byggande av utrustning som används i flera år
  (fordon, batterier, maskiner, laddpunkter, solceller) och som ökar utsläppen får
  "lifetime": {"min", "med", "max"}, utrustningens livslängd i år enligt analysen, KORTAST i
  min (en kortare livslängd ger varje år en större andel). Kalkylen skriver av tillverkningen
  jämnt över livslängden, så att varje år bär en årlig andel av den i stället för att hela
  hamnar det år den köps. Ange källan i "kallor"."lifetime"; saknar analysen livslängd, gör
  ett rimligt antagande och skriv det i "not".
- Livslängden är hur många år utrustningen används innan den skrotas, inte hur länge
  kommunen eller hushållet behåller den. En förnyelsecykel, en leasingtid eller en
  avskrivningstid i bokföringen är inte livslängden: en tjänstebil som byts efter tre år
  rullar vidare hos nästa ägare, så livslängden är bilens.
- Köps utrustningen löpande (bilar som byts varje år): en årlig drivare med det som köps per
  år som a0, som förut. Köps den en gång (laddpunkter som byggs ett visst år): "kind":
  "engång", "year" = året den köps, a0 = mängden, ef0 = kg CO2e per enhet och delta_a = 1
  när hela mängden tillkommer genom åtgärden, utan ramp.end_year. Lägg aldrig en
  engångsinvestering som en årlig drivare: då räknas den en gång per år.
- Ingen lifetime på en drivare som minskar utsläppen, eller på drift, el och bränsle.
"""

_TAIL = r"""
REGLER:
- Använd talen från analysen. Saknas ett värde: gör ett tydligt rimligt antagande utifrån
  parameterbiblioteket/storleksordning — sätt ALDRIG a0 eller ef0 till 0.
- En drivare per utsläppsdrivare som åtgärden påverkar. Hoppa över opåverkade drivare.
- Inget annat än JSON-objektet i svaret."""

SYSTEM_PROMPT = _HEAD + _FLOOR + _BASE + _FACTORS + _LIFETIME + _TAIL
# The follow-up prompt has the factor rule but not the other two. Measured
# 2026-11-08 on four approved follow-up analyses (omgång 5 of the driftsmedel
# packages), four extractions each: without the rule, an approved
# Konsumtion_faktor 1.1 (anläggningens diesel) became 1.0 in every extraction
# at medium and at high; with it, see docs/DECISIONS.md 2026-11-08. _FLOOR and
# _BASE are not measured there, and the follow-up block already tells a
# one-off post to use the highest values.
SYSTEM_PROMPT_UPPFOLJNING = _HEAD + _FACTORS + _TAIL


def _clean(s: str) -> str:
    """Best-effort cleanup of near-JSON: strip // and /* */ comments and
    trailing commas, outside string literals only.

    This used to be three regexes over the whole text. The // one ate every
    "https://..." source URL from the colon onward, which turned a model reply
    with one trailing comma and one cited source into unparseable JSON, and
    the pipeline fell back to LLM math for a reply that was fine."""
    n = len(s)

    def past_ws_and_comments(j: int) -> int:
        """Index of the next char that is neither whitespace nor a comment."""
        while j < n:
            if s[j] in ' \t\r\n':
                j += 1
            elif s.startswith('//', j):
                nl = s.find('\n', j)
                j = n if nl < 0 else nl
            elif s.startswith('/*', j):
                end = s.find('*/', j + 2)
                j = n if end < 0 else end + 2
            else:
                break
        return j

    out: list[str] = []
    i = 0
    in_str = esc = False
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif s.startswith('//', i):
            nl = s.find('\n', i)
            i = n if nl < 0 else nl
        elif s.startswith('/*', i):
            end = s.find('*/', i + 2)
            i = n if end < 0 else end + 2
        elif ch == ',':
            # Trailing if the next real token closes the container. Comments
            # in between are stripped on their own turn through the loop.
            j = past_ws_and_comments(i + 1)
            if j < n and s[j] in '}]':
                i += 1  # drop the comma, keep what follows
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def _balanced_objects(text: str):
    """Yield every brace-balanced {...} substring (handles strings/escapes).

    String state is tracked only inside an object: outside one, a quote is
    prose ('kallas "stegvis"') and must not hide the JSON that follows. A
    stray '}' in prose is ignored instead of driving depth negative, which
    used to swallow every object after it."""
    depth = start = 0
    in_str = esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"' and depth > 0:
            in_str = True
        elif ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth > 0:
            depth -= 1
            if depth == 0:
                yield text[start:i + 1]


def _parse_json(text: str):
    """Extract the calc-model JSON from the model reply, tolerant of fences,
    surrounding prose, comments and trailing commas. Prefers the object that
    actually looks like the model (has 'drivers')."""
    text = re.sub(r'```(?:json)?', '', text).strip()
    candidates = []
    for chunk in _balanced_objects(text):
        for attempt in (chunk, _clean(chunk)):
            try:
                obj = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                candidates.append(obj)
                break
    # prefer a candidate that has drivers; else the largest dict
    for obj in candidates:
        if obj.get('drivers'):
            return obj
    return max(candidates, key=lambda o: len(json.dumps(o)), default=None)


# The history ends with the pipeline's bridge turn, "Fortsätt med kalkyl och
# tidsprofil", which asks for the prose kalkyl. On 2026-09-23 Sonnet 5 obeyed
# that last turn over the system prompt in 2 of 7 extractions on one lövblåsare
# history and wrote a full markdown kalkyl (0 of 16 on four other histories).
# That evidens had locked a method rule the schema cannot hold (half weight on
# the end year), which is exactly when doing the math yourself looks helpful.
# The prose parses as nothing and the step falls back to the LLM kalkyl.
# Do not tell it to skip calculating: a first draft said "utan egna
# beräkningar", reasoning dropped from ~80 s to ~11 s, and 4 of 7 replies broke
# the unit contract (ef0 per 1000 litres), a silent 1000x headline.
EXTRACT_TURN = (
    "Extrahera nu den numeriska modellen. Själva svaret ska vara ENBART "
    "JSON-objektet enligt systemprompten, utan tabeller eller prosa. Följ "
    "enhetskontraktet noga: ef0 i kg CO2e per EN aktivitetsenhet. Kan en "
    "metodregel i analysen inte uttryckas i schemat, välj närmaste värde som "
    "går att uttrycka."
)


def extraction_messages(conversation_history: list[dict]) -> list[dict]:
    """The history with the extraction request as the final user turn."""
    messages = [dict(m) for m in conversation_history]
    if messages and messages[-1].get('role') == 'user':
        messages[-1]['content'] = f"{messages[-1]['content']}\n\n{EXTRACT_TURN}"
    else:
        messages.append({'role': 'user', 'content': EXTRACT_TURN})
    return messages


def run_kalkyl_extract(conversation_history: list[dict],
                       mode: str = POTENTIAL) -> dict | None:
    """Extract the structured calc model. Returns dict or None on failure."""
    # 12000 + high headroom = 36000, in both modes since 2026-11-08. At 6000 with medium headroom
    # (18000 in all) Sonnet 5 hit the ceiling in 2 of 9 full runs on
    # 2026-09-23 (lövblåsare, batterilager), both with three drivers, one on
    # each evidens variant. The JSON itself is ~1.5k tokens; the rest is
    # reasoning. A clipped extraction falls back to the LLM kalkyl, which took
    # 334 s in one of those runs, past Vercel's limit.
    base = SYSTEM_PROMPT_UPPFOLJNING if mode == UPPFOLJNING else SYSTEM_PROMPT
    system = for_mode(active().render(base) + "\n\n" + kommundata_block(),
                      "kalkyl_extract", mode)
    data = _parse_json(complete("kalkyl_extract", system,
                                extraction_messages(conversation_history), 12000,
                                mode=mode))
    if not isinstance(data, dict) or not data.get('drivers'):
        return None
    return data
