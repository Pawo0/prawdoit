# 08 — Polish-language handling: a benchmark instead of opinions

*Measured 2026-11-21 on the working tree, 8 CPU cores, no GPU, machine shared with other jobs (load 5–9).
Harness, data and raw results: `eval/bench_polish/` (see its README for commands).*

## 1. Answers first

**Can we do better than the hand-written Polish hacks with proper tooling?** On this benchmark, no off-the-shelf
replacement improved verification. A stemmer/lemmatizer changed nothing; a bigger embedder and a reranker move a
threshold-free signal a little at a high CPU price; two rewrites of the same-claim rule traded missed verdicts for
false ones. The benchmark does show *where* the errors are — and it is not morphology.

1. **A dictionary stemmer or lemmatizer in `tokens()` changes nothing measurable.** On 128 positive variants the gold
   document's BM25 rank improved in 4–5 items and worsened in 3–5, for every analyzer tried (pystempel/Polimorf,
   simplemma, simplemma + 6-char prefix). In the full pipeline the best of them changed the outcome of **0 of 170 items**
   (0 fixed, 0 broken). The hypothesis of `research/06_stemming.md` is not supported. The 6-character prefix
   is crude but it is not what loses verdicts.
2. **Retrieval is not the bottleneck.** The right Demagog claim is ranked first by the current embedder for 96.9% of
   variants (top-5: 98.4%), including typos, missing diacritics and questions. Every one of the 16 missed verdicts had
   the right document in hand and lost it in a later stage.
3. **The weak component is the same-claim decision in `engine.same_claim`** (cosine thresholds + lexical-overlap
   gate). It fails in both directions:
   - it gives **false verdicts on 8 of 27 hard negatives (30%)** — five of them because `cos >= 0.88` alone is treated
     as "same claim" although NLI entailment was ≤ 0.07, a sixth through another Demagog claim at cosine 0.884. The
     embedder cannot tell
     *Tarczyński vs Tusk* from *Tarczyński vs Trzaskowski*, or *port Szczecin* from *port Gdańsk* (cosine 0.93–0.96);
   - it **abstains on 16 of 120 true matches**, 9 of them because of the lexical gate (`lex >= 0.4`) or the
     0.78–0.80 cosine dead zone, although NLI entailment was 0.86–0.99. These are the README's "ranny / postrzelony"
     paraphrases. No stemmer can fix them: the words are different lexemes.
4. **A stronger embedder or a cross-encoder reranker helps separation only moderately** and costs a lot of CPU
   (table in §6). Neither was run inside the pipeline.
