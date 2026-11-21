# bench_polish — does a change to Polish-language handling make verification better or worse?

A small, re-runnable benchmark built from Demagog fact-checks (`data/corpus/demagog.jsonl` = ground truth).
Report with results and interpretation of the first split: `research/08_polish_language_benchmark.md`.

## Two splits — read this first

| | **v1 — tuning split** | **v2 — held-out confirmation split** |
|---|---|---|
| Use it for | diagnosing failures, trying rules and thresholds, fitting anything | confirming, on claims nobody has tuned on, a change that already looks good on v1 |
| Claims | 32 (`seeds.json`, seed 20261121) | 48 other claims (`seeds_v2.json`, seed 20261122) |
| Items | 170 (`variants.tsv` → `bench.jsonl`) | 262 (`variants_v2.tsv` → `bench_v2.jsonl`) |
| Results | `results/<name>.json` | `results/<name>_v2.json` |
| Switch | default (`--set v1`) | `--set v2` |

**Do not tune on v2.** Concretely:

- Develop on v1 only. Run v2 when a change is finished, look at the aggregate numbers and at `compare.py ... --set v2`
  (which items flipped, new false verdicts), and report them. Do not open v2 traces to design a rule, do not pick a
  threshold on v2, do not add a special case for a v2 item.
- A fitted model (e.g. a calibrated "same claim?" classifier) is fitted on one split and tested on the other — never
  fitted or model-selected on both.
- Every look at v2 spends a little of it. The `results/*_v2.json` files are the log of how often it was used; keep them.
- The two splits share no Demagog document, and near-duplicate stories were excluded (see "How v2 was built"), so a
  rule that memorises a v1 claim cannot score on v2.

**Freeze and errata rule (both splits).** The variants were written by hand before any system output was seen. They are
frozen: never edit, delete or re-label a line of `variants.tsv` / `variants_v2.tsv` to make an item pass or because a
result looks odd. If a label turns out to be wrong, add a line to `errata_v2.tsv` (item id, what is wrong, why, date)
and say explicitly in any analysis that excludes or re-labels the item; the frozen file and the headline numbers stay
as they are. New items go into new lines of v1 (never v2), or into a future v3.

## What is in it

| File | Purpose |
|---|---|
| `seeds.json` | v1: 32 Demagog claims, seeded stratified sample (seed 20261121; quotas false 12 / misleading 7 / mixed 4 / true 7 / unverifiable 2; round-robin over 2026 / 2025 / older). Frozen. |
| `variants.tsv` | v1: 170 hand-written user inputs, each labelled with its phenomenon. Written before any system output was seen. **Do not edit to make a variant pass** — add new lines instead. |
| `bench.jsonl` | v1: `seeds.json` × `variants.tsv` with expected verdicts (`build_dataset.py`). |
| `seeds_v2.json` | v2: 48 Demagog claims, same stratification, seed 20261122 (false 18 / misleading 11 / mixed 7 / true 11 / unverifiable 1). Seed numbers 101–148, so item ids never collide with v1. Frozen. |
| `sample_skips_v2.tsv` | v2: the 10 claims excluded by hand from the sample, with reasons. Input of the sampler. |
| `variants_v2.tsv` | v2: 262 hand-written inputs, same labels as v1; hard negatives carry a sub-type (`hardneg:person` …). Frozen. Dropped hard-negative candidates are listed at the end of the file. |
| `bench_v2.jsonl` | v2: `seeds_v2.json` × `variants_v2.tsv` (`build_dataset.py --set v2`); hard negatives have a `subtype` field. |
| `errata_v2.tsv` | v2: labelling problems found after the freeze (one entry: the four positives of seed 127 have a debatable expected verdict). |
| `build_dataset.py` | Builds either split (`--set v1|v2`); holds both samplers. |
| `run_bench.py` | Full pipeline (`service.run_check`) on every item + a per-stage trace of the gold document. `--set v1|v2`. |
| `compare.py` | Paired comparison of two runs: fixed / broken / new false verdicts, per phenomenon, sign test. `--set v1|v2`. |
| `lexical_bench.py` | Analyzer only (no neural model): BM25 rank of the gold document and the lexical gate, for 4 analyzers. v1 only. |
| `signal_bench.py` | Threshold-free comparison of "same claim?" signals: embedders and cross-encoder rerankers. v1 only. |
| `guard_check.py` | No model, about half a minute: the name/number agreement guard (`backend/prawdowid/agreement.py`) on every Polish fact-checked claim of the corpus — benign rewrites must not be read as disagreement, synthetic in-place swaps must be. |
| `results/*.json` | Outputs of the runs described in the report; `results/baseline_v2.json` is the v2 baseline. `eng0_baseline` … `eng4_all` belong to report section 11 (fragment fix, diacritics, agreement guard). |

