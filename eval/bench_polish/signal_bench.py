"""Threshold-free comparison of "is this the same claim?" signals on the claim index (~3k fact-checked claims).

    backend/.venv/bin/python eval/bench_polish/signal_bench.py \
        --embed sdadas/mmlw-roberta-base sdadas/mmlw-retrieval-roberta-base --rerank sdadas/polish-reranker-base-ranknet

Why threshold-free: the engine's cosine thresholds (0.68/0.78/0.80/0.82/0.85/0.86/0.88) were calibrated for
mmlw-retrieval-e5-small. Another embedder or a cross-encoder has a different score scale, so dropping it into the
pipeline unchanged would measure the thresholds, not the model. Here every signal is judged the same way:
  - ranking:    rank of the gold Demagog claim among all indexed claims for the 128 positive variants (R@1, R@5, MRR)
  - separation: score(query, gold claim) for positives  vs  the best score ANY indexed claim gets for the 27 hard
                negatives (that best score is what a matcher would have to reject). AUC, and the share of positives
                above the highest hard-negative score ("recall at 0 false accepts") / above the 2nd highest (1 FA).
The oracle threshold is chosen on the benchmark itself, so recall@0FA is an upper bound for every signal alike.
Models are loaded one at a time. Results: results/signals.json
"""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from pathlib import Path

import numpy as np

from run_bench import HERE, mrr, recall_at, rss_mb, setup_env

QUERY_PREFIX = {"sdadas/mmlw-roberta-base": "zapytanie: ", "sdadas/mmlw-retrieval-roberta-base": "zapytanie: ",
                "sdadas/mmlw-e5-small": "query: ", "intfloat/multilingual-e5-small": "query: "}


def auc(pos: list[float], neg: list[float]) -> float:
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def separation(pos: list[float], neg_top: list[float]) -> dict:
    s = sorted(neg_top, reverse=True)
    return {"auc": auc(pos, neg_top), "recall@0FA": round(sum(p > s[0] for p in pos) / len(pos), 3),
            "recall@1FA": round(sum(p > s[1] for p in pos) / len(pos), 3),
            "pos_median": round(statistics.median(pos), 3), "hardneg_top_median": round(statistics.median(neg_top), 3),
            "hardneg_top_max": round(s[0], 3)}


