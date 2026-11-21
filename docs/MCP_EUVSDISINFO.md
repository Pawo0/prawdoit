# EUvsDisinfo MCP — pobieranie przypadków i analiz

## Co to jest
Organizatorzy HackNation 2026 udostępniają serwer MCP z bazą **EUvsDisinfo** (EEAS East StratCom Task Force):
`https://euvsdisinfo-mcp-server.vercel.app/mcp`. Transport to **streamable HTTP**, nie SSE: każde żądanie to `POST`, a
odpowiedź przychodzi jako `application/json` albo `text/event-stream` z liniami `data:`. Serwer ma dwa narzędzia,
oba z argumentami `{offset, limit ≤ 100}`:

| narzędzie | zawartość | ok. liczba |
|---|---|---|
| `cases` | przypadki dezinformacji: `claim` (teza), `fact` (obalenie), `date` (unix), `keywords`, `countries`, `linksToDisinformation`, `url` | 19 tys. |
| `articles` | analizy EUvsDisinfo: `title`, `content` (HTML), `dateGmt`, `articleLanguage`, `categories`, `url` | 6,7 tys. |

Specyfikacja z przykładami: `pdftotext -layout rules/How_to_grab_all_Articles_and_Cases_from_disinfo.pdf -`.

**Licencja i atrybucja.** Treści EUvsDisinfo (EEAS) wolno ponownie wykorzystywać pod warunkiem podania źródła
(nota prawna EEAS, decyzja Komisji 2011/833/UE). Treści stron trzecich są wyłączone. Każdy rekord ma pole `license`
i `publisher` = „EUvsDisinfo (EEAS East StratCom Task Force)”, a w interfejsie cytujemy je z linkiem do
`euvsdisinfo.eu/report/...`. Linki do mediów, które szerzą dezinformację (`linksToDisinformation`), trafiają
**wyłącznie** do surowego zrzutu `data/raw/euvsdisinfo_mcp/`. To materiał obalany, więc nigdy nie służy jako dowód.

## Token
Bez tokenu serwer odpowiada `HTTP 401` z błędem JSON-RPC `-32001`: *„Unauthorized: API key required. Provide via
?key=YOUR_KEY, Authorization header, or X-API-Key header”*. Przy złym tokenie zwraca *„Unauthorized: Invalid API key”*.
Sprawdzone 2026-11-21. Używamy nagłówka `Authorization: Bearer …`. Token w `?key=` ląduje w logach, więc go nie używamy.

```bash
read -rs PRAWDOWID_EUVSDISINFO_TOKEN && export PRAWDOWID_EUVSDISINFO_TOKEN   # wklej token, nie trafi do historii
```

- Token podajemy **tylko** przez zmienną środowiskową. Nie wpisujemy go do repo, do `data/sources/*.json`, do
  `.mcp.json` ani do zgłoszeń. Plik rejestru zawiera jedynie nazwę zmiennej (`params.token_env`).
- Zmienna musi być ustawiona w środowisku procesu backendu (uvicorn albo harmonogram). Po ustawieniu trzeba go
  zrestartować. Dopóki jej nie ma, źródło raportuje „brak tokenu” i nic nie wysyła.

## Szybki test (probe)
```bash
cd backend
.venv/bin/python -m prawdowid.source_handlers.euvsdisinfo_mcp --probe
```
Probe wykonuje kolejno: `initialize`, `tools/list`, pobranie 1 przypadku i 1 artykułu, a następnie ostatniego
elementu każdej listy (żeby pokazać kolejność dat). Na koniec drukuje podsumowanie i przykładowy rekord korpusu.
Kody wyjścia: `0` OK, `1` błąd sieci/serwera, `2` brak tokenu (wtedy sprawdza tylko, czy serwer odpowiada 401),
`3` token odrzucony.

Ręczny zrzut do pliku (parametry domyślne bierze z rejestru, nadpisujemy je flagami):
```bash
.venv/bin/python -m prawdowid.source_handlers.euvsdisinfo_mcp --dump 200 /tmp/euvsdisinfo_mcp.jsonl \
    --kinds cases --since 2024-01-01 --countries Poland      # N=0 → wszystko; --no-raw bez surowego zrzutu
```

## Jak to pobieramy
- **Rejestr:** `data/sources/euvsdisinfo_mcp.json`, `method: "custom"`, `params.handler: "euvsdisinfo_mcp"`.
  Wywoływana jest funkcja `fetch(source)` z `backend/prawdowid/source_handlers/euvsdisinfo_mcp.py`.
  Pozostałe ustawienia: kategoria `incident`, tier 3, harmonogram co 24 h, `enabled: true`.
  Wynik trafia do `data/corpus/euvsdisinfo_mcp.jsonl`, a stan uruchomień do SQLite (`source_runs`).
- **Panel `/admin`** edytuje ten plik: włączenie i wyłączenie, parametry, ręczne uruchomienie. Błąd „brak tokenu”
  albo „odrzucił dostęp” widać tam jako status ostatniego uruchomienia.
