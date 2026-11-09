Evidens & antaganden för åtgärd: Öka och bibehålla hållbara resvanor under och efter byggtiden av resecentrum (profil 1: Mobility management under byggtiden av Karlstads resecentrum, profil 2: Bibehållna hållbara resvanor efter öppningen av resecentrum)

Kort om detta steg
Underlaget är de godkända EMAP- och Baslinje & BAU-analyserna för de två åtgärdsprofilerna. För varje drivare anger jag vilka parametrar åtgärden påverkar. För dem sätter jag antagandespann (min/medel/max) med källor, kvalitet och lokaliserbarhet. Delbedömningarna per drivare har samordnats så att samma beteendeeffekt inte räknas två gånger. Kalkyl & Tidsprofil-agenten använder antagandena för att räkna ton CO₂e.

Underlag från tidigare steg
Sex drivare ingår, alla i transportsektorn. Drivare 1–3 hör till byggtiden 2025–2028 och drivare 4–6 till tiden efter öppningen 2029–2032.

Störst effekt får de territoriella drivarna, Drivare 1 (Bilkörning till och genom centrum) och Drivare 4 (Pendling till centrum inom kommunen). Där körs bilkilometrarna inom kommunen.

Två BAU-trender är viktiga:
- **Under bygget** ökar bilkörningen med +1,5 %/år (medel) på grund av störningarna.
- **Efter öppningen** är bilpendlingen oförändrad (0 %/år, medel), eftersom resecentrums egen effekt redan ingår i BAU.
- **Emissionsfaktorn** sjunker med −5 %/år (medel) genom elektrifieringen, från 0,14 till ca 0,098 kg CO₂e/fordonskm 2030. Det minskar nyttan per flyttad kilometer.

De viktigaste dataluckorna är antal nådda, inpendlarnas fördelning (antal, bilandel och sträcka inom och utanför kommunen) och kommunanställdas resor. Alla drivare har därför låg datakvalitet.

Påverkade drivare och parametrar
Alla sex drivare påverkas via ΔA (Shift, bil till buss, tåg, cykel och gång). Ingen drivare har ΔEF, utom att Drivare 6 (Kommunens tjänsteresor) använder en egen låg emissionsfaktor för kommunens bilar. Effekten räknas som en kedja: andel som nås, andel som ändrar sig, hur mycket de ändrar sig och åtgärdens andel utöver BAU (attribution eller additionalitet).

Fördelningen mellan drivarna är följande:
- **Karlstadsbornas konsumtionsbaserade utsläpp** bärs av de territoriella drivarna, Drivare 1 och Drivare 4, via Konsumtion_faktor. Överlappet är fullt eftersom kilometrarna körs inom kommunen.
- **Inpendlarnas sträcka utanför kommunen** räknas i Drivare 2 (byggtid) och Drivare 5 (efter öppning). Den hör till hemkommunernas konsumtionsbaserade utsläpp och redovisas som separat regional nytta.
- **Kommunanställda:** Drivare 3 redovisas som en "varav"-post inom Drivare 1 och summeras inte. Drivare 6 omfattar bara tjänsteresor, eftersom de anställdas pendling redan ingår i Drivare 4. Drivare 6 räknas därför additivt.

Ingen drivare lämnas opåverkad.

## Antaganden per drivare

