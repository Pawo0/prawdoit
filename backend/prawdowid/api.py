"""HTTP API + static website. Run: uvicorn prawdowid.api:app --port 8000"""
from __future__ import annotations

import csv
import io
import json
import logging
from collections import Counter

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, ratelimit, store
from .admin_api import check_token, public_registry, router as admin_router
from .channels.meta import router as meta_router
from .jobs import guard_auto, router as jobs_router
from .config import settings
from .index import INDEX, TIER, TIER_LABEL
from .schemas import ChatRequest, CheckRequest, CheckResult, QuickRequest, QuickResult
from .service import QuickBusy, engine_info, quick_score, run_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("prawdowid.api")

app = FastAPI(title="Prawdowid API", version=__version__,
              description="Weryfikacja informacji oparta na wiarygodnych źródłach — prototyp (HackNation 2026).")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"^(chrome-extension|moz-extension|safari-web-extension)://.*$|^http://localhost(:\d+)?$",
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
app.include_router(meta_router)
app.include_router(admin_router)  # source registry admin: /admin, /api/admin/*, background scheduler
app.include_router(jobs_router)  # async checks for the waiting window: /api/check/async, /api/jobs/{id}

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Per client address and minute (ratelimit.py): full checks and tier-1 batches have separate buckets, so
    background page scanning cannot use up the budget for checks, and the other way round."""
    if request.method == "POST":
        path = request.url.path
        limit = (("check", settings.rate_limit_per_min)
                 if path.startswith("/api/check") or path == "/api/chat-reply"
                 else ("quick", settings.rate_limit_quick_per_min) if path == "/api/quick" else None)
        if limit:
            wait = ratelimit.hit(limit[0], ratelimit.client_ip(request), limit[1])
            if wait is not None:
                return JSONResponse({"detail": ratelimit.MESSAGE}, status_code=429, headers={"Retry-After": str(wait)})
    return await call_next(request)


@app.on_event("startup")
def _startup() -> None:
    INDEX.load()
    # A shipped embedding cache can skip loading the retrieval model entirely.
    # Warm it before readiness, rather than downloading it on the first user's request.
    INDEX.encode_query(["rozgrzewka"])
    from .nli import NLI_MODEL

    NLI_MODEL.score([("rozgrzewka", "rozgrzewka")])  # warm-up so the first user does not wait for model load
    store.purge_expired()


# ------------------------------------------------------------------ core API
@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "engine": engine_info(), "corpus": INDEX.stats}


@app.post("/api/check", response_model=CheckResult)
def api_check(req: CheckRequest, request: Request):
    if not (req.text or req.url or req.image_b64):
        raise HTTPException(422, "Podaj tekst, adres URL lub obraz.")
    guard_auto(req, request)
    return run_check(req)


@app.get("/api/check/{check_id}")
def api_get_check(check_id: str):
    r = store.get_check(check_id)
    if not r:
        raise HTTPException(404, "Nie znaleziono sprawdzenia (mogło wygasnąć zgodnie z polityką retencji).")
    return r


@app.post("/api/chat-reply")
def api_chat_reply(body: ChatRequest):
    """For thin channel adapters (Discord bot, SMS gateway): same verification, chat-formatted reply."""
    from .channels.formatting import chat_text

    text = body.text
    channel = body.channel
    if not text.strip():
        raise HTTPException(422, "Pusta wiadomość")
    res = run_check(CheckRequest(text=text, channel=channel, session=body.session or None))
    bold = "**" if channel == "discord" else "*"
    return {"id": res.id, "text": chat_text(res, bold=bold, max_len=None if channel == "discord" else 3500,
                                            sms=channel == "sms"), "status": res.status,
            "verdicts": [c.verdict for c in res.claims]}


@app.post("/api/quick", response_model=list[QuickResult])
def api_quick(req: QuickRequest):
    """Tier 1 (router). Per item `state`: none | candidate | match — see schemas.QuickResult. Errors are never a
    statement about content: 429 (client limit) and 503 (inference slot busy) both carry Retry-After."""
    try:
        return quick_score(req)
    except QuickBusy as e:
        return JSONResponse({"detail": "Serwer jest zajęty — spróbuj za chwilę. To nie jest ocena treści.",
                             "status": "blad_techniczny"}, status_code=503, headers={"Retry-After": str(e.retry_after)})


@app.delete("/api/session/{session}")
def api_delete_session(session: str):
    return {"deleted_checks": store.delete_session(session)}


@app.post("/api/feedback")
def api_feedback(body: dict):
    msg = str(body.get("message", "")).strip()
    if not msg:
        raise HTTPException(422, "Pusta wiadomość")
    store.add_feedback(str(body.get("check_id", "")), msg)
    return {"ok": True}


@app.get("/api/sources")
def api_sources():
    pubs: dict[str, dict] = {}
    for d in INDEX.docs:
        p = pubs.setdefault(d.publisher, {"publisher": d.publisher, "domains": set(), "source_type": d.source_type,
                                          "tier": TIER[d.source_type], "tier_label": TIER_LABEL[TIER[d.source_type]],
                                          "documents": 0, "licenses": Counter(), "newest": None, "oldest": None,
                                          "retrieved_at": None})
        p["domains"].add(d.domain)
        p["documents"] += 1
        p["licenses"][d.license] += 1
        if d.published_at:
            p["newest"] = max(p["newest"] or d.published_at, d.published_at)
            p["oldest"] = min(p["oldest"] or d.published_at, d.published_at)
        if d.retrieved_at:
            p["retrieved_at"] = max(p["retrieved_at"] or d.retrieved_at, d.retrieved_at)
    out = []
    for p in sorted(pubs.values(), key=lambda x: (x["tier"], -x["documents"])):
        p["domains"] = sorted(p["domains"])
        p["licenses"] = [k for k, _ in p["licenses"].most_common(3)]
        out.append(p)
    return {"stats": INDEX.stats, "publishers": out, "sources": public_registry()}  # sources: data/sources registry


@app.get("/api/stats")
def api_stats():
    return store.stats() | {"corpus": INDEX.stats, "engine": engine_info()}


# ------------------------------------------------------------------ moderator / analyst
def _mod(token: str | None) -> None:
    check_token(token, settings.moderator_token, "X-Moderator-Token", "PRAWDOWID_MODERATOR_TOKEN", "moderatora")


@app.get("/api/cases")
def api_cases(x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    return {"cases": store.list_cases(), "security_events": store.recent_security_events(20), "stats": store.stats(),
            "feedback": store.list_feedback()}


@app.post("/api/cases/{case_id}")
def api_case_update(case_id: str, body: dict, x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    if not store.update_case(case_id, body.get("status", "w toku"), body.get("note", "")):
        raise HTTPException(404, "Brak sprawy")
    return {"ok": True}


@app.get("/api/export/checks.{fmt}")
def api_export(fmt: str, x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    rows = store._db.execute("SELECT id, created_at, channel, input_masked, status, verdicts, sources, total_ms, case_id "
                             "FROM checks ORDER BY created_at DESC").fetchall()
    data = [dict(r) for r in rows]
    if fmt == "json":
        return JSONResponse(data)
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(data[0].keys()) if data else ["id"])
        w.writeheader()
        w.writerows(data)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    raise HTTPException(400, "fmt: csv|json")


# ------------------------------------------------------------------ website
WEB = settings.web_dir


def _page(name: str):
    return FileResponse(WEB / name, media_type="text/html")


@app.get("/")
def page_index():
    return _page("index.html")


@app.get("/analiza/{check_id}")
def page_result(check_id: str):
    return _page("analiza.html")


@app.get("/sprawdz")
def page_check():
    return _page("analiza.html")


for _name in ("metodologia", "zrodla", "moderator", "czat", "o-projekcie"):
    app.add_api_route(f"/{_name}", (lambda n=_name: _page(f"{n}.html")), methods=["GET"], include_in_schema=False)

app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
app.mount("/demo", StaticFiles(directory=WEB / "demo", html=True), name="demo")  # test pages for the extension


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    return FileResponse(WEB / "static" / "sw.js", media_type="application/javascript")


@app.post("/share-target")
async def share_target(request: Request):
    """PWA Web Share Target: Android users can 'Share' a post from the Facebook/X app to Prawdowid."""
    form = await request.form()
    text = " ".join(str(form.get(k, "")) for k in ("title", "text", "url")).strip()
    res = run_check(CheckRequest(text=text[:6000], channel="pwa-share"))
    from fastapi.responses import RedirectResponse

    return RedirectResponse(f"/analiza/{res.id}", status_code=303)
