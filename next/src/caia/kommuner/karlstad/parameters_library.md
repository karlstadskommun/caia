# Klimatparameter-sammanställning för åtgärdsanalys

Struktur: varje rad är en möjlig standardparameter som agentflödet kan använda vid EMAP/Baslinje/BAU/Evidens/Kalkyl. "Karlstad_specifikt" fylls i där lokal data finns; annars lämnas den tom eller med "?".

---

## 1. Övergripande basparametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE_pop | Bas | Kommunbefolkning | ? | 97 233 | personer | 2023 | - | 1 | 0 | BAU | SCB 2023. (98 084 år 2024). |
| BASE_ghg_percap_territorial | Bas | Territoriella utsläpp per capita (alla växthusgaser) | 2–3 | ? | ton CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Grov kontroll. 225 kt / 97k inv ≈ 2.3 ton. |
| BASE_co2_total_territorial | Bas | Totala territoriella växthusgasutsläpp i kommunen | ? | LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) | ton CO2e/år | 2023 | CO2e | 1 | 0 | BAU | Hämtas från SMHI/RUS-export (data/Kommunrapport...). Avser CO2e. |
| BASE_co2_percap_territorial | Bas | Territoriella utsläpp per invånare | ? | LOOKUP(DATA_EMISSIONS_TOTAL, "Totala utsläpp", 2023) / BASE_pop | ton CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Beräknat |
| BASE_share_transport_in_territorial | Bas | Transportsektorns andel av territoriella utsläpp | 40–50 % | 55 % | % av totala CO2e | 2023 | - | 1 | 0 | BAU | Klimatkollen/SMHI 2023: Transporter står för ca 55% av territoriella utsläpp. |

---

## 2. Transporter och mobilitet – aktivitets- och beteendeparametrar

