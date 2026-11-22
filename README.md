# Prawdowid

Narzędzie do sprawdzania informacji na podstawie wiarygodnych źródeł. Prototyp na wyzwanie MSZ „PRAWDOWID”
(HackNation 2026).

Użytkownik wysyła tekst, link albo zrzut ekranu. Prawdowid wyodrębnia twierdzenia, szuka ich w źródłach urzędowych
i u fact-checkerów, po czym odpowiada jedną z pięciu klas:

- potwierdzone,
- fałszywe,
- wprowadzające w błąd,
- brak wystarczających dowodów,
- nie podlega weryfikacji (opinie, prognozy).

Każdej ocenie towarzyszy dosłowny cytat ze źródła (tytuł, wydawca, data, link), lista przesłanek i informacja, czego nie
udało się ustalić. Prawdowid nie rozstrzyga, co jest prawdą. Pokazuje, co mówią źródła, a gdy nie mówią nic
rozstrzygającego, wstrzymuje się od odpowiedzi.

## Metoda

Sprawdzenie przebiega w stałej kolejności:

1. **Wejście.** Tekst jest oczyszczany z danych osobowych. Link w wiadomości jest pobierany (z ochroną przed SSRF),
   zrzut ekranu odczytywany lokalnie przez OCR. Treść pobrana z sieci jest skanowana pod kątem ukrytych instrukcji
   (prompt injection); wykryta próba jest ignorowana i zapisywana jako zdarzenie.
2. **Twierdzenia.** Z wiadomości wybierane są do trzech twierdzeń. Opinie i prognozy są oznaczane i nie dostają
   werdyktu faktograficznego.
3. **Wyszukiwanie.** Hybrydowe: BM25 i wektory (`mmlw-retrieval-e5-small`) po lokalnym korpusie oraz osobny indeks
   twierdzeń już ocenionych przez fact-checkerów. Gdy korpus nie ma dowodu, system może przeszukać na żywo wyłącznie
   zaufane serwisy z rejestru i Google Fact Check API. Awaria wyszukiwania kończy się komunikatem, nigdy werdyktem.
4. **Ocena relacji.** Model NLI (mDeBERTa) ocenia, czy fragment popiera tezę, przeczy jej, czy jest neutralny.
   Liczby, daty i definicje wskaźników są porównywane osobno, bo NLI jest w nich zawodne. Dodatkowe sprawdzenia
   pilnują, by dowód dotyczył tej samej osoby, kwoty i okresu, a nie tylko podobnego tematu.
   Sama ocena podobnej wypowiedzi przez fact-checkera nie wystarcza: wybrany cytat musi zawierać ustalenie (nie
   pytanie ani relację z pogłoski) i obejmować całą tezę. Cytat, który tego nie spełnia, nie może być podstawą
   werdyktu.
5. **Decyzja.** Werdykt wynika z uporządkowanych reguł R1–R6 (`engine._decide()`), nie z modelu językowego. Sprzeczne
   dowody prowadzą do ujawnienia konfliktu i wstrzymania się. Podstawą rozstrzygnięcia mogą być tylko źródła urzędowe
   i fact-checkingowe; media i bazy incydentów służą jako kontekst.
6. **Odpowiedź.** Krótka odpowiedź po polsku („Nie. Demagog ocenił…”), ta sama w każdym kanale. Siła podstawy
   wynika z typu źródła, zgodności fragmentu, wieku materiału, konfliktów i liczby niezależnych wydawców. Opcjonalny
   LLM może jedynie uprościć gotowe wyjaśnienie; nie wolno mu dodać liczb ani linków.
7. **Audyt.** Każde sprawdzenie zostaje zapisane (zamaskowane wejście, źródła, reguły, wynik). Podobne zgłoszenia
   trafiają do jednej sprawy w panelu analityka.

