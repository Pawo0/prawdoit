# eval/organizers — the organisers' reference scenarios as an always-run test

The organisers' document `rules/Czy we Włoszech ostatnio odbywał się strajk generalny.docx` lists scenarios A–J: a
question to the chatbot and an example answer for each. This directory turns that document into a test that every
change to the verification engine has to pass. Baseline (commit `84047c3`, 21.11.2026): `baseline/results.md`.

## Run

```bash
# everything, strict (exit 1 if any variant fails; the unsupported screenshot scenario counts as a failure)
backend/.venv/bin/python eval/organizers/run_organizers.py

# while known failures remain: fail only if something that passed in the baseline fails now
backend/.venv/bin/python eval/organizers/run_organizers.py --no-regress-from eval/organizers/baseline/results.json

# other switches
#   --allow-known-gaps     report structurally unsupported inputs (today: F1, the screenshot) as gaps, exit code unchanged
#   --only A,C,J2          scenario letters or id prefixes
#   --tier offline         text-only variants;  --tier controlled  = loopback pages and forced failures
#   --out DIR / --no-write where results.md and results.json go (default: this directory)
#   --keep-runtime         keep the temporary database and index copy for inspection

# opt-in network tier: real Google Fact Check Tools calls (J4, J5). Not deterministic, never part of the gate.
# The key is taken from the environment (PRAWDOWID_GOOGLE_FACTCHECK_KEY) or, and only that variable, from a dotenv file;
# it is never printed and is masked in everything that is written.
backend/.venv/bin/python eval/organizers/run_organizers.py --tier network --google-key-file .env --out /tmp/organizers-network

# as a unit test (same strict run in a subprocess, so it fails until every variant passes;
# PRAWDOWID_ORGANIZERS_ARGS="--allow-known-gaps" passes flags through, PRAWDOWID_SKIP_ORGANIZERS=1 skips it)
backend/.venv/bin/python backend/tests/test_organizers_scenarios.py
```

Runtime, measured on 8 CPU cores with the models already downloaded: 30–45 s for the default run — 14–26 s to load
the corpus and the two models, 15–17 s for the 16 variants (21 pipeline calls); peak RSS 3.3 GB. Exit codes: 0 pass,
1 failures (or regressions with `--no-regress-from`), 2 the scenario file is out of sync with the document.

The default run needs no internet, and nothing is written into `data/`. The run uses a fresh temporary SQLite
database (so the case counter of scenario H starts from zero and the demo database is never touched), sets
`PRAWDOWID_LIVE_SEARCH=0` and `PRAWDOWID_SCHEDULER=0`, removes the Google / Brave / SearXNG / LLM settings from the
environment, redirects the live-search corpus file to the temporary directory and works on a temporary copy of the
embedding cache (`data/index`; the server rewrites those tracked files whenever the corpus has texts it has not
embedded yet). The temporary directory is deleted at the end (`--keep-runtime` keeps it). Three consecutive runs at
the baseline commit gave identical results.

## Files

| File | Purpose |
|---|---|
| `build_scenarios.py` | Source of the expectations. Reads the question templates and example answers verbatim from the `.docx` (standard library) and writes `scenarios.jsonl`. Edit expectations here, then re-run it. |
| `scenarios.jsonl` | One record per scenario variant (generated). |
| `run_organizers.py` | Runs every variant in-process through `service.run_check`, prints the table, writes `results.md` / `results.json`. Re-reads the `.docx` on every run and stops with exit code 2 if `scenarios.jsonl` no longer matches it or a row of the document has no scenario. |
| `pages/*.html` | Controlled pages for B2, I1, I2 (E uses `web/demo/injection.html`). Served from 127.0.0.1 during the run. |
| `fixtures/f_screenshot.png`, `make_fixtures.py` | The screenshot for F and the script that drew it. |
| `baseline/` | Results at the commit the test was written against. Do not overwrite; it is the reference for `--no-regress-from`. `baseline/network/` holds the one run of the network tier. |
| `results.md`, `results.json` | The latest run. |

## Scenario variants

`tier`: `offline` = a text question, live search off; `controlled` = needs a page served from the loopback address or
the live stage with a forced failure; neither needs the network, and together they are the default run and the gate.
`network` = real calls to Google Fact Check Tools, run only with `--network` or `--tier network`.

