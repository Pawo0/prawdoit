# Research summary, 21 Nov 2026: requirements, Polish handling, extension tiers, containers

This file summarises three research reports written today and one integration check, and records the decision
each one leads to. The reports hold the evidence; this file holds the conclusions and the order of work.

| Report | Question it answers |
|---|---|
| [07_requirements_audit.md](07_requirements_audit.md) | Is every mandatory point of the task met, and how do we close the gaps? |
| [08_polish_language_benchmark.md](08_polish_language_benchmark.md) + [`eval/bench_polish/`](../eval/bench_polish/README.md) | Can proper Polish tooling replace our hacks, measured on Demagog claims? |
| [09_architecture_two_tier_and_containers.md](09_architecture_two_tier_and_containers.md) | Is the infrastructure sound, should the extension use two models, how do we containerise? |

Each report was written by a separate agent that did not see the others. The architecture review was given the
code and the task statement only, not our opinions. Claims marked **(checked)** below were re-verified against the
code or data after the reports came in; everything else is the report's own finding.

## Decisions

| Topic | Decision | Reason |
|---|---|---|
| Polish stemmer / lemmatizer | Do not add one | Changed 0 of 170 benchmark outcomes and 0 cases in the three existing eval sets (checked from saved results) |
| Bigger embedder, reranker | Do not add now | Retrieval already puts the right Demagog claim first for 96.9% of inputs; the reranker adds about 1.9 s per query on CPU |
| Where verification errors come from | Fix the same-claim decision and fragment selection, not morphology or retrieval | Failure trace in the benchmark; two other reports point at the same functions independently |
| Second model that tags content as "suspicious" | Do not build | Conflicts with the task rules, and the cheap signal tags true and false content at the same rate |
| Extension tiers | Keep two tiers, make tier 1 a router (`none` / invisible `candidate` / sourced `match`) | High recall without showing an unsourced accusation |
| Containers | Keep the existing one-image Docker setup; fix four mismatches with the current backend | It was validated against the older backend only |
| Split into gateway / tagger / verifier / ingest services | Not for the hackathon | Needs eight code changes (durable job queue, shared DB, index snapshots); one image is enough for a jury run |
| First priority overall | Commit and push the local work | The repository the jury clones does not contain most of today's code |

## 1. Mandatory requirements

The boundary condition (end to end, no fabricated sources, abstention, two channels) is met in substance. The
gaps below are in mandatory sections of the task; full table, designs and verification steps are in report 07.

| # | Gap | Evidence | Fix | Estimate |
|---|---|---|---|---|
| 1 | Most of today's work is untracked; `backend/requirements.txt` has no versions | `git status` (checked) | Commit, push, test a fresh clone | 1 h |
| 2 | `data/raw/` (809 full HTML pages) is tracked and already on the remote | `git ls-files data/raw` (checked) | `git rm -r --cached data/raw`; decide on rewriting history | 30 min |
| 3 | Citation correctness (target ≥ 85%) is not measured | `eval/run_eval.py` has no such metric (checked) | Add the metric and a hand-labelled sample of about 30 rows | 3–4 h with fix 4 |
| 4 | The quoted fragment is picked by word overlap with the claim, so it can be the sentence that restates the false claim | `engine._best_fragment` (checked); the audit's hand sample found about half of 16 fragments support the verdict | Fix the adjacency bug first (section 2), then prefer the fragment that carries the stance | — |
| 5 | Rate limit of 30 checks per minute per IP; the jury set has at least 30 cases; behind a proxy all users share one bucket | `api.py` rate-limit middleware (checked) | Raise to about 120; trust the proxy header | 15 min |
| 6 | PII masking covers the input excerpt and moderator cases only; retention purge deletes only the `checks` table | `mask_pii` call sites and `store.purge_expired` (checked) | Mask the result before saving and returning; extend the purge | 1–1.5 h |
| 7 | Organisers' scenarios: A-1, C and I end in abstention, B was not run, F is not implemented; the table in `docs/COMPLIANCE.md` is an unfilled placeholder | audit's read of the demo database; placeholder (checked) | Index sub-sentences of multi-part claims, add a URL-slug fallback, state C and B as unsupported, fill the table | 3–4 h |
| 8 | Injection scanning runs after text extraction, so HTML comments and hidden text in a fetched page are not seen | report 07 | Scan the raw HTML as well | 1.5–2 h |
| 9 | `/czat` calls the async API directly; the webhook adapter runs only when a checkbox is ticked | `web/czat.html` (checked) | Make the adapter the default path | small |
| 10 | Official "data cards" (GUS, NBP, Eurostat, ELI) show template-generated sentences as "Fragment źródła" | report 07 | Label them "karta danych" in the UI and methodology | small |
| 11 | A missing Google Fact Check key disables that provider silently | `websearch.py` `start_google` (checked) | Report it in `live_search.steps` | small |
| 12 | Notification of a designated user: the case is queued, nothing is sent | report 07 | Webhook or e-mail with a sent / not-sent state | 1 h |