Resvanetalen nedan kommer ur Resvaneundersökning Region Värmland 2023, kommunrapport Karlstad (DATA_TRAVEL_SURVEY i sektion 12), här kallad RVU 2023. Figur, tabell och sida står per rad. Talen gäller hela kommunen och boende 16-84 år, eftersom CAIA:s åtgärder gäller kommunen. PAC läser samma rapport men använder tätortsraden (tabell 14 s. 29) för enskilda planer, därför skiljer sig bilandelen mellan verktygen: 53 procent för kommunen, 47 för tätorten. Tal som rapporten inte redovisar (körsträcka och personkilometer per färdmedel) är schabloner.

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TR_mode_share_car | Transport | Andel resor (antal) med bil | 50–60 | 53 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen, 7 205 resor. Bil som förare och passagerare tillsammans; rapporten delar inte upp dem. Tätorten 47 (tabell 14 s. 29). Se även DATA_CITIZEN_SURVEY_2024: 39% kör kortare än 5 km flera ggr/vecka. |
| TR_mode_share_non_car | Transport | Andel resor med gång, cykel, kollektivtrafik m.m. | 40–50 | 47 | % av resor | 2023 | - | 1 | 0 | BAU | 100 minus bilandelen 53. Samma sak som summan av cykel 20, buss 11, tåg 1, till fots 13 och övrigt 2 i RVU 2023 figur 18 s. 25; uppdelningen står i TR_mode_share_bike, _bus, _train, _walk och _other. |
| TR_vkt_percap_passenger_car | Transport | Årlig körsträcka personbil per capita | 7 000–10 000 | ? | km/person, år | 2023 | - | 1 | 0 | BAU | Schablon. Finns inte i RVU 2023, som redovisar resor och reslängder men ingen körsträcka per person. Används i BAU för personbilstrafik. Lokal källa att hämta: Trafikanalys körsträckor per kommun. |
| TR_share_evs_new_sales | Transport | Andel elbilar (BEV) i nybilsförsäljning | 30–40 | ~30 | % av nybilsförsäljning | 2023 | - | 1 | 0 | BAU | Newsworthy/SCB 2023: Andel laddbara (BEV+PHEV) ca 45% i Q4. Estimerat ren elbil (BEV) ca 30%. |
| TR_share_evs_fleet_2030 | Transport | Andel elbilar i fordonsflottan 2030 (BAU) | 20–40 | ? | % av personbilsflotta | 2030 | - | 1 | 0 | BAU | Beroende på nationella prognoser (Trafikverket). Karlstad hade ca 3-4% elbilar i trafik 2023. |
| TR_public_transport_km_percap | Transport | Kollektivtrafikresande per capita | 400–800 | ? | person-km/person, år | 2023 | - | 1 | 0 | BAU | Schablon. Finns inte i RVU 2023, som inte redovisar personkilometer per färdmedel. Kan fyllas lokalt från regional kollektivtrafikdata. |
| TR_cycling_km_percap | Transport | Cykelkilometer per capita | 200–600 | ? | km/person, år | 2023 | - | 1 | 0 | BAU | Schablon. Finns inte i RVU 2023, som inte redovisar personkilometer per färdmedel. Används i åtgärder som ökar cykling. |
| TR_freight_road_tonkm_percap | Transport | Vägtransporter, godstransportarbete per capita | 3 000–7 000 | ? | tonkm/person, år | 2023 | - | 1 | 0 | BAU | Relevans framför allt för godstransportåtgärder. |
| TR_trips_percap_perday | Transport | Antal resor per person och dag | 2–3 | 2,2 | resor/person, dag | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 14 s. 20, hela kommunen, 4 930 svarande. Tätort och landsbygd har också 2,2 (tabell 10 s. 20), samma tal PAC räknar med. Enligt brödtexten s. 20 ingår även de som inte reste under mätdagen, så talet är per invånare 16-84 år och gäller alla veckodagar. Används för att härleda personkilometer per färdmedel. |
| TR_median_trip_length_km | Transport | Medianlängd per resa | 4–7 | 5 | km per resa | 2023 | - | 1 | 0 | BAU | RVU 2023 s. 23 och figur 16 s. 23: medianen för en resa i kommunen, alla färdmedel, avrundad till hel kilometer, 7 619 resor. Det är en median, inte ett medelvärde. Den som räknar kilometer som resor gånger reslängd behöver ett medelvärde, och medianen skalar bort långresorna, så kilometertalet blir för lågt. Rapporten publicerar inget medelvärde. PAC räknar också med median och säger det; medelreslängden är efterfrågad hos kommunen och Region Värmland. För bilresor enbart ger PAC:s härledning ur samma rapport en bilmedian på cirka 7,6 km för kommunen (7,0 för tätorten, plus minus 1,5 km). |
| TR_mode_share_bike | Transport | Andel resor (antal) med cykel | 10–20 | 20 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen. Tätorten 23 (tabell 14 s. 29). |
| TR_mode_share_bus | Transport | Andel resor (antal) med buss | 5–15 | 11 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen. Tätorten 12 (tabell 14 s. 29). |
| TR_mode_share_train | Transport | Andel resor (antal) med tåg | 1–5 | 1 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen. Tågsegmentet saknar etikett i figuren; 1 är resten upp till 100, eftersom de märkta segmenten summerar till 99. Tätorten 1 (tabell 14 s. 29). Framför allt regionala och långväga resor. |
| TR_mode_share_walk | Transport | Andel resor (antal) till fots | 10–20 | 13 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen. Tätorten 15 (tabell 14 s. 29). |
| TR_mode_share_other | Transport | Andel resor (antal) med övriga färdmedel | 0–5 | 2 | % av resor | 2023 | - | 1 | 0 | BAU | RVU 2023 figur 18 s. 25, hela kommunen. Tätorten 2 (tabell 14 s. 29). Övriga färdmedel (ex. moped, taxi); liten kategori, kan slås ihop vid behov. |

---

