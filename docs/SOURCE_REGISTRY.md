# Rejestr źródeł (source registry) — kontrakt danych

Jedno źródło = jeden plik `data/sources/<id>.json` (czytelny dla człowieka, łatwy do audytu i porównania w git).
Panel administratora (`/admin`) edytuje te pliki; harmonogram pobiera źródła i zapisuje dokumenty do
`data/corpus/<id>.jsonl`. Stan pobierania (ostatnie uruchomienie, błędy, liczba dokumentów) jest danymi
roboczymi i trafia do SQLite (`data/runtime/prawdowid.sqlite`, tabela `source_runs`), nie do pliku źródła.

Katalog `/zrodla` (rejestr i wydawcy osobno) oraz lista źródeł `/admin` mają paginację po 10, 25 lub 50 pozycji
(domyślnie 10), licznik i przyciski pierwszej, poprzedniej, następnej i ostatniej strony. Stronicowanie działa
w przeglądarce; API nadal zwraca pełne listy do audytu i integracji. Automatyczne odświeżanie panelu zachowuje
wybraną stronę i limit; po usunięciu ostatniej strony wybierana jest ostatnia dostępna. Zmiana limitu wraca
na pierwszą stronę. Test z kontrolowanym API: `node eval/test_source_pagination.cjs` (Playwright/Chromium,
opcjonalnie `CHROME_PATH` i `SCREENSHOT_DIR`).

## Plik źródła `data/sources/<id>.json`

```json
{
  "id": "kgpsp_aktualnosci",
  "name": "Państwowa Straż Pożarna — aktualności",
  "publisher": "Komenda Główna Państwowej Straży Pożarnej",
  "url": "https://www.gov.pl/web/kgpsp/aktualnosci",
  "category": "official",
  "tier": 1,
  "method": "govpl_list",
  "params": {"list_url": "https://www.gov.pl/web/kgpsp/aktualnosci", "max_items": 30},
  "enabled": true,
  "schedule_hours": 6,
  "web_search": true,
  "topics": ["bezpieczenstwo", "pozary"],
  "language": "pl",
  "license": "Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych …” (cytat warunków portalu)",
  "qualification": "Organ właściwy dla ochrony przeciwpożarowej; komunikaty urzędowe.",
  "scope": "organiser_listed",
  "scope_basis": "rules/resources.txt: gov.pl/web/kgpsp/aktualnosci",
  "added_by": "organizator (rules/resources.txt)",
  "added_at": "2026-11-21"
}
```

| Pole | Znaczenie |
|---|---|
| `id` | stały identyfikator (slug, `[a-z0-9_]+`); nazwa pliku korpusu `data/corpus/<id>.jsonl` |
| `name`, `publisher`, `url` | nazwa dla człowieka, wydawca (instytucja), strona wejściowa |
| `category` | `official` \| `factcheck` \| `incident` \| `media` (= `source_type` dokumentów) |
| `tier` | 1 = pierwotne/urzędowe, 2 = fact-checking IFCN/EFCSN, 3 = baza incydentów, 4 = media (tylko kontekst) |
| `method` | sposób pobierania — patrz niżej |
| `params` | parametry metody |
| `enabled` | czy źródło jest pobierane i indeksowane (wyłączone → nie trafia do indeksu) |
| `schedule_hours` | co ile godzin odświeżać; `0` = tylko ręcznie |
| `web_search` | czy domena źródła może dostarczać dowodów w wyszukiwaniu na żywo (gdy korpus nic nie znalazł) |
| `topics` | tematy (słownik poniżej) — dobór „Przydatnych stron” na stronie wyjaśnienia |
| `license`, `qualification` | licencja/warunki i uzasadnienie wiarygodności (zasady kwalifikacji) |
| `scope` | zakres względem oczekiwań organizatora: `organiser_listed` \| `organiser_implied` \| `organiser_recommended` \| `outside` (brak pola = `outside`) — patrz niżej |
| `scope_basis` | gdzie organizator wskazuje to źródło (dokument i miejsce); wymagane dla każdego zakresu poza `outside` |
| `added_by`, `added_at` | kto i kiedy dodał źródło |

### Zakres organizatora (`scope`)

