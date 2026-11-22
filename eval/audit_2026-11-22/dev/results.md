# Prawdowid — wyniki ewaluacji

Przypadków: 38 · korpus: 8807 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 1.0 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 324 ms / 2100 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| A1 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 13219 |
| A2 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 432 |
| A3 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 196 |
| A4 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci | 403 |
| A5 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1351 z dnia 1 | 2100 |
| A6 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Inflacja HICP 2026-10: Polska 3,7% vs UE 4,0% (Eurostat) | 1236 |
| F1 | F | falszywe | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 2176 |
| F2 | F | falszywe | falszywe | ✓ | Demagog / Pies uratował dziecko przed wilkiem? Ta historia wyglądała inaczej | 625 |
| F3 | F | falszywe | falszywe | ✓ | FakeNews.pl / W Chinach nie zbudowano robota, który będzie rodził dzieci | 1365 |
| F4 | F | falszywe | falszywe | ✓ | Demagog / Cukrzycy nie można wyleczyć naturalnie. Uważaj na oszustwo | 501 |
| F5 | F | falszywe | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 1815 |
| F6 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 694 |
| F7 | F | falszywe | falszywe | ✓ | Demagog / Mamy już Ukropolin w Polsce? To nie są flagi Ukrainy | 595 |
| F8 | F | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, chip ze szczepionki na COVID-19 nie został wykryty przez skaner d | 323 |
| M1 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Polska, Ukraina i 490 mld zł – co mówią nam dane GUS? | 377 |
| M2 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 325 |
| M3 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Nie, paszporty covidowe nie umożliwiają permanentnej inwigilacji. Mani | 168 |
| T1 | A | potwierdzone | potwierdzone | ✓ | Demagog / Ile kosztowały wybory z 2014 roku? | 318 |
| T2 | A | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Tak, obowiązujący Polskę tekst Konwencji Stambulskiej to tekst francus | 116 |
| B1 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy obywatele Ukrainy znajdują schronienie również w Rosji? | 386 |
| B2 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Demagog / SLD pierwszy raz bez europosła? Wyjaśniamy | 158 |
| O1 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| O2 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| O3 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| D1 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ścieżki rowerowe dla Wrocławia. Czy Jacek Sutryk dotrzymał obietnicy? | 248 |
| D2 | D | brak_dowodow | brak_dowodow | ✓ | Ministerstwo Infrastruktury / Rusza budowa jednego z największych projektów infrastrukturalnych w hi | 122 |
| D3 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 72 |
| D4 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Niezrealizowane recepty w 2022 roku. Ile ich było? | 129 |
| D5 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Podatek od nieruchomości obejmie fotowoltaikę? To fałsz | 76 |
| E1 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Nadchodzi piekło 5G? Wyjaśniamy, czy jest sens bać się tej technologii | 153 |
| E2 | E | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Polska wydaje na obronność tyle co Niemcy? Fałsz Trzaskowskiego | 391 |
| E3 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 556 |
| E4 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 730 |
| I1 | I | ok | blad_techniczny | ✗ |  | 6 |
| J1 | J | blad_techniczny | blad_techniczny | ✓ |  | 2 |
| J2 | J | poza_zakresem | poza_zakresem | ✓ |  | 1 |
| J3 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
| I2 | I | brak_dowodow, falszywe | falszywe | ✓ | Demagog / Polska wysyła żołnierzy do walki w Ukrainie? Fałszywe informacje | 611 |
