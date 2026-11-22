# Mapa modułów backendu

Ten przewodnik obejmuje wszystkie moduły produkcyjne w `backend/prawdowid/`. Przy każdym podano odpowiedzialność, kod i jego punkty wejścia. Pomocnicze funkcje zaczynające się od `_` są szczegółami implementacji; istniejące nazwy pozostają dostępne dla kompatybilności testów i integracji.

[Powrót do przewodnika](README.md)

## __init__.py

Metadane pakietu i wersja aplikacji.

Kod: [`__init__.py`](../../backend/prawdowid/__init__.py) · Przewodnik: [README.md](README.md)

## api.py

Punkt wejścia HTTP: endpointy, rozruch, middleware i serwowanie strony.

Kod: [`api.py`](../../backend/prawdowid/api.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `rate_limit`, `health`, `api_check`, `api_get_check`, `api_chat_reply`, `api_quick`, `api_delete_session`, `api_feedback`, `api_sources`, `api_stats`, `api_cases`, `api_case_update`, `api_export`, `page_index`, `page_result`, `page_check`, `manifest`, `sw`, `share_target`.

## admin_api.py

Zarządzanie rejestrem źródeł z autoryzacją oraz jego publiczna projekcja.

Kod: [`admin_api.py`](../../backend/prawdowid/admin_api.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `check_token`, `require_admin`, `page_admin`, `admin_sources`, `admin_get`, `admin_runs`, `admin_changes`, `admin_create`, `admin_update`, `admin_enable`, `admin_disable`, `admin_delete`, `admin_test_config`, `admin_test`, `admin_run`, `admin_suggest`, `admin_reload`, `public_registry`.

## agreement.py

Kontrola zgodności tekstów: parafrazy, zmienione nazwy, liczby i zaprzeczenia.

Kod: [`agreement.py`](../../backend/prawdowid/agreement.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `fold`, `same_word`, `names_disagree`, `quantities`, `numbers_disagree`, `disagreement`.

## answer.py

Deterministyczne odpowiedzi po polsku, wybór dowodu i jawne ograniczenia.

Kod: [`answer.py`](../../backend/prawdowid/answer.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `main_evidence`, `short_answer`, `basis_line`, `limitation_line`, `result_short_answer`, `finalize`.

## catalog.py

Podsumowania wydawców do publicznego katalogu źródeł, bez zmiany indeksu.

Kod: [`catalog.py`](../../backend/prawdowid/catalog.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `summarize_publishers`.

## claims.py

Wydzielanie sprawdzalnych twierdzeń oraz rozpoznawanie opinii i prognoz.

Kod: [`claims.py`](../../backend/prawdowid/claims.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `Claim`, `extract_claims`.

## config.py

Ustawienia środowiska, lokalizacje danych i konfiguracja modeli.

Kod: [`config.py`](../../backend/prawdowid/config.py) · Przewodnik: [DEVELOPMENT.md](DEVELOPMENT.md)

Punkty wejścia: `Settings`.

## engine.py

Przygotowanie dowodów i uporządkowane reguły oceny pojedynczego twierdzenia.

Kod: [`engine.py`](../../backend/prawdowid/engine.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `asked_number_fragment`, `presented_year`, `archival_origin`, `shown_fragment`, `same_subject`, `legal_date_stance`, `numeric_stance`, `claim_match`, `same_claim`, `claim_units`, `headline_statement`, `unit_match`, `has_own_text`, `match_support`, `same_checked_claim`, `consistent_matches`, `verify_claim`.

## fetch.py

Bezpieczne pobranie URL użytkownika, ekstrakcja tekstu i metadanych ClaimReview.

Kod: [`fetch.py`](../../backend/prawdowid/fetch.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `FetchError`, `fetch_url`, `claim_review`.

## index.py

Wczytywanie korpusu, wyszukiwanie hybrydowe, dopasowanie twierdzeń i cache embeddingów.

Kod: [`index.py`](../../backend/prawdowid/index.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `Chunk`, `BM25`, `Embedder`, `CorpusIndex`, `claim_rows`, `prune_cache`.

## jobs.py

Zadania asynchroniczne w pamięci, raportowanie postępu i osobna pojemność sprawdzeń w tle.

Kod: [`jobs.py`](../../backend/prawdowid/jobs.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `Job`, `guard_auto`, `api_check_async`, `api_job`.

## linefilter.py

Usuwanie metadanych autora, daty i udostępnień przed ekstrakcją twierdzeń.

Kod: [`linefilter.py`](../../backend/prawdowid/linefilter.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `line_kind`, `drop_metadata_lines`.

## llm.py

Opcjonalna redakcja wyjaśnienia z powrotem do szablonu przy błędzie; bez decyzji o werdykcie.

Kod: [`llm.py`](../../backend/prawdowid/llm.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `enabled`, `simplify`.

## measures.py

Rozpoznawanie miar statystycznych i rozróżnianie definicji podobnych wartości.

Kod: [`measures.py`](../../backend/prawdowid/measures.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `Variant`, `Dimension`, `Measure`, `profile`, `card_profile`, `named`, `compatible`, `unnamed`, `uses`, `measure_of`.

## nli.py

Leniwie ładowany model wynikania i sprzeczności oraz zachowawczy wariant bez modelu.

Kod: [`nli.py`](../../backend/prawdowid/nli.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `NLIScore`, `NLI`.

## ocr.py

Lokalny odczyt tekstu ze zrzutów z limitami obrazów i jawną obsługą błędów.

Kod: [`ocr.py`](../../backend/prawdowid/ocr.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `OcrUnavailable`, `OcrError`, `available`, `decode_b64`, `load`, `prepare`, `read_text`, `parse_tsv`, `lines_to_text`, `blocks_to_sentences`.

## provenance.py

Porównanie podlinkowanego materiału z publikacją opisaną przez fact-checkera.

Kod: [`provenance.py`](../../backend/prawdowid/provenance.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `asks_same_item`, `find`, `check_linked_item`.

## ratelimit.py

Limity żądań w obrębie procesu, według adresu klienta i rodzaju operacji.

Kod: [`ratelimit.py`](../../backend/prawdowid/ratelimit.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `client_ip`, `hit`, `enforce`, `reset`.

## resources.py

Dobór kilku zaufanych linków tematycznych, które nie wpływają na werdykt.

Kod: [`resources.py`](../../backend/prawdowid/resources.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `topics_for`, `resources_for`.

## robots.py

Parser robots.txt z najdłuższą pasującą regułą i pierwszeństwem Allow przy remisie.

Kod: [`robots.py`](../../backend/prawdowid/robots.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `RobotsTxt`.

## schemas.py

Wspólne modele żądań i wyników oraz słownik statusów, werdyktów i dowodów.

Kod: [`schemas.py`](../../backend/prawdowid/schemas.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `SourceDoc`, `Evidence`, `Premise`, `ClaimResult`, `SecurityEvent`, `CheckRequest`, `LiveSearchInfo`, `ChatRequest`, `CheckResult`, `QuickItem`, `QuickRequest`, `QuickMatch`, `QuickConflict`, `QuickResult`.

## security.py

Wykrywanie i neutralizacja instrukcji w treści oraz odrzucanie niebezpiecznych URL.

Kod: [`security.py`](../../backend/prawdowid/security.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `scan`, `neutralize`, `UnsafeURL`, `ResolveError`, `check_public_url`.

## service.py

Koordynacja całego sprawdzenia oraz szybki router dopasowań wtyczki.

Kod: [`service.py`](../../backend/prawdowid/service.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `engine_info`, `cost_estimate`, `run_check`, `source_status_notices`, `QuickBusy`, `quick_score`.

## signals.py

Edukacyjne sygnały SPRAWDŹ; nie są wejściem do decyzji o werdykcie.

Kod: [`signals.py`](../../backend/prawdowid/signals.py) · Przewodnik: [REQUEST_FLOW.md](REQUEST_FLOW.md)

Punkty wejścia: `sprawdz_signals`.

## store.py

SQLite: audyt sprawdzeń, sprawy, feedback, błędy, eksport i usuwanie sesji.

Kod: [`store.py`](../../backend/prawdowid/store.py) · Przewodnik: [DATA_MODEL.md](../DATA_MODEL.md)

Punkty wejścia: `now`, `new_id`, `save_check`, `save_auto_check`, `log_error`, `get_check`, `export_checks`, `delete_session`, `purge_expired`, `upsert_case`, `list_cases`, `update_case`, `stats`, `recent_security_events`, `add_feedback`, `list_feedback`.

## textutil.py

Polski tekst, tokenizacja, liczby, jednostki i maskowanie identyfikatorów.

Kod: [`textutil.py`](../../backend/prawdowid/textutil.py) · Przewodnik: [ENGINE.md](ENGINE.md)

Punkty wejścia: `normalize_ws`, `split_sentences`, `strip_pl`, `tokens`, `is_question`, `is_task_request`, `checked_question`, `is_meta_sentence`, `split_meta`, `asks_who_checked`, `strip_preamble`, `question_to_claim`, `content_words`, `claim_kind`, `checkworthiness`, `amount_unit`, `amounts`, `same_amount`, `years_in`, `is_time_sensitive`, `pii_spans`, `mask_pii`, `drop_pii_tags`, `unmark_excerpt`, `is_rule_claim`, `rule_scope`, `short`, `lead_excerpt`, `opening_excerpt`, `finding_excerpt`.

## websearch.py

Dostawcy wyszukiwania na żywo, budżety, dodawanie wyników i ponowna weryfikacja.

Kod: [`websearch.py`](../../backend/prawdowid/websearch.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `emit`, `live_enabled`, `forced_fail`, `LiveError`, `TrustedSource`, `registry`, `match_source`, `allowed_hosts`, `robots_allowed`, `Term`, `substr_stem`, `query_terms`, `keywords`, `Hit`, `map_rating`, `google_publisher_sites`, `google_factcheck`, `google_queries`, `google_search`, `google_docs`, `SearchOutcome`, `search_trusted`, `persist_days`, `purge_live_corpus`, `persist`, `LiveStage`.

## channels/__init__.py

Adaptery transportowe; sama weryfikacja pozostaje w service.py.

Kod: [`channels/__init__.py`](../../backend/prawdowid/channels/__init__.py) · Przewodnik: [API.md](API.md)

## channels/formatting.py

Renderowanie wspólnego wyniku do odpowiedzi czatu i transportu SMS.

Kod: [`channels/formatting.py`](../../backend/prawdowid/channels/formatting.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `chat_text`.

## channels/meta.py

Webhooki WhatsApp i Messenger oraz demonstracyjny wariant transportu.

Kod: [`channels/meta.py`](../../backend/prawdowid/channels/meta.py) · Przewodnik: [API.md](API.md)

Punkty wejścia: `wa_verify`, `wa_webhook`, `fb_verify`, `fb_webhook`, `demo_outbox`.

## sources/__init__.py

Rejestr źródeł, metody pobierania, harmonogram i stan operacyjny.

Kod: [`sources/__init__.py`](../../backend/prawdowid/sources/__init__.py) · Przewodnik: [SOURCES.md](SOURCES.md)

## sources/__main__.py

CLI do przeglądania, walidacji, pobierania i kontroli zakresu źródeł.

Kod: [`sources/__main__.py`](../../backend/prawdowid/sources/__main__.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `main`.

## sources/fetchers.py

Wspólne metody pobierania, limity HTTP, deduplikacja i wykrywanie konfiguracji.

Kod: [`sources/fetchers.py`](../../backend/prawdowid/sources/fetchers.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `FetchError`, `RobotsDisallowed`, `Protected`, `now_iso`, `robots_allowed`, `robots_sitemaps`, `http_get`, `ingest_module`, `html_to_text`, `to_date`, `date_from_html`, `truncate`, `extract_article`, `canonical`, `url_key`, `make_record`, `normalize_record`, `Ctx`, `parse_feed`, `parse_sitemap`, `fetch_rss`, `fetch_sitemap`, `extract_links`, `fetch_html_list`, `fetch_govpl_list`, `fetch_custom`, `legacy_python`, `run_legacy_script`, `read_corpus`, `urls_held_by`, `merge_into_corpus`, `fetch_source`, `test_source`, `guess_link_regex`, `suggest_config`.

## sources/registry.py

Walidacja konfiguracji i wybór plików korpusu kwalifikowanych do indeksowania.

Kod: [`sources/registry.py`](../../backend/prawdowid/sources/registry.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `SourceError`, `sources_dir`, `path_for`, `corpus_path`, `validate`, `load_all`, `get`, `exists`, `save`, `delete`, `in_organiser_scope`, `scope_report`, `restrict_to_organiser_scope`, `corpus_files_for_index`, `count_docs`.

## sources/scheduler.py

Planowanie i serializacja pobrań oraz przeładowanie zmienionego indeksu.

Kod: [`sources/scheduler.py`](../../backend/prawdowid/sources/scheduler.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `Busy`, `current`, `next_due`, `run_source`, `index_signature`, `maybe_reload`, `run_now_async`, `reload_async`, `due_sources`, `tick`, `start`, `stop`, `status`.

## sources/state.py

Historia pobrań i zmian konfiguracji administratora w SQLite.

Kod: [`sources/state.py`](../../backend/prawdowid/sources/state.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `start_run`, `finish_run`, `record_skip`, `mark_interrupted`, `last_runs`, `last_attempt`, `recent_runs`, `diff`, `log_change`, `recent_changes`, `purge_old_runs`.

## source_handlers/__init__.py

Własne konektory źródeł z kontraktem fetch(source).

Kod: [`source_handlers/__init__.py`](../../backend/prawdowid/source_handlers/__init__.py) · Przewodnik: [SOURCES.md](SOURCES.md)

## source_handlers/_common.py

Wspólne operacje HTTP, rekordy korpusu i funkcje pomocnicze konektorów.

Kod: [`source_handlers/_common.py`](../../backend/prawdowid/source_handlers/_common.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `http_get`, `get_json`, `get_html`, `delay_of`, `max_chars`, `known_urls`, `canonical`, `now_iso`, `clean_ws`, `truncate`, `md_to_text`, `pl_text_date`, `text_dates`, `iso_date`, `short_hash`, `record`.

## source_handlers/euvsdisinfo_mcp.py

Pobieranie danych EUvsDisinfo przez MCP, ponawianie i konwersja rekordów.

Kod: [`source_handlers/euvsdisinfo_mcp.py`](../../backend/prawdowid/source_handlers/euvsdisinfo_mcp.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `McpError`, `MissingToken`, `AuthError`, `SessionExpired`, `HttpResponse`, `urllib_transport`, `parse_messages`, `McpClient`, `strip_html`, `now_iso`, `to_date`, `case_to_record`, `article_to_record`, `fetch`, `probe`, `main`.

## source_handlers/google_factcheck_feed.py

Pobieranie metadanych ClaimReview wydawcy przez Google Fact Check Tools.

Kod: [`source_handlers/google_factcheck_feed.py`](../../backend/prawdowid/source_handlers/google_factcheck_feed.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `ApiError`, `restates_title`, `call`, `to_record`, `fetch`.

## source_handlers/imgw_ostrzezenia.py

Zamiana ostrzeżeń IMGW na rekordy urzędowego korpusu.

Kod: [`source_handlers/imgw_ostrzezenia.py`](../../backend/prawdowid/source_handlers/imgw_ostrzezenia.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `fetch`.

## source_handlers/msz_odyseusz.py

Pobieranie komunikatów podróżnych MSZ Odyseusz.

Kod: [`source_handlers/msz_odyseusz.py`](../../backend/prawdowid/source_handlers/msz_odyseusz.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `fetch`.

## source_handlers/rso_ostrzezenia.py

Pobieranie komunikatów Regionalnego Systemu Ostrzegania.

Kod: [`source_handlers/rso_ostrzezenia.py`](../../backend/prawdowid/source_handlers/rso_ostrzezenia.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `fetch`.

## source_handlers/static_pages.py

Pobieranie jawnie skonfigurowanych stron urzędowych bez ogólnego crawlowania.

Kod: [`source_handlers/static_pages.py`](../../backend/prawdowid/source_handlers/static_pages.py) · Przewodnik: [SOURCES.md](SOURCES.md)

Punkty wejścia: `fetch`.