Organizator wskazał, że źródłem prawdy są Demagog (przez API) i strony, które sam podał. Każdy wpis rejestru mówi więc
jawnie, skąd się wziął (analiza i pomiary: `research/10_organiser_sources.md`):

| `scope` | Znaczenie | Przykłady |
|---|---|---|
| `organiser_listed` | adres lub baza z `rules/resources.txt` | Odyseusz, RCB, RSO, IMGW, policja.pl, moje.cert.pl, Google Fact Check |
| `organiser_implied` | źródło użyte w scenariuszach referencyjnych lub instrukcjach organizatora albo ten sam serwis/instytucja co adres z listy | Demagog, PAP, EUvsDisinfo, aktualności MSZ, cert.pl |
| `organiser_recommended` | wymienione tylko wśród „rekomendowanych punktów odniesienia” w treści zadania (sekcja 7), także ogólnie („korpusy organizacji IFCN/EFCSN”) | dane.gov.pl, ISAP, EUR-Lex, FakeNews.pl i AFP Sprawdzam (obie drogi, także przez bazę Google: organizator wskazał bazę, nie tych wydawców), Konkret24, Pravda, Check First |
| `outside` | dodane przez zespół, organizator ich nie wymienia | GUS, NBP, Eurostat, Przedstawicielstwo KE (PKW: `organiser_recommended`, przez ISAP) |

- Formularz panelu `/admin` nie ma pola zakresu, więc dodane w nim źródło dostaje `outside`. Zakres organizatora wpisuje
  się w pliku albo w polach `scope` + `scope_basis` treści JSON wysłanej do `/api/admin/sources`; bez uzasadnienia
  zapis jest odrzucany.
- `python -m prawdowid.sources scope` (z `backend/`) wypisuje źródła według zakresu i kończy się kodem 1, gdy baza wiedzy
  zawiera coś spoza zakresu: włączone źródło `outside`, plik korpusu bez wpisu w rejestrze albo rekordy wyszukiwania na
  żywo (`live_web.jsonl`) pochodzące ze źródła, które jest wyłączone lub poza zakresem. `--strict` zawęża zakres do
  `organiser_listed` + `organiser_implied`.
- `python -m prawdowid.sources scope --restrict` wyłącza (nie usuwa) włączone źródła spoza zakresu i zapisuje powód w
  polu `notes`; plików korpusu nie rusza. Włączyć z powrotem można w panelu `/admin`.
- Zakres pokazują: katalog `/zrodla` (pod nazwą źródła), `/api/sources` (`scope`, `scope_basis`) i `docs/SOURCES.md`.

### Metody pobierania (`method`)

| Metoda | `params` | Opis |
|---|---|---|
| `rss` | `feed_url`, `max_items` (30), `fetch_full_text` (bool, `true`) | kanał RSS/Atom; `false` = tylko opis z kanału |
| `sitemap` | `sitemap_url`, `url_regex`, `max_items` (30), `date_regex` (opcj.) | mapa strony XML (też `.xml.gz`); indeks map → 3 najnowsze mapy; najnowsze wg `lastmod` |
| `html_list` | `list_urls` (lista), `link_regex`, `max_items` (30), `min_text_chars` (300), `date_regex` (opcj.) | strona z listą artykułów → linki pasujące do wzorca (`re.search`, kolejność jak na stronie) → ekstrakcja treści; `date_regex` (grupa 1 na HTML artykułu, np. `5 listopada 2026` / `05.11.2026`) zastępuje datę z metadanych, gdy ta jest datą modyfikacji serwisu |
| `govpl_list` | `list_url`, `max_items` (30) | lista aktualności w serwisie gov.pl (stronicowanie `?page=N&size=10`; parser z `ingest/official_govpl.py`) |
| `custom` | `handler` (+ dowolne) | moduł `prawdowid.source_handlers.<handler>` z funkcją `fetch(source: dict) -> list[dict]` zwracającą rekordy korpusu; dostaje też `source["_known_urls"]` (już zapisane adresy); wyjątki z krotki `EXPECTED_ERRORS` modułu (np. „brak tokenu”) dają czytelny status `error` z komunikatem, bez śladu stosu |
| `legacy_script` | `script` (np. `ingest/official_gus.py`), `args` (lista), `timeout_s` (3600) | istniejący skrypt z `ingest/` zapisujący (nadpisujący) `data/corpus/<id>.jsonl`; uruchamiany w `ingest/` interpreterem `ingest/.venv_official` (`official_*`) lub `ingest/.venv` (`harvest_*`) |
| `live_search` | — | dokumenty dodawane przez wyszukiwanie na żywo (`live_web`); bez harmonogramu |
| `google_factcheck` | `publisher_sites` (lista domen, opcj.) | Google Fact Check Tools API, zapytania na żywo (klucz `PRAWDOWID_GOOGLE_FACTCHECK_KEY`, wysyłany w nagłówku `X-Goog-Api-Key`, nigdy w adresie); zapytania to słowa kluczowe twierdzenia w kilku rundach (API nie odpowiada na całe zdania); gdy strona wyników jest pełna innych wydawców, zapytanie jest powtarzane z filtrem `reviewPublisherSiteFilter` dla domen z `publisher_sites` (np. `demagog.org.pl`) należących do włączonych źródeł |
| `reference_only` | — | nie pobieramy (np. mapy/aplikacje dynamiczne); służy jako zaufany link i domena wyszukiwania |