## 3. Transporter – emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_petrol_tank_to_wheel | Transport | Emissionsfaktor bensin (TTW) | 2,3–2,4 | - | kg CO2/liter | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Standard från nationella/internationella riktlinjer. |
| EF_diesel_tank_to_wheel | Transport | Emissionsfaktor diesel (TTW) | 2,6–2,7 | - | kg CO2/liter | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Standard. |
| EF_passenger_car_avg | Transport | Genomsnittlig EF för personbilar (CO2 per km) - Territoriell mix | 0,12–0,18 | - | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Gäller kommuninvånarnas bilar (blandad flotta). |
| EF_municipal_cars_avg | Transport | Genomsnittlig EF för Kommunens egna bilar | 0,0–0,05 | Beräknas (El/Gas + 2% bensin) | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | "Alla är el eller gas. Vissa gasbilar tankas med bensin (~2% av totalt drivmedel)." |
| EF_bus_diesel_perpkm | Transport | EF dieselbuss per personkilometer | 0,08–0,12 | - | kg CO2/pkm | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | För kollektivtrafikåtgärder. |
| EF_ev_per_km | Transport | Utsläpp elbil per km (indirekt via el) | 0,02–0,05 | - | kg CO2/km | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Beroende på elmix (se elmix-sektion). |
| EF_freight_truck_tonkm | Transport | EF godstransport väg, tung lastbil | 0,06–0,12 | - | kg CO2/tonkm | 2023 | CO2 | 1 | 1 | BAU+Åtgärd | Beroende på lastfaktor, fordonstyp. |
| EF_air_travel_shorthaul | Transport | Flyg, kortdistans per personkilometer | 0,15–0,25 | - | kg CO2e/pkm | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Livscykelinkluderande d.v.s. CO2e. |
| EF_air_travel_longhaul | Transport | Flyg, långdistans per personkilometer | 0,09–0,15 | - | kg CO2e/pkm | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Används ihop med data om flygsträckor. Se DATA_CITIZEN_SURVEY_2024 för flygfrekvens (59% flyger aldrig). |

---

## 4. Byggnader och uppvärmning

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HEAT_energy_use_percap_res | Byggnader | Årlig energianvändning för uppvärmning i bostäder per invånare | 8000–12000 | LOOKUP(DATA_ENERGY_RESIDENTIAL, "MWh", "Per person") * 1000 | kWh/person, år | 2022 | - | 1 | 0 | BAU | Ersätter m2-mått då lokal data ges per person (6,67 MWh/år). |
| HEAT_space_heat_kwh_perm2_nonres | Byggnader | Årlig uppvärmningsenergi i lokaler | 70–140 | ? | kWh/m2, år | 2023 | - | 1 | 0 | BAU | Beror på lokaltyp; kan kalibreras mot kommunens energistatistik. |
| HEAT_dhw_share_of_total | Byggnader | Andel av värmebehov som tappvarmvatten | 20–30 | ? | % av värmebehov | 2023 | - | 1 | 0 | BAU | Viktigt när åtgärder påverkar tappvarmvatten specifikt. |
| HEAT_share_district_heating_res | Byggnader | Andel bostadsarea ansluten till fjärrvärme | 50–80 | LOOKUP(DATA_ENERGY_RESIDENTIAL, "Småhus" vs "Flerbostadshus") | % av bostadsarea | 2022 | - | 1 | 0 | BAU | Proxy: Flerbostadshus har ofta FV, småhus ofta annat. Se datafil för fördelning MWh. |
| HEAT_share_electric_heating_res | Byggnader | Andel bostadsarea med direktverkande el/elpanna | 10–30 | ? | % av bostadsarea | 2023 | - | 1 | 0 | BAU | Relevant för åtgärder som fasar ut direktverkande el. |
| HEAT_share_biofuel_heating_res | Byggnader | Andel bostadsarea med biobränsle (panna) | 5–20 | ? | % av bostadsarea | 2023 | - | 1 | 0 | BAU | Främst i småhus. |

---

