# Zgodność z wymaganiami (audyt 21.11.2026)

Źródła wymagań: „MSZ — Pełna treść zadania konkursowego” (sekcje 2–6, 8, warunek brzegowy) i Regulamin (§4.2).
✅ spełnione · ⚠️ częściowo / poza repozytorium · ❌ brak. Dowód = plik, endpoint lub test do samodzielnego sprawdzenia.

## Warunek brzegowy (bez niego funkcje premiowane nie są punktowane)
| Wymaganie | Status | Dowód |
|---|---|---|
| End-to-end bez ręcznej ingerencji | ✅ | `POST /api/check`, `/api/check/async` → zapis w SQLite; `eval/run_eval.py` (145 przypadków bez interwencji) |
| Brak sfabrykowanych źródeł | ✅ | werdykt z reguł R1–R6, cytat musi występować dosłownie w źródle (bramka V2, `engine._quote_ok`); LLM opcjonalny, tylko upraszcza język |
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
| Premiowane: multimodalność (OCR, obraz, dźwięk) | ❌ | luka 1; ujawnione w `docs/DEMO.md` i `ARCHITECTURE.md` |
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
| Opcjonalnie: OpenAPI, Docker | ⚠️ | OpenAPI: `/docs`, `/openapi.json` (FastAPI); Dockerfile brak (luka 9) |

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
| Zależności zewnętrzne: klucze, limity, koszty, miejsce, awarie; brak klucza ≠ wynik | ✅ | `docs/COSTS.md`; `PRAWDOWID_FORCE_FAIL` → scenariusz J |
| Wynik nie zależy od zakodowanych przykładów ani odpowiedzi testowych | ✅ (od 22.11) | audyt kodu względem przypadków `eval/` i scenariuszy A–J: [Dopasowanie do przypadków testowych](#dopasowanie-do-przypadków-testowych) |
| Zakaz: LLM jako fakt bez źródła | ✅ | LLM nie decyduje; wynik LLM odrzucany, gdy doda liczbę/link (`llm.simplify`) |
| Zakaz: obchodzenie zabezpieczeń/płatnych baz | ✅ | robots.txt (RFC 9309), brak obchodzenia Incapsula/CAPTCHA (np. pap.pl → komunikat), brak DuckDuckGo HTML |
| Zakaz: werdykt z domeny/autora/kanału/popularności/etykiety tego samego modelu | ✅ | domena tylko filtruje; dowód = fragment + NLI/reguła liczbowa |
| Status źródła (sankcje) tylko jako neutralne ostrzeżenie | ✅ | `service.source_status_notices` („Status źródła…”), eval `expect_notice` |
| Zakaz: deklarowanie reverse image search bez API | ✅ | nie deklarujemy; F ujawnione jako nieobsługiwane |
| Zakaz: archiwizacja pełnych treści bez podstawy | ⚠️ | korpus: twierdzenie, ocena, krótki fragment, link; **ale** `data/raw/` (pełne HTML stron, 809 plików) jest śledzone w git — luka 5 |

## Sekcja 6 — scenariusze referencyjne organizatorów (pytania z `rules/…strajk generalny.docx`)
Uruchomione raz w procesie, wyszukiwanie na żywo włączone (21.11.2026). Szczegóły: `docs/COMPLIANCE.md` (ta tabela).

| Scen. | Pytanie (wypełnione) | Oczekiwane | Otrzymane | |
|---|---|---|---|---|
@@AJ@@

**Jak testowany jest E z URL.** Ochrona SSRF odrzuca adresy prywatne (127.0.0.1 też — sprawdzone w teście i w wierszu
„E, ochrona włączona”). Dlatego: (1) `backend/tests/test_url_injection.py` serwuje `web/demo/injection.html` na 127.0.0.1,
sprawdza, że ochrona go odrzuca, a potem — tylko dla tego serwera testowego — podmienia `fetch.check_public_url`, żeby
przeszła prawdziwa ścieżka pobrania (httpx, limity, trafilatura), skan i neutralizacja; (2) pełny przebieg werdyktu
(wiersz E) używa tej samej podmiany w procesie; (3) na publicznym wdrożeniu (np. tunel HTTPS) jury wkleja po prostu
`https://<host>/demo/injection.html` — ochrona SSRF zostaje włączona.

**Mierniki (zbiory `eval/`, `PRAWDOWID_LIVE_SEARCH=0`)**: macro-F1 dev @@F1DEV@@ · ślepy 1 @@F1H@@ · ślepy 2 @@F1B@@ (cel ≥ 0,75);
pokrycie cytowań 100%; abstynencja 100%; odporność na injection 100%; mediana < 1 s; spójność kanałów 100%;
pętla informacji: tak. Poprawność cytowania (≥ 85%) mierzona automatycznie (cytat dosłowny + zgodność stanowiska);
ręczna próba — do wykonania przez jury.

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
| Dane źródłowe (korpus) | per źródło: CC BY 4.0 / CC BY-SA 4.0 (gov.pl, Eurostat, KE), art. 4 pr. aut. (akty, obwieszczenia), prawo cytatu z atrybucją (fact-checkerzy), zgoda EEAS (EUvsDisinfo) | pole `license` w rejestrze, `docs/SOURCES.md` | ✅ |
| Surowa pamięć stron `data/raw/` | pełne kopie artykułów (część „all rights reserved”) | `.gitignore` (dodane 21.11) — ale 809 plików już w historii git | ⚠️ luka 5 |
| Modele | `sdadas/mmlw-retrieval-e5-small` Apache-2.0; `mDeBERTa-v3-base-xnli…` MIT | `docs/ARCHITECTURE.md` | ✅ |
| Biblioteki Python | fastapi MIT, uvicorn BSD-3, httpx BSD-3, trafilatura 2.x Apache-2.0, numpy BSD-3, sentence-transformers / transformers Apache-2.0, torch BSD-style, pydantic MIT, python-multipart Apache-2.0, rapidfuzz MIT, PyYAML MIT, Pillow MIT-CMU, discord.py MIT, playwright Apache-2.0, mcp MIT (z metadanych zainstalowanych pakietów) | ten plik | ✅ wszystkie liberalne |
| Grafika, czcionki, JS | własne (SVG/PNG w repo), bez CDN i bibliotek zewnętrznych w `web/`, `extension/` | — | ✅ |
| Licencja kodu projektu | brak pliku `LICENSE` | — | ⚠️ luka 4 |

## Większe luki (niewdrożone) — szacunek pracy
| # | Luka | Szacunek |
|---|---|---|
| 1 | OCR zrzutów ekranu (scenariusz F): Tesseract `pol` / PaddleOCR lokalnie, endpoint obrazu, UI, ujawnienie, że data na obrazie nie potwierdza daty publikacji | 4–6 h |
| 2 | Wyszukiwanie wcześniejszych wystąpień obrazu (lokalny indeks pHash ograniczony do obrazów z fact-checków) | 1 dzień |
| 3 | Pytania-meta o materiał („Czy film udostępniony przez X pokazywał…?”, B) i dopasowanie URL/tytułu do materiału sprawdzanego przez fact-checkera (I): dziś właściwy artykuł Demagoga jest pokazywany jako materiał pokrewny, ale bez werdyktu; potrzebna reformulacja pytania + indeks linków wychodzących z fact-checków + ponowna ewaluacja | 1–1,5 dnia |
| 4 | Plik `LICENSE` (decyzja zespołu; zależności pozwalają na MIT/Apache-2.0) | 10 min |
| 5 | `git rm -r --cached data/raw` (pliki zostają lokalnie), a przed upublicznieniem repo — usunięcie z historii (`git filter-repo`) | 30 min + koordynacja zespołu |
| 6 | Eksport spraw/incydentów do STIX 2.1 (OpenCTI) z technikami DISARM | 4 h |
| 7 | Powiadomienie analityka poza panelem (webhook/e-mail) przy sprawie „wysoki” — z rozróżnieniem „wysłano / nie wysłano” | 1–2 h |
| 8 | Kontrolowana archiwizacja wskazanego materiału (podstawa prawna, retencja, procedura usunięcia) | 1 dzień + opinia prawna |
| 9 | Dockerfile + compose (model cache w wolumenie) | 1 h |
