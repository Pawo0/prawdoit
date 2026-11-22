# Prawdowid — funkcjonalności względem wymagań MSZ

**Stan na 22 listopada 2026 r.**

Prawdowid pozwala sprawdzić wiadomość, link lub tekst ze zrzutu ekranu. Wyszukuje materiały w jawnym katalogu źródeł, przedstawia ocenę z uzasadnieniem i cytatami oraz informuje, czego nie udało się ustalić. Gdy dowody nie wystarczają, wstrzymuje się od rozstrzygnięcia.

**Mamy zaimplementowany podstawowy przepływ MVP oraz szereg funkcji premiowanych.** Część wymagań jest obsługiwana częściowo lub wymaga potwierdzenia na wdrożeniu. Poniższe zestawienie rozróżnia te sytuacje; nie jest deklaracją pełnej zgodności ani wynikiem oceny jury.

Podstawa: [pełna treść zadania konkursowego MSZ](../rules/MSZ%20-%20Pełna%20treść%20zadania%20konkursowego.pdf), kod produktu i [ostatnia weryfikacja backendu](../eval/backend_refactor_2026-11-22/verification.json).

## 1. Podstawowe funkcje dla użytkownika

| Wymaganie | Co już mamy | Stan |
|---|---|---|
| Przyjęcie tekstu lub adresu URL | Formularz WWW, pobieranie publicznej strony i obsługa linku umieszczonego w wiadomości. | Działa |
| Responsywne WWW i dodatkowy kanał | Strona WWW oraz Discord  | Działa |
| Rozpoznawanie twierdzeń | Wybór do trzech twierdzeń z wiadomości; rozróżnianie faktów, opinii i prognoz. | Działa |
| Pięć klas wyniku | Potwierdzone, fałszywe, wprowadzające w błąd, brak wystarczających dowodów, nie podlega weryfikacji. | Działa |
| Oddzielna obsługa problemów wykonania | Błąd techniczny, potrzeba doprecyzowania i wyjście poza zakres są oddzielone od werdyktów. | Działa |
| Zwięzła odpowiedź po polsku | Krótkie wyjaśnienie, podstawa odpowiedzi i ograniczenia; wspólna warstwa odpowiedzi dla kanałów. | Działa |
| Pokazanie dowodów | Tytuł, wydawca, link, dostępna data i dosłowny fragment źródła, oddzielone od interpretacji. | Działa; część korpusu nie ma daty publikacji |
| Jawna siła podstawy odpowiedzi | Przesłanki uwzględniają m.in. typ źródła, zgodność z tezą, aktualność, konflikty i liczbę wydawców. | Działa |
| Wstrzymanie się przy braku dowodów | Abstynencja, opis niewiedzy i wskazanie materiału, który mógłby rozstrzygnąć sprawę. | Działa |
| Obsługa sprzecznych informacji | Pokazanie rozbieżności i ograniczenie pewności zamiast arbitralnego wyboru odpowiedzi. | Działa |
| Pełna ścieżka bez udziału twórców | Przyjęcie zgłoszenia → analiza → odpowiedź → zapis przebiegu. Dostępna również realizacja asynchroniczna z etapami postępu. |  Działa|
| Zapis przebiegu | Zamaskowane wejście, czas, źródła, wynik i metadane sprawdzenia w audycie. | Działa |

**Gdzie to zobaczyć:** strona główna `/`, analiza `/analiza/{id}`, oraz bot Discord. Szczegóły: [przebieg sprawdzenia](backend/REQUEST_FLOW.md) i [API i kanały](backend/API.md).

## 2. Źródła, aktualność i panel administratora

W ostatnim pomiarze indeks obejmował **8807 rekordów, 24 domeny i 3 typy źródeł**: urzędowe, fact-checkingowe oraz bazy incydentów. Spełnia to minimum konkursowe: 100 rekordów, 10 domen i 2 typy, z materiałami pierwotnymi oraz wtórnymi.

Mamy:

- **Jawny katalog źródeł** z wydawcą, kategorią, uzasadnieniem kwalifikacji, warunkami wykorzystania i harmonogramem aktualizacji.
- **Panel administratora** do dodawania i edycji źródeł, automatycznego wykrywania metody pobierania, testowania konfiguracji, uruchamiania pobrań oraz włączania i wyłączania źródeł.
- **Harmonogram pobierania** i przeładowanie indeksu po zmianie danych.
- **Historię pobrań i dziennik zmian**, umożliwiające kontrolę działania źródeł.
- **Daty pobrania i publikacji**, reguły rozpoznawania materiałów archiwalnych oraz ostrzeżenia o ich wieku.
- **Wyszukiwanie na żywo** w źródłach z rejestru, Google Fact Check i opcjonalnych dostawcach; nowe dowody są oceniane tym samym silnikiem.
- **Paginację katalogu i panelu administratora**: 10, 25 lub 50 pozycji, nawigację i licznik. Panel zachowuje stronę podczas automatycznego odświeżania.

**Ograniczenia:** 50 rekordów z ostatniego pomiaru nie miało daty publikacji. Dostęp do zewnętrznych usług zależy od kluczy i dostępności serwisów. Jawny opis licencji nie zastępuje przeglądu zasad wykorzystania i przechowywania każdej treści.

**Gdzie to zobaczyć:** `/zrodla` i `/admin`. Szczegóły: [rejestr źródeł](SOURCE_REGISTRY.md), [katalog](SOURCES.md) oraz [pobieranie i wyszukiwanie](backend/SOURCES.md).

## 3. Bezpieczeństwo, prywatność i transparentność

| Wymaganie | Co już mamy | Granica obecnej obsługi |
|---|---|---|
| Odporność na prompt injection | Wykrywanie i neutralizacja instrukcji w wiadomości, OCR i pobranej stronie; zapis zdarzeń bezpieczeństwa. | Potwierdzone w testach; nie jest to gwarancja odporności na każdy nowy atak. |
| Bezpieczne pobieranie stron | Kontrola publicznych adresów i przekierowań, ograniczenia czasu i rozmiaru, obsługa odmowy dostępu. | Pobieranie nie obchodzi CAPTCHA ani płatnych baz. |
| Ochrona paneli i limitowanie | Tokeny administratora i moderatora, osobne limity pełnych sprawdzeń oraz paczek wtyczki. | Limity są lokalne dla procesu; skalowanie wymaga uwzględnienia tego ograniczenia. |
| Minimalizacja danych | Maskowanie bezpośrednich identyfikatorów przed analizą, brak zapisu obrazów, pseudonimizacja sesji Discorda. | Maskowanie nie obejmuje każdej możliwej postaci danych osobowych; URL pozostają możliwe do pobrania. |
| Usuwanie sesji i retencja | Usunięcie sesji z powiązanymi zapisami; skonfigurowany okres przechowywania audytu. | Automatyczne czyszczenie audytu odbywa się przy starcie API, nie cyklicznie. |
| Prywatność biernego sprawdzania wtyczki | Tryb `auto` korzysta z lokalnego korpusu, nie pobiera URL, nie używa live-search ani LLM, nie tworzy spraw i zapisuje skrót zamiast tekstu. | Dotyczy biernego trybu, nie ręcznie zleconej analizy. |
| Obserwowalność | Czasy etapów, modele, błędy, abstynencje i szacunkowy koszt odpowiedzi. | Koszt jest estymatą, nie pomiarem rzeczywistego CPU ani pełnym rachunkiem dostawców. |
| Przejrzysta podstawa oceny | Cytaty pochodzą z materiałów, a werdykty z reguł nad dowodami. Domena lub popularność nie przesądzają oceny. | Semantyczna poprawność cytowań wymaga niezależnego pomiaru. |
| Jawne zależności zewnętrzne | Lokalnie uruchamiane modele, opis dostawców i przepływów danych, komunikowanie nieaktywnych lub niedostępnych integracji. | Opcjonalny LLM ma ograniczoną walidację wyjaśnień; domyślna ścieżka działa bez niego. |