| Id | Document row | How it is driven |
|---|---|---|
| `A1-depesza-pap` | A, first example (placeholders) | text; placeholders filled from the Demagog record (Donald Tusk, flood, September 2024); a second filling (“13 września 2024 r.”) must give the same result |
| `A2-strajk-wlochy` | A, second example | text, verbatim |
| `B1-stare-nagranie` | B | text only (Michał Woś, 2026, Trybunał Konstytucyjny); second filling “we wrześniu 2026 r.” |
| `B2-stare-nagranie-link` | B | link to a controlled page with the post + the question, as in the document |
| `C-rozbieznosc-700-650` | C | text, verbatim |
| `D-brak-dowodow-pcim` | D | text, verbatim |
| `E-instrukcja-w-zrodle` | E | question + link to `web/demo/injection.html`; control run = the same question without the link |
| `F1-zrzut-ekranu` | F | image `fixtures/f_screenshot.png` through an image field of `CheckRequest` (`image_b64`, `image_base64`, `image` or `image_path`) — none exists today, so it is reported as unsupported |
| `F2-tekst-ze-zrzutu` | F (derived, not in the document) | the text an OCR would return, sent as text — the part of F that does not need OCR |
| `G-spojnosc-kanalow` | G | the question through `run_check(channel="web")` and through the WhatsApp demo adapter (`channels.meta._wa_process`, the payload shape Meta sends) |
| `H-powtorne-zgloszenie` | H | question (web), the organisers' paraphrase (second channel), then the question again while the case store is made to fail |
| `I1-ta-sama-depesza` | I, matching variant | question + controlled page with the headline, topic and date of the dispatch Demagog describes |
| `I2-inna-depesza` | I, non-matching variant | question + controlled page about another dispatch (same site, person and topic; other headline and date) |
| `J1-api-dziala` | J, “working API and a hit” | text |
| `J2-awaria-api` | J, forced failure | `PRAWDOWID_LIVE_SEARCH=1` + `PRAWDOWID_FORCE_FAIL=google_factcheck,websearch`; the publication is in the local corpus |
| `J3-awaria-bez-kopii-lokalnej` | J, forced failure | as J2, and the publication is hidden from the local index for this run, so the failed live search is the only way to find it |
| `J4-api-google-na-zywo` | J, “working API and a hit”, for real (network) | live stage on with the real key; the publication is also in the local corpus; the Google step must report at least one review from a registry domain |
| `J5-api-google-jedyne-zrodlo` | J, “working API and a hit”, for real (network) | as J4, with the publication hidden from the local index: the answer can only come from Google's index — what a corpus without this article does |

A scenario letter passes only if all its variants pass. In the network tier the requests carry a neutral User-Agent
instead of the application's own.

## What the expectations mean

Expectations test substance, not the wording of the example answer. Regular expressions are case-insensitive and
matched on whitespace-normalised text. Two surfaces are checked:

- **reply** — the chat message a second channel sends (`channels/formatting.chat_text`): short answer, decisive
  source with link, “Podstawa” and “Ograniczenie” lines, notices. This is the strictest surface; the main web view
  shows the same fields first.
- **page** — everything the analysis page shows: the reply fields plus the explanation and every evidence item with
  its quoted fragment.

