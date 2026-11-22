"""Channel-agnostic verification service. Web, extension, WhatsApp/Messenger/Discord adapters all call run_check /
quick_score, so the substantive result is identical regardless of channel (challenge requirement G)."""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading
import time
from collections import OrderedDict
from urllib.parse import urlparse
from datetime import date, datetime, timezone

from . import llm, ocr, provenance, store, websearch
from .claims import extract_claims
from .config import settings
from .engine import same_claim, verify_claim
from .fetch import FetchError, fetch_url
from .index import INDEX
from .nli import NLI_MODEL
from .schemas import CheckRequest, CheckResult, QuickConflict, QuickMatch, QuickRequest, QuickResult
from .security import ResolveError, UnsafeURL, neutralize, scan
from .signals import sprawdz_signals
from .schemas import RULES_VERSION
from .textutil import HIGH_RISK, is_task_request, mask_pii, normalize_ws, short, split_sentences, tokens

log = logging.getLogger("prawdowid.service")

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
        "llm_status": ("skonfigurowany — tylko upraszcza język gotowego wyjaśnienia" if llm.enabled()
                       else "nieskonfigurowany — wyjaśnienia z szablonów"),
        "corpus_documents": INDEX.stats.get("documents"),
        "corpus_loaded_at": INDEX.loaded_at,
        "rules_version": RULES_VERSION,
        "processing": ("lokalnie (serwer własny)" + ("" if not llm.enabled() else f"; LLM: {settings.llm_base_url}")
                       + ("; wyszukiwanie na żywo: tylko zaufane domeny z rejestru źródeł"
                          + (" + Google Fact Check API" if os.environ.get("PRAWDOWID_GOOGLE_FACTCHECK_KEY")
                             else " (Google Fact Check nieaktywne: brak klucza API)")
                          if websearch.live_enabled() else "; wyszukiwanie na żywo wyłączone")),
    }


def cost_estimate(res: CheckResult) -> dict:
    """Estimated marginal cost of one answer (zł): wall time as CPU-time proxy × rate + LLM tokens × rate.
    External APIs used here are free within their quotas (Google Fact Check, site search); they are counted, not priced."""
    cpu = res.timings_ms.get("total_ms", 0) / 1000 * settings.cost_pln_per_cpu_s
    tokens = sum(int(u.get("total_tokens") or 0) for u in res.engine.get("llm_calls", []))
    llm_pln = tokens / 1000 * settings.cost_pln_per_1k_llm_tokens
    ls = res.live_search
    return {"pln": round(cpu + llm_pln, 6), "cpu_pln": round(cpu, 6), "llm_tokens": tokens, "llm_pln": round(llm_pln, 6),
            "external_calls": sum(s.get("status") != "nieaktywne" for s in ls.steps) if ls else 0}


TASK_MESSAGE = ("To prośba o napisanie lub przetłumaczenie tekstu, a nie informacja do sprawdzenia, więc nie wydajemy "
                "werdyktu. Prawdowid sprawdza twierdzenia o faktach — wklej wiadomość lub zdanie, które chcesz "
                "zweryfikować.")
OCR_NOTICE = ("Tekst odczytałem automatycznie z obrazu (OCR) — mogą w nim być błędy odczytu. "
              "Data na zrzucie ekranu jest tylko częścią obrazu i nie dowodzi, kiedy tekst naprawdę opublikowano.")


def _read_image(req: CheckRequest, res: CheckResult, cid: str, timings: dict) -> str:
    """Screenshot -> text (ocr.py), "" on failure. Neither the image nor the raw text is stored (the audit row keeps
    the masked excerpt as for any text); a failure is a technical notice, never a verdict."""
    t0 = time.perf_counter()
    res.input_kind = "image"
    try:
        text = ocr.read_text(ocr.decode_b64(req.image_b64 or ""))
    except ocr.OcrUnavailable as e:
        log.warning("OCR unavailable: %s", e)
        res.status = "blad_techniczny"
        res.status_message = ("Odczyt tekstu z obrazu nie jest dostępny na tym serwerze. To błąd techniczny, a nie "
                              "ocena treści. Wklej tekst ze zrzutu ekranu.")
        store.log_error(cid, "ocr", str(e))
        return ""
    except ocr.OcrError as e:
        res.status = "blad_techniczny"
        res.status_message = f"Nie udało się odczytać obrazu: {e}. To nie jest ocena treści. Wklej tekst ze zrzutu."
        return ""
    finally:
        timings["ocr_ms"] = (time.perf_counter() - t0) * 1000
    if len(text) < 10:
        res.status = "doprecyzuj"
        res.status_message = "Nie odczytałem tekstu z obrazu. Wklej tekst ze zrzutu ekranu albo przyślij wyraźniejszy obraz."
        return ""
    res.warnings.insert(0, OCR_NOTICE)
    return text