Drivare 1: Körsträcka med personbil till och genom centrum (inom kommunen)
  Mekanism: Shift, ΔA enligt EMAP. Busprioritering, tillfälliga cykel- och gångstråk, omledning och riktad information gör att en del av resenärerna inte väljer bilen under bygget. Fordonskilometrarna blir därmed lägre än i BAU, där störningarna driver upp bilandelen (g_A medel +1,5 %/år). Effekten räknas som en kedja: andel som nås, andel av dem som ändrar sig, hur mycket de ändrar sig och åtgärdens andel av förändringen.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 0.6
    Overlap_faktor: 0.6
    Motivering_faktorer: Alla kilometrar körs inom kommunen och räknas därför fullt territoriellt. Ungefär 60 % av A0 (ca 4,4e7 av 7,5e7 fordonskm) är Karlstadbornas egna resor. Drivaren bär därmed hela Karlstads konsumtionsbaserade effekt för profil 1. Resten är inpendlares körning inom kommunen, som hör till hemkommunernas konsumtion. Inpendlarnas sträcka utanför kommunen räknas i Drivare 2. Den konsumtionsbaserade delen ligger helt inom den territoriella, så överlappet är 0.6. Konsumtion_faktor bygger på tailpipe-EF utan uppströmspåslag.

  Parameter: reach
    Antagande_min: 0,45 (45 % av bilresenärerna till och genom centrum nås av information, skyltning eller omledning)
    Antagande_med: 0,60 (60 % nås)
    Antagande_max: 0,75 (75 % nås)
    Enhet: andel av bil-fordonskm i målgruppen
    Tidsaspekt: per år 2025–2028. Ramp: 50 % effekt 2025 (uppstart), 100 % 2026–2028. Ingen effekt efter 2028. Gemensamt förlopp för Drivare 1–3.
    Källor: KOMM_typical_reach_share_general (50–70 %). Målgruppen 30 000–40 000 resenärer per vardag kommer från åtgärdsprofilen.
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Räckvidden kan ligga över en vanlig kampanj, eftersom bilister som kör genom byggområdet möter omledning och skyltning fysiskt. Räckvidd betyder ändå inte engagemang. Räckvidden kan mätas med en enkät under byggtiden.

  Parameter: andel_ändrar
    Antagande_min: 0,10 (10 % av de nådda ändrar sina bilresor)
    Antagande_med: 0,20 (20 % ändrar sig)
    Antagande_max: 0,25 (25 % ändrar sig)
    Enhet: andel av nådda
    Tidsaspekt: per år 2025–2028
    Källor: Möser & Bamberg (2008), Cairns m.fl. (2004). Ändringsbenägenheten i målgruppen stöds av TR_mode_share_bus (11 %), TR_mode_share_bike (20 %) och DATA_CITIZEN_SURVEY_2024, Short_Car_Trips (39 % kör kortare än 5 km flera gånger i veckan).
    Kvalitet: medel
    Lokaliserbarhet: medel
    Kommentar_antagande: Andelen korta bilresor är stor, vilket gör ett byte till cykel, gång eller buss realistiskt för en betydande grupp. Störningarna gör samtidigt bilen mindre attraktiv, så resenärerna är mer mottagliga under bygget än annars.

  Parameter: ΔA_ändrare
    Antagande_min: -0,20 (de som ändrar sig kör 20 % färre bilkm än i BAU)
    Antagande_med: -0,35 (35 % färre bilkm)
    Antagande_max: -0,45 (45 % färre bilkm)
    Enhet: relativ förändring av fordonskm jämfört med BAU, bland dem som ändrar sig
    Tidsaspekt: nivå relativt BAU samma år, 2025–2028
    Källor: KOMM_soft_max_effect_car_km (10–15 % bland deltagare), Cairns m.fl. (2004), TR_median_trip_length_km (bilmedian ca 7,6 km).
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Tillsammans med andel_ändrar ger detta 2–11 % (medel 7 %) lägre bilkm bland de nådda. Det stämmer med KOMM-intervallet 10–15 % som maxeffekt hos engagerade deltagare. De flesta byter bara en del av sina resor.

  Parameter: attribution
    Antagande_min: 0,40 (40 % av förändringen beror på åtgärden)
    Antagande_med: 0,60 (60 %)
    Antagande_max: 0,80 (80 %)
    Enhet: andel av förändringen som tillskrivs åtgärden
    Tidsaspekt: gäller hela perioden 2025–2028
    Källor: Cairns, Hass-Klau & Goodwin (1998) om att en del trafik försvinner av sig själv när vägkapaciteten minskar. Profilens avgränsning mot resecentrumprojektet, Region Värmlands kollektivtrafiksatsningar och nationella styrmedel.
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: En del av färdmedelsbytet hade skett ändå, eftersom kapacitetsminskningen och trängseln i sig avskräcker från bilkörning. Den samordnade trafikinformationen delas dessutom med Region Värmland. Ingen ΔEF ansätts: emissionsfaktorn följer BAU (ca 0,120 kg CO2e/fordonskm 2026), och elbilar räknas som nära noll territoriellt.