Szczegóły: [silnik weryfikacji](docs/backend/ENGINE.md), [przebieg sprawdzenia](docs/backend/REQUEST_FLOW.md),
[metodologia dla użytkownika](web/metodologia.html).

## Stan prac

- Pełna ścieżka działa bez udziału twórców: zgłoszenie, analiza, odpowiedź z dowodami, zapis w audycie.
- Kanały: strona WWW (z PWA i udostępnianiem z Androida), wtyczka przeglądarki, bot Discord, serwer MCP.
- Rejestr kilkudziesięciu źródeł (fact-checkerzy i serwisy urzędowe), pobieranych według harmonogramu, z panelem
  administracyjnym. Indeks odświeża się bez restartu.
- Na zbiorach testowych, w tym przygotowanych bez wglądu w kod, system spełnia cele MVP z sekcji 6 wyzwania dla
  trafności werdyktu, wstrzymywania się przy braku dowodów, odporności na prompt injection i czasu odpowiedzi.
  Pozostałe błędy to prawie wyłącznie „brak dowodów” zamiast werdyktu, czyli błąd bezpieczny. System nie potwierdził
  żadnej fałszywej tezy ani nie zaprzeczył prawdziwej. Instrukcje wstrzyknięte w treść stron nie zmieniły żadnego werdyktu.
- Cel pokrycia cytowań nie jest potwierdzony. Ręczny audyt wykazał, że nie każda teza w odpowiedzi miała oparcie
  w cytacie. Kontrola cytatu powstała w odpowiedzi na ten audyt: odrzuca słabo uzasadnione odpowiedzi kosztem
  większej liczby wstrzymań. Ponownej recenzji cytatów jeszcze nie wykonano. Zob. [audyt cytatów](docs/CITATION_AUDIT.md)
  i [walidację poprawki](eval/citation_grounding_2026-11-22/README.md).
- Odpowiedź z lokalnego korpusu zajmuje zwykle poniżej sekundy na CPU. Wyszukiwanie na żywo ma budżet 15 s.

Wyniki na naszym zbiorze testowym: 145 przypadków ze scenariuszy A–J z sekcji 6 wyzwania, lokalny korpus,
bez wyszukiwania na żywo, ze ścisłą kontrolą cytatów.

| Miernik | Wynik | Cel MVP |
|---|---|---|
| Trafność werdyktu (macro-F1) | 0,799 | ≥ 0,75 |
| Wstrzymanie się przy braku dowodów | 100% | ≥ 80% |
| Odporność na prompt injection | 100% | ≥ 90% |
| Czas odpowiedzi (mediana / p95) | 0,14 s / 0,55 s | ≤ 30 s |

Dane do odtworzenia: [`eval/citation_grounding_2026-11-22/`](eval/citation_grounding_2026-11-22/README.md). Ograniczenia:
[ryzyka](docs/RISKS.md), [zgodność z wymaganiami](docs/COMPLIANCE.md).

## Uruchomienie

### Docker

```bash
cp .env.example .env    # ustaw PRAWDOWID_MODERATOR_TOKEN i PRAWDOWID_ADMIN_TOKEN (openssl rand -hex 32)
docker compose up -d --build
```

Strona: http://localhost:8000. Pierwszy start pobiera modele. Hosting, HTTPS i lokalny LLM:
[DEPLOYMENT](docs/DEPLOYMENT.md).

### Lokalnie

```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
PRAWDOWID_DEV_MODE=1 uvicorn prawdowid.api:app --port 8000
```

W trybie `PRAWDOWID_DEV_MODE=1` panele `/moderator` i `/admin` przyjmują tokeny `demo-moderator` i `demo-admin`.
Poza nim wymagają tokenów z `.env`, a bez nich są zamknięte. Kontener nie wystartuje w trybie deweloperskim.

OCR wymaga zainstalowanego `tesseract`.

### Konfiguracja

Wszystkie zmienne są opisane w [`.env.example`](.env.example). Najważniejsze:

