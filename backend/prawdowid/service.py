"""Channel-agnostic verification service. Web, extension, WhatsApp/Messenger/Discord adapters all call run_check /
quick_score, so the substantive result is identical regardless of channel (challenge requirement G)."""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import time
from collections import OrderedDict
from urllib.parse import urlparse
from datetime import date, datetime, timezone

from . import llm, store, websearch
from .claims import extract_claims
from .config import settings
from .engine import same_claim, verify_claim
from .fetch import FetchError, fetch_url
from .index import INDEX
from .nli import NLI_MODEL
from .schemas import CheckRequest, CheckResult, QuickMatch, QuickRequest, QuickResult
from .security import ResolveError, UnsafeURL, neutralize, scan
from .signals import sprawdz_signals
from .schemas import RULES_VERSION
from .textutil import mask_pii, normalize_ws, short, split_sentences, tokens

log = logging.getLogger("prawdowid.service")

HIGH_RISK = re.compile(
    r"\b(ewakuac\w*|wojn\w*|mobilizac\w*|pob[oó]r\w*|atak\w*|zamach\w*|skażon\w*|zatru\w*|alarm\w*|schron\w*|blackout\w*|"
    r"epidemi\w*|jodek|jod\b|upadł\w* bank\w*|wybor\w*|głosowani\w*|referend\w*|rakiet\w*|dron\w*|sabota\w*)",
    re.IGNORECASE,
)

_NO_TEXT = ("Nie udało się odczytać treści strony (strona jest pusta albo blokuje automatyczny dostęp — takich "
            "zabezpieczeń nie obchodzimy).")

SUMMARY = {
    "falszywe": "Źródła przeczą tej informacji",
    "wprowadzajace_w_blad": "Wprowadza w błąd",
    "potwierdzone": "Potwierdzone w źródłach",
    "brak_dowodow": "Brak wystarczających dowodów",
    "nie_podlega_weryfikacji": "Opinia / nie podlega weryfikacji",
}


def engine_info() -> dict:
    return {
        "embed_model": settings.embed_model,
        "nli_model": NLI_MODEL.name,
        "llm": settings.llm_model if llm.enabled() else None,
        "corpus_documents": INDEX.stats.get("documents"),
        "corpus_loaded_at": INDEX.loaded_at,
        "rules_version": RULES_VERSION,
        "processing": ("lokalnie (serwer własny)" + ("" if not llm.enabled() else f"; LLM: {settings.llm_base_url}")
                       + ("; wyszukiwanie na żywo: tylko zaufane domeny z rejestru źródeł"
                          + (" + Google Fact Check API" if os.environ.get("PRAWDOWID_GOOGLE_FACTCHECK_KEY") else "")
                          if websearch.live_enabled() else "")),
    }


def cost_estimate(res: CheckResult) -> dict:
    """Estimated marginal cost of one answer (zł): wall time as CPU-time proxy × rate + LLM tokens × rate.
    External APIs used here are free within their quotas (Google Fact Check, site search); they are counted, not priced."""
    cpu = res.timings_ms.get("total_ms", 0) / 1000 * settings.cost_pln_per_cpu_s
    tokens = sum(int(u.get("total_tokens") or 0) for u in res.engine.get("llm_calls", []))
    llm_pln = tokens / 1000 * settings.cost_pln_per_1k_llm_tokens
    ls = res.live_search
    return {"pln": round(cpu + llm_pln, 6), "cpu_pln": round(cpu, 6), "llm_tokens": tokens, "llm_pln": round(llm_pln, 6),
            "external_calls": len(ls.steps) if ls else 0}


