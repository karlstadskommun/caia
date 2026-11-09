# Klimatparameter-sammanställning för åtgärdsanalys

Struktur: varje rad är en möjlig standardparameter som agentflödet kan använda vid EMAP/Baslinje/BAU/Evidens/Kalkyl. "Lokalt_värde" fylls i där kommunen har egen data; annars lämnas den tom eller med "?". I den här mallen är alla lokala värden tomma, så varje parameter använder sitt standardvärde (nationell schablon) tills kommunen fyller i sina egna. En LOOKUP(...) hämtar värdet ur en datafil i sektion 12 när filen finns i data/.

---

## 1. Övergripande basparametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE_pop | Bas | Kommunbefolkning | ? | ? | personer | 2023 | - | 1 | 0 | BAU |  |
| BASE_ghg_percap_territorial | Bas | Territoriella utsläpp per capita (alla växthusgaser) | 2–3 | ? | ton CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Grov kontroll: kommunens totala territoriella utsläpp delat med befolkningen. |
| BASE_co2_total_territorial | Bas | Totala territoriella växthusgasutsläpp i kommunen | ? | LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) | ton CO2e/år | 2023 | CO2e | 1 | 0 | BAU | Hämtas från SMHI/RUS-export (data/Kommunrapport...). Avser CO2e. |
| BASE_co2_percap_territorial | Bas | Territoriella utsläpp per invånare | ? | LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / BASE_pop | ton CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Beräknat |
| BASE_share_transport_in_territorial | Bas | Transportsektorns andel av territoriella utsläpp | 40–50 % | ? | % av totala CO2e | 2023 | - | 1 | 0 | BAU |  |

---

## 2. Transporter och mobilitet – aktivitets- och beteendeparametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TR_mode_share_car | Transport | Andel resor (antal) med bil | 50–60 | | % av resor | 2023 | - | 1 | 0 | BAU | Lokalt resvaneunderlag. Se även DATA_CITIZEN_SURVEY_2024: 39% kör kortare än 5 km flera ggr/vecka. |
| TR_mode_share_non_car | Transport | Andel resor med gång, cykel, kollektivtrafik m.m. | 40–50 | ? | % av resor | 2023 | - | 1 | 0 | BAU |  |
| TR_vkt_percap_passenger_car | Transport | Årlig körsträcka personbil per capita | 7 000–10 000 | | km/person, år | 2023 | - | 1 | 0 | BAU | Används i BAU för personbilstrafik. Kan kalibreras mot kommunens trafikdata. |
| TR_share_evs_new_sales | Transport | Andel elbilar (BEV) i nybilsförsäljning | 30–40 | ? | % av nybilsförsäljning | 2023 | - | 1 | 0 | BAU |  |
| TR_share_evs_fleet_2030 | Transport | Andel elbilar i fordonsflottan 2030 (BAU) | 20–40 | ? | % av personbilsflotta | 2030 | - | 1 | 0 | BAU | Beroende på nationella prognoser (Trafikverket). |
| TR_public_transport_km_percap | Transport | Kollektivtrafikresande per capita | 400–800 | | person-km/person, år | 2023 | - | 1 | 0 | BAU | Kan fyllas lokalt från regional kollektivtrafikdata. |
| TR_cycling_km_percap | Transport | Cykelkilometer per capita | 200–600 | | km/person, år | 2023 | - | 1 | 0 | BAU | Används i åtgärder som ökar cykling. |
| TR_freight_road_tonkm_percap | Transport | Vägtransporter, godstransportarbete per capita | 3 000–7 000 | ? | tonkm/person, år | 2023 | - | 1 | 0 | BAU | Relevans framför allt för godstransportåtgärder. |
| TR_trips_percap_perday | Transport | Antal resor per person och dag | 2–3 | | resor/person, dag | 2023 | - | 1 | 0 | BAU | Baserat på kommunens resvaneundersökning; används för att härleda personkilometer per färdmedel. |
| TR_median_trip_length_km | Transport | Medianlängd per resa | 4–7 | | km per resa | 2023 | - | 1 | 0 | BAU | Lokalt värde; kombineras vid behov med reslängdsintervall i mer detaljerade modeller. |
| TR_mode_share_bike | Transport | Andel resor (antal) med cykel | 10–20 | | % av resor | 2023 | - | 1 | 0 | BAU | Lokalt resvaneunderlag; andel av alla resor med cykel. |
| TR_mode_share_bus | Transport | Andel resor (antal) med buss | 5–15 | | % av resor | 2023 | - | 1 | 0 | BAU | Lokalt resvaneunderlag; regional kollektivtrafik. |
| TR_mode_share_train | Transport | Andel resor (antal) med tåg | 1–5 | | % av resor | 2023 | - | 1 | 0 | BAU | Lokalt resvaneunderlag; framför allt regional/långväga resor. |
| TR_mode_share_walk | Transport | Andel resor (antal) till fots | 10–20 | | % av resor | 2023 | - | 1 | 0 | BAU | Lokalt resvaneunderlag; gångresor inom kommunen. |
| TR_mode_share_other | Transport | Andel resor (antal) med övriga färdmedel | 0–5 | | % av resor | 2023 | - | 1 | 0 | BAU | Övriga färdmedel (ex. moped, taxi); liten kategori, kan slås ihop vid behov. |

