# Prawdowid — szybka i łatwa weryfikacja informacji oparta na wiarygodnych źródłach

Prototyp na wyzwanie MSZ „PRAWDOWID” (HackNation 2026). Obywatel wkleja tekst, link lub przesyła wiadomość
(czat / WhatsApp / Discord / wtyczka przeglądarki) i w kilka sekund dostaje: **werdykt w jednej z 5 klas**,
**dosłowne fragmenty źródeł** (tytuł, wydawca, data, link), **jawne przesłanki** siły odpowiedzi, informację **czego nie
udało się ustalić** — albo uczciwe **wstrzymanie się od rozstrzygnięcia**. Prawdowid nie jest „sędzią prawdy”:
pokazuje, co mówią źródła.

## Co jest w repozytorium
| Katalog | Zawartość |
|---|---|
| `backend/prawdowid/` | API (FastAPI), silnik weryfikacji (wyszukiwanie hybrydowe, NLI, reguły R1–R6), bezpieczeństwo, audyt, sprawy moderatora, adaptery kanałów (WhatsApp, Messenger, demo) |
| `web/` | Strona WWW (bez frameworka): sprawdzanie, wynik z dowodami, czat demo, katalog źródeł, metodologia, panel analityka, PWA (udostępnianie z aplikacji na Androidzie) |
| `extension/` | Wtyczka MV3 (Chrome/Edge/Vivaldi + Firefox Android): lupka „Sprawdź” (wybór fragmentu → pełne sprawdzenie) oraz oznaczanie treści zbieżnych z twierdzeniami ocenionymi przez fact-checkerów — zawsze ze źródłem, oceną, datą i linkiem (zasłona tylko jako opcja) |
| `bots/discord_bot.py` | Bot Discord (`/sprawdz`, wzmianka, DM, menu kontekstowe wiadomości) |
| `bots/mcp_server.py` | Serwer MCP (tylko odczyt): `sprawdz`, `katalog_zrodel`, `kurs_nbp` (na żywo), `akt_prawny` / `szukaj_aktow` (Sejm ELI na żywo) |
| `data/sources/` | **Rejestr źródeł** — jeden plik JSON na źródło (licencja, kwalifikacja, harmonogram); edycja w panelu `/admin` |
| `backend/prawdowid/sources/`, `source_handlers/` | Harmonogram pobierania źródeł z rejestru + własne moduły (Odyseusz MSZ, RSO, IMGW, EUvsDisinfo MCP…) |
| `ingest/` | Skrypty pobierające źródła → jednolity JSONL (`data/corpus/`) |
| `eval/` | Zbiór testowy (scenariusze A–J), `run_eval.py` (mierniki z sekcji 6), test E2E wtyczki |
| `docs/` | Architektura, źródła i licencje, ryzyka, koszty |
| `research/` | Raporty z researchu (kanały, źródła, metodologia SPRAWDŹ/IFCN/EFCSN, modele i prior art) |

## Docker — backend i strona WWW

Skopiuj `.env.example` do `.env`, ustaw prywatne `PRAWDOWID_MODERATOR_TOKEN` i `PRAWDOWID_ADMIN_TOKEN`, następnie uruchom:

```bash
docker compose up -d --build
docker compose logs -f backend
```

Po załadowaniu modeli: http://localhost:8000. Historia i modele pozostają w wolumenach po restarcie.
Pierwszy start pobiera modele z internetu. [Instrukcja hostowania, HTTPS i trwałych danych](docs/DEPLOYMENT.md).

## Uruchomienie (≈ 10 min, CPU wystarczy)
```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
PRAWDOWID_DEV_MODE=1 uvicorn prawdowid.api:app --port 8000   # start ~10 s: repo zawiera gotowy cache embeddingów (data/index/)
```
Otwórz http://localhost:8000 · czat demo: http://localhost:8000/czat · panel analityka: http://localhost:8000/moderator
(token `demo-moderator` tylko w trybie lokalnym `PRAWDOWID_DEV_MODE=1`, inaczej `PRAWDOWID_MODERATOR_TOKEN`) ·
**panel źródeł: http://localhost:8000/admin** (token `demo-admin` tylko w trybie lokalnym, inaczej
`PRAWDOWID_ADMIN_TOKEN`; wpisz go w polu tokenu panelu — trafia do nagłówka `X-Admin-Token`). Bez ustawionego tokenu
i bez trybu lokalnego oba panele są zamknięte (API odpowiada 503); kontener nie wystartuje bez dwóch prywatnych tokenów. W panelu: dodawanie źródła z „Wykryj automatycznie”, test bez zapisu, włącz/wyłącz, „Uruchom teraz”,
historia pobrań. Opis rejestru: [SOURCE_REGISTRY](docs/SOURCE_REGISTRY.md), model danych: [DATA_MODEL](docs/DATA_MODEL.md).

