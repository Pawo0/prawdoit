# Prawdowid — wyniki ewaluacji

Przypadków: 145 · korpus: 8807 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.954 | ≥ 0,75 |
| Obecność materiału przy werdykcie (stare proxy) | 1.0 | nie jest miarą pokrycia tez |
| Pokrycie każdej tezy dowodem | wymaga niezależnych adnotacji | ≥ 95% |
| Poprawność cytowania | wymaga niezależnych adnotacji | ≥ 85% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 115 ms / 412 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| dev:A1 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 7281 |
| dev:A2 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 78 |
| dev:A3 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 67 |
| dev:A4 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci | 106 |
| dev:A5 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1351 z dnia 1 | 253 |
| dev:A6 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Inflacja HICP 2026-10: Polska 3,7% vs UE 4,0% (Eurostat) | 100 |
| dev:F1 | F | falszywe | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 361 |
| dev:F2 | F | falszywe | falszywe | ✓ | Demagog / Pies uratował dziecko przed wilkiem? Ta historia wyglądała inaczej | 209 |
| dev:F3 | F | falszywe | falszywe | ✓ | FakeNews.pl / W Chinach nie zbudowano robota, który będzie rodził dzieci | 200 |
| dev:F4 | F | falszywe | falszywe | ✓ | Demagog / Cukrzycy nie można wyleczyć naturalnie. Uważaj na oszustwo | 201 |
| dev:F5 | F | falszywe | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 253 |
| dev:F6 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 277 |
| dev:F7 | F | falszywe | falszywe | ✓ | Demagog / Mamy już Ukropolin w Polsce? To nie są flagi Ukrainy | 346 |
| dev:F8 | F | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, chip ze szczepionki na COVID-19 nie został wykryty przez skaner d | 188 |
| dev:M1 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Polska, Ukraina i 490 mld zł – co mówią nam dane GUS? | 203 |
| dev:M2 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 193 |
| dev:M3 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Nie, paszporty covidowe nie umożliwiają permanentnej inwigilacji. Mani | 97 |
| dev:T1 | A | potwierdzone | potwierdzone | ✓ | Demagog / Ile kosztowały wybory z 2014 roku? | 188 |
| dev:T2 | A | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Tak, obowiązujący Polskę tekst Konwencji Stambulskiej to tekst francus | 69 |
| dev:B1 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy obywatele Ukrainy znajdują schronienie również w Rosji? | 229 |
| dev:B2 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / SLD pierwszy raz bez europosła? Wyjaśniamy | 92 |
| dev:O1 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:O2 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:O3 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:D1 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ścieżki rowerowe dla Wrocławia. Czy Jacek Sutryk dotrzymał obietnicy? | 145 |
| dev:D2 | D | brak_dowodow | brak_dowodow | ✓ | Ministerstwo Infrastruktury / Rusza budowa jednego z największych projektów infrastrukturalnych w hi | 70 |
| dev:D3 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 39 |
| dev:D4 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Niezrealizowane recepty w 2022 roku. Ile ich było? | 71 |
| dev:D5 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Podatek od nieruchomości obejmie fotowoltaikę? To fałsz | 41 |
| dev:E1 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Nadchodzi piekło 5G? Wyjaśniamy, czy jest sens bać się tej technologii | 89 |
| dev:E2 | E | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Polska wydaje na obronność tyle co Niemcy? Fałsz Trzaskowskiego | 223 |
| dev:E3 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 315 |
| dev:E4 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 444 |
| dev:I1 | I | ok | blad_techniczny | ✗ |  | 6 |
| dev:J1 | J | blad_techniczny | blad_techniczny | ✓ |  | 1 |
| dev:J2 | J | poza_zakresem | poza_zakresem | ✓ |  | 0 |
| dev:J3 | J | doprecyzuj | doprecyzuj | ✓ |  | 0 |
| dev:I2 | I | brak_dowodow, falszywe | falszywe | ✓ | Demagog / Polska wysyła żołnierzy do walki w Ukrainie? Fałszywe informacje | 376 |
| heldout:H01 | F | falszywe | falszywe | ✓ | Demagog / Nikt w Polsce nie może ubiegać się o azyl? To fałsz | 245 |
| heldout:H02 | F | falszywe | falszywe | ✓ | FakeNews.pl / Kanada nie wprowadziła prawa karającego za cytowanie Biblii | 148 |
| heldout:H03 | F | falszywe | falszywe | ✓ | FakeNews.pl / 3I/ATLAS to kometa międzygwiezdna, a nie statek obcych | 114 |
| heldout:H04 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy 1 sierpnia Taylor Swift hajlowała na stadionie Narodowym? | 94 |
| heldout:H05 | F | falszywe | falszywe | ✓ | Demagog / W Buczy nie ginęli cywile? Uwaga na fałszywy przekaz | 204 |
| heldout:H06 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Sto wozów strażackich. Czy taką pomoc dla Polski wysłała Szwecja? | 80 |
| heldout:H07 | F | falszywe | falszywe | ✓ | Demagog / Najwyższy stopień alarmowy w Warszawie? Policja dementuje | 284 |
| heldout:H08 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 211 |
| heldout:H09 | T | potwierdzone | potwierdzone | ✓ | Demagog / Dług publiczny Polski niższy niż średnia UE? To prawda | 240 |
| heldout:H10 | T | potwierdzone | potwierdzone | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 418 |
| heldout:H11 | T | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy w wyniku śmierci samobójczej ginie dwa razy więcej Polaków niż w w | 273 |
| heldout:H12 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Kolej w Krakowie. Czy mieszkańcy z niej korzystają? | 227 |
| heldout:H13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Eksport paliwa do Ukrainy. Orlen nie sprzedaje go taniej niż w Polsce | 408 |
| heldout:H14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / 4400 górników bez pracy przez ukraińską spółkę? Przyczyna zwolnień jes | 117 |
| heldout:H15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 196 |
| heldout:H16 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Co trzecie dziecko rodzi się poza małżeństwem? Trend jest wzrostowy | 134 |
| heldout:H17 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — lipiec 2026: 3,0% r/r (GUS) | 73 |
| heldout:H18 | A | falszywe | brak_dowodow | ✗ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2025: 4,9% r/r (GUS, COICOP 1999) | 202 |
| heldout:H19 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 59 |
| heldout:H20 | A | potwierdzone | potwierdzone | ✓ | Demagog / Karol Nawrocki jest prezydentem. Wybory 2025 nie były sfałszowane | 484 |
| heldout:H21 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 76 |
| heldout:H22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 6 grudnia 2024 r. o zmianie ustawy o dniach wolnych od p | 31 |
| heldout:H23 | A | falszywe | falszywe | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 14 września 2026 r. w sprawie wys | 87 |
| heldout:H24 | A | falszywe | falszywe | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2022/2065 z dnia 1 | 104 |
| heldout:H25 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Szczepionki powodują autyzm? Kolejny fałsz Wilka o szczepionkach | 347 |
| heldout:H26 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy UE wprowadza zakaz naprawy starych samochodów? | 221 |
| heldout:H27 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Kancelaria Prezesa Rady Ministrów / Premier: W obliczu tragedii w Krakowie zobaczyliśmy to, co w ludziach  | 279 |
| heldout:H28 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 347 |
| heldout:H29 | Q | falszywe | brak_dowodow | ✗ | Demagog / Auschwitz pod kontrolą Izraela? Nie zapadła taka decyzja | 92 |
| heldout:H30 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Godzina za 8 zł. Które miasto ma najdroższe bilety komunikacji miejski | 241 |
| heldout:H31 | Q | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Niemcy nie rozbierają wiatraków z powodu ich nieopłacalności | 208 |
| heldout:H32 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| heldout:H33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H36 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ile miasta dopłacają do komunikacji miejskiej dla mieszkańców? | 106 |
| heldout:H37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Biedronka „narzuca” 1 proc. na WOŚP przy zakupach? To fałszywe informa | 74 |
| heldout:H38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kolejne internetowe oszustwo. Tym razem „ucierpiała” Anna Mucha | 42 |
| heldout:H39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Klaus Schwab powiedział, że ludzie nie będą mieć aut? Wyjaśniamy | 72 |
| heldout:H40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kto decyduje o sprowadzaniu zagranicznych studentów? Nie jest to jedna | 79 |
| heldout:H41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Pociągi znacznie punktualniejsze? Rzecznik rządu manipuluje danymi | 31 |
| heldout:H42 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / UE nie wprowadza obowiązkowej weryfikacji wieku w Internecie | 92 |
| heldout:H43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie ma dowodów na związek między paracetamolem a autyzmem | 120 |
| heldout:H44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba urodzeń żywych w Polsce — 2025: 238 264 (GUS BDL) | 65 |
| heldout:H45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Pfizer i nowa lista 49 efektów ubocznych szczepionek? Uwaga – to fałsz | 295 |
| heldout:H46 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Polskie drony nie zaatakowały Rosji. Fałszywe narracje po incydencie n | 269 |
| heldout:H47 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Austrii zapowiedziano wprowadzenie lockdownu dla niezaszczepiony | 71 |
| heldout:H48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / Blisko 3/4 importu ropy pochodzi z Rosji. Jak Polska wypada na tle UE? | 217 |
| heldout:H49 | B | wprowadzajace_w_blad, brak_dowodow, falszywe | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 13 lipca 2020 r. o w | 89 |
| heldout:H50 | X | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 260 |
| heldout:H51 | X | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Po co szczepienia na grypę, skoro ludzie dalej chorują? Wyjaśniamy | 161 |
| heldout:H52 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Stopa bezrobocia rejestrowanego w Polsce — wrzesień 2026: 5,8% (GUS) | 68 |
| heldout:H53 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 109 |
| heldout:H54 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 125 |
| heldout:H55 | J | blad_techniczny | blad_techniczny | ✓ |  | 2 |
| heldout:H56 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| heldout:H57 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| blind2:B2-01 | F | falszywe | falszywe | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 135 |
| blind2:B2-02 | F | falszywe | falszywe | ✓ | Demagog / Soda oczyszczona nie pomoże na raka. To dezinformacja medyczna | 277 |
| blind2:B2-03 | F | falszywe | falszywe | ✓ | FakeNews.pl / Unia Europejska nie zakaże picia kawy z mlekiem i cukrem | 135 |
| blind2:B2-04 | Q | falszywe | brak_dowodow | ✗ | FakeNews.pl / W wyborach można głosować z aplikacją mObywatel | 104 |
| blind2:B2-05 | F | falszywe | falszywe | ✓ | FakeNews.pl / Nazwa Mostu Grunwaldzkiego we Wrocławiu nie zostanie zmieniona na niem | 127 |
| blind2:B2-06 | F | falszywe | brak_dowodow | ✗ | Demagog / Rafał Brzoska nie został postrzelony. Historia zmyślona przez oszustów | 42 |
| blind2:B2-07 | F | falszywe | falszywe | ✓ | Demagog / Czy to nagranie z ukraińskiej mobilizacji? Zweryfikowaliśmy film | 423 |
| blind2:B2-08 | F | falszywe | falszywe | ✓ | Demagog / Wybuch Etny przekreślił wysiłki klimatyczne UE? Poseł Pejo się myli. | 266 |
| blind2:B2-09 | F | falszywe | falszywe | ✓ | Demagog / Pakt migracyjny. Wszystkie państwa UE są nim związane | 694 |
| blind2:B2-10 | Q | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy mamy nowy banknot o nominale 1000 zł? Sprawdzamy | 85 |
| blind2:B2-11 | M | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | Demagog / Twoje pieniądze z PPK pójdą na państwowe projekty? Nie ma takich planó | 160 |
| blind2:B2-12 | M | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Panele słoneczne przyśpieszają zmianę klimatu? Raport wyjęto z konteks | 120 |
| blind2:B2-13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Winnice w Mołdawii. Co się z nimi stanie po wejściu do UE? | 286 |
| blind2:B2-14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Czy wiatraki wywołują suszę? Zmanipulowano wnioski z badań | 206 |
| blind2:B2-15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | Demagog / Przestępczość Ukraińców w Polsce. Co mówią statystyki? | 215 |
| blind2:B2-16 | T | potwierdzone | potwierdzone | ✓ | Demagog / Eurowybory – ile mandatów przypadnie Polsce? | 212 |
| blind2:B2-17 | T | potwierdzone | potwierdzone | ✓ | Demagog / Do 100 mld zł rocznie. Czy tyle kosztuje Polskę nadmierne spożycie alk | 412 |
| blind2:B2-18 | T | potwierdzone | potwierdzone | ✓ | Demagog / 95 proc. Ukraińców w wieku poborowym pracuje. Jak rząd to policzył? | 448 |
| blind2:B2-19 | T | potwierdzone | potwierdzone | ✓ | FakeNews.pl / Polecenie Orlenu dotyczące informowania o awarii dystrybutorów jest pr | 115 |
| blind2:B2-20 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Ile jest pustostanów w Krakowie? W sieci krążą różne dane | 298 |
| blind2:B2-21 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 11 września 2025 r. w sprawie wys | 73 |
| blind2:B2-22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 10 stycznia 2018 r. o ograniczeniu handlu w niedziele i  | 121 |
| blind2:B2-23 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP USD/PLN z 2026-11-20: 4,0613 zł | 65 |
| blind2:B2-24 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Ochrona czasowa (Ukraina) 2026-09: Polska 858 545 osób (Eurostat) | 164 |
| blind2:B2-25 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1689 z dnia 1 | 95 |
| blind2:B2-26 | A | falszywe | falszywe | ✓ | Narodowy Bank Polski / Stopy procentowe NBP — stopa referencyjna 3,75% (od 2026-03-05) | 91 |
| blind2:B2-27 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — czerwiec 2026: 2,5% r/r (GUS) | 111 |
| blind2:B2-28 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 96 |
| blind2:B2-29 | A | falszywe | falszywe | ✓ | Eurostat (Komisja Europejska) / Deficyt sektora finansów publicznych 2025: Polska -7,2% PKB (Eurostat) | 279 |
| blind2:B2-30 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / 5G i Bluetooth wciąż nie wywołują raka. To znana teoria spiskowa | 212 |
| blind2:B2-31 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Choroby psychiczne a zakaźność. „Kompletna bzdura” z TikToka | 191 |
| blind2:B2-32 | N | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Demagog / Fałszywa aplikacja Lotto. Jak ją rozpoznać? | 97 |
| blind2:B2-33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-36 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Lewandowski mówi o aplikacji do zarabiania? To scam z użyciem AI | 74 |
| blind2:B2-38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Incydent w Katowicach nie ma związku z zamknięciem kąpieliska – wyjaśn | 33 |
| blind2:B2-39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Upada jeden z większych szpitali w Polsce? Ministerstwo Zdrowia dement | 91 |
| blind2:B2-40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Uwaga na oszustwo! ZTM Gdańsk nie rozdaje kart na przejazdy | 28 |
| blind2:B2-41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / [Debata TVP] NFZ niezgodny z Konstytucją? Wyrok dotyczył innej ustawy | 36 |
| blind2:B2-42 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Złóż życzenia i odbierz nagrodę. To kolejne oszustwo na Biedronkę | 39 |
| blind2:B2-43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Putin aresztuje Gatesa za stworzenie dżumy? Taka sytuacja nie miała mi | 138 |
| blind2:B2-44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba zgonów w Polsce — 2025: 405 747 (GUS BDL) | 187 |
| blind2:B2-45 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Donald Tusk nie mówił o polskim ataku na Westerplatte | 626 |
| blind2:B2-46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Macron został przyłapany na braniu kokainy? Uwaga na dezinformację | 88 |
| blind2:B2-47 | B | wprowadzajace_w_blad, brak_dowodow | wprowadzajace_w_blad | ✓ | Stowarzyszenie Pravda / Pokojowa Nagroda Nobla dla dziennikarzy! | 70 |
| blind2:B2-48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Singapurze niezaszczepieni na koronawirusa będą musieli sami opł | 123 |
| blind2:B2-49 | J | blad_techniczny | blad_techniczny | ✓ |  | 1 |
| blind2:B2-50 | J | doprecyzuj | doprecyzuj | ✓ |  | 0 |
