"""HTTP entry point: routes, startup, middleware and static website delivery.

HTTP API + static website. Run: uvicorn prawdowid.api:app --port 8000

Reading guide: docs/backend/API.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import csv
import io
import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, ratelimit, store
from .admin_api import check_token, public_registry, router as admin_router
from .channels.meta import router as meta_router
from .jobs import guard_auto, router as jobs_router
from .catalog import summarize_publishers
from .config import settings
from .index import INDEX
from .schemas import ChatRequest, CheckRequest, CheckResult, QuickRequest, QuickResult
from .service import QuickBusy, engine_info, quick_score, run_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("prawdowid.api")

app = FastAPI(
    title="Prawdowid API",
    version=__version__,
    description="Weryfikacja informacji oparta na wiarygodnych źródłach — prototyp (HackNation 2026).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension|moz-extension|safari-web-extension)://.*$|^http://localhost(:\d+)?$",
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(meta_router)
app.include_router(
    admin_router
)  # source registry admin: /admin, /api/admin/*, background scheduler
app.include_router(
    jobs_router
)  # async checks for the waiting window: /api/check/async, /api/jobs/{id}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Per client address and minute (ratelimit.py): full checks and tier-1 batches have separate buckets, so
    background page scanning cannot use up the budget for checks, and the other way round."""
    if request.method == "POST":
        path = request.url.path
        limit = (
            ("check", settings.rate_limit_per_min)
            if path.startswith("/api/check") or path == "/api/chat-reply"
            else ("quick", settings.rate_limit_quick_per_min) if path == "/api/quick" else None
        )
        if limit:
            wait = ratelimit.hit(limit[0], ratelimit.client_ip(request), limit[1])
            if wait is not None:
                return JSONResponse(
                    {"detail": ratelimit.MESSAGE},
                    status_code=429,
                    headers={"Retry-After": str(wait)},
                )
    return await call_next(request)


@app.on_event("startup")
def _startup() -> None:
    from .websearch import purge_live_corpus

    purge_live_corpus()  # expired live-search pages (all of them when storing is off), before indexing
    INDEX.load()
    # A shipped embedding cache can skip loading the retrieval model entirely.
    # Warm it before readiness, rather than downloading it on the first user's request.
    INDEX.encode_query(["rozgrzewka"])
    from .nli import NLI_MODEL

    NLI_MODEL.score(
        [("rozgrzewka", "rozgrzewka")]
    )  # warm-up so the first user does not wait for model load
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
    result = store.get_check(check_id)
    if not result:
        raise HTTPException(
            404, "Nie znaleziono sprawdzenia (mogło wygasnąć zgodnie z polityką retencji)."
        )
    return result


@app.post("/api/chat-reply")
def api_chat_reply(body: ChatRequest):
    """For thin channel adapters (Discord bot, SMS gateway): same verification, chat-formatted reply."""
    from .channels.formatting import chat_text

    text = body.text
    channel = body.channel
    if not text.strip():
        raise HTTPException(422, "Pusta wiadomość")
    result = run_check(CheckRequest(text=text, channel=channel, session=body.session or None))
    bold = "**" if channel == "discord" else "*"
    return {
        "id": result.id,
        "text": chat_text(
            result, bold=bold, max_len=None if channel == "discord" else 3500, sms=channel == "sms"
        ),
        "status": result.status,
        "verdicts": [c.verdict for c in result.claims],
    }


@app.post("/api/quick", response_model=list[QuickResult])
def api_quick(req: QuickRequest):
    """Tier 1 (router). Per item `state`: none | candidate | match — see schemas.QuickResult. Errors are never a
    statement about content: 429 (client limit) and 503 (inference slot busy) both carry Retry-After.
    """
    try:
        return quick_score(req)
    except QuickBusy as e:
        return JSONResponse(
            {
                "detail": "Serwer jest zajęty — spróbuj za chwilę. To nie jest ocena treści.",
                "status": "blad_techniczny",
            },
            status_code=503,
            headers={"Retry-After": str(e.retry_after)},
        )


@app.delete("/api/session/{session}")
def api_delete_session(session: str):
    return {"deleted_checks": store.delete_session(session)}


@app.post("/api/feedback")
def api_feedback(body: dict):
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(422, "Pusta wiadomość")
    store.add_feedback(str(body.get("check_id", "")), message)
    return {"ok": True}


@app.get("/api/sources")
def api_sources():
    return {
        "stats": INDEX.stats,
        "publishers": summarize_publishers(INDEX.docs),
        "sources": public_registry(),
    }


@app.get("/api/stats")
def api_stats():
    return store.stats() | {"corpus": INDEX.stats, "engine": engine_info()}


# ------------------------------------------------------------------ moderator / analyst
def _mod(token: str | None) -> None:
    check_token(
        token,
        settings.moderator_token,
        "X-Moderator-Token",
        "PRAWDOWID_MODERATOR_TOKEN",
        "moderatora",
    )


@app.get("/api/cases")
def api_cases(x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    return {
        "cases": store.list_cases(),
        "security_events": store.recent_security_events(20),
        "stats": store.stats(),
        "feedback": store.list_feedback(),
    }


@app.post("/api/cases/{case_id}")
def api_case_update(case_id: str, body: dict, x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    if not store.update_case(case_id, body.get("status", "w toku"), body.get("note", "")):
        raise HTTPException(404, "Brak sprawy")
    return {"ok": True}


@app.get("/api/export/checks.{fmt}")
def api_export(fmt: str, x_moderator_token: str | None = Header(default=None)):
    _mod(x_moderator_token)
    data = store.export_checks()
    if fmt == "json":
        return JSONResponse(data)
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(data[0].keys()) if data else ["id"])
        writer.writeheader()
        writer.writerows(data)
        return PlainTextResponse(buffer.getvalue(), media_type="text/csv")
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
    app.add_api_route(
        f"/{_name}", (lambda n=_name: _page(f"{n}.html")), methods=["GET"], include_in_schema=False
    )

app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
app.mount(
    "/demo", StaticFiles(directory=WEB / "demo", html=True), name="demo"
)  # test pages for the extension


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(
        WEB / "static" / "manifest.webmanifest", media_type="application/manifest+json"
    )


@app.get("/sw.js")
def sw():
    return FileResponse(WEB / "static" / "sw.js", media_type="application/javascript")


@app.post("/share-target")
async def share_target(request: Request):
    """PWA Web Share Target: Android users can 'Share' a post from the Facebook/X app to Prawdowid."""
    form = await request.form()
    text = " ".join(str(form.get(k, "")) for k in ("title", "text", "url")).strip()
    result = run_check(CheckRequest(text=text[:6000], channel="pwa-share"))
    from fastapi.responses import RedirectResponse

    return RedirectResponse(f"/analiza/{result.id}", status_code=303)