---

## 3. Transporter – emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_petrol_tank_to_wheel | Transport | Emissionsfaktor bensin (TTW) | 2,3–2,4 | - | kg CO2/liter | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Standard från nationella/internationella riktlinjer. |
| EF_diesel_tank_to_wheel | Transport | Emissionsfaktor diesel (TTW) | 2,6–2,7 | - | kg CO2/liter | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Standard. |
| EF_passenger_car_avg | Transport | Genomsnittlig EF för personbilar (CO2 per km) - Territoriell mix | 0,12–0,18 | - | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Gäller kommuninvånarnas bilar (blandad flotta). |
| EF_municipal_cars_avg | Transport | Genomsnittlig EF för Kommunens egna bilar | 0,0–0,05 | ? | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd |  |
| EF_bus_diesel_perpkm | Transport | EF dieselbuss per personkilometer | 0,08–0,12 | - | kg CO2/pkm | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | För kollektivtrafikåtgärder. |
| EF_ev_per_km | Transport | Utsläpp elbil per km (indirekt via el) | 0,02–0,05 | - | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Beroende på elmix (se elmix-sektion). |
| EF_freight_truck_tonkm | Transport | EF godstransport väg, tung lastbil | 0,06–0,12 | - | kg CO2/tonkm | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Beroende på lastfaktor, fordonstyp. |
| EF_air_travel_shorthaul | Transport | Flyg, kortdistans per personkilometer | 0,15–0,25 | - | kg CO2e/pkm | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Livscykelinkluderande d.v.s. CO2e. |
| EF_air_travel_longhaul | Transport | Flyg, långdistans per personkilometer | 0,09–0,15 | - | kg CO2e/pkm | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Används ihop med data om flygsträckor. Se DATA_CITIZEN_SURVEY_2024 för flygfrekvens (59% flyger aldrig). |

---