Item groups and what counts as correct (identical in both splits):

- `pos` (v1 120, v2 188): 7 phenomena — `inflect`, `question`, `nodiac`, `colloq`, `para`, `short`, `typo`, four per
  claim by a fixed rotation. Expected = the verdict implied by Demagog's rating (false → `falszywe`,
  misleading/mixed → `wprowadzajace_w_blad`, true → `potwierdzone`).
- `unverifiable` (v1 8, v2 4): variants of claims Demagog rated "Nieweryfikowalne". Expected: no verdict.
- `neg` (v1 15, v2 22): the opposite of a false/true claim. Expected: the flipped verdict.
- `hardneg` (v1 27, v2 48): same topic and entities as a sampled claim, but a statement nobody checked. Expected: no
  verdict.

Outcome per item: `correct`, `abstain` (a verdict was expected, none given — a miss), `false_verdict` (a decisive
verdict that is wrong, or any decisive verdict where none was expected). **False verdicts are reported separately and
matter most.**

## How v2 was built

**Sample.** Same procedure as v1 (quota per rating, round-robin over 2026 / 2025 / 2014–2024, claims of 35–190
characters, no doctored-image ratings, no claims that mention a photo or video), other seed, 48 claims: periods
19 / 18 / 11. The corpus has only three "Nieweryfikowalne" claims and v1 uses two, so v2 has one; the two missing
slots went to the scarce ratings. Of the 1 294 Demagog records, 435 never enter either sample: 51 have no claim, 2 no
usable rating, 211 a claim outside the length window, 70 a doctored-image rating, 101 a claim that refers to a
photo/video. While walking the shuffled strata the sampler skipped 25 more records: 12 v1 seed documents, 3 flagged
by the lexical near-duplicate check (claim, or claim+title, sharing ≥ 35% of their 5-character stems or ≥ 60% of the
shorter one, and at least 3 stems; two against a v1 seed, one against an already picked v2 claim — the check is
deliberately loose and all three are same-subject claims rather than the same story), and 10 by hand
(`sample_skips_v2.tsv`): 7 not self-contained or not a statement, 1 the same story as a v1 seed that the lexical
check missed, 2 with a debatable label (a hypothetical example; a story that another fact-checker in the corpus rates
differently from Demagog). Each skipped claim is replaced by the next one of its stratum.

**Variants.** Written from the claim and the fact-check text only, in the order: all variants → corpus text search
for the hard negatives → commit (`a1a273c`) → one baseline run. Nothing was edited after the run.

**Hard negatives** (one per claim) are labelled by sub-type:

| Sub-type | n | What changes |
|---|---|---|
| `person` | 7 | a different person or group in the same role |
| `place` | 9 | a different place, institution or object in the same role |
| `number` | 6 | a different number, date or year (only where the fact-check does not cover the new value) |
| `predicate` | 13 | a different predicate about the same subject |
| `neighbour` | 7 | a true neighbouring fact on the same topic that no corpus document states |
| `othercov` | 6 | a statement close to *another* corpus document, which that document does not rate |

Each was checked by plain text search over all of `data/corpus/*.jsonl` (fact-checks and official sources). Anything
that another document rates, or simply states as a fact, was dropped — 11 named candidates plus a class of entity
swaps that the seed's own fact-check refutes anyway; the list is at the end of `variants_v2.tsv`.

**Known weaknesses of v2.**

- The author did not read `engine.py`, `service.py`, `index.py`, `claims.py`, the saved results or §3–8 of the report
  before the freeze, but did read `run_bench.py` in order to extend it, and its `trace()` / `patch_rules()` quote the
  matching thresholds (cosine 0.68 / 0.78 / 0.80 / 0.86 / 0.88, entailment 0.8, lexical overlap 0.4). No variant was
  written with them in mind and nothing was scored before the freeze, but v2 is not "threshold-blind" in the strict
  sense.
- One author, and the same kind of author as v1 (a language model writing as a native speaker). Real user phrasing is
  more varied.
- Hard negatives are 18% of v2 against 16% of v1, and they are harder by design (no swap that the fact-check itself
  refutes), so the overall accuracy of the two splits is not directly comparable; compare group by group.
- Ground truth is Demagog only. Other publishers in the corpus rate some of the same stories; one seed was dropped
  for that reason, the rest were not checked exhaustively.

