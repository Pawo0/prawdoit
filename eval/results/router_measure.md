# Router measurement, 2026-11-21

Produced by `eval/measure_router.py` (repo data only, live search off, corpus of 4,382 documents / 3,085 fact-checked
claims). Raw output: `router_measure.json` (all sets) and `router_measure_tier2_corpus.json` (background check on the
two corpus sets). Rates are followed by a Wilson 95 % interval.

```
backend/.venv/bin/python eval/measure_router.py --tier2 --official 300 --verbatim 200 --loo 100
backend/.venv/bin/python eval/measure_router.py --tier2 --official 300 --verbatim 200 --loo 100 --sets "corpus/(official|rated-true)"
```

Conditions: 8-CPU laptop shared with other model runs and swapping at the time, in process (no HTTP). Latency is
therefore an upper bound for this machine, not a server benchmark. The bench and case sets were written from the
corpus, so they measure paraphrases of *known* claims; they say nothing about claims nobody has checked.

## Tier 1 (router): states per set

P = the input repeats a debunked claim; N = the input must not get a visible tag.

| set | kind | n | routed onwards (candidate + match) | visible tag (match) | hidden by conflict rule | none |
|---|---|---|---|---|---|---|
| bench/pos-debunked — 7 kinds of rewording of claims Demagog debunked | P | 92 | 92 = 100 % [96.0–100] | 71 = 77.2 % [67.6–84.6] | 0 | 0 |
| cases/false-or-misleading — team eval cases, incl. claims refuted only by official data | P | 67 | 67 = 100 % [94.6–100] | 37 = 55.2 % [43.4–66.5] | 0 | 0 |
| corpus/debunked-verbatim — debunked Demagog claims word for word (upper bound) | P | 200 | 200 = 100 % [98.1–100] | 198 = 99.0 % [96.4–99.7] | 0 | 0 |
| corpus/debunked-loo — the same with the claim's own document hidden | P | 100 | 100 = 100 % [96.3–100] | 8 = 8.0 % [4.1–15.0] | 0 | 0 |
| bench/hardneg — same topic and entities, a statement nobody checked | N | 27 | 27 = 100 % | **0 = 0 % [0–12.5]** | 0 | 0 |
| bench/neg — the opposite of a rated claim | N | 15 | 15 = 100 % | **0 = 0 % [0–20.4]** | 0 | 0 |
| bench/pos-true — rewordings of claims Demagog rated true | N | 28 | 28 = 100 % | **0 = 0 % [0–12.1]** | 0 | 0 |
| bench/unverifiable | N | 8 | 8 = 100 % | 0 = 0 % [0–32.4] | 0 | 0 |
| cases/other — expected confirmed / no evidence / opinion | N | 64 | 64 = 100 % | 0 = 0 % [0–5.7] | 0 | 0 |
| corpus/rated-true — every claim a fact-checker rated true, word for word | N | 127 | 127 = 100 % | **0 = 0 % [0–2.9]** | 1 | 0 |
| corpus/official-sentences — random sentences from MSZ, MON, KPRM news | N | 300 | 298 = 99.3 % [97.6–99.8] | **0 = 0 % [0–1.3]** | 0 | 2 |

- Paraphrased positives together (bench + cases): routed onwards 159/159 = 100 % [97.6–100]; visible tag at once
  108/159 = 67.9 % [60.3–74.7].
- Visible false tags on all N sets together: 0/569 = 0 % [0–0.7].
- Leave-one-out: only 8 % of debunked claims are still matched once their own fact-check is hidden — a visible tag
  depends on that exact claim being in the corpus; another publisher's entry rarely catches it.
- The conflict rule fired once: a claim Demagog rated true (wind-farm capacity, cosine 1.0) with a debunked twin at
  0.898. Without the rule it would have been tagged "rated false".