## 5. Fjärrvärme – emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_district_heat_SE_avg_2020s | Fjärrvärme | Svenskt genomsnitt fjärrvärme | 50–80 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Beror på bränslemix; används om lokal data saknas. |
| EF_district_heat_Karlstad_2023 | Fjärrvärme | Lokalt klimatvärde fjärrvärme Karlstad 2023 | ? | 19 | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Fjärrvärmens lokala miljövärden 2023. Låg klimatintensitet. |
| EF_district_heat_Karlstad_2024 | Fjärrvärme | Lokalt klimatvärde fjärrvärme Karlstad 2024 | ? | 10 | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Fjärrvärmens lokala miljövärden 2024. Mycket låg klimatintensitet, används här med 2023 som gemensamt referensår i sammanställningen. |
| HEAT_district_heat_renewable_share | Fjärrvärme | Andel förnybart/återvunnet i fjärrvärmemix | 90–100 | ~100 | % | 2023 | - | 1 | 0 | BAU | Karlstads fjärrvärme klassas som 100 % förnybar/återvunnen i produktinfo. |

---

## 6. Elmix och elrelaterade parametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EF_el_SE_consumption_2020s | El | Svensk konsumtionsbaserad elmix (medel) | 40–60 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Typiska forsknings-/myndighetsvärden kring 2020-talet, tillämpade med 2023 som referensår. |
| EF_el_SE_consumption_2030_BAU | El | Förväntad svensk elmix 2030 (BAU) | 20–40 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Baserat på scenarier med mer fossilfri el och högre export, men versionerat med 2023 som gemensamt referensår i denna sammanställning. |
| EF_el_residual_mix_SE | El | Svensk residualmix (utan ursprungsgarantier) | 60–100 | ? | g CO2e/kWh | 2023 | CO2e | 1 | 0 | BAU | Används om man inte vill tillgodoräkna ursprungsgarantier. |
| EF_el_Karlstad_product_guaranteed | El | Karlstads Energi elprodukt (ursprungsmärkt förnybar) | ? | 0 | g CO2e/kWh | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Enligt produktinfo; gäller de kunder som valt denna produkt. |
| EL_share_customers_guaranteed | El | Andel elanvändning som har ursprungsmärkt el | 50–90 | ? | % av elanvändning | 2023 | - | 1 | 1 | BAU+Åtgärd | Kräver lokal uppgift från energibolaget; lämnas öppen. |

---

## 7. Livsmedel – generella emissionsfaktorer

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FOOD_beef_emission_factor | Livsmedel | Nötkött, slaktkropp till butik | 20–35 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd | Beroende på systemgränser; robust skillnad mot växtbaserat. |
| FOOD_pork_emission_factor | Livsmedel | Fläskkött | 5–8 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_poultry_emission_factor | Livsmedel | Kyckling | 3–5 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_dairy_milk_emission_factor | Livsmedel | Mjölk, standard | 0,8–1,3 | ? | kg CO2e/liter | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_cheese_emission_factor | Livsmedel | Hårdost | 8–13 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_plant_based_drink_emission_factor | Livsmedel | Växtbaserad dryck (havre/soja etc) | 0,4–0,8 | ? | kg CO2e/liter | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |
| FOOD_veg_mixed_emission_factor | Livsmedel | Blandade vegetabilier | 0,5–2 | ? | kg CO2e/kg | 2023 | CO2e | 1 | 1 | BAU+Åtgärd |  |

---

## 8. Konsumtion – Konsumtionskompassen (Karlstad-specifika nivåer)

Här tolkas Konsumtionskompassens data som:
- "Karlstad" = kg CO2e per person och år för respektive kategori
- "per100sek" = kg CO2e per 100 kr konsumtion i kategorin.

### 8.1 Nivåer per capita (kg CO2e/person, år)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONS_dir_vehicle_CO2e_pc_Karlstad | Konsumtion | Direkta utsläpp från fordonsanvändning (bränsle, egen bil) per invånare | 600–800 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=07.D") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | COICOP-kategori för direkt bränsleanvändning i fordon. |
| CONS_air_travel_CO2e_pc_Karlstad | Konsumtion | Utsläpp från flygresor per invånare | 600–800 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=07.3.3") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Konsumtionsbaserad allokering av flyg. |
| CONS_district_heat_CO2e_pc_Karlstad | Konsumtion | Fjärrvärme/energi för uppvärmning/kylning per invånare | 150–300 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=04.5.5") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | COICOP 04.5.5 – energianvändning i hushåll. |
| CONS_dairy_eggs_CO2e_pc_Karlstad | Konsumtion | Mjölk, ost, andra mejeriprodukter samt ägg per invånare | 150–250 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=01.1.4") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Ger bas för åtgärder kring mejeri/ägg. |
| CONS_housing_imputed_rent_CO2e_pc_Karlstad | Konsumtion | Imputerad hyra/kapitalkostnad för eget boende per invånare | 150–250 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "Karlstad", "coicop=04.2.1") | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Proxy för bygg-/kapitalrelaterad klimatpåverkan från boendet. |