| Key in `expect` | Meaning |
|---|---|
| `status_in` | `CheckResult.status` (technical failure / clarification / out of scope are statuses, never verdicts) |
| `verdict_in`, `verdict_not_in` | verdict class of every claim in the result. With no claim at all it passes only for a non-`ok` status (no verdict was given) |
| `single_claim` | the message produced exactly one claim (C: the “Dlaczego…?” sentence is not a second claim) |
| `no_conflict` | the result is not flagged as “conflicting sources” |
| `opener`, `opener_not` | how the short answer starts: a plain “Nie.” / “Tak, …” / an abstention (“Nie udało mi się…”); A2 must not open with a bare yes or no |
| `cites_main` | the decisive source (`main_evidence`) is the expected publication, by URL |
| `cites_evidence` | the expected publication is among the shown evidence (used where no verdict is expected) |
| `cites_shown` | the reply contains the link to the expected publication |
| `not_cites_main`, `no_main_evidence` | the fact-check is not used as a decisive source / no decisive source at all |
| `quote.verbatim` | the quoted fragment is a verbatim part of the record in `data/corpus/*.jsonl` (checked against the file, not through the engine) and the link equals the record's URL |
| `quote.supports_any` | the quoted fragment itself carries the finding (e.g. “nie została usunięta”, “nie jest jedynym miastem”) — the §6 metric “czy cytowany fragment rzeczywiście wspiera tezę” |
| `quoted_factchecks_only` | the short answer quotes no checked claim of any other publication |
| `reply_must`, `page_must` | every group must be found: a group is `{name, any: [regex…], unless: [regex…]}`; with `unless` the match is per sentence and a sentence containing an `unless` pattern does not count (negations, hedges) |
| `reply_must_not`, `page_must_not` | no group may be found (e.g. “nie ma takiego artykułu”; a rating of some other claim attached to an abstention) |
| `page_fetched` | the linked controlled page was really downloaded (`url_meta.url`) |
| `security` | at least N events of the given kind coming from the page, in the result and in the `security_events` table |
| `same_as_control` | verdict, decisive source and evidence list equal the control run without the page (E: “instrukcja nie zmienia werdyktu ani dowodów”) |
| `channels_consistent` | G: same verdict, same decisive publication, same evidence list and same short answer on the web and in the second channel; the adapter produced exactly one reply and one audited check |
| `one_case`, `case_notice` | H: both submissions carry the same case id, the case row has `count = 2` and lists both check ids; with the case store failing, the reply must not mention a case |
| `live_status`, `error_logged` | J: the live stage ran and reported the failure; the failure is in the `errors` table |
| `google` | J4/J5: the Google Fact Check step of the live stage has the given status and returned at least N reviews published on registry domains |
| `ocr_must` | F: the text read from the image contains the claim and the visible date |

`advisory` holds the same kind of checks for things the document asks for conditionally (“if the question also
checks…”) or that go beyond the minimum; they are reported as `○ (advisory)` and never change the result.

Checks applied to every answer, whatever the scenario:

- every verdict rests on a decisive source whose quote is verbatim in the corpus (no fabricated sources);
- a non-`ok` status carries no verdict;
- a case id is mentioned only if the store really holds this submission under that case;
- the answer took at most 30 s;
- the corpus contains the publications the scenario depends on (a missing record is reported as the reason).

## Publications the scenarios depend on

| Scenario | Record | File |
|---|---|---|
| A1, F, I | Demagog, 16.09.2024, “Donald Tusk uspokajał przed powodzią. Depesza PAP nie została usunięta” (`live_web:39b8c0e4aebf5572`) | `data/corpus/live_web.jsonl` |
| A2 | MSZ / Odyseusz, 19.11.2026, “Włochy: komunikat i ostrzeżenia MSZ dla podróżujących” (`msz_odyseusz:IT:2026-11-19`) | `data/corpus/msz_odyseusz.jsonl` |
| B | Demagog, 17.09.2026, “Policja zasłania protestujących parawanem? Woś udostępnia stare nagranie” | `data/corpus/demagog.jsonl` |
| C | Demagog, 05.04.2024, “Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?” (`live_web:8370cbabc1f5ad69`) | `data/corpus/live_web.jsonl` |
| E, G, J | Demagog, 12.03.2024, “Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy” (`live_web:9493cdbd8a0a12d2`) | `data/corpus/live_web.jsonl` |

All five are in the corpus at `84047c3`, so every baseline failure is of the class “fails although the publication
is in the corpus” (each result carries a `failure_class`: that, “publication missing from the corpus”, “input kind
not implemented” or “no publication involved”). But three of the five are not in the harvested
`data/corpus/demagog.jsonl` (at `84047c3` it holds 20 documents from 2024 and neither the PAP-dispatch nor the two
Wrocław articles); they exist only in `live_web.jsonl` (tracked since `d85b69d`), 25 records the live search
captured during testing on 21.11.2026, 16:40–16:42 UTC. If that file is regenerated or pruned before the Demagog archive is harvested, A1, C, E, G, I and
J lose their publication and the run says so (“corpus contains …” fails). The dependency check goes by URL, so it
keeps working when the same articles arrive in `demagog.jsonl` under other ids. The PAP dispatch itself (the primary
source of A1) is not in the corpus: pap.pl blocks automated access.

## Baseline (commit `84047c3`): what fails and where it is lost

6 of 16 variants pass: D, E, G, H, I2, J1. Line numbers refer to `84047c3`. “Measured” = numbers from a diagnostic
run of the same models on the same corpus; nothing in `backend/` was changed.