def run_check(req: CheckRequest, progress=None) -> CheckResult:
    """progress: optional callback(stage, stage_label) — used by the async job API (jobs.py)."""
    t_start = time.perf_counter()
    websearch.emit(progress, "analiza")
    timings: dict[str, float] = {}
    cid = store.new_id()
    res = CheckResult(id=cid, created_at=store.now(), channel=req.channel, status="ok",
                      input_kind="url" if (req.url and not req.text) else "text", input_excerpt="",
                      engine=engine_info())
    text = normalize_ws(req.text or "")[: settings.max_input_chars]
    url = (req.url or "").strip()
    # a bare URL pasted as text
    if not url and re.fullmatch(r"https?://\S+", text):
        url, text = text, ""
        res.input_kind = "url"

    if url:
        t0 = time.perf_counter()
        websearch.emit(progress, "pobieranie")
        try:
            page = fetch_url(url)
            res.url_meta = {k: page[k] for k in ("url", "domain", "title", "sitename", "date", "author")}
            if len(page.get("text") or "") < 80:  # e.g. a bot-protection stub page
                raise FetchError(_NO_TEXT)
            res.security_events += scan(page["text"], "treść pobranej strony")
            text = normalize_ws(f"{page['title']}. {page['text']}" if page["title"] else page["text"])
            if page.get("date"):
                try:
                    age = (datetime.now(timezone.utc).date() - date.fromisoformat(page["date"][:10])).days
                    if age > settings.stale_days:
                        res.warnings.append(f"Materiał archiwalny: strona opublikowana {page['date']} "
                                            f"({age // 365} l. temu). Sprawdź, czy nie jest przedstawiana jako bieżąca.")
                except ValueError:
                    pass
        except UnsafeURL as e:
            res.status, res.status_message = "poza_zakresem", str(e)
        except (FetchError, ResolveError) as e:
            res.status = "blad_techniczny"
            res.status_message = f"{e} To błąd techniczny, a nie ocena treści. Możesz wkleić tekst artykułu."
            store.log_error(cid, "fetch", str(e))
        timings["fetch_ms"] = (time.perf_counter() - t0) * 1000

    # a message with a link ("Czy X? Sprawdź też tę stronę: https://…"): the question stays the claim source, the page
    # is fetched with the same SSRF guard, scanned for injected instructions (scenario E) and used for claims only
    # when the message itself has none. A failed fetch is a notice, never a verdict and never a failed check.
    page_text = ""
    links = [] if url else re.findall(r"https?://[^\s<>\"'„”]+", text)
    if links:
        link = links[0].rstrip(".,;:!?)]}")
        t0 = time.perf_counter()
        websearch.emit(progress, "pobieranie")
        try:
            page = fetch_url(link)
            res.url_meta = {k: page[k] for k in ("url", "domain", "title", "sitename", "date", "author")}
            if len(page.get("text") or "") < 80:  # e.g. a bot-protection stub page
                raise FetchError(_NO_TEXT)
            res.security_events += scan(page["text"], "treść strony podanej w wiadomości")
            page_text = normalize_ws(f"{page['title']}. {page['text']}" if page["title"] else page["text"])
        except UnsafeURL as e:
            res.warnings.append(f"Nie pobrano strony z wiadomości: {e} Sprawdziłem tylko treść wiadomości.")
        except (FetchError, ResolveError) as e:
            res.warnings.append(f"Strona z wiadomości: {e} To błąd techniczny, a nie ocena treści — sprawdziłem "
                                "tylko treść wiadomości.")
            store.log_error(cid, "fetch", str(e))
        timings["fetch_ms"] = (time.perf_counter() - t0) * 1000

    res.input_excerpt = short(mask_pii(text or url), 500)
    domains = {urlparse(u).hostname or "" for u in re.findall(r"https?://\S+", f"{url} {req.text or ''}")}
    res.warnings += source_status_notices({d.removeprefix("www.") for d in domains if d})
    if res.status == "ok":
        res.security_events += scan(req.text or "", "wiadomość użytkownika")
        if res.security_events:
            res.warnings.append("W treści wykryto fragmenty przypominające polecenia dla systemu (np. „zignoruj "
                                "instrukcje”). Potraktowaliśmy je jako zwykły tekst — nie wpływają na ocenę. "
                                "Zdarzenie zostało zapisane.")
        clean = neutralize(re.sub(r"https?://\S+", " ", text) if page_text else text)
        claims = extract_claims(clean, max_claims=3)
        if page_text and not any(len(c.query.split()) >= 3 for c in claims):
            clean = neutralize(page_text)  # "Co z tym artykułem? <link>": the claims are on the linked page
            claims = extract_claims(clean, max_claims=3)
        vocab = INDEX.bm25.postings if INDEX.bm25 else {}
        known = [t for t in tokens(clean) if t in vocab and not t[0].isdigit()]
        if not claims or not any(len(c.query.split()) >= 3 for c in claims) or len(set(known)) < 2:
            res.status = "doprecyzuj"
            res.status_message = ("Nie rozpoznaliśmy twierdzenia, które da się sprawdzić. Napisz jedno konkretne zdanie, "
                                  "np. „Od 2026 r. emerytury w Polsce zostaną obniżone o 20%”, albo wklej link.")
        else:
            live = websearch.LiveStage(cid, progress)  # Google Fact Check + trusted-domain fallback; never raises
            try:
                websearch.emit(progress, "baza")
                live.start_google(claims)
                res.claims = [verify_claim(c, timings) for c in claims]
            except Exception as e:  # noqa: BLE001
                log.exception("engine failure")
                store.log_error(cid, "engine", repr(e))
                res.status = "blad_techniczny"
                res.status_message = "Wystąpił błąd techniczny podczas analizy. To nie jest ocena treści — spróbuj ponownie."
                res.claims = []
            if res.claims:
                res.claims = live.finish(claims, res.claims, timings)
                res.live_search = live.info()
                res.security_events += live.events
                res.warnings += live.warnings

    # optional LLM rephrasing of already-decided explanations
    if res.claims and llm.enabled():
        t0 = time.perf_counter()
        for c in res.claims:
            if c.verdict in ("falszywe", "potwierdzone", "wprowadzajace_w_blad"):
                txt, usage = llm.simplify(c.explanation, c.verdict_label)
                res.engine.setdefault("llm_calls", []).append(usage)
                if txt:
                    c.explanation = txt
        timings["llm_ms"] = (time.perf_counter() - t0) * 1000

    # claim decomposition overview + SPRAWDŹ educational signals (never affect verdicts)
    if res.claims:
        kinds = [c.kind for c in res.claims]
        nf, no = kinds.count("fakt"), len(kinds) - kinds.count("fakt")
        res.claims_overview = (f"Znaleźliśmy {len(kinds)} twierdzeni{'e' if len(kinds) == 1 else 'a'} do sprawdzenia: "
                               f"{nf} faktyczn{'e' if nf == 1 else 'e'}" + (f", {no} opini{'a' if no == 1 else 'e'}/prognoz{'a' if no == 1 else 'y'}" if no else "") + ".")
        res.signals = sprawdz_signals(text, kinds, res.url_meta, any(c.context_type == "NIEAKTUALNE" for c in res.claims)
                                      or any(w.startswith("Materiał archiwalny") for w in res.warnings),
                                      any(c.evidence for c in res.claims))

    # summary
    if res.claims:
        vs = [c.verdict for c in res.claims]
        if len(vs) == 1:
            res.summary = SUMMARY[vs[0]]
        else:
            parts = [f"{SUMMARY[v]}: {vs.count(v)}" for v in dict.fromkeys(vs)]
            res.summary = f"Sprawdzono {len(vs)} twierdzenia — " + "; ".join(parts)

    # information loop: unresolved, check-worthy -> moderator case (grouped with similar ones)
    unresolved = [c for c in res.claims if (c.verdict == "brak_dowodow" and c.kind == "fakt")
                  or any(r.startswith("HR:") for r in c.rules_fired)]
    if unresolved and res.status == "ok":
        c = unresolved[0]
        try:
            emb = INDEX.encode_query([c.claim])[0]
            case_id, count = store.upsert_case(cid, mask_pii(c.claim), emb, req.channel, c.high_risk)
            res.case_id = case_id
            res.case_status = (f"Sprawa {case_id} została dodana do kolejki analityka (podobnych zgłoszeń: {count}). "
                               "Analityk zobaczy ją w panelu; nie wysłano żadnych powiadomień poza tę kolejkę.")
        except Exception as e:  # noqa: BLE001
            store.log_error(cid, "cases", repr(e))

    # short answers (deterministic, from the fields above) + trusted pages for the explanation page
    websearch.emit(progress, "odpowiedz")
    try:
        from . import answer, resources

        answer.finalize(res)
        res.resources = resources.resources_for(res)
    except Exception as e:  # noqa: BLE001 — presentation layer must never turn into a failed check
        log.exception("short answer failed")
        store.log_error(cid, "answer", repr(e))

    timings["total_ms"] = (time.perf_counter() - t_start) * 1000
    res.timings_ms = {k: round(v, 1) for k, v in timings.items()}
    res.engine["cost_estimate"] = cost_estimate(res)
    try:
        store.save_check(res.model_dump(), res.input_excerpt, req.session)
    except Exception as e:  # noqa: BLE001
        log.warning("audit save failed: %s", e)
    return res