Drivare 2: Körsträcka med personbil för resor till centrum, konsumtionsbaserade utsläpp (inpendlares sträcka utanför kommunen)
  Mekanism: Shift, ΔA enligt EMAP. Inpendlare som nås av information, busprioritering och omledning under bygget väljer bilen mer sällan, så deras bilkörning ökar mindre än i BAU och en del resor flyttas till buss och tåg. Blocket räknar bara den del av inpendlarnas resor som ligger utanför Karlstads kommun. Sträckan inom kommunen och Karlstadsbornas konsumtion ingår redan i Drivare 1. Beteendeeffekten är samma kedja som i Drivare 1.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 0.0
    Konsumtion_faktor: 1.0
    Overlap_faktor: 0.0
    Motivering_faktorer: Sträckan utanför kommungränsen ger inga territoriella utsläpp i Karlstad. För inpendlarnas hushåll ger den däremot full konsumtionsbaserad effekt. Överlapp får därför inte vara större än 0. Det innebär ingen dubbelräkning, eftersom sträckan inom kommunen räknas i Drivare 1. Effekten hamnar i hemkommunernas konsumtionsbaserade utsläpp och redovisas som separat regional nytta, inte som minskning av Karlstads utsläpp. EF är tailpipe enligt BAU utan uppströmspåslag, på samma sätt som i Drivare 5.
  Parameter: andel_utanför
    Antagande_min: 0,30 (30 % av drivarens A är inpendlarnas km utanför kommunen)
    Antagande_med: 0,40 (ca 4,8e7 av 1,2e8 fordonskm: inpendlarnas 7,8e7 minus ca 3e7 inom kommunen)
    Antagande_max: 0,50 (längre pendlingsavstånd, t.ex. från Grums och Arvika)
    Enhet: andel av drivarens A (fordonskm/år)
    Tidsaspekt: konstant 2025–2028, appliceras på BAU-nivån för A (g_A medel +1,5 %/år)
    Källor: Baslinje Drivare 2 (A0 1,2e8, varav 4,4e7 invånare och 7,8e7 inpendlare, ca 3e7 inom kommunen), Baslinje Drivare 5 (12 km inom kommunen av ca 30 km enkel väg, ANTAGANDE), TR_median_trip_length_km, EF_passenger_car_avg
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Andelen avgränsar drivaren så att den inte överlappar Drivare 1. Den motsvarar ca 60 % av inpendlarnas km, samma som andel_utanför i Drivare 5. Den kan kalibreras med SCB:s pendlingsstatistik per hemkommun.
  Parameter: ΔA_netto
    Antagande_min: -0,004 (0,4 % färre bilkm än BAU)
    Antagande_med: -0,025 (2,5 % färre bilkm än BAU)
    Antagande_max: -0,068 (6,8 % färre bilkm än BAU)
    Enhet: relativ förändring av fordonskm jämfört med BAU, netto efter räckvidd, andel som ändrar sig, effekt och attribution
    Tidsaspekt: nivå relativt BAU samma år. Ramp: 50 % effekt 2025, 100 % 2026–2028. Ingen effekt efter 2028.
    Källor: Kedjan i Drivare 1 (reach 0,45/0,60/0,75 × andel_ändrar 0,10/0,20/0,25 × ΔA_ändrare 0,20/0,35/0,45 × attribution 0,40/0,60/0,80), KOMM_typical_reach_share_general, KOMM_soft_max_effect_car_km, Möser & Bamberg (2008), Cairns m.fl. (2004)
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: Värdet är produkten av kedjan i Drivare 1. Samma beteendeeffekt gäller alltså inpendlarnas hela resa, och om kedjan i Drivare 1 kalibreras ska värdet räknas om. Räckvidden kan vara något lägre för inpendlare än för invånare, men inpendlare möter omledningen fysiskt varje dag. Kvarvarande utsläpp från buss och tåg sätts till 0, eftersom de nya resenärerna ryms i befintligt utbud.

Drivare 3: Bilkörning i tjänst och pendling för kommunanställda till centrum
  Mekanism: Shift, ΔA enligt EMAP. Kommunen når sina anställda i centrum direkt med riktad information som arbetsgivare, och busprioritering och tillfälliga stråk gör andra färdmedel lättare att välja. Därför pendlar de anställda mindre med bil under byggtiden. En mindre del av tjänsteresorna med kommunens bilar ersätts med cykel, gång eller buss. Effekten räknas som en kedja: räckvidd × minskning av bilkm bland de nådda × attribution, utöver BAU (+0,5 %/år under bygget).
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 1.0
    Overlap_faktor: 1.0
    Motivering_faktorer: Bilkörningen sker inom kommunen och ingår i de anställdas resande, så enligt transportregeln är överlappet fullt. Kilometrarna är en delmängd av A0 i Drivare 1 och redovisas därför som en icke-additiv "varav kommunens egna"-post, som inte summeras med Drivare 1. Kommunens egna utsläpp avgränsas till tjänsteresorna, i linje med Drivare 6 och DATA_MUNICIPAL_ORG. Pendlingen redovisas som information, "varav kommunanställdas pendling".
  Parameter: räckvidd_anställda
    Antagande_min: 0,6 (60 % av kommunanställda i centrum nås av riktad information)
    Antagande_med: 0,8 (80 % nås via intranät, chefer och arbetsplatsträffar)
    Antagande_max: 0,9 (90 % nås, med personliga reseråd på större arbetsplatser)
    Enhet: andel av kommunanställda med arbetsplats i centrum (ca 2 400 enligt baslinjen)
    Tidsaspekt: per år 2025–2028. Ramp: 50 % effekt 2025, 100 % 2026–2028. Ingen effekt efter 2028.
    Källor: KOMM_typical_reach_share_general (50–70 %), uppräknat eftersom kommunen når sina egna anställda direkt. Antalet anställda kommer från localContext (8 000 anställda i koncernen) och baslinjen för Drivare 3 (30 % i centrum).
    Kvalitet: medel
    Lokaliserbarhet: lätt
    Kommentar_antagande: Räckvidden är högre än för allmänna kampanjer eftersom kommunen har egna kanaler. Den kan mätas med personalenkät.
  Parameter: ΔA_pendling
    Antagande_min: -0,03 (3 % färre bilpendlingskm bland de nådda, jämfört med BAU)
    Antagande_med: -0,07 (7 % färre)
    Antagande_max: -0,12 (12 % färre)
    Enhet: andel av bilpendlingskm (privatbil, ca 4,8e6 fordonskm/år i baslinjen), relativt BAU
    Tidsaspekt: nivå relativt BAU för respektive år 2025–2028, med samma ramp som räckvidd_anställda
    Källor: KOMM_soft_max_effect_car_km (10–15 % bland engagerade deltagare), EF_passenger_car_avg (BAU-trend från 0,14 till ca 0,10), TR_mode_share_car, Möser & Bamberg (2008), Cairns m.fl. (2004)
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Alla som nås ändrar sig inte, så medelvärdet ligger under parameterns 10–15 %. Effekten består både av en undviken BAU-ökning och av viss överflyttning till andra färdmedel. Netto blir räckvidd × ΔA × attribution, i medel ca −3,4 % av drivarens pendlingskm.
  Parameter: ΔA_tjänst
    Antagande_min: -0,02 (2 % färre tjänstekm med kommunens bilar)
    Antagande_med: -0,05 (5 % färre)
    Antagande_max: -0,10 (10 % färre, med cykelpool och resepolicy under byggtiden)
    Enhet: andel av tjänstekm i kommunens bilar (ca 1e6 fordonskm/år), relativt BAU
    Tidsaspekt: per år 2025–2028, med samma ramp som räckvidd_anställda
    Källor: EF_municipal_cars_avg (0,0–0,05 kg CO2/km, el och gas plus ca 2 % bensin, medel ca 0,02 tailpipe), DATA_MUNICIPAL_ORG (Bil, buss och tåg: 5 889 ton, för jämförelse)
    Kvalitet: låg
    Lokaliserbarhet: lätt
    Kommentar_antagande: Klimatnyttan blir mycket liten eftersom kommunens bilar redan är nästan fossilfria. Kalkylen ska använda EF_municipal_cars_avg och inte privatbilens EF.
  Parameter: attribution
    Antagande_min: 0,40 (40 % av förändringen beror på åtgärden)
    Antagande_med: 0,60
    Antagande_max: 0,80
    Enhet: andel av förändringen som tillskrivs åtgärden
    Tidsaspekt: gäller hela perioden 2025–2028, för både pendling och tjänsteresor
    Källor: Attributionen i Drivare 1 (gemensam för profil 1), Cairns, Hass-Klau & Goodwin (1998), åtgärdsprofil 1 (avgränsning mot resecentrumprojektet och Region Värmlands satsningar)
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: Kapacitetsminskningen och trängseln får en del anställda att avstå från bilen även utan insatserna. Värdena är harmoniserade med Drivare 1 så att "varav"-posten följer samma logik som huvuddrivaren.