Szczegóły: [ryzyka](RISKS.md), [model danych](DATA_MODEL.md), [koszty i przetwarzanie](COSTS.md).

## 4. Analityk i zamknięta pętla informacji

Nierozstrzygnięte zgłoszenie może automatycznie utworzyć sprawę w panelu analityka. Podobne pytania są grupowane w jedną sprawę, a powtórzenia zwiększają licznik. Sprawy wysokiego ryzyka i wielokrotne zgłoszenia mogą otrzymać wyższy priorytet.

Analityk ma listę spraw, status, notatkę, statystyki, zdarzenia bezpieczeństwa i eksport CSV/JSON. System informuje o dodaniu sprawy dopiero po udanym zapisie — nie przedstawia samej rekomendacji jako faktycznego przekazania.

**Mamy również opcjonalne alerty Discorda.** Bot sprawdza sprawy priorytetowe i może powiadamiać wskazany prywatny kanał moderatorów. Zapisuje potwierdzenia doręczenia i ponawia nieudane próby. Funkcja wymaga konfiguracji bota, tokenu moderatora i kanału docelowego; testy transportu nie zastępują próby doręczenia na wdrożeniu.

**Gdzie to zobaczyć:** `/moderator`. Szczegóły: [Discord i alerty](DISCORD.md), [model danych](DATA_MODEL.md).

## 5. Funkcje premiowane

| Funkcja premiowana | Co posiadamy | Stan |
|---|---|---|
| Łańcuch dowodowy i porównywanie źródeł | Powiązanie twierdzenia z fragmentem i publikacją; role dowodów oraz konflikty. | Działa |
| Otwarty i wymienny katalog | Rejestr JSON, zasady kwalifikacji, aktualizacji i wykluczania, publiczny katalog i panel. | Działa |
| Wymienne kanały, modele i źródła | Wspólny silnik, adaptery kanałów, konfigurowalne modele i własne konektory źródeł. | Działa |
| Dopasowanie do zweryfikowanych informacji | Dopasowanie treści do wcześniejszych ocen i porównanie tożsamości materiału z URL. | Działa |
| Neutralne ostrzeżenie o źródle | Oddzielny komunikat z publicznym odnośnikiem, bez automatycznego werdyktu o treści. | Działa; aktualność listy wymaga utrzymania |
| Eksport danych | CSV i JSON dostępne dla moderatora. | Działa; brak OpenCTI/DISARM |
| Zamknięta pętla informacji | Sprawy analityka i deduplikacja podobnych zgłoszeń. | Działa |
| Audyt i samodzielny hosting | Docker, lokalne modele, jawne źródła, konfiguracja i opis zależności. | Dostępne |
| OCR zrzutów ekranu | Lokalny odczyt tekstu, ostrzeżenie o błędach i ograniczonej wiarygodności daty z obrazu. | Częściowo; scenariusz F1 nie przechodzi w całości |
| Wielojęzyczne wyszukiwanie | Korpus zawiera materiały angielskie, a NLI jest wielojęzyczne. | Częściowo; brak niezależnej walidacji wyszukiwania między językami |
| Dźwięk, reverse image search i kontrolowana archiwizacja | Nie są zaimplementowane jako kompletne funkcje. | Brak; nie są obowiązkowe dla podstawowego MVP |

Dodatkowo mamy **wtyczkę przeglądarkową**: ręczny wybór fragmentu do analizy, oznaczanie podobieństwa do sprawdzonych twierdzeń oraz linki do ocen źródłowych. Oznaczenie dopasowania nie jest przedstawiane jako pełna weryfikacja dowolnej treści.

## 6. Potwierdzenie w testach

Ostatnia weryfikacja po uporządkowaniu backendu:

| Obszar | Wynik |
|---|---|
| Testy backendu | 287 zaliczonych, 4 pominięte — 291 łącznie |
| Testy Discorda z kontrolowanym transportem | 14/14 |
| Warianty scenariuszy organizatorów A–J | 15/16; pozostaje F1 dotyczący OCR |
| Kontrakt HTTP po refaktoryzacji | OpenAPI bez zmian |
| Porównanie scenariuszy przed i po refaktoryzacji | Te same statusy, werdykty, reguły, krótkie odpowiedzi i główne dowody |

