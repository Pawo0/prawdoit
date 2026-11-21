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
uvicorn prawdowid.api:app --port 8000        # pierwszy start buduje indeks embeddingów (cache w data/index/)
```
Otwórz http://localhost:8000 · czat demo: http://localhost:8000/czat · panel analityka: http://localhost:8000/moderator
(token demo: `demo-moderator`, zmień przez `PRAWDOWID_MODERATOR_TOKEN`).

**Wtyczka:** `chrome://extensions` → tryb dewelopera → „Załaduj rozpakowane” → katalog `extension/`.
Strona testowa: http://localhost:8000/demo/feed.html. Firefox (także Android): `about:debugging` → „Załaduj tymczasowy dodatek” → `extension/manifest.json`.

**Discord:** `PRAWDOWID_DISCORD_TOKEN=... python bots/discord_bot.py` (instrukcja w pliku).
**WhatsApp/Messenger:** zmienne `PRAWDOWID_WA_*`, `PRAWDOWID_FB_*` + publiczny HTTPS (np. `cloudflared tunnel --url http://localhost:8000`); bez nich działa adapter demonstracyjny z identycznym formatem webhooka.

**Ewaluacja:** `backend/.venv/bin/python eval/run_eval.py` → `eval/results/results.md`.
**Odświeżenie źródeł:** `ingest/run_factchecks.sh`, `ingest/run_official.sh`.

Szczegóły: [architektura](docs/ARCHITECTURE.md) · [ryzyka](docs/RISKS.md) · [metodologia](web/metodologia.html)
