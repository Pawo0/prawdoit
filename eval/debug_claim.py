"""Show retrieval candidates, similarities, NLI scores and the decision for given claims (tuning aid)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from prawdowid.index import INDEX
from prawdowid import engine
from prawdowid.claims import extract_claims

INDEX.load()
orig = engine._decide
def spy(claim, support, refute, misleading, unverif, evidence, high_risk):
    for name, L in (("SUP", support), ("REF", refute), ("MIS", misleading), ("UNV", unverif)):
        for c in L:
            d = INDEX.docs[c.doc_idx]
            print(f"   {name} {d.publisher[:18]:18} ccos={c.claim_cos:.3f} fcos={c.frag_cos:.3f} num={c.numeric} "
                  f"nli={tuple(round(x,2) for x in (c.nli.entail,c.nli.contra)) if c.nli else None} "
                  f"nlic={tuple(round(x,2) for x in (c.nli_claim.entail,c.nli_claim.contra)) if c.nli_claim else None} | {(d.claim or d.title)[:80]}")
    return orig(claim, support, refute, misleading, unverif, evidence, high_risk)
engine._decide = spy
orig_eq = engine.INDEX.match_claims
def mc(q_emb, query, k=8):
    r = orig_eq(q_emb, query, k)
    for di, cos in r[:5]:
        d = INDEX.docs[di]; print(f"   match {cos:.3f} {d.publisher[:14]:14} [{d.verdict}] {(d.claim or d.title)[:90]}")
    return r
engine.INDEX.match_claims = mc
for q in sys.argv[1:]:
    t = {}
    t0 = time.time()
    for c in extract_claims(q):
        print(f"\n### {c.text} [{c.kind}] q='{c.query}'")
        r = engine.verify_claim(c, t)
        print(f" => {r.verdict} {r.strength_label} rules={r.rules_fired} reasons={r.reason_codes}")
    print(f" timings={ {k: round(v) for k, v in t.items()} } total={time.time()-t0:.1f}s")