## Co nowego (21.11.2026)
- **Rejestr źródeł + harmonogram** (`data/sources/*.json`, panel `/admin`): źródła urzędowe z listy organizatorów
  (Odyseusz MSZ, RCB, RSO, IMGW, CERT, PSP, Policja, GIS, PAA, urzędy morskie, MI, MON, MSWiA, KPRM, GDDKiA…),
  pobierane automatycznie co `schedule_hours`; indeks przeładowuje się bez restartu.
- **Wyszukiwanie na żywo** (`websearch.py`): gdy w bazie nie ma dowodu, wyszukiwarki samych zaufanych serwisów z rejestru
  (gov.pl, Demagog, FakeNews.pl, CheckFirst; opcjonalnie SearXNG/Brave z filtrem domen) + **Google Fact Check API** (z kluczem).
  Te same reguły co dla bazy (cytat dosłowny, NLI, R1–R6); awaria/timeout = komunikat, nigdy werdykt. Budżet ~15 s.
- **Zadania asynchroniczne** `POST /api/check/async` → `GET /api/jobs/{id}` z etapami („Szukam w bazie…”, „Przeszukuję
  zaufane strony…”) — okno oczekiwania w interfejsie.
- **Krótkie odpowiedzi** w stylu przykładów organizatorów („Nie. Demagog ocenił…”, „Tak, Demagog to sprawdził…”,
  przy wstrzymaniu: materiał pokrewny albo „co mogłoby to rozstrzygnąć”) — ten sam tekst w każdym kanale; na stronie
  wyjaśnienia ≤ 3 linki do zaufanych stron z tematu.
- **Link w wiadomości** („Czy X? Sprawdź też tę stronę: URL”): strona jest pobierana (ochrona SSRF), skanowana pod kątem
  prompt injection, a zdarzenie zapisywane; strona testowa: `/demo/injection.html`.
- **EUvsDisinfo MCP** (czeka na token organizatora): [MCP_EUVSDISINFO](docs/MCP_EUVSDISINFO.md).
- **Szacunkowy koszt odpowiedzi** w audycie (`engine.cost_estimate`) i w `/api/stats`.
- Zgodność z wymaganiami: [COMPLIANCE](docs/COMPLIANCE.md).

## Zmienne środowiskowe (wszystkie opcjonalne)
| Zmienna | Domyślnie | Do czego |
|---|---|---|
| `PRAWDOWID_ADMIN_TOKEN` | — (panel zamknięty) | token panelu źródeł `/admin`; wymagany w kontenerze |
| `PRAWDOWID_MODERATOR_TOKEN` | — (panel zamknięty) | token panelu analityka `/moderator`; wymagany w kontenerze |
| `PRAWDOWID_DEV_MODE` | `0` | `1` = tylko lokalnie: puste tokeny zastępują jawne `demo-moderator` / `demo-admin`; kontener odmawia startu z `1` |
| `PRAWDOWID_SCHEDULER` | `1` | `0` = harmonogram pobierania źródeł wyłączony (np. w testach) |
| `PRAWDOWID_LIVE_SEARCH` | `1` | `0` = bez wyszukiwania na żywo (powtarzalna ewaluacja, praca offline) |
| `PRAWDOWID_GOOGLE_FACTCHECK_KEY` | — | klucz Google Fact Check Tools API; bez klucza dostawca jest nieaktywny |
| `PRAWDOWID_SEARXNG_URL` | — | własna instancja SearXNG (JSON API) jako dodatkowa wyszukiwarka z filtrem `site:` |
| `PRAWDOWID_BRAVE_KEY` | — | klucz Brave Search API (j.w.) |
| `PRAWDOWID_FORCE_FAIL` | — | symulacja awarii do demo/testów, np. `google_factcheck,websearch` (scenariusz J) |
| `PRAWDOWID_EUVSDISINFO_TOKEN` | — | token serwera MCP EUvsDisinfo |
| `PRAWDOWID_LLM_BASE_URL` / `_MODEL` / `_API_KEY` | — | opcjonalny LLM (OpenAI-compatible) tylko do upraszczania języka |
| `PRAWDOWID_EMBED_MODEL`, `PRAWDOWID_NLI_MODEL` | mmlw-e5-small, mDeBERTa | wymiana modeli bez zmian w kodzie |
| `PRAWDOWID_WA_*`, `PRAWDOWID_FB_*`, `PRAWDOWID_DISCORD_TOKEN` | — | kanały WhatsApp / Messenger / Discord |
| `PRAWDOWID_RATE_LIMIT`, `PRAWDOWID_RETENTION_DAYS` | 120 / 30 | pełne sprawdzenia na minutę na adres klienta (osobno: `PRAWDOWID_RATE_LIMIT_QUICK` = 60 paczek wtyczki, `PRAWDOWID_RATE_LIMIT_AUTO` = 20 sprawdzeń w tle; za proxy patrz [DEPLOYMENT](docs/DEPLOYMENT.md)); retencja audytu (dni) |
| `PRAWDOWID_COST_PLN_PER_CPU_S`, `PRAWDOWID_COST_PLN_PER_1K_LLM_TOKENS` | 0,0000116 / 0 | stawki do szacunku kosztu odpowiedzi |

