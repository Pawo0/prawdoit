# Zgodność z wymaganiami (audyt 21.11.2026, aktualizacja 22.11.2026)

Źródła wymagań: „MSZ — Pełna treść zadania konkursowego” (sekcje 2–6, 8, warunek brzegowy) i Regulamin (§4.2).
✅ spełnione · ⚠️ częściowo / poza repozytorium · ❌ brak. Dowód = plik, endpoint lub test do samodzielnego sprawdzenia.

## Warunek brzegowy (bez niego funkcje premiowane nie są punktowane)
| Wymaganie | Status | Dowód |
|---|---|---|
| End-to-end bez ręcznej ingerencji | ✅ | `POST /api/check`, `/api/check/async` → zapis w SQLite; `eval/run_eval.py` (145 przypadków bez interwencji) |
| Brak sfabrykowanych źródeł | ✅ | werdykt z reguł R1–R6, cytat wycinany dosłownie z tekstu źródła (V2: z konstrukcji `engine._fragment_windows`, test `_quote_ok`); LLM opcjonalny, tylko upraszcza język |
| Wstrzymanie się przy braku dowodów | ✅ | abstynencja 100% we wszystkich zbiorach (`eval/results_2026-11-21*/results.md`), scenariusze D, H, J2 poniżej |
| Dwa kanały / kanał + adapter demo | ✅ | WWW + czat demo (`/czat`), adapter WhatsApp/Messenger (`channels/meta.py`, `?demo=1`), Discord (`bots/discord_bot.py`), wtyczka |

## Sekcja 2 — wyzwanie
| Wymaganie | Status | Dowód |
|---|---|---|
| Wejście: tekst lub URL | ✅ | `CheckRequest.text/url`; URL w treści wiadomości też pobierany (`service.run_check`, test `backend/tests/test_url_injection.py`) |
| 5 klas wyniku; awaria / doprecyzuj / poza zakresem osobno | ✅ | `schemas.Verdict`, `CheckResult.status`; eval: „statusy niewerdyktowe” 100% |
| Tytuł, wydawca, data, link, fragment; źródła oddzielone od interpretacji | ✅ | `schemas.Evidence`; strona `/analiza/{id}` (dowody osobno od wyjaśnienia) |
| Siła werdyktu z jawnych przesłanek | ✅ | `ClaimResult.premises`, `basis_line` („Podstawa: mocna — 2 niezależne źródła…”), `/metodologia` |
| Wyjaśnienie, czego nie ustalono | ✅ | `reason_codes`, `what_unknown`, `would_settle`, krótka odpowiedź z materiałem pokrewnym (`answer.py`) |
| Powiadomienie wskazanego użytkownika (wysokie ryzyko, powtórzenia) | ⚠️ | sprawa w kolejce analityka z priorytetem „wysoki” (ryzyko lub ≥ 3 zgłoszenia), panel `/moderator`; brak e-maila/webhooka (luka 7) |
| Odporność na prompt injection | ✅ | `security.scan/neutralize`; eval: 100% (dev/ślepe); scenariusz E z URL poniżej |

## Sekcja 3 — MVP i funkcje premiowane
| Wymaganie | Status | Dowód |
|---|---|---|
| Responsywne WWW + drugi kanał | ✅ | `web/`, `/czat`, adaptery jw. |
| Rozpoznawanie 1–3 twierdzeń | ✅ | `claims.extract_claims` (fakt / opinia / prognoza) |
| ≥ 2 typy źródeł, prezentacja materiałów | ✅ | 52 włączone źródła, 4,4 tys. dok., 24 domeny, kat. A/B (`docs/SOURCES.md`, `/zrodla`, `/api/sources`) |
| Wynik + uzasadnienie + siła + ograniczenia | ✅ | `short_answer`, `basis_line`, `limitation_line` |
| Polski, prosty język | ✅ | szablony `answer.py`; `web/metodologia.html` |
| Zapis przebiegu (pytanie, czas, źródła, wynik) | ✅ | tabela `checks` (SQLite), eksport `/api/export/checks.csv|json` |
| Pełna ścieżka bez twórców | ✅ | jw. |
| Premiowane: łańcuch dowodowy, porównanie źródeł | ✅ | dowody z rolą (popiera/przeczy/kontekst), konflikt → „źródła sprzeczne” |
| Premiowane: otwarty katalog źródeł z zasadami | ✅ | rejestr `data/sources/*.json`, panel `/admin`, `docs/SOURCE_REGISTRY.md` |
| Premiowane: wymienne kanały/modele/źródła | ✅ | adaptery kanałów, `PRAWDOWID_EMBED_MODEL/NLI_MODEL/LLM_*`, rejestr źródeł |
| Premiowane: dopasowanie do incydentów; domena nie decyduje | ✅ | dopasowanie do twierdzeń fact-checków; `data/watchlist.json` → neutralne ostrzeżenie o statusie źródła |
| Premiowane: eksport CSV/JSON | ✅ | `/api/export/checks.{csv,json}` |
| Premiowane: OpenCTI/DISARM | ❌ | luka 6 |
| Premiowane: multimodalność (OCR, obraz, dźwięk) | ⚠️ | OCR zrzutów ekranu lokalnie (Tesseract `pol`, `ocr.py`, `CheckRequest.image_b64`, obraz nie jest zapisywany; bez pliku `tesseract` → błąd techniczny, nie werdykt); brak wyszukiwania wcześniejszych wystąpień obrazu (luka 2) i dźwięku |
| Premiowane: kontrolowana archiwizacja | ❌ | luka 8 (celowo: brak podstawy prawnej do archiwizacji pełnych treści) |
| Premiowane: zależności spoza EOG, miejsce przetwarzania | ✅ | modele lokalne; Google/Brave opcjonalne i opisane (`docs/COSTS.md`), `engine.processing` w każdym wyniku |
| Premiowane: pętla informacji, grupowanie | ✅ | `store.upsert_case` (cos ≥ 0,86); scenariusz H |

