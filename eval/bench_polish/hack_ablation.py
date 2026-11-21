"""Which text-normalisation hacks still earn their keep? (embedder only, ~30 s)

    backend/.venv/bin/python eval/bench_polish/hack_ablation.py

1. Question -> statement rewriting (`strip_preamble` / `question_to_claim`): cosine to the gold claim with the raw
   user text vs. with the rewritten query, for the `question` variants (and all positives as a control).
2. Diacritics: cosine for `nodiac` variants vs. the same seed's other close-to-verbatim variants (dense side only;
   the lexical side is covered by lexical_bench.py).
Results: results/hack_ablation.json
"""
from __future__ import annotations

import json
import statistics

from run_bench import HERE, setup_env


def main() -> None:
    setup_env()
    from prawdowid.claims import extract_claims
    from prawdowid.index import INDEX
    from prawdowid.security import neutralize
    from prawdowid.textutil import normalize_ws

    INDEX.load()
    gold_idx = {d.id: i for i, d in enumerate(INDEX.docs)}
    row_of = {d: r for r, d in enumerate(INDEX.claim_doc_idx)}
    items = [json.loads(l) for l in (HERE / "bench.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pos = [it for it in items if it["group"] in ("pos", "unverifiable")]
    out = {}
    for label, sel in (("question", [it for it in pos if it["type"] == "question"]), ("all_positives", pos)):
        raw = INDEX.encode_query([normalize_ws(it["text"]) for it in sel])
        rew = INDEX.encode_query([(extract_claims(neutralize(normalize_ws(it["text"])), 3) or [None])[0].query for it in sel])
        rows = [row_of[gold_idx[it["gold_doc"]]] for it in sel]
        c_raw = [float(raw[i] @ INDEX.claim_emb[r]) for i, r in enumerate(rows)]
        c_rew = [float(rew[i] @ INDEX.claim_emb[r]) for i, r in enumerate(rows)]
        rank1 = lambda q: sum(int((INDEX.claim_emb @ q[i]).argmax()) == r for i, r in enumerate(rows))  # noqa: E731
        out[label] = {"n": len(sel), "median_cos_raw": round(statistics.median(c_raw), 3), "median_cos_rewritten": round(statistics.median(c_rew), 3),
                      "cos>=0.88_raw": sum(c >= 0.88 for c in c_raw), "cos>=0.88_rewritten": sum(c >= 0.88 for c in c_rew),
                      "cos>=0.82_raw": sum(c >= 0.82 for c in c_raw), "cos>=0.82_rewritten": sum(c >= 0.82 for c in c_rew),
                      "rank1_raw": rank1(raw), "rank1_rewritten": rank1(rew),
                      "rewriting_helped": sum(b > a + 0.005 for a, b in zip(c_raw, c_rew)), "rewriting_hurt": sum(b < a - 0.005 for a, b in zip(c_raw, c_rew))}
        print(label, json.dumps(out[label]))
    for t in ("nodiac", "typo", "inflect", "question", "short", "colloq", "para"):
        sel = [it for it in pos if it["type"] == t]
        q = INDEX.encode_query([(extract_claims(neutralize(normalize_ws(it["text"])), 3) or [None])[0].query for it in sel])
        cs = [float(q[i] @ INDEX.claim_emb[row_of[gold_idx[it["gold_doc"]]]]) for i, it in enumerate(sel)]
        out[f"cos_{t}"] = {"n": len(sel), "median": round(statistics.median(cs), 3), "min": round(min(cs), 3), ">=0.88": sum(c >= 0.88 for c in cs)}
        print(t, json.dumps(out[f"cos_{t}"]))
    (HERE / "results" / "hack_ablation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
