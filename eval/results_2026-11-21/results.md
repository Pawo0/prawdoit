# Prawdowid — wyniki ewaluacji

Przypadków: 38 · korpus: 4410 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 1.0 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 584 ms / 1819 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| A1 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 4474 |
| A2 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 423 |
| A3 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 339 |
| A4 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci | 597 |
| A5 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1351 z dnia 1 | 1501 |
| A6 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Inflacja HICP 2026-10: Polska 3,7% vs UE 4,0% (Eurostat) | 629 |
| F1 | F | falszywe | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 1077 |
| F2 | F | falszywe | falszywe | ✓ | Demagog / Pies uratował dziecko przed wilkiem? Ta historia wyglądała inaczej | 477 |
| F3 | F | falszywe | falszywe | ✓ | FakeNews.pl / W Chinach nie zbudowano robota, który będzie rodził dzieci | 581 |
| F4 | F | falszywe | falszywe | ✓ | Demagog / Cukrzycy nie można wyleczyć naturalnie. Uważaj na oszustwo | 458 |
| F5 | F | falszywe | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 671 |
| F6 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 1010 |
| F7 | F | falszywe | falszywe | ✓ | Demagog / Mamy już Ukropolin w Polsce? To nie są flagi Ukrainy | 888 |
| F8 | F | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, chip ze szczepionki na COVID-19 nie został wykryty przez skaner d | 1043 |
| M1 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Polska, Ukraina i 490 mld zł – co mówią nam dane GUS? | 1070 |
| M2 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 850 |
| M3 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Nie, paszporty covidowe nie umożliwiają permanentnej inwigilacji. Mani | 465 |
| T1 | A | potwierdzone | potwierdzone | ✓ | Demagog / Ile kosztowały wybory z 2014 roku? | 588 |
| T2 | A | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Tak, obowiązujący Polskę tekst Konwencji Stambulskiej to tekst francus | 611 |
| B1 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy obywatele Ukrainy znajdują schronienie również w Rosji? | 1603 |
| B2 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 10 czerwca 2024 r. o | 445 |
| O1 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 13 |
| O2 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 9 |
| O3 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 9 |
| D1 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Gminy płacą za brak recyklingu. Kto wymyślił te przepisy? | 393 |
| D2 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Repolonizacja CPK. Co zmienił rząd Donalda Tuska? | 248 |
| D3 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 210 |
| D4 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, leki na raka nie zostały skreślone z listy leków refundowanych | 121 |
| D5 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ile jest stacji ładowania samochodów elektrycznych w Polsce i Holandii | 140 |
| E1 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Nadchodzi piekło 5G? Wyjaśniamy, czy jest sens bać się tej technologii | 523 |
| E2 | E | brak_dowodow, falszywe | brak_dowodow | ✓ | EUvsDisinfo (EEAS East StratCom Task Force) / The USA wants to establish a Greater Poland in Eastern Europe in excha | 1554 |
| E3 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 938 |
| E4 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 1509 |
| I1 | I | ok | brak_dowodow | ✓ | Ministerstwo Spraw Zagranicznych / Oświadczenia MSZ w związku z atrybucją przez Danię rosyjskim służbom s | 2568 |
| J1 | J | blad_techniczny | blad_techniczny | ✓ |  | 50 |
| J2 | J | poza_zakresem | poza_zakresem | ✓ |  | 12 |
| J3 | J | doprecyzuj | doprecyzuj | ✓ |  | 14 |
| I2 | I | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Rosyjski dziennikarz z wiadomością dla Polaków. Uważaj na propagandowy | 1819 |
