# Prawdowid — wyniki ewaluacji

Przypadków: 38 · korpus: 2285 dok., 16 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 1.0 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 455 ms / 3378 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| A1 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 8930 |
| A2 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2026: 3,0% r/r (GUS) | 359 |
| A3 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 290 |
| A4 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci | 477 |
| A5 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1351 z dnia 1 | 1749 |
| A6 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Inflacja HICP 2026-10: Polska 3,7% vs UE 4,0% (Eurostat) | 575 |
| F1 | F | falszywe | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 1244 |
| F2 | F | falszywe | falszywe | ✓ | FakeNews.pl / Wilk nie zaatakował dwuletniego dziecka w Toskanii | 374 |
| F3 | F | falszywe | falszywe | ✓ | FakeNews.pl / W Chinach nie zbudowano robota, który będzie rodził dzieci | 410 |
| F4 | F | falszywe | falszywe | ✓ | Demagog / Cukrzycy nie można wyleczyć naturalnie. Uważaj na oszustwo | 382 |
| F5 | F | falszywe | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 1012 |
| F6 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 573 |
| F7 | F | falszywe | falszywe | ✓ | Demagog / Mamy już Ukropolin w Polsce? To nie są flagi Ukrainy | 717 |
| F8 | F | brak_dowodow | brak_dowodow | ✓ | Demagog / Szczepionki przeciw COVID-19 zbrodnią przeciw ludzkości? Manipulacja! | 934 |
| M1 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Polska, Ukraina i 490 mld zł – co mówią nam dane GUS? | 849 |
| M2 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 496 |
| M3 | B | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | FakeNews.pl / Nie, paszporty covidowe nie umożliwiają permanentnej inwigilacji. Mani | 931 |
| T1 | A | potwierdzone | potwierdzone | ✓ | Demagog / Ile kosztowały wybory z 2014 roku? | 344 |
| T2 | A | potwierdzone | potwierdzone | ✓ | Stowarzyszenie Pravda / Tak, obowiązujący Polskę tekst Konwencji Stambulskiej to tekst francus | 434 |
| B1 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy obywatele Ukrainy znajdują schronienie również w Rosji? | 717 |
| B2 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 10 czerwca 2024 r. o | 375 |
| O1 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 11 |
| O2 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 13 |
| O3 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 15 |
| D1 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Tragiczny wypadek w Krakowie. Na tej drodze dochodziło już do zdarzeń  | 417 |
| D2 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Z CPK za PiS nic się nie działo? Fałsz Trzaskowskiego | 136 |
| D3 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 175 |
| D4 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / „Lex szarlatan” nie odbiera wolności wyboru pacjentom. Analiza | 189 |
| D5 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Ile jest stacji ładowania samochodów elektrycznych w Polsce i Holandii | 245 |
| E1 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Konkret24 (TVN24) / Tysiące noworodków chorują z powodu "szczepionki od Gatesów"? W tej hi | 219 |
| E2 | E | brak_dowodow, falszywe | brak_dowodow | ✓ | EUvsDisinfo (EEAS East StratCom Task Force) / The USA wants to establish a Greater Poland in Eastern Europe in excha | 2699 |
| E3 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 2411 |
| E4 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Niemcy w kombinezonach ochronnych nie „podrzucali” do Polski chorych m | 973 |
| I1 | I | ok | brak_dowodow | ✓ | Ministerstwo Spraw Zagranicznych / Oświadczenia MSZ w związku z atrybucją przez Danię rosyjskim służbom s | 3378 |
| J1 | J | blad_techniczny | blad_techniczny | ✓ |  | 5101 |
| J2 | J | poza_zakresem | poza_zakresem | ✓ |  | 13 |
| J3 | J | doprecyzuj | doprecyzuj | ✓ |  | 13 |
| I2 | I | brak_dowodow, falszywe | brak_dowodow | ✓ | Demagog / Pomyłka ukraińskiej redakcji. Sikorski nie mówił o F-16 | 822 |
