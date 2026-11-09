Evidens & antaganden för åtgärd: Krav på laddbara tjänstebilar och utbyggnad av laddinfrastruktur vid kommunala arbetsplatser

---

## Kort om detta steg

Utifrån EMAP-analysen och Baslinje & BAU-underlaget identifierar jag här vilka drivare och parametrar som åtgärden faktiskt påverkar, och föreslår antagandespann (min/medel/max) med källor och kvalitetsbedömning. Fokus ligger på den direkt kvantifierbara drivaren – omställning av kommunens icke-laddbara tjänstebilar – medan laddinfrastrukturen behandlas som en möjliggörare vars effekt är inbakad i fordonsdrivaren. Antagandena avser effekt **utöver BAU** och beskriver hur snabbt och hur långt flottan ställs om samt hur emissionsfaktorn per körd kilometer förändras. Dessa antaganden används i nästa steg för att räkna ton CO₂e.

---

## Underlag från tidigare steg

Baslinjen identifierade två drivare: (1) körsträcka med icke-laddbara tjänstebilar (direkt kvantifierbar, A0 ≈ 3,0e6 km/år, EF0 ≈ 0,13 kg CO2/km, motsvarande ~390 ton CO2/år) och (2) laddinfrastruktur (indirekt enabler utan egen utsläppsbaslinje). Drivare 1 är den som påverkas mest av åtgärden. En viktig BAU-aspekt är att flottan redan elektrifieras gradvis genom nationella styrmedel (EU-krav, bonus-malus) med en antagen minskning av fossil körsträcka om -2 till -8 %/år, vilket innebär att en betydande del av omställningen sker även utan det lokala kravet – åtgärdseffekten måste därför räknas som tillägg till denna bana. Centrala dataluckor är att faktisk flottstorlek, nuvarande laddbar andel och körsträcka per fordon alla är antaganden, samt att det är oklart om kravet gäller enbart BEV eller även laddhybrider (PHEV).

---

## Påverkade drivare och parametrar

- **Drivare 1 (icke-laddbara tjänstebilar):** Påverkas direkt av åtgärden via en kombination av **adoption** (kravet tvingar fram snabbare omställning av flottan än BAU) och **ΔEF** (varje omställt fordon byter från fossil EF ~0,13 kg CO2/km till el-EF ~0,02–0,05 kg CO2/km). Detta är åtgärdens huvudsakliga klimatnytta.
- **Drivare 2 (laddinfrastruktur):** Möjliggörare för Drivare 1. Klimatnyttan kvantifieras **inte separat** utan är en förutsättning för att adoptionen i Drivare 1 ska kunna realiseras. Om infrastrukturen även öppnas för anställdas privata elbilar tillkommer en potentiell effekt på pendlingsresor, men detta kvantifieras inte här på grund av bristande underlag.

---

## Antaganden per drivare

