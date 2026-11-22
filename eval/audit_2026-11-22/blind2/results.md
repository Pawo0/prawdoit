# Prawdowid — wyniki ewaluacji

Przypadków: 50 · korpus: 8807 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.912 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 202 ms / 816 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| B2-01 | F | falszywe | falszywe | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 8409 |
| B2-02 | F | falszywe | falszywe | ✓ | Demagog / Soda oczyszczona nie pomoże na raka. To dezinformacja medyczna | 442 |
| B2-03 | F | falszywe | falszywe | ✓ | FakeNews.pl / Unia Europejska nie zakaże picia kawy z mlekiem i cukrem | 216 |
| B2-04 | Q | falszywe | brak_dowodow | ✗ | FakeNews.pl / W wyborach można głosować z aplikacją mObywatel | 177 |
| B2-05 | F | falszywe | falszywe | ✓ | FakeNews.pl / Nazwa Mostu Grunwaldzkiego we Wrocławiu nie zostanie zmieniona na niem | 216 |
| B2-06 | F | falszywe | brak_dowodow | ✗ | Demagog / Rafał Brzoska nie został postrzelony. Historia zmyślona przez oszustów | 76 |
| B2-07 | F | falszywe | falszywe | ✓ | Demagog / Czy to nagranie z ukraińskiej mobilizacji? Zweryfikowaliśmy film | 752 |
| B2-08 | F | falszywe | falszywe | ✓ | Demagog / Wybuch Etny przekreślił wysiłki klimatyczne UE? Poseł Pejo się myli. | 454 |
| B2-09 | F | falszywe | falszywe | ✓ | Demagog / Pakt migracyjny. Wszystkie państwa UE są nim związane | 1236 |
| B2-10 | Q | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy mamy nowy banknot o nominale 1000 zł? Sprawdzamy | 149 |
| B2-11 | M | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | Demagog / Twoje pieniądze z PPK pójdą na państwowe projekty? Nie ma takich planó | 276 |
| B2-12 | M | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Panele słoneczne przyśpieszają zmianę klimatu? Raport wyjęto z konteks | 212 |
| B2-13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Winnice w Mołdawii. Co się z nimi stanie po wejściu do UE? | 495 |
| B2-14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Czy wiatraki wywołują suszę? Zmanipulowano wnioski z badań | 351 |
| B2-15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | Demagog / Przestępczość Ukraińców w Polsce. Co mówią statystyki? | 370 |
| B2-16 | T | potwierdzone | potwierdzone | ✓ | Demagog / Eurowybory – ile mandatów przypadnie Polsce? | 351 |
| B2-17 | T | potwierdzone | potwierdzone | ✓ | Demagog / Do 100 mld zł rocznie. Czy tyle kosztuje Polskę nadmierne spożycie alk | 704 |
| B2-18 | T | potwierdzone | potwierdzone | ✓ | Demagog / 95 proc. Ukraińców w wieku poborowym pracuje. Jak rząd to policzył? | 816 |
| B2-19 | T | potwierdzone | potwierdzone | ✓ | FakeNews.pl / Polecenie Orlenu dotyczące informowania o awarii dystrybutorów jest pr | 205 |
| B2-20 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Ile jest pustostanów w Krakowie? W sieci krążą różne dane | 486 |
| B2-21 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 11 września 2025 r. w sprawie wys | 120 |
| B2-22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 10 stycznia 2018 r. o ograniczeniu handlu w niedziele i  | 198 |
| B2-23 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP USD/PLN z 2026-11-20: 4,0613 zł | 110 |
| B2-24 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Ochrona czasowa (Ukraina) 2026-09: Polska 858 545 osób (Eurostat) | 295 |
| B2-25 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1689 z dnia 1 | 164 |
| B2-26 | A | falszywe | falszywe | ✓ | Narodowy Bank Polski / Stopy procentowe NBP — stopa referencyjna 3,75% (od 2026-03-05) | 153 |
| B2-27 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — czerwiec 2026: 2,5% r/r (GUS) | 192 |
| B2-28 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 167 |
| B2-29 | A | falszywe | falszywe | ✓ | Eurostat (Komisja Europejska) / Deficyt sektora finansów publicznych 2025: Polska -7,2% PKB (Eurostat) | 506 |
| B2-30 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / 5G i Bluetooth wciąż nie wywołują raka. To znana teoria spiskowa | 367 |
| B2-31 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Choroby psychiczne a zakaźność. „Kompletna bzdura” z TikToka | 322 |
| B2-32 | N | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Demagog / Fałszywa aplikacja Lotto. Jak ją rozpoznać? | 167 |
| B2-33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 3 |
| B2-34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| B2-35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| B2-36 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 2 |
| B2-37 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Lewandowski mówi o aplikacji do zarabiania? To scam z użyciem AI | 123 |
| B2-38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Incydent w Katowicach nie ma związku z zamknięciem kąpieliska – wyjaśn | 58 |
| B2-39 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Upada jeden z większych szpitali w Polsce? Ministerstwo Zdrowia dement | 152 |
| B2-40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Uwaga na oszustwo! ZTM Gdańsk nie rozdaje kart na przejazdy | 47 |
| B2-41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / [Debata TVP] NFZ niezgodny z Konstytucją? Wyrok dotyczył innej ustawy | 63 |
| B2-42 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Złóż życzenia i odbierz nagrodę. To kolejne oszustwo na Biedronkę | 71 |
| B2-43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Putin aresztuje Gatesa za stworzenie dżumy? Taka sytuacja nie miała mi | 227 |
| B2-44 | E | potwierdzone, brak_dowodow | potwierdzone | ✓ | Główny Urząd Statystyczny — Bank Danych Lokalnych / Liczba zgonów w Polsce — 2025: 405 747 (GUS BDL) | 317 |
| B2-45 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Donald Tusk nie mówił o polskim ataku na Westerplatte | 1048 |
| B2-46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Czy Macron został przyłapany na braniu kokainy? Uwaga na dezinformację | 149 |
| B2-47 | B | wprowadzajace_w_blad, brak_dowodow | wprowadzajace_w_blad | ✓ | Stowarzyszenie Pravda / Pokojowa Nagroda Nobla dla dziennikarzy! | 120 |
| B2-48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Singapurze niezaszczepieni na koronawirusa będą musieli sami opł | 207 |
| B2-49 | J | blad_techniczny | blad_techniczny | ✓ |  | 5 |
| B2-50 | J | doprecyzuj | doprecyzuj | ✓ |  | 1 |