def _masked(page: dict) -> dict:
    """A fetched page goes through the same PII masking as the user's text (claims may come from it)."""
    return {**page, "title": mask_pii(page.get("title") or ""), "text": mask_pii(page.get("text") or "")}


def run_check(req: CheckRequest, progress=None) -> CheckResult:
    """progress: optional callback(stage, stage_label) — used by the async job API (jobs.py).

    mode="auto" (a background check the extension router starts for a `candidate` the user did not ask about) runs
    the same claim extraction, retrieval and rules on the LOCAL corpus only and leaves no trace of the text:
    no URL/link fetch, no live search (it would send the claim to third-party sites), no LLM call, no moderator case,
    and the audit row holds a SHA-256 of the text instead of the text (store.save_auto_check). The returned result
    still carries the claims and their evidence, so the caller can show the source."""
    t_start = time.perf_counter()
    websearch.emit(progress, "analiza")
    timings: dict[str, float] = {}
    cid = store.new_id()
    auto = req.mode == "auto"
    channel = f"{req.channel[:20]}-auto" if auto and not req.channel.endswith("-auto") else req.channel
    res = CheckResult(id=cid, created_at=store.now(), channel=channel, status="ok",
                      input_kind="url" if (req.url and not req.text) else "text", input_excerpt="",
                      engine=engine_info(), mode=req.mode)
    text = normalize_ws(req.text or "")[: settings.max_input_chars]
    ocr_text = _read_image(req, res, cid, timings) if (req.image_b64 and not auto) else ""
    if ocr_text:  # the question that came with the screenshot first, then what the image says
        text = normalize_ws(f"{text}\n{ocr_text}")[: settings.max_input_chars]
    # Direct identifiers (PESEL, ID card / passport, phone, bank account, personal e-mail) are masked here, once,
    # before claim extraction: retrieval, the live-search queries, the optional LLM, the audit row (result_json) and the
    # moderator queue only ever see the placeholders. Names, places, dates, amounts and statistics are not masked
    # (policy: textutil.mask_pii, docs/COMPLIANCE.md). URLs stay as typed so links can be fetched.
    text, ocr_text = mask_pii(text), mask_pii(ocr_text)
    user_text = mask_pii(req.text or "")
    unavailable: list[str] = []  # dependencies that did not run (config, key, outage) — engine.unavailable, shown in UI
    url = "" if auto else (req.url or "").strip()  # auto: text only, nothing is fetched on the user's behalf
    # a bare URL pasted as text
    if not url and not auto and re.fullmatch(r"https?://\S+", text):
        url, text = text, ""
        res.input_kind = "url"

    if url:
        t0 = time.perf_counter()
        websearch.emit(progress, "pobieranie")
        try:
            page = _masked(fetch_url(url))
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

    # a message with a link ("Czy X? Zobacz ten artykuł: https://…"): the question stays the claim source, the page
    # is fetched with the same SSRF guard, scanned for injected instructions (scenario E) and used for claims only
    # when the message itself has none. A failed fetch is a notice, never a verdict and never a failed check.
    page_text = ""
    links = [] if (url or auto) else re.findall(r"https?://[^\s<>\"'„”]+", text)
    if links:
        link = links[0].rstrip(".,;:!?)]}")
        t0 = time.perf_counter()
        websearch.emit(progress, "pobieranie")
        try:
            page = _masked(fetch_url(link))
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
    domains = {urlparse(u).hostname or "" for u in re.findall(r"https?://\S+", f"{url} {user_text}")}
    res.warnings += source_status_notices({d.removeprefix("www.") for d in domains if d})
    if res.status == "ok":
        res.security_events += scan(user_text, "wiadomość użytkownika")
        if ocr_text:
            res.security_events += scan(ocr_text, "tekst odczytany z obrazu")
        if res.security_events:
            res.warnings.append("W treści wykryto fragmenty przypominające polecenia dla systemu (np. „zignoruj "
                                "instrukcje”). Potraktowaliśmy je jako zwykły tekst — nie wpływają na ocenę. "
                                "Zdarzenie zostało zapisane.")
        clean = neutralize(re.sub(r"https?://\S+", " ", text) if page_text else text)
        task = is_task_request(clean)  # "napisz wiersz…", "przetłumacz…": a task, not information to check
        claims = [] if task else extract_claims(clean, max_claims=3)
        if page_text and not task and not any(len(c.query.split()) >= 3 for c in claims):
            clean = neutralize(page_text)  # "Co z tym artykułem? <link>": the claims are on the linked page
            claims = extract_claims(clean, max_claims=3)
        vocab = INDEX.bm25.postings if INDEX.bm25 else {}
        known = [t for t in tokens(clean) if t in vocab and not t[0].isdigit()]
        if task:
            res.status = "poza_zakresem"
            res.status_message = TASK_MESSAGE
        elif not claims or not any(len(c.query.split()) >= 3 for c in claims) or len(set(known)) < 2:
            res.status = "doprecyzuj"
            res.status_message = ("Nie rozpoznaliśmy twierdzenia, które da się sprawdzić. Napisz jedno konkretne zdanie, "
                                  "np. „Od 2026 r. emerytury w Polsce zostaną obniżone o 20%”, albo wklej link.")
        elif page_text and res.url_meta and provenance.asks_same_item(user_text):
            # "Czy ten artykuł to ten sam tekst, który oceniał <checker>? <link>": a question about the identity
            # of the linked item, answered by comparing its headline and date with the fact-check records (scenario I)
            try:
                res.claims = [provenance.check_linked_item(claims[0].text, res.url_meta)]
            except Exception as e:  # noqa: BLE001
                log.exception("provenance check failure")
                store.log_error(cid, "engine", repr(e))
                res.status = "blad_techniczny"
                res.status_message = "Wystąpił błąd techniczny podczas analizy. To nie jest ocena treści — spróbuj ponownie."
        else:
            live = websearch.LiveStage(cid, progress)  # Google Fact Check + trusted-domain fallback; never raises
            if auto or req.live_search is False:
                live.enabled = False  # start_google() and finish() are then no-ops: local corpus only
                unavailable.append("Wyszukiwanie na żywo nie było używane w tym sprawdzeniu ("
                                   + ("sprawdzenie w tle z wtyczki" if auto else "wyłączone w zapytaniu")
                                   + ") — sprawdzono tylko lokalną bazę źródeł.")
            elif not live.enabled:
                unavailable.append(websearch.NOTICE_LIVE_OFF)
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
                unavailable += live.inactive()

    # optional LLM rephrasing of already-decided explanations
    if res.claims and llm.enabled() and not auto:  # auto: the text is not sent to the LLM endpoint
        t0 = time.perf_counter()
        for c in res.claims:
            if c.verdict in ("falszywe", "potwierdzone", "wprowadzajace_w_blad"):
                txt, usage = llm.simplify(c.explanation, c.verdict_label)
                res.engine.setdefault("llm_calls", []).append(usage)
                if txt:
                    c.explanation = txt
        calls = res.engine.get("llm_calls", [])
        errors = sorted({u["error"] for u in calls if u.get("error")})
        if errors:  # an outage is said out loud; the deterministic explanation stays and the verdict is unchanged
            unavailable.append(f"Model językowy był niedostępny (błąd techniczny: {', '.join(errors)}) — wyjaśnienie "
                               "pochodzi z szablonu, werdykt bez zmian.")
            store.log_error(cid, "llm", ", ".join(errors))
        if any(u.get("rejected") for u in calls):
            unavailable.append("Tekst modelu językowego odrzucono w walidacji (np. nowe liczby lub linki) — "
                               "wyjaśnienie pochodzi z szablonu.")
        timings["llm_ms"] = (time.perf_counter() - t0) * 1000
    if unavailable:
        res.engine["unavailable"] = list(dict.fromkeys(unavailable))

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
    if unresolved and res.status == "ok" and not auto:  # auto: passive browsing must not fill the analyst queue
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
        if auto:
            store.save_auto_check(res.model_dump(), hashlib.sha256(text.encode()).hexdigest())
        else:
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


