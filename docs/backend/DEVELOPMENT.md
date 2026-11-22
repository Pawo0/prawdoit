# Rozwój i testowanie backendu

Zmiana backendu może wpłynąć na cytat, werdykt, prywatność albo format odpowiedzi kilku kanałów naraz. Dlatego sprawdzamy osobno styl kodu, kontrakt HTTP, testy bez modeli i pełne scenariusze z inferencją.

Poniższe polecenia wykonuje się z katalogu głównego `prawowid/`, chyba że podano inaczej. Korzystają z istniejącego środowiska `backend/.venv`; jego utworzenie i zależności runtime opisuje [README projektu](../../README.md).

## Narzędzia i styl

```bash
uv pip install --python backend/.venv/bin/python -r backend/requirements-dev.txt
backend/.venv/bin/python -m black --config backend/pyproject.toml --check backend/prawdowid
backend/.venv/bin/python -m pyflakes backend/prawdowid
```

Do sformatowania zamiast kontroli usuń `--check`. Black 25.1.0 i Pyflakes 3.4.0 są przypięte jako narzędzia programisty. Nie są dodawane do zależności obrazu produkcyjnego. Formatter używa szerokości 100 znaków i składni Python 3.12.

W kodzie stosujemy nazwy angielskie, a w przewodniku wyjaśnienia polskie. Nazwa funkcji powinna mówić, co robi etap. Komentarz ma tłumaczyć powód reguły, ograniczenie lub kontrakt, zamiast powtarzać instrukcję. Złożone operacje i obsługa wyjątków nie powinny mieścić się w kilku instrukcjach rozdzielonych średnikami w jednej linii.

Zachowuj nazwy publicznych funkcji, pól modeli, parametrów używanych przez klientów, identyfikatorów dokumentów i kodów reguł, jeśli zmiana nie dotyczy świadomie ich kontraktu. Wewnętrzne skróty odziedziczone przez testy mogą pozostać; opis w mapie modułów wskazuje ich rolę.

## Szybkie testy bez rzeczywistych modeli

```bash
PRAWDOWID_SKIP_ORGANIZERS=1 PRAWDOWID_LIVE_SEARCH=0 \
  backend/.venv/bin/python -m unittest discover -s backend/tests -q

backend/.venv/bin/python eval/test_discord.py
```

`backend/tests/_testenv.py` ustawia tymczasowy runtime i wyłącza harmonogram przed importem kodu. Nie uruchamiaj testów z runtime wskazującym na dane demonstracji lub użytkowników. Część testów wymaga możliwości uruchomienia serwera na localhost. Błąd wiązania gniazda w sandboxie nie jest dowodem błędu aplikacji.

Ważne grupy regresji:

- `test_catalog_and_export.py`: publiczny katalog i autoryzowany eksport CSV/JSON po wydzieleniu warstw.
- `test_main_evidence.py`, `test_finding_quote.py`, `test_fragment_windows.py`: wybór i zgodność cytatu.
- `test_agreement_guard.py`, `test_subject_gate.py`, `test_match_consistency.py`: podobieństwo nie może oznaczać tej samej tezy bez kontroli szczegółów.
- `test_archival_material.py`, `test_definitional_measures.py`, `test_would_settle.py`: czas materiału, definicje liczb i podpowiedź potrzebnego dowodu.
- `test_pii_masking.py`, `test_auto_mode.py`: maskowanie, minimalizacja i bierny tryb wtyczki.
- `test_url_injection.py`, `test_injection_patterns.py`, `test_panel_tokens.py`, `test_rate_limit.py`: granice bezpieczeństwa.
- `test_google_factcheck.py`, `test_live_persist.py`, `test_unavailable_notices.py`: dostawcy, trwały zapis i jawne awarie.
- `test_source_scope.py`, `test_euvsdisinfo_mcp.py`: kwalifikacja i konektory.
- `eval/test_discord.py`: transport, usuwanie sesji i alerty z atrapami; test nie wysyła prawdziwych wiadomości.

Pełną listę znajdziesz w [`backend/tests/`](../../backend/tests/). Testy powinny obejmować zachowanie, które ma pozostać prawdziwe po kolejnej zmianie implementacji.

## Scenariusze z rzeczywistymi modelami

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  backend/.venv/bin/python eval/organizers/run_organizers.py --out /tmp/prawdowid-organizers
```

Tryb offline wymaga wcześniej pobranych modeli. Domyślny runner używa tymczasowej bazy i kopii cache indeksu, wyłącza rzeczywistych dostawców live-search i udostępnia kontrolowane strony przez localhost. Nie nadpisuj historycznego raportu, jeśli służy jako porównanie; wskaż `--out`.

Runner zwraca kod 1, gdy jakikolwiek wariant nie przejdzie. Wersja przed refaktoryzacją miała 15/16 zaliczonych wariantów na lokalnym środowisku. Pozostały F1 dotyczył OCR i metadanych zrzutu. Odtworzenie tego samego błędu oznacza brak nowej regresji, ale nie oznacza zaliczenia całego zestawu. Nie rozluźniaj testu tylko po to, aby refaktoryzacja była zielona.

Do oceny regresji porównuj nie tylko łączną liczbę, lecz także werdykty, źródła, fragmenty, reguły i wynik każdej kontroli. UUID, ID spraw, czas odpowiedzi i metadane środowiska zmieniają się między przebiegami.

## Ewaluacja jakości

`eval/run_eval.py` mierzy wyniki na `cases.jsonl`, `cases_heldout.jsonl` i `cases_blind2.jsonl`. Uruchomienia zapisują audyt i mogą budować cache. Dla pomiaru użyj osobnego runtime oraz kopii `data/index`:

```bash
PRAWDOWID_RUNTIME_DIR=/tmp/prawdowid-eval-runtime \
PRAWDOWID_INDEX_DIR=/tmp/prawdowid-eval-index \
PRAWDOWID_SCHEDULER=0 PRAWDOWID_LIVE_SEARCH=0 \
  backend/.venv/bin/python eval/run_eval.py \
  --cases eval/cases.jsonl --out /tmp/prawdowid-eval-results