def by_type(items, ranks, scores, thr) -> dict:
    out = {}
    for t in dict.fromkeys(it["type"] for it in items):
        ix = [i for i, it in enumerate(items) if it["type"] == t]
        out[t] = {"n": len(ix), "R@1": recall_at([ranks[i] for i in ix], 1),
                  "above_0FA_threshold": sum(scores[i] > thr for i in ix)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", nargs="*", default=[])
    ap.add_argument("--rerank", nargs="*", default=[])
    ap.add_argument("--rerank-k", type=int, default=30)
    args = ap.parse_args()
    setup_env()
    import torch
    from prawdowid import engine
    from prawdowid.claims import extract_claims
    from prawdowid.config import settings
    from prawdowid.index import INDEX
    from prawdowid.security import neutralize
    from prawdowid.textutil import normalize_ws

    INDEX.load()
    gold_idx = {d.id: i for i, d in enumerate(INDEX.docs)}
    claim_row = {d: r for r, d in enumerate(INDEX.claim_doc_idx)}
    items = [json.loads(l) for l in (HERE / "bench.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # query = what the engine would search with (preamble stripped, question -> statement); for multi-claim inputs
    # the claim closest to the gold claim under the baseline embedder
    queries, rows = [], []
    for it in items:
        row = claim_row[gold_idx[it["gold_doc"]]]
        cl = extract_claims(neutralize(normalize_ws(it["text"])), max_claims=3)
        qs = [c.query for c in cl] or [it["text"]]
        embs = INDEX.encode_query(qs)
        queries.append(qs[int(np.argmax(embs @ INDEX.claim_emb[row]))])
        rows.append(row)
    pos_ix = [i for i, it in enumerate(items) if it["group"] in ("pos", "unverifiable")]
    hn_ix = [i for i, it in enumerate(items) if it["group"] == "hardneg"]
    pos_items = [items[i] for i in pos_ix]
    results: dict = {"n_pos": len(pos_ix), "n_hardneg": len(hn_ix), "n_claims": len(INDEX.claim_texts), "signals": {}}

    def report(name: str, score_matrix_fn, extra: dict) -> None:
        """score_matrix_fn(i) -> (scores over candidate claim rows, candidate rows) for item i"""
        ranks, gold_scores, hn_top = [], [], []
        for i in pos_ix:
            sc, cand = score_matrix_fn(i)
            if rows[i] in cand:
                g = sc[cand.index(rows[i])]
                ranks.append(int((np.asarray(sc) > g).sum()) + 1)
                gold_scores.append(float(g))
            else:
                ranks.append(None)
                gold_scores.append(float("-inf"))
        for i in hn_ix:
            sc, _ = score_matrix_fn(i)
            hn_top.append(float(np.max(sc)))
        sep = separation(gold_scores, hn_top)
        res = {"R@1": recall_at(ranks, 1), "R@5": recall_at(ranks, 5), "MRR": mrr(ranks), **sep,
               "by_type": by_type(pos_items, ranks, gold_scores, sep["hardneg_top_max"]), **extra,
               "gold_scores": [round(x, 4) if x != float("-inf") else None for x in gold_scores],
               "ranks": ranks, "hardneg_top": [round(x, 4) for x in hn_top]}
        results["signals"][name] = res
        print(name, json.dumps({k: v for k, v in res.items() if k not in ("gold_scores", "ranks", "hardneg_top", "by_type")}), flush=True)
        print("   by type:", json.dumps(res["by_type"]), flush=True)

    all_rows = list(range(len(INDEX.claim_texts)))
    # ---- baseline embedder (cached claim embeddings)
    t0 = time.perf_counter()
    q_base = INDEX.encode_query(queries)
    base_ms = (time.perf_counter() - t0) * 1000 / len(queries)
    base_cos = q_base @ INDEX.claim_emb.T
    report(f"cos:{settings.embed_model}", lambda i: (base_cos[i], all_rows), {"query_ms": round(base_ms, 1)})
    # ---- lexical only (BM25 over claims with the current analyzer), for reference
    def bm(i):
        hits = INDEX.claim_bm25.search(engine.tokens(queries[i]), k=50)
        return ([s for _, s in hits] or [0.0], [r for r, _ in hits] or [-1])
    report("bm25:prefix6", bm, {})
    chunk_sample = [c.text for c in INDEX.chunks[:: max(1, len(INDEX.chunks) // 200)]][:200]
    n_chunks = len(INDEX.chunks)
    INDEX.embedder = None
    gc.collect()

    # ---- alternative embedders: claims and queries both with the query prefix (symmetric, as the engine does)
    from sentence_transformers import CrossEncoder, SentenceTransformer

    for name in args.embed:
        r0, t0 = rss_mb(), time.perf_counter()
        m = SentenceTransformer(name, device="cpu", model_kwargs={"torch_dtype": torch.float32})
        m.max_seq_length = 192
        load_s = time.perf_counter() - t0
        pre = QUERY_PREFIX.get(name, "")
        enc = lambda xs: m.encode([pre + x for x in xs], batch_size=32, normalize_embeddings=True, convert_to_numpy=True,  # noqa: E731
                                  show_progress_bar=False).astype(np.float32)
        t0 = time.perf_counter()
        c_emb = enc(INDEX.claim_texts)
        claims_s = time.perf_counter() - t0
        lat = []
        for q in queries[:40]:
            t0 = time.perf_counter()
            enc([q])
            lat.append((time.perf_counter() - t0) * 1000)
        q_emb = enc(queries)
        t0 = time.perf_counter()
        m.encode(chunk_sample, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        chunk_rate = len(chunk_sample) / (time.perf_counter() - t0)
        cos = q_emb @ c_emb.T
        report(f"cos:{name}", lambda i, cos=cos: (cos[i], all_rows),
               {"load_s": round(load_s, 1), "rss_added_mb": rss_mb() - r0, "claim_index_embed_s": round(claims_s, 1),
                "query_ms_p50": round(statistics.median(lat), 1), "query_ms_p95": round(sorted(lat)[int(len(lat) * 0.95) - 1], 1),
                "chunks_per_s": round(chunk_rate, 1), "est_full_passage_reembed_min": round(n_chunks / chunk_rate / 60, 1)})
        del m
        gc.collect()

    # ---- cross-encoder rerankers over the baseline's top-k (dense) + top-k (BM25) claim candidates
    cand_lists = []
    for i in range(len(items)):
        dense = np.argsort(-base_cos[i])[: args.rerank_k].tolist()
        lex = [r for r, _ in INDEX.claim_bm25.search(engine.tokens(queries[i]), k=args.rerank_k)]
        cand_lists.append(list(dict.fromkeys(dense + lex)))
    in_cand = sum(rows[i] in cand_lists[i] for i in pos_ix)
    for name in args.rerank:
        r0, t0 = rss_mb(), time.perf_counter()
        ce = CrossEncoder(name, device="cpu", max_length=256)
        load_s = time.perf_counter() - t0
        scores, lat = {}, []
        for i in pos_ix + hn_ix:
            t0 = time.perf_counter()
            scores[i] = ce.predict([(queries[i], INDEX.claim_texts[r]) for r in cand_lists[i]], batch_size=32, show_progress_bar=False)
            lat.append((time.perf_counter() - t0) * 1000)
        lat.sort()
        t0 = time.perf_counter()
        ce.predict([(queries[0], INDEX.claim_texts[r]) for r in cand_lists[0][:8]], batch_size=8, show_progress_bar=False)
        top8_ms = (time.perf_counter() - t0) * 1000
        report(f"rerank:{name}", lambda i: (scores[i], cand_lists[i]),
               {"load_s": round(load_s, 1), "rss_added_mb": rss_mb() - r0, "gold_in_candidates": f"{in_cand}/{len(pos_ix)}",
                "pairs_per_query_mean": round(statistics.mean(len(c) for c in cand_lists), 1),
                "query_ms_p50": round(statistics.median(lat)), "query_ms_p95": round(lat[int(len(lat) * 0.95) - 1]),
                "ms_for_8_pairs": round(top8_ms)})
        del ce
        gc.collect()
    out = HERE / "results" / "signals.json"
    prev = json.loads(out.read_text()) if out.exists() else {"signals": {}}
    prev["signals"].update(results["signals"])
    results["signals"] = prev["signals"]
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
