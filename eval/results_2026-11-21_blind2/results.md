# Prawdowid — wyniki ewaluacji

Przypadków: 50 · korpus: 4410 dok., 24 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.901 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 1.0 | ≥ 90% |
| Czas (mediana / p95) | 581 ms / 1733 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 1.0 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| B2-01 | F | falszywe | falszywe | ✓ | FakeNews.pl / Węgiel brunatny nie jest najtańszym źródłem energii w Polsce | 13447 |
| B2-02 | F | falszywe | falszywe | ✓ | Demagog / Soda oczyszczona nie pomoże na raka. To dezinformacja medyczna | 734 |
| B2-03 | F | falszywe | falszywe | ✓ | FakeNews.pl / Unia Europejska nie zakaże picia kawy z mlekiem i cukrem | 1181 |
| B2-04 | Q | falszywe | brak_dowodow | ✗ | FakeNews.pl / W wyborach można głosować z aplikacją mObywatel | 1733 |
| B2-05 | F | falszywe | falszywe | ✓ | FakeNews.pl / Nazwa Mostu Grunwaldzkiego we Wrocławiu nie zostanie zmieniona na niem | 1131 |
| B2-06 | F | falszywe | brak_dowodow | ✗ | FakeNews.pl / Pasek TVP Info „Rafała Trzaskowskiego nadal nie ma” to przeróbka. | 188 |
| B2-07 | F | falszywe | brak_dowodow | ✗ | Konkret24 (TVN24) / "Teraz kobiety". Czy na Ukrainie trwa przymusowy pobór kobiet | 1331 |
| B2-08 | F | falszywe | falszywe | ✓ | FakeNews.pl / Erupcja Etny nie przekreśliła unijnych planów zmniejszenia emisji CO₂  | 650 |
| B2-09 | F | falszywe | falszywe | ✓ | Demagog / Pakt migracyjny. Wszystkie państwa UE są nim związane | 1905 |
| B2-10 | Q | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Czy mamy nowy banknot o nominale 1000 zł? Sprawdzamy | 491 |
| B2-11 | M | wprowadzajace_w_blad, falszywe | brak_dowodow | ✗ | Demagog / Twoje pieniądze z PPK pójdą na państwowe projekty? Nie ma takich planó | 535 |
| B2-12 | M | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Panele słoneczne przyśpieszają zmianę klimatu? Raport wyjęto z konteks | 942 |
| B2-13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Winnice w Mołdawii. Co się z nimi stanie po wejściu do UE? | 1319 |
| B2-14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Czy wiatraki wywołują suszę? Zmanipulowano wnioski z badań | 1078 |
| B2-15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | Demagog / Przestępczość Ukraińców w Polsce. Co mówią statystyki? | 902 |
| B2-16 | T | potwierdzone | potwierdzone | ✓ | Demagog / Eurowybory – ile mandatów przypadnie Polsce? | 654 |
| B2-17 | T | potwierdzone | potwierdzone | ✓ | Demagog / Do 100 mld zł rocznie. Czy tyle kosztuje Polskę nadmierne spożycie alk | 1077 |
| B2-18 | T | potwierdzone | potwierdzone | ✓ | Demagog / 95 proc. Ukraińców w wieku poborowym pracuje. Jak rząd to policzył? | 817 |
| B2-19 | T | potwierdzone | potwierdzone | ✓ | FakeNews.pl / Polecenie Orlenu dotyczące informowania o awarii dystrybutorów jest pr | 670 |
| B2-20 | Q | potwierdzone | potwierdzone | ✓ | Demagog / Ile jest pustostanów w Krakowie? W sieci krążą różne dane | 1082 |
| B2-21 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Rozporządzenie Rady Ministrów z dnia 11 września 2025 r. w sprawie wys | 495 |
| B2-22 | A | potwierdzone | potwierdzone | ✓ | Sejm RP — ISAP / Dziennik Ustaw (ELI API) / Ustawa z dnia 10 stycznia 2018 r. o ograniczeniu handlu w niedziele i  | 722 |
| B2-23 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP USD/PLN z 2026-11-20: 4,0613 zł | 465 |
| B2-24 | A | potwierdzone | potwierdzone | ✓ | Eurostat (Komisja Europejska) / Ochrona czasowa (Ukraina) 2026-09: Polska 858 545 osób (Eurostat) | 779 |
| B2-25 | A | potwierdzone | potwierdzone | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2024/1689 z dnia 1 | 667 |
| B2-26 | A | falszywe | falszywe | ✓ | Narodowy Bank Polski / Stopy procentowe NBP — stopa referencyjna 3,75% (od 2026-03-05) | 479 |
| B2-27 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — czerwiec 2026: 2,5% r/r (GUS) | 656 |
| B2-28 | A | falszywe | falszywe | ✓ | Państwowa Komisja Wyborcza / Obwieszczenie Państwowej Komisji Wyborczej z dnia 17 października 2023 | 563 |
| B2-29 | A | falszywe | falszywe | ✓ | Eurostat (Komisja Europejska) / Deficyt sektora finansów publicznych 2025: Polska -7,2% PKB (Eurostat) | 618 |
| B2-30 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / 5G i Bluetooth wciąż nie wywołują raka. To znana teoria spiskowa | 504 |
| B2-31 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Choroby psychiczne a zakaźność. „Kompletna bzdura” z TikToka | 415 |
| B2-32 | N | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Demagog / Fałszywa aplikacja Lotto. Jak ją rozpoznać? | 510 |
| B2-33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 13 |
| B2-34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 11 |
| B2-35 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 11 |
| B2-36 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 10 |
| B2-37 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Robert Lewandowski ofiarą oszustwa z kryptowalutami w tle | 227 |
| B2-38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Chlorowana woda w basenie? Pod kontrolą nie szkodzi zdrowiu | 214 |
| B2-39 | D | brak_dowodow | brak_dowodow | ✓ | EUvsDisinfo (EEAS East StratCom Task Force) / Russia must close all NATO consulates in Kaliningrad because of espion | 137 |
| B2-40 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / SCT w Krakowie. Ile pojazdów miała wykluczyć według urzędników? | 255 |
| B2-41 | D | brak_dowodow | brak_dowodow | ✓ | Konkret24 (TVN24) / Ministra zdrowia: płacimy 100 procent za profilaktykę gastroskopii. Ni | 216 |
| B2-42 | D | brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Korupcja na Ukrainie. Czy minister obrony został zwolniony za kradzież | 230 |
| B2-43 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Putin aresztuje Gatesa za stworzenie dżumy? Taka sytuacja nie miała mi | 1705 |
| B2-44 | E | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 514 |
| B2-45 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Donald Tusk nie mówił o polskim ataku na Westerplatte | 1865 |
| B2-46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Europejscy przywódcy nie zażywali narkotyków w pociągu | 475 |
| B2-47 | B | wprowadzajace_w_blad, brak_dowodow | wprowadzajace_w_blad | ✓ | Stowarzyszenie Pravda / Pokojowa Nagroda Nobla dla dziennikarzy! | 507 |
| B2-48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy w Singapurze niezaszczepieni na koronawirusa będą musieli sami opł | 600 |
| B2-49 | J | blad_techniczny | blad_techniczny | ✓ |  | 50 |
| B2-50 | J | doprecyzuj | doprecyzuj | ✓ |  | 10 |
