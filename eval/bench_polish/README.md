# bench_polish — does a change to Polish-language handling make verification better or worse?

A small, re-runnable benchmark built from Demagog fact-checks (`data/corpus/demagog.jsonl` = ground truth).
Report with results and interpretation: `research/08_polish_language_benchmark.md`.

## What is in it

| File | Purpose |
|---|---|
| `seeds.json` | 32 Demagog claims, seeded stratified sample (seed 20261121; quotas false 12 / misleading 7 / mixed 4 / true 7 / unverifiable 2; round-robin over 2026 / 2025 / older). Frozen. |
| `variants.tsv` | 170 hand-written user inputs, each labelled with its phenomenon. Written before any system output was seen. **Do not edit to make a variant pass** — add new lines instead. |
| `bench.jsonl` | `seeds.json` × `variants.tsv` with expected verdicts (`build_dataset.py`). |
| `run_bench.py` | Full pipeline (`service.run_check`) on every item + a per-stage trace of the gold document. |
| `compare.py` | Paired comparison of two runs: fixed / broken / new false verdicts, per phenomenon, sign test. |
| `lexical_bench.py` | Analyzer only (no neural model): BM25 rank of the gold document and the lexical gate, for 4 analyzers. |
| `signal_bench.py` | Threshold-free comparison of "same claim?" signals: embedders and cross-encoder rerankers. |
| `results/*.json` | Outputs of the runs described in the report. |

Item groups and what counts as correct:

- `pos` (120): 7 phenomena — `inflect`, `question`, `nodiac`, `colloq`, `para`, `short`, `typo`. Expected = the verdict
  implied by Demagog's rating (false → `falszywe`, misleading/mixed → `wprowadzajace_w_blad`, true → `potwierdzone`).
- `unverifiable` (8): variants of claims Demagog rated "Nieweryfikowalne". Expected: no verdict.
- `neg` (15): the opposite of a false/true claim. Expected: the flipped verdict.
- `hardneg` (27): same topic and entities as a sampled claim, but a statement nobody checked (entity swap, other
  predicate, other number). Expected: no verdict.

Outcome per item: `correct`, `abstain` (a verdict was expected, none given — a miss), `false_verdict` (a decisive
verdict that is wrong, or any decisive verdict where none was expected). **False verdicts are reported separately and
matter most.**

## Run

```bash
# baseline, ~4.5 min on 8 CPU cores (1 s per item incl. trace), peak RSS ~3.3 GB
backend/.venv/bin/python eval/bench_polish/run_bench.py --name baseline

# a variant, then the paired comparison
PYTHONPATH=/path/to/extra backend/.venv/bin/python eval/bench_polish/run_bench.py --name lemma_p6 --analyzer simplemma_p6
backend/.venv/bin/python eval/bench_polish/compare.py baseline lemma_p6

# analyzer-only (no models, ~1 min) and matcher-signal comparison (~5 min)
PYTHONPATH=/path/to/extra backend/.venv/bin/python eval/bench_polish/lexical_bench.py
cd eval/bench_polish && ../../backend/.venv/bin/python signal_bench.py \
    --embed sdadas/mmlw-roberta-base --rerank sdadas/polish-reranker-base-ranknet
```

`/path/to/extra` is a directory with the optional analyzer packages, kept out of `backend/.venv`:
`uv pip install --python backend/.venv/bin/python --target /path/to/extra pystempel==2.0.0 simplemma==2.0.0`.

Useful switches of `run_bench.py`: `--analyzer {prefix6,pystempel,simplemma,simplemma_p6}`, `--no-alt` (disable the
`_alt_stems` hack), `--rule {no_lex,bidir_nli}` (what-if variants of `engine.same_claim`, patched in memory — see
`patch_rules`), `--no-trace` (faster), `--regress eval/cases.jsonl eval/cases_heldout.jsonl eval/cases_blind2.jsonl`
(run the existing sets, text cases only, through the same patched pipeline), `--skip-bench`.

To test a change made in the code itself, just run `--name <something>` on the changed tree and `compare.py baseline <something>`.

## Isolation

The harness never writes into `data/`. On first use it copies `data/index` and `data/corpus` into a work directory
(`/tmp/prawdowid_bench`, override with `PRAWDOWID_BENCH_WORK`) and points `PRAWDOWID_INDEX_DIR`, `PRAWDOWID_CORPUS_DIR`
and `PRAWDOWID_RUNTIME_DIR` there; scheduler and live search are off; `HF_HUB_OFFLINE=1`. Delete the work directory to
pick up a newer corpus (results then are not comparable with older runs — re-run the baseline too).

## Reading the numbers

170 items from 32 claims: variants of one claim are not independent, so treat the effective sample as closer to 32 than
170. A difference of 2–3 items is noise. Trust the paired output of `compare.py` (which items flipped, in which
direction) and the false-verdict list, not the change in accuracy. Latency depends on machine load; compare runs made
back to back.