**Drivare 1: Icke-laddbara tjänstebilar i kommunens flotta**
  Mekanism: Shift – kravet driver på ett drivmedels-/teknikskifte där fossildrivna tjänstebilar ersätts med laddbara fordon snabbare än vid naturlig flottaomsättning. Effekten uttrycks dels som ökad adoptionstakt (andel av flottan som ställts om till 2030 utöver BAU), dels som förändrad emissionsfaktor per körd kilometer för de omställda fordonen.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: 1.0
    Konsumtion_faktor: 1.0
    Overlap_faktor: 1.0
    Motivering_faktorer: Kommunens tjänstebilar körs fysiskt inom kommunen, så minskad fossilförbränning ger full territoriell effekt. Samma utsläpp ingår i kommunkoncernens konsumtionsbaserade fotavtryck (organisationens egna transporter), varför konsumtionsfaktorn också är 1.0. Enligt regeln för laddinfrastruktur/transport inom kommunen sätts överlappet till 1.0 (lika med den minsta av territoriell och konsumtion) för att undvika dubbelräkning. Notera att en mindre residualeffekt kvarstår på konsumtionssidan via elförbrukningen för de nya elbilarna, men denna hanteras via ΔEF nedan.

  Parameter: adoption (andel av BAU-2030:s kvarvarande icke-laddbara delflotta som ytterligare ställs om till laddbar pga åtgärden)
    Antagande_min: 0,25 (25 % av den fossila delflotta som återstår i BAU 2030 ställs om extra tack vare kravet)
    Antagande_med: 0,50 (50 % av kvarvarande fossil delflotta ställs om extra)
    Antagande_max: 0,85 (85 % – nära total utfasning; enduraspecialfordon utan laddbara alternativ kvarstår)
    Enhet: andel av kvarvarande icke-laddbar delflotta (relativt BAU 2030)
    Tidsaspekt: nivå relativt 2030 BAU, infasning 2027–2030
    Källor: EF_municipal_cars_avg, TR_share_evs_fleet_2030 (parameterbiblioteket); kommunala fordonsupphandlingskrav är väl beprövade och når ofta mycket hög andel laddbara i nyanskaffning. Jämför nationella upphandlingstrender (TR_share_evs_new_sales ~30 % BEV i ordinarie nybilsförsäljning 2023) – ett formellt kommunalt krav ligger väsentligt över detta.
    Kvalitet: medel
    Lokaliserbarhet: svår
    Kommentar_antagande: Kravet är ett direkt styrmedel över kommunens egen flotta, vilket gör hög adoption realistisk (kommunen har full rådighet). Osäkerheten ligger i hur stor den kvarvarande fossila delflottan faktiskt är 2030 (beror på BAU-banan) och i att specialfordon kan sakna laddbara alternativ. Eftersom flottstorlek och nuvarande laddbar andel är antaganden är lokaliserbarheten svår tills fordonsregister erhålls.

  Parameter: ΔEF (emissionsfaktor per km för omställda fordon: från fossil till el)
    Antagande_min: -0,08 (från ~0,13 till ~0,05 kg CO2/km; motsvarar delvis PHEV som ofta körs på bränsle, eller el med residualmix)
    Antagande_med: -0,10 (från ~0,13 till ~0,03 kg CO2/km; BEV på svensk elmix)
    Antagande_max: -0,13 (från ~0,13 till ~0,00 kg CO2/km; BEV på ursprungsmärkt förnybar el, EF_el_Karlstad_product_guaranteed = 0)
    Enhet: kg CO2/km (förändring jämfört med fossil delflotta)
    Tidsaspekt: nivå per omställt fordon, gäller från driftsättning 2027–2030
    Källor: EF_passenger_car_avg (0,12–0,18), EF_ev_per_km (0,02–0,05), EF_el_Karlstad_product_guaranteed (0 g CO2e/kWh), EF_el_SE_consumption_2020s/2030_BAU (parameterbiblioteket).
    Kvalitet: medel
    Lokaliserbarhet: medel
    Kommentar_antagande: Storleken på ΔEF avgörs starkt av om kravet omfattar BEV eller PHEV. För BEV som laddas med Karlstads Energis ursprungsmärkta el närmar sig territoriell EF noll (endast marginella nätförluster). För PHEV är den reella effekten lägre eftersom laddhybrider ofta körs på bensin om laddning sker sällan – därför sätts min-scenariot försiktigt. Max-scenariot förutsätter helt eldrivna fordon på förnybar el.

---

**Drivare 2: Laddinfrastruktur vid kommunala arbetsplatser (enabler)**
  Mekanism: Shift/möjliggörare – infrastrukturen skapar de fysiska förutsättningarna för att laddbara tjänstebilar (och potentiellt anställdas privata elbilar) faktiskt kan laddas och användas. Den genererar inga direkta utsläppsminskningar i sig.
  Klimatfaktorer (Territoriell / Konsumtion / Överlapp):
    Territoriell_faktor: – (kvantifieras ej separat)
    Konsumtion_faktor: – (kvantifieras ej separat)
    Overlap_faktor: – (kvantifieras ej separat)
    Motivering_faktorer: Klimatnyttan av laddinfrastrukturen kvantifieras inte som en egen drivare eftersom effekten är helt beroende av och redan inbakad i adoptionsantagandet för Drivare 1. Om infrastrukturen redovisas separat skulle den enligt regeln för laddinfrastruktur ges Territoriell_faktor 1.0, Konsumtion_faktor 1.0 och Overlap_faktor 1.0 – men för att undvika dubbelräkning med Drivare 1 sätts inga egna antaganden här.
    Kommentar: Infrastrukturen är en nödvändig förutsättning för att adoptionsantagandet i Drivare 1 ska kunna nå de högre scenarierna. Utan utbyggd laddning bör adoptionen i Drivare 1 hållas i den lägre delen av spannet. Bygg-/installationsutsläpp (inbäddad CO2) från laddstolpar är ej beaktade och bedöms som marginella i sammanhanget. Om infrastrukturen även möjliggör laddning av anställdas privata fordon (pendling) finns en additionell, ej kvantifierad potential som bör utredas separat.

