# Prawdowid — wyniki ewaluacji

Przypadków: 57 · korpus: 8807 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.96 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 188 ms / 723 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| H01 | F | falszywe | falszywe | ✓ | Demagog / Nikt w Polsce nie może ubiegać się o azyl? To fałsz | 9445 |
| H02 | F | falszywe | falszywe | ✓ | FakeNews.pl / Kanada nie wprowadziła prawa karającego za cytowanie Biblii | 283 |
| H03 | F | falszywe | falszywe | ✓ | FakeNews.pl / 3I/ATLAS to kometa międzygwiezdna, a nie statek obcych | 205 |
| H04 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy 1 sierpnia Taylor Swift hajlowała na stadionie Narodowym? | 166 |
| H05 | F | falszywe | falszywe | ✓ | Demagog / W Buczy nie ginęli cywile? Uwaga na fałszywy przekaz | 339 |
| H06 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Sto wozów strażackich. Czy taką pomoc dla Polski wysłała Szwecja? | 138 |
| H07 | F | falszywe | falszywe | ✓ | Demagog / Najwyższy stopień alarmowy w Warszawie? Policja dementuje | 364 |
| H08 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 357 |
| H09 | T | potwierdzone | potwierdzone | ✓ | Demagog / Dług publiczny Polski niższy niż średnia UE? To prawda | 399 |
| H10 | T | potwierdzone | potwierdzone | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 729 |
| H11 | T | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy w wyniku śmierci samobójczej ginie dwa razy więcej Polaków niż w w | 487 |
| H12 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Kolej w Krakowie. Czy mieszkańcy z niej korzystają? | 401 |
| H13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Eksport paliwa do Ukrainy. Orlen nie sprzedaje go taniej niż w Polsce | 723 |
| H14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / 4400 górników bez pracy przez ukraińską spółkę? Przyczyna zwolnień jes | 207 |
| H15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 335 |
| H16 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Co trzecie dziecko rodzi się poza małżeństwem? Trend jest wzrostowy | 237 |
| H17 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — lipiec 2026: 3,0% r/r (GUS) | 130 |
| H18 | A | falszywe | brak_dowodow | ✗ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2025: 4,9% r/r (GUS, COICOP 1999) | 343 |
| H19 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 102 |
| H20 | A | potwierdzone | potwierdzone | ✓ | Demagog / Karol Nawrocki jest prezydentem. Wybory 2025 nie były sfałszowane | 838 |
| H21 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 129 |
| H22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 6 grudnia 2024 r. o zmianie ustawy o dniach wolnych od p | 41 |
| H23 | A | falszywe | falszywe | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 14 września 2026 r. w sprawie wys | 148 |
| H24 | A | falszywe | falszywe | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2022/2065 z dnia 1 | 182 |
| H25 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Szczepionki powodują autyzm? Kolejny fałsz Wilka o szczepionkach | 603 |
| H26 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy UE wprowadza zakaz naprawy starych samochodów? | 371 |
| H27 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Kancelaria Prezesa Rady Ministrów / Premier: W obliczu tragedii w Krakowie zobaczyliśmy to, co w ludziach  | 459 |
| H28 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 611 |
| H29 | Q | falszywe | brak_dowodow | ✗ | Demagog / Auschwitz pod kontrolą Izraela? Nie zapadła taka decyzja | 166 |
| H30 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Godzina za 8 zł. Które miasto ma najdroższe bilety komunikacji miejski | 407 |
| H31 | Q | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Niemcy nie rozbierają wiatraków z powodu ich nieopłacalności | 354 |
| H32 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| H33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| H34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| H35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| H36 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ile miasta dopłacają do komunikacji miejskiej dla mieszkańców? | 185 |
| H37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Biedronka „narzuca” 1 proc. na WOŚP przy zakupach? To fałszywe informa | 126 |
| H38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kolejne internetowe oszustwo. Tym razem „ucierpiała” Anna Mucha | 78 |
| H39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Klaus Schwab powiedział, że ludzie nie będą mieć aut? Wyjaśniamy | 124 |
| H40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Kto decyduje o sprowadzaniu zagranicznych studentów? Nie jest to jedna | 130 |
| H41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Pociągi znacznie punktualniejsze? Rzecznik rządu manipuluje danymi | 46 |
| H42 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / UE nie wprowadza obowiązkowej weryfikacji wieku w Internecie | 136 |
| H43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie ma dowodów na związek między paracetamolem a autyzmem | 188 |
| H44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba urodzeń żywych w Polsce — 2025: 238 264 (GUS BDL) | 108 |
| H45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Pfizer i nowa lista 49 efektów ubocznych szczepionek? Uwaga – to fałsz | 446 |
| H46 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Polskie drony nie zaatakowały Rosji. Fałszywe narracje po incydencie n | 416 |
| H47 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Austrii zapowiedziano wprowadzenie lockdownu dla niezaszczepiony | 114 |
| H48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / Blisko 3/4 importu ropy pochodzi z Rosji. Jak Polska wypada na tle UE? | 345 |
| H49 | B | wprowadzajace_w_blad, brak_dowodow, falszywe | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 13 lipca 2020 r. o w | 145 |
| H50 | X | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 385 |
| H51 | X | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Po co szczepienia na grypę, skoro ludzie dalej chorują? Wyjaśniamy | 263 |
| H52 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Stopa bezrobocia rejestrowanego w Polsce — wrzesień 2026: 5,8% (GUS) | 110 |
| H53 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 173 |
| H54 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 190 |
| H55 | J | blad_techniczny | blad_techniczny | ✓ |  | 5 |
| H56 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| H57 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
