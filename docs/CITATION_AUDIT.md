# Audyt poprawności cytatów i pokrycia tez

**Pomiar z 22 listopada 2026 r. — pojedyncza ocena semantyczna AI, niezależna od reguł i NLI silnika.**

W próbce odpowiedzi Prawdowida obecność źródła nie zapewniała poprawnego uzasadnienia każdej tezy. Pokrycie wystarczającym dowodem wyniosło **82,5%**, a poprawność ocenionych powiązań teza–cytat **69,6%**. W tej recenzji oba wyniki są poniżej celów konkursowych 95% i 85%.

To wynik jawnych adnotacji jednego recenzenta AI. Nie jest zatwierdzeniem niezależnego człowieka ani estymatą jakości wszystkich przyszłych odpowiedzi. Sam recenzent uczestniczył wcześniej w pracach nad projektem; niezależność jest tu ograniczona do odrębnego sposobu oceniania, bez użycia silnika i jego NLI jako sędziego.

Definicje pochodzą z tabeli „Mierniki obowiązkowe”, strona 8 [zadania konkursowego](../rules/MSZ%20-%20Pełna%20treść%20zadania%20konkursowego.pdf): pokrycie dotyczy odsetka tez faktograficznych z dowodem, a poprawność tego, czy fragment rzeczywiście wspiera tezę.

## Zakres i metoda

Zamrożono odpowiedzi dla 145 istniejących przypadków oraz przywołane rekordy źródłowe. Wybrano deterministyczną próbę 30 odpowiedzi, warstwowaną według rodzaju wyniku, wielowątkowości i braku twierdzeń, z ziarnem `20261122`. Zbiory wejściowe były wcześniej używane do rozwoju produktu; nie stanowią nowego testu ślepego.

Recenzja obejmowała 393 powierzchnie tekstowe. W 16 odpowiedziach wystąpiło łącznie 57 odrębnych ustaleń faktograficznych. Pozostałe 14 odpowiedzi zawierało jedynie abstynencję, opinię lub komunikat wykonania, więc nie zwiększało mianownika tez. Powtórzenia tej samej tezy między krótką odpowiedzią, wyjaśnieniem i podsumowaniem liczono raz w obrębie odpowiedzi.

Oceniano osobno wnioski, dodatkowe fakty w wyjaśnieniu oraz atrybucje ocen wydawcom. Wyłączono surowe cytowanie pytania użytkownika, metadane bibliograficzne, nawigacyjne rekomendacje stron i czysto proceduralne komunikaty. Ich klasyfikację zapisano jawnie; nie potraktowano ich jako automatycznie poprawnych cytowań.

Recenzent nie otrzymał oczekiwanych etykiet i notatek autorów testów w pakietach. Porównywał treść odpowiedzi z pokazanym fragmentem i zamrożonym rekordem źródła. Nie pobierano ponownie stron ani danych pierwotnych. Ocena nie sprawdza więc niezależnie, czy dane instytucji lub fact-checkera są prawdziwe i aktualne poza tym zapisem.

## Wyniki

| Miara | Licznik / mianownik | Wynik | Znaczenie |
|---|---:|---:|---|
| Obecność źródła przy tezie | 57 / 57 | 100% | Każda oceniana teza miała przypisany materiał; nie jest to jeszcze dowód. |
| Pokrycie tezy wystarczającym dowodem | 47 / 57 | **82,5%** | Cel ≥95% nie został osiągnięty w tej recenzji. |
| Poprawność powiązania teza–cytat | 32 / 46 | **69,6%** | Cel ≥85% nie został osiągnięty w tej recenzji. |
| Poprawność wszystkich ocenionych powiązań dowodowych | 48 / 62 | 77,4% | Obejmuje też metadane i automatyczne karty danych. |
| Niepokryte tezy | 10 / 57 | 17,5% | Lista z uzasadnieniami znajduje się w raporcie JSON. |

Spośród 62 relacji 46 dotyczyło dosłownych cytatów, 12 metadanych oceny źródła, a 4 automatycznych opisów danych. Metadane i opisy danych nie podnoszą wyniku poprawności dosłownego cytowania. Ocenione fragmenty nie miały niezgodności dosłowności względem zamrożonych rekordów; błędy dotyczyły ich znaczenia i zakresu.

Poprawność liczymy dla ocenionych relacji teza–cytat, nie dla wszystkich kart pokazanych jako materiały kontekstowe. Jeden fragment może być poprawny jako dowód tego, co napisał internauta, ale błędny jako dowód prawdziwości albo fałszywości jego twierdzenia.

Ze względu na warstwowanie, wspólne odpowiedzi dla kilku tez i jednego recenzenta nie przedstawiamy tych wartości jako ważonego wyniku populacji ani nie dodajemy pozornego przedziału ufności.

## Najważniejsze stwierdzone problemy