Evaluation numbers need restating before they go into the submission:

- **Macro-F1 is lenient.** When a case accepts several labels, the gold label is set to whatever was predicted
  (`run_eval.py`, `macro_f1`, checked). Counting the first accepted label as gold, the audit gets 0.91 / 0.83 / 0.81
  on dev / held-out / blind-2 instead of 1.00 / 0.94 / 0.90, and 0.64 for the first blind-2 run.
- **"After fixes" results on the blind sets are not blind.** Report the first-run numbers as the estimate.
- **Everything is measured with live search off.** On the demo server the live stage ran in 50 of 192 checks with
  a median of 11.2 s and a maximum of 32.8 s, and decided 2 of them.
- **The eval writes to the live database.** 93 open moderator cases are test debris; clear them before a demo.

Overstated rows in `docs/COMPLIANCE.md`: citation correctness "measured automatically", verbatim quote for data
cards, privacy, rate limit, "short excerpt" (stored excerpts have a median of 2,400–2,900 characters for three
fact-checkers), and the `NIEAKTUALNE_DOWODY` reason code, which no code path emits (checked).

## 2. Polish-language handling

**Result: the hacks are not what limits quality.** The benchmark is 170 hand-written variants of 32 Demagog claims
(inflection, question form, no diacritics, colloquial, paraphrase, shortened, typos, negations, and 27 hard
negatives that swap an entity, predicate or number). It runs in about 4.5 minutes on CPU.

| Measure | Baseline |
|---|---|
| Correct | 141 / 170 (82.9%) |
| Missed (abstained when a verdict was due) | 18 |
| False verdicts | 11, of which 8 on the 27 hard negatives |
| Right Demagog claim ranked first by the embedder | 96.9% |
| Inflected variants | 19 / 19 |
| True paraphrases | 9 / 18 |
| Latency p50 / p95 | 727 / 2137 ms (NLI is 638 / 2047 ms of that) |

| Variant | Outcome against baseline | Cost |
|---|---|---|
| simplemma lemmatizer in the analyzer, full pipeline | 0 fixed, 0 broken; existing eval sets identical | +3–6 s load, +350–400 MB RAM |
| pystempel (Polimorf), BM25 only | Gold rank better for 5, worse for 5; worse without diacritics and on typos | +4–9 s load |
| `sdadas/mmlw-roberta-base` embedder, signal only | Separates positives from hard negatives better (AUC 0.81 → 0.89), no paraphrase gain | about 60 min to re-embed passages |
| `sdadas/polish-reranker-base-ranknet`, signal only | +1 item at rank 1 | +1.9 s p50 per query |
| Drop the lexical gate and close the cosine gap | Fixed 8, broke 6; false verdicts 11 → 18 | — |
| Bidirectional NLI instead of the cosine-only rule | Fixed 16, broke 23; false verdicts 11 → 14 | +64% latency |

Where the baseline fails (21 errors on positives and negations, 8 on hard negatives):

- **Same-claim rule, too strict:** 5 lost to the lexical gate (`lex >= 0.4`) and 4 to the cosine gap 0.78–0.80,
  all with NLI entailment above 0.86.
- **Same-claim rule, too loose:** 6 of the 8 hard-negative false verdicts pass through `cos >= 0.88`, which
  accepts a match with no entailment check (`engine.same_claim`, checked). Example: a claim about Tusk matched to
  one about Trzaskowski at cosine 0.926 with entailment 0.07.
- **Fragment bug:** `_best_fragment` drops sentences of 15 characters or fewer and then joins neighbours in the
  filtered list, so the joined fragment is not verbatim and the quote gate discards the document (mechanism
  checked in code). 70 of 400 sampled fact-check documents have such a window.
- **Diacritics:** one opinion/prediction regex misreads text typed without diacritics.