## Run

```bash
# baseline on the tuning split, ~4.5 min on 8 CPU cores (1 s per item incl. trace), peak RSS ~3.3 GB
backend/.venv/bin/python eval/bench_polish/run_bench.py --name baseline

# a variant on v1, then the paired comparison
PYTHONPATH=/path/to/extra backend/.venv/bin/python eval/bench_polish/run_bench.py --name lemma_p6 --analyzer simplemma_p6
backend/.venv/bin/python eval/bench_polish/compare.py baseline lemma_p6

# confirmation on the held-out split (writes results/<name>_v2.json), then the paired comparison against baseline_v2
backend/.venv/bin/python eval/bench_polish/run_bench.py --name lemma_p6 --analyzer simplemma_p6 --set v2
backend/.venv/bin/python eval/bench_polish/compare.py baseline lemma_p6 --set v2

# rebuild the datasets from the frozen seeds and variants (deterministic; never needed unless a file was lost)
backend/.venv/bin/python eval/bench_polish/build_dataset.py            # bench.jsonl
backend/.venv/bin/python eval/bench_polish/build_dataset.py --set v2   # bench_v2.jsonl

# analyzer-only (no models, ~1 min) and matcher-signal comparison (~5 min), v1 only
PYTHONPATH=/path/to/extra backend/.venv/bin/python eval/bench_polish/lexical_bench.py
cd eval/bench_polish && ../../backend/.venv/bin/python signal_bench.py \
    --embed sdadas/mmlw-roberta-base --rerank sdadas/polish-reranker-base-ranknet
```

`/path/to/extra` is a directory with the optional analyzer packages, kept out of `backend/.venv`:
`uv pip install --python backend/.venv/bin/python --target /path/to/extra pystempel==2.0.0 simplemma==2.0.0`.

Useful switches of `run_bench.py`: `--set {v1,v2}`, `--analyzer {prefix6,pystempel,simplemma,simplemma_p6}`, `--no-alt`
(disable the `_alt_stems` hack), `--rule {no_lex,bidir_nli}` (what-if variants of `engine.same_claim`, patched in memory
— see `patch_rules`), `--no-trace` (faster), `--regress eval/cases.jsonl eval/cases_heldout.jsonl eval/cases_blind2.jsonl`
(run the existing sets, text cases only, through the same patched pipeline), `--skip-bench`.

To test a change made in the code itself, just run `--name <something>` on the changed tree and
`compare.py baseline <something>`; when it holds on v1, repeat both commands with `--set v2`. The baseline of each
split must come from the same corpus snapshot as the run it is compared with.

## Isolation

The harness never writes into `data/`. On first use it copies `data/index` and `data/corpus` into a work directory
(`/tmp/prawdowid_bench`, override with `PRAWDOWID_BENCH_WORK`) and points `PRAWDOWID_INDEX_DIR`, `PRAWDOWID_CORPUS_DIR`
and `PRAWDOWID_RUNTIME_DIR` there; scheduler and live search are off; `HF_HUB_OFFLINE=1`. Delete the work directory to
pick up a newer corpus (results then are not comparable with older runs — re-run the baseline too).

## Reading the numbers

### Baseline on both splits (same code, same corpus snapshot: 4 382 documents, 3 085 fact-checked claims)

`results/baseline.json` (v1) and `results/baseline_v2.json` (v2, one run, made after the freeze). Measured.

| | v1 n | v1 correct | v1 miss | v1 false verdict | v2 n | v2 correct | v2 miss | v2 false verdict |
|---|---|---|---|---|---|---|---|---|
| **All** | 170 | **141 (82.9%)** | 18 | **11 (6.5%)** | 262 | **207 (79.0%)** | 37 | **18 (6.9%)** |
| positives | 120 | 101 (84.2%) | 16 | 3 | 188 | 153 (81.4%) | 32 | 3 |
| unverifiable | 8 | 8 | – | 0 | 4 | 4 | – | 0 |
| negated | 15 | 13 (86.7%) | 2 | 0 | 22 | 16 (72.7%) | 5 | 1 |
| hard negatives | 27 | 19 | – | **8 (29.6%)** | 48 | 34 | – | **14 (29.2%)** |
| `inflect` | 19 | 19 | 0 | 0 | 28 | 27 | 1 | 0 |
| `question` | 19 | 17 | 1 | 1 | 28 | 26 | 0 | 2 |
| `nodiac` | 18 | 16 | 2 | 0 | 28 | 24 | 3 | 1 |
| `typo` | 18 | 17 | 1 | 0 | 27 | 23 | 4 | 0 |
| `short` | 18 | 16 | 1 | 1 | 27 | 23 | 4 | 0 |
| `colloq` | 18 | 15 | 3 | 0 | 27 | 20 | 7 | 0 |
| `para` | 18 | **9** | 8 | 1 | 27 | **14** | 13 | 0 |

