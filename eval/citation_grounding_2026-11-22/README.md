# Walidacja kontroli cytatów V5 — reguły 1.1

Mechanizm produkcyjny zmieniono po [audycie bazowym](../../docs/CITATION_AUDIT.md). Samo dopasowanie do sprawdzonej wypowiedzi nie wystarcza do werdyktu. Wybrany cytat musi przejść osobną kontrolę ustalenia, relacji i zakresu. [Opis implementacji](../../docs/backend/ENGINE.md#kontrola-cytatu-v5-reguły-11).

## Co sprawdzono

- 16 nowych testów bez modeli, na wymyślonych twierdzeniach i publikacjach: pytania, powtórzenie pogłoski, liczby i jednostki, inny okres, nieustalony kraj, surowe sumy zamiast wskaźników, brak wsparcia dla części zdania, neutralne NLI, podmieniony cytat, dobór lepszej alternatywy, ograniczenie liczby porównań i odrzucenie źródła także z wyboru głównego dowodu.
- Backend: **302 testy uruchomione, 4 pominięte, bez błędów** z `PRAWDOWID_SKIP_ORGANIZERS=1` (298 zaliczonych). Test referencyjny ma osobny przebieg poniżej.
- Dotychczasowy protokół niezależnego od silnika pomiaru: 10 testów zaliczonych.
- Pełny przebieg 145 dotychczasowych przypadków z lokalnym korpusem, bez live-search i opcjonalnego LLM. Świeża baza danych, kopia indeksu, modele z lokalnego cache.
- Scenariusze referencyjne: **15/16 zaliczonych**. F1-zrzut-ekranu pozostaje niezaliczony: OCR odczytuje obraz, ale nagłówek użytkownika/data tworzy dodatkową tezę, a oczekiwane frazy OCR nie pasują do odczytu. To nie brak obsługi OCR. Według użytkownika osobna poprawka jest w pracy u kolegi; nie oznaczamy jej jako dostarczonej w tym zestawie zmian.

## Wynik i koszt ostrożniejszej oceny

Na tych samych 145 przypadkach macro-F1 zmieniło się z **0,954 do 0,799**, accuracy z 0,945 do 0,772. Liczba wyników `brak_dowodow` wzrosła z **40 do 69**. Większość utraconych rozstrzygnięć to abstencje, ale nie wolno utożsamiać wszystkich zmian klasy z poprawą. Dokładne przypadki i etykiety są w wynikach obu przebiegów.

Nowy wynik nadal przekracza cel macro-F1 0,75 w tym zbiorze rozwojowym. To **regresja zdolności do rozstrzygania**, jawny koszt odrzucania słabo uzasadnionych odpowiedzi. Potrzebne są lepsze fragmenty lub bardziej kompletne źródła, aby odzyskiwać rozstrzygnięcia bez przywracania nieuzasadnionych cytatów. Nie obniżano progów NLI w celu odzyskania wyniku.

Mediana wynosiła 138 ms, p95 548 ms w tym środowisku. To przebieg lokalny, nie pomiar publicznego hostingu. Zbiory były wcześniej używane do rozwoju systemu; nie są nowym testem ślepym.

## Przykłady z parowanej próby

- **P003, szczepienia przeciw grypie:** zamiast pytania jako uzasadnienia cytowany jest wniosek: brak eradykacji choroby nie oznacza nieskuteczności szczepień.
- **P023, przestępczość:** cytat porównuje wskaźnik na 1000 mieszkańców między populacjami. Same sumy przestępstw nie przechodzą kontroli wskaźnika.
- **P021 i P022, wiatraki i fotografia:** materiał ograniczony do opisu postu nie rozstrzyga już tezy; wynik to abstencja.
- **P024, wybory:** brak uzasadnienia dokładnego procentu nie pozwala potwierdzić całego zdania na podstawie samego ustalenia zwycięzcy.
- **P027, uchodźcy:** odrzucone fragmenty o niezgodnym zakresie nie tworzą już komunikatu o konflikcie dowodów.

[Parowane odpowiedzi](paired_outputs.json) zachowują te same identyfikatory 30 przypadków z audytu bazowego, nowe cytaty, werdykty i reguły. To materiał do przeglądu, **nie nowy wynik semantycznego audytu**. NLI i heurystyki nadal mogą się mylić; m.in. metafory, liczby słowne, szersze implikacje i deiktyczne określenia miejsca wymagają oceny w kontekście. Nie deklarujemy, że V5 dowodzi każdego zdania ani że nowe progi 95%/85% są osiągnięte.

## Odtworzenie

- [Wyniki pełnego przebiegu](capture/results.md), [JSON](capture/results.json), [dokładne wejście](capture/cases.jsonl).
- [Pełne odpowiedzi](capture/responses.jsonl), [zamrożone źródła](capture/citation_sources.jsonl), [skróty danych](capture/citation_capture.json).
- [Scenariusze referencyjne](organizers/results.md) i [szczegóły testów](organizers/results.json).
- [Ustawienia i skróty kodu](provenance.json). Zapis wykonano dla niezacommitowanych zmian względem `859842e`.

```bash
PRAWDOWID_SKIP_ORGANIZERS=1 backend/.venv/bin/python -m unittest discover -s backend/tests -q
backend/.venv/bin/python backend/tests/test_evidence_grounding.py
python3 eval/citations/test_protocol.py
```

Do powtórzenia kolekcji użyj świeżego runtime, kopii `data/index`, ustawień zapisanych w `provenance.json` i `eval/run_eval.py --cases eval/citation_grounding_2026-11-22/capture/cases.jsonl --citation-audit --out /tmp/citation-grounding-capture`, zgodnie z [instrukcją](../../eval/citations/README.md). Do potwierdzenia poprawności cytowania po zmianie potrzebna jest odrębna recenzja nowych odpowiedzi; własny wynik V5 nie zastępuje adnotacji.
