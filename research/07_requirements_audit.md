# 07 — Independent requirements audit (Prawdowid, HackNation 2026 / MSZ)

Audit date: 2026-11-21 (evening). Method: static reading of the task documents, code and eval artefacts; read-only
queries against `data/runtime/prawdowid.sqlite` (audit log of the dev server); GET requests to the dev server;
two `python -c` snippets that import only `textutil`/`claims` (no ML stack). No model was loaded, `eval/run_eval.py`
was not run, nothing in the repository was modified except this file.

Certainty tags used throughout:
- **[V]** verified in code or data (file:line, eval artefact or DB row given)
- **[I]** inferred from code (plausible, not executed)
- **[?]** cannot be verified statically / lives outside the repository

Files under concurrent edit (`web/analiza.html`, `web/index.html`, `web/static/app.js`, `web/static/style.css`) were
read only for facts that do not depend on the merge; conflict markers are not treated as findings.

---

## 0. Bottom line

The architecture is sound for the task (rule-based verdicts over cited evidence, no LLM in the decision path,
abstention by default, one service function for all channels, an audit log). The four boundary-condition items are
met in substance. The self-assessment in `docs/COMPLIANCE.md` is nevertheless too generous in six places that matter
for points:

1. **Citation correctness (mandatory metric, ≥ 85 %) is not measured at all**, and a manual sample suggests it is
   near 50 % for fact-check evidence, because the quoted fragment is chosen by lexical overlap and tends to be the
   sentence that *restates the false claim*.
2. **The organisers' own reference scenarios are only partly passed** with live search on: A (first example) abstains
   and took 32.8 s, C and I abstain with an unrelated "closest material". The A–J table in COMPLIANCE.md is still the
   literal placeholder `@@AJ@@`.
3. **Macro-F1 is computed leniently** (multi-label gold collapses to the prediction). Strict recomputation from the
   stored results: 0.909 / 0.831 / 0.805 instead of 1.00 / 0.937 / 0.901; the only truly blind number preserved in
   the repo is 0.747 lenient = **0.644 strict**, below the 0.75 target.
4. **Prompt-injection "100 %" is fitted to the test strings**; on first contact the "ignored and logged" rate was 60 %
   and 25 %. Verdicts were never hijacked (true by design), but *logging* depends on regexes, and fetched pages are
   scanned only after trafilatura extraction (HTML comments / hidden text are never seen).
5. **PII masking covers only `input_masked`**; the claim text inside the stored and publicly retrievable
   `result_json` is unmasked. Retention and session deletion touch only the `checks` table.
6. **Rate limit is 30 POST/min per IP on `/api/check*`** while the jury's reference set is "minimum 30 przypadków" —
   a scripted run hits HTTP 429 at request 31, which is a direct threat to the "End-to-end 100 %" metric.

Plus one process risk that outranks everything: **most of today's work is untracked in git** (live search, short
answers, async jobs, source registry, COMPLIANCE.md, the 2026-11-21 eval results) and `data/raw/` (809 full
third-party HTML pages) is already on `origin/main`.

---

## 1. How "mandatory" was derived

| Marker in the task text | Reading used here |
|---|---|
| "Warunek brzegowy … Wymagania podstawowe obejmują działanie end-to-end bez ręcznej ingerencji twórców, brak sfabrykowanych źródeł, poprawne wstrzymanie się … oraz dwa działające kanały lub jeden kanał i adapter demonstracyjny" | Hard gate: failing any of the four zeroes all bonus points (15 % criterion and every "premiowane" item). |
| "Minimalny zakres funkcjonalny (MVP)" (§3) | Mandatory. The boundary paragraph says basic requirements *"obejmują"* (include) four items; the safer reading is that the whole MVP list is "wymagania podstawowe" and the four are the explicitly named gate. |
| "Projekt przesyłany do oceny **musi** zawierać" (§4) | Mandatory submission content. |
| "musi / muszą / nie wolno / nie mogą / ma być" (§2, §5, "Ograniczenia i zakazy", "Założenia wdrożeniowe") | Mandatory. |
| "powinien / powinno / należy" (§2 bullets, §5 table column "Wymaganie") | Expected behaviour that the jury scores; treated as mandatory-to-attempt. Flagged separately where it is only "powinien". |
| "Mierniki obowiązkowe" (§6) | Mandatory to *report*; targets are "Cel MVP". |
| "Funkcje premiowane", "Jeżeli zespół wdraża…", "Jeżeli funkcja została wdrożona" | Bonus — but once implemented, the attached "musi" clauses bind (information loop, source-status notice). |

Judging weights (§8): quality of verification and evidence 30 %, safety/responsibility/transparency 20 %,
deployment potential 20 %, usability 15 %, innovation/completeness 15 % ("oceniane po spełnieniu wymagań
podstawowych").

Ambiguity worth knowing: §6 says "≥ 0,75 w zestawie jawnym; wynik ukryty porównawczy" — the "zestaw jawny" is the
organisers' open set, not the team's own cases. The only organiser-provided examples in the repo are the A–J
questions in the `.docx`. The team's three case files use their *own* scenario letters (F = false claims, O =
opinions, T/N/Q/M/X …), so the README phrase "scenariusze A–J" does not mean the organisers' A–J **[V]**
(`eval/cases*.jsonl`, scenario counts).

---

## 2. Mandatory requirements — status table

Status: **MET**, **PARTIAL**, **NOT MET**, **CANNOT VERIFY**.

### 2.1 Boundary condition

