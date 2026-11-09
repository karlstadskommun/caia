CoVe QA för åtgärd: Krav på laddbara tjänstebilar och utbyggnad av laddinfrastruktur vid kommunala arbetsplatser

---

## Kort om detta steg

I detta steg gör jag en chain-of-verification (CoVe) av hela analysen för åtgärden. Jag kontrollerar källornas aktualitet och kvalitet, att enheter hänger ihop, att resultatets storleksordning är rimlig, att effekten är beräknad utöver BAU och inte dubbelräknad, samt att drivarsummorna stämmer mot totalen. Jag avslutar med en samlad QA-status (ok eller varning) med konkreta anmärkningar och åtgärdsförslag. Inga siffror eller antaganden från tidigare steg ändras – jag kommenterar och föreslår åtgärder.

---

## Genomgång av källor

**Källor_aktualitet:**
De bärande parametrarna från biblioteket (EF_municipal_cars_avg, EF_passenger_car_avg, EF_ev_per_km, EF_el_Karlstad_product_guaranteed, TR_share_evs_new_sales/fleet_2030) har referensår 2023 och bedöms som aktuella (yngre än 3 år). De externa källorna (Trafikverket/Naturvårdsverkets elektrifieringsscenarier, ICCT om PHEV real-world) är relevanta och rimligt aktuella. Den centrala svagheten är inte källåldern utan att flottdata i praktiken saknas – flottstorlek, laddbar andel och körsträcka per fordon är alla antaganden, inte hämtade från ett fordonsregister.

**Källor_relevans:**
Källorna matchar åtgärdstypen (kommunal fordonsupphandling, elektrifiering). Karlstad-specifika värden används där de finns (EF_el_Karlstad_product_guaranteed = 0, EF_municipal_cars_avg) och generella värden används som riktmärke för den fossila delflottan. Kopplingen till kommunkoncernens egna konsumtionsbaserade transportutsläpp (DATA_MUNICIPAL_ORG, 5 889 ton CO2e för "Bil, buss och tåg") är relevant men grov – det är oklart om posten avser egna fordon, köpta transporttjänster eller båda.

**Källor_kvalitet:**
Kvaliteten på emissionsfaktorerna bedöms som medel–hög. Kvaliteten på aktivitetsdata (A0) bedöms som låg, eftersom hela baslinjen vilar på tre kedjade antaganden (~400 fordon × ~50 % icke-laddbar × ~15 000 km/år).

---

## Enheter och storleksordning

**Enhetskontroll:**
- Beräkningskedjan km/år × kg CO2/km → kg CO2 → ton CO2e är dimensionellt konsekvent.
- ΔEF anges i kg CO2/km, konsistent med EF0. Ingen enhetsavvikelse noterad.
- Gas_typ: fordonens direktutsläpp anges som CO2 (TTW) i biblioteket, medan resultatet rapporteras som CO2e. Detta är en mindre men noterbar inkonsekvens – för fossil vägtrafik är skillnaden marginell, men bör harmoniseras i redovisningen.

**Storleksordning_resultat:**
- Baslinje ~390 ton CO2/år och medeleffekt 118 ton CO2e/år 2030 (~30 % av den fossila delflottans utsläpp) är internt konsistent och rimligt givet en additionell omställning på 50 % av kvarvarande fossil delflotta.
- **Viktig storleksordningsanmärkning:** Parameterbiblioteket anger EF_municipal_cars_avg = 0,0–0,05 kg CO2/km för hela den nuvarande kommunflottan, med notering att flertalet fordon redan är el eller gas. Analysens antagande att ~50 % av flottan fortfarande är icke-laddbar med EF0 = 0,13 kg CO2/km ger ett vägt flottsnitt på ~0,075 kg CO2/km, vilket ligger klart över bibliotekets 0,0–0,05. Detta indikerar att den fossila delflottan (och därmed både baslinjen och effekten) kan vara **överskattad**. Storleksordningen bör därför tolkas som ett tak snarare än en central skattning tills fordonsregister bekräftar andelen.
- Effekten (118 ton) är liten i relation till kommunkoncernens transportutsläpp (5 889 ton) och försumbar mot kommunens territoriella totalutsläpp (~225 kt). Detta är i sig inte ett fel, men storleken bör kommuniceras tydligt.

**Drivarsumma_vs_total:**
Endast Drivare 1 kvantifieras (118 ton). Drivare 2 (laddinfrastruktur) är korrekt satt till enabler utan egen effekt. Summan av drivare (118 + 0) motsvarar totalen (118 ton). Konsistent.

---

## BAU- och effektlogik

**BAU_hantering:**
BAU är logiskt uppbyggt: flottan elektrifieras gradvis även utan åtgärden via nationella styrmedel (Tier 2, g_A −2 till −8 %/år, g_EF −1 till −3 %/år), och åtgärdseffekten räknas explicit som additionell omställning av den fossila delflotta som återstår i BAU 2030. Åtgärden ligger alltså inte redan inbakad i BAU. Detta hanterar en central risk korrekt: eftersom mycket av elektrifieringen sker ändå, undviks överskattning genom att bara det additionella räknas.

**Antaganden_vs_resultat:**
Resultaten följer logiskt av antagandena: min 59 < medel 118 < max 201 ton CO2e/år 2030. Skalningen mellan scenarierna är rimlig och speglar paketlogiken (lågt = långsammare omställning + PHEV på blandel; högt = snabb omställning + BEV på förnybar el).