- **Przebieg:** `initialize` → nagłówek `mcp-session-id` → `notifications/initialized` → `tools/call` strona po
  stronie (100 na stronę, 1 s przerwy między wywołaniami), aż do `hasNextPage: false`. Ponowienia z wykładniczym
  backoffem (sieć, 429, 5xx, z poszanowaniem `Retry-After`). Gdy serwer zgubi sesję, klient raz ją odnawia.
  Kolejność dat na serwerze jest nieznana, dlatego każde uruchomienie przegląda całość: ok. 260 wywołań, ~5 min.
- **Filtry (`params`):**
  - `kinds`: domyślnie `["cases","articles"]`.
  - `since`: domyślnie `"2023-01-01"`, `null` wyłącza filtr dat.
  - `max_records`: łączny limit, `null` = bez limitu.
  - `article_languages`: domyślnie `["pl","en"]`.
  - `countries`: opcjonalny, np. `["Poland"]` dla przypadków.
  - Dodatkowo `page_size`, `delay`, `endpoint`, `token_env`.
- **Mapowanie:**
  - Przypadek → `source_type: incident`. `claim` to teza dezinformacji, `text` to obalenie (`fact`),
    `verdict: false`, `verdict_raw: "Disinformation (EUvsDisinfo)"`, `published_at` pochodzi z `date`.
    Tagi to słowa kluczowe, `kraj:<X>` i `via:mcp`.
  - Artykuł → `source_type: factcheck`, z HTML usuniętym z `content`.
  - Przypadki bez obalenia pomijamy, bo sama teza nie może być dowodem.
- **Deduplikacja:** identyfikatory `euvsdisinfo:<slug z /report/<slug>/>` są takie same jak w
  `ingest/harvest_euvsdisinfo.py`. Indeks bierze pierwszy rekord o danym `id`, a `euvsdisinfo.jsonl` jest czytany
  przed `euvsdisinfo_mcp.jsonl`, więc istniejące 300 przypadków nie dubluje się. Artykuły mają identyfikatory
  `euvsdisinfo:article/<ścieżka URL>`.
- **Surowe dane:** `data/raw/euvsdisinfo_mcp/{cases,articles}.jsonl.gz` zawierają pełne odpowiedzi, łącznie z
  linkami do mediów. Uruchomienie przerwane limitem `max_records` zapisuje `*.sample.jsonl.gz`. Plik `last_run.json`
  zawiera statystyki: pobrane, odrzucone wg powodu, liczbę żądań i ponowień.
- **Testy offline** (bez tokenu i sieci, na przykładach z PDF): `backend/.venv/bin/python backend/tests/test_euvsdisinfo_mcp.py`

## Surowe zapytania (curl)
```bash
MCP=https://euvsdisinfo-mcp-server.vercel.app/mcp
H=(-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream"
   -H "Authorization: Bearer $PRAWDOWID_EUVSDISINFO_TOKEN")

# 1. initialize — zapamiętaj nagłówek mcp-session-id
SID=$(curl -sS -D - -o /dev/null -X POST "$MCP" "${H[@]}" -d '{"jsonrpc":"2.0","id":0,"method":"initialize",
  "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}' \
  | awk -F': ' 'tolower($1)=="mcp-session-id"{print $2}' | tr -d '\r'); echo "$SID"

# 2. notifications/initialized (odpowiedź 202, bez treści)
curl -sS -X POST "$MCP" "${H[@]}" -H "mcp-session-id: $SID" -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. tools/list
curl -sS -X POST "$MCP" "${H[@]}" -H "mcp-session-id: $SID" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 4. tools/call — strona 3 przy limit=10 → offset=20 (dla artykułów: "name":"articles")
curl -sS -X POST "$MCP" "${H[@]}" -H "mcp-session-id: $SID" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call",
  "params":{"name":"cases","arguments":{"offset":20,"limit":10}}}'
```
Odpowiedź w formacie `text/event-stream` zawiera JSON w linii `data:`. Dane są w `result.structuredContent`
(`total`, `cases`/`articles`, `hasNextPage`), a krótki opis tekstowy w `result.content[]`.

## Claude Code — eksploracja interaktywna
```bash
claude mcp add --transport http euvsdisinfo https://euvsdisinfo-mcp-server.vercel.app/mcp \
    --header "Authorization: Bearer $PRAWDOWID_EUVSDISINFO_TOKEN"
claude mcp list            # w sesji: /mcp
```
Domyślny zakres `local` zapisuje token w `~/.claude.json`, czyli poza repo. **Nie używaj** `-s project` z wpisanym
tokenem, bo trafiłby do `.mcp.json` w repo. Jeśli konfiguracja ma być w repo, w `.mcp.json` wpisz
`"headers": {"Authorization": "Bearer ${PRAWDOWID_EUVSDISINFO_TOKEN}"}` (Claude Code rozwija zmienne).
Przykładowe polecenie: *„Pobierz przez euvsdisinfo 20 przypadków od offsetu 0 i wypisz te dotyczące Polski”*.

**Nasz serwer MCP** (`bots/mcp_server.py`, stdio, tylko odczyt) udostępnia następujące narzędzia:
- `sprawdz` — weryfikacja przez `/api/check`;
- `katalog_zrodel`;
- `kurs_nbp`;
- `akt_prawny` i `szukaj_aktow` — Sejm ELI.

Dodanie do Claude Code:
`claude mcp add prawdowid -e PRAWDOWID_API=http://localhost:8000 -- "$PWD/backend/.venv/bin/python" "$PWD/bots/mcp_server.py"`