### 8.2 Intensiteter per 100 kr (kg CO2e/100 kr)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONS_dir_vehicle_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för utgifter till fordonsbränsle (egen bil) | 8–10 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=07.D") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Används när åtgärder anges i minskade bränslekostnader. |
| CONS_air_travel_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för utgifter till flyg | 15–25 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=07.3.3") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Hög intensitet per krona. |
| CONS_district_heat_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för konsumtion av fjärrvärme/energi | 4–7 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=04.5.5") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Kopplar kostnad till utsläpp vid hushållsåtgärder. |
| CONS_dairy_eggs_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet för mejeri/ägg | 3–6 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=01.1.4") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Relevant för kostrelaterade åtgärder. |
| CONS_housing_imputed_rent_intensity_CO2e_per100sek | Konsumtion | Klimatintensitet kopplad till imputerad hyra (boendekapital) | 0,5–1,2 | LOOKUP(DATA_CONSUMPTION_FOOTPRINT, "per100sek", "coicop=04.2.1") | kg CO2e/100 kr | 2023 | CO2e | 0 | 1 | Åtgärd | Mer för avancerade modeller där boendekostnad används som styrvariabel. |

---

## 9. Övriga varor och tjänster (generella)

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GOODS_clothing_footwear_CO2e_percap | Varor | Utsläpp från kläder och skor per invånare | 200–400 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Kan ersättas med Konsumtionskompassen-värde när det finns. |
| GOODS_it_electronics_CO2e_percap | Varor | Utsläpp från IT/elektronik per invånare | 100–300 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU | Används i åtgärder om livslängdsförlängning/återbruk. |
| GOODS_furniture_CO2e_percap | Varor | Utsläpp från möbler/inredning per invånare | 100–250 | ? | kg CO2e/person, år | 2023 | CO2e | 1 | 0 | BAU |  |
| GOODS_secondhand_share | Varor | Andel relevant varukonsumtion som redan är second hand/återbruk | 0,02 | LOOKUP(DATA_CITIZEN_SURVEY_2024, "Secondhand_Frequency") | andel (0–1) | 2024 | - | 1 | 1 | BAU+Åtgärd | Se medborgarundersökning 2024 (ca 50% handlar aldrig, resten ibland). |
| GOODS_secondhand_emissions_ratio | Varor | Relativ utsläppsintensitet för second hand/återbruk jämfört med nyproducerade varor | 0,25 | - | relativ faktor (kg CO2e/100 kr) | 2023 | CO2e | 0 | 1 | Åtgärd | Intervall 0,10–0,40; ~75 % lägre utsläpp per krona än nyköp; stöd från LCA för textilier/möbler/IT. |
| GOODS_repair_share | Varor | Andel produkter som repareras i stället för ersätts | 5–15 | ? | % av produkter | 2023 | - | 1 | 1 | BAU+Åtgärd | Viktigt för cirkulära åtgärder. |

---