Moduły `custom` dostarczane z projektem: `msz_odyseusz`, `rso_ostrzezenia`, `imgw_ostrzezenia`, `static_pages`,
`euvsdisinfo_mcp` (`docs/MCP_EUVSDISINFO.md`) oraz **`google_factcheck_feed`** — „Demagog przez API”: lista ocen jednego
wydawcy z Google Fact Check Tools API (`site`, `max_age_days` 200, `page_size` ≤ 100, `max_pages`, `key_env`,
`dedupe_against` = identyfikatory korpusów, których adresy pomijamy). Rekord ma dosłowne pola ClaimReview wydawcy
(tytuł oceny + sprawdzane twierdzenie, etykieta oceny), bez treści artykułu (tag `claimreview-only`). Wpisy:
`demagog_google_api`, `afp_sprawdzam`, `fakenews_google_api`. Parametr wspólny `id_prefix`: źródło, które dostarcza te
same dokumenty co inne drugą drogą, zachowuje jego przestrzeń identyfikatorów (`demagog:…`, `euvsdisinfo:…`) — indeks
ładuje pierwszy rekord o danym `id`, więc ta sama ocena nie trafia do bazy dwa razy. Gdy identyfikatora nie da się
odtworzyć (FakeNews.pl: numery wpisów), działa `dedupe_against`: adresy z korpusów tych źródeł są pomijane przy
pobieraniu i usuwane z pliku przy każdym scaleniu (także po pustym uruchomieniu), ale tylko gdy indeks te korpusy
ładuje (źródło włączone albo bez wpisu w rejestrze) — po wyłączeniu zbioru stron droga przez API dostarcza oceny sama.
Adresy porównujemy po zdekodowaniu znaków `%XX` (`co%e2%82%82` w zbiorach stron = `co%E2%82%82` w API).

Parametry wspólne dla metod pobierających: `max_docs` (ile najnowszych rekordów zostaje w pliku korpusu, domyślnie 500),
`max_chars` (długość tekstu rekordu, domyślnie 4000), `excerpt_chars` (źródła bez otwartej licencji: zapisywany jest
tylko początkowy fragment tekstu, dosłownie, do tylu znaków; np. CERT Polska — 300), `delay_s` (odstęp między zapytaniami do hosta; tylko spowalnia —
minimum 1,5 s, a gdy robots.txt podaje `Crawl-delay`, obowiązuje on). Nieznane parametry są zachowywane (dla `custom`).

### Jak działa pobieranie (implementacja: `backend/prawdowid/sources/`)
- `max_items` = ile najnowszych pozycji listy/kanału/mapy sprawdzamy w jednym uruchomieniu; adresy już zapisane w korpusie
  nie są pobierane ponownie. Nowe rekordy są scalane z plikiem (`id` i `url` bez duplikatów, od najnowszych, limit `max_docs`),
  zapis atomowy. `id` rekordu = `<id źródła>:<sha1(url)[:12]>`, `source_type` = `category`, `license`/`language`/`publisher`
  z pliku źródła, `tags` = id źródła + `topics`; tekst i data z trafilatury (dla gov.pl — parser gov.pl).
