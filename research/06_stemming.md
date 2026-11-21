# 06 — Lexical search: no Polish stemmer, heuristics only

*Compiled 2026-11-21. Checked against `textutil.py`, `engine.py`, `websearch.py`, the PIRB paper, the `pystempel` repo, and the `sdadas/mmlw-retrieval-e5-small` model card.*

## What we do

There is no Polish tokenizer or stemmer. `tokens()` in `backend/prawdowid/textutil.py` is the analyzer for BM25, for claim–quote overlap, and for the “same subject” check on official cards:

- regex tokens (numbers, or a run of Polish letters; hyphenated words split);
- a fixed stopword list;
- diacritics stripped;
- the word cut to six characters (`szczepionki` / `szczepionek` → `szczep`).

Two other heuristics do not share those rules. `substr_stem()` in `websearch.py` strips a list of endings before gov.pl / WordPress search (`Wrocławiu` → `Wrocław`). `_alt_stems()` in `engine.py` rewrites `sz/ch`, `cz/c`, `rz/r` and compares four-character prefixes, only when deciding whether an official card is on-topic. It exists because the six-character cut misses `Włochy` / `Włoszech` and `Niemcy` / `Niemczech`. BM25 itself still indexes the raw prefixes, so `ludzie` ≠ `ludzi` and `rok` ≠ `roku`, while `ustawa` and `ustawić` both become `ustaw`.

Dense retrieval is separate: `sdadas/mmlw-retrieval-e5-small`, fused with BM25 by reciprocal rank fusion. Opinion and prediction detection is another regex layer and does not affect the index.

## What a real analyzer is

PIRB’s BM25 baseline (Anserini, Lucene Polish analyzer) lemmatizes with Morfologik, BSD. Stempel, the algorithmic stemmer in Lucene and Elasticsearch, is free to use; the Python port `pystempel` ships an Apache-2.0 table and a BSD-2 Polimorf table. On the author’s test the default table still splits 63% of a lemma’s forms; the Polimorf table brings that to 13%, at about 50k words/s after one load of a few seconds. The “proprietary” note in `05_oss_models_prior_art.md` refers to old commercial extra tables, not these. `simplemma` (MIT) is lighter and weaker on the same consonant alternations. spaCy or Morfeusz are the wrong weight for this CPU path.

## Is it worth changing?

`mmlw-retrieval-e5-small` scores **52.34 NDCG@10** on PIRB. In the PIRB paper the same training line goes from **52.25** dense-only to **54.25** fused with Morfologik BM25 — about two points, and that BM25 is lemmatized, not a six-character prefix. A prefix index leaves part of that gap, mostly on names and short inflected words, where the embedder is weakest. It will not move hits the embedder already ranks.

A Polish cross-encoder reranker is the larger step in that benchmark (124M Apache-2.0 rerankers land around 57–60) and costs seconds of CPU. A lemmatizer does not.

Worth doing, in order:

1. One dictionary stemmer (`pystempel` Polimorf, or Morfologik) inside `tokens()`, shared by BM25, quote overlap, the official-card gate, and live-search keywords. Rebuild BM25 postings; keep the embedding cache and digit tokens. Check `Włochy`/`Włoszech`, `Niemcy`/`Niemczech`, `Kraków`/`Krakowie`, `Rosji`/`Rosja`, `ludzie`/`ludzi`.
2. Leave the embedder and rank fusion alone while doing that.
3. For ranking quality beyond inflection, a reranker on the top 10–20, or a stronger Polish embedder, moves the score more than stemming does.
