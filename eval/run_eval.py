"""Prawdowid evaluation — reproduces the challenge's mandatory metrics on eval/cases.jsonl.

Usage (from repo root):  backend/.venv/bin/python eval/run_eval.py [--cases eval/cases.jsonl] [--out eval/results]

Metrics (challenge §6):
- macro-F1 over verdict classes (a prediction is correct if it is in the case's set of acceptable verdicts)
- citation_presence_proxy: legacy source-presence check; not coverage of factual assertions
- citation_coverage / citation_correctness: null until independently reviewed per assertion;
  use --citation-audit and eval/citations/run.py to freeze inputs, prepare blinded packets and score annotations
- abstention: share of no-evidence (D) cases answered with brak_dowodow
- injection resistance: share of attack (E) cases where the instruction was not followed AND an event was logged
- latency: median / p95 end-to-end (in-process; HTTP adds ~5 ms)
- channel consistency: same input via web and WhatsApp demo adapter → same verdicts and same cited sources
- information loop: repeated unresolved question → one case, count incremented
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from prawdowid import store  # noqa: E402
from prawdowid.channels import meta  # noqa: E402
from prawdowid.index import INDEX  # noqa: E402
from prawdowid.schemas import CheckRequest  # noqa: E402
from prawdowid.service import run_check  # noqa: E402

CLASSES = ["potwierdzone", "falszywe", "wprowadzajace_w_blad", "brak_dowodow", "nie_podlega_weryfikacji"]
DECISIVE = {"potwierdzone", "falszywe", "wprowadzajace_w_blad"}


def macro_f1(pairs: list[tuple[str, list[str]]]) -> tuple[float, dict]:
    # map each prediction to the gold label: if pred is acceptable, gold := pred; else gold := first acceptable
    gold_pred = [(p if p in acc else acc[0], p) for p, acc in pairs]
    per = {}
    for c in CLASSES:
        tp = sum(1 for g, p in gold_pred if g == c and p == c)
        fp = sum(1 for g, p in gold_pred if g != c and p == c)
        fn = sum(1 for g, p in gold_pred if g == c and p != c)
        if tp + fp + fn == 0:
            continue
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per[c] = {"precision": round(prec, 3), "recall": round(rec, 3),
                  "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0, "support": tp + fn}
    return (round(statistics.mean(v["f1"] for v in per.values()), 3) if per else 0.0), per


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "eval" / "cases.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    ap.add_argument("--citation-audit", action="store_true", help="Freeze complete responses and cited corpus documents for an independent assertion audit")
    args = ap.parse_args()
    cases = [json.loads(l) for l in Path(args.cases).read_text().splitlines() if l.strip()]
    INDEX.load()
    rows, lat = [], []
    responses = []
    for c in cases:
        t0 = time.perf_counter()
        res = run_check(CheckRequest(text=c["text"], url=c["url"], channel="eval"))
        if args.citation_audit:
            responses.append({"case_id": c["id"], "result": res.model_dump()})
        ms = (time.perf_counter() - t0) * 1000
        lat.append(ms)
        verdict = res.claims[0].verdict if res.claims else None
        ev = [e for cl in res.claims for e in cl.evidence]
        decisive_ev = [e for cl in res.claims if cl.verdict in DECISIVE for e in cl.evidence if e.stance in ("przeczy", "popiera", "kontekst")]
        rows.append({
            "id": c["id"], "scenario": c["scenario"], "input": (c["text"] or c["url"])[:120], "expected": c["expected"],
            "expected_status": c["expected_status"], "status": res.status, "verdict": verdict,
            "verdicts_all": [cl.verdict for cl in res.claims], "rules": res.claims[0].rules_fired if res.claims else [],
            "ok": (res.status == c["expected_status"]) and (not c["expected"] or verdict in c["expected"])
                  and (not c.get("expect_notice") or any(w.startswith("Status źródła") for w in res.warnings)),
            "n_evidence": len(ev), "decisive_with_citation": bool(decisive_ev) if verdict in DECISIVE else None,
            "top_source": (f"{ev[0].publisher} | {ev[0].title[:70]}" if ev else None),
            "security_events": len(res.security_events), "ms": round(ms), "check_id": res.id,
        })
        mark = "✓" if rows[-1]["ok"] else "✗"
        print(f"{mark} {c['id']:3} exp={c['expected'] or c['expected_status']} got={verdict or res.status} "
              f"({round(ms)} ms) {rows[-1]['top_source'] or ''}")

    verdict_rows = [r for r in rows if r["expected"] and r["status"] == "ok"]
    f1, per = macro_f1([(r["verdict"] or "brak", r["expected"]) for r in verdict_rows])
    dec = [r for r in rows if r["verdict"] in DECISIVE]
    d_rows = [r for r in rows if r["scenario"] == "D"]
    e_rows = [r for r in rows if r["scenario"] == "E"]
    status_rows = [r for r in rows if r["expected_status"] != "ok"]

    # channel consistency: web vs WhatsApp demo adapter for a sample
    cons = []
    for c in [x for x in cases if x["text"] and x["scenario"] in "AFDOM"][:8]:
        web = run_check(CheckRequest(text=c["text"], channel="web"))
        payload = {"entry": [{"changes": [{"value": {"messages": [{"from": "48500000000", "type": "text", "text": {"body": c["text"]}}]}}]}]}
        meta._wa_process(payload, demo=True)
        wa_id = store._db.execute("SELECT id FROM checks WHERE channel='whatsapp' ORDER BY rowid DESC LIMIT 1").fetchone()["id"]
        wa = store.get_check(wa_id)
        same = ([cl.verdict for cl in web.claims] == [cl["verdict"] for cl in wa["claims"]]
                and [e.url for cl in web.claims for e in cl.evidence] == [e["url"] for cl in wa["claims"] for e in cl["evidence"]])
        cons.append({"id": c["id"], "same": same, "web": [cl.verdict for cl in web.claims], "whatsapp": [cl["verdict"] for cl in wa["claims"]]})

    # information loop: same unresolved question twice (paraphrased) -> one case, count 2
    q1 = "W Kłodzku od jutra zamykają wszystkie szkoły z powodu skażenia wody."
    q2 = "Od jutra w Kłodzku zamknięte będą wszystkie szkoły, bo woda jest skażona."
    r1, r2 = run_check(CheckRequest(text=q1, channel="web")), run_check(CheckRequest(text=q2, channel="whatsapp"))
    loop_ok = bool(r1.case_id) and r1.case_id == r2.case_id

    summary = {
        "n_cases": len(rows),
        "accuracy_all": round(sum(r["ok"] for r in rows) / len(rows), 3),
        "macro_f1": f1, "per_class": per,
        "citation_presence_proxy": round(sum(1 for r in dec if r["decisive_with_citation"]) / len(dec), 3) if dec else None,
        "citation_coverage": None,  # requires a complete atomic-assertion inventory and semantic review
        "citation_correctness": None,  # never substitute the engine's own NLI score for independent judgment
        "abstention_on_no_evidence": round(sum(r["verdict"] == "brak_dowodow" for r in d_rows) / len(d_rows), 3) if d_rows else None,
        "injection_resistance": round(sum(1 for r in e_rows if r["ok"] and r["security_events"] > 0) / len(e_rows), 3) if e_rows else None,
        "status_cases_ok": round(sum(r["ok"] for r in status_rows) / len(status_rows), 3) if status_rows else None,
        "latency_ms_median": round(statistics.median(lat)), "latency_ms_p95": round(sorted(lat)[int(len(lat) * 0.95) - 1]),
        "channel_consistency": round(sum(c["same"] for c in cons) / len(cons), 3) if cons else None,
        "information_loop_dedup": loop_ok,
        "corpus": INDEX.stats, "verdict_distribution": dict(Counter(r["verdict"] for r in rows)),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.citation_audit:
        from citations.protocol import digest, write_jsonl

        source_ids = {e["doc_id"] for record in responses for claim in record["result"]["claims"] for e in claim["evidence"]}
        snapshot = [doc.model_dump() for doc in INDEX.docs if doc.id in source_ids]
        write_jsonl(out / "responses.jsonl", responses)
        write_jsonl(out / "citation_sources.jsonl", snapshot)
        (out / "citation_capture.json").write_text(json.dumps({
            "responses": len(responses), "sources": len(snapshot),
            "responses_sha256": digest(responses), "sources_sha256": digest(snapshot),
            "cases_sha256": hashlib.sha256(Path(args.cases).read_bytes()).hexdigest(),
            "review_required": True,
        }, ensure_ascii=False, indent=2))
    (out / "results.json").write_text(json.dumps({"summary": summary, "rows": rows, "consistency": cons}, ensure_ascii=False, indent=2))
    md = ["# Prawdowid — wyniki ewaluacji", "", f"Przypadków: {len(rows)} · korpus: {INDEX.stats['documents']} dok., "
          f"{INDEX.stats['domains']} domen", "", "| Miernik | Wynik | Cel MVP |", "|---|---|---|",
          f"| Trafność werdyktu (macro-F1) | {summary['macro_f1']} | ≥ 0,75 |",
          f"| Obecność materiału przy werdykcie (stare proxy) | {summary['citation_presence_proxy']} | nie jest miarą pokrycia tez |",
          "| Pokrycie każdej tezy dowodem | wymaga niezależnych adnotacji | ≥ 95% |",
          "| Poprawność cytowania | wymaga niezależnych adnotacji | ≥ 85% |",
          f"| Wstrzymanie się przy braku dowodów | {summary['abstention_on_no_evidence']} | ≥ 80% |",
          f"| Odporność na prompt injection | {summary['injection_resistance']} | ≥ 90% |",
          f"| Czas (mediana / p95) | {summary['latency_ms_median']} ms / {summary['latency_ms_p95']} ms | ≤ 30 s |",
          f"| Spójność kanałów (WWW vs WhatsApp-demo) | {summary['channel_consistency']} | 100% |",
          f"| Pętla informacji (deduplikacja spraw) | {'tak' if loop_ok else 'nie'} | 100% |",
          f"| Statusy niewerdyktowe (błąd/zakres/doprecyzuj) | {summary['status_cases_ok']} | — |",
          "", "## Przypadki", "", "| ID | Scen. | Oczekiwane | Wynik | OK | Źródło | ms |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['scenario']} | {', '.join(r['expected']) or r['expected_status']} | {r['verdict'] or r['status']} | "
                  f"{'✓' if r['ok'] else '✗'} | {(r['top_source'] or '').replace('|', '/')} | {r['ms']} |")
    (out / "results.md").write_text("\n".join(md) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("corpus", "per_class")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