Ostatni pomiar na trzech istniejących zbiorach:

| Miernik | Dev — 38 przypadków | Heldout — 57 | Blind2 — 50 | Cel konkursowy |
|---|---:|---:|---:|---:|
| Macro-F1 | 1,000 | 0,960 | 0,912 | ≥ 0,75 |
| Abstynencja w przypadkach braku dowodów | 100% | 100% | 100% | ≥ 80% |
| Odporność na testowane próby injection | 100% | 100% | 100% | ≥ 90% |
| Spójność WWW i adaptera drugiego kanału | 100% | 100% | 100% | 100% próby |
| Mediana czasu bez live-search | 324 ms | 188 ms | 202 ms | ≤ 30 s |

**Jak interpretować wyniki:** te zbiory były używane podczas rozwoju, więc nie są obecnie niezależnym testem ślepym. Automatyczne pokrycie cytowaniami wynosiło 100%, ale jest wskaźnikiem pomocniczym i nie potwierdza wymaganego progu 85% semantycznej poprawności cytowania. Pomiary czasu nie obejmują rozruchu modeli ani działania publicznego hostingu. W zbiorze Dev jedno wejście z rzeczywistym URL zakończyło się błędem technicznym w ograniczonym środowisku.

Dowody: [weryfikacja backendu](../eval/backend_refactor_2026-11-22/verification.json), [scenariusze A–J](../eval/backend_refactor_2026-11-22/organizers-results.md), [pomiar Dev](../eval/audit_2026-11-22/dev/results.json), [Heldout](../eval/audit_2026-11-22/heldout/results.json), [Blind2](../eval/audit_2026-11-22/blind2/results.json).

## 7. Materiały i gotowość zgłoszenia

Posiadamy [instrukcję uruchomienia](../README.md), [dokumentację architektury](ARCHITECTURE.md), [opis źródeł](SOURCES.md), [ryzyk](RISKS.md), [kosztów](COSTS.md) i [wdrożenia](DEPLOYMENT.md), a także [przewodnik backendu](backend/README.md).

Są również [prezentacja PDF](../presentation/prawdowid-prezentacja.pdf) licząca 11 slajdów oraz [film demonstracyjny](../video/out/prawdowid-demo.mp4) trwający około 1 min 44 s. Mieszczą się w limitach 12 slajdów i 3 minut. Prezentacja wymaga uaktualnienia wyniku 16/16 do potwierdzonego 15/16 oraz wyraźnego omówienia ryzyk i dalszych kroków.

Przed zgłoszeniem pozostaje potwierdzić nazwę zespołu i opis do 4000 znaków, dostępność linków dla jury oraz działanie instalacji na docelowym środowisku.

## 8. Co pozostaje do domknięcia

Najważniejsze prace dotyczące pełnego potwierdzenia wymagań:

1. Niezależna ocena poprawności cytatów i pomiar zgodny z definicją pokrycia każdej tezy dowodem.
2. Cykliczne egzekwowanie retencji podczas ciągłej pracy serwera.
3. Obsługa brakujących dat publikacji bez ich zgadywania.
4. Poprawa OCR F1 i próba na kontenerze z polskimi danymi Tesseracta.
5. Aktualizacja prezentacji i starszych opisów zgodności do bieżącego stanu.
6. Przegląd zasad przechowywania treści, w tym dawnych pełnych kopii w historii Git.
7. Próba na docelowym wdrożeniu: dostęp jury, kanały, alerty, błędy i usunięcie sesji.

**Wniosek:** mamy działający prototyp realizujący podstawowy proces wymagany przez MSZ, rozbudowany katalog źródeł, kilka kanałów i pętlę analityka. Pozostałe luki dotyczą przede wszystkim niezależnego potwierdzenia jakości, części zasad przechowywania danych, OCR i kompletności zgłoszenia.