Drivare 4: Körsträcka med personbil för pendling till centrum inom kommunen
  Mekanism: Shift, ΔA enligt EMAP. Kampanjer, arbetsgivarsamarbeten och incitament (provåkarkort, cykelpaket) får inpendlare och centrumanställda att byta en del bilpendling inom kommunen mot tåg, buss, cykel och gång. Effekten räknas som en kedja: andel nådda × minskning bland nådda × varaktighet × additionalitet. Åtgärden ändrar inte emissionsfaktorn. Kalkylen använder BAU-EF (0,14 kg CO2e/fordonskm 2023, −5 %/år i medel, ca 0,098 år 2030).
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 0.2
    Overlap_faktor: 0.2
    Motivering_faktorer: All körning i drivaren sker inom kommunen och räknas därför fullt territoriellt. Bara Karlstadsbornas del, ca 20 % av fordonskm i baslinjen (ca 7e6 av 3,5e7), hör till Karlstads konsumtionsbaserade utsläpp. Inpendlarnas konsumtion hör till hemkommunerna och hanteras i Drivare 5. Överlappet följer transportregeln och sätts till den minsta faktorn, 0.2.
  Parameter: adoption_nådda
    Antagande_min: 0,20 (en femtedel av drivarens bilpendlingskm finns hos personer som nås aktivt)
    Antagande_med: 0,35
    Antagande_max: 0,50
    Enhet: andel av drivarens bilpendlingskm (fordonskm/år) i målgruppen
    Tidsaspekt: per år 2029–2032. Ramp: 50 % effekt 2029, 100 % 2030–2032. Gemensamt förlopp för Drivare 4–6.
    Källor: KOMM_typical_reach_share_general (50–70 % nås minst en gång). Omfattningen i åtgärdsprofilen (5 000–8 000 anställda hos 20–30 arbetsgivare, 500–1 000 incitament per år, ca 15 000 inpendlare). Baslinjen för Drivare 4 (ca 5 400 inpendlande bilförare och ca 2 000 bilpendlande centrumanställda boende i kommunen).
    Kvalitet: låg
    Lokaliserbarhet: lätt
    Kommentar_antagande: Inpendlare står för ca 80 % av drivarens kilometrar. Värdet är därför ett viktat medel av inpendlarnas räckvidd (0,15/0,30/0,45, samma personer som i Drivare 5) och en högre räckvidd för centrumanställda som bor i kommunen (ca 0,40/0,55/0,70), som nås via sina arbetsgivare. Värdena avser verkligt engagemang, inte bara att någon sett budskapet. Spannet kan kalibreras när antalet anslutna arbetsgivare är känt.
  Parameter: ΔA_bland_nådda
    Antagande_min: −0,04 (4 % färre bilpendlingskm bland nådda jämfört med BAU)
    Antagande_med: −0,08
    Antagande_max: −0,13
    Enhet: relativ förändring av fordonskm (andel)
    Tidsaspekt: nivå relativt BAU per år 2029–2032
    Källor: KOMM_soft_max_effect_car_km (10–15 % bland deltagare). Möser & Bamberg (2008). Cairns m.fl. (2004/2008), Smarter Choices. TR_mode_share_car (53 % kommun, 47 % tätort).
    Kvalitet: medel
    Lokaliserbarhet: medel
    Kommentar_antagande: Metastudier av mjuka åtgärder och arbetsplatsresplaner visar ofta 5–15 % minskning bland deltagare. Medelvärdet sätts lågt i det spannet, eftersom inpendlare har långa resor och delvis saknar alternativ. Maxvärdet förutsätter att incitamenten utnyttjar resecentrums förbättrade tågutbud.
  Parameter: varaktighet
    Antagande_min: 0,60 (60 % av minskningen hos tidigare deltagare består nästa år)
    Antagande_med: 0,75
    Antagande_max: 0,90
    Enhet: andel/år
    Tidsaspekt: per år efter första deltagarår. Används främst för effekt efter 2032 och för deltagare som inte nås igen.
    Källor: Uppföljningar av personlig reseplanering (Brög m.fl., IndiMark/TravelSmart) och Fujii & Gärling (2003) om vanebrott via provåkarkort. Inget parameterbibliotek-värde finns.
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: Insatserna pågår under hela 2029–2032 och fyller på med nya deltagare. Under perioden antas därför effekten i stort sett bibehållas, och parametern avgör hur snabbt effekten avtar efteråt. Uppföljningar visar att en betydande del av effekten består när ett bra alternativ finns, här tågen vid resecentrum. Evidensen är ändå spretig.
  Parameter: additionalitet
    Antagande_min: 0,50 (halva förändringen hos nådda beror på åtgärden, resten hade skett via resecentrum, Region Värmlands kampanjer eller befintliga förmåner)
    Antagande_med: 0,65
    Antagande_max: 0,80
    Enhet: andel
    Tidsaspekt: gäller hela perioden 2029–2032
    Källor: BAU för Drivare 4 (g_A medel 0 %/år inklusive resecentrumeffekten). Åtgärdsprofilens kommentar om överlapp med förmånscykel och regionens kampanjer. Expertbedömning.
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Resecentrums infrastruktureffekt ligger redan i BAU. Bland dem som nås finns ändå personer som hade bytt färdmedel ändå, så kallade "free riders". Andelen sjunker om regionen kör egna parallella pendlarkampanjer mot samma arbetsgivare.