Both attempts to loosen the same-claim rule produced more false verdicts, because the NLI model over-entails
topical neighbours. The lexical gate and thresholds are compensating for that, so they stay until a better
equivalence signal is measured.

What to do:

1. Fix `_best_fragment` so it only joins adjacent sentences. Expected +2 correct on the benchmark; the fix itself
   has not been run yet.
2. Make the `claim_kind` regexes diacritic-insensitive.
3. Before touching `same_claim`, test a replacement on the benchmark: another NLI model, an entity/number
   agreement guard on the `cos >= 0.88` route, or a small classifier over the existing signals. Accept a change
   only if false verdicts do not rise.
4. Grow the benchmark and split it by claim before tuning anything on it.

No hack can be deleted today. Limits of this result: 32 claims means differences of 2–3 items are noise; the
variants were written by the same agent that read the thresholds (before seeing any output); alternative NLI
models, Morfeusz2 and spaCy were not measured; latency was taken on a loaded machine.

Re-run: `backend/.venv/bin/python eval/bench_polish/run_bench.py --name X`, then
`backend/.venv/bin/python eval/bench_polish/compare.py baseline X`.

## 3. Extension: two tiers

The proposal was a fast model that tags suspicious content and a slower model that verifies it. The system
already has the two tiers (`/api/quick` and `/api/check`). The review recommends keeping that shape and not
adding a tagger that marks content as suspicious:

- **Rules.** The task forbids a judgement from style, source, popularity or a model-generated label, and requires
  a source for every finding. A "suspicious" tag is such a judgement.
- **Signal.** The check-worthiness heuristic tags 62.7% of Demagog's debunked claims and 63.3% of sentences in MSZ
  news. 94.5% of true-rated fact-check claims have a debunked claim within cosine 0.74.

Recommended design:

| Tier 1 state | Shown to the user | What happens |
|---|---|---|
| `none` | nothing | — |
| `candidate` | nothing | Top 3 per page go to tier 2 in the background: local corpus only, no live search, no moderator case, text not stored |
| `match` | badge with fact-checker, rating, date and link | Full check on click |

A badge appears only for a decisive, sourced verdict. No "podejrzane" wording, no percentage; the overlay is
opt-in. Suppress the badge when a true-rated claim is equally close.

Smallest version worth building:

1. Run NLI in `/api/quick` only from cosine 0.80 (it now starts at 0.74 although a match needs 0.80; same output,
   fewer calls).
2. Rate-limit `/api/quick` (it has none).
3. Switch the extension's manual check to `/api/check/async` with polling. It is one synchronous fetch with a
   45 s timeout (`extension/background.js`, checked), and the review reports that Chrome stops a service worker
   whose fetch exceeds 30 s.
4. Add the `candidate` state and an `auto` flag; the API contract is in report 09, section 3.7.

**Why tier 2 misses cases** is a data and matching problem, not model strength:

- 746 fact-check documents have no mapped verdict, including all 290 Konkret24 entries (which also have no
  extracted claim) and 312 from FakeNews.pl (checked). They cannot yield a verdict through claim matching.
- Each fact-check has one index key, its claim or title (`index._build_indexes`, checked). Adding the title and
  first sentence as extra keys raises recall without a new model.
- Claim extraction keeps at most 3 sentences scoring 0.4 or more; 37% of Demagog's debunked claims fall below
  that score.
- The same-claim rule and fragment bug from section 2.

## 4. Infrastructure and containers

The current design is sound for one user and one process. One uvicorn process holds both models, the index, the
job registry, rate-limit counters, caches and the scheduler, so a second replica would break job polling and
could answer the same question differently. For a jury run the risks are:

- no cap on concurrent inference on the synchronous endpoints (only async jobs are capped, at 2 workers);
- the rate limit in section 1;
- the scheduler swapping the index while requests read it; turn it off while judging;
- published default tokens (`demo-admin`, `demo-moderator`) on any public host.

**Existing Docker setup** (`Dockerfile`, `compose.yaml`, `docs/DEPLOYMENT.md`, commit `eeec4ff`). It agrees with
the review's minimal path: one image, one worker, CPU-only torch, non-root user, SQLite on a volume. It is better
in two respects: pinned versions in `backend/requirements-container.txt`, and it refuses to start with the demo
moderator token. It was validated against the older backend (its notes mention a 2,285-document corpus). Read
against the current backend, four things do not work as intended. This is from reading the files; the image was
not built.