## 10. Kommunikationsinsatser – generella beteendeparametrar

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KOMM_typical_reach_share_general | Kommunikation | Andel av definierad målgrupp som nås (minst en gång) av en större kommunikationskampanj via flera kanaler under ett år | 50–70 | – | % av målgrupp | 2023 | - | 0 | 1 | Åtgärd | Rimlig räckvidd för kommunala/institutionella kampanjer som använder flera kanaler (sociala medier, webb, affischer, event). Baserat på generella riktlinjer kring kampanjplanering och typiska mediastudier, inte på en enskild hårt kvantifierad svensk studie. |
| KOMM_soft_max_effect_car_km | Kommunikation | Typisk maximal relativ minskning av bilresor/bilkilometer hos deltagare i mobilitetsprojekt som bygger på information, personlig reseplanering och andra mjuka åtgärder (utan ekonomiska styrmedel) | 10–15 | – | % förändring bland deltagare | 2023 | - | 0 | 1 | Åtgärd | Metastudier och utvärderingar av “personal travel planning” och hållbart resande visar ofta 5–20 % minskning av bilresor hos deltagare, med medelvärden kring 11–15 %. Parametern avser effekt bland de som nås och engageras, inte i hela befolkningen. |
| KOMM_soft_max_effect_matsvinn | Kommunikation | Typisk maximal relativ minskning av matsvinn (kg) i en målgrupp/enhet vid informationskampanjer och nudging (t.ex. hushåll, skolmatsal, storkök) | 20–30 | – | % förändring bland deltagare/enheter | 2023 | - | 0 | 1 | Åtgärd | Litteraturöversikter och fallstudier för matsvinnsarbete i offentliga kök och hushåll visar ofta minskningar i storleksordningen 15–35 % när information/nudging kombineras med praktiska åtgärder (portionering, tallriksstorlek, feedback etc.). Parametern anger en “rimlig” maxeffekt, inte ett löfte. |

---

## 11. Livsmedelskonsumtion – nivåer per capita

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
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
| DATA_EMISSIONS_TOTAL | `Kommunrapport_karlstad_vaxthusgaser_totalt.csv` | Totala utsläpp per sektor och år (SMHI/RUS) | Sektor, År, Utsläppsslag | - |
| DATA_MUNICIPAL_ORG | `Kommunkoncernens_egna_konsumtionsbaserade_CO2e-utsläpp.json` | Kommunens egna organisationsutsläpp | Huvudkategori, Kategori | 2022 |
| DATA_CONSUMPTION_FOOTPRINT | `fotavtryck-per-konsumtionskategori.json` | Konsumtionsbaserade utsläpp per kategori (COICOP) för medelinvånare | coicop, Karlstad (kg/pers) | 2023 (implied) |
| DATA_HOUSEHOLD_TIME_SERIES | `hushållens-totala-utsläpp-över-tid.json` | Totala konsumtionsutsläpp över tid | region, 2019-2023 | - |
| DATA_TRAVEL_SURVEY | `rvu-karlstad-kommunrapport.pdf` | Resvaneundersökning Region Värmland 2023, kommunrapport Karlstad (Region Värmland och Enkätfabriken). PDF:en ligger inte i data/ och läses inte av agenterna; talen som används är avskrivna i sektion 2 med figur, tabell och sida | Färdmedelsfördelning (figur 18 s. 25), resor per person och dag (figur 14 s. 20), medianreslängd (s. 23) | 2023 |
| DATA_ENERGY_RESIDENTIAL | `energianvandning_bostader_karlstad.csv` | Energianvändning bostäder (Småhus/Flerbostadshus) | Kategori, MWh | - |
| DATA_CITIZEN_SURVEY_2024 | `medborgarundersokning_karlstad_2024.csv` | Medborgarundersökning 2024 (Kött, Secondhand, Bil, Flyg) | Question, Response_Option, Percentage | 2024 |

**Instruktion till agenterna:**
När en rad i parametertabellen har `LOOKUP(DATA_XYZ, ...)` som lokalt värde:
1.  Hämta värdet ur datakontextens sammandrag av den filen. Ingen kod körs, värdet läses ur texten.
2.  Ange vilken rad eller kategori i sammandraget värdet kommer från.
3.  Finns inget sammandrag av filen, använd radens standardvärde och skriv att det är en schablon.

---

## 13. Byggmaterial och byggavfall