5. **The crude gates exist for a reason: the NLI model over-entails.** Removing the lexical gate and closing the dead
   zone recovered 8 paraphrases but produced 7 new false verdicts (false verdicts 11 → 18); replacing cosine-only
   acceptance with bidirectional NLI removed 6 of the 8 hard-negative false verdicts but broke 23 other items
   (11 → 14 false verdicts, 141 → 134 correct, and 5 regressions with 2 new false verdicts on the existing sets).
   mDeBERTa-XNLI gives entailment ≥ 0.8 to topical neighbours ("biolaboratoria w Ukrainie" ⇒ "Gardasil zawiera
   substancję stosowaną w wojnie biologicznej") and < 0.2 to some typo variants of the very same sentence. So neither
   cosine nor this NLI model is a reliable equivalence test on its own, and the present rule set is a local optimum.
6. A side finding unrelated to Polish: **the verbatim-quote gate (V2) silently discards correct documents** when
   `_best_fragment` joins two sentences that are not adjacent (it filters out sentences ≤ 15 characters first).
   2 of the 16 missed verdicts; 17.5% of fact-check documents contain at least one such window.

## 2. Benchmark design

Ground truth is Demagog (`data/corpus/demagog.jsonl`, 1 294 fact-checks, 1 243 with an explicit claim).

- **Sample**: 32 claims, seed 20261121, stratified by rating (false 12, misleading 7, mixed 4, true 7, unverifiable 2
  — true/mixed/unverifiable deliberately over-sampled, they are 5% / 4% / 0.2% of the corpus) and round-robin over
  2026 / 2025 / 2014–2024. Claims describing a doctored photo or video were excluded (the "claim" is a caption).
  Frozen in `seeds.json`.
- **Variants**: 170 inputs written by hand, one phenomenon each, types assigned by a fixed rotation (not chosen per
  claim):

  | Group | n | Types | Expected |
  |---|---|---|---|
  | positives | 120 | 4 of the 7 types per claim: `inflect`, `question`, `nodiac`, `colloq`, `para`, `short`, `typo` (18–19 items per type, counting the next row) | verdict implied by the rating |
  | unverifiable | 8 | same types, for the 2 "Nieweryfikowalne" claims | no verdict |
  | negated | 15 | `neg`: opposite of a false/true claim | flipped verdict |
  | hard negatives | 27 | `hardneg`: same topic and entities, a statement nobody checked (entity swap, other predicate, other number) | no verdict |

- **Scoring**: `correct`, `abstain` (verdict expected, none given), `false_verdict` (wrong decisive verdict, or any
  decisive verdict where none is expected). False verdicts are counted separately everywhere.
- **Retrieval metrics** (128 positives + unverifiable): rank of the gold document in the claim index (dense, BM25,
  the engine's `match_claims`) and in the passage index (BM25, dense, hybrid) → R@1, R@5, MRR.
- **Per-stage trace**: for every item the harness replays the engine's steps for the gold document (kind gate → claim
  candidates → cosine floors → NLI both directions → `same_claim`) and records the first stage that stops it.
- **Variants are monkeypatched in-process**; the index cache, corpus snapshot and SQLite live in a scratch work
  directory. No file outside `eval/bench_polish/` and this report was created or changed.

**Statistical power.** 170 items come from 32 claims, and variants of one claim succeed or fail together (e.g. both
false verdicts on positives come from one claim). Treat the effective sample as nearer 32 than 170. A 95% interval for
82.9% accuracy is roughly ±6 points even if items were independent, so differences of 2–3 items between variants are
noise. Conclusions below rest on paired flips (which item changed, in which direction, and why), not on deltas.

## 3. Baseline

`run_bench.py --name baseline` → `results/baseline.json`. Corpus snapshot: 4 382 documents, 21 494 passages,
3 085 fact-checked claims.

| | n | correct | abstained (miss) | false verdict |
|---|---|---|---|---|
| **All** | 170 | **141 (82.9%)** | 18 | **11 (6.5%)** |
| positives | 120 | 101 | 16 | 3 |
| unverifiable | 8 | 8 | – | 0 |
| negated | 15 | 13 | 2 | 0 |
| hard negatives | 27 | 19 | – | **8 (30%)** |

Macro-F1 over the four verdict classes: 0.827.

Per phenomenon (positives + unverifiable):

| Type | n | correct | false verdict | gold claim dense R@1 | gold claim BM25 R@1 | median cosine to gold claim | passes lexical gate |
|---|---|---|---|---|---|---|---|
| inflect | 19 | 19 | 0 | 1.00 | 1.00 | 0.975 | 19 |
| question | 19 | 17 | 1 | 1.00 | 1.00 | 0.975 | 19 |
| nodiac | 18 | 16 | 0 | 1.00 | 1.00 | 0.957 | 18 |
| typo | 18 | 17 | 0 | 1.00 | 1.00 | 0.948 | 18 |
| short | 18 | 16 | 1 | 0.94 | 1.00 | 0.961 | 18 |
| colloq | 18 | 15 | 0 | 1.00 | 0.89 | 0.904 | 11 |
| **para** | 18 | **9** | 1 | 0.83 | **0.28** | 0.861 | **1** |

Inflection, question form, missing diacritics and typos are handled: 69 of 74 correct, and the 5 misses have other
causes (below). The loss is concentrated in true paraphrases and, to a lesser degree, colloquial rewording.

Retrieval, all 128: claim index dense R@1 0.969 / R@5 0.984 / MRR 0.978; claim BM25 R@1 0.883; passage index hybrid
R@1 0.945 / R@5 0.969 (BM25 alone 0.922, dense alone 0.922 — fusion helps a little).

## 4. Where the baseline fails

**Missed verdicts and wrong verdicts on positives and negations (21 items), by the first stage that stopped the gold
document:**

| Stage | Items | What happened |
|---|---|---|
| Lexical gate `lex >= 0.4` in `same_claim` | 5 | cosine 0.83–0.86, NLI entailment 0.86–0.97, but < 40% of the claim's 6-char stems appear in the user text. All paraphrase/colloquial. |
| Cosine dead zone 0.78–0.80 | 4 | NLI is computed from 0.78 but no rule accepts below 0.80. Entailment was 0.92–0.99 in all four. |
| NLI entailment < 0.8 at cosine 0.80–0.86 | 3 | one typo variant (entailment 0.18 — NLI is fragile to typos), two paraphrases that drop part of the claim. |
| NLI contradiction veto | 5 | 2 negations detected in one direction only (0.81/0.96 vs 0.59/0.77; rule needs both ≥ 0.80); 1 colloquial variant; 2 variants of a numeric claim where NLI invents a contradiction (0.59, 0.92) — the gold document is vetoed and another fact-check then decides → **2 false verdicts**. |
| Quote gate V2 | 2 | `same_claim` = True, but the chosen fragment is not verbatim (non-adjacent sentences joined) and the document is dropped. |
| Rule R4 "archival" | 1 | matched correctly as *Prawda*, downgraded to *wprowadza w błąd* because my paraphrase said "dziś" and the fact-check is older than 365 days. Counted as a false verdict; arguably intended behaviour. |
| Kind gate R1 (regex) | 1 | `nodiac` input: "zostanie zwolniony … wroci" → *prognoza*, because the past-tense and factual-cue regexes need diacritics ("dopuscil", "wroci" do not match). |
| Retrieval miss / cosine floor | **0** | — |

**False verdicts on hard negatives (8 of 27):**

| Route | Items | Example |
|---|---|---|
| `cos >= 0.88` accepted without NLI support (5 traced: entailment 0.00–0.07; the 6th matched a different Demagog claim at cosine 0.884, route not traced) | 6 | "Dominik Tarczyński skonfrontował się z **Rafałem Trzaskowskim** w debacie na żywo" → *fałsz* (cosine 0.926 to the Tusk claim; NLI entailment 0.000, neutral 0.994). Also Ukraine↔Poland role swap (0.963), port Gdańsk for Szczecin-Świnoujście (0.957), "rząd wypłacił 250 tys. zł" vs "rząd zamordował 250 tys." (0.899). |
| Negation rule (`cos >= 0.85` and contradiction ≥ 0.8 both ways) flips a verdict | 2 | "W 2023 r. w Polsce urodziło się najwięcej dzieci w UE" → *fałsz* via the claim about the largest population decline. One of the two (monthly vs hourly ticket) is debatable as a label. |

Reading: the errors are in **matching**, not in retrieval, and not in morphology. The embedder's cosine is being used
as an equivalence test, which it is not: it measures topical closeness, so it is too strict for paraphrases
(median 0.86) and too lenient for entity swaps (0.90–0.96).

## 5. Variants

### 5.1 Analyzer: real stemmer / lemmatizer instead of the 6-char prefix

`lexical_bench.py` (no neural model; both BM25 indexes rebuilt per analyzer) → `results/lexical.json`.

| Analyzer | claim BM25 R@1 / R@5 / MRR | passage BM25 R@1 / R@5 | rank better / worse vs prefix | lexical gate passed (of 128) | `nodiac` mean overlap | `typo` mean overlap |
|---|---|---|---|---|---|---|
| **prefix6 (current)** | 0.883 / 0.898 / 0.894 | 0.922 / 0.945 | – | 104 | **0.97** | **0.80** |
| pystempel 2.0.0, Polimorf table | 0.875 / 0.914 / 0.895 | 0.914 / 0.953 | 5 / 5 | 103 | 0.73 | 0.70 |
| simplemma 2.0.0 | 0.875 / 0.922 / 0.894 | 0.914 / 0.953 | 4 / 4 | 105 | 0.75 | 0.70 |
| simplemma, then 6-char prefix | 0.898 / 0.930 / 0.913 | 0.930 / 0.953 | 4 / 3 | 107 | 0.85 | 0.79 |

- No analyzer moves BM25 on paraphrases (R@1 0.28 → 0.28–0.33): different lexemes stay different after lemmatisation.
- Dictionary analyzers are **worse on text without diacritics and with typos** — exactly the inputs citizens type.
  "zakonczenie", "polakow", "rekalmy" are not in the dictionary and are not normalised; the prefix cut is indifferent
  to that.
- pystempel mangles lower-cased proper names (`Krakowie → krak`, `Kraków → kraka`, `Włoszech → włonek`,
  `Niemczech → niemczech`), so it would not even replace `_alt_stems`. simplemma gets them right
  (`Włoszech → Włochy`, `Niemczech → Niemcy`, `Węgrzech → Węgry`, `ludzi → człowiek`).

Full pipeline, best analyzer (`simplemma_p6`), `compare.py baseline lemma_simplemma_p6`:
**0 fixed, 0 broken, 0 new false verdicts** — all 170 outcomes identical (141 correct, 18 abstained, 11 false
verdicts). The analyzer reaches the verdict only through BM25 candidates that the embedder then re-scores, and through
the lexical gate, where lemmatisation moves 3 items across the 0.4 line and none of them changes a decision.

**Verdict: null result.** Do not replace the analyzer for quality reasons.

### 5.2 Stronger embedder for claim matching

`signal_bench.py` → `results/signals_run1.log`. Threshold-free on purpose: the engine's seven cosine thresholds are
calibrated for the current model, so a drop-in swap would measure thresholds, not models. Ranking = rank of the gold
claim among 3 085; separation = score of the gold claim for the 128 positives against the best score any claim gets
for each of the 27 hard negatives (AUC; share of positives above the highest hard-negative score = recall at zero
false accepts, with an oracle threshold — an upper bound, equally optimistic for every row).

| Signal | R@1 | R@5 | MRR | AUC pos vs hard-neg | recall @ 0 false accepts | @ 1 false accept |
|---|---|---|---|---|---|---|
| cosine, `sdadas/mmlw-retrieval-e5-small` (current) | 0.969 | 0.984 | 0.978 | 0.812 | 38% | 41% |
| cosine, `sdadas/mmlw-roberta-base` (Apache-2.0, 124M, STS-style) | 0.977 | 1.000 | 0.984 | 0.891 | 56% | 63% |
| BM25 score (prefix6), for reference | 0.883 | 0.898 | 0.894 | 0.672 | 30% | 45% |

The base-size model ranks one more item first (125 vs 124 of 128) and separates hard negatives better, but still
puts **no paraphrase and 2 of 18 colloquial variants** above the zero-false-accept line. It is the same kind of signal
with the same blind spot. Not measured in the full pipeline (needs re-calibrated thresholds and a re-embedded passage
index: 5.8 passages/s here → about 60 min for 21 494 passages).

### 5.3 Cross-encoder reranker on the top-k

`sdadas/polish-reranker-base-ranknet` (Apache-2.0, 124M; PIRB rerankers NDCG@10 60.32 per its model card) over the
union of dense top-10 and BM25 top-10 claims (17.4 pairs per query on average; gold present for 127/128)
→ `results/signals_run2.log`, `results/signals.json`.

| Signal | R@1 | R@5 | MRR | AUC | recall @ 0 FA | @ 1 FA | latency |
|---|---|---|---|---|---|---|---|
| reranker score | 0.977 | 0.992 | 0.981 | 0.889 | 64% | 66% | **1 852 ms p50 / 3 580 ms p95** per query; 653 ms for 8 pairs |

Ranking gain: one item (125 vs 124 first). There is nothing left to rerank — R@1 is already 97%. As a match signal it
is better than cosine (5 of 18 colloquial and 3 of 18 paraphrases above the line) but its scores saturate
(median 0.999 for positives, 0.983 for the best wrong claim): it was trained for query–document relevance, and a
same-topic claim *is* relevant. It would double to triple per-query latency. **Not worth adding.**

### 5.4 NLI as the matcher (the model that is already loaded)

From the baseline traces (`results/baseline.json`), same pairs for every row: user text vs gold claim for positives,
user text vs the "trap" claim (the sampled claim the hard negative was derived from) for hard negatives. The trap was
the top-1 candidate for 20 of 27; for the other 7 the NLI scores of the actual top-1 claim are not in the trace, so the
hard-negative column is a lower bound and the pipeline runs below are the real test.

| Signal (current mDeBERTa-v3 NLI, or cosine) | AUC pos vs hard-neg | recall @ 0 false accepts | positives ≥ 0.8 | hard negatives ≥ 0.8 |
|---|---|---|---|---|
| cosine (current embedder) | 0.831 | 38% | 123 / 128 | 26 / 27 |
| entailment, user text ⇒ checked claim (what the engine uses) | 0.896 | 13% | 76 / 128 | 1 / 27 |
| entailment, checked claim ⇒ user text (computed today only for negation) | 0.964 | 70% | 86 / 128 | 0 / 27 |
| **max of both directions** | **0.964** | 27% | **105 / 128** | **1 / 27** |
| min of both directions | 0.947 | 83% | 57 / 128 | 0 / 27 |

One-directional entailment is too strict as the only test (a shortened claim does not entail the full one: `short`
variants pass in 6 of 18, typos in 8 of 18), which is why the engine leans on cosine. Taking the better of the two
directions accepts 105 of 128 true matches and 1 of 27 hard negatives; the current rule accepts 111 and 5, plus 2
wrong flips. Negation: contradiction ≥ 0.8 in the forward direction for 15 of 15 negated variants, in both directions
for 13.

Two what-if rule sets were run through the full pipeline (`--rule`, engine source patched in memory). **Both were
designed after seeing the baseline failures, so they are diagnostics, not validated improvements**:

| Run | correct | abstained | false verdicts | fixed / broken vs baseline | hard-neg FV | latency p50 / p95 |
|---|---|---|---|---|---|---|
| baseline | 141 | 18 | 11 | – | 8 | 727 / 2 137 ms |
| `--rule no_lex`: drop the lexical gate, ask NLI from cosine 0.74 instead of 0.78–0.80 | 143 | 9 | **18** | 8 / 6 | 8 | 794 / 1 876 ms |
| `--rule bidir_nli`: no cosine-only acceptance, no lexical gate; same claim ⇔ no contradiction, cosine ≥ 0.74, entailment ≥ 0.8 in either direction | 134 | 22 | **14** | 16 / 23 (sign test p = 0.34) | **2** | 1 190 / 3 417 ms |

- `no_lex` does what the trace predicted for the gold documents: paraphrases 9 → 15 of 18 correct. But the looser floor
  also admits *other* fact-checks: the biolab claim is "refuted" through a Gardasil fact-check (2 items), all four
  variants of the unverifiable Danish wind-power claim get *wprowadza w błąd* from a neighbouring fact-check about
  wind farms and prices, and one more correct match is downgraded by the archival rule. Seven new false verdicts, none
  removed.
- `bidir_nli` removes the entity-swap false verdicts as intended (hard negatives 8 → 2; the 2 left are the
  negation-rule flips) and fixes 10 paraphrase misses, but 15 near-verbatim positives that were accepted on cosine
  alone now get no verdict (neither direction reaches 0.8 — typos, shortened forms, questions), and 9 new false
  verdicts appear through neighbouring claims (5 of them on the 8 "unverifiable" variants).
- The trace-based table above was therefore **too optimistic**: it only looked at the gold/trap claim, while the
  damage comes from the other 7 candidates per query.

**Verdict: both what-ifs are worse than the baseline once false verdicts are weighed.** They confirm the diagnosis
(the misses and the false verdicts are both decided in `same_claim`) and show that the fix is not a threshold edit.

### 5.5 Which hacks earn their keep

| Hack | Evidence | Verdict |
|---|---|---|
| 6-char prefix stem in `tokens()` | §5.1: no analyzer beats it; it is the most robust to missing diacritics and typos | **Keep.** |
| Diacritic stripping in `tokens()` | `nodiac` BM25 R@1 1.00; dense cosine median 0.957 vs 0.975 with diacritics | **Keep** (the lexical side depends on it; the embedder copes on its own). |
| `_alt_stems()` consonant alternations | Not exercised by Demagog matching (official cards only). simplemma resolves `Włoszech/Niemczech/Węgrzech` correctly, pystempel does not. An ablation run without the hack was **not done** (cut for time; `--no-alt` exists in the harness). | Keep while the prefix analyzer stays. |
| `substr_stem()` in `websearch.py` | Live search is off in the benchmark | **Not measured.** |
| Question → statement rewriting (`strip_preamble`, `question_to_claim`) | `hack_ablation.py`: raw question vs rewritten — median cosine 0.968 vs 0.975, same rank (19/19 first) and same threshold decisions; helped in 13, hurt in 0 | Not needed by the embedder; keep for NLI, where the hypothesis must be a statement (effect on NLI not measured). |
| Opinion / prediction regexes (`claim_kind`) | Fired on 1 of 170 inputs, wrongly (`nodiac` text read as a prediction) | Keep, but match on diacritic-stripped text; the benchmark has no opinion inputs, so its recall is **not measured** here. |
| Lexical gate `lex >= 0.4` in `same_claim` | Blocks 5 true paraphrases with entailment 0.86–0.97 — but removing it (with the dead zone) added 7 false verdicts (§5.4) | **Keep for now.** It compensates for NLI over-entailment; it can go only together with a better equivalence signal. |
| `cos >= 0.88` ⇒ same claim | Causes 6 of the 8 false verdicts on hard negatives — but 43 of 104 accepted true matches rely on it (forward entailment < 0.8), and replacing it by NLI lost 15 of them (§5.4) | **Keep for now**; it is the known source of entity-swap false verdicts. |

## 6. Speed and footprint

Same machine, under load; pipeline latency is end-to-end `run_check` in process.

| Variant | Load time | Per query | Added RAM | Install / disk | Index rebuild |
|---|---|---|---|---|---|
| Baseline pipeline | index 4–5 s with warm embedding cache (13.8 s when 41 new passages had to be embedded), models 3–9 s | **p50 727 ms, p95 2 137 ms** (NLI 638 / 2 047 ms; retrieval 54 / 98 ms) | peak RSS 3.3 GB | – | – |
| pystempel 2.0.0 | 3.9–9.1 s | tokenising a query: 0.10 ms (0.06 ms today) | +164–256 MB | 2.7 MB + sortedcontainers, tqdm | BM25 rebuild 8.5 s (4.8 s today) |
| simplemma 2.0.0 | 3.0–6.1 s | 0.06–0.08 ms | +343–410 MB | 19 MB, no dependencies | 5.3–6.6 s |
| `mmlw-roberta-base` embedder | 0.2 s (warm disk cache) | 47 ms p50 / 69 ms p95 per query embedding | +267 MB | 481 MB | claim index 176 s; passage index ≈ 60 min (extrapolated from 200 passages) |
| `polish-reranker-base-ranknet` | 0.1 s (warm) | **+1 852 ms p50 / +3 580 ms p95** (17 pairs); +653 ms (8 pairs) | +125 MB (measured as RSS growth after the embedder was freed — a lower bound; weights are 481 MB) | 481 MB | none |
| `--rule bidir_nli` (reverse NLI pass for every claim candidate) | – | p50 1 190 ms, p95 3 417 ms (NLI 1 092 / 3 349 ms) — +64% | none | none | none |

## 7. Regression check on the existing sets

Text cases of `eval/cases.jsonl`, `cases_heldout.jsonl`, `cases_blind2.jsonl` through the same harness, same corpus
snapshot (URL cases skipped — no network). These sets were used to tune the current rules, so they can only show
regressions.

| Set (text cases) | Baseline | `simplemma_p6` analyzer | `--rule bidir_nli` | `--rule no_lex` |
|---|---|---|---|---|
| `cases.jsonl` (35) | 34 ok, 0 false verdicts | 34 ok, 0 — identical per case | 33 ok, 0 FV (T1 lost; B1 changed within accepted set) | 34 ok, 0 FV — identical |
| `cases_heldout.jsonl` (56) | 49 ok, 2 false verdicts (H52, H53) | 49 ok, 2 — identical per case | **45 ok, 4 FV** (H04, H07, H11 lost; H13, H14 now *fałsz* instead of *wprowadza w błąd*; H29 gained) | 49 ok, **3 FV** (H29 gained; H13 now *fałsz* instead of *wprowadza w błąd*) |
| `cases_blind2.jsonl` (49) | 41 ok, 0 false verdicts | 41 ok, 0 — identical per case | 41 ok, 0 FV (B2-03 lost, B2-11 gained) | 42 ok, 0 FV (B2-11 gained) |

The lemmatising analyzer changes no outcome on any of the 140 cases either. All baseline failures but two are
"no evidence instead of a verdict", as the README says. `no_lex` looks harmless here (+2 cases, +1 false verdict) —
these sets contain few neighbouring-claim traps, which is why the hard negatives and "unverifiable" variants of the
new benchmark are needed to see its cost. `bidir_nli` regresses on the held-out set (−4 cases, +2 false verdicts).

## 8. Recommendation

What to change, in order:

1. **Fix `_best_fragment`** so that it only joins adjacent sentences (pair first, filter short ones after). Small and
   safe; recovers documents the quote gate throws away today (2 of the 16 missed verdicts here; 17.5% of fact-check
   documents are exposed). Expected gain on this benchmark: +2 correct, no new risk. *Inferred from the trace — the
   fix itself was not run.*
2. **Make the regex layer diacritic-insensitive** (`claim_kind`: apply the past-tense and factual-cue patterns to
   diacritic-stripped text). One wrong "prediction" in 18 `nodiac` inputs; cheap. *Not run.*
3. **Treat the same-claim decision as the component to replace, and do it with data, not with another threshold.**
   Both failure classes live there (9 + 3 + 5 misses, 8 + 2 false verdicts), and §5.4 shows that neither cosine nor
   the current NLI model can carry it alone. The next things worth *measuring* with this harness, none of them done
   here: (a) another NLI model — the over-entailment on topical neighbours and the fragility to typos are properties
   of this checkpoint; (b) a small calibrated classifier over the signals already computed (cosine, entailment and
   contradiction in both directions, number/entity agreement), fitted on a larger seed sample split by claim;
   (c) an explicit named-entity / number agreement guard on the cosine-only route, which is what the six entity-swap
   false verdicts have in common. Until one of these beats the baseline on false verdicts, leave `same_claim` alone.
4. **Grow the benchmark before tuning on it**: 32 claims cannot be both a tuning set and a test set. Add seeds
   (`build_dataset.py` is seeded; `variants.tsv` is append-only) and split by claim.

What I would **not** change: the analyzer (prefix stem + diacritic stripping), the embedder, rank fusion; and I would
not add a reranker. None of them is where verdicts are lost; a dictionary analyzer is measurably worse on text
without diacritics; the embedder swap costs a full re-embed (about an hour of CPU here) plus re-calibration of seven
thresholds; the reranker doubles to triples latency for one item of ranking gain.

**Hacks that can be deleted now: none.** Every hack tested either does measurable work (prefix stem, diacritic
stripping, lexical gate, cosine thresholds) or is harmless and cheap (question rewriting). Hacks that must stay:
prefix stemming, diacritic stripping, `_alt_stems` (compensates the prefix stem on official cards; not ablated),
question rewriting (for NLI), the opinion/prediction regexes, the lexical gate and the cosine thresholds in
`same_claim`, the numeric rule. The lexical gate and the cosine-only acceptance are the two to retire *when* step 3
delivers a better equivalence signal.

## 9. Measured, inferred, not measured

**Measured here**: everything in §3, §4, §5.1, the three rows of §5.2/5.3, both pipeline what-ifs of §5.4, §6, §7;
the V2 mechanism (91 of
12 069 candidate windows in 400 sampled fact-check documents are not verbatim; 70 documents affected).

**Taken from model cards / PyPI, not verified**: PIRB NDCG@10 figures (56.38 for `mmlw-retrieval-roberta-base`, 60.32
for the reranker), licences (Apache-2.0 for the three sdadas models used; pystempel code Apache-style, Polimorf table
BSD-2; simplemma MIT), package sizes.

**Not measured**: `sdadas/mmlw-retrieval-roberta-base` (downloaded, run cut for time); any alternative NLI model; an
embedder swap inside the full pipeline; Morfeusz2 (1.99.15 on PyPI, 9–16 MB wheels, own licence) and spaCy `pl`
(needs a separate model package) — not installed, judged too heavy for the gain §5.1 leaves available;
`substr_stem` / live search; official-card paths (numeric rule, `_alt_stems`) beyond the regression sets; recall of the
opinion/prediction regexes; latency on an idle machine.

**Validity caveats**

- I wrote the variants, and I had read `engine.py` (including its thresholds) before writing them. They were written
  before any output was seen and were not edited afterwards, but hard negatives built by swapping an entity are the
  kind of input I expected to be difficult. The 30% false-verdict rate describes *this* adversarial set, not traffic.
- 32 claims. One claim (Biejat, three numbers) produces both false verdicts on positives; one claim's quote-gate
  problem produces two misses. Per-phenomenon cells have 18–19 items.
- Positives count as correct only with Demagog's verdict. Other fact-checkers in the corpus may legitimately rate a
  neighbouring claim differently; I checked the two cases where another publisher's document decided (it was a
  different claim both times).