| Variant | Stage that loses it | Where | Smallest general fix |
|---|---|---|---|
| A1 | same-claim matching | `engine.py:356` (`same_claim`), pairs built at `:406-409` | The checked claim is two sentences (“…została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r.”). Cosine is 0.896 (enough on its own), but the reverse NLI direction reads a contradiction (0.58 ≥ 0.5) and vetoes the match. Measured on the first sentence alone: cosine 0.92, contradiction 0.03 / 0.00 → match. Fix: score the whole claim and each of its sentences, accept the best unit; never use the article title as a unit (it is the negation of the claim). |
| A2 | channel formatting | `channels/formatting.py:31-36`, `answer.py:175-181, 214-218` | Substance is right (announced for 20 November, MSZ notice quoted, no yes/no). The reply names “Ministerstwo Spraw Zagranicznych” but gives neither the Odyseusz link nor its name: a source line is printed only for a decisive source, and the “what would settle it” hint is dropped when a related item is shown. Fix: remember which evidence item was presented as related and print its source line with the link. |
| B1, B2 | stance for fact-check articles | `engine.py:413` (fragment NLI only for official/media), `:443-459` | The question is about the material (“did the film show a then-current protest?”), the checked claim is the politician's caption; cosine 0.74–0.83, no match. The article's own finding (“Materiał nie dotyczy jednak aktualnych wydarzeń – pochodzi z marca 2021 roku”) is retrieved and shown, but never judged. Measured: NLI contradiction 1.00 for that fragment, but ≥ 0.8 also for unrelated sentences of the article, so a fragment rule needs tight gates (summary bullets only, cosine ≥ 0.80, lexical overlap ≥ 0.4, not a restatement of the checked claim) and must be accepted by `eval/bench_polish` (hard negatives). |
| C | claim extraction, same-claim matching, answer wording | `claims.py:34` (meta sentence dropped), `engine.py:356`, `answer.py:151-172` | Three things: the “Dlaczego w analizie Demagoga jest 650 mln zł?” sentence is removed and nothing downstream uses it; the checked claim is a long quote with the 700 mln clause at the end (cosine 0.78; the sentence splitter also breaks it at “przyp.”); the “closest material” picked is another article. Fix: keep the meta clause on the claim; when it names a second number and a candidate fact-check contains the first number in its checked claim and the second in its text, answer from that record: both figures with the verbatim sentence for the second, “not two contradicting measurements”, and the overall rating. Deterministic, no model. |
| F1 | not implemented | `schemas.py:115-119`, `channels/meta.py:31-33` | No image input, no OCR. See “Scenario F” below. |
| F2 | claim extraction / answer wording | `claims.py:44`, `answer.py:118-123`, `textutil.py:129-133` | “Czy Demagog to sprawdzał? <claim>” — the question sentence is discarded as too short, so the answer opens with “Nie.” (reads as “Demagog did not check it”) instead of “Tak, Demagog to sprawdził…”. Fix: detect the who-checked question in a neighbouring sentence and pass it to the answer layer. |
| I1 | URL handling | `service.py:149-153`, `claims.py:29-39` | The meta question itself becomes the claim; the linked page is fetched but not used, and nothing compares it with fact-check records. The reply offers a fact-check about a different PAP dispatch as “closest material”. Measured: the page headline occurs verbatim in exactly one fact-check record (the right one); the headline of the other-dispatch page in none. Fix: for a question about a linked item, match the page's headline and date against fact-check records and report the match with its basis, or say that nothing matches. |
| J2 | answer wording / channel formatting | `answer.py:273-280`, `channels/formatting.py:63-64`, `web/static/app.js:273`, `web/czat.html:52` | The outage notice is in `warnings`, but the chat message and the main web view drop it on the assumption that the “Ograniczenie” line carries it — which is true only for abstentions. Fix: mention the failed live check in the limitation line for every verdict. |
| J3 | answer wording | `answer.py:151-172` (`_related`) | The abstention with the technical message is right, but a fact-check of another claim (“Warszawa 2 razy więcej wydaje… — Fałsz”) is attached because it shares the name “Wrocław”. Measured: that claim covers 14 % of the question's content words, the right one 86 %. Fix: require a minimum coverage of the question's content words before a rated fact-check is shown as “closest”. |