Två källor, båda öppna. Per kilo material: Boverkets klimatdatabas, version 02.07.000 (Excel från boverket.se/sv/om-boverket/oppna-data/boverkets-klimatdatabas/), med Resurs-ID per rad. Standardvärdet är spannet från databasens typiska värde till dess konservativa värde, som är det typiska gånger 1,25 (databasens kolumn "A1-A3 faktor för konservativa värden"). Värdena gäller produktskedet A1-A3; transport (A4) och byggspill (A5) står i kommentaren. Per kvadratmeter renovering: SKR och Offentliga fastigheter 2022, "Klimatpåverkan från renoverings- och ombyggnadsprojekt", skriven av IVL Svenska Miljöinstitutet, som redovisar åtta pilotprojekt ur IVL:s projekt Klimatkrav till rimlig kostnad ROT (Andersson m.fl. 2022). Byggdelarna stomme (8-10) och husunderbyggnad (7-8) står inte med, eftersom de bara bygger på tre respektive två projekt. Ingen källa ger en faktor per kilo byggavfall; rivningsprocessen per kvadratmeter nedan är det som finns.

| Parameter_ID | Kategori | Beskrivning | Standardvärde (SE/EU-typiskt) | Karlstad_specifikt | Enhet | Ar_galler | Gas_typ | Use_BAU | Use_Atgard | Primär_användning | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BYGG_municipal_husbyggande_CO2e | Bygg | Kommunkoncernens egna utsläpp från husbyggande | ? | LOOKUP(DATA_MUNICIPAL_ORG, "Husbyggande") | ton CO2e/år | 2022 | CO2e | 1 | 0 | BAU | Kategorin Husbyggande under Fastigheter & Anläggningsarbeten i datakontextens sammandrag. Konsumtionsbaserat; filen skiljer inte nybyggnad från renovering. Specialiserade bygg- och anläggningstjänster är en egen kategori i samma fil. |
| BYGG_renov_CO2e_perm2 | Bygg | Renovering och ombyggnad, bygg- och rivningsskedet (produkt, transport, byggprocess, rivning) | 40-160 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 s. 17 och figur 4, åtta pilotprojekt (flerbostadshus, kontor, en utbildningslokal). Produktskedet är största delen i alla åtta. Driftenergi ingår inte. Byggdelsraderna under (BYGG_renov_installationer till BYGG_renov_rivning) är delar av den här totalen: räkna med totalen eller med byggdelarna, aldrig båda. Stomme och husunderbyggnad saknas bland byggdelarna. |
| BYGG_renov_installationer_CO2e_perm2 | Bygg | Renovering, produktskedet för installationer | 17-40 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 tabell 2 s. 17, fem projekt. Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_renov_fasad_CO2e_perm2 | Bygg | Renovering, produktskedet för fasader | 5-34 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 tabell 2 s. 17, åtta projekt. Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_renov_stomkomplettering_CO2e_perm2 | Bygg | Renovering, produktskedet för stomkomplettering och rumsbildning | 2-33 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 tabell 2 s. 17, sju projekt. Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_renov_ytskikt_CO2e_perm2 | Bygg | Renovering, produktskedet för invändiga ytskikt | 4-19 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 tabell 2 s. 17, sex projekt. Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_renov_yttertak_CO2e_perm2 | Bygg | Renovering, produktskedet för yttertak | 3-18 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 tabell 2 s. 17, åtta projekt. 3 vid ett mindre ingrepp, 18 när hela taket byttes (s. 18). Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_renov_rivning_CO2e_perm2 | Bygg | Renovering, rivningsprocessen (demontering, transport, avfallshantering) | 4-9 | ? | kg CO2e/m2 BTA | 2022 | CO2e | 1 | 1 | BAU+Åtgärd | SKR 2022 figur 7 s. 19 och s. 20: sex av åtta piloter ligger på 4-9, hela spannet är 1-26 (26 vid omfattande rivning, cirka 1 när bara tak och fasad berördes). Avfallshanteringen är oftast största delen. Del av BYGG_renov_CO2e_perm2, räkna inte båda. |
| BYGG_newbuild_ref_CO2e_perm2 | Bygg | Nyproduktion flerbostadshus, referensvärde för jämförelse | 300-450 | ? | kg CO2e/m2 BTA | 2021 | CO2e | 0 | 1 | Åtgärd | Boverkets referensvärdesstudie (Malmqvist m.fl. 2021), citerad i SKR 2022 s. 12 och 17. Kontor 300-400. Andrahandsuppgift. |
| BYGG_EF_reused_product | Bygg | Återanvänd byggprodukt, produktskedet A1-A3 | 0 | ? | kg CO2e/kg | 2026 | CO2e | 0 | 1 | Åtgärd | Boverket 6000000174. A5 byggspill 0, A4 transport 0,00539 kg CO2e/kg och ska räknas med (Boverkets handbok, Indata för produktskedet). Material för upprustning ingår inte i nollan. |
| BYGG_EF_concrete_C30_37 | Bygg | Fabriksbetong husbyggnad C30/37 | 0,116-0,145 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000032. A4 0,00472, A5 0,00449 kg CO2e/kg. 2 350 kg/m3. |
| BYGG_EF_concrete_C30_37_lowcarbon | Bygg | Fabriksbetong husbyggnad klimatförbättrad C30/37 | 0,0867-0,108 | ? | kg CO2e/kg | 2026 | CO2e | 0 | 1 | Åtgärd | Boverket 6000000033. A4 0,00472, A5 0,00339 kg CO2e/kg. |
| BYGG_EF_rebar_scrap | Bygg | Armeringsstål, 100 % skrotbaserat | 0,596-0,745 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000154. A4 0,0989, A5 0,076 kg CO2e/kg. |
| BYGG_EF_structural_steel | Bygg | Konstruktionsstål, 80 % primär råvara | 2,52-3,15 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000150. A4 0,0989, A5 0,162 kg CO2e/kg. Skrotbaserat (6000000151): 0,9-1,13. |
| BYGG_EF_steel_studs | Bygg | Lättreglar av stål, primär | 2,41-3,01 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000152. A4 0,036, A5 0,061 kg CO2e/kg. |
| BYGG_EF_sheet_steel | Bygg | Tunnplåt för beklädnad, 80 % primär | 2,59-3,24 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000153. A4 0,0989, A5 0,167 kg CO2e/kg. |
| BYGG_EF_sawn_timber | Bygg | Sågat virke, barrträ | 0,064-0,08 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000007. A4 0,0225, A5 0,0103 kg CO2e/kg. 455 kg/m3. Biogent kol ingår inte. |
| BYGG_EF_glulam | Bygg | Limträ, gran | 0,106-0,133 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000168. A4 0,045, A5 0,00888 kg CO2e/kg. 434 kg/m3. |
| BYGG_EF_gypsum_board | Bygg | Gipsskiva, standardskiva | 0,227-0,284 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000020. A4 0,0315, A5 0,0378 kg CO2e/kg. 710 kg/m3. |
| BYGG_EF_glass_wool | Bygg | Glasull, skivor och rullar | 0,89-1,11 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000001. A4 0,045, A5 0,081 kg CO2e/kg. 18,7 kg/m3. |
| BYGG_EF_stone_wool | Bygg | Stenull, skivor och rullar | 1,28-1,6 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000123. A4 0,045, A5 0,115 kg CO2e/kg. 29 kg/m3. |
| BYGG_EF_brick | Bygg | Tegelsten | 0,251-0,314 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000082. A4 0,0629, A5 0,0188 kg CO2e/kg. 1 800 kg/m3. |
| BYGG_EF_window_wood | Bygg | Fönster, trä, inåtgående, 3-glas | 1,7-2,13 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000105. A4 0,0539 kg CO2e/kg, A5 0. 35,6 kg per m2 fönster. |
| BYGG_EF_window_wood_alu | Bygg | Fönster, trä/aluminium, inåtgående, 3-glas | 2-2,5 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000106. A4 0,0539 kg CO2e/kg, A5 0. 40,2 kg per m2 fönster. |
| BYGG_EF_door_interior | Bygg | Innerdörr utan glas, slät eller spegeldörr, oklassad | 1,43-1,79 | ? | kg CO2e/kg | 2026 | CO2e | 1 | 1 | BAU+Åtgärd | Boverket 6000000121. A4 0,0539 kg CO2e/kg, A5 0. 16,5 kg per m2 dörr. |