- Grzeczność: UA `PrawdowidHackathonBot/0.1 (research prototype)`, robots.txt sprawdzany dla każdego adresu (także po
  przekierowaniu; niedostępny robots.txt = nie pobieramy; reguły wg RFC 9309 — wygrywa najdłuższa pasująca reguła, przy
  remisie `Allow`; `backend/prawdowid/robots.py`, wspólne z `ingest/official_common.py` i wyszukiwaniem na żywo), ochrona SSRF, ponawianie przy 429/5xx. CAPTCHA, test antybotowy,
  HTTP 401/403 lub uporczywe 429 przerywają uruchomienie (status `error`) — zabezpieczeń nie obchodzimy.
- Harmonogram (wątek w procesie API, `PRAWDOWID_SCHEDULER=1` domyślnie): co minutę uruchamia — po kolei, jedno naraz —
  włączone źródła z metodą pobierającą, dla których od ostatniej próby minęło `schedule_hours` (po błędzie: najwyżej 2 h).
  Przed pierwszym uruchomieniem z rejestru za „ostatnią próbę” uznaje się czas modyfikacji pliku korpusu. Potem przeładowuje
  indeks, jeśli zmienił się zestaw plików do indeksowania (nowe dokumenty, włączenie/wyłączenie, zmiana z CLI lub ręczna).
- Indeks ładuje pliki korpusu źródeł z `enabled: true` **oraz pliki bez wpisu w rejestrze** (nic nie znika po cichu).
  Usunięcie źródła w panelu przenosi jego korpus do `data/corpus/archive/`.
- `live_search`, `google_factcheck`, `reference_only` nie są pobierane według harmonogramu.
- CLI (z `backend/`): `python -m prawdowid.sources list | run <id> | run --due | run --all | test <id> | suggest <url> | validate | scope [--strict] [--restrict]`.
- Głębsze pobranie historii (ostatnie miesiące) źródeł z listy organizatora, tymi samymi funkcjami i zasadami grzeczności:
  `python ingest/backfill_organiser_sources.py <grupa>` — uruchomienie według harmonogramu sprawdza tylko najnowsze
  pozycje listy (`max_items`), więc historia sprzed dodania źródła wymaga jednorazowego przejścia po stronach listy.
- Panel `/admin` (token `PRAWDOWID_ADMIN_TOKEN`, nagłówek `X-Admin-Token`): dodawanie z „Wykryj automatycznie”
  (gov.pl → RSS z `<link rel=alternate>` → mapa strony → `html_list` z heurystycznym wzorcem linków), „Testuj” (3 rekordy,
  nic nie jest zapisywane), „Zapisz”, „Uruchom teraz”, włącz/wyłącz. API: `/api/admin/*` (opis: `docs/DATA_MODEL.md`).
- Walidacja zapisu: `id` `[a-z0-9_]{2,64}`, wymagane `name`, `publisher`, `url`, `license`, `qualification`, poprawna
  `category`/`method`/`tier`, wymagane parametry metody, tematy ze słownika.

### Słownik tematów (`topics`)
`podroze`, `pogoda`, `woda_powodz`, `drogi`, `kolej`, `lotnictwo`, `morze`, `transport`, `zdrowie`, `zywnosc`,
`promieniowanie`, `powietrze`, `cyber`, `oszustwa`, `bezpieczenstwo`, `obronnosc`, `pozary`, `prawo`,
`statystyka`, `finanse`, `wybory`, `ue`, `dezinformacja`, `zagranica`, `rzad`

## Rekord korpusu (`data/corpus/<id>.jsonl`, jedna linia = jeden dokument)
Pola jak `SourceDoc` w `backend/prawdowid/schemas.py`: `id`, `source_type`, `publisher`, `domain`, `url`, `title`,
`published_at` (data publikacji), `retrieved_at` (czas pobrania, UTC), `language`, `license`, `text`, opcjonalnie
`claim`, `claim_author`, `verdict_raw`, `verdict` (`true|false|misleading|mixed|unverifiable`), `tags`.