# ------------------------------------------------------------------ extension fast path = tier-1 ROUTER
# Tier 1 does not judge content. It answers one question per item — "does this text repeat a claim that a named
# fact-checker already rated false / misleading?" — and routes:
#   match      shown by the extension, always with publisher, rating, date and link (QuickMatch);
#   candidate  never shown; the extension may send the best few to tier 2 in the background (run_check mode="auto");
#   none       nothing.
# research/09_architecture_two_tier_and_containers.md §3.4–3.5.
_QCACHE: OrderedDict[str, QuickResult] = OrderedDict()
RISK_W = {"false": 1.0, "misleading": 0.85, "mixed": 0.7}
# engine.same_claim cannot return True below cosine 0.80 (nor False below 0.85), so NLI below this gate cannot change
# the result. backend/tests/test_router_quick.py fails if the engine rule moves under the gate.
QUICK_NLI_GATE = 0.80
# A claim rated TRUE that is this close (cosine) to the debunked one suppresses the tag: fact-checkers rated two
# nearly identical statements differently, so a similarity match cannot say which one the text repeats.
CONFLICT_MARGIN = 0.03
_NO_MATCH = "brak zbieżności ze zweryfikowanymi fałszami"
_QUICK_SEM = threading.BoundedSemaphore(settings.quick_concurrency)