Drivare 5: Körsträcka med personbil för inpendlares pendling, konsumtionsbaserade utsläpp
  Mekanism: Shift, ΔA enligt EMAP. Inpendlare som nås av kampanjer, arbetsgivarsamarbeten och incitament byter en del bilpendling mot tåg, buss, samåkning eller cykel. Blocket räknar bara den del av pendlingssträckan som ligger utanför Karlstads kommun, eftersom sträckan inom kommunen redan räknas i Drivare 4.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 0.0
    Konsumtion_faktor: 1.0
    Overlap_faktor: 0.0
    Motivering_faktorer: Sträckan utanför kommungränsen ger inga territoriella utsläpp i Karlstad men full konsumtionseffekt för inpendlarnas hushåll. Överlapp kan därför inte vara större än 0. Det innebär ingen dubbelräkning, eftersom den del som ligger inom kommunen redan räknas i Drivare 4. Effekten hamnar i hemkommunernas konsumtionsbaserade utsläpp och ska redovisas separat, inte som minskning av Karlstads konsumtionsbaserade utsläpp.
  Parameter: andel_utanför
    Antagande_min: 0,50 (hälften av inpendlarnas bilkm ligger utanför kommunen)
    Antagande_med: 0,60 (ca 4,3e7 av 7,1e7 fordonskm enligt baslinjen)
    Antagande_max: 0,70 (längre pendlingsavstånd, t.ex. från Grums och Arvika)
    Enhet: andel av A för Drivare 5
    Tidsaspekt: konstant 2029–2032
    Källor: Baslinje Drivare 5 (12 km inom och ca 30 km totalt enkel väg, ANTAGANDE), TR_median_trip_length_km, EF_passenger_car_avg
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Andelen styr hur stor del av Drivare 5 som inte överlappar Drivare 4. Den kan kalibreras med SCB:s pendlingsstatistik per hemkommun.
  Parameter: adoption_nådda
    Antagande_min: 0,15 (15 % av de ca 5 400 bilpendlande inpendlarna nås aktivt)
    Antagande_med: 0,30 (30 % nås via arbetsgivarsamarbeten och incitament)
    Antagande_max: 0,45 (45 % nås, med brett deltagande hos arbetsgivare)
    Enhet: andel av bilpendlande inpendlare mot centrum
    Tidsaspekt: genomsnitt per år 2029–2032
    Källor: KOMM_typical_reach_share_general (50–70 % nås minst en gång). Åtgärdsprofil 2 (20–30 arbetsgivare med 5 000–8 000 anställda, incitament till 500–1 000 personer per år, ANTAGANDE). Baslinje Drivare 4 och 5 (ca 5 400 bilförare).
    Kvalitet: låg
    Lokaliserbarhet: medel
    Kommentar_antagande: Spannet ligger under den generella räckvidden eftersom det avser aktiv kontakt via arbetsgivare eller incitament, inte att någon bara sett en kampanj. Inpendlare är en bråkdel av de anställda hos samarbetande arbetsgivare.
  Parameter: ΔA_deltagare
    Antagande_min: -0,04 (4 % färre bilkm bland nådda, med avtagande effekt)
    Antagande_med: -0,08 (8 % färre bilkm bland nådda, i snitt över perioden)
    Antagande_max: -0,13 (13 % färre bilkm, med starka incitament och bra tåganslutning)
    Enhet: relativ förändring av bilkm bland nådda
    Tidsaspekt: genomsnittlig nivå relativt BAU per år 2029–2032. Ramp: 50 % effekt 2029, 100 % 2030–2032. Efter 2032 avtar effekten enligt varaktigheten i Drivare 4 (0,60/0,75/0,90 per år).
    Källor: KOMM_soft_max_effect_car_km (10–15 %), Möser & Bamberg 2008, Cairns m.fl. 2008, Thøgersen 2009. EF enligt BAU för Drivare 5 (medel 0,098 kg CO2e/fkm 2030, EF_passenger_car_avg).
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: Värdena ligger under litteraturens 10–15 %, eftersom långa pendlingsavstånd gör cykel mindre aktuellt och effekten av provåkarkort ofta avtar. Kvarvarande utsläpp från tåg och buss sätts till ungefär 0, eftersom extra resenärer ryms i befintligt utbud.
  Parameter: additionalitet
    Antagande_min: 0,50 (hälften av förändringen är åtgärdens förtjänst)
    Antagande_med: 0,65
    Antagande_max: 0,80
    Enhet: andel av förändringen utöver BAU
    Tidsaspekt: konstant 2029–2032
    Källor: Baslinje Drivare 4 och 5 (BAU innehåller resecentrums effekt, g_A medel 0 %/år), åtgärdsprofil 2 (överlapp med Region Värmlands kampanjer och förmånscykel)
    Kvalitet: låg
    Lokaliserbarhet: svår
    Kommentar_antagande: Faktorn drar av byten som resecentrum, Region Värmland eller befintliga arbetsgivarförmåner ändå hade gett. Värdena är harmoniserade med Drivare 4 (0,50/0,65/0,80), eftersom det är samma personer och samma insatser.

