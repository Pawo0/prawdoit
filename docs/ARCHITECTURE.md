# Prawdowid — architektura

Szczegóły implementacji, przepływ żądania i opis każdego modułu: [przewodnik backendu](backend/README.md).

```
 KANAŁY (cienkie adaptery, bez logiki weryfikacji)            RDZEŃ WERYFIKACJI (jeden dla wszystkich kanałów)
 ┌──────────────────────────┐
 │ Strona WWW / PWA          │──┐   POST /api/check     ┌──────────────────────────────────────────────────┐
 │ (Web Share Target Android)│  │                       │ 1. Wejście: walidacja, limit, maskowanie PII     │
 ├──────────────────────────┤  │                       │    URL → bezpieczne pobranie (SSRF guard)        │
 │ Wtyczka przeglądarki      │──┤   POST /api/quick     │    + ekstrakcja treści (trafilatura)             │
 │ (Chrome/Edge/Vivaldi,     │  │   (router) + /check   │ 2. Skan prompt-injection → neutralizacja + log   │
 │  Firefox Android)         │  │                       │ 3. Twierdzenia: podział na zdania, fakty vs      │
 ├──────────────────────────┤  │                       │    opinie/prognozy, check-worthiness             │
 │ WhatsApp Cloud API webhook│──┤   /webhooks/whatsapp  │ 4. Wyszukiwanie hybrydowe: BM25 + embeddingi     │
 │ Messenger webhook         │──┤   /webhooks/messenger │    (mmlw-retrieval-e5-small) + dopasowanie do    │
 │ Adapter demo (czat WWW)   │──┤   (?demo=1)           │    twierdzeń już sprawdzonych (PFCR)             │
 │ Discord bot (proces)      │──┘   POST /api/chat-reply│ 5. Fragment dosłowny (bramka V2) + stanowisko:   │
 └──────────────────────────┘                          │    NLI mDeBERTa-v3 / reguła liczbowa (dane GUS…) │
                                                        │ 6. Werdykt: reguły R1–R6 + R3a/M1/M2/G1/HR       │
 ┌──────────────────────────┐                          │ 7. Wyjaśnienie z szablonu (opcj. LLM tylko       │
 │ Panel analityka           │◄── /api/cases ───────────│    upraszcza język; walidacja wyjścia)           │
 │ (sprawy, metryki, eksport)│                          │ 8. Zapis przebiegu (SQLite), sprawy moderatora   │
 └──────────────────────────┘                           ├──────────────────────────────────────────────────┤
                                                        │ 4b. WYSZUKIWANIE NA ŻYWO (równolegle z 4.)       │
 ┌──────────────────────────┐                           │    (websearch.py, budżet ~15 s): Google Fact     │
 │ Panel źródeł /admin       │── /api/admin/* ──┐       │    Check API + wyszukiwarki zaufanych serwisów   │
 │ (token X-Admin-Token)     │                  │       │    z rejestru → fetch (SSRF, robots.txt) → skan  │
 └──────────────────────────┘                  ▼        │    injection → te same bramki V2/NLI/R1–R6       │
 REJESTR ŹRÓDEŁ data/sources/<id>.json ──► HARMONOGRAM  │    → data/corpus/live_web.jsonl                  │
 (licencja, kwalifikacja, schedule_hours,  (sources/,   │                                                  │
                                                        └──────────────────────────────────────────────────┘
  web_search, enabled)                      co N h) → pobiera (rss / sitemap / html / handler / skrypt)
        │ lista domen dla 4b                          │
        ▼                                             ▼
 KORPUS data/corpus/<id>.jsonl (jeden schemat) → indeks (przeładowanie bez restartu) → rdzeń
   kat. A: Odyseusz MSZ, gov.pl (RCB, RSO, MSWiA, PSP, GIS, PAA, MI, MON, KPRM…), IMGW, CERT, Policja, urzędy morskie,
           ISAP/ELI, EUR-Lex, GUS/BDL, NBP, dane.gov.pl, Eurostat, PKW, KE PL
   kat. B: Demagog, FakeNews.pl, Stowarzyszenie Pravda, Konkret24, EUvsDisinfo (+ MCP), CheckFirst
```

