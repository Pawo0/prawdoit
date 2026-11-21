"""Measure the tier-1 router (`service.quick_score`, POST /api/quick) on data that is already in the repo.

    backend/.venv/bin/python eval/measure_router.py                    # router only
    backend/.venv/bin/python eval/measure_router.py --tier2            # + background (auto) tier-2 checks
    backend/.venv/bin/python eval/measure_router.py --official 0 --verbatim 0 --loo 0   # quick look, bench only

What it reports (research/09_architecture_two_tier_and_containers.md §3.8), each rate with a Wilson 95 % interval:

  recall      share of inputs that repeat a debunked claim that are routed onwards (state candidate or match), and
              the share that gets the visible sourced tag at once (state match);
  false tags  share of inputs that must NOT get a visible tag and get one (state match): hard negatives and negations
              from eval/bench_polish, claims that fact-checkers rated TRUE, sentences from official sources;
  NLI saved   NLI pairs with the old gate (cosine 0.74) and with the new one (0.80), and whether any legacy output
              field (risk, level, match, reason) differs between the two;
  latency     wall time per batch of 16 items, old gate and new;
  --tier2     what the background check adds: for the bench items, how many would get a badge from an auto-mode
              check (decisive verdict + cited source), on positives and on items that must stay unmarked.

Sets, all from the repo:
  bench/*        eval/bench_polish/bench.jsonl — 170 hand-written variants of 32 Demagog claims (ground truth: the
                 Demagog rating in data/corpus/demagog.jsonl)
  cases/*        eval/cases*.jsonl, text cases only
  corpus/*       claims from data/corpus: debunked claims verbatim (upper bound — the claim is in the index),
                 the same with the claim's own document hidden (leave-one-out: is it caught through another entry?),
                 claims rated true, sentences from MSZ / MON / KPRM news

Nothing in the repo is modified: index cache, corpus snapshot and the SQLite runtime live in a work directory
(PRAWDOWID_BENCH_WORK, default /tmp/prawdowid_router_bench). Live search is off. Needs the two local models
(about 3 GB RAM); nothing is sent anywhere.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = 16
LEGACY = ("risk", "level", "match", "reason")
DEBUNKED = ("false", "misleading", "mixed")
DECISIVE_FALSE = ("falszywe", "wprowadzajace_w_blad")


def setup_env() -> Path:
    work = Path(os.environ.get("PRAWDOWID_BENCH_WORK", "/tmp/prawdowid_router_bench"))
    work.mkdir(parents=True, exist_ok=True)
    for name in ("index", "corpus"):
        if not (work / name).exists():
            shutil.copytree(ROOT / "data" / name, work / name)
    rt = work / "runtime"
    shutil.rmtree(rt, ignore_errors=True)
    rt.mkdir()
    os.environ.update(PRAWDOWID_INDEX_DIR=str(work / "index"), PRAWDOWID_CORPUS_DIR=str(work / "corpus"),
                      PRAWDOWID_RUNTIME_DIR=str(rt), PRAWDOWID_SCHEDULER="0", PRAWDOWID_LIVE_SEARCH="0",
                      PRAWDOWID_LLM_BASE_URL="", TOKENIZERS_PARALLELISM="false")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(ROOT / "backend"))
    return work


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n))


def rate(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% [{100 * lo:.1f}–{100 * hi:.1f}]" if n else "0/0"


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else 0.0


# ---------------------------------------------------------------------------------------------------- data sets
def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_sets(args) -> dict[str, dict]:
    """name -> {kind: 'P' (repeats a debunked claim) | 'N' (must not get a visible tag), items: [(id, text)]}"""
    from prawdowid.textutil import normalize_ws, split_sentences

    rng = random.Random(args.seed)
    sets: dict[str, dict] = {}

    def add(name: str, kind: str, items: list[tuple[str, str]], note: str) -> None:
        if items:
            sets[name] = {"kind": kind, "note": note, "items": items}

    bench = jsonl(ROOT / "eval" / "bench_polish" / "bench.jsonl")
    pos = [b for b in bench if b["group"] == "pos"]
    add("bench/pos-debunked", "P", [(b["id"], b["text"]) for b in pos if b["rating"] in DEBUNKED],
        "variants (inflection, question, no diacritics, colloquial, paraphrase, short, typo) of claims Demagog debunked")
    add("bench/hardneg", "N", [(b["id"], b["text"]) for b in bench if b["group"] == "hardneg"],
        "same topic and entities as a rated claim, but a statement nobody checked")
    add("bench/neg", "N", [(b["id"], b["text"]) for b in bench if b["group"] == "neg"],
        "the opposite of a rated claim")
    add("bench/pos-true", "N", [(b["id"], b["text"]) for b in pos if b["rating"] == "true"],
        "variants of claims Demagog rated true")
    add("bench/unverifiable", "N", [(b["id"], b["text"]) for b in bench if b["group"] == "unverifiable"],
        "variants of claims Demagog rated unverifiable")

    cases = []
    for name in ("cases.jsonl", "cases_heldout.jsonl", "cases_blind2.jsonl"):
        cases += [c for c in jsonl(ROOT / "eval" / name) if c.get("text") and not c.get("url") and c.get("expected")]
    falsy = lambda c: c["expected"][0] in DECISIVE_FALSE and "potwierdzone" not in c["expected"]  # noqa: E731
    add("cases/false-or-misleading", "P", [(c["id"], c["text"]) for c in cases if falsy(c)],
        "team eval cases expected false/misleading (includes claims refuted by official data, which have no rated "
        "claim to match: for those only `candidate` is possible)")
    add("cases/other", "N", [(c["id"], c["text"]) for c in cases if not set(c["expected"]) & set(DECISIVE_FALSE)],
        "team eval cases expected confirmed / no evidence / opinion")

    corpus = Path(os.environ["PRAWDOWID_CORPUS_DIR"])
    fc = []
    for f in sorted(corpus.glob("*.jsonl")):
        fc += [d for d in jsonl(f) if d.get("source_type") in ("factcheck", "incident") and (d.get("claim") or d.get("title"))]
    claim = lambda d: normalize_ws(d.get("claim") or d["title"])[:1500]  # noqa: E731
    demagog = [d for d in fc if d["publisher"] == "Demagog" and d.get("verdict") in DEBUNKED and len(claim(d)) >= 40]
    rng.shuffle(demagog)
    add("corpus/debunked-verbatim", "P", [(d["id"], claim(d)) for d in demagog[: args.verbatim]],
        "Demagog claims rated false/misleading/mixed, word for word (the claim itself is in the index: upper bound)")
    sets["corpus/debunked-loo"] = {"kind": "P", "loo": True, "items": [(d["id"], claim(d)) for d in demagog[: args.loo]],
                                   "note": "the same claims with their own document hidden from the index: caught only "
                                           "if another entry rates the same claim"}
    if not args.loo:
        del sets["corpus/debunked-loo"]
    add("corpus/rated-true", "N", [(d["id"], claim(d)) for d in fc if d.get("verdict") == "true" and len(claim(d)) >= 40],
        "every claim a fact-checker rated true, word for word")
    official = []
    for name in ("official_govpl_msz.jsonl", "mon_aktualnosci.jsonl", "kprm_wydarzenia.jsonl"):
        if (corpus / name).exists():
            for d in jsonl(corpus / name):
                official += [(f"{d['id']}#{i}", s) for i, s in enumerate(split_sentences(normalize_ws(d.get("text") or "")))
                             if 40 <= len(s) <= 400]
    rng.shuffle(official)
    add("corpus/official-sentences", "N", official[: args.official],
        "random sentences from MSZ (gov.pl), MON and KPRM news: ordinary true content")
    return sets


# ---------------------------------------------------------------------------------------------------- measurement
class NLICounter:
    """Counts the pairs sent to the NLI model."""

    def __init__(self, nli) -> None:
        self.nli, self.pairs, self._orig = nli, 0, nli.score
        nli.score = self._score

    def _score(self, pairs):
        self.pairs += len(pairs)
        return self._orig(pairs)

    def take(self) -> int:
        n, self.pairs = self.pairs, 0
        return n


def run_quick(items: list[tuple[str, str]], counter: NLICounter, **kw) -> tuple[dict[str, object], list[float], int]:
    from prawdowid.schemas import QuickItem, QuickRequest
    from prawdowid.service import quick_score

    out, times = {}, []
    counter.take()
    for i in range(0, len(items), BATCH):
        chunk = items[i: i + BATCH]
        t = time.perf_counter()
        res = quick_score(QuickRequest(items=[QuickItem(id=str(n), text=text[:4000]) for n, (_, text) in enumerate(chunk)]),
                          use_cache=False, **kw)
        if len(chunk) == BATCH:
            times.append(time.perf_counter() - t)
        for (item_id, _), r in zip(chunk, res):
            out[item_id] = r
    return out, times, counter.take()


def run_loo(items: list[tuple[str, str]], counter: NLICounter) -> dict[str, object]:
    """Each claim alone, with its own document's claim vector hidden from the index."""
    from prawdowid.index import INDEX

    by_id = {d.id: i for i, d in enumerate(INDEX.docs)}
    rows_of: dict[int, list[int]] = {}
    for row, di in enumerate(INDEX.claim_doc_idx):
        rows_of.setdefault(di, []).append(row)
    out = {}
    for item_id, text in items:
        rows = rows_of.get(by_id.get(item_id, -1), [])
        saved = INDEX.claim_emb[rows].copy()
        INDEX.claim_emb[rows] = 0.0  # cosine 0 to everything: the document cannot be the nearest claim
        try:
            out.update(run_quick([(item_id, text)], counter)[0])
        finally:
            INDEX.claim_emb[rows] = saved
    return out


