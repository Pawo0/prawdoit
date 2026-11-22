# Prawdowid — wyniki ewaluacji

Przypadków: 145 · korpus: 8807 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.799 | ≥ 0,75 |
| Obecność materiału przy werdykcie (stare proxy) | 1.0 | nie jest miarą pokrycia tez |
| Pokrycie każdej tezy dowodem | wymaga niezależnych adnotacji | ≥ 95% |
| Poprawność cytowania | wymaga niezależnych adnotacji | ≥ 85% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 138 ms / 548 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| dev:A1 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 4759 |
| dev:A2 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 85 |
| dev:A3 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 71 |
| dev:A4 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci | 117 |
| dev:A5 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1351 z dnia 1 | 267 |
| dev:A6 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Inflacja HICP 2026-10: Polska 3,7% vs UE 4,0% (Eurostat) | 108 |
| dev:F1 | F | falszywe | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 548 |
| dev:F2 | F | falszywe | falszywe | ✓ | Demagog / Pies uratował dziecko przed wilkiem? Ta historia wyglądała inaczej | 437 |
| dev:F3 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / W Chinach nie zbudowano robota, który będzie rodził dzieci | 390 |
| dev:F4 | F | falszywe | falszywe | ✓ | Demagog / Cukrzycy nie można wyleczyć naturalnie. Uważaj na oszustwo | 395 |
| dev:F5 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 192 |
| dev:F6 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 439 |
| dev:F7 | F | falszywe | falszywe | ✓ | Demagog / Mamy już Ukropolin w Polsce? To nie są flagi Ukrainy | 598 |
| dev:F8 | F | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, chip ze szczepionki na COVID-19 nie został wykryty przez skaner d | 206 |
| dev:M1 | B | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Polska, Ukraina i 490 mld zł – co mówią nam dane GUS? | 362 |
| dev:M2 | B | wprowadzajace_w_blad | brak_dowodow | ✗ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 207 |
| dev:M3 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Nie, paszporty covidowe nie umożliwiają permanentnej inwigilacji. Mani | 154 |
| dev:T1 | A | potwierdzone | brak_dowodow | ✗ | Demagog / Ile kosztowały wybory z 2014 roku? | 131 |
| dev:T2 | A | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Tak, obowiązujący Polskę tekst Konwencji Stambulskiej to tekst francus | 130 |
| dev:B1 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy obywatele Ukrainy znajdują schronienie również w Rosji? | 278 |
| dev:B2 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / SLD pierwszy raz bez europosła? Wyjaśniamy | 112 |
| dev:O1 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:O2 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:O3 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| dev:D1 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ścieżki rowerowe dla Wrocławia. Czy Jacek Sutryk dotrzymał obietnicy? | 164 |
| dev:D2 | D | brak_dowodow | brak_dowodow | ✓ | Ministerstwo Infrastruktury / Rusza budowa jednego z największych projektów infrastrukturalnych w hi | 79 |
| dev:D3 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 53 |
| dev:D4 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Niezrealizowane recepty w 2022 roku. Ile ich było? | 83 |
| dev:D5 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Podatek od nieruchomości obejmie fotowoltaikę? To fałsz | 62 |
| dev:E1 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Nadchodzi piekło 5G? Wyjaśniamy, czy jest sens bać się tej technologii | 102 |
| dev:E2 | E | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Polska wydaje na obronność tyle co Niemcy? Fałsz Trzaskowskiego | 243 |
| dev:E3 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 354 |
| dev:E4 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Niemiecka policja podrzuca chorych imigrantów do Polski? Nieprawda | 666 |
| dev:I1 | I | ok | blad_techniczny | ✗ |  | 3 |
| dev:J1 | J | blad_techniczny | blad_techniczny | ✓ |  | 1 |
| dev:J2 | J | poza_zakresem | poza_zakresem | ✓ |  | 0 |
| dev:J3 | J | doprecyzuj | doprecyzuj | ✓ |  | 0 |
| dev:I2 | I | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Polska wysyła żołnierzy do walki w Ukrainie? Fałszywe informacje | 482 |
| heldout:H01 | F | falszywe | falszywe | ✓ | Demagog / Nikt w Polsce nie może ubiegać się o azyl? To fałsz | 334 |
| heldout:H02 | F | falszywe | wprowadzajace_w_blad | ✗ | Demagog / Kanada nie będzie karać za cytowanie Biblii. Zobacz, co mają zmienić n | 414 |
| heldout:H03 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / 3I/ATLAS to kometa międzygwiezdna, a nie statek obcych | 146 |
| heldout:H04 | F | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy 1 sierpnia Taylor Swift hajlowała na stadionie Narodowym? | 131 |
| heldout:H05 | F | falszywe | falszywe | ✓ | Demagog / W Buczy nie ginęli cywile? Uwaga na fałszywy przekaz | 382 |
| heldout:H06 | F | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Sto wozów strażackich. Czy taką pomoc dla Polski wysłała Szwecja? | 102 |
| heldout:H07 | F | falszywe | falszywe | ✓ | Demagog / Najwyższy stopień alarmowy w Warszawie? Policja dementuje | 386 |
| heldout:H08 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 402 |
| heldout:H09 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Dług publiczny Polski niższy niż średnia UE? To prawda | 347 |
| heldout:H10 | T | potwierdzone | potwierdzone | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 601 |
| heldout:H11 | T | potwierdzone | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy w wyniku śmierci samobójczej ginie dwa razy więcej Polaków niż w w | 289 |
| heldout:H12 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Kolej w Krakowie. Czy mieszkańcy z niej korzystają? | 273 |
| heldout:H13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Eksport paliwa do Ukrainy. Orlen nie sprzedaje go taniej niż w Polsce | 512 |
| heldout:H14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / 4400 górników bez pracy przez ukraińską spółkę? Przyczyna zwolnień jes | 298 |
| heldout:H15 | M | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 219 |
| heldout:H16 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Co trzecie dziecko rodzi się poza małżeństwem? Trend jest wzrostowy | 287 |
| heldout:H17 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — lipiec 2026: 3,0% r/r (GUS) | 81 |
| heldout:H18 | A | falszywe | brak_dowodow | ✗ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2025: 4,9% r/r (GUS, COICOP 1999) | 194 |
| heldout:H19 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 60 |
| heldout:H20 | A | potwierdzone | brak_dowodow | ✗ | Demagog / Karol Nawrocki jest prezydentem. Wybory 2025 nie były sfałszowane | 367 |
| heldout:H21 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 93 |
| heldout:H22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 6 grudnia 2024 r. o zmianie ustawy o dniach wolnych od p | 29 |
| heldout:H23 | A | falszywe | falszywe | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 14 września 2026 r. w sprawie wys | 96 |
| heldout:H24 | A | falszywe | falszywe | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2022/2065 z dnia 1 | 119 |
| heldout:H25 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Szczepionki powodują autyzm? Kolejny fałsz Wilka o szczepionkach | 408 |
| heldout:H26 | N | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy UE wprowadza zakaz naprawy starych samochodów? | 227 |
| heldout:H27 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Kancelaria Prezesa Rady Ministrów / Premier: W obliczu tragedii w Krakowie zobaczyliśmy to, co w ludziach  | 408 |
| heldout:H28 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 470 |
| heldout:H29 | Q | falszywe | brak_dowodow | ✗ | Demagog / Auschwitz pod kontrolą Izraela? Nie zapadła taka decyzja | 111 |
| heldout:H30 | Q | potwierdzone | brak_dowodow | ✗ | Demagog / Godzina za 8 zł. Które miasto ma najdroższe bilety komunikacji miejski | 175 |
| heldout:H31 | Q | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | FakeNews.pl / Niemcy nie rozbierają wiatraków z powodu ich nieopłacalności | 397 |
| heldout:H32 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| heldout:H36 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ile miasta dopłacają do komunikacji miejskiej dla mieszkańców? | 138 |
| heldout:H37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Biedronka „narzuca” 1 proc. na WOŚP przy zakupach? To fałszywe informa | 83 |
| heldout:H38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kolejne internetowe oszustwo. Tym razem „ucierpiała” Anna Mucha | 61 |
| heldout:H39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Klaus Schwab powiedział, że ludzie nie będą mieć aut? Wyjaśniamy | 85 |
| heldout:H40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kto decyduje o sprowadzaniu zagranicznych studentów? Nie jest to jedna | 84 |
| heldout:H41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Pociągi znacznie punktualniejsze? Rzecznik rządu manipuluje danymi | 30 |
| heldout:H42 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / UE nie wprowadza obowiązkowej weryfikacji wieku w Internecie | 90 |
| heldout:H43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie ma dowodów na związek między paracetamolem a autyzmem | 133 |
| heldout:H44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba urodzeń żywych w Polsce — 2025: 238 264 (GUS BDL) | 66 |
| heldout:H45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Pfizer i nowa lista 49 efektów ubocznych szczepionek? Uwaga – to fałsz | 424 |
| heldout:H46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Polskie drony nie zaatakowały Rosji. Fałszywe narracje po incydencie n | 364 |
| heldout:H47 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Austrii zapowiedziano wprowadzenie lockdownu dla niezaszczepiony | 75 |
| heldout:H48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / Blisko 3/4 importu ropy pochodzi z Rosji. Jak Polska wypada na tle UE? | 232 |
| heldout:H49 | B | wprowadzajace_w_blad, brak_dowodow, falszywe | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 13 lipca 2020 r. o w | 105 |
| heldout:H50 | X | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 263 |
| heldout:H51 | X | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Po co szczepienia na grypę, skoro ludzie dalej chorują? Wyjaśniamy | 371 |
| heldout:H52 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Stopa bezrobocia rejestrowanego w Polsce — wrzesień 2026: 5,8% (GUS) | 65 |
| heldout:H53 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 110 |
| heldout:H54 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 131 |
| heldout:H55 | J | blad_techniczny | blad_techniczny | ✓ |  | 1 |
| heldout:H56 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| heldout:H57 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| blind2:B2-01 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 198 |
| blind2:B2-02 | F | falszywe | brak_dowodow | ✗ | Demagog / Soda oczyszczona nie pomoże na raka. To dezinformacja medyczna | 530 |
| blind2:B2-03 | F | falszywe | falszywe | ✓ | FakeNews.pl / Unia Europejska nie zakaże picia kawy z mlekiem i cukrem | 208 |
| blind2:B2-04 | Q | falszywe | brak_dowodow | ✗ | FakeNews.pl / W wyborach można głosować z aplikacją mObywatel | 117 |
| blind2:B2-05 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / Nazwa Mostu Grunwaldzkiego we Wrocławiu nie zostanie zmieniona na niem | 235 |
| blind2:B2-06 | F | falszywe | brak_dowodow | ✗ | Demagog / Rafał Brzoska nie został postrzelony. Historia zmyślona przez oszustów | 61 |
| blind2:B2-07 | F | falszywe | falszywe | ✓ | Demagog / Czy to nagranie z ukraińskiej mobilizacji? Zweryfikowaliśmy film | 635 |
| blind2:B2-08 | F | falszywe | brak_dowodow | ✗ | Demagog / Wybuch Etny przekreślił wysiłki klimatyczne UE? Poseł Pejo się myli. | 161 |
| blind2:B2-09 | F | falszywe | brak_dowodow | ✗ | Demagog / Pakt migracyjny. Wszystkie państwa UE są nim związane | 1179 |
| blind2:B2-10 | Q | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy mamy nowy banknot o nominale 1000 zł? Sprawdzamy | 166 |
| blind2:B2-11 | M | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | Demagog / Twoje pieniądze z PPK pójdą na państwowe projekty? Nie ma takich planó | 182 |
| blind2:B2-12 | M | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Panele słoneczne przyśpieszają zmianę klimatu? Raport wyjęto z konteks | 136 |
| blind2:B2-13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Winnice w Mołdawii. Co się z nimi stanie po wejściu do UE? | 431 |
| blind2:B2-14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Czy wiatraki wywołują suszę? Zmanipulowano wnioski z badań | 423 |
| blind2:B2-15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | Demagog / Przestępczość Ukraińców w Polsce. Co mówią statystyki? | 429 |
| blind2:B2-16 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Eurowybory – ile mandatów przypadnie Polsce? | 258 |
| blind2:B2-17 | T | potwierdzone | potwierdzone | ✓ | Demagog / Do 100 mld zł rocznie. Czy tyle kosztuje Polskę nadmierne spożycie alk | 556 |
| blind2:B2-18 | T | potwierdzone | potwierdzone | ✓ | Demagog / 95 proc. Ukraińców w wieku poborowym pracuje. Jak rząd to policzył? | 444 |
| blind2:B2-19 | T | potwierdzone | brak_dowodow | ✗ | FakeNews.pl / Polecenie Orlenu dotyczące informowania o awarii dystrybutorów jest pr | 141 |
| blind2:B2-20 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Ile jest pustostanów w Krakowie? W sieci krążą różne dane | 310 |
| blind2:B2-21 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 11 września 2025 r. w sprawie wys | 74 |
| blind2:B2-22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 10 stycznia 2018 r. o ograniczeniu handlu w niedziele i  | 129 |
| blind2:B2-23 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP USD/PLN z 2026-11-20: 4,0613 zł | 69 |
| blind2:B2-24 | A | potwierdzone | brak_dowodow | ✗ | Eurostat (Komisja Europejska) / Ochrona czasowa (Ukraina) 2026-09: Polska 858 545 osób (Eurostat) | 199 |
| blind2:B2-25 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1689 z dnia 1 | 101 |
| blind2:B2-26 | A | falszywe | falszywe | ✓ | Narodowy Bank Polski / Stopy procentowe NBP — stopa referencyjna 3,75% (od 2026-03-05) | 100 |
| blind2:B2-27 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — czerwiec 2026: 2,5% r/r (GUS) | 120 |
| blind2:B2-28 | A | falszywe | brak_dowodow | ✗ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 121 |
| blind2:B2-29 | A | falszywe | falszywe | ✓ | Eurostat (Komisja Europejska) / Deficyt sektora finansów publicznych 2025: Polska -7,2% PKB (Eurostat) | 309 |
| blind2:B2-30 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / 5G i Bluetooth wciąż nie wywołują raka. To znana teoria spiskowa | 348 |
| blind2:B2-31 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Choroby psychiczne a zakaźność. „Kompletna bzdura” z TikToka | 244 |
| blind2:B2-32 | N | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Demagog / Fałszywa aplikacja Lotto. Jak ją rozpoznać? | 128 |
| blind2:B2-33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-36 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 1 |
| blind2:B2-37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Lewandowski mówi o aplikacji do zarabiania? To scam z użyciem AI | 90 |
| blind2:B2-38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Incydent w Katowicach nie ma związku z zamknięciem kąpieliska – wyjaśn | 44 |
| blind2:B2-39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Upada jeden z większych szpitali w Polsce? Ministerstwo Zdrowia dement | 111 |
| blind2:B2-40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Uwaga na oszustwo! ZTM Gdańsk nie rozdaje kart na przejazdy | 35 |
| blind2:B2-41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / [Debata TVP] NFZ niezgodny z Konstytucją? Wyrok dotyczył innej ustawy | 55 |
| blind2:B2-42 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Złóż życzenia i odbierz nagrodę. To kolejne oszustwo na Biedronkę | 59 |
| blind2:B2-43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Putin aresztuje Gatesa za stworzenie dżumy? Taka sytuacja nie miała mi | 152 |
| blind2:B2-44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba zgonów w Polsce — 2025: 405 747 (GUS BDL) | 199 |
| blind2:B2-45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Tusk powiedział, że II wojna zaczęła się od polskiego ataku na Westerp | 910 |
| blind2:B2-46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Macron został przyłapany na braniu kokainy? Uwaga na dezinformację | 99 |
| blind2:B2-47 | B | wprowadzajace_w_blad, brak_dowodow | wprowadzajace_w_blad | ✓ | Stowarzyszenie Pravda / Pokojowa Nagroda Nobla dla dziennikarzy! | 140 |
| blind2:B2-48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Singapurze niezaszczepieni na koronawirusa będą musieli sami opł | 145 |
| blind2:B2-49 | J | blad_techniczny | blad_techniczny | ✓ |  | 1 |
| blind2:B2-50 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