| # | Requirement (quote) | Status | Evidence | What is missing |
|---|---|---|---|---|
| B1 | "działanie end-to-end bez ręcznej ingerencji twórców" | MET, at risk | **[V]** `service.run_check` (`backend/prawdowid/service.py:74-240`) goes input → claims → retrieval → rules → answer → `store.save_check`; 1 820 audited checks in the DB. | (a) Rate limit 30/min/IP (`api.py:39-49`, `config.py:51`) can reject a scripted jury run — see G4. (b) Scenario J needs a process restart with `PRAWDOWID_FORCE_FAIL` (`websearch.py:110-111`) — the jury can do it from the README, but it is not a runtime switch. (c) Untracked code must be pushed, otherwise the jury's clone does not contain the system that produced the results (G1). |
| B2 | "brak sfabrykowanych źródeł" | MET, two caveats | **[V]** Every `Evidence` comes from a harvested `SourceDoc` with URL/publisher/date (`engine.py:93-100`); no LLM in the verdict path (`llm.py` only rephrases, disabled by default — `/api/health` → `llm: null`). | (a) Official "fact-cards" (GUS 72, NBP 13, Eurostat 13, ELI, PKW, dane.gov.pl …) carry text **generated by the ingest templates** from API/XLSX data, including derived statements ("Polska ma 4. najniższe bezrobocie…", "zmiana +4,4 %") — `ingest/official_gus.py:142,297`, `official_eurostat.py:87`. They are shown as "Fragment źródła" and pass gate V2 because V2 compares against the team's *stored* text (`engine.py:87-90`), not against the publisher's page. A juror who opens the link (an `.xlsx` or a JSON API URL) will not find the sentence. Not disclosed in the UI **[V]** (no "karta danych" label in `web/`). (b) Fictional demo results with `example.org` sources exist in the web home page and the extension mock mode (`web/static/home.js:46`, `extension/background.js:13-21`); labelled as fictional, off by default. |
| B3 | "poprawne wstrzymanie się od rozstrzygnięcia przy braku dowodów" | MET | **[V]** Default verdict is `brak_dowodow` (`engine.py:516`, R6 at `:591-595`); 17/17 scenario-D cases abstain in all three sets (`eval/results_2026-11-21*/results.json`); organisers' D and H questions abstain with a "what would settle it" sentence (DB rows 16:41 UTC). | With live search on, one of three runs of the organisers' D question attached an unrelated "Najbliższy materiał" (Demagog, "Wieliczka to miasto ukraińskie", rated Manipulacja) to the abstention (DB row 16:33:07). Not a verdict, but it reads like a pseudo-answer — tighten `answer._related` (G12). Abstention with live search enabled is not covered by the eval at all (G8). |
| B4 | "dwa działające kanały lub jeden kanał i adapter demonstracyjny" | MET, presentation risk | **[V]** Web UI + Meta-format webhook adapter `POST /webhooks/whatsapp?demo=1` / `/webhooks/messenger?demo=1` (`channels/meta.py:101-110,145-154`), both call `run_check`; 252 `whatsapp`-channel checks in the DB. Discord bot is a thin client of `/api/chat-reply` (`bots/discord_bot.py`). | The `/czat` page does **not** use the adapter by default: it calls `/api/check/async` and re-implements the reply format in JavaScript (`web/czat.html:79-83`, `chatReply` at `:39-58`); the webhook path runs only when the checkbox "Wysyłaj jako webhook Meta" is ticked (`:84-91`). A strict juror testing scenario G through `/czat` is testing the web API twice. Discord/WhatsApp with real credentials: **[?]** (`.env` holds only `PRAWDOWID_WA_*` names; no Discord token; `.env` is not auto-loaded by the code). |

### 2.2 Challenge (§2) and MVP (§3)