class QuickBusy(RuntimeError):
    """All quick-path inference slots are taken. The API answers 503 + Retry-After; the client renders nothing."""

    retry_after = 2


def _segments(text: str) -> list[str]:
    text = normalize_ws(text)[:2000]
    sents = [s for s in split_sentences(text) if 30 <= len(s) <= 400][:8]
    segs = sents + ([text[:400]] if len(text) > 40 else [])
    return list(dict.fromkeys(segs))


def _checkable(text: str) -> float | None:
    """Score (0..1) of the best factual sentence tier 2 could check, or None. Uses tier 2's own claim extraction, so
    "candidate" means "run_check would look this up" rather than a separate notion of suspicious content."""
    facts = [c for c in extract_claims(normalize_ws(text)[:2000], max_claims=3)
             if c.kind == "fakt" and len(c.query.split()) >= 3]
    return max(c.score for c in facts) if facts else None


def _route(r: QuickResult, text: str, sim: float | None, near: bool) -> QuickResult:
    """Fill state / priority / reasons of a result that is not a visible match."""
    score = _checkable(text)
    reasons = list(r.reasons)
    if near and "CONFLICTING_RATINGS" not in reasons:
        reasons.append("NEAR_MISS")
    high_risk = bool(HIGH_RISK.search(text))
    if high_risk and (near or score is not None):
        reasons.append("HIGH_RISK_TOPIC")
    if score is not None:
        reasons.append("FACTUAL_SENTENCE")
    # order for the automatic checks: near miss to a rated claim > high-risk topic > check-worthiness
    if near:
        priority = 0.6 + 0.4 * max(0.0, min(1.0, ((sim or 0.0) - settings.claim_match_soft) / 0.16))
    elif score is None:
        priority = 0.0
    elif high_risk:
        priority = 0.4 + 0.2 * score
    else:
        priority = 0.4 * score
    r.state = "candidate" if (near or score is not None) else "none"
    r.priority, r.reasons = round(priority, 3), reasons
    return r


def quick_score(req: QuickRequest, *, nli_gate: float = QUICK_NLI_GATE, suppress_conflicts: bool = True,
                use_cache: bool = True) -> list[QuickResult]:
    """The keyword switches exist for eval/measure_router.py (before/after comparison); the API uses the defaults."""
    out: dict[str, QuickResult] = {}
    todo: list[tuple[str, str, str, list[str]]] = []
    stamp = INDEX.loaded_at or ""  # a cached result is valid for one index load
    for it in req.items:
        h = hashlib.sha1(f"{stamp}\n{normalize_ws(it.text)}".encode()).hexdigest()
        if use_cache and h in _QCACHE:
            out[it.id] = _QCACHE[h].model_copy(update={"id": it.id})
            continue
        segs = _segments(it.text)
        if not segs:
            out[it.id] = QuickResult(id=it.id, risk=0.0, level="brak", reason="za krótki tekst")
            continue
        todo.append((it.id, h, it.text, segs))
    if todo:
        # One batch infers at a time (settings.quick_concurrency): background page scanning must not starve a
        # manual check running in another thread. The wait is bounded, so worker threads are never parked for long.
        if not _QUICK_SEM.acquire(timeout=settings.quick_wait_s):
            raise QuickBusy("quick path busy")
        try:
            for item_id, h, r in _quick_infer(todo, nli_gate, suppress_conflicts):
                out[item_id] = r
                if use_cache:
                    _cache(h, r)
        finally:
            _QUICK_SEM.release()
    return [out[it.id] for it in req.items]


