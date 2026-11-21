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
| `extension/` | Wtyczka MV3 (Chrome/Edge/Vivaldi + Firefox Android): oznaczanie w czasie rzeczywistym treści zbieżnych z obalonymi twierdzeniami (zasłona / odznaka z prawdopodobieństwem), przycisk „Wybierz fragment” |
| `bots/discord_bot.py` | Bot Discord (`/sprawdz`, wzmianka, DM, menu kontekstowe wiadomości) |
| `bots/mcp_server.py` | Serwer MCP (tylko odczyt): `sprawdz`, `katalog_zrodel`, `kurs_nbp` (na żywo), `akt_prawny` / `szukaj_aktow` (Sejm ELI na żywo) |
| `ingest/` | Skrypty pobierające źródła → jednolity JSONL (`data/corpus/`) |
| `eval/` | Zbiór testowy (scenariusze A–J), `run_eval.py` (mierniki z sekcji 6), test E2E wtyczki |
| `docs/` | Architektura, źródła i licencje, ryzyka, koszty |
| `research/` | Raporty z researchu (kanały, źródła, metodologia SPRAWDŹ/IFCN/EFCSN, modele i prior art) |

## Uruchomienie (≈ 10 min, CPU wystarczy)
```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
uvicorn prawdowid.api:app --port 8000        # start ~10 s: repo zawiera gotowy cache embeddingów (data/index/)
```
Otwórz http://localhost:8000 · czat demo: http://localhost:8000/czat · panel analityka: http://localhost:8000/moderator
(token demo: `demo-moderator`, zmień przez `PRAWDOWID_MODERATOR_TOKEN`).

**Wtyczka:** `chrome://extensions` → tryb dewelopera → „Załaduj rozpakowane” → katalog `extension/`.
Strona testowa: http://localhost:8000/demo/feed.html. Firefox (także Android): `about:debugging` → „Załaduj tymczasowy dodatek” → `extension/manifest.json`.

**Discord:** `PRAWDOWID_DISCORD_TOKEN=... python bots/discord_bot.py` (instrukcja w pliku).
**WhatsApp/Messenger:** zmienne `PRAWDOWID_WA_*`, `PRAWDOWID_FB_*` + publiczny HTTPS (np. `cloudflared tunnel --url http://localhost:8000`); bez nich działa adapter demonstracyjny z identycznym formatem webhooka.

**Ewaluacja:** `backend/.venv/bin/python eval/run_eval.py` → `eval/results/results.md`.
**Odświeżenie źródeł:** `ingest/run_factchecks.sh`, `ingest/run_official.sh`.

## Wyniki testów (sekcja 6 wyzwania)
| Miernik | Cel MVP | Zbiór deweloperski (38) | Zbiór niezależny „held-out” (57) — 1. przebieg ślepy | po poprawkach ogólnych |
|---|---|---|---|---|
| Trafność werdyktu (macro-F1) | ≥ 0,75 | 1,00 | **0,774** | 0,936 |
| Pokrycie cytowań | ≥ 95% | 100% | 100% | 100% |
| Wstrzymanie się przy braku dowodów | ≥ 80% | 100% | 100% | 100% |
| Odporność na prompt injection | ≥ 90% | 100% | 60% | 100% |
| Czas (mediana) | ≤ 30 s | 0,4 s | 0,5 s | 0,5 s |
| Spójność kanałów (WWW vs WhatsApp-demo) | 100% | 100% | 100% | 100% |
| Pętla informacji (deduplikacja spraw) | 100% | tak | tak | tak |

Zbiór „held-out” napisał niezależny agent na podstawie korpusu, bez wglądu w kod. Kolejne poprawki były regułami
ogólnymi (miary statystyczne, formy prompt injection, powitania), nie łatkami pod przypadki — ale po nich zbiór nie
jest już w pełni ślepy; uczciwą estymatą jest 1. przebieg. Wszystkie pozostałe błędy to „brak dowodów” zamiast werdyktu
(błąd bezpieczny), nie fałszywe werdykty. Wyniki: `eval/results*/results.md`; odtworzenie: sekcja „Ewaluacja”.

Szczegóły: [architektura](docs/ARCHITECTURE.md) · [źródła i licencje](docs/SOURCES.md) · [ryzyka](docs/RISKS.md) ·
[koszty](docs/COSTS.md) · [scenariusz demo](docs/DEMO.md) · [podsumowanie researchu](docs/RESEARCH_SUMMARY.md) ·
[metodologia](web/metodologia.html)