| Pakiet | Problem | Dlaczego samo źródło nie wystarcza |
|---|---|---|
| P003 — szczepienia przeciw grypie | Cytatem uzasadniającym ocenę jest pytanie „Dlaczego […] dalej chorujemy? Wyjaśniamy”. | W pełnym rekordzie jest wyjaśnienie, ale pokazany fragment nie przekazuje brakującego kontekstu. |
| P021 — niemieckie wiatraki | Główny cytat powtarza sugestię postów o nieopłacalności. | Przytoczenie pogłoski nie jest jej sprostowaniem; dodatkowy przykład jednej farmy nie rozstrzyga całego uogólnienia. |
| P022 — zdjęcie Taylor Swift | Cytat mówi tylko, że post ze zdjęciem wywołał oburzenie. | Nie ustala miejsca, czasu ani rzeczywistego pochodzenia fotografii. |
| P023 — przestępstwa na 1000 osób | Wybrano liczby wszystkich przestępstw i przestępstw obcokrajowców. | Brakuje mianowników ludności i danych dotyczących konkretnie Ukraińców, potrzebnych do oceny ilorazu. |
| P024 — wynik wyborów | Odpowiedź potwierdza zdanie zawierające zwycięzcę i dokładny odsetek 50,89%. | Fragment wspiera zwycięstwo, ale nie podaje odsetka; tę część trzeba oceniać osobno. |
| P025 — polskie mandaty do PE | Cytat podaje 720 mandatów całego parlamentu. | Nie dowodzi 53 mandatów Polski ani jej pozycji wśród delegacji, mimo że pełny rekord zawiera te informacje. |
| P026 — naprawy starszych aut | Główny cytat przytacza wpis o zakazie. | Sam główny cytat nie uzasadnia sprostowania; teza ma jednak pokrycie w innym wyświetlonym fragmencie, który przytacza stanowisko PE. |
| P027 — uchodźcy w Rosji | Komunikat mówi o sprzecznych źródłach. | Pokazane fragmenty nie wykazują rozbieżności tej samej liczby, w tym samym czasie i zakresie. |

Częściowe wsparcie stwierdzono też dla P011: cytat odnoszący się szczególnie do dolnośląskiego nie pokazuje wartości dla dwóch województw wymienionych przez użytkownika ani danych krajowych. Rzetelna ocena całej tezy wymaga szerszego fragmentu.

Te wyniki nie oznaczają, że każdy wskazany werdykt jest fałszywy. Rozróżniamy błędny lub niepełny **dobór uzasadnienia** od błędu samego końcowego ustalenia.

## Co zostało zmienione w pomiarze

`eval/run_eval.py` nie przedstawia już starej obecności materiału jako rzeczywistego pokrycia cytowaniami. Dawny licznik ma nazwę `citation_presence_proxy`, a `citation_coverage` i `citation_correctness` są `null` do czasu osobnego audytu.

Nowy protokół:

- zamraża pełną odpowiedź i teksty przywołanych źródeł;
- nie pozwala, aby pierwsze poprawnie udokumentowane twierdzenie zakryło brak dowodu dla kolejnego;
- wymaga inwentarza wszystkich ustaleń, także dodatkowych w wyjaśnieniach;
- rozróżnia dowód wystarczający, częściowy, niepopierający, sprzeczny i nieocenialny;
- nie zalicza nieobecnego cytatu, zmienionego pakietu ani źródła przypisanego do innego twierdzenia;
- nie traktuje braku tez jako 100% jakości;
- zachowuje typ recenzenta i oddziela ocenę AI od recenzji człowieka.

Protokół przeszedł 10 testów, także z optymalizacją `python -O`. Nie zmieniano reguł werdyktów ani doboru cytatów tylko po to, aby poprawić wynik pomiaru.

## Materiały do odtworzenia i recenzji

- [Pochodzenie danych, ustawienia i SHA-256 artefaktów](../eval/citation_audit_2026-11-22/provenance.json) oraz [dokładne wejście kolekcji](../eval/citation_audit_2026-11-22/capture/cases.jsonl).
- [Protokół i polecenia](../eval/citations/README.md).
- [Wynik liczbowy i niepokryte tezy](../eval/citation_audit_2026-11-22/report.json).
- [Pakiety do recenzji bez oczekiwanych etykiet](../eval/citation_audit_2026-11-22/review/packets.jsonl).
- [Pełne oceny AI z uzasadnieniami](../eval/citation_audit_2026-11-22/review/reviews.ai.jsonl).
- [Pusty inwentarz do niezależnej oceny człowieka](../eval/citation_audit_2026-11-22/review/reviews.blank.jsonl).
- [Przykład formatu pojedynczej adnotacji](../eval/citation_audit_2026-11-22/review/annotation-example.json).
- [Sposób losowania](../eval/citation_audit_2026-11-22/review/sampling.json) i [mapa przypadków dla koordynatora](../eval/citation_audit_2026-11-22/review/sampling_map.jsonl).
- [Pełne odpowiedzi](../eval/citation_audit_2026-11-22/capture/responses.jsonl), [zamrożone źródła](../eval/citation_audit_2026-11-22/capture/citation_sources.jsonl) i [ich skróty](../eval/citation_audit_2026-11-22/capture/citation_capture.json).

## Zmiana mechanizmu po audycie

Powyższe 82,5% i 69,6% dotyczą wersji **sprzed poprawki**. Reguły silnika 1.1 dodają kontrolę cytatu V5, szukanie ustalenia w całym zapisanym artykule i kontrole liczb oraz zakresu. Szczegóły: [silnik i V5](backend/ENGINE.md). Wyników audytu nie nadpisujemy ani nie podnosimy na podstawie własnych ocen NLI silnika. Walidacja zmiany jest w [raporcie regresji](../eval/citation_grounding_2026-11-22/README.md).

## Dalszy krok

Niezależny człowiek powinien ocenić te same pakiety bez podglądania ocen AI, a sporne przypadki poddać drugiemu przeglądowi. Do tego czasu nie oznaczamy progu 85% jako potwierdzonego.

W samym produkcie priorytetem jest dobór fragmentu zawierającego ustalenie zamiast opisu pogłoski, osobne pokrycie liczb i części zdania oraz sprawdzanie zakresu rzekomego konfliktu źródeł. Po takich poprawkach trzeba zebrać nową próbę; obecna stanie się zestawem regresyjnym.