Macro-F1 0.827 (v1) and 0.786 (v2). Gold claim found by the dense claim index at rank 1: 0.969 and 0.979.

v2 hard negatives by sub-type (false verdicts / n): `number` 3/6, `othercov` 3/6, `predicate` 4/13, `person` 2/7,
`place` 2/9, `neighbour` 0/7. Cells this small are anecdotes, not rates.

What the comparison shows:

- **v2 reproduces v1.** Overall accuracy is 3.9 points lower on v2 (95% interval for the difference, resampling
  claims: −12.4 to +4.3), positives 2.8 points lower (−12.1 to +6.2), and the false-verdict rate on hard negatives is
  the same (29.6% vs 29.2%). The picture of the report holds on unseen claims: inflection, question form, missing
  diacritics and typos mostly work, true paraphrases fail half the time (9/18, 14/27), and about three hard negatives
  in ten get a verdict they should not get.
- The three false verdicts on v2 positives come from two claims. Two are the debatable case recorded in
  `errata_v2.tsv` (an official police document in the corpus calls the claim false outright, Demagog says "missing
  context"); the third is a different fact-check deciding. Without that claim v2 has 1 false verdict on 184 positives.
- Five of the 14 hard-negative false verdicts on v2 are *confirmations* ("potwierdzone") of statements nobody
  checked — a different year or a different predicate, matched to a "true" fact-check (v1: 1 of 8; there the
  typical false verdict is "fałsz"). Hard negatives built on "true" claims fail most often in both splits (v1 3 of 7,
  v2 5 of 11).
- Two v2 claims lose all four positives (seed 121, whose corpus claim is a raw tweet, and seed 147, a three-number
  claim; why they fail was not analysed), so outcomes inside a claim are correlated: the 188 positives carry about
  as much information as ~110 independent items.
- First stage that stopped the gold document on the 41 missed or wrong positives and negations of v2: NLI
  contradiction veto 10, entailment below 0.8 at cosine 0.80–0.86 8, matched but a later rule or another document
  decided 7, kind gate 5, lexical
  gate 4, cosine below 0.78 3, cosine 0.78–0.80 2, low entailment at cosine 0.86–0.88 2. Read once for this table;
  these traces must not be used to tune (see above).

### What the two splits can and cannot detect

Variants of one claim succeed or fail together, so the unit is the claim: 32 in v1, 48 in v2, 80 together.
Always read `compare.py` (which items flipped, in which direction, new false verdicts), not the change in accuracy.

- **Sign test over claims** (a claim counts as better/worse if its number of correct items moved): a change is
  distinguishable from noise at p < 0.05 only from **6 claims better and none worse**, or 8 vs 1, 10 vs 2, 12 vs 3.
  This holds for any split size; a larger split only makes it easier to reach.
- **Size of a detectable net effect** (inferred, not measured on v2): on v1 the per-claim change in accuracy under the
  two saved rule what-ifs had a standard deviation of 18 and 25 points across claims. With that spread, the mean
  change needed for p < 0.05 is about 6–9 points on v1 alone, 5–7 on v2 alone and **4–5.5 points on the 80 claims
  together**; to find such a change four times out of five it has to be about **6–8 points** (roughly 25–35 of the
  432 items, net). Changes of 2–3 points — 10 items — are noise even on both splits.
- **False verdicts on hard negatives**: one item per claim, 75 in total, baseline 22 (29.3%, 95% interval 20–40%).
  A loosening of the matcher is visibly unsafe only if it adds at least 6 false verdicts and removes none (+8 points);
  to be caught four times out of five it must add about 8–9 (+11 points). The benchmark cannot show that a change is *safe* —
  only that it is not grossly unsafe on these 75 statements. On v2 alone (48) the interval is 18–43%.
- **Per-phenomenon and per-sub-type cells** (18–28 items per split, 6–13 per hard-negative sub-type) support only
  gross statements such as "paraphrases went from half to most". They cannot rank two variants.
- **Between splits**: a difference between v1 and v2 smaller than about 10 points is not evidence that a change
  over-fitted v1; look instead at whether the direction and the kind of flips repeat.

Latency depends on machine load; compare runs made back to back.
