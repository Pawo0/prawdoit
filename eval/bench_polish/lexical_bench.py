"""Analyzer-only benchmark (no neural model is loaded): what does swapping tokens() do to the lexical side?

    PYTHONPATH=<dir with simplemma/pystempel> backend/.venv/bin/python eval/bench_polish/lexical_bench.py

For each analyzer: rebuild both BM25 indexes (claims, passages), then for the 128 positive variants report the rank of
the gold Demagog document by BM25 alone (R@1/R@5/MRR, per phenomenon) and how many variants pass the engine's lexical
gate `lex >= 0.4` (share of the fact-checked claim's tokens present in the user text). Results: results/lexical.json
"""
from __future__ import annotations

import json
import statistics
import time

from run_bench import HERE, doc_rank, mrr, patch_analyzer, recall_at, rss_mb, setup_env


def main() -> None:
    setup_env()
    from prawdowid import engine
    from prawdowid.claims import extract_claims
    from prawdowid.index import BM25, INDEX
    from prawdowid.security import neutralize
    from prawdowid.textutil import normalize_ws

    INDEX.load()  # embeddings come from the cache; the embedder is not instantiated
    gold_idx = {d.id: i for i, d in enumerate(INDEX.docs)}
    items = [json.loads(l) for l in (HERE / "bench.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pos = [it for it in items if it["group"] in ("pos", "unverifiable")]
    queries = {it["id"]: " ".join(c.query for c in extract_claims(neutralize(normalize_ws(it["text"])), max_claims=3)) or it["text"]
               for it in items}
    out = {}
    for kind in ("prefix6", "pystempel", "simplemma", "simplemma_p6"):
        r0, t0 = rss_mb(), time.perf_counter()
        if kind != "prefix6":
            patch_analyzer(kind)
        load_s = time.perf_counter() - t0
        tok = engine.tokens
        t0 = time.perf_counter()
        chunk_toks = [tok(c.text) for c in INDEX.chunks]
        tok_s = time.perf_counter() - t0
        n_tok = sum(len(t) for t in chunk_toks)
        t0 = time.perf_counter()
        bm_chunks, bm_claims = BM25(chunk_toks), BM25([tok(t) for t in INDEX.claim_texts])
        build_s = time.perf_counter() - t0
        rows, lat = [], []
        for it in pos:
            g = gold_idx[it["gold_doc"]]
            t0 = time.perf_counter()
            q = tok(queries[it["id"]])
            lat.append((time.perf_counter() - t0) * 1000)
            rows.append({"id": it["id"], "type": it["type"],
                         "claim_rank": doc_rank([INDEX.claim_doc_idx[i] for i, _ in bm_claims.search(q, k=50)], g),
                         "chunk_rank": doc_rank([INDEX.chunks[i].doc_idx for i, _ in bm_chunks.search(q, k=50)], g),
                         "lex": round(len(set(tok(it["gold_claim"])) & set(q)) / max(1, len(set(tok(it["gold_claim"])))), 3)})
        res = {"analyzer_load_s": round(load_s, 2), "rss_added_mb": rss_mb() - r0, "corpus_tokens": n_tok,
               "tokenize_corpus_s_cold": round(tok_s, 1), "bm25_build_s": round(build_s, 1), "vocab": len(bm_chunks.postings),
               "query_tokenize_ms_p50": round(statistics.median(lat), 3),
               "claims": {"R@1": recall_at([r["claim_rank"] for r in rows], 1), "R@5": recall_at([r["claim_rank"] for r in rows], 5),
                          "MRR": mrr([r["claim_rank"] for r in rows])},
               "chunks": {"R@1": recall_at([r["chunk_rank"] for r in rows], 1), "R@5": recall_at([r["chunk_rank"] for r in rows], 5),
                          "MRR": mrr([r["chunk_rank"] for r in rows])},
               "lex_gate_pass(>=0.4)": sum(r["lex"] >= 0.4 for r in rows), "mean_lex": round(statistics.mean(r["lex"] for r in rows), 3),
               "by_type": {}, "rows": rows}
        for t in dict.fromkeys(r["type"] for r in rows):
            tr = [r for r in rows if r["type"] == t]
            res["by_type"][t] = {"n": len(tr), "claims_R@1": recall_at([r["claim_rank"] for r in tr], 1),
                                 "claims_MRR": mrr([r["claim_rank"] for r in tr]), "chunks_R@5": recall_at([r["chunk_rank"] for r in tr], 5),
                                 "lex_pass": sum(r["lex"] >= 0.4 for r in tr), "mean_lex": round(statistics.mean(r["lex"] for r in tr), 3)}
        out[kind] = res
        print(kind, json.dumps({k: v for k, v in res.items() if k not in ("rows", "by_type")}))
        for t, v in res["by_type"].items():
            print(f"    {t:9}", json.dumps(v))
    base = {r["id"]: r for r in out["prefix6"]["rows"]}
    for kind in list(out)[1:]:
        up = sum((r["claim_rank"] or 999) < (base[r["id"]]["claim_rank"] or 999) for r in out[kind]["rows"])
        down = sum((r["claim_rank"] or 999) > (base[r["id"]]["claim_rank"] or 999) for r in out[kind]["rows"])
        out[kind]["paired_vs_prefix6"] = {"claim_rank_better": up, "claim_rank_worse": down}
        print(f"{kind} vs prefix6 — gold claim BM25 rank better in {up}, worse in {down} of {len(base)}")
    (HERE / "results" / "lexical.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