## Sekcja 4 — wymagania formalne
| Wymaganie | Status | Dowód |
|---|---|---|
| Nazwa zespołu, tytuł, opis ≤ 4000 zn. | ⚠️ | poza repozytorium (formularz zgłoszenia) |
| Prezentacja PDF ≤ 12 slajdów, film ≤ 3 min | ⚠️ | poza repozytorium; scenariusz filmu: `docs/DEMO.md` |
| Repozytorium + instrukcja uruchomienia | ✅ | `README.md` |
| Architektura, przepływ danych, modele, dostawcy, ograniczenia | ✅ | `docs/ARCHITECTURE.md`, `docs/COSTS.md` |
| Źródła, licencje, kwalifikacja, aktualizacja | ✅ | `docs/SOURCES.md` (generowany z rejestru), `docs/SOURCE_REGISTRY.md` |
| Wyniki testów (sekcja 6) z danymi do odtworzenia | ✅ | `eval/cases*.jsonl`, `eval/run_eval.py`, `eval/results_2026-11-21*/` |
| Ryzyka: halucynacje, stronniczość, prywatność, injection, dostępność, nadużycia | ✅ | `docs/RISKS.md` |
| Brak kluczy/sekretów/danych osobowych w repo | ✅ | sekrety tylko w env (`config.py`); `.gitignore`: `.env`, `data/runtime/`; tokeny paneli bez wartości domyślnych poza trybem lokalnym (`PRAWDOWID_DEV_MODE`). Skan 21.11.2026 (drzewo robocze + pełna historia 18 gałęzi i zdalnych refów; wzorce kluczy Google `AIza`, `sk-`, `ghp_`/`github_pat_`, `xox?-`, `hf_`, tokenów Discord, `Bearer`, kluczy prywatnych, przypisań `*_TOKEN/KEY/SECRET=`; pliki `.env*`): **brak sekretów**, w historii nigdy nie było pliku `.env` (tylko `.env.example`); zrzuty ekranu panelu mają zamaskowane pole tokenu. Dane osobowe: tylko adresy e-mail autorów w metadanych commitów (decyzja zespołu przy ewentualnym przepisaniu historii) |
| Opcjonalnie: OpenAPI, Docker | ✅ | OpenAPI: `/docs`, `/openapi.json` (FastAPI); `Dockerfile`, `compose.yaml`, `docs/DEPLOYMENT.md` |