Drivare 6: Bilkörning i tjänst och pendling för kommunanställda i centrum
  Mekanism: Shift, ΔA, som i EMAP. Blocket avgränsas till kommunanställdas tjänsteresor med bil, eftersom deras pendling i privatbil redan ingår i Drivare 4 och 5. Kommunen har direkt rådighet som arbetsgivare och kan flytta tjänsteresor från bil till cykel, elcykel, buss och tåg via resepolicy, tjänstecyklar och tillgång till kollektivtrafik vid resecentrum.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 0.3
    Konsumtion_faktor: 1.0
    Overlap_faktor: 0.3
    Motivering_faktorer: EF_tjänst nedan är ett livscykelvärde för kommunens till största del el- och gasdrivna bilar. Territoriellt syns bara bensinandelen och den fossila delen av fordonsgasen, eftersom elen redovisas i sektorn El och fjärrvärme. Därför är den territoriella faktorn låg. Resorna sker inom kommunen, så överlappet sätts till den minsta faktorn (0.3).

  Parameter: A_tjänst
    Antagande_min: 0,8e6 (tjänsteresor med bil, del av A0 = 6e6)
    Antagande_med: 1,0e6 (enligt baslinjens uppdelning)
    Antagande_max: 1,2e6 (inkluderar ca 0,2e6 i privatbil i tjänst, ANTAGANDE)
    Enhet: fordonskm/år
    Tidsaspekt: nivå 2023, följer baslinjens BAU-trend g_A för Drivare 6 (medel -0,5 %/år)
    Källor: Baslinjen för Drivare 6 (A0 6e6, varav ca 1e6 tjänsteresor), DATA_MUNICIPAL_ORG (Bil, buss och tåg: 5 889 ton), EF_municipal_cars_avg
    Kvalitet: låg
    Lokaliserbarhet: lätt
    Kommentar_antagande: Värdet är en schablon. Det kan ersättas direkt med körjournaler, bilpoolsdata och milersättning för förvaltningar med arbetsplats i centrum.

  Parameter: ΔA_tjänst
    Antagande_min: -0,03 (3 % färre tjänste-fordonskm än BAU)
    Antagande_med: -0,07 (7 % färre)
    Antagande_max: -0,12 (12 % färre)
    Enhet: andel av BAU-aktivitet (fordonskm)
    Tidsaspekt: nivå relativt BAU per år 2029–2032. Ramp: 50 % effekt 2029, 100 % 2030–2032. Effekten antas bestå efter 2032, eftersom den bygger på policy och utrustning.
    Källor: KOMM_soft_max_effect_car_km (10–15 % bland deltagare), TR_mode_share_car, TR_median_trip_length_km (korta resor inom tätorten), Cairns m.fl. 2004/2008 (arbetsplatsers resplaner)
    Kvalitet: låg
    Lokaliserbarhet: lätt
    Kommentar_antagande: Kedjan är andel tjänsteresor som omfattas av policyn (0,6/0,8/1,0) gånger minskningen bland dem (0,05/0,09/0,12). Resecentrums egen effekt ligger redan i BAU och är därför inte medräknad här. Effekten antas avta mindre än kampanjeffekter, eftersom den bygger på policy och utrustning som finns kvar.

  Parameter: EF_tjänst
    Antagande_min: 0,015 (nästan helt el och biogas)
    Antagande_med: 0,03 (kommunens bilar plus en liten andel privatbil i tjänst)
    Antagande_max: 0,045 (större andel bensin och privatbil)
    Enhet: kg CO2e/fordonskm (livscykel)
    Tidsaspekt: nivå 2023, därefter enligt BAU g_EF (medel -5 %/år)
    Källor: EF_municipal_cars_avg (0,0–0,05), EF_ev_per_km (0,02–0,05), EF_passenger_car_avg (0,12–0,18), EF_el_SE_consumption_2030_BAU
    Kvalitet: medel
    Lokaliserbarhet: lätt
    Kommentar_antagande: Värdet ersätter baslinjens viktade EF0 (0,12) för denna avgränsning, eftersom det viktade värdet domineras av pendling i privatbil. Med det låga EF-värdet blir klimatnyttan liten men inte noll.