# ------------------------------------------------------------------ source-status notices (scenario I)
def _watchlist() -> list[dict]:
    import json

    p = settings.root / "data" / "watchlist.json"
    try:
        return json.loads(p.read_text())["entries"] if p.exists() else []
    except (ValueError, KeyError):
        return []


def source_status_notices(domains: set[str]) -> list[str]:
    out = []
    for e in _watchlist():
        if any(d == e["pattern"] or d.endswith("." + e["pattern"]) for d in domains):
            out.append(f"Status źródła: domena pojawia się w katalogu incydentów jako część „{e['label']}” "
                       f"({e['publisher']}, {e['date']}: {e['source_url']}). To informacja o kanale, a nie o tej treści — "
                       "ocena poniżej opiera się wyłącznie na dowodach dotyczących treści.")
    return out


# ------------------------------------------------------------------ extension fast path
_QCACHE: OrderedDict[str, QuickResult] = OrderedDict()
RISK_W = {"false": 1.0, "misleading": 0.85, "mixed": 0.7}


def _segments(text: str) -> list[str]:
    text = normalize_ws(text)[:2000]
    sents = [s for s in split_sentences(text) if 30 <= len(s) <= 400][:8]
    segs = sents + ([text[:400]] if len(text) > 40 else [])
    return list(dict.fromkeys(segs))