| Mismatch | Effect in the container | Fix |
|---|---|---|
| `data/sources/` is not copied and is excluded by `.dockerignore` | The three disabled sources (PKW, Eurostat, KE PL) are indexed, because a corpus file without a registry entry counts as enabled; live search has no trusted-domain list; `/zrodla` and `/admin` are empty | `COPY data/sources`, allow it in `.dockerignore` |
| `ingest/` is not in the image while the scheduler defaults to on | 17 of 53 sources are harvested by `ingest/` scripts and fail | Set `PRAWDOWID_SCHEDULER=0` in `compose.yaml`, or ship `ingest/` with its dependencies |
| `/app/data/corpus` is owned by root, the server runs as UID 10001 | Scheduler output and live-search results (`live_web.jsonl`) cannot be written | Point `PRAWDOWID_CORPUS_DIR` and `PRAWDOWID_SOURCES_DIR` at the state volume with seeding, as is done for the index |
| `compose.yaml` passes a fixed list of variables | `PRAWDOWID_ADMIN_TOKEN` never reaches the container, so `/admin` always uses `demo-admin`; live-search, Google key, WhatsApp and LLM variables are also dropped | Add `env_file: .env`; make `docker/start.py` reject the default admin token too |

Open difference: the existing setup downloads models at first start into a volume; the review bakes them into the
image so a jury run does not depend on Hugging Face (about 2.3 GB estimated). Baking is the safer choice for
judging; the volume is the better choice for frequent rebuilds.

The split into gateway, tagger, verifier, ingest, Postgres and Redis is described in report 09, sections 4.4 and
4.6, with the code changes it needs. None of it is required for the hackathon.

## 5. Order of work

| # | Action | Estimate | Source |
|---|---|---|---|
| 1 | Commit and push; untrack `data/raw`; test a fresh clone | 1.5 h | 07 |
| 2 | Rate limit to about 120 with proxy header; scheduler off and private tokens for the demo | 30 min | 07, 09 |
| 3 | Fix the four Docker mismatches, then build and run `eval/test_container.py` | 1 h | section 4 |
| 4 | Fix `_best_fragment` adjacency; diacritic-insensitive `claim_kind`; re-run `bench_polish` | 1 h | 08 |
| 5 | Citation-correctness metric and hand-labelled sample; strict macro-F1; fill the placeholders in `docs/COMPLIANCE.md` | 3–4 h | 07 |
| 6 | Extra index keys per fact-check; sub-sentence matching for multi-part claims; cap the live stage | 3–4 h | 07, 09 |
| 7 | PII masking of stored results; purge all tables | 1–1.5 h | 07 |
| 8 | Extension: async polling, `/api/quick` rate limit and NLI from 0.80, `candidate` state | 2–3 h | 09 |
| 9 | Injection scan on raw HTML | 1.5–2 h | 07 |
| 10 | Slides, video, description of at most 4,000 characters | 3–4 h | 07 |

Estimates are the reports' own and have not been tested.

## 6. Open questions

- **Automatic tier 2 on passively viewed pages, or click only?** The review recommends automatic for at most 3
  items per page with the local corpus only. Click-only is the more cautious reading of the privacy rules.
- **Rewrite git history to remove `data/raw`?** Untracking stops the problem growing; removal from history needs
  the whole team to re-clone.
- **Bake models into the image or keep the volume?** See section 4.
- **`cos >= 0.88` shortcut.** It causes most false verdicts on adversarial inputs, yet both tested replacements
  were worse. An entity/number agreement guard is the next thing to measure.

## Repository state after today's integration

- Local `main` is at `eeec4ff` ("dockerized backend"), which is upstream plus the Docker commit from
  `github.com/Pawo0/prawdoit` (remote `prawdoit`). The earlier local work is applied on top, uncommitted.
- Four web files conflicted with the UI redesign and were resolved: the redesign is kept, and async checks with
  stages and cancel, short answers and trusted links were ported into it. `web/static/home.js`,
  `web/metodologia.html` and `eval/test_web_ui.cjs` were adjusted for the same reason. `eval/test_web_ui.cjs`,
  `eval/test_extension_ui.cjs` and `eval/test_extension_mock.cjs` pass.
- Backups: `stash@{1}` holds the full pre-merge working tree including untracked files; `stash@{0}` holds the
  tracked changes from before the Docker commit was applied. Nothing was committed or pushed.