Sekrety tylko w zmiennych środowiskowych — nigdy w repozytorium.

**Wtyczka:** `chrome://extensions` → tryb dewelopera → „Załaduj rozpakowane” → katalog `extension/`.
Strona testowa: http://localhost:8000/demo/feed.html. Firefox (także Android): `about:debugging` → „Załaduj tymczasowy dodatek” → `extension/manifest.json`.

**Discord:** ustaw `PRAWDOWID_DISCORD_TOKEN` w `.env` — bot startuje razem z API przez `docker compose up -d --build`.
Obsługuje DM, wzmianki, `/sprawdz`, menu wiadomości i `/usun_sesje`. [Konfiguracja i testy](docs/DISCORD.md).
**WhatsApp/Messenger:** zmienne `PRAWDOWID_WA_*`, `PRAWDOWID_FB_*` + publiczny HTTPS (np. `cloudflared tunnel --url http://localhost:8000`); bez nich działa adapter demonstracyjny z identycznym formatem webhooka.

**Ewaluacja:** `PRAWDOWID_LIVE_SEARCH=0 backend/.venv/bin/python eval/run_eval.py [--cases eval/cases_heldout.jsonl|eval/cases_blind2.jsonl] [--out ...]`
→ `results.md` / `results.json`. Test E2E wtyczki: `eval/test_extension.py`, portale: `eval/test_real_sites.py`.
**Odświeżenie źródeł:** `ingest/run_factchecks.sh`, `ingest/run_official.sh`.

## Wyniki testów (sekcja 6 wyzwania)
Trzy zbiory (łącznie 145 przypadków, scenariusze A–J), przebieg 21.11.2026 na korpusie 4,4 tys. dok. (`eval/results_2026-11-21*/`),
bez wyszukiwania na żywo (`PRAWDOWID_LIVE_SEARCH=0`, powtarzalność). Zbiory „ślepe” przygotowały niezależne agenty wyłącznie na podstawie
korpusu i opisu wyzwania, bez wglądu w kod. **Uczciwą estymatą jakości są pierwsze przebiegi na zbiorach ślepych**
(kolumny „1. przebieg”); kolejne kolumny pokazują wynik po poprawkach ogólnych (reguły, nie łatki pod przypadki).

| Miernik | Cel MVP | Dev (38) | Ślepy 1 (57): 1. przebieg → po poprawkach | Ślepy 2 (50): 1. przebieg → po poprawkach |
|---|---|---|---|---|
| Trafność werdyktu (macro-F1) | ≥ 0,75 | 1,00 | **0,774** → 0,937 | **0,747** → 0,901 |
| Pokrycie cytowań | ≥ 95% | 100% | 100% → 100% | 100% → 100% |
| Wstrzymanie się przy braku dowodów | ≥ 80% | 100% | 100% → 100% | 100% → 100% |
| Odporność na prompt injection (instrukcja zignorowana **i** zdarzenie zapisane) | ≥ 90% | 100% | 60% → 100% | 25% → 100% |
| Statusy niewerdyktowe (błąd / doprecyzuj) | — | 100% | 33% → 100% | 50% → 100% |
| Czas (mediana / p95) | ≤ 30 s | 0,6 / 1,8 s | 0,6 / 2,0 s | 0,6 / 1,7 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 100% | 100% | 100% | 100% |
| Pętla informacji (deduplikacja spraw) | 100% | tak | tak | tak |

Wszystkie pozostałe błędy to **„brak dowodów” zamiast werdyktu** (błąd bezpieczny) — przy parafrazach semantycznych
(np. „ranny w strzelaninie” vs „postrzelony”). Żaden przypadek nie kończy się fałszywym werdyktem. We wszystkich próbach
prompt injection werdykt nie podążył za instrukcją (także w 1. przebiegach); poprawki dotyczyły wykrywania i
odnotowania nowych form ataku (komentarz HTML, blok ```system, base64, odgrywanie ról).
Z wyszukiwaniem na żywo czas odpowiedzi, gdy baza nie ma dowodu, rośnie do ok. 6–15 s (budżet 15 s).
Scenariusze referencyjne organizatorów A–J (pytania z docx) i ich wyniki: [COMPLIANCE](docs/COMPLIANCE.md).
Wyniki: `eval/results*/results.md` i `results.json`; odtworzenie: sekcja „Ewaluacja”.

Szczegóły: [architektura](docs/ARCHITECTURE.md) · [źródła i licencje](docs/SOURCES.md) · [ryzyka](docs/RISKS.md) ·
[koszty](docs/COSTS.md) · [zgodność z wymaganiami](docs/COMPLIANCE.md) · [rejestr źródeł](docs/SOURCE_REGISTRY.md) ·
[model danych](docs/DATA_MODEL.md) · [scenariusz demo](docs/DEMO.md) · [podsumowanie researchu](docs/RESEARCH_SUMMARY.md) ·
[metodologia](web/metodologia.html)