def quick_score(req: QuickRequest) -> list[QuickResult]:
    out: dict[str, QuickResult] = {}
    todo: list[tuple[str, str, list[str]]] = []
    for it in req.items:
        h = hashlib.sha1(normalize_ws(it.text).encode()).hexdigest()
        if h in _QCACHE:
            out[it.id] = _QCACHE[h].model_copy(update={"id": it.id})
            continue
        segs = _segments(it.text)
        if not segs:
            out[it.id] = QuickResult(id=it.id, risk=0.0, level="brak", reason="za krótki tekst")
            continue
        todo.append((it.id, h, segs))
    if todo:
        flat = [s for _, _, segs in todo for s in segs]
        embs = INDEX.encode_query(flat)
        doc_idx, sims = INDEX.match_claims_batch(embs)
        pos = 0
        pending_nli: list[tuple[str, str, int, float, str]] = []
        for item_id, h, segs in todo:
            best = None
            for j in range(len(segs)):
                di, sim = int(doc_idx[pos + j]), float(sims[pos + j])
                d = INDEX.docs[di]
                if d.verdict in RISK_W and (best is None or sim > best[1]):
                    best = (di, sim, segs[j])
            pos += len(segs)
            if best and best[1] >= settings.claim_match_soft:
                pending_nli.append((item_id, h, best[0], best[1], best[2]))
            else:
                r = QuickResult(id=item_id, risk=0.0, level="brak", reason="brak zbieżności ze zweryfikowanymi fałszami")
                out[item_id] = r
                _cache(h, r)
        fwd = NLI_MODEL.score([(seg, INDEX.docs[di].claim or INDEX.docs[di].title) for _, _, di, _, seg in pending_nli])
        # reverse direction only where the forward pass hints at a contradiction (negation check) — saves CPU
        need = [i for i, f in enumerate(fwd) if f.contra >= 0.3]
        rev_scores = NLI_MODEL.score([(INDEX.docs[pending_nli[i][2]].claim or INDEX.docs[pending_nli[i][2]].title,
                                       pending_nli[i][4]) for i in need])
        rev = list(fwd)
        for i, r_ in zip(need, rev_scores):
            rev[i] = r_
        for (item_id, h, di, sim, seg), s, s_rev in zip(pending_nli, fwd, rev):
            d = INDEX.docs[di]
            # P(content repeats the debunked claim): similarity (calibrated logistic) x does the post ASSERT it (NLI)
            p_match = 1 / (1 + math.exp(-(sim - 0.78) * 25))
            decision = same_claim(sim, s, s_rev, d.claim or d.title, seg, d.source_type)
            if decision is not True:
                agree = 0.0  # opposite (e.g. the post debunks it) or merely related — never flag
            else:
                agree = 0.30 + 0.70 * s.entail
            risk = round(p_match * agree * RISK_W[d.verdict], 3)
            level = "wysokie" if risk >= 0.6 else "srednie" if risk >= 0.35 else "brak"
            r = QuickResult(
                id=item_id, risk=risk, level=level,
                match=QuickMatch(claim=d.claim or d.title, verdict=d.verdict, verdict_raw=d.verdict_raw,
                                 publisher=d.publisher, url=d.url, title=d.title, published_at=d.published_at,
                                 similarity=round(sim, 3), sentence=seg),
                reason=f"Treść jest zbieżna z twierdzeniem ocenionym przez {d.publisher} jako „{d.verdict_raw}”.",
            )
            out[item_id] = r
            _cache(h, r)
    return [out[it.id] for it in req.items]


def _cache(h: str, r: QuickResult) -> None:
    _QCACHE[h] = r
    if len(_QCACHE) > 5000:
        _QCACHE.popitem(last=False)