```

Przed uruchomieniem skopiuj `data/index/` do wybranego katalogu indeksu, jeśli chcesz uniknąć ponownego liczenia wszystkich embeddingów. Wskaż świeży runtime przy każdym niezależnym pomiarze.

Obecne zbiory służyły do rozwoju systemu. Wynik po poprawkach nie jest nową oceną ślepą. Dawny licznik obecności cytowań jest dostępny jako `citation_presence_proxy`; rzeczywiste pokrycie i poprawność wymagają adnotacji. [Protokół audytu](../../eval/citations/README.md) opisuje zamrożenie pełnych odpowiedzi (`--citation-audit`), pakiety recenzenckie i pomiar każdej atomowej tezy. [Aktualny raport](../CITATION_AUDIT.md) zawiera pierwszą ocenę AI i ograniczenia niezależności. Sama refaktoryzacja powinna zachować wyniki przy tych samych danych, modelach i ustawieniach.

## Sprawdzenie kontraktu HTTP

Nie uruchamiaj startupu modeli, jeśli chcesz tylko odczytać OpenAPI. Ustaw osobny `PRAWDOWID_RUNTIME_DIR` i `PRAWDOWID_SCHEDULER=0`, a następnie wywołaj `app.openapi()` po imporcie `prawdowid.api`.

Przy zmianie publicznych modeli lub ścieżek porównaj specyfikację przed i po. Dodanie docstringa do endpointu też może zmienić jego opis w OpenAPI. Podczas tej refaktoryzacji zachowano specyfikację bez zmian.

## Bezpieczeństwo zmian

Kontekst sprawdzenia jest lokalny, lecz indeks, modele, pule zadań i SQLite żyją w procesie. Nie przenoś inicjalizacji tych zasobów do nowej warstwy bez sprawdzenia kolejności importów i testów współbieżności. Nie twórz nowych globalnych kolejek lub połączeń w samym adapterze kanału.

Szczególnie istotne są kolejność maskowania i wyszukiwania, oddzielenie błędów od ocen oraz ograniczenia `mode="auto"`. Wyłączenie sieci, spraw moderatora lub trwałego tekstu w tym trybie jest kontraktem prywatności.

## Znane ograniczenia zachowane podczas refaktoryzacji

- Czyszczenie audytu zgodnie z retencją odbywa się przy starcie API, nie cyklicznie podczas ciągłej pracy.
- Lokalny OCR zależy od programu Tesseract i danych językowych. Kod dopuszcza angielski, gdy polski nie jest dostępny; może to pogorszyć polskie znaki i daty. Docker instaluje pakiet polski.
- Działające zadania są pamięcią procesu, a limity nie są globalnym limitem wielu instancji.
- Indeks może zawierać pliki korpusu bez konfiguracji rejestru.
- Opcjonalne uproszczenie przez LLM nie ma pełnej walidacji semantycznej nowych faktów.
- Wyszukiwanie na żywo i aktualizacja korpusu mogą zmienić wynik między dwoma pozornie identycznymi zapytaniami.

Zmiana tych zachowań wymaga osobnego celu funkcjonalnego i regresji, nie powinna być ukryta w porządkowaniu stylu kodu.

## Wyniki weryfikacji refaktoryzacji

Przebieg z 22.11.2026 względem bazowego `ffad79d`:

- Testy backendu: 291 przypadków, 287 zaliczonych i 4 pominięte.
- Testy Discorda z atrapami: 14 zaliczonych.
- Scenariusze organizatorów: 15/16; ten sam niezaliczony F1 co przed zmianą. Wszystkie wyniki poszczególnych kontroli są zgodne z bazą.
- Statusy, werdykty, reguły, kody przyczyn, krótkie odpowiedzi i główne dowody są identyczne dla wszystkich przebiegów scenariuszy.
- Specyfikacja OpenAPI jest identyczna. Black i Pyflakes przechodzą dla wszystkich modułów produkcyjnych.
- W 38 z 44 pierwotnych modułów drzewo składniowe po pominięciu docstringów pozostało identyczne. Zmiany pozostałych to wydzielenie etapów i katalogu, czytelniejsze zmienne, granica eksportu oraz usunięcie nieużywanych importów.

[Podsumowanie kontroli](../../eval/backend_refactor_2026-11-22/verification.json) i [pełny raport scenariuszy](../../eval/backend_refactor_2026-11-22/organizers-results.md) są zapisane w repozytorium. Zmiana czasów i identyfikatorów między przebiegami jest oczekiwana.