---

## Nyckelantaganden – överblick

- Kravet antas ställa om 25–85 % (medel 50 %) av den fossila delflotta som annars skulle återstå i BAU 2030, utöver den omställning som redan sker via nationella styrmedel.
- Emissionsfaktorn för omställda fordon antas sjunka med 0,08–0,13 kg CO2/km (från fossil ~0,13 till el 0,00–0,05), beroende på om fordonen är BEV eller PHEV och vilken elprodukt som används.
- Laddinfrastrukturen (Drivare 2) kvantifieras inte separat utan är en förutsättning som bär upp adoptionsantagandet i Drivare 1.
- Åtgärdens klimatnytta är i absoluta tal begränsad (baslinjen är ~390 ton CO2/år) eftersom kommunens flotta redan är till stor del elektrifierad/gasdriven.
- Effekten faller på både territoriella och konsumtionsbaserade utsläpp med fullt överlapp (faktorer 1.0/1.0/1.0).

---

## Övergripande antaganden och scenariologik

Åtgärden antas genomföras successivt 2027–2030, med gradvis stigande andel omställda fordon i takt med naturlig flottaomsättning och nya upphandlingskrav. Antagandespannen för adoption och ΔEF ska tolkas som ett **paket**: ett lågt scenario innebär både långsammare omställning och mindre gynnsam EF (t.ex. PHEV på blandel), medan ett högt scenario kombinerar snabb omställning med BEV på förnybar el. Eftersom kommunen har full rådighet över sin egen fordonsflotta är genomförandegraden i grunden hög, men den reella nettonyttan begränsas av att BAU redan fasar ut fossila fordon – det är alltså den **additionella** omställningen utöver BAU som räknas. Adoptionsantagandena är medvetet kopplade till infrastrukturens utbyggnad: de högre scenarierna förutsätter att laddinfrastrukturen (Drivare 2) faktiskt är på plats. Ett medvetet konservativt drag är att min-scenariot för ΔEF antar betydande PHEV-inslag med bränslekörning, vilket speglar den vanliga skillnaden mellan teoretisk och faktisk laddhybrideffekt.

---

## Dataluckor för detta steg

- Saknar faktiskt antal tjänstebilar och nuvarande fördelning laddbara/icke-laddbara – hela adoptionsspannet vilar på antaganden om flottans sammansättning.
- Oklart om kravet omfattar enbart BEV eller även PHEV – avgörande för ΔEF-spannet och för risken att laddhybrider körs på bränsle.
- Saknar uppgift om genomsnittlig körsträcka per tjänstebil (15 000 km/år är schablon), vilket påverkar hur mycket varje omställt fordon bidrar.
- Oklart vilken elprodukt kommunens fordon laddas med (ursprungsmärkt förnybar el ger EF ≈ 0; residualmix ger högre) – styr var i EF-spannet resultatet hamnar.
- Ingen lokal utvärdering av tidigare fordonsupphandlingar finns tillgänglig för att kalibrera adoptionstakten mot faktiskt utfall.
- Effekten av att öppna laddinfrastrukturen för anställdas privata elbilar (pendling) är inte kvantifierad och saknar underlag om antal laddpunkter och nyttjandegrad.

---

## Externa källor och studier

- Naturvårdsverket / Trafikverket: nationella scenarier för elektrifiering av personbilsflottan och styrmedelseffekter (bonus-malus, EU:s krav på nollutsläpp i nybilsförsäljning 2035) – använt för att motivera BAU-elektrisering och adoptionsnivåer.
- Upphandlingsmyndigheten: vägledning och kriterier för miljöanpassad fordonsupphandling i offentlig sektor – stödjer antagandet om hög adoption vid formella kommunala krav.
- Studier om skillnad mellan typgodkänd och faktisk körning för laddhybrider (bl.a. ICCT:s rapporter om PHEV "real-world" utsläpp) – motiverar det försiktiga min-scenariot för ΔEF.
- I övrigt baseras analysen på parameterbiblioteket (EF_municipal_cars_avg, EF_passenger_car_avg, EF_ev_per_km, EF_el_Karlstad_product_guaranteed, TR_share_evs_new_sales, TR_share_evs_fleet_2030) och kommunkoncernens egna konsumtionsbaserade utsläpp (DATA_MUNICIPAL_ORG).