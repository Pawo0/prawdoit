"""Polish-language benchmark harness: full pipeline + per-stage trace for every item of bench.jsonl.

    backend/.venv/bin/python eval/bench_polish/run_bench.py --name baseline
    PYTHONPATH=<dir with simplemma/pystempel> backend/.venv/bin/python eval/bench_polish/run_bench.py \
        --name lemma_simplemma --analyzer simplemma
    backend/.venv/bin/python eval/bench_polish/compare.py baseline lemma_simplemma

Nothing in the repo is modified: variants are monkeypatched in-process, and the index cache / SQLite runtime are
redirected to a work dir (default /tmp/prawdowid_bench, override with PRAWDOWID_BENCH_WORK). The corpus is snapshotted
into the work dir on first use so that all variants see the same documents (delete the work dir to re-snapshot).

Analyzer variants (--analyzer): prefix6 (current), pystempel, simplemma, simplemma_p6 (lemma, then 6-char prefix).
Other switches: --no-alt (disable the consonant-alternation hack), --regress <cases.jsonl> (run an existing eval set
through the same patched pipeline and print accuracy).
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import statistics
import sys
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DECISIVE = {"potwierdzone", "falszywe", "wprowadzajace_w_blad"}
CLASSES = ["potwierdzone", "falszywe", "wprowadzajace_w_blad", "brak_dowodow"]


def rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def setup_env() -> Path:
    work = Path(os.environ.get("PRAWDOWID_BENCH_WORK", "/tmp/prawdowid_bench"))
    work.mkdir(parents=True, exist_ok=True)
    for name in ("index", "corpus"):
        if not (work / name).exists():
            shutil.copytree(ROOT / "data" / name, work / name)
    rt = work / "runtime"
    shutil.rmtree(rt, ignore_errors=True)  # fresh audit DB per run; never the repo's data/runtime
    rt.mkdir()
    os.environ.update(PRAWDOWID_INDEX_DIR=str(work / "index"), PRAWDOWID_CORPUS_DIR=str(work / "corpus"),
                      PRAWDOWID_RUNTIME_DIR=str(rt), PRAWDOWID_SCHEDULER="0", PRAWDOWID_LIVE_SEARCH="0",
                      PRAWDOWID_LLM_BASE_URL="", TOKENIZERS_PARALLELISM="false")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(ROOT / "backend"))
    return work


# --------------------------------------------------------------------------------------------- analyzer variants
def make_tokens(kind: str):
    """Drop-in replacement for textutil.tokens(). Stop words, number handling and diacritic stripping are unchanged;
    only the word normaliser differs."""
    import prawdowid.textutil as tu

    if kind == "pystempel":
        from pystempel import Stemmer

        st = Stemmer.polimorf()
        norm = lru_cache(maxsize=1_000_000)(lambda w: tu.strip_pl(st(w.lower()) or w))
        cut = False
    elif kind in ("simplemma", "simplemma_p6"):
        import simplemma

        norm = lru_cache(maxsize=1_000_000)(lambda w: tu.strip_pl(simplemma.lemmatize(w, lang="pl")))
        cut = kind.endswith("_p6")
    else:
        raise SystemExit(f"unknown analyzer {kind}")

    def tokens(text: str, stem: int = 6) -> list[str]:
        out = []
        for m in tu._TOKEN_RE.finditer(text):
            t = m.group(0)
            low = t.lower()
            if low in tu.STOP or len(t) < 2:
                continue
            if t[0].isdigit():
                out.append(low.replace(",", "."))
                continue
            n = norm(t)
            out.append(n[:stem] if cut else n)
        return out

    return tokens, norm


def patch_analyzer(kind: str) -> None:
    import re

    import prawdowid.answer as answer
    import prawdowid.engine as engine
    import prawdowid.index as index
    import prawdowid.service as service
    import prawdowid.textutil as tu
    import prawdowid.websearch as websearch

    tokens, norm = make_tokens(kind)
    for mod in (tu, engine, index, service, websearch, answer):  # every `from .textutil import tokens` binding
        if hasattr(mod, "tokens"):
            mod.tokens = tokens
    # module-level constant computed with the old analyzer at import time
    engine._GENERIC = set(tokens("polsce polska polski gus nbp eurostat kurs średni dane wskaźnik według wyniósł wyniosła "
                                 "wynosi procent proc r/r rok roku miesiąc ceny obwieszczenie państwowej komisji wyborczej dnia"))
    cut = kind.endswith("_p6")

    def _bound_values(keys, source, unit):  # same as engine._bound_values, with the patched word normaliser
        occ: dict[str, list[int]] = {}
        for m in engine._WORD.finditer(source):
            st = norm(m.group(0))
            st = st[:6] if cut else st
            if st in keys:
                occ.setdefault(st, []).append(m.end())
        nums = [(m.start(), float(m.group(1).replace(",", ".")), engine._unit(m.group(2))) for m in engine._NUM.finditer(source)]
        bound: dict[str, list[float]] = {}
        for k, ends in occ.items():
            for e in ends:
                nxt = next((v for p, v, u in nums if e <= p <= e + 90 and u == unit), None)
                if nxt is not None:
                    bound.setdefault(k, []).append(nxt)
        if not bound:
            return []
        rarest = min(len(occ[k]) for k in bound)
        return [v for k in bound if len(occ[k]) == rarest for v in bound[k]]

    engine._bound_values = _bound_values
    _ = re


def patch_no_alt() -> None:
    """Disable the sz/ch, cz/c, rz/r alternation hack: compare analyzer tokens directly."""
    import prawdowid.engine as engine

    engine._alt_stems = lambda toks: set(toks)


def patch_rules(kind: str) -> None:
    """What-if variants of the "is it the same claim as the fact-checked one?" decision (engine.same_claim).
    engine.py is re-executed in memory with edited source — the file on disk is untouched. Apply BEFORE patch_analyzer.

    no_lex   : drop the lexical-overlap gate (`lex >= 0.4`) and close the 0.78–0.80 dead zone (NLI asked from 0.74 =
               settings.claim_match_soft).
    bidir_nli: no cosine-only acceptance and no lexical gate. Same claim  <=>  no contradiction (either direction) and
               cos >= 0.74 and entailment >= 0.8 in at least one direction (user text => checked claim, or the reverse).
               The reverse NLI pass is computed for every claim candidate (today only for cos >= 0.85)."""
    import prawdowid.engine as engine
    import prawdowid.service as service

    src = Path(engine.__file__).read_text(encoding="utf-8")

    def sub(old: str, new: str) -> None:
        nonlocal src
        assert src.count(old) == 1, f"engine.py changed, cannot patch: {old!r}"
        src = src.replace(old, new)

    sub("c.claim_cos >= 0.78:", "c.claim_cos >= 0.74:")
    if kind == "no_lex":
        sub("cos >= 0.80 and fwd.entail >= 0.8 and lex >= 0.4)", "cos >= 0.74 and fwd.entail >= 0.8)")
    elif kind == "bidir_nli":
        sub("if c.claim_cos >= 0.85:  # reverse direction", "if c.claim_cos >= 0.74:  # reverse direction")
        sub("""            (cos >= 0.88 and not incident)
            or (cos >= 0.86 and fwd.entail >= (0.8 if incident else 0.5))
            or (not incident and cos >= 0.80 and fwd.entail >= 0.8 and lex >= 0.4)):""",
            """            cos >= 0.74 and max(fwd.entail, 0.0 if incident else rev.entail) >= 0.8):""")
    else:
        raise SystemExit(f"unknown rule variant {kind}")
    exec(compile(src, engine.__file__, "exec"), engine.__dict__)
    service.verify_claim, service.same_claim = engine.verify_claim, engine.same_claim


# --------------------------------------------------------------------------------------------- per-item trace
def doc_rank(order: list[int], gold: int) -> int | None:
    seen: list[int] = []
    for d in order:
        if d not in seen:
            seen.append(d)
    return seen.index(gold) + 1 if gold in seen else None


def trace(text: str, gold_idx: int) -> dict:
    """Where does the gold Demagog document stand at each stage? Mirrors engine.verify_claim for the first claim."""
    import numpy as np
    from prawdowid import engine
    from prawdowid.claims import extract_claims
    from prawdowid.index import INDEX
    from prawdowid.nli import NLI_MODEL
    from prawdowid.security import neutralize
    from prawdowid.textutil import normalize_ws

    claims = extract_claims(neutralize(normalize_ws(text)), max_claims=3)
    if not claims:
        return {"stage": "no_claim"}
    best = None
    for c in claims:  # multi-sentence inputs are split into several claims: trace the one closest to the gold claim
        q_emb = INDEX.encode_query([c.query])[0]
        row = INDEX.claim_doc_idx.index(gold_idx)
        cos_all = INDEX.claim_emb @ q_emb
        if best is None or cos_all[row] > best[3][best[2]]:
            best = (c, q_emb, row, cos_all)
    c, q_emb, row, cos_all = best
    q = c.query
    toks = engine.tokens(q)
    t = {"query": q, "kind": c.kind, "n_claims": len(claims), "gold_cos": round(float(cos_all[row]), 4)}
    t["claim_dense_rank"] = int((cos_all > cos_all[row]).sum()) + 1
    bm = [INDEX.claim_doc_idx[i] for i, _ in INDEX.claim_bm25.search(toks, k=50)]
    t["claim_bm25_rank"] = doc_rank(bm, gold_idx)
    mc = INDEX.match_claims(q_emb, q, k=8)
    t["match_rank"] = doc_rank([d for d, _ in mc], gold_idx)
    t["top1_cos"] = round(mc[0][1], 4) if mc else None
    t["top1_doc"] = INDEX.docs[mc[0][0]].id if mc else None
    hy = INDEX.search_chunks(q, q_emb, k=40)
    t["chunk_hybrid_rank"] = doc_rank([INDEX.chunks[i].doc_idx for i, _, _ in hy], gold_idx)
    t["chunk_bm25_rank"] = doc_rank([INDEX.chunks[i].doc_idx for i, _ in INDEX.bm25.search(toks, k=40)], gold_idx)
    dense = np.argsort(-(INDEX.chunk_emb @ q_emb))[:40]
    t["chunk_dense_rank"] = doc_rank([INDEX.chunks[int(i)].doc_idx for i in dense], gold_idx)
    d = INDEX.docs[gold_idx]
    fwd, rev = NLI_MODEL.score([(q, d.claim), (d.claim, q)])
    t["nli_fwd"] = [round(fwd.entail, 3), round(fwd.neutral, 3), round(fwd.contra, 3)]
    t["nli_rev"] = [round(rev.entail, 3), round(rev.neutral, 3), round(rev.contra, 3)]
    t["lex"] = round(engine._relevance(set(engine.tokens(d.claim)), q), 3)
    cos = t["gold_cos"]
    same = engine.same_claim(cos, fwd, rev if cos >= 0.85 else fwd, d.claim, q, d.source_type) if cos >= 0.78 else None
    t["same_claim"] = same
    # first stage at which the gold document stops being able to produce a verdict
    if c.kind in ("opinia", "prognoza"):
        t["stage"] = "1_kind_gate(R1 regex)"
    elif t["match_rank"] is None:
        t["stage"] = "2_retrieval_miss(not in top-8 claims)"
    elif cos < 0.68:
        t["stage"] = "3_cos_floor(<0.68)"
    elif cos < 0.78:
        t["stage"] = "4_match_threshold(cos<0.78: NLI never asked)"
    elif same is None:
        if max(fwd.contra, rev.contra if cos >= 0.85 else fwd.contra) >= 0.5:
            t["stage"] = "5_nli_contradiction_veto"
        elif cos < 0.80:
            t["stage"] = "5_cos_0.78-0.80_dead_zone"
        elif fwd.entail < 0.8 and cos < 0.86:
            t["stage"] = "5_nli_entail<0.8(cos 0.80-0.86)"
        elif fwd.entail >= 0.8 and t["lex"] < 0.4 and cos < 0.86:
            t["stage"] = "5_lexical_gate(lex<0.4)"
        else:
            t["stage"] = "5_nli_entail_low(cos 0.86-0.88)"
    else:
        t["stage"] = "6_matched(same=%s)" % same
    return t


def predicted(res) -> str:
    vs = [c.verdict for c in res.claims]
    if res.status != "ok" or not vs:
        return f"status:{res.status}"
    dec = [v for v in vs if v in DECISIVE]
    return dec[0] if dec else vs[0]


def outcome(pred: str, expected: str) -> str:
    """correct | abstain | false_verdict. An abstention where a verdict was expected is a miss, not a false verdict."""
    if expected == "brak_dowodow":
        return "false_verdict" if pred in DECISIVE else "correct"
    if pred == expected:
        return "correct"
    return "false_verdict" if pred in DECISIVE else "abstain"


def macro_f1(rows: list[dict]) -> float:
    f = []
    for cls in CLASSES:
        norm = lambda p: p if p in DECISIVE else "brak_dowodow"  # noqa: E731
        tp = sum(r["expected"] == cls and norm(r["pred"]) == cls for r in rows)
        fp = sum(r["expected"] != cls and norm(r["pred"]) == cls for r in rows)
        fn = sum(r["expected"] == cls and norm(r["pred"]) != cls for r in rows)
        if tp + fp + fn:
            f.append(2 * tp / (2 * tp + fp + fn))
    return round(statistics.mean(f), 3)


def recall_at(ranks: list, k: int) -> float:
    return round(sum(1 for r in ranks if r is not None and r <= k) / max(1, len(ranks)), 3)


def mrr(ranks: list) -> float:
    return round(statistics.mean(1 / r if r else 0.0 for r in ranks), 3) if ranks else 0.0


def summarise(rows: list[dict]) -> dict:
    s: dict = {"n": len(rows)}
    oc = Counter(r["outcome"] for r in rows)
    s["correct"], s["abstain_miss"], s["false_verdicts"] = oc["correct"], oc["abstain"], oc["false_verdict"]
    s["accuracy"] = round(oc["correct"] / len(rows), 3)
    s["macro_f1"] = macro_f1(rows)
    for g in ("pos", "neg", "hardneg", "unverifiable"):
        gr = [r for r in rows if r["group"] == g]
        c = Counter(r["outcome"] for r in gr)
        s[f"group_{g}"] = {"n": len(gr), "correct": c["correct"], "abstain_miss": c["abstain"], "false_verdict": c["false_verdict"]}
    s["by_type"] = {}
    for t in dict.fromkeys(r["type"] for r in rows):
        tr = [r for r in rows if r["type"] == t]
        c = Counter(r["outcome"] for r in tr)
        s["by_type"][t] = {"n": len(tr), "correct": c["correct"], "abstain_miss": c["abstain"], "false_verdict": c["false_verdict"]}
    ret = [r for r in rows if r["group"] in ("pos", "unverifiable") and "trace" in r and "gold_cos" in r["trace"]]
    s["retrieval_n"] = len(ret)
    s["retrieval"] = {}
    for key in ("claim_dense_rank", "claim_bm25_rank", "match_rank", "chunk_bm25_rank", "chunk_dense_rank", "chunk_hybrid_rank"):
        ranks = [r["trace"][key] for r in ret]
        s["retrieval"][key] = {"R@1": recall_at(ranks, 1), "R@5": recall_at(ranks, 5), "MRR": mrr(ranks)}
    s["retrieval_by_type"] = {}
    for t in dict.fromkeys(r["type"] for r in ret):
        tr = [r["trace"] for r in ret if r["type"] == t]
        s["retrieval_by_type"][t] = {"n": len(tr), "claim_bm25_R@1": recall_at([x["claim_bm25_rank"] for x in tr], 1),
                                     "claim_bm25_R@5": recall_at([x["claim_bm25_rank"] for x in tr], 5),
                                     "chunk_bm25_R@5": recall_at([x["chunk_bm25_rank"] for x in tr], 5),
                                     "claim_dense_R@1": recall_at([x["claim_dense_rank"] for x in tr], 1),
                                     "cos>=0.82": sum(x["gold_cos"] >= 0.82 for x in tr),
                                     "cos>=0.78": sum(x["gold_cos"] >= 0.78 for x in tr),
                                     "median_cos": round(statistics.median(x["gold_cos"] for x in tr), 3)}
    miss = [r for r in rows if r["group"] in ("pos", "neg") and r["outcome"] != "correct" and "trace" in r]
    s["failure_stage"] = dict(Counter(r["trace"].get("stage", "?") for r in miss).most_common())
    lat = sorted(r["ms"] for r in rows)
    s["latency_ms"] = {"p50": round(statistics.median(lat)), "p95": round(lat[int(len(lat) * 0.95) - 1]), "max": round(lat[-1])}
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--analyzer", default="prefix6")
    ap.add_argument("--no-alt", action="store_true")
    ap.add_argument("--rule", default="", help="what-if same-claim rule: no_lex | bidir_nli (see patch_rules)")
    ap.add_argument("--bench", default=str(HERE / "bench.jsonl"))
    ap.add_argument("--regress", nargs="*", default=[], help="existing eval sets (eval/cases*.jsonl) to run as regression check")
    ap.add_argument("--no-trace", action="store_true")
    ap.add_argument("--skip-bench", action="store_true", help="only run the --regress sets")
    args = ap.parse_args()
    setup_env()
    rss0 = rss_mb()
    t0 = time.perf_counter()
    if args.rule:
        patch_rules(args.rule)
    if args.analyzer != "prefix6":
        patch_analyzer(args.analyzer)
    if args.no_alt:
        patch_no_alt()
    t_an = time.perf_counter() - t0
    rss_an = rss_mb()
    from prawdowid.index import INDEX
    from prawdowid.nli import NLI_MODEL
    from prawdowid.schemas import CheckRequest
    from prawdowid.service import run_check

    t0 = time.perf_counter()
    INDEX.load()
    t_index = time.perf_counter() - t0
    t0 = time.perf_counter()
    INDEX.encode_query(["rozgrzewka"])
    NLI_MODEL.score([("a", "b")])
    t_models = time.perf_counter() - t0
    gold_idx = {d.id: i for i, d in enumerate(INDEX.docs)}

    items = [json.loads(l) for l in Path(args.bench).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.skip_bench:
        items = []
    rows = []
    for it in items:
        t0 = time.perf_counter()
        res = run_check(CheckRequest(text=it["text"], url=None, channel="eval"))
        ms = (time.perf_counter() - t0) * 1000
        pred = predicted(res)
        r = {**{k: it[k] for k in ("id", "seed", "type", "group", "text", "expected", "gold_doc")}, "pred": pred,
             "outcome": outcome(pred, it["expected"]), "ms": round(ms, 1), "timings": res.timings_ms,
             "verdicts_all": [c.verdict for c in res.claims], "rules": [x for c in res.claims for x in c.rules_fired],
             "reason_codes": [x for c in res.claims for x in c.reason_codes],
             "quote_gate_skips": sum("bramka V2" in l for c in res.claims for l in c.limitations),
             "decisive_sources": [e.doc_id for c in res.claims if c.verdict in DECISIVE for e in c.evidence
                                  if e.stance in ("przeczy", "popiera") or e.same_claim is not None][:3]}
        if not args.no_trace and it["gold_doc"] in gold_idx:
            r["trace"] = trace(it["text"], gold_idx[it["gold_doc"]])
        rows.append(r)
        print(f"{'OK ' if r['outcome'] == 'correct' else 'ABS' if r['outcome'] == 'abstain' else 'ERR'} {r['id']:12} "
              f"exp={r['expected'][:12]:12} got={pred[:14]:14} {r.get('trace', {}).get('stage', '')}", flush=True)

    summary = summarise(rows) if rows else {}
    summary.setdefault("latency_ms", {})
    summary["setup"] = {"analyzer": args.analyzer, "rule": args.rule, "no_alt": args.no_alt, "embed_model": os.environ.get("PRAWDOWID_EMBED_MODEL", "default"),
                        "analyzer_load_s": round(t_an, 2), "analyzer_rss_mb": rss_an - rss0, "index_build_s": round(t_index, 1),
                        "models_load_s": round(t_models, 1), "peak_rss_mb": rss_mb(), "documents": INDEX.stats.get("documents"),
                        "chunks": INDEX.stats.get("chunks"), "claims": INDEX.stats.get("factchecked_claims")}
    regress = {}
    for path in args.regress:
        cases = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        cases = [c for c in cases if not c.get("url")]  # text-only: no network in the benchmark
        rr = []
        for c in cases:
            res = run_check(CheckRequest(text=c["text"], url=None, channel="eval"))
            v = res.claims[0].verdict if res.claims else None
            ok = res.status == c["expected_status"] and (not c["expected"] or v in c["expected"])
            fv = bool(c["expected"]) and v in DECISIVE and v not in c["expected"]
            rr.append({"id": c["id"], "ok": ok, "verdict": v or res.status, "expected": c["expected"] or c["expected_status"], "false_verdict": fv})
        regress[Path(path).name] = {"n": len(rr), "ok": sum(r["ok"] for r in rr), "false_verdicts": sum(r["false_verdict"] for r in rr), "rows": rr}
        print(f"regress {Path(path).name}: {regress[Path(path).name]['ok']}/{len(rr)} ok, false verdicts {regress[Path(path).name]['false_verdicts']}")
    out = HERE / "results" / f"{args.name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows, "regress": regress}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("retrieval_by_type",)}, ensure_ascii=False, indent=1))
    print("peak RSS MB:", rss_mb())


if __name__ == "__main__":
    main()