| Zmienna | Znaczenie |
|---|---|
| `PRAWDOWID_LIVE_SEARCH` | `0` wyłącza wyszukiwanie na żywo (praca offline, powtarzalna ewaluacja) |
| `PRAWDOWID_SCHEDULER` | `0` wyłącza harmonogram pobierania źródeł |
| `PRAWDOWID_GOOGLE_FACTCHECK_KEY`, `PRAWDOWID_SEARXNG_URL`, `PRAWDOWID_BRAVE_KEY` | dostawcy wyszukiwania na żywo; bez klucza dostawca jest nieaktywny |
| `PRAWDOWID_LLM_BASE_URL`, `_MODEL`, `_API_KEY` | opcjonalny LLM (API zgodne z OpenAI), tylko do upraszczania języka |
| `PRAWDOWID_DISCORD_TOKEN` | bot Discord |

Sekrety trzymamy wyłącznie w zmiennych środowiskowych.

### Kanały

- **Wtyczka:** `chrome://extensions` → tryb dewelopera → „Załaduj rozpakowane” → `extension/`. W Firefoksie:
  `about:debugging` → „Załaduj tymczasowy dodatek” → `extension/manifest.json`. Strona testowa:
  http://localhost:8000/demo/feed.html.
- **Discord:** ustaw `PRAWDOWID_DISCORD_TOKEN`; bot startuje razem z backendem. Zob. [DISCORD](docs/DISCORD.md).
- **MCP:** `bots/mcp_server.py` udostępnia narzędzia tylko do odczytu (`sprawdz`, `katalog_zrodel`, `kurs_nbp`,
  `akt_prawny`, `szukaj_aktow`).

## Ewaluacja

```bash
PRAWDOWID_LIVE_SEARCH=0 backend/.venv/bin/python eval/run_eval.py [--cases eval/cases_heldout.jsonl] [--out DIR]
backend/.venv/bin/python eval/organizers/run_organizers.py
```

Pierwsze polecenie zapisuje `results.md` i `results.json`. Zbiory: `eval/cases.jsonl` (deweloperski),
`cases_heldout.jsonl` i `cases_blind2.jsonl` (przygotowane niezależnie, później użyte do strojenia, więc nie są już
testami ślepymi). Testy jednostkowe: `backend/tests/`, opis w [DEVELOPMENT](docs/backend/DEVELOPMENT.md).

## Struktura

| Katalog | Zawartość |
|---|---|
| `backend/prawdowid/` | API (FastAPI), silnik weryfikacji, bezpieczeństwo, audyt, adaptery kanałów |
| `web/` | strona WWW bez frameworka: sprawdzanie, wynik, katalog źródeł, metodologia, panele |
| `extension/` | wtyczka MV3 (Chrome, Edge, Firefox na Androida) |
| `bots/` | bot Discord i serwer MCP |
| `data/sources/` | rejestr źródeł, jeden plik JSON na źródło |
| `data/corpus/` | korpus w JSONL |
| `ingest/` | skrypty pobierające źródła do korpusu |
| `eval/` | zbiory testowe, skrypty i zapisane wyniki |
| `docs/` | architektura, źródła i licencje, ryzyka, koszty, wdrożenie |
| `research/` | notatki z researchu |

## Dokumentacja

[Architektura](docs/ARCHITECTURE.md) · [backend](docs/backend/README.md) · [moduły](docs/backend/MODULES.md) ·
[źródła i licencje](docs/SOURCES.md) · [rejestr źródeł](docs/SOURCE_REGISTRY.md) · [model danych](docs/DATA_MODEL.md) ·
[funkcjonalności](docs/FUNKCJONALNOSCI.md) · [zgodność](docs/COMPLIANCE.md) · [ryzyka](docs/RISKS.md) ·
[koszty](docs/COSTS.md) · [scenariusz demo](docs/DEMO.md)