## 4. Byggnader och uppvärmning

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HEAT_energy_use_percap_res | Byggnader | Årlig energianvändning för uppvärmning i bostäder per invånare | 8000–12000 | LOOKUP(DATA_ENERGY_RESIDENTIAL, "MWh", "Per person") * 1000 | kWh/person, år | 2023 | - | 1 | 0 | BAU | Ersätter m2-mått då lokal data ges per person (6,67 MWh/år). |
| HEAT_space_heat_kwh_perm2_nonres | Byggnader | Årlig uppvärmningsenergi i lokaler | 70–140 | ? | kWh/m2, år | 2023 | - | 1 | 0 | BAU | Beror på lokaltyp; kan kalibreras mot kommunens energistatistik. |
| HEAT_dhw_share_of_total | Byggnader | Andel av värmebehov som tappvarmvatten | 20–30 | ? | % av värmebehov | 2023 | - | 1 | 0 | BAU | Viktigt när åtgärder påverkar tappvarmvatten specifikt. |
| HEAT_share_district_heating_res | Byggnader | Andel bostadsarea ansluten till fjärrvärme | 50–80 | LOOKUP(DATA_ENERGY_RESIDENTIAL, "Småhus" vs "Flerbostadshus") | % av bostadsarea | 2023 | - | 1 | 0 | BAU | Proxiy: Flerbostadshus har ofta FV, småhus ofta annat. Se datafil för fördelning MWh. |
| HEAT_share_electric_heating_res | Byggnader | Andel bostadsarea med direktverkande el/elpanna | 10–30 | ? | % av bostadsarea | 2023 | - | 1 | 0 | BAU | Relevant för åtgärder som fasar ut direktverkande el. |
| HEAT_share_biofuel_heating_res | Byggnader | Andel bostadsarea med biobränsle (panna) | 5–20 | ? | % av bostadsarea | 2023 | - | 1 | 0 | BAU | Främst i småhus. |

---

## 5. Fjärrvärme – emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_district_heat_SE_avg_2020s | Fjärrvärme | Svenskt genomsnitt fjärrvärme | 50–80 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Beror på bränslemix; används om lokal data saknas. |
| EF_district_heat_lokal_2023 | Fjärrvärme | Lokalt klimatvärde för fjärrvärmen i kommunens nät 2023 | ? | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU |  |
| EF_district_heat_lokal_2024 | Fjärrvärme | Lokalt klimatvärde för fjärrvärmen i kommunens nät 2024 | ? | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU |  |
| HEAT_district_heat_renewable_share | Fjärrvärme | Andel förnybart/återvunnet i fjärrvärmemix | 90–100 | ? | % | 2023 | - | 1 | 0 | BAU |  |

---

## 6. Elmix och elrelaterade parametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_el_SE_consumption_2020s | El | Svensk konsumtionsbaserad elmix (medel) | 40–60 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Typiska forsknings-/myndighetsvärden kring 2020-talet, tillämpade med 2023 som referensår. |
| EF_el_SE_consumption_2030_BAU | El | Förväntad svensk elmix 2030 (BAU) | 20–40 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Baserat på scenarier med mer fossilfri el och högre export, men versionerat med 2023 som gemensamt referensår i denna sammanställning. |
| EF_el_residual_mix_SE | El | Svensk residualmix (utan ursprungsgarantier) | 60–100 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Används om man inte vill tillgodoräkna ursprungsgarantier. |
| EF_el_lokal_product_guaranteed | El | Det lokala energibolagets elprodukt (ursprungsmärkt förnybar) | ? | ? | g CO2e/kWh | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| EL_share_customers_guaranteed | El | Andel elanvändning som har ursprungsmärkt el | 50–90 | ? | % av elanvändning | 2023 | - | 1 | 1 | BAU+Åtgärd | Kräver lokal uppgift från energibolaget; lämnas öppen. |

---

## 7. Livsmedel – generella emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FOOD_beef_emission_factor | Livsmedel | Nötkött, slaktkropp till butik | 20–35 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Beroende på systemgränser; robust skillnad mot växtbaserat. |
| FOOD_pork_emission_factor | Livsmedel | Fläskkött | 5–8 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_poultry_emission_factor | Livsmedel | Kyckling | 3–5 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_dairy_milk_emission_factor | Livsmedel | Mjölk, standard | 0,8–1,3 | ? | kg CO2e/liter | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_cheese_emission_factor | Livsmedel | Hårdost | 8–13 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_plant_based_drink_emission_factor | Livsmedel | Växtbaserad dryck (havre/soja etc) | 0,4–0,8 | ? | kg CO2e/liter | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_veg_mixed_emission_factor | Livsmedel | Blandade vegetabilier | 0,5–2 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |

---

## 8. Konsumtion – Konsumtionskompassen (kommunspecifika nivåer)