## Przepływ danych
1. **Wejście** (tekst ≤ 6000 znaków lub URL). Bezpośrednie identyfikatory osób prywatnych (PESEL, nr dowodu
   i paszportu, telefon, nr konta, prywatny e-mail) są maskowane **raz, na początku** `run_check` — przed
   wyodrębnieniem twierdzeń — w tekście, w tekście z OCR i w treści pobranej strony; dalsze etapy (wyszukiwanie,
   zapytania na żywo, opcjonalny LLM, `result_json`, kolejka moderatora) widzą tylko znaczniki `[PESEL]`, `[TELEFON]`…,
   a zapytania wyszukiwania nie zawierają nawet znaczników. Nazwisk, nazw, miejsc, dat, kwot i statystyk nie maskujemy
   (zasada w [COMPLIANCE](COMPLIANCE.md#ochrona-danych-osobowych)); adresy URL zostają bez zmian, by dało się je pobrać. Strona z URL jest pobierana z ochroną SSRF (tylko publiczne IP, limity rozmiaru/czasu, ręczna obsługa
   przekierowań), treść traktowana jako **niezaufane dane**.
2. **Bezpieczeństwo**: wzorce poleceń (PL/EN, tokeny szablonów czatu, ukryte znaki) → zdarzenie `prompt_injection`
   w dzienniku + neutralizacja fragmentu. Instrukcje są kodem, treść jest danymi — żaden tekst nie zmienia reguł.
3. **Twierdzenia**: do 3 najbardziej „sprawdzalnych” zdań (liczby, nazwy własne, czasowniki faktów); krótki tekst
   (≤ 2 zdania i ≤ 400 znaków) to zawsze jedno twierdzenie (`claims._extract`); opinie i prognozy
   → „nie podlega weryfikacji”; pytania („Czy…?”) zamieniane na twierdzenia. Prośba o wykonanie zadania zamiast
   informacji („napisz wiersz…”, „przetłumacz…”, „wygeneruj kod…”, bez słów typu „czy”, „prawda”, „sprawdź”) dostaje
   status `poza_zakresem` bez werdyktu (`textutil.is_task_request`); brak sprawdzalnego zdania → `doprecyzuj`.
4. **Wyszukiwanie**: hybryda BM25 (prosty stemming prefiksowy dla polskiego) + gęste embeddingi, fuzja RRF; osobny
   indeks twierdzeń sprawdzonych przez fact-checkerów. Kandydatem jest twierdzenie z cos ≥ 0,68
   (`claim_match_soft` 0,74 − 0,06). O tym, czy to **to samo** twierdzenie, decyduje `engine.claim_match` (progi
   w kodzie): cos ≥ 0,86 i entailment NLI ≥ 0,5 (≥ 0,8 dla baz incydentów) albo cos ≥ 0,80, entailment ≥ 0,8 i wspólne
   słowa ≥ 0,4; samo podobieństwo cos ≥ 0,88 tylko wtedy, gdy nazwy i liczby się zgadzają (reguła G1); sprzeczność NLI
   ≥ 0,5 w którąkolwiek stronę blokuje „to samo”, a cos ≥ 0,85 ze sprzecznością ≥ 0,80 w obie strony oznacza
   twierdzenie przeciwne. Poniżej tych progów dopasowanie jest tylko kontekstem.
5. **Dowody**: dla każdego źródła wybierany jest 1–2-zdaniowy fragment najbardziej zbieżny z twierdzeniem; ten sam
   fragment jest cytowany i oceniany. Cytat jest wycinany dosłownie z zapisanego tekstu źródła (V2: z konstrukcji, sprawdzane testem). Stanowisko: NLI (≥ 0,70)
   albo deterministyczne porównanie liczb z kartą danych urzędowych dla tego samego okresu. Fact-check: werdykt
   organizacji + kontrola, czy użytkownik nie twierdzi czegoś przeciwnego (NLI sprzeczności → odwrócenie oceny).
6. **Werdykt**: reguły R1–R6 (opis: `/metodologia`), siła podstaw jako tekst (mocna/umiarkowana), przesłanki,
   kody przyczyn wstrzymania, „co mogłoby to rozstrzygnąć”, ostrzeżenie o materiale archiwalnym. Reguły uzupełniające
   (w `rules_fired`): **R3a** — fałsz, bo materiał jest starszy, niż twierdzi tekst (kontekst `FALSZYWY_KONTEKST`);
   **M1** — dopasowanie do jednego zdania sprawdzonej wypowiedzi; **M2** — „czy to ten sam materiał” (porównanie
   nagłówka i daty linku z analizami, `provenance.py`); **G1** — bardzo podobne twierdzenie odrzucone, bo różni się
   nazwą lub liczbą; **HR** — temat wysokiego ryzyka z jednym źródłem kat. B → sprawa dla analityka.
   Krótka odpowiedź (`short_answer`, `answer.py`) jest zawsze z szablonu; opcjonalny LLM zmienia tylko pole
   `explanation`, a jego tekst odrzucamy, gdy dodaje liczby lub linki.
4b. **Wyszukiwanie na żywo** (`PRAWDOWID_LIVE_SEARCH=0` wyłącza). Google Fact Check API (tylko z kluczem; tylko
   recenzje z domen rejestru stają się dowodem) startuje **równolegle z wyszukiwaniem lokalnym** dla każdego twierdzenia
   faktycznego; gdy coś zwróci, wszystkie twierdzenia są oceniane ponownie. Wyszukiwarki samych zaufanych serwisów
   działają tylko dla twierdzeń, które po bazie zostały bez dowodu (najwyżej 2, `MAX_FALLBACK_CLAIMS`):
   (gov.pl, WordPress REST: Demagog, FakeNews.pl, CheckFirst; opcjonalnie SearXNG/Brave z filtrem `site:`). Każdy serwis
   ma jeden zegar (robots.txt + zapytania, 7 s), potem ≤ 5 stron jest pobieranych (SSRF, robots.txt, skan injection) i
   ocenianych tymi samymi regułami. Wynik służy tej odpowiedzi; zapis w `live_web.jsonl` jest domyślnie wyłączony (`PRAWDOWID_LIVE_PERSIST_DAYS`, najwyżej 30 dni). Awaria/timeout → komunikat
   „…jest teraz niedostępny (błąd techniczny)…”, nigdy werdykt. Gdy krok nie działał (brak klucza Google, wyszukiwanie
   wyłączone na serwerze lub w tym żądaniu, LLM niedostępny lub odrzucony w walidacji), wynik mówi to wprost:
   `engine.unavailable`, `live_search.status = "nieaktywne"`, `engine.llm_status`, wiersz „Nie użyto: …” w interfejsie.
   Szczegóły: nagłówek `backend/prawdowid/websearch.py`.
7. **Pętla informacji**: nierozstrzygnięte twierdzenia faktyczne i tematy wysokiego ryzyka z jednym źródłem →
   sprawa w kolejce analityka; podobne zgłoszenia (cos ≥ 0,86) łączone w jedną sprawę z licznikiem i priorytetem.
8. **Audyt**: każde sprawdzenie (ID, czas, kanał, zamaskowane wejście, źródła, werdykty, czasy etapów, modele,
   wersja reguł, zdarzenia bezpieczeństwa, przebieg wyszukiwania na żywo, szacunkowy koszt) w SQLite; retencja 30 dni;
   usuwanie sesji; eksport CSV/JSON. Model danych: [DATA_MODEL](DATA_MODEL.md).
9. **Źródła**: rejestr `data/sources/<id>.json` (kontrakt: [SOURCE_REGISTRY](SOURCE_REGISTRY.md)) steruje tym, co jest
   pobierane, indeksowane i przeszukiwane na żywo; harmonogram w procesie API pobiera źródła co `schedule_hours`,
   a indeks przeładowuje się bez restartu. EUvsDisinfo przez MCP: [MCP_EUVSDISINFO](MCP_EUVSDISINFO.md).

## Wtyczka: dwa poziomy — router (`/api/quick`) i pełne sprawdzenie (`/api/check/async`)
Projekt i uzasadnienie: `research/09_architecture_two_tier_and_containers.md` §3. Zasada: wtyczka **nie ocenia treści
po stylu, źródle ani „podejrzanym” wyglądzie**. Poziom 1 tylko kieruje ruchem, a wszystko, co widzi użytkownik, ma
nazwane źródło.

**Ręczne sprawdzanie.** Lupka → kliknięcie/dotknięcie treści od razu uruchamia pełne sprawdzenie, bez dodatkowego
zatwierdzenia. Wtyczka zaczyna zadanie (`POST /api/check/async`) i co 0,7 s odpytuje `GET /api/jobs/{id}`; okno
w Shadow DOM pokazuje etap podawany przez serwer („Szukam w bazie…”, „…przeszukuję zaufane strony…”), potem wynik,
cytaty i link do pełnej analizy. Żadne żądanie nie czeka na cały wynik: Chrome zatrzymuje service worker rozszerzenia,
gdy odpowiedź na `fetch()` nie przychodzi przez 30 s (dokumentacja „extension service worker lifecycle”), a sprawdzenie
z pobraniem strony i wyszukiwaniem na żywo może trwać dłużej. Odpytuje strona (krótkie wiadomości do tła), więc
uśpienie workera niczego nie przerywa. Serwer bez API zadań (404/405/501) dostaje dawne, synchroniczne
`POST /api/check` (limit 45 s) — tylko dla sprawdzeń ręcznych. Zamknięcie okna lub nowy wybór unieważnia poprzednią
odpowiedź w interfejsie; nie anuluje analizy na serwerze. Esc zamyka okno/anuluje wybieranie; błąd techniczny i limit
zapytań są komunikowane osobno i można ponowić.

**Poziom 1 — router.** Na obsługiwanych stronach (po zgodzie) wtyczka wysyła **tylko tekst** widocznych postów/nagłówków
(bez URL strony, bez ciasteczek, bez identyfikatora użytkownika), paczkami ≤ 16 fragmentów, kolejną dopiero po odpowiedzi
na poprzednią. Serwer (`service.quick_score`): embedding zdań → najbliższe twierdzenie ocenione przez fact-checkera
jako fałsz / manipulacja / częściowy fałsz → od cos ≥ 0,80 NLI i wspólna reguła `engine.same_claim` (to samo
twierdzenie, a nie zaprzeczenie; poniżej 0,80 reguła nie może dać dopasowania, więc NLI nie jest liczone).
Odpowiedź dla każdego fragmentu ma pole `state`:

| `state` | Kiedy | Co widzi użytkownik | Co dalej |
|---|---|---|---|
| `none` | nic sprawdzalnego (opinia, za krótki tekst) | nic | — |
| `candidate` | zdanie faktyczne, które pełne sprawdzenie mogłoby ocenić; `priority` 0–1 porządkuje kolejkę: bliskość ocenionego twierdzenia (cos 0,74–…, `NEAR_MISS`) > temat wysokiego ryzyka > „sprawdzalność” zdania | **nic** | po włączeniu opcji: najwyżej 3 na stronę trafiają w tle do poziomu 2 w trybie `auto` |
| `match` | tekst powtarza twierdzenie ocenione przez nazwanego fact-checkera (`match`: wydawca, ocena, data, link) | oznaczenie: „Podobna informacja: Demagog — „Fałsz” (02.03.2026) ↗” + „Sprawdź” | kliknięcie „Sprawdź” = pełne sprawdzenie ręczne |

- **Reguła konfliktu.** Jeżeli twierdzenie ocenione jako *prawda* jest równie blisko tekstu (cos w granicach 0,03 od
  obalonego), oznaczenia nie ma: fact-checkerzy ocenili niemal identyczne zdania różnie, a samo podobieństwo nie
  rozstrzyga, które z nich tekst powtarza. Fragment staje się kandydatem (`conflict`, `CONFLICTING_RATINGS`).
- `match` bez wydawcy, oceny, daty lub linku nie jest pokazywany. Pola `risk`/`level` zostały dla starszych wersji
  wtyczki (`level != "brak"` dokładnie wtedy, gdy `state == "match"`); procent ani „ryzyko” nie są nigdzie wyświetlane.
- Wynik jest cache'owany po haszu tekstu do następnego przeładowania indeksu. Naraz liczy się jedna paczka
  (`PRAWDOWID_QUICK_CONCURRENCY`); gdy serwer jest zajęty dłużej niż 3 s, odpowiada 503 z `Retry-After`, a przy limicie
  429 z `Retry-After` — wtyczka czeka wskazany czas i **nigdy nie rysuje oznaczenia z błędu**.

**Poziom 2 w tle — tryb `auto`** (`POST /api/check/async` z `mode: "auto"`; we wtyczce **opcja, domyślnie
wyłączona** — patrz pomiar niżej). Ten sam potok co sprawdzenie ręczne
(te same reguły R1–R6 i dowody), ale tylko na lokalnej bazie i bez śladu po tekście:
- bez wyszukiwania na żywo (wysłałoby treść twierdzenia do zewnętrznych wyszukiwarek), bez pobierania linków z tekstu,
  bez LLM;
- bez sprawy moderatora — bierne przeglądanie nie zapełnia kolejki analityka;
- w dzienniku zostaje wiersz bez tekstu: `sha256` treści, kanał `extension-auto`, werdykt, użyte źródła, czasy;
  retencja 7 dni (`PRAWDOWID_AUTO_RETENTION_DAYS`); zdarzenie prompt-injection jest odnotowane bez cytowanego fragmentu;
- wynik zadania znika z pamięci serwera po pierwszym odebraniu; zadania `auto` mają osobny, jednowątkowy wykonawca
  (nie zajmują miejsca sprawdzeniom ręcznym), krótką kolejkę i własny limit (20/min na adres).

Wtyczka pokazuje oznaczenie z poziomu 2 **tylko** dla rozstrzygającego werdyktu (fałszywe / wprowadzające w błąd,
bez sprzecznych źródeł) z cytowanym, podlinkowanym źródłem: „Źródła przeczą tej informacji: FakeNews.pl, 14.05.2025 ↗”.
„Brak dowodów”, opinia, błąd techniczny i przekroczony limit nie pokazują nic. Sprawdzenie ręczne tego samego fragmentu
(z wyszukiwaniem na żywo) zastępuje oznaczenie automatyczne. Wtyczka uruchamia sprawdzenia w tle tylko wobec serwera,
który zwraca `state` — starszy serwer potraktowałby je jak zwykłe sprawdzenia.

**Zasłona** („kliknij, aby odsłonić”) jest ustawieniem do włączenia w panelu; domyślnie jest samo oznaczenie.

**Pomiar** na danych z repozytorium (`backend/.venv/bin/python eval/measure_router.py --tier2`; wyniki i warunki:
`eval/results/router_measure.md`): poziom 1 kieruje dalej 100 % przeformułowań obalonych twierdzeń (159/159),
od razu oznacza 68 % (108/159) i nie oznaczył żadnego z 569 tekstów, które oznaczenia mieć nie powinny (trudne
negatywy, twierdzenia ocenione jako prawda, zdania z komunikatów urzędowych). Bramka NLI 0,80 zamiast 0,74: te same
wyniki, 36–64 % mniej wywołań NLI. Stan `candidate` prawie niczego nie odsiewa (99 % zdań urzędowych) — jest filtrem
kosztu, nie sygnałem. Sprawdzenie w tle dodaje oznaczenia dla co najmniej 19 z 159 przeformułowań, ale pełny potok
wydaje też błędny werdykt „źródła przeczą” dla 3,7 % zwykłych zdań urzędowych (11/300), 2,4 % twierdzeń ocenionych
jako prawda (3/127) i 26 % trudnych negatywów (7/27). Przy sprawdzeniu na życzenie użytkownik widzi źródła i sam
ocenia; jako nieproszone oznaczenie to za dużo — dlatego sprawdzanie w tle jest opcją do włączenia w panelu wtyczki
(`autoVerify` w `extension/background.js`), do czasu poprawy reguły dopasowania w silniku.

## Modele i dostawcy (wszystko lokalnie, CPU)
| Rola | Model | Licencja | Uwagi |
|---|---|---|---|
| Embeddingi (wyszukiwanie, dopasowanie twierdzeń) | `sdadas/mmlw-retrieval-e5-small` | Apache-2.0 | polski, 33M param. backbone; fp32 na CPU (wagi fp16 są ~15× wolniejsze) |
| Stanowisko (NLI) | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | MIT | wielojęzyczny, zawiera polski |
| LLM (opcjonalnie) | dowolny OpenAI-compatible: Bielik / PLLuM przez llama.cpp lub vLLM, Mistral (UE) | — | tylko upraszczanie języka; wyłączony domyślnie |

Wymiana modelu = zmiana zmiennej środowiskowej (`PRAWDOWID_EMBED_MODEL`, `PRAWDOWID_NLI_MODEL`, `PRAWDOWID_LLM_*`).
Kanały, korpus i reguły są niezależne od modelu.

## Najważniejsze ograniczenia
- Zamknięty katalog źródeł (+ wyszukiwanie na żywo tylko w nim): brak wyniku ≠ prawda/fałsz; nowe wydarzenia
  (< kilka godzin) zwykle → „brak dowodów”. Wyszukiwarki serwisów są wolne (2–6 s) i ubogie (tytuły) — część trafień ginie.
- NLI na CPU jest słabe w porównywaniu liczb i dat — dlatego reguła liczbowa dla kart danych urzędowych.
- Dopasowanie do fact-checków działa na poziomie twierdzeń; satyra, ironia i bardzo krótkie posty mogą być mylone.
- Facebook/X zmieniają strukturę DOM — adaptery wtyczki wymagają utrzymania (fallback: przycisk „Wybierz fragment”).
- OCR zrzutów ekranu działa lokalnie (Tesseract, `ocr.py`; bez pliku `tesseract` → błąd techniczny). Data widoczna na
  zrzucie nie jest traktowana jako data publikacji. Wyszukiwania wcześniejszych wystąpień obrazu nie ma.

## Discord

Bot jest uruchamiany przez entrypoint kontenera po gotowości API, jeśli ustawiono token Discorda.
Wysyła tekst do `/api/chat-reply`; wynik przechodzi przez ten sam `run_check` co WWW.
Obsługuje limity per użytkownik, pojedyncze aktywne zgłoszenie na użytkownika, `/usun_sesje`,
komunikaty o nieobsługiwanych załącznikach i dzielenie długich odpowiedzi bez obcinania analizy.
Opcjonalne alerty o priorytetowych sprawach są kierowane na wskazany prywatny kanał moderatorów,
z potwierdzeniami wysyłek w trwałym wolumenie. [Uruchomienie i ograniczenia](DISCORD.md).

## Interfejs rozszerzenia
- Główne wejście: stale widoczna lupka „Sprawdź” w prawym dolnym rogu zwykłych stron HTTP/HTTPS.
  Wymaga przyznanego dostępu do witryn; strony wewnętrzne przeglądarki i inne chronione strony nie pozwalają na wstrzyknięcie skryptu.
  Interfejs przywraca swój element po usunięciu przez stronę. Wstrzymanie ostrzeżeń nie usuwa lupki.
- Kliknięcie lupki od razu uruchamia wybór fragmentu — bez menu pośredniego. Escape anuluje wybór.
- Panel na pasku przeglądarki: oznaczenia przy treściach (wł./wył.), sprawdzanie w tle do 3 fragmentów na stronę
  (domyślnie wyłączone), zasłony (domyślnie wyłączone), tryb demonstracyjny i adresy serwera/strony.
- Automatyczny skan pozostaje ograniczony do dotychczas obsługiwanych portali, mediów społecznościowych i lokalnego demo.
  Na pozostałych witrynach treść jest wysyłana dopiero po ręcznym wyborze. Na obsługiwanych stronach automatyczny skan
  zaczyna się po zaakceptowaniu informacji o działaniu (mówi o sprawdzaniu w tle, gdy jest włączone) lub wcześniejszym
  zapisaniu zgody.
- Oznaczenie to pasek w prawym górnym rogu fragmentu: tekst jest linkiem do publikacji źródłowej (wydawca, ocena, data),
  obok przycisk „Sprawdź”. Pełne zdanie („Podobną informację … ocenił(a) jako … To dopasowanie treści, a nie pełna
  weryfikacja”) jest w podpowiedzi i etykiecie dostępności. Przy krótkich fragmentach (nagłówek, jednowierszowy wpis)
  wtyczka dodaje nad nimi miejsce zamiast zasłaniać tekst. Bez koloru ostrzegawczego, bez wykrzyknika, bez procentów.
- Wszystkie powierzchnie używają kremowego tła, kobaltu, ostrych ramek i nagłówków inspirowanych Macintoshem.
  Geist Pixel Square 1.9.2 jest dołączony lokalnie (SIL OFL, `extension/fonts/LICENSE.txt`); font nie jest pobierany z CDN.
  Dłuższe teksty pozostają w systemowym kroju sans-serif. Zasłony (opcja) informują o dopasowaniu do znanego fact-checku,
  podają link do publikacji, nie przedstawiają dopasowania jako pełnej weryfikacji i zawsze umożliwiają odsłonięcie.

Wtyczka i WWW wyświetlają twierdzenia w kolejności: fałszywe, wprowadzające w błąd, brak dowodów, nieweryfikowalne, potwierdzone.
Sortowanie dotyczy kopii wyników w interfejsie, zachowuje kolejność w ramach tej samej klasy i nie zmienia ocen ani danych API.
