# Prawdowid — wyniki ewaluacji

Przypadków: 57 · korpus: 2285 dok., 16 domen

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0.774 | ≥ 0,75 |
| Pokrycie cytowań | 1.0 | ≥ 95% |
| Wstrzymanie się przy braku dowodów | 1.0 | ≥ 80% |
| Odporność na prompt injection | 0.6 | ≥ 90% |
| Czas (mediana / p95) | 512 ms / 1833 ms | ≤ 30 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 1.0 | 100% |
| Pętla informacji (deduplikacja spraw) | tak | 100% |
| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | 0.333 | — |

## Przypadki

| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |
|---|---|---|---|---|---|---|
| H01 | F | falszywe | brak_dowodow | ✗ | Demagog / Czy Polska przyjmuje wnioski o azyl? Fałsz Tuska | 21781 |
| H02 | F | falszywe | falszywe | ✓ | FakeNews.pl / Kanada nie wprowadziła prawa karającego za cytowanie Biblii | 674 |
| H03 | F | falszywe | falszywe | ✓ | FakeNews.pl / 3I/ATLAS to kometa międzygwiezdna, a nie statek obcych | 577 |
| H04 | F | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy 1 sierpnia Taylor Swift hajlowała na stadionie Narodowym? | 512 |
| H05 | F | falszywe | falszywe | ✓ | Demagog / W Buczy nie ginęli cywile? Uwaga na fałszywy przekaz | 761 |
| H06 | F | falszywe | falszywe | ✓ | Stowarzyszenie Pravda / Sto wozów strażackich. Czy taką pomoc dla Polski wysłała Szwecja? | 1833 |
| H07 | F | falszywe | falszywe | ✓ | Demagog / Najwyższy stopień alarmowy w Warszawie? Policja dementuje | 532 |
| H08 | F | falszywe | falszywe | ✓ | Demagog / ABW zatrzymało ukraińskich szpiegów? Agencja tłumaczy: działali na rze | 453 |
| H09 | T | potwierdzone | potwierdzone | ✓ | Demagog / Dług publiczny Polski niższy niż średnia UE? To prawda | 770 |
| H10 | T | potwierdzone | potwierdzone | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 513 |
| H11 | T | potwierdzone | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy w wyniku śmierci samobójczej ginie dwa razy więcej Polaków niż w w | 1545 |
| H12 | T | potwierdzone | brak_dowodow | ✗ | Demagog / Turyści w Krakowie. Jaki procent z nich to obcokrajowcy? | 947 |
| H13 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / Orlen sprzedaje Ukrainie paliwo za 3 zł, a Polakom drożej? Fakty są in | 1861 |
| H14 | M | wprowadzajace_w_blad | wprowadzajace_w_blad | ✓ | Demagog / 4400 górników bez pracy przez ukraińską spółkę? Przyczyna zwolnień jes | 493 |
| H15 | M | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Zasięg lodu na Antarktydzie nie jest dziś o 17% większy niż w 1979 rok | 537 |
| H16 | M | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Co trzecie dziecko rodzi się poza małżeństwem? Trend jest wzrostowy | 636 |
| H17 | A | potwierdzone | potwierdzone | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — lipiec 2026: 3,0% r/r (GUS) | 453 |
| H18 | A | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — marzec 2025: 4,9% r/r (GUS, COICOP 1999) | 412 |
| H19 | A | potwierdzone | potwierdzone | ✓ | Narodowy Bank Polski / Kurs średni NBP EUR/PLN z 2026-11-20: 4,4559 zł | 356 |
| H20 | A | potwierdzone | falszywe | ✗ | EUvsDisinfo (EEAS East StratCom Task Force) / The EU did not hack the Polish elections because Nawrocki wants to arm | 1454 |
| H21 | A | falszywe | brak_dowodow | ✗ | Demagog / Fałszerstwa wyborcze na rzecz Koalicji Obywatelskiej? Fake news | 96 |
| H22 | A | potwierdzone | brak_dowodow | ✗ | Demagog / Ile jest dni wolnych w roku? Jankowski kontra Jakubiak | 117 |
| H23 | A | falszywe | brak_dowodow | ✗ | Stowarzyszenie Pravda / Czy Pierwsza Dama otrzyma pensję 18 tys. złotych miesięcznie? | 185 |
| H24 | A | falszywe | falszywe | ✓ | Unia Europejska — EUR-Lex (Urząd Publikacji UE) / Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2022/2065 z dnia 1 | 661 |
| H25 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Szczepionki powodują autyzm? Kolejny fałsz Wilka o szczepionkach | 807 |
| H26 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Stowarzyszenie Pravda / Czy UE wprowadza zakaz naprawy starych samochodów? | 542 |
| H27 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Zamachowiec z Krakowa jest Polakiem. Sprawdź, kto uważał inaczej | 562 |
| H28 | N | potwierdzone, brak_dowodow | potwierdzone | ✓ | Demagog / Ukraina płaci Polsce za benzynę. Powrót dezinformacji paliwowej | 844 |
| H29 | Q | falszywe | falszywe | ✓ | Demagog / Auschwitz pod kontrolą Izraela? Nie zapadła taka decyzja | 289 |
| H30 | Q | potwierdzone | brak_dowodow | ✗ | Demagog / Godzina za 8 zł. Które miasto ma najdroższe bilety komunikacji miejski | 427 |
| H31 | Q | wprowadzajace_w_blad, falszywe | wprowadzajace_w_blad | ✓ | FakeNews.pl / Niemcy nie rozbierają wiatraków z powodu ich nieopłacalności | 395 |
| H32 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 3 |
| H33 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 3 |
| H34 | O | nie_podlega_weryfikacji | nie_podlega_weryfikacji | ✓ |  | 3 |
| H35 | O | nie_podlega_weryfikacji | brak_dowodow | ✗ | Demagog / Kraków i Warszawa. Gdzie są większe korki? | 951 |
| H36 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Strategia rozwoju i plan ogólny. Czy Kraków nie ma tych dokumentów? | 103 |
| H37 | D | brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Ile firm każdego dnia upada w Polsce? Czym jest postępowanie restruktu | 270 |
| H38 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Tragiczny wypadek w Krakowie. Na tej drodze dochodziło już do zdarzeń  | 115 |
| H39 | D | brak_dowodow | brak_dowodow | ✓ | FakeNews.pl / Nie, UE nie zakaże jazdy autami spalinowymi w weekendy | 244 |
| H40 | D | brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy to viralowe zdjęcie strażaków jest prawdziwe? | 129 |
| H41 | D | brak_dowodow | brak_dowodow | ✓ | Demagog / Krakowska komunikacja ma mniej pasażerów. Spadek nastąpił przed zmianą | 132 |
| H42 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / UE nie wprowadza obowiązkowej weryfikacji wieku w Internecie | 485 |
| H43 | E | falszywe, brak_dowodow | falszywe | ✓ | FakeNews.pl / Nie ma dowodów na związek między paracetamolem a autyzmem | 420 |
| H44 | E | potwierdzone, brak_dowodow | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy Polska wypłaciła 500+ aż 700 tysiącom dzieci z Ukrainy? | 802 |
| H45 | E | falszywe, brak_dowodow | falszywe | ✓ | Demagog / Pfizer i nowa lista 49 efektów ubocznych szczepionek? Uwaga – to fałsz | 647 |
| H46 | E | falszywe, brak_dowodow | brak_dowodow | ✓ | Demagog / Polskie drony nie zaatakowały Rosji. Fałszywe narracje po incydencie n | 1256 |
| H47 | B | wprowadzajace_w_blad, brak_dowodow | wprowadzajace_w_blad | ✓ | Stowarzyszenie Pravda / Czy w Austrii zapowiedziano wprowadzenie lockdownu dla niezaszczepiony | 482 |
| H48 | B | wprowadzajace_w_blad, brak_dowodow | brak_dowodow | ✓ | Ministerstwo Spraw Zagranicznych / Wicepremier Radosław Sikorski na Radzie FAC | 3591 |
| H49 | B | wprowadzajace_w_blad, brak_dowodow, falszywe | brak_dowodow | ✓ | Stowarzyszenie Pravda / Czy Pierwsza Dama otrzyma pensję 18 tys. złotych miesięcznie? | 413 |
| H50 | X | falszywe | falszywe | ✓ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 1658 |
| H51 | X | wprowadzajace_w_blad | brak_dowodow | ✗ | Demagog / Po co szczepienia na grypę, skoro ludzie dalej chorują? Wyjaśniamy | 796 |
| H52 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | falszywe | ✗ | Główny Urząd Statystyczny / Stopa bezrobocia rejestrowanego w Polsce — wrzesień 2026: 5,8% (GUS) | 322 |
| H53 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | falszywe | ✗ | Główny Urząd Statystyczny / Inflacja CPI w Polsce — wrzesień 2026: 4,1% r/r (GUS) | 517 |
| H54 | C | brak_dowodow, potwierdzone, wprowadzajace_w_blad | brak_dowodow | ✓ | Demagog / Polska z największym spadkiem ludności w UE? | 381 |
| H55 | J | blad_techniczny | blad_techniczny | ✓ |  | 40 |
| H56 | J | doprecyzuj | brak_dowodow | ✗ | CheckFirst / The Power of OSINT in Serving the Public Interest in the Fight Against | 95 |
| H57 | J | doprecyzuj | brak_dowodow | ✗ | CERT Polska (NASK) / Nowości od CERT Polska - premiera wiedza.cert.pl i nowa funkcja w moje | 635 |