- Two hard negatives are debatable as labels (the opposite-sounding ticket claim; the births-vs-population claim): the
  system's *fałsz* is defensible on common sense, though no fact-check establishes it.
- The oracle thresholds in §5.2–5.4 are chosen on the benchmark itself.
- The what-if rules of §5.4 were designed after the diagnosis, on the same items — and still lost to the baseline,
  so the negative result is conservative. The baseline rules, in turn, were never tuned on this set.
- Three of the new false verdicts under the what-if rules were checked by hand (Gardasil, Małopolska giełda rolna,
  wind farms and prices): different claims, so they are real mismatches, not rating disagreements between publishers.

## 10. Reproduce

```bash
uv pip install --python backend/.venv/bin/python --target /tmp/pl_extra pystempel==2.0.0 simplemma==2.0.0
backend/.venv/bin/python eval/bench_polish/run_bench.py --name baseline                      # ~4.5 min
PYTHONPATH=/tmp/pl_extra backend/.venv/bin/python eval/bench_polish/lexical_bench.py         # ~1 min, no models
PYTHONPATH=/tmp/pl_extra backend/.venv/bin/python eval/bench_polish/run_bench.py --name lemma_simplemma_p6 \
    --analyzer simplemma_p6 --no-trace --regress eval/cases.jsonl eval/cases_heldout.jsonl eval/cases_blind2.jsonl
backend/.venv/bin/python eval/bench_polish/compare.py baseline lemma_simplemma_p6
```

Extra packages used (installed outside `backend/.venv`): pystempel 2.0.0, simplemma 2.0.0, sortedcontainers 2.4.0,
tqdm 4.70.1. Models: `sdadas/mmlw-roberta-base`, `sdadas/polish-reranker-base-ranknet` (Hugging Face cache).