**Specialkontroll_Energi:**
Åtgärden avser transport (fossilförbränning i kommunens egna fordon), inte hushålls-/företagsenergi. Att den territoriella effekten är full (118 ton, faktor 1.0) är här **korrekt och inte en varningsflagga**, eftersom bensin-/dieselförbränningen fysiskt sker i kommunens fordon inom kommunen och ersätts med el som produceras utanför den territoriella gränsen. Domänregeln om att energibesparing i hushåll/företag ska vara konsumtionsbaserad är inte tillämplig på detta fordonsbyte. Att territoriell = konsumtion = 118 ton är därmed logiskt.

**Tidsprofil_rimlighet:**
Infasning 2027–2030 med gradvis upprampning är realistisk för fordonsflottsomställning som följer naturlig utrangeringstakt och upphandlingscykler. Kumulativt 248 ton med medeleffekt 50 ton/år är förenligt med en linjär upprampning från 2027 till full effekt 2030.

---

## Dubbelräkning och portföljperspektiv

**Dubbelräkning_inom_atgärden:**
Låg risk. Drivare 2 (infrastruktur) kvantifieras inte separat utan är en förutsättning inbakad i adoptionsantagandet för Drivare 1. Detta undviker korrekt att samma utsläppsminskning räknas två gånger inom åtgärden. Adoption och ΔEF multipliceras (andel omställda km × EF-förändring) utan överlapp.

**Dubbelräkning_mot_andra_atgärder:**
Medel risk. Åtgärdens utsläpp ingår i kommunkoncernens egna organisationsutsläpp/transporter (DATA_MUNICIPAL_ORG). Om portföljen innehåller andra åtgärder riktade mot kommunens tjänsteresor, fordonspool, mobilitetspolicy eller upphandling finns risk för överlapp. Ingen konkret portföljinformation har varit tillgänglig i underlaget, varför risknivån bedöms översiktligt.

**Kommentar_dubbelräkning:**
De viktigaste riskerna är (a) överlapp med eventuella andra åtgärder mot kommunens egna transporter och (b) att laddinfrastrukturen, om den senare kvantifieras separat i en annan åtgärd, dubbelräknas mot Drivare 1. Rekommendationen är att på portföljnivå hålla samman fordonskrav + laddinfrastruktur som ett paket och märka posten mot kommunkoncernens organisationsutsläpp för att kunna kvitta överlapp.

---

## Samlad QA-bedömning

QA-status: varning

QA-anmärkningar:
- Hela baslinjen (A0 ≈ 3,0e6 km/år) vilar på tre kedjade antaganden (flottstorlek ~400, icke-laddbar andel ~50 %, körsträcka ~15 000 km/fordon) utan bekräftelse från fordonsregister – hög osäkerhet i utgångspunkten.
- Möjlig överskattning: antagen icke-laddbar andel (~50 %) och EF0 (0,13 kg CO2/km) ger ett vägt flottsnitt (~0,075) som överstiger parameterbibliotekets EF_municipal_cars_avg (0,0–0,05), vilket indikerar att flottan redan är mer elektrifierad än antaget och att effekten kan vara lägre.
- Oklart om kravet omfattar enbart BEV eller även PHEV – avgörande för ΔEF och för risken att laddhybrider körs på bränsle (påverkar var i spannet 59–201 ton resultatet hamnar).
- Additionalitet mot BAU är känslig: eftersom nationella styrmedel redan fasar ut fossila fordon är den additionella nyttan liten och starkt beroende av BAU-antagandena.
- Mindre inkonsekvens CO2 vs CO2e i redovisningen av fordonens direktutsläpp.
- Medel risk för dubbelräkning mot andra åtgärder som berör kommunens egna transporter/organisationsutsläpp.

QA-åtgärdsförslag:
- Hämta faktiska uppgifter om kommunkoncernens fordonsflotta (antal, drivmedelsfördelning, körsträcka) och räkna om baslinjen; detta är den enskilt viktigaste åtgärden.
- Stäm av antagen icke-laddbar andel och EF0 mot EF_municipal_cars_avg och justera om flottan redan är mer elektrifierad än antaget.
- Precisera om kravet gäller BEV eller även PHEV och snäva in ΔEF-spannet därefter.
- Dokumentera vilken elprodukt fordonen laddas med (ursprungsmärkt förnybar el ger EF ≈ 0; residualmix högre).
- Harmonisera gasredovisningen (CO2 vs CO2e) i rapportkortet.
- Märk åtgärden mot kommunkoncernens organisationsutsläpp och kontrollera överlapp mot övriga transport-/mobilitetsåtgärder på portföljnivå.

---

## Frågor till miljöstrateg för detta steg

- Är det acceptabelt att presentera ett resultat (medel 118 ton/år) som helt vilar på antagen flottdata, eller ska QA-status sättas till ok först efter att verkligt fordonsregister inhämtats?
- Hur ska spänningen mellan antagen fossil delflotta (EF0 0,13, andel ~50 %) och parameterbibliotekets EF_municipal_cars_avg (0,0–0,05, redan till stor del elektrifierad) hanteras – ska baslinjen justeras ned?
- Ska kravet definieras som enbart BEV eller inkludera PHEV, och ska ΔEF-spannet snävas in därefter?
- Hur ska eventuellt överlapp med andra åtgärder som berör kommunens egna transporter hanteras i den slutliga portföljanalysen?
- Ska den potentiella (ej kvantifierade) effekten av att öppna laddinfrastrukturen för anställdas privata elbilar utredas som en separat drivare/åtgärd?