def summarise(name: str, spec: dict, results: dict[str, object]) -> dict:
    rs = [results[i] for i, _ in spec["items"]]
    states = Counter(r.state for r in rs)
    n = len(rs)
    row = {"set": name, "kind": spec["kind"], "n": n, "note": spec["note"], "states": dict(states),
           "match": states["match"], "candidate": states["candidate"], "none": states["none"],
           "routed": states["match"] + states["candidate"],
           "suppressed_by_conflict": sum(1 for r in rs if r.conflict is not None),
           "near_miss": sum(1 for r in rs if "NEAR_MISS" in r.reasons),
           "priority_ge_0.6": sum(1 for r in rs if r.state == "candidate" and r.priority >= 0.6)}
    row["match_ci"], row["routed_ci"] = wilson(row["match"], n), wilson(row["routed"], n)
    row["visible"] = [{"id": i, "text": t[:160], "publisher": results[i].match.publisher, "claim": results[i].match.claim[:160],
                       "verdict_raw": results[i].match.verdict_raw, "similarity": results[i].match.similarity}
                      for i, t in spec["items"] if results[i].state == "match"]
    row["conflicts"] = [{"id": i, "text": t[:160], "debunked": results[i].match.claim[:120], "true": results[i].conflict.claim[:120],
                         "sim_debunked": results[i].match.similarity, "sim_true": results[i].conflict.similarity}
                        for i, t in spec["items"] if results[i].conflict is not None]
    return row