Här tolkas Konsumtionskompassens data som:
- "Exempelstad" = kg CO2e per person och år för respektive kategori (kolumnen heter som `ort` i kommun.toml)
- "per100sek" = kg CO2e per 100 kr konsumtion i kategorin.

### 8.1 Nivåer per capita (kg CO2e/person, år)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONS_dir_vehicle_CO2e_pc_lokal | Konsumtion | Direkta utsläpp från fordonsanvändning (bränsle, egen bil) per invånare | 600–800 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Exempelstad", "coicop=07.D") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | COICOP-kategori för direkt bränsleanvändning i fordon. |
| CONS_air_travel_CO2e_pc_lokal | Konsumtion | Utsläpp från flygresor per invånare | 600–800 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Exempelstad", "coicop=07.3.3") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Konsumtionsbaserad allokering av flyg. |
| CONS_district_heat_CO2e_pc_lokal | Konsumtion | Fjärrvärme/energi för uppvärmning/kylning per invånare | 150–300 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Exempelstad", "coicop=04.5.5") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | COICOP 04.5.5 – energianvändning i hushåll. |
| CONS_dairy_eggs_CO2e_pc_lokal | Konsumtion | Mjölk, ost, andra mejeriprodukter samt ägg per invånare | 150–250 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Exempelstad", "coicop=01.1.4") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Ger bas för åtgärder kring mejeri/ägg. |
| CONS_housing_imputed_rent_CO2e_pc_lokal | Konsumtion | Imputerad hyra/kapitalkostnad för eget boende per invånare | 150–250 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Exempelstad", "coicop=04.2.1") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Proxy för bygg-/kapitalrelaterad klimatpåverkan från boendet. |

### 8.2 Intensiteter per 100 kr (kg CO2e/100 kr)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONS_dir_vehicle_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för utgifter till fordonsbränsle (egen bil) | 8–10 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=07.D") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Används när åtgärder anges i minskade bränslekostnader. |
| CONS_air_travel_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för utgifter till flyg | 15–25 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=07.3.3") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Hög intensitet per krona. |
| CONS_district_heat_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för konsumtion av fjärrvärme/energi | 4–7 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=04.5.5") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Kopplar kostnad till utsläpp vid hushållsåtgärder. |
| CONS_dairy_eggs_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för mejeri/ägg | 3–6 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=01.1.4") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Relevant för kostrelaterade åtgärder. |
| CONS_housing_imputed_rent_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet kopplad till imputerad hyra (boendekapital) | 0,5–1,2 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=04.2.1") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Mer för avancerade modeller där boendekostnad används som styrvariabel. |

---

## 9. Övriga varor och tjänster (generella)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GOODS_clothing_footwear_CO2e_percap | Varor | Utsläpp från kläder och skor per invånare | 200–400 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Kan ersättas med Konsumtionskompassen-värde när det finns. |
| GOODS_it_electronics_CO2e_percap | Varor | Utsläpp från IT/elektronik per invånare | 100–300 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Används i åtgärder om livslängdsförlängning/återbruk. |
| GOODS_furniture_CO2e_percap | Varor | Utsläpp från möbler/inredning per invånare | 100–250 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU |  |
| GOODS_secondhand_share | Varor | Andel relevant varukonsumtion som redan är second hand/återbruk | 0,02 | LOOKUP(DATA_CITIZEN_SURVEY_2024, "Secondhand_Frequency") | andel (0–1) | 2024 | - | 1 | 1 | BAU+Åtgärd | Se medborgarundersökning 2024 (ca 50% handlar aldrig, resten ibland). |
| GOODS_secondhand_emissions_ratio | Varor | Relativ utsläppsintensitet för second hand/återbruk jämfört med nyproducerade varor | 0,25 | - | relativ faktor (kg CO2e/100 kr) | 2023 | CO2e | 0 | 1 | Åtgärd | Intervall 0,10–0,40; ~75 % lägre utsläpp per krona än nyköp; stöd från LCA för textilier/möbler/IT. |
| GOODS_repair_share | Varor | Andel produkter som repareras i stället för ersätts | 5–15 | ? | % av produkter | 2023 | - | 1 | 1 | BAU+Åtgärd | Viktigt för cirkulära åtgärder. |