def _quick_infer(todo: list[tuple[str, str, str, list[str]]], nli_gate: float, suppress_conflicts: bool
                 ) -> list[tuple[str, str, QuickResult]]:
    done: list[tuple[str, str, QuickResult]] = []
    flat = [s for _, _, _, segs in todo for s in segs]
    embs = INDEX.encode_query(flat)
    doc_idx, sims = INDEX.match_claims_batch(embs)
    true_idx, true_sims = INDEX.match_claims_batch(embs, verdicts=("true",))
    pos = 0
    pending_nli: list[tuple[str, str, str, int, float, str, int]] = []

    def _match(d, sim: float, seg: str) -> QuickMatch:
        return QuickMatch(claim=d.claim or d.title, verdict=d.verdict, verdict_raw=d.verdict_raw, publisher=d.publisher,
                          url=d.url, title=d.title, published_at=d.published_at, similarity=round(sim, 3), sentence=seg)

    for item_id, h, text, segs in todo:
        best = None
        for j in range(len(segs)):
            di, sim = int(doc_idx[pos + j]), float(sims[pos + j])
            d = INDEX.docs[di]
            if d.verdict in RISK_W and (best is None or sim > best[1]):
                best = (di, sim, segs[j], pos + j)
        pos += len(segs)
        if best and best[1] >= max(nli_gate, settings.claim_match_soft):
            pending_nli.append((item_id, h, text, *best))
        elif best and best[1] >= settings.claim_match_soft:
            # near-miss band (soft threshold .. NLI gate): same_claim cannot accept it, so no NLI call is spent
            d = INDEX.docs[best[0]]
            r = QuickResult(id=item_id, risk=0.0, level="brak", match=_match(d, best[1], best[2]),
                            reason=f"Treść jest zbieżna z twierdzeniem ocenionym przez {d.publisher} jako „{d.verdict_raw}”.")
            done.append((item_id, h, _route(r, text, best[1], near=True)))
        else:
            r = QuickResult(id=item_id, risk=0.0, level="brak", reason=_NO_MATCH)
            done.append((item_id, h, _route(r, text, None, near=False)))
    fwd = NLI_MODEL.score([(seg, INDEX.docs[di].claim or INDEX.docs[di].title) for _, _, _, di, _, seg, _ in pending_nli])
    # reverse direction only where the forward pass hints at a contradiction (negation check) — saves CPU
    need = [i for i, f in enumerate(fwd) if f.contra >= 0.3]
    rev_scores = NLI_MODEL.score([(INDEX.docs[pending_nli[i][3]].claim or INDEX.docs[pending_nli[i][3]].title,
                                   pending_nli[i][5]) for i in need])
    rev = list(fwd)
    for i, r_ in zip(need, rev_scores):
        rev[i] = r_
    for (item_id, h, text, di, sim, seg, row), s, s_rev in zip(pending_nli, fwd, rev):
        d = INDEX.docs[di]
        # similarity (calibrated logistic) x does the post ASSERT the rated claim (NLI); an internal score, never shown
        p_match = 1 / (1 + math.exp(-(sim - 0.78) * 25))
        decision = same_claim(sim, s, s_rev, d.claim or d.title, seg, d.source_type)
        if decision is not True:
            agree = 0.0  # opposite (e.g. the post debunks it) or merely related — never a match
        else:
            agree = 0.30 + 0.70 * s.entail
        risk = round(p_match * agree * RISK_W[d.verdict], 3)
        level = "wysokie" if risk >= 0.6 else "srednie" if risk >= 0.35 else "brak"
        r = QuickResult(
            id=item_id, risk=risk, level=level, match=_match(d, sim, seg),
            reason=f"Treść jest zbieżna z twierdzeniem ocenionym przez {d.publisher} jako „{d.verdict_raw}”.",
        )
        if level != "brak" and suppress_conflicts:
            t = INDEX.docs[int(true_idx[row])]
            t_sim = float(true_sims[row])
            if t.verdict == "true" and t_sim >= sim - CONFLICT_MARGIN:
                r.conflict = QuickConflict(claim=t.claim or t.title, verdict_raw=t.verdict_raw, publisher=t.publisher,
                                           url=t.url, published_at=t.published_at, similarity=round(t_sim, 3))
                r.risk, r.level = 0.0, "brak"
                r.reasons = ["CONFLICTING_RATINGS"]
                r.reason = (f"Zbliżone twierdzenia oceniono różnie ({d.publisher}: „{d.verdict_raw}”, {t.publisher}: "
                            f"„{t.verdict_raw}”) — bez oznaczenia.")
        complete = bool(d.publisher and d.url and d.published_at and (d.verdict_raw or d.verdict))
        if r.level != "brak" and not complete:
            r.risk, r.level = 0.0, "brak"  # a visible match must name publisher, rating, date and link
        if r.level != "brak":
            r.state, r.reasons = "match", ["RATED_CLAIM_MATCH"]
        else:
            # decision False = the text denies the rated claim: not a near miss, at most a checkable sentence
            r = _route(r, text, sim, near=decision is not False)
        done.append((item_id, h, r))
    return done


def _cache(h: str, r: QuickResult) -> None:
    _QCACHE[h] = r
    if len(_QCACHE) > 5000:
        _QCACHE.popitem(last=False)