def badge_from_check(res) -> bool:
    """The extension's rule for a background check: decisive false/misleading verdict AND a cited, linked source."""
    if res.status != "ok":
        return False
    for c in res.claims:
        if c.verdict not in DECISIVE_FALSE:
            continue
        ev = c.evidence[c.main_evidence] if c.main_evidence is not None and c.main_evidence < len(c.evidence) else next(
            (e for e in c.evidence if e.stance == "przeczy"), None)
        if ev is not None and ev.publisher and ev.url.startswith("http"):
            return True
    return False


def run_tier2(sets: dict[str, dict], quick: dict[str, dict[str, object]]) -> list[dict]:
    from prawdowid.schemas import CheckRequest
    from prawdowid.service import run_check

    rows = []
    for name, spec in sets.items():
        if not name.startswith(("bench/", "cases/")):
            continue
        n = len(spec["items"])
        decisive = badge = dropped = top3 = 0
        lat = []
        for item_id, text in spec["items"]:
            t = time.perf_counter()
            res = run_check(CheckRequest(text=text[:6000], channel="extension", mode="auto"))
            lat.append(time.perf_counter() - t)
            is_false = any(c.verdict in DECISIVE_FALSE for c in res.claims)
            q = quick[name][item_id]
            decisive += is_false
            dropped += is_false and q.state == "none"
            shown = badge_from_check(res)
            badge += shown
            top3 += shown and q.state == "candidate" and q.priority >= 0.6
        rows.append({"set": name, "kind": spec["kind"], "n": n, "tier2_false_or_misleading": decisive,
                     "tier2_badge": badge, "dropped_by_tier1": dropped, "badge_and_near_miss_candidate": top3,
                     "latency_s_p50": round(pct(lat, 0.5), 3), "latency_s_p95": round(pct(lat, 0.95), 3)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--official", type=int, default=400, help="sample of official-source sentences (0 = skip)")
    ap.add_argument("--verbatim", type=int, default=300, help="sample of debunked Demagog claims, word for word")
    ap.add_argument("--loo", type=int, default=150, help="of those, how many to repeat with their own document hidden")
    ap.add_argument("--tier2", action="store_true", help="also run a background (auto) check on the bench and case items")
    ap.add_argument("--seed", type=int, default=20261121)
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "router_measure.json"))
    args = ap.parse_args()
    setup_env()

    from prawdowid import service
    from prawdowid.config import settings
    from prawdowid.index import INDEX
    from prawdowid.nli import NLI_MODEL

    t0 = time.perf_counter()
    INDEX.load()
    INDEX.encode_query(["rozgrzewka"])
    NLI_MODEL.score([("rozgrzewka", "rozgrzewka")])
    counter = NLICounter(NLI_MODEL)
    print(f"index: {INDEX.stats}; models ready in {time.perf_counter() - t0:.1f}s", file=sys.stderr)

    sets = build_sets(args)
    quick: dict[str, dict[str, object]] = {}
    rows, gate = [], {"items": 0, "nli_pairs_old_gate": 0, "nli_pairs_new_gate": 0, "legacy_fields_differ": [],
                      "changed_by_conflict_rule": 0, "batch_s_old": [], "batch_s_new": []}
    legacy = lambda r: tuple(getattr(r, f) for f in LEGACY)  # noqa: E731
    for name, spec in sets.items():
        if spec.get("loo"):
            quick[name] = run_loo(spec["items"], counter)
            rows.append(summarise(name, spec, quick[name]))
            continue
        # A: the gate as it was (NLI from the soft threshold), no conflict rule = the behaviour before this change
        old, t_old, pairs_old = run_quick(spec["items"], counter, nli_gate=settings.claim_match_soft, suppress_conflicts=False)
        # B: the router as shipped
        new, t_new, pairs_new = run_quick(spec["items"], counter)
        quick[name] = new
        gate["items"] += len(spec["items"])
        gate["nli_pairs_old_gate"] += pairs_old
        gate["nli_pairs_new_gate"] += pairs_new
        gate["batch_s_old"] += t_old
        gate["batch_s_new"] += t_new
        # same legacy output? Items the conflict rule changed are re-run with the new gate and the rule off.
        changed = [(i, t) for i, t in spec["items"] if new[i].conflict is not None]
        gate["changed_by_conflict_rule"] += len(changed)
        plain = run_quick(changed, counter, suppress_conflicts=False)[0] if changed else {}
        for i, t in spec["items"]:
            a, b = legacy(old[i]), legacy(plain.get(i, new[i]))
            if a != b:
                gate["legacy_fields_differ"].append({"set": name, "id": i, "old": [old[i].risk, old[i].level],
                                                     "new": [plain.get(i, new[i]).risk, plain.get(i, new[i]).level]})
        rows.append(summarise(name, spec, new))
        print(f"  {name}: {len(spec['items'])} items", file=sys.stderr)

    tier2 = run_tier2(sets, quick) if args.tier2 else []

    # ------------------------------------------------------------------------------------------------ report
    lat = {k: {"n_batches": len(gate[f"batch_s_{k}"]), "p50_s": round(pct(gate[f"batch_s_{k}"], 0.5), 3),
               "p95_s": round(pct(gate[f"batch_s_{k}"], 0.95), 3),
               "mean_s": round(statistics.mean(gate[f"batch_s_{k}"]), 3) if gate[f"batch_s_{k}"] else 0.0}
           for k in ("old", "new")}
    saved = gate["nli_pairs_old_gate"] - gate["nli_pairs_new_gate"]
    print("\n## Router states per set (P = repeats a debunked claim, N = must not get a visible tag)\n")
    print("| set | kind | n | routed onwards (candidate+match) | visible tag (match) | hidden by conflict rule | none |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['set']} | {r['kind']} | {r['n']} | {rate(r['routed'], r['n'])} | {rate(r['match'], r['n'])} | "
              f"{r['suppressed_by_conflict']} | {r['none']} |")
    p_rows = [r for r in rows if r["kind"] == "P" and not r["set"].endswith(("verbatim", "loo"))]
    n_rows = [r for r in rows if r["kind"] == "N"]
    tot = lambda rs, k: sum(r[k] for r in rs)  # noqa: E731
    print(f"\nRecall on paraphrased positives (bench + cases): routed {rate(tot(p_rows, 'routed'), tot(p_rows, 'n'))}; "
          f"visible tag {rate(tot(p_rows, 'match'), tot(p_rows, 'n'))}")
    print(f"False visible tags on all N sets together: {rate(tot(n_rows, 'match'), tot(n_rows, 'n'))}")
    for r in rows:
        for v in r["visible"] if r["kind"] == "N" else []:
            print(f"  FALSE TAG {r['set']} {v['id']}: „{v['text']}” ← {v['publisher']} „{v['verdict_raw']}” „{v['claim']}” "
                  f"(cos {v['similarity']})")
        for c in r["conflicts"]:
            print(f"  conflict rule, {r['set']} {c['id']}: debunked {c['sim_debunked']} vs true {c['sim_true']}: „{c['true']}”")
    print(f"\n## NLI gate {settings.claim_match_soft} → {service.QUICK_NLI_GATE} on {gate['items']} items\n")
    print(f"NLI pairs: {gate['nli_pairs_old_gate']} → {gate['nli_pairs_new_gate']} "
          f"(saved {saved} = {100 * saved / max(1, gate['nli_pairs_old_gate']):.1f}%)")
    print(f"Items whose legacy output (risk, level, match, reason) differs between the two gates: "
          f"{len(gate['legacy_fields_differ'])} (items changed on purpose by the conflict rule: {gate['changed_by_conflict_rule']})")
    for d in gate["legacy_fields_differ"][:20]:
        print(f"  DIFF {d}")
    print(f"\n## Latency per batch of {BATCH} items (in process, this machine, {os.cpu_count()} CPUs)\n")
    print(f"old gate: p50 {lat['old']['p50_s']} s, p95 {lat['old']['p95_s']} s, mean {lat['old']['mean_s']} s "
          f"({lat['old']['n_batches']} batches)")
    print(f"new gate: p50 {lat['new']['p50_s']} s, p95 {lat['new']['p95_s']} s, mean {lat['new']['mean_s']} s "
          f"({lat['new']['n_batches']} batches)")
    if tier2:
        print("\n## Background (auto) tier-2 check on the same items — local corpus, no live search\n")
        print("| set | kind | n | tier 2 says false/misleading | of those tier 1 dropped (state none) | badge "
              "(decisive + cited source) | badge AND near-miss candidate | check p50 / p95 s |")
        print("|---|---|---|---|---|---|---|---|")
        for r in tier2:
            print(f"| {r['set']} | {r['kind']} | {r['n']} | {rate(r['tier2_false_or_misleading'], r['n'])} | "
                  f"{r['dropped_by_tier1']} | {rate(r['tier2_badge'], r['n'])} | {r['badge_and_near_miss_candidate']} | "
                  f"{r['latency_s_p50']} / {r['latency_s_p95']} |")
        f_all = sum(r["tier2_false_or_misleading"] for r in tier2)
        print(f"\nTier-2-relative recall: of {f_all} items tier 2 rates false/misleading, tier 1 dropped "
              f"{sum(r['dropped_by_tier1'] for r in tier2)} → kept {rate(f_all - sum(r['dropped_by_tier1'] for r in tier2), f_all)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gate_out = {k: v for k, v in gate.items() if not k.startswith("batch_s")}
    out.write_text(json.dumps({"args": vars(args), "index": INDEX.stats, "nli_gate": service.QUICK_NLI_GATE,
                               "conflict_margin": service.CONFLICT_MARGIN, "cpus": os.cpu_count(), "sets": rows,
                               "gate": gate_out, "latency_batch16": lat, "tier2": tier2}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\nJSON: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