Network tier (run once on 21.11.2026 with the real key, results in `baseline/network/`): both variants fail.

| Variant | Stage that loses it | Where | Smallest general fix |
|---|---|---|---|
| J4, J5 | live search, query building | `websearch.py:799-804` (`start_google` sends `c.query`, the whole claim sentence) | The API call succeeds, but Google's `claims:search` returns 0 claims for the sentence. Measured with the application's own `google_factcheck()`: the full sentence returns 0 for the J, A1, C and B questions, while 2–4 distinctive words return the right Demagog review for A1 (“Donalda Tuska PAP”), C (“Wrocław komunikację”) and B (“Konstytucyjnym Trybunałem Michała Wosia”); for J the words picked by `websearch.keywords()` (“Wrocław przejazdami darmowymi jedynym”) still return 0. Fix: query Google with several short keyword variants in parallel (the way the site search already does, `query_terms`), prefer names and nouns in base form, union the reviews and let the engine's claim matching decide. In J5 the site-search fallback also missed the article within its time budget, so with a corpus that lacks the article the organisers' J question ends in an abstention. |

So J1 passes today only because the article is in the local corpus (captured earlier by the site search).

Also measured: J1 (and J2) pass on a knife edge — forward contradiction 0.50 against the 0.5 threshold of
`same_claim`; on the first sentence of the checked claim it is 0.01. The sentence-level fix for A1 removes that risk.

### Scenario F (screenshot): what OCR would take

Tesseract is not installed and cannot be installed without root. EasyOCR 1.7.2 (Apache-2.0, PyTorch, has a Polish
model) resolves against the project's Python environment with 11 extra packages (about 250 MB): easyocr,
torchvision, opencv-python-headless, scikit-image, shapely, pyclipper, python-bidi, ninja, imageio, lazy-loader,
tifffile. `torchvision` must come from the PyTorch CPU index (`torchvision==0.29.2+cpu`); the default PyPI wheel
fails to import with the installed `torch 2.15.0+cpu`. Measured with the packages in a scratch directory (nothing
was installed into the environment): on `fixtures/f_screenshot.png` EasyOCR (`['pl']`, CPU) read every line
correctly, Polish letters included (“Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie
powodzią, została usunięta!”, “15 września 2024”; confidence 0.66–0.80), in 3.7 s per image, peak 0.95 GB RAM for
the OCR process; the two model files (98 MB) are downloaded on first use. The fixture is a clean rendering; real
screenshots (JPEG artefacts, small fonts, dark mode) were not measured.
Remaining work besides the library: an image field in `CheckRequest` / the API, the upload in the web UI and the
media download in the chat adapters, the “date on the image is not the publication date” sentence, cost and
retention notes in `docs/`. The runner starts exercising F1 as soon as `CheckRequest` has one of the fields
`image_b64`, `image_base64`, `image`, `image_path`.

## Readings chosen where the document is ambiguous

- **A1 / B placeholders** are filled from the Demagog records above. Jurors may fill them with other people and
  dates; the second filling of A1 and B1 is a small guard against fitting one wording.
- **A1, primary source**: the bracketed note is conditional (“if the question also checks…”), so quoting the
  dispatch headline is advisory.
- **C** is called “Sprzeczność: two credible sources give different data” in the task statement, but in the
  organisers' example both figures come from one Demagog article. The test requires the explanation (estimate from
  the statement vs. a specific item and year, plus Demagog's overall rating) and forbids the “conflicting sources”
  outcome.
- **F** is optional in the task statement (“if implemented”), but it is a row of the document, so an unsupported
  image input fails the strict run. `--allow-known-gaps` reports it without failing.
- **I**: the entry is a controlled page, because pap.pl cannot be fetched by a bot. “Shows the basis of the match”
  = the reply states the match in a non-negated sentence, repeats the headline and the date, and links the Demagog
  publication. The non-matching variant only requires that no match is stated and no verdict is given.
- **J, forced failure**: the document's example answer assumes the failed index is the only way to find the article.
  J3 tests exactly that (no verdict, technical message, no “closest” rating of another claim). J2 keeps the article
  in the local corpus: a verdict backed by that cited record is accepted, but the outage must be visible in the
  reply itself.
- **“The bot informs about the record only if the system confirmed it” (H)** is tested in both directions: a case id
  in a reply must exist in the store, and with the store failing the reply must not mention a case.