- **`candidate` selects almost nothing.** 99.3 % of ordinary official sentences are candidates, and 83 % of them
  (250/300) are in the near-miss band (cosine >= 0.74 to some debunked claim), so `priority` mostly orders by topical
  closeness. The state is high-recall as designed; it is a cost filter only, and "none" is rare (2/300).

## Change 1: NLI from cosine 0.80 instead of 0.74

| inputs | NLI pairs, old gate | new gate | saved | items whose risk / level / match / reason differ |
|---|---|---|---|---|
| all sets above except leave-one-out (928 items) | 1,021 | 657 | 364 = 35.7 % | 0 |
| rated-true + official sentences only (427 items) | 466 | 168 | 298 = 63.9 % | 0 |
| previous code (commit 84047c3) against the new code, conflict rule off (878 items, one-off script) | 971 | 607 | 364 = 37.5 % | 0 |

The saving depends on the content: about a third on inputs that are mostly close to debunked claims, about two thirds
on ordinary and true content.

## Latency per batch of 16 items (in process, loaded machine)

| inputs | old gate p50 / p95 | new gate p50 / p95 |
|---|---|---|
| all sets (52 batches) | 6.7 s / 10.4 s | 3.6 s / 8.4 s |
| rated-true + official sentences (25 batches) | 9.2 s / 14.6 s | 2.4 s / 6.4 s |

Both are far above the 1.5 s p95 budget in research/09 §3.5. NLI dominates (about 0.3 s per pair here). Over HTTP on
the same machine a 3-item batch (one match, two candidates) took 0.4 s.

## Tier 2 in the background (mode "auto", local corpus, no live search)

A badge = decisive false/misleading verdict with a cited, linked source — the extension's rule.

| set | kind | n | badge | of those: near-miss candidate (priority >= 0.6) | check p50 / p95 |
|---|---|---|---|---|---|
| bench/pos-debunked | P | 92 | 78 = 84.8 % [76.1–90.7] | 9 (the other 69 are tier-1 matches) | 0.74 s / 2.48 s |
| cases/false-or-misleading | P | 67 | 45 = 67.2 % [55.3–77.2] | 10 | 0.74 s / 2.41 s |
| bench/hardneg | N | 27 | **7 = 25.9 % [13.2–44.7]** | 7 | 0.87 s / 2.57 s |
| bench/neg | N | 15 | **5 = 33.3 % [15.2–58.3]** | 5 | 0.75 s / 1.64 s |
| bench/pos-true | N | 28 | **2 = 7.1 % [2.0–22.6]** | 2 | 1.14 s / 2.07 s |
| bench/unverifiable | N | 8 | 0 | 0 | 1.35 s / 1.53 s |
| cases/other | N | 64 | 0 = 0 % [0–5.7] | 0 | 0.47 s / 1.50 s |
| corpus/rated-true | N | 127 | **3 = 2.4 % [0.8–6.7]** | 3 | 0.80 s / 2.97 s |
| corpus/official-sentences | N | 300 | **11 = 3.7 % [2.1–6.4]** | 10 | 0.55 s / 1.79 s |

- Tier-2-relative recall: of the 138 bench/case items (and 14 corpus items) the full check rates false/misleading,
  tier 1 dropped none.
- What the background check adds over tier 1 on positives: at least 19 more marked items of 159 (108 -> 127 or more).
- What it costs: a wrong "sources contradict this" badge on 3.7 % of ordinary official sentences, 2.4 % of claims
  rated true, and 26–33 % of hard negatives and negations. Some of the bench/neg badges may be correct (the opposite
  of a claim rated true); the set is not split by that here. With three checks per page view, 3.7 % per sentence is
  roughly a 1-in-10 chance of a wrong badge on a page of ordinary official text.
- These are verdicts of the existing full pipeline (research/08 reports false verdicts on 8 of 27 hard negatives for
  the same engine), not something auto mode introduces. The difference is that the user did not ask.
- Because of this, background checks ship switched off in the extension (popup option). The router, the auto mode
  and its tests are complete; the default is one line in `extension/background.js` (`autoVerify`).