---



## 10. Kommunikationsinsatser – generella beteendeparametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KOMM_typical_reach_share_general | Kommunikation | Andel av definierad målgrupp som nås (minst en gång) av en större kommunikationskampanj via flera kanaler under ett år | 50–70 | – | % av målgrupp | 2023 | - | 0 | 1 | Åtgärd | Rimlig räckvidd för kommunala/institutionella kampanjer som använder flera kanaler (sociala medier, webb, affischer, event). Baserat på generella riktlinjer kring kampanjplanering och typiska mediastudier, inte på en enskild hårt kvantifierad svensk studie. |
| KOMM_soft_max_effect_car_km | Kommunikation | Typisk maximal relativ minskning av bilresor/bilkilometer hos deltagare i mobilitetsprojekt som bygger på information, personlig reseplanering och andra mjuka åtgärder (utan ekonomiska styrmedel) | 10–15 | – | % förändring bland deltagare | 2023 | - | 0 | 1 | Åtgärd | Metastudier och utvärderingar av “personal travel planning” och hållbart resande visar ofta 5–20 % minskning av bilresor hos deltagare, med medelvärden kring 11–15 %. Parametern avser effekt bland de som nås och engageras, inte i hela befolkningen. |
| KOMM_soft_max_effect_matsvinn | Kommunikation | Typisk maximal relativ minskning av matsvinn (kg) i en målgrupp/enhet vid informationskampanjer och nudging (t.ex. hushåll, skolmatsal, storkök) | 20–30 | – | % förändring bland deltagare/enheter | 2023 | - | 0 | 1 | Åtgärd | Litteraturöversikter och fallstudier för matsvinnsarbete i offentliga kök och hushåll visar ofta minskningar i storleksordningen 15–35 % när information/nudging kombineras med praktiska åtgärder (portionering, tallriksstorlek, feedback etc.). Parametern anger en “rimlig” maxeffekt, inte ett löfte. |

---

## 11. Livsmedelskonsumtion – nivåer per capita

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Lokalt_värde | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MAT_meat_total_kg_percap_SE | Livsmedel | Totalkonsumtion av kött (nöt, gris, lamm, fjäderfä; slaktad vikt) per person och år, Sverige | 79–80 | LOOKUP(DATA_CITIZEN_SURVEY_2024, "Meat_Frequency") | kg/person, år | 2024 | - | 1 | 0 | BAU | Använd frekvensdata från medborgarundersökning för att justera nationellt snitt om möjligt. |
| MAT_milk_l_percap_SE | Livsmedel | Konsumtion av konsumtionsmjölk per person och år, Sverige | ~61 | – | liter/person, år | 2023 | - | 1 | 0 | BAU | Jordbruksstatistisk sammanställning anger ca 61,4 liter per person 2023. |
| MAT_cheese_kg_percap_SE | Livsmedel | Konsumtion av ost per person och år, Sverige | 19–21 | – | kg/person, år | 2023 | - | 1 | 0 | BAU | Preliminära siffror visar ~19,2 kg 2023 och 21,1 kg 2024. |
| MAT_eggs_kg_percap_SE | Livsmedel | Konsumtion av ägg per person och år, Sverige | 13–14 | – | kg/person, år | 2023 | - | 1 | 0 | BAU | Jordbruksverket anger omkring 14 kg per person och år i de senaste sammanställningarna. |
| MAT_food_total_CO2e_percap_SE | Livsmedel | Konsumtionsbaserade växthusgasutsläpp från livsmedel (hela kosten) per person | ~1,5 | – | ton CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Folkhälsomyndighetens/Naturvårdsverkets sammanställning anger att mat står för cirka 1,5 ton CO2e per person och år, ungefär en femtedel av de konsumtionsbaserade utsläppen. |
| MAT_food_waste_total_kg_percap_households | Livsmedel | Totalt livsmedelsavfall (fast + till avlopp) från hushåll per person och år, Sverige | ~74 | – | kg/person, år | 2021–2023 | - | 1 | 0 | BAU | Naturvårdsverket uppskattar att hushåll slänger omkring 74 kg livsmedel per person och år som fast avfall, utöver cirka 18 kg mat och dryck via avloppet (årtal varierar något mellan studier). |
| MAT_food_waste_edible_kg_percap_households | Livsmedel | Matsvinn (ätbar del) i hushåll per person och år, Sverige | 30–35 | – | kg/person, år | 2021–2023 | - | 1 | 0 | BAU | Livsmedelsverket/Naturvårdsverket anger ca 16 kg ätbart livsmedelsavfall i sopor per person och år samt cirka 18 kg mat och dryck via avloppet, dvs totalt runt 34 kg ätbart matsvinn. |
| MAT_share_food_expenditure_out_of_home | Livsmedel | Andel av hushållens **matrelaterade** utgifter som går till restauranger, caféer, hotell (äta ute) | ~35 | – | % av matrelaterade utgifter | 2022 | - | 1 | 1 | BAU+Åtgärd | SCB visar att hushåll lägger ca 13–14 % av totala utgifterna på livsmedel/alkoholfria drycker och ca 7 % på restauranger/caféer/hotell. Det innebär att ungefär 7 / (13,6+7) ≈ 34 % av matrelaterad konsumtion sker utanför hemmet. |