Nyckelantaganden – överblick
- **Under byggtiden** antas mobility management ge 0,4–6,8 % färre personbilskilometer till och genom centrum än i BAU, med medel ca 2,5 %. Det gäller både territoriellt och för inpendlarnas sträcka utanför kommunen. Kedjan är:
  - räckvidd 45–75 %,
  - 10–25 % av de nådda ändrar sig,
  - de som ändrar sig kör 20–45 % mindre,
  - attribution 40–80 %.
- **Efter öppningen** antas bilpendlingen mot centrum bli ca 0,4–5,2 % lägre än i BAU inom kommunen, med medel ca 1,8 %. Kedjan är:
  - 20–50 % av bilpendlingskilometrarna finns hos nådda personer,
  - de nådda minskar med 4–13 %,
  - additionalitet 50–80 %.
  
  Inpendlarnas sträcka utanför kommunen följer samma beteende. Där är andelen nådda 15–45 %.
- **Varaktighet:** efter 2032 antas 60–90 % av effekten finnas kvar varje år. Byggtidens effekt upphör vid öppningen.
- **Emissionsfaktorn** följer BAU (ca 0,120 kg CO₂e/fordonskm 2026 och 0,098 kg 2030). Kommunens bilar har 0,015–0,045 kg CO₂e/fordonskm (livscykel), så kommunens egen nytta blir marginell.
- **Konsumtionsbaserad nytta för Karlstad** utgör ca 60 % av den territoriella effekten under bygget och ca 20 % efter öppningen. Inpendlarnas nytta utanför kommunen hör till hemkommunerna och redovisas separat.

Övergripande antaganden och scenariologik
Profil 1 är beslutad och startade 2025. Den räknas med 50 % effekt 2025 och full effekt 2026–2028, och upphör vid öppningen. Profil 2 är på idéstadiet och räknas med 50 % effekt 2029 och full effekt 2030–2032.

Spannen ska läsas som paket: min kombineras med min, medel med medel och max med max. Kombineras min- och max-värden från olika led blir utfallet orimligt.

Effekten räknas alltid utöver BAU. Under bygget innebär det i första hand en undviken ökning av biltrafiken. Efter öppningen innebär det en minskning utöver resecentrums egen infrastruktureffekt, som redan ligger i BAU. Attributionen och additionaliteten drar av det som hade skett ändå.

Medelvärdena ligger medvetet under litteraturens 10–15 % för engagerade deltagare. Insatserna är breda och har ingen personlig reseplanering, och inpendlarna har långa resor och färre alternativ till bilen.

Alla emissionsfaktorer avser utsläpp från avgasröret (tailpipe). Uppströmsutsläpp från drivmedelsproduktion och el till elbilar ingår inte. Om de räknas in blir den konsumtionsbaserade effekten ungefär 10–25 % större.

Merutsläpp från kollektivtrafiken sätts till 0. De resenärer som byter färdmedel antas få plats i befintliga turer.

Dataluckor för detta steg
- Det finns inga trafikräkningar eller enkäter om räckvidd och beteendeförändring vid stationsområdet före, under eller efter bygget. Därför är hela kedjan (räckvidd, andel som ändrar sig och effekt) okalibrerad.
- Pendlingsstatistik per hemkommun saknas: antal inpendlare mot centrum, deras bilandel och fördelningen mellan sträcka inom och utanför kommunen. Uppgiften styr både Konsumtion_faktor och andel_utanför.
- Det är oklart hur mycket av färdmedelsbytet som beror på kapacitetsminskningen och Region Värmlands egna insatser. Därför är attributionen och additionaliteten osäkra.
- Antal anslutna arbetsgivare och anställda samt antal utdelade incitament i profil 2 är okända.
- Det saknas svenska uppföljningar av hur länge effekten av provåkarkort och arbetsgivarsamarbeten håller för regionala pendlare.
- Kommunens egna resdata saknas: körjournaler, bilpoolsdata, milersättning och personalresvaneenkät för arbetsplatser i centrum.
- Lokala elbilsandelar för 2024–2032 saknas, både för Karlstad och för grannkommunerna. Det saknas också ett beslut om uppströms- och elutsläpp ska ingå i den konsumtionsbaserade emissionsfaktorn.