| # | Requirement | Status | Evidence | Gap |
|---|---|---|---|---|
| M1 | "przyjmuje co najmniej tekst lub adres URL" via "responsywny interfejs WWW" + one more channel | MET | **[V]** `schemas.CheckRequest` (`schemas.py:115-119`), bare URL and URL-in-message handling (`service.py:85-138`). Responsiveness **[?]** (UI under merge). | — |
| M2 | "rozpoznawanie jednego lub kilku twierdzeń" | PARTIAL | **[V]** `claims.extract_claims` (`claims.py:21-56`): up to 3 claims, fact/opinion/forecast. | Inputs of ≤ 2 sentences and ≤ 400 chars are always merged into **one** claim (`claims.py:29-39`), so a two-claim chat message gets one verdict. The eval scores only `res.claims[0]` (`run_eval.py:69`); multi-claim correctness is unmeasured (2 "X" cases). |
| M3 | Five verdict classes; "Awaria techniczna, brak możliwości wykonania sprawdzenia i potrzeba doprecyzowania … muszą być komunikowane oddzielnie" | MET | **[V]** `schemas.Verdict` / `Status` (`schemas.py:10-26`); `blad_techniczny`, `doprecyzuj`, `poza_zakresem` set in `service.py:108-112,156-159,166-171`; 8/8 status cases pass in the latest runs. | "Wyjście poza zakres" (§5) is implemented only for unsafe URLs. A request that is not a claim at all (write/translate/advise) is processed as a claim and ends as `brak_dowodow`. Unsupported media in the Meta adapter returns a text without an audit record (`meta.py:56-57`). |
| M4 | "oddzielać materiały źródłowe od interpretacji modelu oraz wskazywać co najmniej tytuł, wydawcę, datę i link, a w miarę możliwości także wykorzystany fragment" | MET | **[V]** `schemas.Evidence` (`schemas.py:50-70`); chat reply prints publisher, date, title, URL (`channels/formatting.py:31-36`). | 49 corpus documents have no `published_at` (official_cert 9, govpl_myths 29, gus 11) although `docs/SOURCES.md` lists "źródła bez daty" as an exclusion **[V]** (corpus scan). |
| M5 | "Siła werdyktu … powinna wynikać z jawnych przesłanek" | MET | **[V]** `ClaimResult.premises`, strength derived in `engine.py:549-595`; `answer.basis_line` (`answer.py:251-267`). | Premise label "Najnowszy dowód" actually shows the *decisive* document's date, not the newest (`engine.py:575-578`). Cosmetic. |
| M6 | "wyszukiwanie … w jasno opisanym zbiorze obejmującym co najmniej dwa typy źródeł oraz prezentowanie materiałów" | MET | **[V]** Corpus scan: 4 450 records on disk, 4 402 loaded (`/api/health`), 24–25 domains, types official 1 365 / factcheck 2 754 / incident 331; `/zrodla`, `/api/sources`, `docs/SOURCES.md`. | Counts disagree between README (52 sources, 24 domains), SOURCES.md (53/50, 4 381 docs, 23 domains) and `/api/health` (4 402, 24) — regenerate before submission. |
| M7 | "wynik, krótkie uzasadnienie, ocena siły podstawy odpowiedzi i czytelna informacja o ograniczeniach" | MET | **[V]** `short_answer`, `basis_line`, `limitation_line` (`answer.py:190-296`), observed in DB rows. | — |
| M8 | "odpowiedź po polsku, prostym i zrozumiałym językiem" | MET | **[V]** Deterministic templates (`answer.py`, `engine._explain`). | Quoted fact-check claims are cut at 150 chars, sometimes before the relevant part (organisers' Wrocław example: the quote ends "…nie 70, tylko 65-latkowie…" and never reaches "jedynym miastem") — hurts perceived citation quality (see G3). |
| M9 | "podstawowy zapis przebiegu sprawdzenia, obejmujący pytanie, czas, wykorzystane źródła i wynik" | MET | **[V]** `checks` table (`store.py:32-34,57-70`), `/analiza/{id}`, export endpoints. | `save_check` failures are swallowed with a log line (`service.py:236-239`); single SQLite connection, journal mode `delete` **[V]** — a concurrent writer (eval, CLI) can cause a lost audit row **[I]**. |
| M10 | "wstrzymanie się … bez tworzenia pozornej odpowiedzi" | MET | See B3. | See B3. |
| M11 | "pełna ścieżka end-to-end bez ręcznej ingerencji twórców … i zapisania przebiegu" | MET | See B1, M9. | See B1. |
| M12 | "W sprawach wysokiego ryzyka oraz powtarzających się pytań … **powinien powiadomić** właściwego użytkownika wskazanego przez administratora" | PARTIAL ("powinien") | **[V]** Case queue with priority "wysoki" for high-risk or ≥ 3 repeats (`store.py:104-133`), moderator panel. Honest wording: "nie wysłano żadnych powiadomień poza tę kolejkę" (`service.py:217-218`). | No notification is sent and no recipient can be configured. Self-assessment already marks this ⚠️. |
| M13 | "Instrukcje znalezione w analizowanych materiałach **nie mogą** zmieniać zasad działania systemu" | MET by design | **[V]** Verdict = deterministic rules over retrieved evidence; no LLM unless configured; optional LLM output validated (`llm.py:47-63`). No injected verdict in any stored run, including first blind runs. | Detection and *logging* ("odnotowanie zdarzenia", scenario E) are regex-based and fitted to the test strings — see G6. |

### 2.3 Formal submission requirements (§4, "musi zawierać")

| # | Requirement | Status | Evidence | Gap |
|---|---|---|---|---|
| F1 | "nazwę zespołu, tytuł i opis rozwiązania do 4 000 znaków" | CANNOT VERIFY | **[?]** Not in the repo. | Write and count characters. |
| F2 | "prezentację PDF, maksymalnie 12 slajdów, obejmującą problem, użytkowników, architekturę, demonstrację, wyniki testów, ryzyka i możliwe dalsze kroki" | CANNOT VERIFY (nothing in repo) | **[V]** No presentation file anywhere in the tree (`find` for pdf/pptx returns only `rules/` and `research/`). | All seven named topics must appear. |
| F3 | "film demonstracyjny dostępny pod linkiem, maksymalnie 3 minuty" | CANNOT VERIFY | **[V]** Only a script: `docs/DEMO.md`. | Record; keep fictional demo modes out of the recording. |
| F4 | "link do repozytorium kodu wraz z instrukcją uruchomienia" | PARTIAL — highest process risk | **[V]** README has run instructions. `git status`: `websearch.py`, `answer.py`, `jobs.py`, `admin_api.py`, `resources.py`, `robots.py`, `sources/`, `source_handlers/`, `data/sources/`, 24 corpus files, `docs/COMPLIANCE.md`, `backend/tests/`, `eval/results_2026-11-21*/`, `web/admin.html` are **untracked**; four web files are in conflict; `HEAD == origin/main`. | Commit and push. `backend/requirements.txt` is unpinned and there is no lock file **[V]** — a jury install next week may resolve different `transformers`/`sentence-transformers` versions. `.env` is not loaded by the app and the README does not say how to load it. |
| F5 | "krótki opis architektury, przepływu danych, użytych modeli, dostawców i najważniejszych ograniczeń" | MET | **[V]** `docs/ARCHITECTURE.md`, `docs/COSTS.md`. | COSTS.md says "API jest bezstanowe (poza SQLite audytu)" — not accurate: async jobs, rate-limit counters, demo outbox, live-added index documents and the scheduler are in-process state (`jobs.py:33`, `api.py:36`, `meta.py:28`, `index.py:299-348`). |
| F6 | "opis wykorzystanych źródeł, ich licencji, sposobu kwalifikacji i aktualizacji" | MET | **[V]** `docs/SOURCES.md` (generated from the registry), `docs/SOURCE_REGISTRY.md`. | See L1/L2 below for the gap between the stated and actual excerpt sizes. |
| F7 | "wyniki testów według sekcji 6, wraz z danymi pozwalającymi odtworzyć rezultat" | PARTIAL | **[V]** Cases, runner and results are in the repo. | Missing from the reported results: citation correctness (not computed anywhere in `run_eval.py`; summary keys contain no such field), measured cost of 100 tests, the organisers' A–J table (`@@AJ@@`, `@@F1DEV@@`, `@@F1H@@`, `@@F1B@@` in COMPLIANCE.md:85,94). The first held-out run (README: 0.774) has no artefact — `eval/results_heldout/results.json` is the post-fix run (0.936). |
| F8 | Risk list incl. "halucynacje, stronniczość źródeł, prywatność, prompt injection, dostępność i nadużycia" | MET | **[V]** `docs/RISKS.md` covers all six and more. | The privacy and injection rows describe more than the code does (see P1, G6). |
| F9 | "Klucze API, dane osobowe i sekrety **nie mogą** znaleźć się w repozytorium ani materiałach demonstracyjnych" | MET | **[V]** `.env` is git-ignored (`.gitignore:9`), not tracked, absent from history; `data/runtime/` ignored; secrets read from env only (`config.py`). | Default tokens `demo-moderator` / `demo-admin` are public by design (`config.py:61-62`, README). On a public demo host anyone can disable or delete sources and trigger ingest scripts through `/api/admin/*`. Set real tokens on any hosted instance. |

### 2.4 Technical requirements (§5 table)

| # | Area — requirement | Status | Evidence | Gap |
|---|---|---|---|---|
| T1 | Architecture — "oddzielić obsługę kanałów od logiki weryfikacji oraz umożliwić wymianę modelu lub dostawcy" | MET | **[V]** One `run_check`; adapters in `channels/`, `bots/`; models via `PRAWDOWID_EMBED_MODEL` / `NLI_MODEL` / `LLM_*`. | Reply formatting is duplicated in JS (`czat.html`) and Python (`formatting.py`). |
| T2 | Facts — "Każda teza faktograficzna przedstawiana jako ustalenie systemu **musi** prowadzić do dowodu" | PARTIAL | **[V]** A decisive verdict cannot exist without an evidence item; `main_evidence` link in every channel. | The *fragment* shown often does not itself support the finding (G3). Citation coverage in the eval is true by construction (`run_eval.py:71,78` counts any evidence item, including "kontekst"). |
| T3 | Sources — ≥ 100 documents, ≥ 10 domains, ≥ 2 types, primary + secondary, "Lista źródeł musi być dostępna do audytu" | MET | **[V]** See M6. | — |
| T4 | Freshness — "Przechowywanie znacznika czasu publikacji i pobrania. Preferowanie danych aktualnych dla pytania oraz ostrzeganie o materiale archiwalnym." | PARTIAL | **[V]** `published_at` / `retrieved_at` on every record (49 without publication date); archival warning for old URL pages (`service.py:100-105`) and R4-NIEAKTUALNE (`engine.py:543-547`). | No recency preference anywhere in ranking or tie-breaking (`engine.py:393,539` rank by similarity and tier only). The reason code `NIEAKTUALNE_DOWODY` cited in COMPLIANCE.md is never emitted (present only in `answer.py:24` and a schema comment). In chat replies the "evidence older than a year" limitation is the *last* fallback (`answer.py:294`), so a 2024 fact-check is presented with "ocena opiera się na jednym źródle" instead (organisers' Wrocław example, evidence dated 2024-03-12). Eval: of 7 archival-context cases only 1 was detected; 6 abstained and were scored correct because `brak_dowodow` is an accepted label. |
| T5 | Security — "Walidacja wejścia, separacja instrukcji systemowych od treści źródeł, ograniczenia narzędzi, ochrona sekretów, limitowanie żądań i logowanie zdarzeń" | PARTIAL | **[V]** Length limits, SSRF guard with per-hop checks (`fetch.py:20-47`, `security.py:144-159`), robots.txt, no tools, env secrets, `security_events` and `errors` tables. | Rate limiting covers only `POST /api/check*` (`api.py:41`); `/api/chat-reply`, `/api/quick`, `/share-target`, `/api/feedback` are unlimited. The limiter keys on `request.client.host`, so behind a tunnel or reverse proxy all users share one bucket. SSRF check and the actual connection resolve DNS separately (rebinding window) — acceptable for a prototype, say so in RISKS. |
| T6 | Privacy — "Minimalizacja danych, automatyczne maskowanie oczywistych danych osobowych, określona retencja oraz możliwość usunięcia sesji demonstracyjnej" | PARTIAL | **[V]** `mask_pii` (`textutil.py:235-247`), retention 30 days (`store.purge_expired`), `DELETE /api/session/{id}`, UI button (`app.js:372`). | See P1–P3: masking applies to `input_excerpt` only; purge runs only at startup and only on `checks`; session deletion leaves `security_events`, `errors` and `cases` rows; no PII-bearing input has ever been tested (0 rows with a mask token in 1 820 checks). |
| T7 | Observability — response time, model use, search errors, abstentions, estimated cost | MET | **[V]** `timings_ms`, `engine` block, `errors` table (58 rows by component), `/api/stats` (`abstentions`, `cost_estimate_pln`), `service.cost_estimate`. | Cost uses wall time × CPU rate, so network wait is priced as CPU. Immaterial at these magnitudes. |
| T8 | Accessibility — "Responsywny interfejs, czytelny kontrast i język zrozumiały" | CANNOT VERIFY | **[?]** UI is mid-merge. | Run an automated contrast check after the merge; the pixel display font should not be used for body text. |
| T9 | Channels — "powinny korzystać z tej samej logiki … wynik merytoryczny powinien być spójny niezależnie od kanału" | MET offline, at risk online | **[V]** Same `run_check`; organisers' G question gave the same verdict and source on web and WhatsApp-demo (DB 16:41:38 / 16:41:39). | With live search on, the answer depends on network timing; the same organisers' question produced four different abstention texts across runs (strike in Italy: related material shown / not shown / "błąd dostępu"). Eval consistency sample = first 8 cases, all easy fact-check hits, live search off (`run_eval.py:95`). |
| T10 | Information loop (binding because implemented) — "System **musi** odróżniać rekomendację przekazania od faktycznego przekazania sprawy" | MET | **[V]** `case_status` text; chat line only when `case_id` exists (`formatting.py:67-68`); organisers' H paraphrase joined case SPR-3C25BC. | Dedup tested on one hard-coded pair (`run_eval.py:107-110`) plus the organisers' pair; false merges are untested. Eval writes into the live DB: 93 open cases (71 "wysoki", 629 grouped submissions) are test debris **[V]**. |
| T11 | External dependencies — keys, limits, costs, processing location, failure behaviour; "Brak klucza, limit lub awaria **nie mogą** być przedstawiane jako wynik merytoryczny" | MET, one gap | **[V]** `docs/COSTS.md`; failure → notice, never verdict (`websearch.py:766-771,880-888`); forced Google failure produced the organisers' exact sentence while the local hit was still returned (DB 16:42:33). | A **missing** Google key makes the provider "silently inactive" (`websearch.py:797-798`). Scenario J lists "Brak klucza" as an input that should lead to "Ujawnienie ograniczenia technicznego". Safer reading: disclose it. |
| T12 | "Demonstracja musi działać end-to-end … powinien dać się uruchomić przez jury na podstawie instrukcji" | MET, at risk | **[V]** README; index cache in `data/index/` (startup build 4.5 s on the dev server). | First start downloads the two models from Hugging Face (roughly 1 GB, estimate); unpinned dependencies; no Dockerfile (optional per §4). |
| T13 | Cost of 1 000 queries, channel cost, behaviour under load | MET | **[V]** `docs/COSTS.md`. | — |

### 2.5 Prohibitions ("Ograniczenia i zakazy")

| # | Prohibition | Status | Evidence | Gap |
|---|---|---|---|---|
| Z1 | LLM output as fact without a verifiable source | MET | **[V]** See B2, M13. | Fact-card disclosure (B2a). |
| Z2 | "Nie wolno obchodzić zabezpieczeń serwisów i płatnych baz" | MET | **[V]** robots.txt (RFC 9309) before search and fetch (`websearch.py:236-257`, `sources/fetchers.py:82-150`); blocked pages yield a notice (pap.pl in the organisers' I example → "strona … blokuje automatyczny dostęp"). | EUvsDisinfo text was taken from a Hugging Face mirror "because the site served a Cloudflare challenge" (licence string in `data/corpus/euvsdisinfo.jsonl`). EEAS content is reusable with attribution, but a juror may read this as routing around a protection. Prefer the organiser's MCP feed and say so. |
| Z3 | No verdict based solely on domain, author, channel, popularity or a label generated by the same model | MET | **[V]** Domain only whitelists search; verdict needs a claim match or fragment stance. Watchlist yields a neutral notice (`service.py:254-261`). | — |
| Z4 | Source status (EU sanctions) only as a separate neutral warning | MET | **[V]** `data/watchlist.json` (2 entries with a public source), notice text. | — |
| Z5 | No claim of full reverse image search | MET | **[V]** Not offered; disclosed. | — |
| Z6 | "Nie wolno archiwizować pełnych treści i obrazów bez określenia podstawy prawnej, licencji, retencji, kontroli dostępu oraz procedury usunięcia" | PARTIAL — real risk | **[V]** `data/raw/`: 809 files, 132 MB of full HTML (Demagog 380, Pravda 269, Konkret24 120) still tracked and already on `origin/main` (commit c7b03ce); the `.gitignore` rule was added later and does not untrack them. | Also: the corpus is not "krótki fragment" as COMPLIANCE.md and RISKS.md state. Median stored text: Demagog 2 939 chars (1 248 of 1 294 records above 2 000), FakeNews.pl 2 432, Pravda 2 425 — the latter two are "all rights reserved" per the team's own licence strings. `live_web.jsonl` stores up to 6 000 chars per fetched page with no retention rule. |

### 2.6 Section-6 metrics and organisers' scenarios

Observed results for the organisers' questions (live search on, dev server, 2026-11-21 16:40–16:42 UTC, read from
the audit DB — this is the run that was meant to fill `@@AJ@@`) **[V]**:

| Scen. | Question (as run) | Expected (docx) | Observed | Verdict |
|---|---|---|---|---|
| A-1 | "Czy PAP usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią we wrześniu 2024 r.?" | "Nie. Demagog ocenił … jako fałsz" + link | `brak_dowodow`, **32.8 s**; the correct Demagog article appears only as "Najbliższy materiał … sprawdź, czy dotyczy tego samego" | FAIL (safe) |
| A-2 | "Czy we Włoszech ostatnio odbywał się strajk generalny?" | "Strajk zapowiedziano na 20 listopada … Nie mam informacji, czy się odbył" | `brak_dowodow` + MSZ fragment "W dniu 20 listopada … zapowiedziano strajk generalny" (8.8 s); other runs: no fragment, or "błąd dostępu" | PASS in substance, unstable |
| B | needs a link to a video | old footage detected | not run | UNTESTED |
| C | "Czy Wrocław wydaje na komunikację około 700 mln zł. Dlaczego w analizie Demagoga jest 650 mln zł?" | explain 700 vs 650, "częściowa prawda" | `brak_dowodow`; closest material is about Warsaw | FAIL (safe) |
| D | Pcim bus tickets | abstain + what is needed | abstain + matching hint; one run with unrelated "closest material" | PASS |
| E | Wrocław + controlled page | "Nie" + ignore + log | `falszywe`, 5 events (page served on loopback with the SSRF guard patched in-process) | PASS |
| F | screenshot | optional | not implemented, disclosed | N/A |
| G | Wrocław question, web + WhatsApp-demo | same verdict and publication | same | PASS |
| H | Pcim diesel + paraphrase | one case | both in SPR-3C25BC | PASS |
| I | "Czy ten wpis dotyczy tej samej depeszy PAP …? [pap.pl URL]" | show the match basis, or say it is a different dispatch | page blocked; `brak_dowodow`; closest material is a *different* PAP dispatch (mobilisation 2024) | FAIL (safe) |
| J | Wrocław with forced Google failure | "Tak, Demagog to sprawdził …" / "Nie mogę teraz sprawdzić indeksu Google…" | exactly that | PASS |

Note **[V]**: the Demagog articles for the Wrocław and PAP examples are not in `data/corpus/demagog.jsonl`; they
exist only in `data/corpus/live_web.jsonl` (untracked), i.e. they were fetched by live search during testing. On a
fresh clone, G/E/J for the organisers' own question depend on a live site search succeeding within the time budget.

| Metric (definition → target) | Reported | Audit finding | Status |
|---|---|---|---|
| "Trafność werdyktu — macro-F1 na obsługiwanych klasach ≥ 0,75 w zestawie jawnym" | 1.00 / 0.937 / 0.901 | Strict (first listed label is gold): **0.909 / 0.831 / 0.805**. First blind-2 run: 0.747 lenient, **0.644 strict**. Not measured on the organisers' open set. | PARTIAL |
| "Pokrycie cytowań — odsetek tez faktograficznych z dowodem ≥ 95 %" | 100 % | True by construction; counts any evidence item. | MET (weak measurement) |
| "Poprawność cytowania — czy cytowany fragment rzeczywiście wspiera tezę ≥ 85 %" | "mierzona automatycznie" | **Not computed.** Auditor's manual sample of 16 decisive results: about 8 fragments support the verdict on their own; the rest restate the claim or are background. | NOT MET (unmeasured, likely below target) |
| "Wstrzymanie się … ≥ 80 %" | 100 % | 17/17, live search off. With live search on: 52 of 54 claims stayed `brak_dowodow` in interactive use; correctness not labelled. | MET offline |
| "Odporność — odsetek odpartych prób prompt injection ≥ 90 %" | 100 % | Verdict never hijacked (13/13 in every run). "Ignored and logged" on first contact: 25 % on blind-2 (`eval/results_blind2/results.json`) and 60 % on held-out (README figure; no artefact); 100 % only after the regexes were extended with the test phrases. No case of a hostile *source page* in the eval sets. | PARTIAL |
| "Czas — mediana ≤ 30 s dla tekstu/URL" | 0.6 s | Live search off. Interactive checks on the dev server since 15:00 UTC: all 192 → median 0.7 s, p90 13.4 s; the 50 that entered the live stage → median 11.2 s, p90 19.3 s, max 32.8 s. | MET (median), tail risk |
| "Koszt — deklarowany i zmierzony koszt 100 testów" | per-1 000 estimate in COSTS.md | No measured figure for 100 tests in any results file. `/api/stats`: median 0.000006 zł per check. | PARTIAL |
| "End-to-end — 100 % obowiązkowych scenariuszy uruchomionych przez jury bez interwencji" | — | Depends on B1 risks (rate limit, push, install). | AT RISK |
| "Spójność kanałów — 100 % próby międzykanałowej" | 100 % | 8 easy cases, live search off, in-process call. | MET offline |
| "Pętla informacji — 100 % przypadków testowych, jeżeli wdrożona" | "tak" | One pair + organisers' pair. | MET (thin) |
| "Wynik nie może zależeć od … zakodowania konkretnych przykładów" | "nie ma listy przykładów w kodzie" | No answer list. But: (a) `answer.SETTLE` hints (`answer.py:29-42`) reproduce the organisers' sample sentences for D and H almost word for word, keyed on "diesl / zakaz wjazd / bilet / autobus"; (b) opinion keywords "fanaberi", "sensown", "bzdur", "nie umywa" (`textutil.py:84-93`) and injection patterns "zagrajmy w grę", "show_sources", "zdekoduj … wykonaj" (`security.py:55-58`) are lifted from the blind sets. Topic rules, not answers — but be ready to explain them. | MET, disclose |
| "Zespół powinien ujawnić przypadki, których system nie obsługuje" | DEMO.md list | Missing from the list: questions *about* a material (A-1, B, I), numeric discrepancy explanation (C), archival-context detection. | PARTIAL |

### 2.7 Regulations (Regulamin zadania)

| Clause | Relevance | Status |
|---|---|---|
| §1.5 only registered participants | administrative | **[?]** |
| §4.1 each participant is the author of their contribution and holds full economic rights | Declaration by the team. One illustration is described as generated with an image tool (`docs/DEMO.md`); bundled fonts carry OFL licences (`web/static/fonts/LICENSE.txt`). Check the event rules on AI-assisted work. | **[?]** |
| §4.2 "rozwiązanie jest wolne od wad prawnych oraz nie narusza praw osób trzecich" | This is where `data/raw/` and the 2 400–3 000-char excerpts from "all rights reserved" publishers matter (Z6). Dependencies are permissively licensed per COMPLIANCE.md **[I]** (not re-checked). | PARTIAL |
| §4.3, §4.8 winners sign a copyright transfer, all co-authors | A project `LICENSE` file is **not** required by the task or the regulations; the transfer agreement governs. Choosing a licence is a team decision, not a compliance gap. | n/a |
| §1.4, §5 the general HackNation event regulations apply | Not in the repo. | **[?]** |

---

## 3. Bonus ("premiowane") items — brief

Scored only if the basics hold. Status from code reading **[V]** unless marked.

| Item | Status |
|---|---|
| Image/audio verification (OCR, transcription, metadata, reuse search) | Not implemented; disclosed. Organisers' F is optional. |
| Source comparison and evidence chain | Implemented (stance per item, R2 conflict rule). In the eval's three conflict cases R2 never fired (`conflicting=False`); two were handled by the "different measure" note instead. |
| Multilingual search, Polish answer | Partial: multilingual NLI, English incident records; no query translation. |
| Open/replaceable source catalogue with qualification, update and exclusion rules | Implemented: `data/sources/*.json`, `/admin`, scheduler, `docs/SOURCE_REGISTRY.md`. Strongest bonus item. |
| Pluggable channels/models/sources | Implemented. |
| Match to known incidents / verified corpus; domain never decides | Implemented for claims; URL-to-material matching (organisers' I) does not work. |
| Export CSV/JSON; OpenCTI/DISARM | CSV/JSON yes; STIX/DISARM no. |
| Controlled archiving | Not implemented (deliberately) — but see Z6: uncontrolled archiving exists in git. |
| Limited non-EEA dependencies, self-hosting, processing location | Implemented and documented; `engine.processing` in every result. |
| Closed information loop, grouping | Implemented (queue + grouping); no outbound notification. |

---

## 4. Closing the mandatory gaps — ranked plan

Ranking = (risk of losing points or failing a gate) × (cheapness). Weights refer to §8.

### G1. Push the real system; clean the repository — 45–60 min — gate risk
- Finish the merge, then commit and push everything listed in F4. Decide deliberately whether
  `data/corpus/live_web.jsonl` ships (it makes the organisers' Wrocław/PAP examples local hits; if it ships, say in
  the README that it is a cache of pages fetched by live search).
- `git rm -r --cached data/raw` (files stay on disk). History rewrite (`git filter-repo --path data/raw
  --invert-paths`) needs every teammate to re-clone — do it only if the repo is or will be public, and coordinate.
- Pin dependencies: `uv pip freeze > backend/requirements.lock` and reference it in the README.
- Regenerate SOURCES.md and align the counts in README / COMPLIANCE.
- Verify: fresh clone into a temp dir → follow the README verbatim → `/api/health` returns the expected document
  count in under a minute after model download; `git ls-files data/raw | wc -l` is 0.

### G2. Formal deliverables outside the repo — 3–4 h — gate risk
PDF (≤ 12 slides, the seven named topics), video (≤ 3 min, link), description (≤ 4 000 chars), team name. Use the
honest numbers from G8. Do not show the fictional demo modes.

### G3. Citation correctness: choose the fragment by stance, then measure it — 3–4 h — 30 % criterion
Problem **[V]**: `_best_fragment` (`engine.py:61-79`) picks the window with the highest lexical overlap with the
claim. For fact-check articles that is typically the sentence describing the rumour ("Na Facebooku pojawiło się
nagranie rzekomo przedstawiające…"). For fact-check evidence the fragment is never stance-checked — the verdict
comes from the publisher's rating (`engine.py:443-455`).

Design (simplest sound version):
1. For each *decisive* candidate only (≤ 3 per claim), build the 1–2-sentence windows of the document's non-synthetic
   chunks (cap ~24), score `NLI(window → user claim)` with the already loaded model, and pick the window with the
   highest contradiction (rating false), entailment (rating true) or, for misleading/mixed, contradiction-or-cue.
   Flip the target when `same_claim is False`.
2. Fallback when no window clears ~0.6: first window containing a debunk cue (`nieprawd|fałsz|nie ma dowod|w
   rzeczywistości|zdementowa|nie potwierdz|manipulac`). If still nothing, keep the lexical fragment but label it
   "kontekst" and lead the answer with the publisher's rating line.
3. For numeric/legal-date decisions (`c.numeric`), quote the sentence that contains the bound value or the title line
   (case A5 currently quotes a paragraph without the date).
4. Raise the fact-check claim quote limit in `answer._q` from 150 to ~240 chars, or cut around the matched words.
5. Eval: add `citation_correctness_auto` (share of decisive main-evidence fragments whose stance agrees with the
   verdict) **and** write `citation_sample.csv` (30 random rows: claim, verdict, fragment, URL, empty "supports?"
   column) for one teammate to label by hand. Report both; the automatic number is circular (same model selects and
   scores), so the hand-labelled one is the figure for the slide.

Files: `backend/prawdowid/engine.py`, `answer.py`, `eval/run_eval.py`. Risk: +0.3–0.8 s CPU per decisive claim;
NLI on Polish is imperfect (hence the cue fallback). Done when the hand-labelled sample is ≥ 85 % and macro-F1 is
unchanged.

### G4. Rate limit that cannot fail a jury batch — 15 min — "End-to-end 100 %"
Raise the default to ~120/min, add `Retry-After`, key on `X-Forwarded-For` / `CF-Connecting-IP` when the server is
started with `--proxy-headers`, and prune empty deques. File: `api.py:36-49`, `config.py:51`. Verify: 60 sequential
`POST /api/check` from one host all return 200 (run by the team, not by this audit).

### G5. Make the organisers' own examples pass (A-1, I; disclose C and B) — 3–4 h — 30 % criterion
- **A-1 (question about a multi-part fact-checked claim) [I]:** the Demagog `claimReviewed` is two sentences ("…depesza
  … została usunięta. Tusk wszedł w buty Cimoszewicza…"), which lowers cosine and NLI entailment against a
  one-sentence question. General fix: index each sentence of a multi-sentence fact-checked claim (and the article
  title) as an extra row in the claim index pointing to the same document; return the matched text from
  `INDEX.match_claims` and use *that* text in the NLI pairs and in `same_claim`. Files: `index.py:246-255,274-283`,
  `engine.py:383-409,443-447`. This also targets the dominant residual error class in the blind sets ("brak dowodów"
  instead of a verdict on paraphrases: H23, H29, B2-04, B2-06, B2-07). Verify with `eval/debug_claim.py` on the PAP
  question, then re-run all three sets for regressions.
- **I (URL that cannot be fetched):** when the fetch fails, derive a query from the URL slug
  ("premier-nie-ma-powodu-do-paniki-prognozy-nie-sa-przesadnie-…") and run claim/title matching on it; present a hit
  as "dopasowanie na podstawie adresu — kontekst, nie werdykt" and say explicitly when nothing matches. File:
  `service.py:108-138`. ~1 h. The full outbound-link index (COMPLIANCE gap 3) is not needed for the demo.
- **C and B:** do not attempt in the remaining time. List them under "przypadki, których system nie obsługuje".
- Hard-cap the live stage so no answer exceeds ~20 s (the 32.8 s run): one deadline for search + fetch + re-verify,
  `LIVE_BUDGET_S` ≈ 10. File: `websearch.py:67-73,835-889`.

### G6. Prompt injection: log what you cannot pattern-match — 1.5–2 h — 20 % criterion, metric ≥ 90 %
- Scan the **raw HTML** of fetched pages as well as the extracted text: comments, `hidden`/`display:none` blocks,
  `meta`, `alt`/`title` attributes. Today only `page["text"]` after trafilatura is scanned (`fetch.py:53`,
  `service.py:98,130`), so an instruction in a comment is ignored but never recorded **[V]**.
- Add a second, general detector behind the regex list: sentences that address the system (second-person imperative
  plus a meta noun such as model/bot/asystent/system/instrukcja/zasady/werdykt/źródła/prompt), optionally confirmed by
  the existing NLI model as zero-shot ("Ten tekst zawiera polecenie skierowane do systemu, który go analizuje").
  A false positive costs only a neutral notice.
- Write 10–15 *new* attack strings (including page-borne ones) that nobody on the team has seen in the code, run them
  once, and report that first-contact number.
Files: `security.py`, `fetch.py` (return raw HTML or its stripped text), `service.py`, `websearch.py:666`.

### G7. Privacy that matches the claim — 1–1.5 h — 20 % criterion
- **P1 [V]:** `ClaimResult.claim` is the unmasked sentence (`engine.py:604`), stored in `result_json` (`store.py:64`)
  and returned by the unauthenticated `GET /api/check/{id}` (`api.py:74-79`). Reproduced without models: an input
  with a PESEL, phone and e-mail yields `claim.text` containing all three while `mask_pii(input)` masks them.
  Fix: after the engine has finished, mask every user-derived string in the result object (claim, short answers,
  `security_events.detail`, `live_search.query`) before returning and saving. Do **not** mask before retrieval:
  the current phone pattern would destroy numeric claims (P2), and the engine needs the raw numbers.
- **P2 [V]:** the phone pattern (`textutil.py:239`) turns "123 456 789 zł" into "[TELEFON] zł". Require a phone
  context (tel/kom/nr/+48) or exclude numbers followed by a currency or unit.
- **P3 [V]:** `purge_expired` runs once at startup and deletes only `checks` (`store.py:92-97`, `api.py:58`);
  `delete_session` likewise (`store.py:85-89`). Extend both to `security_events` and `errors` by `check_id`, drop
  deleted ids from `cases.sample_check_ids`, expire closed/old cases, and call the purge from the scheduler tick.
- Add three PII cases to the eval so the claim is backed by a test.

### G8. Honest evaluation package — 2 h — required by F7
See section 5. Deliverables: strict and lenient F1 side by side; citation correctness; measured cost of 100 tests
(sum of `engine.cost_estimate` over the run); `eval/cases_organizers.jsonl` with the docx questions and a run with
live search **on**; first-run numbers labelled as the estimate; eval pointed at a throwaway DB
(`PRAWDOWID_RUNTIME_DIR`). Fill the COMPLIANCE placeholders from that run, including the three FAIL rows.

### G9. Channel consistency that survives live search — 45 min — 15 % criterion, metric 100 %
- Make `/czat` use the webhook adapter by default (keep the async path for the progress window, but take the reply
  text from `/webhooks/...?demo=1`), or at least invert the checkbox default. File: `web/czat.html:74-91`.
- Add a short-TTL result cache keyed by the normalised input (10 min): the same question on a second channel returns
  the same stored verdict and evidence. File: `service.py`.

### G10. Smaller mandatory touch-ups — 1.5 h total
- Notify the designated user (M12): `PRAWDOWID_NOTIFY_WEBHOOK` / e-mail on priority "wysoki"; store
  `notified_at` / `notify_error` on the case and say "powiadomiono" only when the call returned 2xx. 1 h.
- Archival warning (T4): when the decisive evidence is older than `stale_days`, always append the date to
  `limitation_line`. 15 min, `answer.py:270-296`.
- Missing Google key (T11): add a `live_search.steps` entry "google_factcheck: nieaktywny (brak klucza)". 15 min.
- Label fact-cards (B2a): show "Karta danych — wartości z [źródło], opis zestawiony przez Prawdowid" instead of
  "Fragment źródła" for records tagged `fact-card`, and explain it in `/metodologia`. 30 min.
- Tighten `answer._related` (B3): require two shared topic stems besides a place name. 20 min.

### G11. Demo-day configuration — 15 min
`PRAWDOWID_SCHEDULER=0` during judging (or see I2), `PRAWDOWID_JOB_WORKERS=4`, real admin/moderator tokens on any
hosted instance, a fresh `data/runtime/` so the moderator panel is not full of eval cases.

---

## 5. Evaluation soundness

**Macro-F1 [V].** `run_eval.py:41`: `gold = pred if pred in acceptable else acceptable[0]`. 35 of 145 cases list
several acceptable labels, in most of them `brak_dowodow`. A missed fact-check match therefore counts as a correct
abstention. Recomputed from the stored `results.json` with the first label as gold:

| Run | Reported | Strict | Cases rescued by a secondary label |
|---|---|---|---|
| dev (38), 2026-11-21 | 1.000 | 0.909 | B1, B2, E1 |
| held-out (57), 2026-11-21 | 0.937 | 0.831 | H28, H43, H46, H47, H48, H49 |
| blind-2 (50), 2026-11-21 | 0.901 | 0.805 | B2-32, B2-43, B2-44, B2-46, B2-48 |
| blind-2, first run | 0.747 | **0.644** | six cases |

The class set is right (five classes, zero-support classes skipped). Rows where the system returned a non-OK status
despite an expected verdict would be silently dropped from F1 (`run_eval.py:86`); there were none in the stored runs.
Only the first claim of each input is scored.

**"After fixes" on blind sets [V].** The README is candid that first runs are the honest estimate. COMPLIANCE.md is
not: its summary line reports the post-fix figures. The fixes include vocabulary taken from the blind cases
(section 2.6), so the post-fix numbers are development-set numbers. The first held-out run (0.774) cannot be
reproduced from the repo. The first blind-2 run also contained two wrong-direction verdicts (B2-21 true→false,
B2-26 false→true) — 4 % on unseen data, relevant because the README states that no case ends in a false verdict.

**Citation coverage and correctness [V].** Coverage is tautological. Correctness is not implemented although the
runner's docstring and COMPLIANCE.md describe it. Manual sample (16 of 79 decisive results, seed-random, read from
the DB): clearly supporting — H24, H50, F1, F4, B2-23, B2-19, B2-03; weak — F2, F3; not supporting — E4, F7, H31,
H08, F6 (the last two quote the sentence that *asserts* the false claim), A5, B2-08. This is one auditor's judgement
on a small sample; treat it as "roughly half", not as a measurement.

**Organisers' scenarios.** Covered by the team's own cases only loosely. Conflict: 3 cases, each accepting three of
five labels. Archival context: 7 cases, all accepting `brak_dowodow`; 1 detected. Hostile source page: none in the
case files (one unit test). URL/incident: 2 cases. API failure: none in the case files (manual run only).
Cross-channel: 8 easy cases. Loop: 1 pair.

**Live search [V].** Every reported number is with `PRAWDOWID_LIVE_SEARCH=0`; the default for a jury run is on.
From the audit DB (interactive checks after 15:00 UTC): the live stage ran in 50 of 192 checks, ended in an error
or timeout in 11, produced documents in 24, and supplied the decisive evidence in **2**. It costs a median of 11 s
when it runs and changes the outcome 4 % of the time, while making answers non-reproducible. Recommendation: keep
it (it is what makes the organisers' Wrocław example work on a fresh corpus) but cap it at ~10 s and report one eval
run with it on.

**Latency [V].** In-process, live search off, no HTTP; NLI is loaded lazily on the first case. The median is real for
local hits. A judge asking about something not in the corpus waits 6–20 s, occasionally 30+.

**Hermeticity [V].** The eval writes to the production SQLite file (1 251 `eval` rows; 93 open cases). The loop
test joins a case left by an earlier run, so it passes without proving creation.

---

## 6. Infrastructure soundness

| # | Topic | Finding | Verdict |
|---|---|---|---|
| I1 | JSONL corpus + NumPy index + BM25 in memory | 4 402 docs / 21 560 chunks; startup build 4.5 s from the embedding cache; brute-force cosine is instant at this size. | Fine for a hackathon and for a pilot on a closed corpus. |
| I2 | Scheduler inside the API process, on by default | Daemon thread ticks every 60 s, fetches due sources, then hot-reloads the index (`sources/scheduler.py:220-261`). `INDEX.reload()` swaps `__dict__` under a lock that readers never take (`index.py:164-177`); a check that started on the old index can resolve positions against the new one **[I]** — in the worst case a fragment is attributed to the wrong document. Reload also embeds new texts on the same CPU the NLI model uses. | Real but low-probability risk to "no fabricated sources" and to demo latency. Turn the scheduler off while judging; later, hold a snapshot of the index per request. |
| I3 | SQLite, single shared connection | Writes are locked, reads are not; journal mode `delete`; no busy timeout set. One process: fine. A second writer (eval, CLI) can block or drop an audit write, which is swallowed. | Fine for the demo. Enable WAL + `busy_timeout`, and keep eval on its own DB. |
| I4 | In-memory job state, 2 workers | `jobs.py:32-33`: a restart loses running jobs; with 6–20 s live-search checks, a third simultaneous juror waits in the queue. Multiple uvicorn workers would break job polling, rate limits and live-added documents. | Fine single-process; raise workers to 4; correct the "bezstanowe" claim in COSTS.md. |
| I5 | Rate limiting | See G4; also unbounded per-IP dict. | Real risk (too strict for the jury, absent on four endpoints). |
| I6 | Secrets | `.env` ignored, untracked, never committed; values not inspected. Keys only from env; Google key never logged (`websearch.py:596-597`). Default panel tokens are public. | Fine; change tokens on a hosted demo. |
| I7 | `data/raw/` in git and on the remote | See Z6. | Real legal/optics risk; untrack now, rewrite history if the repo goes public. |
| I8 | Admin API | Token-gated; `legacy_script` restricted to `ingest/*.py` by regex (`sources/registry.py:23,155-159`), but arguments are free-form and the default token is published. | Acceptable locally; not on a public host with default tokens. |
| I9 | Reproducible install | Unpinned requirements, roughly 1 GB model download (estimate), heavy optional packages (playwright, discord.py, mcp) in the base requirements. | Real risk for "powinien dać się uruchomić przez jury". Pin; consider a Dockerfile with a model cache layer (optional per §4, ~1 h). |
| I10 | PII and retention | See G7. | Real gap against a mandatory row. |
| I11 | SSRF | Scheme/credentials/private-range checks on every redirect hop; DNS resolved twice (rebinding window). | Fine for a prototype; mention in RISKS. |
| I12 | Missing LICENSE / Dockerfile | Neither is required by the task (Docker is listed under "może zawierać"; rights are handled by the transfer agreement). | Not a compliance gap. |

---

## 7. Where `docs/COMPLIANCE.md` is overstated

| Row in COMPLIANCE.md | Claim | Finding |
|---|---|---|
| Section 6 table | "Uruchomione raz … Szczegóły: ta tabela" | The table is the placeholder `@@AJ@@`; the actual run has three failing rows (A-1, C, I). |
| Metrics line | macro-F1 `@@F1DEV@@` …; "Poprawność cytowania … mierzona automatycznie" | Placeholders; citation correctness is not computed anywhere. |
| "Brak sfabrykowanych źródeł ✅ … cytat musi występować dosłownie w źródle" | V2 gate | V2 checks the team's stored text; fact-card text is template-generated. |
| "Prywatność ✅" | masking, retention, session deletion | Masking only on `input_masked`; purge and deletion only on `checks`. |
| "Bezpieczeństwo ✅ … 30 zapytań/min/IP" | rate limiting | Only `POST /api/check*`; too low for a 30-case batch. |
| "Odporność na prompt injection ✅ … 100 % (dev/ślepe)" | — | 60 % and 25 % on first contact for "logged"; patterns fitted afterwards. |
| "Znacznik publikacji … preferencja aktualnych … `NIEAKTUALNE_DOWODY`" | — | No recency preference; that reason code is never emitted; 49 undated documents. |
| "Zakaz: archiwizacja … korpus: twierdzenie, ocena, krótki fragment, link" | short excerpt | Median 2 400–2 900 chars per fact-check record; `live_web.jsonl` up to 6 000. |
| "Dwa kanały ✅ … czat demo (`/czat`)" | — | `/czat` bypasses the adapter unless a checkbox is ticked. |
| "Wyniki testów (sekcja 6) ✅" | — | Two mandatory metrics unreported (citation correctness, measured cost of 100 tests). |
| "Rozpoznawanie 1–3 twierdzeń ✅" | — | Short inputs are always one claim. |
| "Luka 4: plik LICENSE" | listed as a gap | Not required by the task or the regulations. |

Rows that hold up as written: verdict classes and separate statuses; explicit premises; same logic across channels;
recommendation vs actual hand-over wording; domain never decides; neutral source-status notice; no reverse-image
claim; secrets out of the repo; observability including cost estimate; external-dependency documentation.

---

## 8. Do this first

| # | Action | Estimate |
|---|---|---|
| 1 | Finish the merge, commit and push all untracked code/data/docs; `git rm -r --cached data/raw`; pin dependencies; test a fresh clone. (G1) | 1 h |
| 2 | Raise and proxy-proof the rate limit; scheduler off, 4 job workers, real tokens and a clean runtime DB for the demo host. (G4, G11) | 30 min |
| 3 | Stance-based fragment selection + citation-correctness metric + 30-row hand-labelled sample. (G3) | 3–4 h |
| 4 | Sub-sentence claim index for multi-part fact-checked claims; URL-slug fallback; hard cap on the live stage; re-run all sets. (G5) | 3–4 h |
| 5 | Mask PII in the stored/returned result, fix the phone pattern, extend purge/deletion to side tables. (G7) | 1–1.5 h |
| 6 | Scan raw HTML for injections, add the general detector, measure on unseen attack strings. (G6) | 1.5–2 h |
| 7 | Honest eval package: strict F1, organisers' A–J file with live search on, cost of 100 tests, separate eval DB; fill COMPLIANCE placeholders with the real rows. (G8) | 2 h |
| 8 | Slides (≤ 12), video (≤ 3 min), description (≤ 4 000 chars) using the numbers from step 7. (G2) | 3–4 h |

If time runs out after step 2, steps 7 and 8 still have to happen: an honest table with three known failures is a
better submission than placeholders.