---

## 12. Datakällor och Filer (Register)

Här listas kommunens datafiler. CAIA läser filerna som finns i `data/` och lägger ett sammandrag av var och en i datakontexten som agenterna får. En källa som CAIA inte läser står med för att visa var avskrivna tal kommer ifrån.

| Logiskt_Namn | Filnamn (i `data/`) | Beskrivning | Nyckelvariabler | År (om ej i fil) |
| --- | --- | --- | --- | --- |
| DATA_EMISSIONS_TOTAL | `kommunrapport_vaxthusgaser_totalt.csv` | Totala utsläpp per sektor och år (SMHI/RUS) | Sektor, År, Utsläppsslag | - |
| DATA_MUNICIPAL_ORG | `Kommunkoncernens_egna_konsumtionsbaserade_CO2e-utsläpp.json` | Kommunens egna organisationsutsläpp | Huvudkategori, Kategori | 2022 |
| DATA_CONSUMPTION_FOOTPRINT | `fotavtryck-per-konsumtionskategori.json` | Konsumtionsbaserade utsläpp per kategori (COICOP) för medelinvånare | coicop, Exempelstad (kg/pers) | 2023 (implied) |
| DATA_HOUSEHOLD_TIME_SERIES | `hushållens-totala-utsläpp-över-tid.json` | Totala konsumtionsutsläpp över tid | region, 2019-2023 | - |
| DATA_TRAVEL_SURVEY | `resvaneundersokning.pdf` | Lokal resvaneundersökning. CAIA läser inte PDF:en: skriv av talen (färdmedelsfördelning, resor per person och dag, reslängd) i sektion 2 med tabell och sida | Färdmedelsfördelning, Resor per dag | - |
| DATA_ENERGY_RESIDENTIAL | `energianvandning_bostader.csv` | Energianvändning bostäder (Småhus/Flerbostadshus) | Kategori, MWh | - |
| DATA_CITIZEN_SURVEY_2024 | `medborgarundersokning_2024.csv` | Medborgarundersökning 2024 (Kött, Secondhand, Bil, Flyg) | Question, Response_Option, Percentage | 2024 |

**Instruktion till agenterna:**
När en rad i parametertabellen har `LOOKUP(DATA_XYZ, ...)` som lokalt värde:
1.  Hämta värdet ur datakontextens sammandrag av den filen. Ingen kod körs, värdet läses ur texten.
2.  Ange vilken rad eller kategori i sammandraget värdet kommer från.
3.  Finns inget sammandrag av filen, använd radens standardvärde och skriv att det är en schablon.
