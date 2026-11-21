# Model danych — co gdzie leży

Wszystkie ścieżki względem katalogu repozytorium; każdą można zmienić zmienną `PRAWDOWID_*` (w nawiasie).
Pliki tekstowe (JSON/JSONL) da się czytać zwykłym edytorem; bazę — `sqlite3 data/runtime/prawdowid.sqlite`.

## Przegląd

| Magazyn | Ścieżka | Kto pisze | Format | Retencja |
|---|---|---|---|---|
| Rejestr źródeł | `data/sources/<id>.json` (`SOURCES_DIR`) | panel `/admin`, człowiek, migracja | JSON, 1 plik = 1 źródło | bezterminowo (usunięcie w panelu kasuje plik) |
| Korpus | `data/corpus/<id>.jsonl` (`CORPUS_DIR`) | harmonogram, CLI, skrypty `ingest/`, wyszukiwanie na żywo (`live_web.jsonl`) | JSONL, 1 linia = 1 dokument | najwyżej `params.max_docs` najnowszych (domyślnie 500); skrypty `legacy_script` nadpisują plik w całości |
| Archiwum korpusu | `data/corpus/archive/<id>-<czas>.jsonl` | usunięcie źródła w panelu | JSONL | do ręcznego usunięcia; nie jest indeksowane |
| Baza robocza | `data/runtime/prawdowid.sqlite` (`RUNTIME_DIR`) | API | SQLite, tabele niżej | jak w tabelach niżej |
| Blokada pobierania | `data/runtime/sources.lock` | harmonogram, CLI | pusty plik (`flock`) | — |
| Pamięć embeddingów | `data/index/emb-<hash>.npy` + `.keys.json` (`INDEX_DIR`) | indeks przy ładowaniu | NumPy float32 + lista kluczy | rośnie, nie jest czyszczona; można usunąć (zostanie odbudowana) |
| Surowe pobrania | `data/raw/<źródło>/` | skrypty `ingest/`, moduły `source_handlers` | gzip HTML/JSONL, logi | pamięć podręczna — usunięcie wymusza ponowne pobranie |
| Lista obserwowanych domen | `data/watchlist.json` | człowiek | JSON | — |

## Rejestr źródeł — `data/sources/<id>.json`
Kontrakt i znaczenie pól: `docs/SOURCE_REGISTRY.md`. Najważniejsze: `enabled` (czy pobierane i indeksowane),
`method` + `params` (jak pobierać), `schedule_hours` (co ile godzin; 0 = ręcznie), `license`, `qualification`.
Indeks ładuje korpusy źródeł z `enabled: true` oraz pliki korpusu, które nie mają wpisu w rejestrze.

## Rekord korpusu — `data/corpus/<id>.jsonl`

| Pole | Znaczenie |
|---|---|
| `id` | unikalny klucz, zwykle `<źródło>:<identyfikator>`; dla pobrań z rejestru `<id źródła>:<sha1(url)[:12]>` |
| `source_type` | `official` / `factcheck` / `incident` / `media` (= `category` źródła) |
| `publisher`, `domain`, `url`, `title` | wydawca, domena (bez `www.`), adres, tytuł |
| `published_at` | data publikacji `RRRR-MM-DD` (może być pusta) |
| `retrieved_at` | czas pobrania, UTC |
| `language`, `license` | kod języka, licencja / warunki (z wpisu rejestru) |
| `text` | treść lub fragment (do 4000 znaków, mniej gdy licencja na to nie pozwala) |
| `claim`, `claim_author`, `verdict_raw`, `verdict` | tylko fact-checki/incydenty: twierdzenie, autor, ocena oryginalna, ocena znormalizowana (`true|false|misleading|mixed|unverifiable`) |
| `tags` | słowa kluczowe (dla pobrań z rejestru: id źródła + `topics`) |

## Tabele SQLite — `data/runtime/prawdowid.sqlite`

| Tabela | Kolumny | Znaczenie | Retencja |
|---|---|---|---|
| `checks` | `id`, `created_at`, `channel`, `session`, `input_masked`, `status`, `verdicts` (JSON), `sources` (JSON z URL), `result_json`, `total_ms`, `case_id` | przebieg każdego sprawdzenia; wejście z zamaskowanymi danymi osobowymi | `RETENTION_DAYS` (30 dni), czyszczone przy starcie serwera; `DELETE /api/session/<id>` usuwa sesję. Sprawdzenia w tle wtyczki (`mode: "auto"`, kanał `…-auto`) zapisują wiersz **bez tekstu**: `input_masked` = `sha256:<skrót>`, `session` puste, `result_json` tylko z werdyktem, regułami, metadanymi użytych źródeł i czasami; retencja `AUTO_RETENTION_DAYS` (7 dni); nie tworzą spraw w `cases` |
| `security_events` | `id`, `created_at`, `check_id`, `kind`, `location`, `detail` | wykryte próby wstrzyknięcia poleceń i inne zdarzenia bezpieczeństwa | bez automatycznego czyszczenia |
| `cases` | `id`, `created_at`, `updated_at`, `status` (nowa / w toku / zamknięta), `title`, `count`, `channels`, `sample_check_ids`, `centroid` (embedding), `priority`, `note` | sprawy w kolejce analityka (podobne zgłoszenia łączone) | bez automatycznego czyszczenia |
| `feedback` | `id`, `created_at`, `check_id`, `message` (zamaskowane), `status` | uwagi użytkowników | bez automatycznego czyszczenia |
| `errors` | `id`, `created_at`, `check_id`, `component`, `detail` | błędy komponentów (np. pobranie URL) | bez automatycznego czyszczenia |
| `source_runs` | `id`, `source_id`, `trigger` (`harmonogram` / `admin:<kto>` / `cli`), `started`, `finished`, `status` (`ok` / `error` / `skipped`; chwilowo `running`), `n_new`, `n_total`, `message` | każde uruchomienie pobierania źródła: ile nowych, ile razem w pliku, uwagi lub błąd | 90 dni (czyszczone przy starcie harmonogramu) |
| `source_changes` | `id`, `at`, `who` (imię z panelu lub „administrator”), `source_id`, `action` (`create` / `update` / `enable` / `disable` / `delete`), `diff` (JSON `{pole: [przed, po]}`) | dziennik zmian rejestru wykonanych przez panel | bezterminowo (audyt) |

Czas we wszystkich tabelach: ISO 8601, UTC. Zmiany plików rejestru zrobione ręcznie (poza panelem) nie trafiają do
`source_changes` — widać je w historii git.

## Pamięć embeddingów — `data/index/`
Dwie pary plików na model: `emb-<sha1(model+prefiks)[:10]>.npy` (macierz wektorów) i `.keys.json` (sha1 tekstu → wiersz).
Jedna para dla fragmentów dokumentów (prefiks `passage:`), druga dla twierdzeń fact-checków (prefiks `query:`).
Przy ładowaniu i przeładowaniu indeksu liczone są tylko teksty, których jeszcze nie ma — dlatego dodanie źródła jest tanie.
Sam indeks (BM25, fragmenty) żyje tylko w pamięci procesu i jest budowany przy starcie oraz po zmianie korpusu.

## Jak sprawdzić stan
- `python -m prawdowid.sources list` (z `backend/`) — źródła, liczba dokumentów, ostatnie uruchomienie.
- `sqlite3 data/runtime/prawdowid.sqlite "select started, source_id, status, n_new, message from source_runs order by id desc limit 20"`
- Panel `/admin` (uruchomienia, dziennik zmian), `GET /api/health` (statystyki indeksu, w tym `excluded_files`).