## Sekcja 5 — wymagania techniczne i zakazy
| Wymaganie | Status | Dowód |
|---|---|---|
| Kanały oddzielone od logiki; wymiana modelu/dostawcy | ✅ | `service.run_check` wspólne dla kanałów; modele z env |
| Każda teza → dowód; abstynencja; awaria/niejasne/poza zakresem osobno | ✅ | bramka V2, R1–R6, `status` |
| Korpus ≥ 100 dok., ≥ 10 domen, ≥ 2 typy, źródła pierwotne + wtórne, lista do audytu | ✅ | 4,4 tys. dok., 24 domeny (`/api/health` → `corpus`), `docs/SOURCES.md` |
| Znacznik publikacji i pobrania; preferencja aktualnych; ostrzeżenie o archiwalnych | ✅ | `published_at`, `retrieved_at`; `stale_days=365` → ostrzeżenie „Materiał archiwalny” / `NIEAKTUALNE_DOWODY` |
| Bezpieczeństwo: walidacja, separacja instrukcji, ograniczenia narzędzi, sekrety, limit, logi | ✅ | limit 6000 zn., SSRF guard (`security.check_public_url`), robots.txt, limity na adres klienta: 120 sprawdzeń, 60 paczek wtyczki i 20 sprawdzeń w tle na minutę (`ratelimit.py`), tabele `security_events`, `errors` |
| Prywatność: minimalizacja, maskowanie PII, retencja, usunięcie sesji | ✅ | `textutil.mask_pii` na początku `service.run_check` (zasada niżej: [Ochrona danych osobowych](#ochrona-danych-osobowych)), `RETENTION_DAYS=30` (`store.purge_expired`), `DELETE /api/session/{id}` |
| Obserwowalność: czas, modele, błędy wyszukiwania, abstynencje, **szacunkowy koszt** | ✅ | `timings_ms`, `engine`, tabela `errors`, `/api/stats` (abstentions, `cost_estimate_pln`), `engine.cost_estimate` (dodane 21.11) |
| Dostępność: responsywność, kontrast, prosty język | ✅ | `web/static/style.css`, zrzut `eval/results/screens/07_mobile_wynik.png` |
| Spójność kanałów | ✅ | eval: 100%; scenariusz G |
| Pętla: rekomendacja ≠ faktyczne przekazanie | ✅ | `case_status`: „dodana do kolejki analityka … nie wysłano żadnych powiadomień poza tę kolejkę” |
| Zależności zewnętrzne: klucze, limity, koszty, miejsce, awarie; brak klucza ≠ wynik | ✅ | `docs/COSTS.md`; `PRAWDOWID_FORCE_FAIL` → scenariusz J; krok, który nie działał (brak klucza Google, wyszukiwanie na żywo wyłączone, LLM niedostępny/odrzucony), jest nazwany w wyniku: `engine.unavailable`, `live_search.status = "nieaktywne"`, `engine.llm_status`, wiersz „Nie użyto: …” w UI (test `backend/tests/test_unavailable_notices.py`) |
| Wynik nie zależy od zakodowanych przykładów ani odpowiedzi testowych | ✅ (od 22.11) | audyt kodu względem przypadków `eval/` i scenariuszy A–J: [Dopasowanie do przypadków testowych](#dopasowanie-do-przypadków-testowych) |
| Zakaz: LLM jako fakt bez źródła | ✅ | LLM nie decyduje; wynik LLM odrzucany, gdy doda liczbę/link (`llm.simplify`) |
| Zakaz: obchodzenie zabezpieczeń/płatnych baz | ✅ | robots.txt (RFC 9309), brak obchodzenia Incapsula/CAPTCHA (np. pap.pl → komunikat), brak DuckDuckGo HTML |
| Zakaz: werdykt z domeny/autora/kanału/popularności/etykiety tego samego modelu | ✅ | domena tylko filtruje; dowód = fragment + NLI/reguła liczbowa |
| Status źródła (sankcje) tylko jako neutralne ostrzeżenie | ✅ | `service.source_status_notices` („Status źródła…”), eval `expect_notice` |
| Zakaz: deklarowanie reverse image search bez API | ✅ | nie deklarujemy; F ujawnione jako nieobsługiwane |
| Zakaz: archiwizacja pełnych treści bez podstawy | ⚠️ | `data/raw/` (pełne HTML stron, 809 plików) usunięte z indeksu git 22.11 (pliki zostają lokalnie, `.gitignore`), ale nadal są w historii — luka 5. Korpus (`data/corpus/*.jsonl`, w git) przechowuje tytuł, link, daty, twierdzenie i ocenę oraz tekst dokumentu do ok. 3–4 tys. znaków (tabela niżej); analizy Demagoga — tekst do 12 000 zn. z określoną podstawą, licencją, retencją, kontrolą dostępu i procedurą usunięcia ([Pełny tekst analiz Demagoga](#pełny-tekst-analiz-demagoga)); ocena pozostałych źródeł względem licencji — w toku |

## Sekcja 6 — scenariusze referencyjne organizatorów (pytania z `rules/…strajk generalny.docx`)
`eval/organizers/run_organizers.py` (warstwy `offline` i `controlled`: bez internetu; wyszukiwanie na żywo tylko w
scenariuszach J z wymuszoną awarią), pełne wyniki: `eval/organizers/results.md`. Zaliczenie scenariuszy, pod które
system budowano, nie jest niezależną miarą jakości (zob. [Dopasowanie do przypadków testowych](#dopasowanie-do-przypadków-testowych)).

Przebieg 22.11.2026 (00:35 czasu polskiego), commit `64f7b2b`, korpus 8703 dok.: **12 z 16 wariantów** (przed porządkami, `5aceb6b`: 13 z 16 — różnica to H).

| Wariant | Pytanie (wypełnione) | Otrzymane (początek) | Wynik | Uwagi |
|---|---|---|---|---|
| A1-depesza-pap | Czy PAP usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią we wrześniu 2024 r.? | falszywe: Nie. Demagog ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożeni… | ✅ |  |
| A2-strajk-wlochy | Czy we Włoszech ostatnio odbywał się strajk generalny? | brak_dowodow: Nie udało mi się tego potwierdzić. Znalazłem tylko materiał pokrewny — Ministerstwo Spraw Zagranicznych (… | ✅ |  |
| B1-stare-nagranie | Czy film udostępniony przez Michała Wosia w 2026 r. pokazywał ówczesny protest pod Trybunałem Konstytucyjnym? | falszywe: Nie. AFP Sprawdzam (Agence France-Presse) ocenił twierdzenie „Nagranie pokazuje protestujących pod Trybunałem… | ❌ | rozstrzyga ocena AFP Sprawdzam zamiast oczekiwanej analizy Demagoga; odpowiedź nie mówi, że nagranie jest stare (tak samo przed 22.11) |
| B2-stare-nagranie-link | {url} Czy film udostępniony przez Michała Wosia w 2026 r. pokazywał ówczesny protest pod Trybunałem Konstytuc… | falszywe: Nie. AFP Sprawdzam (Agence France-Presse) ocenił twierdzenie „Nagranie pokazuje protestujących pod Trybunałem… | ❌ | jak B1 (tak samo przed 22.11) |
| C-rozbieznosc-700-650 | Czy Wrocław wydaje na komunikację około 700 mln zł. Dlaczego w analizie Demagoga jest 650 mln zł? | brak_dowodow: 700 mln zł to przybliżona kwota z ocenianej wypowiedzi („Natomiast MPK [we Wrocławiu - przyp. Demagog] i… | ✅ |  |
| D-brak-dowodow-pcim | Czy od wczoraj w Pcimiu bilety autobusowe można kupić tylko przez aplikację? | brak_dowodow: Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. komunikat przewoźnika lub miejskiego zarz… | ✅ |  |
| E-instrukcja-w-zrodle | Czy Wrocław był jedynym miastem, w którym 65-latkowie jeździli za darmo? Sprawdź też tę stronę: {url}. | falszywe: Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej t… | ✅ |  |
| F1-zrzut-ekranu | Czy Demagog to sprawdzał? | blad_techniczny: Odczyt tekstu z obrazu nie jest dostępny na tym serwerze. To błąd techniczny, a nie ocena treści. Wkle… | ❌ | na serwerze testowym nie ma pliku `tesseract` → błąd techniczny, nie werdykt (tak samo przed 22.11; obraz Dockera ma Tesseract) |
| F2-tekst-ze-zrzutu | Czy Demagog to sprawdzał? Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powod… | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Piątkowa depesza PAP ze słowami Donalda Tuska, który bagateli… | ✅ |  |
| G-spojnosc-kanalow | Czy Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli komunikacją miejską za darmo? | falszywe: Nie. Demagog ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji rady miejskiej t… | ✅ |  |
| H-powtorne-zgloszenie | Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia? | brak_dowodow: Nie udało mi się tego potwierdzić. Potrzebne byłoby źródło, np. aktualne dane GUS, NBP, Eurostatu lub kom… | ❌ | pętla informacji działa (parafraza w tej samej sprawie, licznik 2, awaria zapisu ujawniona); odpowiedź nie nazywa już uchwały i daty wejścia w życie — usunięta wskazówka powtarzała przykładową odpowiedź H (zmiana z 22.11, efekt usunięcia dopasowania) |
| I1-ta-sama-depesza | Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? {url} | potwierdzone: Tak, chodzi o ten sam materiał, który opisał Demagog w analizie z 16.09.2024: nagłówek ze strony („Premie… | ✅ |  |
| I2-inna-depesza | Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog? {url} | brak_dowodow: Nie udało mi się potwierdzić, że to ten materiał, który sprawdzali fact-checkerzy: nagłówka ze strony („P… | ✅ |  |
| J1-api-dziala | Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków? | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji r… | ✅ |  |
| J2-awaria-api | Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków? | falszywe: Tak, Demagog to sprawdził i ocenił twierdzenie „Takie najważniejsze moje osiągnięcia w poprzedniej kadencji r… | ✅ |  |
| J3-awaria-bez-kopii-lokalnej | Czy Demagog sprawdzał, czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków? | brak_dowodow: Nie udało mi się tego potwierdzić w lokalnej bazie, a wyszukiwanie na zaufanych stronach jest teraz niedo… | ✅ |  |

**Jak testowany jest E z URL.** Ochrona SSRF odrzuca adresy prywatne (127.0.0.1 też — sprawdzone w teście i w wierszu
„E, ochrona włączona”). Dlatego: (1) `backend/tests/test_url_injection.py` serwuje `web/demo/injection.html` na 127.0.0.1,
sprawdza, że ochrona go odrzuca, a potem — tylko dla tego serwera testowego — podmienia `fetch.check_public_url`, żeby
przeszła prawdziwa ścieżka pobrania (httpx, limity, trafilatura), skan i neutralizacja; (2) pełny przebieg werdyktu
(wiersz E) używa tej samej podmiany w procesie; (3) na publicznym wdrożeniu (np. tunel HTTPS) jury wkleja po prostu
`https://<host>/demo/injection.html` — ochrona SSRF zostaje włączona.

**Mierniki** (zbiory `eval/`, `PRAWDOWID_LIVE_SEARCH=0`, korpus 8703 dok.; przebieg 22.11.2026 na `64f7b2b` — werdykty,
statusy i reguły identyczne jak na `5aceb6b`): macro-F1 dev **0,975** · „ślepy 1” **0,899** · „ślepy 2” **0,872**
(cel ≥ 0,75; oba „ślepe” zbiory są dziś zbiorami strojenia — niezależną estymatą są tylko pierwsze przebiegi, 0,774
i 0,747, README); obecność materiału przy werdykcie (dawne proxy pokrycia) 100%; abstynencja 100%; odporność na injection 100%; statusy niewerdyktowe 100%;
spójność kanałów 100%; pętla informacji: tak.
**Czas:** mediana 0,5–0,7 s, p95 1,7–1,9 s na `5aceb6b`; przebieg 22.11 szedł na współdzielonym serwerze (load average
≈ 180 na 128 rdzeniach) i dał medianę 4,4–5,3 s, p95 14,7–21,4 s — cel ≤ 30 s spełniony w obu.
**Koszt 100 testów** (`engine.cost_estimate`: czas × stawka 1 vCPU 0,0000116 zł/s; płatnych API brak): zmierzony
≈ **0,001 zł** (90–115 s obliczeń na 100 przypadków, `5aceb6b`); przy założeniu, że sprawdzenie zajmuje cały serwer
4 vCPU, ≈ 0,005 zł; deklarowany w `docs/COSTS.md`: < 0,05 zł na 1000 zapytań.
**Audyt cytowań z 22.11.2026:** [jawne adnotacje 30 odpowiedzi i 57 atomowych tez](CITATION_AUDIT.md) dały pokrycie dowodem **47/57 = 82,5%** (cel ≥95%) oraz poprawność powiązań teza–cytat **32/46 = 69,6%** (cel ≥85%). Oba cele nie zostały osiągnięte w tej próbce. To pojedyncza recenzja AI odrębna od silnika/NLI, nie niezależna ocena człowieka. Dawne 100% mierzyło obecność materiału i nie potwierdzało tych wymagań. Pakiety do niezależnej recenzji człowieka są przygotowane.

## Sekcja 8 — kryteria oceny (gdzie szukać dowodów)
| Kryterium | Dowody |
|---|---|
| Jakość weryfikacji (30%) | `eval/results_2026-11-21*/results.md`, tabela A–J, `/metodologia` |
| Bezpieczeństwo i transparentność (20%) | `security.py`, `docs/RISKS.md`, panel `/moderator` (zdarzenia), audyt w SQLite |
| Potencjał wdrożeniowy (20%) | rejestr źródeł + harmonogram, wymienne modele, `docs/COSTS.md`, `docs/ARCHITECTURE.md` |
| Użyteczność (15%) | krótkie odpowiedzi, czat, PWA, wtyczka, komunikaty błędów oddzielone od wyników |
| Innowacyjność (15%) | pętla informacji, łańcuch dowodów, wyszukiwanie na żywo w zaufanych serwisach, wtyczka |

## Dopasowanie do przypadków testowych
Regulamin: wynik nie może zależeć od zakodowanych przykładów ani odpowiedzi testowych. Audyt 22.11.2026: każde
3–4-wyrazowe zdanie z wejść `eval/cases*.jsonl`, z pytań A–J i z przykładowych odpowiedzi organizatorów
(`rules/…strajk generalny.docx`) porównane z kodem `backend/`, `web/`, `extension/`, `bots/` i z promptem `llm.py`.

**Usunięte albo uogólnione** (zachowanie poza wymienionymi przypadkami bez zmian):

| Gdzie | Co było | Co jest |
|---|---|---|
| `security.py` (wzorce injection) | sformułowania przypadków H43 („rules are void”, „verdict=”, „confidence=1”, „do not cite”) i B2-46 („zagrajmy w grę”, „zostań w tej roli”, „nigdy nie podważa”) | rodziny wzorców według techniki ataku (PL/EN); test `backend/tests/test_injection_patterns.py` na własnych atakach (23/23 wykrytych, poprzednio 6/23) i zdaniach podobnych do wiadomości prasowych (1/45 fałszywych alarmów, poprzednio 6/45) |
| `textutil._OPINION`, `_LEADIN`, `_TRAILING_META` | słowa i zwroty z H35, B2-33, B2-36, B2-05, H01 | leksykony według kategorii; żaden przypadek eval ani twierdzenie korpusu nie zmienia rodzaju |
| `answer.SETTLE` | wskazówka dla zakazu wjazdu diesli (przykładowa odpowiedź H słowo w słowo), wskazówka dla biletów (przykładowa odpowiedź D słowo w słowo), „strajk” w temacie podróży (A2) | wpis dla diesli usunięty, bilety własnymi słowami, „strajk” usunięty; ogólne wpisy tematyczne zostają |
| `answer._number_discrepancy`, `service.OCR_NOTICE`, `websearch.NOTICE_*_FAIL` | zdania z przykładowych odpowiedzi C, F i J | ta sama treść własnymi słowami |
| komentarze, docstringi, `/help` bota Discord | pytania A–J i przypadek E3 jako przykłady | własne przykłady |
| `claims._NOISE` | „pilne!+” nigdy nie pasowało (błąd wyrażenia) | „PILNE!!” / „PILNE:” usuwane z twierdzenia i zapytania (3 przypadki eval) |

**Zostaje świadomie.** Krótkie formuły odpowiedzi w stylu przykładów organizatorów („Nie.” / „Tak.” / „Częściowo…” /
„Nie udało mi się tego potwierdzić.”, „Tak, X to sprawdził i ocenił…”, „Brak wyniku w bazie nie oznacza…”) —
organizatorzy podali je jako wzór odpowiedzi; stosujemy je do każdego wyniku, nie do konkretnych wejść. Reguły
zainspirowane scenariuszami (R3a stare nagranie, M2 ten sam materiał, pytanie o liczbę z analizy, „Czy X to
sprawdzał?”) są ogólne; komentarze podają scenariusz, który je zainspirował. Materiały demonstracyjne
(`web/demo/feed.html`, `docs/DEMO.md`, `docs/DISCORD.md`, `eval/screens.py`) używają tekstów przypadków eval jako
przykładowych wejść — nie wpływają na wyniki. Istniejące testy `backend/tests/test_answer_layer.py` (sformułowanie C)
i `test_organizers_scenarios.py` (uruchamia scenariusze A–J) używają tekstów organizatorów celowo.

**Status zbiorów ewaluacyjnych.** `eval/cases.jsonl` (dev) to zbiór strojenia z założenia. Zbiór „ślepy 1”
(`cases_heldout.jsonl`) przestał być ślepy po rundach poprawek (`docs/RESEARCH_SUMMARY.md`). Zbiór „ślepy 2”
(`cases_blind2.jsonl`) trafił do repozytorium w commicie `ae553ba` razem ze wzorcami, które naprawiały jego błędy
(injection B2-43…46, opinie B2-33/B2-36, zwrot B2-05), i z `eval/results_blind2_after_fixes/` — **jest więc zbiorem
strojenia, nie testem ślepym**. Jakość na nieznanych danych szacują tylko pierwsze przebiegi obu zbiorów
(macro-F1 0,774 i 0,747, README). Scenariusze A–J są specyfikacją, pod którą system budowano; ich zaliczenie nie jest
niezależną miarą jakości.

## Ochrona danych osobowych
**Zasada: maskujemy bezpośrednie identyfikatory, a nie treść potrzebną do weryfikacji.** Za wyjaśnieniem organizatorów
(cytat dosłowny): „nie należy maskować informacji, bez których zmienia się sens zapytania albo nie da się znaleźć
dowodu. Na pewno nie należy maskować imion i nazwisk osób publicznych. Maskować należy np. numery pesel, numer
dowodu, numer telefonu itd.”

| Maskujemy (`textutil.mask_pii`) | Warunek, żeby liczba faktograficzna nie została zamaskowana |
|---|---|
| PESEL → `[PESEL]` | 11 cyfr z poprawną sumą kontrolną i datą albo podpisane „PESEL” |
| Nr dowodu osobistego → `[DOWOD]` | 3 wielkie litery + 6 cyfr z poprawną cyfrą kontrolną albo podpisane „dowód”; kody „PL…” (np. Natura 2000) pomijane |
| Nr paszportu → `[PASZPORT]` | 2 wielkie litery + 7 cyfr z poprawną cyfrą kontrolną albo podpisane „paszport” |
| Nr konta (NRB/IBAN) → `[NR_KONTA]` | suma kontrolna mod 97 albo podpisane „konto/rachunek/IBAN” |
| Telefon → `[TELEFON]` | z prefiksem `+`/`00`; numer krajowy tylko z kontekstem („tel.”, „zadzwoń”, „mój numer”, „pod numerem”…) albo zapisany z myślnikami; nigdy, gdy po liczbie stoi jednostka lub waluta (zł, euro, %, mln, osób, głosów…) ani gdy jest częścią dłuższej liczby |
| Prywatny e-mail → `[EMAIL]` | adresy funkcyjne instytucji (`kontakt@`, `biuro@`, `iod@`, `rzecznik@`…) zostają |

Nie maskujemy nazwisk (zwłaszcza osób publicznych), instytucji, miejsc, dat, kwot, statystyk, przedziałów lat ani
sygnatur aktów prawnych. Maskowanie działa **raz, na początku** `service.run_check` — na tekście, tekście z OCR
i treści pobranej strony — więc wyszukiwanie, zapytania do Google Fact Check i wyszukiwarek zaufanych serwisów,
opcjonalny LLM, `result_json` w audycie i kolejka moderatora dostają tylko znaczniki; same znaczniki są usuwane
z zapytań wyszukiwania (`claims.extract_claims`). Adresy URL zostają bez zmian (link musi dać się pobrać).
Sprawdzenie (21.11.2026): 0 z 163 wejść zbiorów `eval/` i scenariuszy organizatorów zawiera coś, co maska zmienia;
na 8 771 dokumentach korpusu maska trafia wyłącznie w numery telefonów i adresy e-mail (wcześniejsza wersja
zamieniała kwoty typu „613 499 158 zł” na `[TELEFON]`). Testy: `backend/tests/test_pii_masking.py`. Ograniczenie:
numer telefonu z samych cyfr, bez kontekstu i bez prefiksu (np. „602 418 977” w środku zdania), nie jest maskowany.

## Regulamin §4.2 — prawa osób trzecich (licencje)
| Element | Licencja / podstawa | Gdzie opisane | Status |
|---|---|---|---|
| Dane źródłowe (korpus) | per źródło: CC BY 4.0 (Eurostat, KE), warunki serwisu Gov.pl (cytowane dosłownie w polu `license`), art. 4 pr. aut. (akty, obwieszczenia), prawo cytatu z atrybucją (fact-checkerzy), zgoda EEAS (EUvsDisinfo) | pole `license` w rejestrze, `docs/SOURCES.md`, tabela niżej | ⚠️ opisane; szczegółowa ocena zgodności w toku |
| Surowa pamięć stron `data/raw/` | pełne kopie artykułów (część „all rights reserved”) | `.gitignore`; usunięte z indeksu git 22.11 — 809 plików nadal w historii git | ⚠️ luka 5 (przepisanie historii: decyzja zespołu) |
| Dokumenty organizatora `rules/` | treść zadania, regulamin, docx ze scenariuszami A–J i przykładowymi odpowiedziami, `resources.txt` | — | ⚠️ decyzja zespołu, czy zostają w publicznym repo |
| Zrzuty ekranu portali `eval/results/real_*.png` | strony tvrepublika.pl, interia.pl, wp.pl (treści i reklamy osób trzecich) | `eval/test_real_sites.py` | ⚠️ decyzja zespołu (zostawić, przyciąć albo usunąć) |
| Modele | `sdadas/mmlw-retrieval-e5-small` Apache-2.0; `mDeBERTa-v3-base-xnli…` MIT | `docs/ARCHITECTURE.md` | ✅ |
| Biblioteki Python | fastapi MIT, uvicorn BSD-3, httpx BSD-3, trafilatura 2.x Apache-2.0, numpy BSD-3, sentence-transformers / transformers Apache-2.0, torch BSD-style, pydantic MIT, python-multipart Apache-2.0, rapidfuzz MIT, PyYAML MIT, Pillow MIT-CMU, discord.py MIT, playwright Apache-2.0, mcp MIT (z metadanych zainstalowanych pakietów) | ten plik | ✅ wszystkie liberalne |
| Grafika, czcionki, JS | własne (SVG/PNG w repo), bez CDN i bibliotek zewnętrznych w `web/`, `extension/` | — | ✅ |
| Licencja kodu projektu | brak pliku `LICENSE` | — | ⚠️ luka 4 |

### Co przechowujemy z każdego źródła (stan 22.11.2026)
Liczby i długości tekstu policzone z `data/corpus/<id>.jsonl`; licencja to dosłowna treść pola `license`
z `data/sources/<id>.json`. **Szczegółowa ocena zgodności źródeł z regulaminem i prawem jest w toku** (osobna
analiza zespołu); ta tabela tylko zestawia, co jest w repozytorium. Uwaga do tej oceny: część wpisów deklaruje
„krótkie fragmenty”, a rekordy mają tekst do ok. 3–4 tys. znaków. Od 22.11.2026 rekordy fakenews.pl, Pravdy i CERT
Polska mają jeden dosłowny fragment do 300 znaków; rekordy z Google Fact Check Tools API, AFP i Konkret24 usunięto.

| Źródło (`id`) | Wł. | Co przechowujemy w `data/corpus/<id>.jsonl` | Licencja (pole `license` w `data/sources/<id>.json`, dosłownie) |
|---|---|---|---|
| `afp_sprawdzam` | nie | nic — rekordy usunięte 22.11.2026, źródło wyłączone (powód w polu `notes` rejestru) | © Agence France-Presse — wszelkie prawa zastrzeżone. Pobieramy wyłącznie metadane ClaimReview udostępniane przez Google Fact Check Tools API (twierdzenie, ocena, tytuł, data, link) — warunki Google APIs; bez treści artykułu, strony sprawdzam.afp.com nie pobieramy. |
| `cert_komunikaty` | tak | 119 dok.: tytuł, link, daty, tekst do 300 zn. (mediana 239) | © NASK / CERT Polska — brak otwartej licencji; zapisane: tytuł, data, link i jeden dosłowny fragment (do 300 znaków) z przypisem (prawo cytatu, art. 29 pr. aut.) |
| `checkfirst` | tak | 31 dok.: tytuł, link, daty, tekst do 3991 zn. (mediana 2863) | © Check First Oy. Site policy (robots.txt/llms.txt): AI systems & RAG pipelines welcome to read, index and cite with attribution to CheckFirst + link. Quoted propaganda in reports is evidence, not CheckFirst's claim. |
| `demagog` | tak | 3353 rekordy z 2973 stron: tytuł, link, daty, twierdzenie i ocena (3239), tekst analizy do 12 000 zn. (mediana 4966; 73 rekordy przycięte) — [podstawa](#pełny-tekst-analiz-demagoga) | © Stowarzyszenie Demagog. 'Ogólne Warunki Licencji' (demagog.org.pl/zasady-udostepniania-tresci): non-commercial reuse allowed without modification (non-distorting shortening OK) with attribution 'Źródło informacji: www.demagog.org.pl' + link; commercial use needs consent. robots Content-Signal: search=yes, ai-train=no, use=reference -> RAG/citation only, never training. |
| `demagog_google_api` | tak | 1 dok.: metadane ClaimReview (twierdzenie, ocena, tytuł, data, link), bez treści artykułu | © Stowarzyszenie Demagog (demagog.org.pl/zasady-udostepniania-tresci: niekomercyjne wykorzystanie z atrybucją i linkiem). Pobieramy wyłącznie metadane ClaimReview udostępniane przez Google Fact Check Tools API (twierdzenie, ocena, tytuł, data, link) — warunki Google APIs; bez treści artykułu. |
| `euvsdisinfo` | tak | 300 dok.: tytuł, link, daty, twierdzenie i ocena (300), tekst do 3227 zn. (mediana 1407) | EUvsDisinfo (EEAS East StratCom Task Force). Reuse authorised provided the source is acknowledged (EEAS legal notice, Decision 2011/833/EU); third-party content excluded. Case texts taken from the Hugging Face copy NLP-UniBW/eu_vs_disinfo of the euvsdisinfo.eu case database, because the site serves a Cloudflare challenge, which we do not circumvent. |
| `euvsdisinfo_mcp` | tak | 0 dokumentów w korpusie (dotąd nic nie pobrano) | EUvsDisinfo (EEAS East StratCom Task Force) — ponowne wykorzystanie dozwolone z podaniem źródła (nota prawna EEAS, decyzja Komisji 2011/833/UE); bez treści stron trzecich. Dostęp przez serwer MCP organizatora HackNation 2026 (token w zmiennej środowiskowej, nigdy w pliku). |
| `fakenews_google_api` | nie | nic — rekordy usunięte 22.11.2026, źródło wyłączone (powód w polu `notes` rejestru) | © fakenews.pl / Fundacja „Przeciwdziałamy Dezinformacji”, all rights reserved (no open licence). Pobieramy wyłącznie metadane ClaimReview udostępniane przez Google Fact Check Tools API (twierdzenie, ocena, tytuł, data, link) — warunki Google APIs; bez treści artykułu. |
| `fakenews_pl` | tak | 883 dok.: tytuł, link, daty, twierdzenie i ocena (588), tekst do 300 zn. (mediana 148) | © fakenews.pl / Fundacja „Przeciwdziałamy Dezinformacji”, all rights reserved (no open licence). Stored: checked claim, rating, title, dates and link, plus one verbatim excerpt (≤300 chars) quoted with attribution; the article is read at its link. |
| `gddkia_drogi` | tak | nic — tylko zaufany link (bez pobierania) | GDDKiA — informacja publiczna |
| `gddkia_informacja_drogowa` | tak | 1 dok.: tytuł, link, daty, tekst do 2337 zn. (mediana 2337) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `gios_powietrze` | tak | nic — tylko zaufany link (bez pobierania) | GIOŚ — dane publiczne, z podaniem źródła |
| `gis_ostrzezenia` | tak | 48 dok.: tytuł, link, daty, tekst do 2993 zn. (mediana 1615) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `google_factcheck` | tak | nic na stałe — zapytanie na żywo (wynik: `live_web`) | Fact Check Tools API — warunki Google APIs; treść oznaczeń należy do wydawców fact-checków (cytat + link) |
| `imgw_baltyk` | tak | nic — tylko zaufany link (bez pobierania) | IMGW-PIB — dane publiczne z podaniem źródła |
| `imgw_hydro` | tak | nic — tylko zaufany link (bez pobierania) | IMGW-PIB — dane publiczne z podaniem źródła |
| `imgw_meteo` | tak | nic — tylko zaufany link (bez pobierania) | IMGW-PIB — dane publiczne z podaniem źródła |
| `imgw_ostrzezenia` | tak | 36 dok.: tytuł, link, daty, tekst do 1465 zn. (mediana 877) | Dane publiczne IMGW-PIB — wolne do ponownego wykorzystania z podaniem źródła: „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy” (danepubliczne.imgw.pl) |
| `kgpsp_aktualnosci` | tak | 200 dok.: tytuł, link, daty, tekst do 3998 zn. (mediana 2002) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `kgsok_aktualnosci` | tak | 190 dok.: tytuł, link, daty, tekst do 3997 zn. (mediana 1294) | © Komenda Główna SOK — cytowanie z podaniem źródła |
| `konkret24` | nie | nic — rekordy usunięte 22.11.2026, źródło wyłączone (powód w polu `notes` rejestru) | © TVN S.A. (Konkret24/TVN24), all rights reserved. Stored only title, lead and a short excerpt (≤700 chars) with link, for citation; full text must be read at source. |
| `kprm_wydarzenia` | tak | 122 dok.: tytuł, link, daty, tekst do 4000 zn. (mediana 3895) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `kwp_radom_aktualnosci` | tak | 325 dok.: tytuł, link, daty, tekst do 3997 zn. (mediana 1966) | © KWP zs. w Radomiu — informacja publiczna; cytowanie z podaniem źródła |
| `live_web` | tak | domyślnie nic (`LIVE_PERSIST_DAYS=0`); po włączeniu: strony z wyszukiwania na żywo przez tyle dni, najdłużej `RETENTION_DAYS`, usuwane przy starcie i przy każdym zapisie | Każdy rekord ma licencję wpisu rejestru, z którego domeny pochodzi (pole license rekordu); krótkie fragmenty z podaniem źródła i linkiem. |
| `mi_aktualnosci` | tak | 131 dok.: tytuł, link, daty, tekst do 3995 zn. (mediana 2549) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `mi_informacje_dla_obywateli` | tak | 3 dok.: tytuł, link, daty, tekst do 3665 zn. (mediana 1020) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `mon_aktualnosci` | tak | 200 dok.: tytuł, link, daty, tekst do 3997 zn. (mediana 3015) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `mswia_aktualnosci` | tak | 127 dok.: tytuł, link, daty, tekst do 3998 zn. (mediana 2965) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `mswia_rso_informacje` | tak | 1 dok.: tytuł, link, daty, tekst do 3931 zn. (mediana 3931) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `msz_odyseusz` | tak | 1195 dok.: tytuł, link, daty, tekst do 4003 zn. (mediana 1813) | Treści MSZ (odyseusz.gov.pl) — materiały urzędowe / informacja publiczna; podać źródło |
| `official_cert` | tak | 17 dok.: tytuł, link, daty, tekst do 300 zn. (mediana 254) | © NASK / CERT Polska — brak otwartej licencji; zapisane: tytuł, data, link i jeden dosłowny fragment (do 300 znaków) z przypisem (prawo cytatu, art. 29 pr. aut.); lista hole.cert.pl: dowolne użycie |
| `official_dane` | tak | 47 dok.: tytuł, link, daty, tekst do 3776 zn. (mediana 1574) | CC0 1.0 lub CC BY 4.0 — dane.gov.pl (Regulamin §5, ustawa o otwartych danych); licencja podana przy każdym zbiorze |
| `official_ec_pl` | tak | 45 dok.: tytuł, link, daty, tekst do 3999 zn. (mediana 3929) | © Unia Europejska, CC BY 4.0 (informacja prawna Komisji Europejskiej); podać źródło |
| `official_eli` | tak | 33 dok.: tytuł, link, daty, tekst do 3999 zn. (mediana 3440) | Akt normatywny — nie podlega prawu autorskiemu (art. 4 pkt 1 pr. aut.); metadane: ELI API Sejmu RP (api.sejm.gov.pl), podać źródło |
| `official_eurlex` | tak | 30 dok.: tytuł, link, daty, tekst do 3998 zn. (mediana 3935) | © Unia Europejska, EUR-Lex — ponowne wykorzystanie wg decyzji 2011/833/UE; streszczenia CC BY 4.0, metadane CC0; autentyczne są tylko teksty opublikowane w Dz.U. UE |
| `official_eurostat` | tak | 13 dok.: tytuł, link, daty, tekst do 679 zn. (mediana 625) | CC BY 4.0 — © European Union, Eurostat; podać źródło (kod zbioru, data dostępu) |
| `official_govpl_msz` | tak | 310 dok.: tytuł, link, daty, tekst do 3999 zn. (mediana 1981) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `official_govpl_myths` | tak | 95 dok.: tytuł, link, daty, tekst do 3997 zn. (mediana 1825) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `official_gus` | tak | 72 dok.: tytuł, link, daty, tekst do 674 zn. (mediana 536) | GUS — wykorzystanie dozwolone z podaniem źródła (stat.gov.pl/copyright); BDL i DBW: CC BY 4.0 (api.stat.gov.pl); podać źródło |
| `official_nbp` | tak | 13 dok.: tytuł, link, daty, tekst do 548 zn. (mediana 427) | NBP — dane publiczne; wymagane podanie źródła z linkiem do www.nbp.pl |
| `official_pkw` | tak | 10 dok.: tytuł, link, daty, tekst do 3981 zn. (mediana 2819) | Dokument urzędowy (obwieszczenie PKW, Dz.U.) — nie podlega prawu autorskiemu (art. 4 pr. aut.) |
| `paa_aktualnosci` | tak | 47 dok.: tytuł, link, daty, tekst do 3877 zn. (mediana 1974) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `paa_monitoring` | tak | nic — tylko zaufany link (bez pobierania) | PAA — informacja publiczna |
| `pap` | tak | nic — tylko zaufany link (bez pobierania) | © Polska Agencja Prasowa S.A. — wszelkie prawa zastrzeżone; nie pobieramy ani nie przechowujemy treści, wyłącznie odnośnik do depeszy (tytuł i link) |
| `policja_aktualnosci` | tak | 214 dok.: tytuł, link, daty, tekst do 3990 zn. (mediana 2040) | © Komenda Główna Policji — informacja publiczna; cytowanie z podaniem źródła |
| `portal_pasazera` | tak | nic — tylko zaufany link (bez pobierania) | PKP PLK — informacja publiczna |
| `pravda` | tak | 269 dok.: tytuł, link, daty, twierdzenie i ocena (211), tekst do 299 zn. (mediana 156) | © Stowarzyszenie Pravda; no open licence stated (all rights reserved). Stored: checked claim, rating, title, dates and link, plus one verbatim excerpt (≤300 chars) quoted with attribution; the article is read at its link. Claim/rating from Pravda's own ClaimReview markup (Data Commons ClaimReview feed). |
| `rcb_komunikaty` | tak | 160 dok.: tytuł, link, daty, tekst do 3981 zn. (mediana 537) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `rcb_raport_dobowy` | tak | 1 dok.: tytuł, link, daty, tekst do 4709 zn. (mediana 4709) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `rso_ostrzezenia` | tak | 100 dok.: tytuł, link, daty, tekst do 3225 zn. (mediana 651) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |
| `sar_morska_sluzba` | tak | nic — tylko zaufany link (bez pobierania) | MSPiR — informacja publiczna |
| `ulc_prawa_pasazera` | tak | nic — tylko zaufany link (bez pobierania) | ULC — informacja publiczna |
| `umgdy_aktualnosci` | tak | 35 dok.: tytuł, link, daty, tekst do 3978 zn. (mediana 3105) | Urząd Morski w Gdyni — informacja publiczna; cytowanie z podaniem źródła |
| `ums_aktualnosci` | tak | 19 dok.: tytuł, link, daty, tekst do 3973 zn. (mediana 2144) | Urząd Morski w Szczecinie — informacja publiczna; cytowanie z podaniem źródła |
| `ums_warunki_zeglugi` | tak | 1 dok.: tytuł, link, daty, tekst do 3960 zn. (mediana 3960) | Urząd Morski w Szczecinie — informacja publiczna; cytowanie z podaniem źródła |
| `utk_pasazerowie` | tak | nic — tylko zaufany link (bez pobierania) | UTK — informacja publiczna |
| `wody_polskie_komunikaty_nawigacyjne` | tak | 10 dok.: tytuł, link, daty, tekst do 4002 zn. (mediana 3986) | Warunki serwisu Gov.pl (gov.pl/web/gov/prawa-autorskie, odczyt 2026-11-22): „Korzystanie przez użytkowników z materiałów urzędowych opublikowanych w serwisie Gov.pl nie wymaga zgody Ministra Cyfryzacji.” „Treści tekstowe publikowane w serwisie (z wyłączeniem treści audiowizualnych), są udostępniane na licencji typu Creative Commons: uznanie autorstwa - na tych samych warunkach 4.0 (CC BY-SA 4.0).” Utwory osób trzecich: za zgodą ich właścicieli. Podajemy źródło i link. |

### Pełny tekst analiz Demagoga
Od 22.11.2026 analizy Demagoga są przechowywane prawie w całości (do 12 000 znaków, wcześniej 3000), bo wniosek
fact-checkera jest zwykle na końcu artykułu: przy limicie 3000 znaków ucinaliśmy 92,8% analiz, a 413 z 1095 zdań
z wnioskiem leżało poza nim. Organizatorzy na Discordzie: „Integracja Google Fact Check z Demagogiem nie ma
similarity search tylko dosłowne matchowanie fraz. Stąd często wyniki z demagoga się nie pojawiają. Zostawiamy wam
wolną rękę.” Regulamin (sekcja 5) wymaga przy archiwizacji pełnych treści określenia pięciu rzeczy:

| Wymóg | Jak jest spełniony |
|---|---|
| Podstawa prawna | „Ogólne Warunki Licencji” Stowarzyszenia Demagog (demagog.org.pl/zasady-udostepniania-tresci): wykorzystanie niekomercyjne bez modyfikacji, dozwolone skróty niezniekształcające sensu, z atrybucją i linkiem; Prawdowid jest bezpłatny i niekomercyjny. Odpowiedzi pokazują tylko krótki dosłowny cytat (do 520 znaków) — prawo cytatu, art. 29 pr. aut. |
| Licencja | pole `license` w `data/sources/demagog.json` (dosłownie w tabeli wyżej); robots.txt Demagoga: `search=yes, ai-train=no, use=reference` — tekst służy wyłącznie wyszukiwaniu i cytowaniu, nigdy trenowaniu modeli |
| Retencja | rekord jest odświeżany przy każdym pobraniu (harmonogram co 24 h); limit tekstu: `FULL_TEXT_LIMITS` w `ingest/common.py` i `backend/prawdowid/index.py`; surowe strony (`data/raw/demagog`) tylko lokalnie, poza gitem |
| Kontrola dostępu | żaden endpoint API nie zwraca pełnego tekstu dokumentu: użytkownik dostaje tytuł, wydawcę, datę, link i dosłowny fragment z atrybucją. Pełny tekst jest tylko w pliku `data/corpus/demagog.jsonl` w repozytorium (dziś prywatnym) — przed upublicznieniem repozytorium: decyzja zespołu, czy ten plik zostaje (licencja zezwala na niekomercyjne rozpowszechnianie z atrybucją) czy jest odtwarzany skryptem `ingest/harvest_demagog.py` |
| Procedura usunięcia | na żądanie Demagoga albo po wycofaniu analizy: usunąć rekord z `data/corpus/demagog.jsonl` i stronę z `data/raw/demagog`, przeładować indeks (panel `/admin`); całe źródło: `enabled: false` w `data/sources/demagog.json` — indeks pomija je od następnego przeładowania. Ograniczenie: harwester nie usuwa sam analiz, które zniknęły z serwisu |

Odtworzenie bez sieci: `ingest/.venv/bin/python ingest/harvest_demagog.py --reparse-cache` (z lokalnej kopii stron).

## Większe luki (niewdrożone) — szacunek pracy
| # | Luka | Szacunek |
|---|---|---|
| 1 | ~~OCR zrzutów ekranu~~ — zrobione (`ocr.py`, Tesseract w obrazie Dockera). Zostaje: scenariusz F1 wymaga pliku `tesseract` na serwerze testowym; bez niego odpowiedź to błąd techniczny | — |
| 2 | Wyszukiwanie wcześniejszych wystąpień obrazu (lokalny indeks pHash ograniczony do obrazów z fact-checków) | 1 dzień |
| 3 | Pytania-meta o materiał: I (ten sam materiał) — zrobione (reguła M2, `provenance.py`); B (stare nagranie, reguła R3a) — werdykt „Fałszywe” jest, ale rozstrzyga inna publikacja niż oczekiwana, a odpowiedź nie mówi, że nagranie jest stare | 0,5–1 dnia |
| 4 | Plik `LICENSE` (decyzja zespołu; zależności pozwalają na MIT/Apache-2.0) | 10 min |
| 5 | ~~`git rm -r --cached data/raw`~~ — zrobione 22.11. Zostaje: przed upublicznieniem repo usunąć `data/raw/` z historii (`git filter-repo --path data/raw --invert-paths`, wymuszone wypchnięcie, ponowne sklonowanie przez wszystkich) | 30 min + koordynacja zespołu |
| 6 | Eksport spraw/incydentów do STIX 2.1 (OpenCTI) z technikami DISARM | 4 h |
| 7 | Powiadomienie analityka poza panelem (webhook/e-mail) przy sprawie „wysoki” — z rozróżnieniem „wysłano / nie wysłano” | 1–2 h |
| 8 | Kontrolowana archiwizacja wskazanego materiału (podstawa prawna, retencja, procedura usunięcia) | 1 dzień + opinia prawna |
| 9 | ~~Dockerfile + compose~~ — zrobione (`Dockerfile`, `compose.yaml`, `docs/DEPLOYMENT.md`) | — |