Externa källor och studier
- Möser, G. & Bamberg, S. (2008). The effectiveness of soft transport policy measures: A critical assessment and meta-analytic synthesis. Journal of Environmental Psychology 28(1).
- Cairns, S. m.fl. (2004). Smarter Choices – Changing the Way We Travel. UK Department for Transport.
- Cairns, S. m.fl. (2008). Smarter Choices: Assessing the potential to achieve traffic reduction using "soft measures". Transport Reviews 28(5).
- Cairns, S., Hass-Klau, C. & Goodwin, P. (1998). Traffic Impact of Highway Capacity Reductions: Assessment of the Evidence. Landor Publishing.
- Fujii, S. & Gärling, T. (2003). Development of script-based travel mode choice after forced change. Transportation Research Part F 6(2).
- Thøgersen, J. (2009). Promoting public transport as a subscription service: Effects of a free month travel card. Transport Policy 16(6).
- Brög, W. m.fl. (2009). Evaluation of voluntary travel behaviour change: Experiences from three continents. Transport Policy 16(6).
- Trafikverket och Västtrafik: utvärderingar av mobility management och trafikantinformation under byggskedet i Västsvenska paketet, 2013–2020. Används som generell referens.

Samstämmighetskontroll
- **Dubbelräkning av Karlstadsbornas konsumtion.** Jag kontrollerade avgränsningarna mellan Drivare 1 (Bilkörning till och genom centrum) och Drivare 2 (Konsumtionsbaserad bilkörning). Båda räknade invånarnas kilometrar konsumtionsbaserat. Drivare 1 bär nu invånardelen (Konsumtion_faktor 0.6, Overlap_faktor 0.6). Drivare 2 är ombyggd så att den bara omfattar inpendlarnas sträcka utanför kommunen (0.0/1.0/0.0) och redovisas som separat regional nytta. Det motsvarar uppdelningen mellan Drivare 4 och Drivare 5.
- **Konsumtionsbas.** Jag kontrollerade emissionsfaktorns bas. Delbedömningen för Drivare 2 hade ett uppströmspåslag på 1,15, men övriga drivare räknade med tailpipe. Nu används tailpipe och BAU-EF med Konsumtion_faktor utan påslag i alla privatbilsdrivare. Påslaget redovisas som känslighet. Drivare 6 (Kommunens tjänsteresor) behåller livscykel-EF 0,015–0,045 med låg territoriell faktor, eftersom tailpipe är nära 0 för kommunens bilar.
- **Attribution och additionalitet.** Jag kontrollerade attribution och additionalitet mellan drivarna. Profil 1 använder nu genomgående 0,40/0,60/0,80: i Drivare 1, i nettoeffekten för Drivare 2 och som ny parameter i Drivare 3. Profil 2 använder genomgående 0,50/0,65/0,80, och Drivare 5 är justerad till samma värden som Drivare 4. Drivare 6 har ingen separat additionalitet, eftersom kommunen har direkt rådighet över sin resepolicy och resecentrums effekt redan ligger i BAU.
- **Adoption för samma personer.** Drivare 4 och Drivare 5 avser till stor del samma inpendlare, och inpendlarna står för ca 80 % av kilometrarna i Drivare 4. Därför är adoption_nådda i Drivare 4 sänkt till 0,20/0,35/0,50. Det är ett viktat värde av inpendlarnas 0,15/0,30/0,45 i Drivare 5 och en något högre räckvidd för centrumanställda som bor i kommunen.
- **Gemensamt förlopp.** Jag tog ställning till delbedömningarnas förslag om ramp och effektår:
  - Profil 1 räknas med 50 % effekt 2025 och 100 % 2026–2028, och effekten upphör efter 2028. BAU för profil 2 innehåller därför ingen kvarstående effekt från profil 1.
  - Profil 2 räknas med 50 % effekt 2029 och 100 % 2030–2032.
  - Efter 2032 avtar effekten i Drivare 4 och Drivare 5 enligt varaktigheten 0,60/0,75/0,90 per år.
- **Kommunens egna utsläpp, överlapp och enheter.** Drivare 3 redovisas som en icke-additiv "varav"-post inom Drivare 1. Kommunens egna utsläpp avgränsas i båda profilerna till tjänsteresor, i Drivare 3 och Drivare 6, vilket stämmer med DATA_MUNICIPAL_ORG. Jag kontrollerade också att alla Overlap_faktorer är högst lika med den minsta av Territoriell_faktor och Konsumtion_faktor, och att alla aktiviteter anges i fordonskm/år som A0. Inga fler avvikelser hittades.
