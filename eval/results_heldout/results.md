# Prawdowid — wyniki ewaluacji

Przypadków: 57 · korpus: 2285 dok., 16 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.936 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 524 ms / 1966 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| H01 | F | falszywe | falszywe | ✓ | Demagog / Czy Polska przyjmuje wnioski o azyl? Fałsz Tuska | 11211 |
| H02 | F | falszywe | falszywe | ✓ | FakeNews.pl / Kanada nie wprowadziła prawa karającego za cytowanie Biblii | 634 |
| H03 | F | falszywe | falszywe | ✓ | FakeNews.pl / 3I/ATLAS to kometa międzygwiezdna, a nie statek obcych | 594 |
| H04 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy 1 sierpnia Taylor Swift hajlowała na stadionie Narodowym? | 477 |
| H05 | F | falszywe | falszywe | ✓ | Demagog / W Buczy nie ginęli cywile? Uwaga na fałszywy przekaz | 817 |
| H06 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Sto wozów strażackich. Czy taką pomoc dla Polski wysłała Szwecja? | 2088 |
| H07 | F | falszywe | falszywe | ✓ | Demagog / Najwyższy stopień alarmowy w Warszawie? Policja dementuje | 727 |
| H08 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 533 |
| H09 | T | potwierdzone | potwierdzone | ✓ | Demagog / Dług publiczny Polski niższy niż średnia UE? To prawda | 783 |
| H10 | T | potwierdzone | potwierdzone | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 537 |
| H11 | T | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy w wyniku śmierci samobójczej ginie dwa razy więcej Polaków niż w w | 1698 |
| H12 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Kolej w Krakowie. Czy mieszkańcy z niej korzystają? | 1000 |
| H13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Orlen sprzedaje Ukrainie paliwo za 3 zł, a Polakom drożej? Fakty są in | 1966 |
| H14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / 4400 górników bez pracy przez ukraińską spółkę? Przyczyna zwolnień jes | 551 |
| H15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 524 |
| H16 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Co trzecie dziecko rodzi się poza małżeństwem? Trend jest wzrostowy | 736 |
| H17 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — lipiec 2026: 3,0% r/r (GUS) | 548 |
| H18 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2025: 4,9% r/r (GUS, COICOP 1999) | 402 |
| H19 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 381 |
| H20 | A | potwierdzone | potwierdzone | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 2 czerwca 2025 r. o  | 1932 |
| H21 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 523 |
| H22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 6 grudnia 2024 r. o zmianie ustawy o dniach wolnych od p | 83 |
| H23 | A | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy Pierwsza Dama otrzyma pensję 18 tys. złotych miesięcznie? | 308 |
| H24 | A | falszywe | falszywe | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2022/2065 z dnia 1 | 827 |
| H25 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Szczepionki powodują autyzm? Kolejny fałsz Wilka o szczepionkach | 907 |
| H26 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy UE wprowadza zakaz naprawy starych samochodów? | 633 |
| H27 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Zamachowiec z Krakowa jest Polakiem. Sprawdź, kto uważał inaczej | 587 |
| H28 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 931 |
| H29 | Q | falszywe | brak_dowodow | ✗ | Demagog / Auschwitz pod kontrolą Izraela? Nie zapadła taka decyzja | 345 |
| H30 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Godzina za 8 zł. Które miasto ma najdroższe bilety komunikacji miejski | 413 |
| H31 | Q | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Niemcy nie rozbierają wiatraków z powodu ich nieopłacalności | 403 |
| H32 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 12 |
| H33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 15 |
| H34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 16 |
| H35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 16 |
| H36 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Strategia rozwoju i plan ogólny. Czy Kraków nie ma tych dokumentów? | 270 |
| H37 | D | brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Ile firm każdego dnia upada w Polsce? Czym jest postępowanie restruktu | 198 |
| H38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Tragiczny wypadek w Krakowie. Na tej drodze dochodziło już do zdarzeń  | 137 |
| H39 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, UE nie zakaże jazdy autami spalinowymi w weekendy | 259 |
| H40 | D | brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy to viralowe zdjęcie strażaków jest prawdziwe? | 233 |
| H41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Krakowska komunikacja ma mniej pasażerów. Spadek nastąpił przed zmianą | 200 |
| H42 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / UE nie wprowadza obowiązkowej weryfikacji wieku w Internecie | 589 |
| H43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie ma dowodów na związek między paracetamolem a autyzmem | 561 |
| H44 | E | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy Polska wypłaciła 500+ aż 700 tysiącom dzieci z Ukrainy? | 480 |
| H45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Pfizer i nowa lista 49 efektów ubocznych szczepionek? Uwaga – to fałsz | 517 |
| H46 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Polskie drony nie zaatakowały Rosji. Fałszywe narracje po incydencie n | 1859 |
| H47 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Austrii zapowiedziano wprowadzenie lockdownu dla niezaszczepiony | 423 |
| H48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / Blisko 3/4 importu ropy pochodzi z Rosji. Jak Polska wypada na tle UE? | 2073 |
| H49 | B | wprowadzajace_w_blad, brak_dowodow, falszywe | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 13 lipca 2020 r. o w | 636 |
| H50 | X | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 1412 |
| H51 | X | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Po co szczepienia na grypę, skoro ludzie dalej chorują? Wyjaśniamy | 1226 |
| H52 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Stopa bezrobocia rejestrowanego w Polsce — wrzesień 2026: 5,8% (GUS) | 438 |
| H53 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 452 |
| H54 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 379 |
| H55 | J | blad_techniczny | blad_techniczny | ✓ |  | 52 |
| H56 | J | doprecyzuj | doprecyzuj | ✓ |  | 10 |
| H57 | J | doprecyzuj | doprecyzuj | ✓ |  | 10 |
