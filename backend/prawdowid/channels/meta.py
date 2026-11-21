"""WhatsApp Cloud API + Messenger Platform webhooks, plus a demo adapter that uses the exact same payloads.

Real mode needs env: PRAWDOWID_WA_VERIFY_TOKEN, PRAWDOWID_WA_ACCESS_TOKEN, PRAWDOWID_WA_PHONE_NUMBER_ID,
PRAWDOWID_WA_APP_SECRET (signature check), PRAWDOWID_FB_PAGE_TOKEN, PRAWDOWID_FB_VERIFY_TOKEN.
Without them the adapter runs in demo mode: replies are returned in the HTTP response / demo outbox instead of
being sent through the Graph API (clearly labelled — no pretend delivery).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..schemas import CheckRequest
from ..service import run_check
from .formatting import chat_text

log = logging.getLogger("prawdowid.meta")
router = APIRouter()
GRAPH = "https://graph.facebook.com/v21.0"
OUTBOX: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))  # demo outbox per user id
_rate: dict[str, deque] = defaultdict(deque)

UNSUPPORTED = ("Prawdowid (prototyp) sprawdza na razie tekst i linki. Odczyt zdjęć/zrzutów ekranu i nagrań nie jest "
               "jeszcze włączony w tym kanale — to ograniczenie techniczne, a nie ocena treści. Przepisz lub wklej "
               "tekst wiadomości albo link.")


def _limited(user: str) -> bool:
    q, now = _rate[user], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    q.append(now)
    return len(q) > settings.rate_limit_per_min


def _verify_sig(request: Request, body: bytes) -> None:
    if not settings.wa_app_secret:
        return
    sig = request.headers.get("x-hub-signature-256", "")
    exp = "sha256=" + hmac.new(settings.wa_app_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, exp):
        raise HTTPException(403, "bad signature")


def _handle_text(channel: str, user: str, text: str | None, kind: str) -> str:
    if _limited(f"{channel}:{user}"):
        return "Za dużo zapytań w krótkim czasie. Spróbuj ponownie za minutę."
    if kind != "text" or not text:
        return UNSUPPORTED
    low = text.strip().lower()
    if low in ("start", "pomoc", "help", "hej", "cześć", "dzień dobry"):
        return ("Dzień dobry! Jestem Prawdowid. Prześlij mi wiadomość, którą chcesz sprawdzić (tekst lub link), "
                "a odpowiem, co mówią o tym wiarygodne źródła. Nie zapisuję Twojego numeru w historii sprawdzeń.")
    res = run_check(CheckRequest(text=text, channel=channel, session=hashlib.sha256(user.encode()).hexdigest()[:16]))
    return chat_text(res)


# ------------------------------------------------------------------ WhatsApp Cloud API
@router.get("/webhooks/whatsapp")
def wa_verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and settings.wa_verify_token and p.get("hub.verify_token") == settings.wa_verify_token:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


def _wa_send(to: str, body: str) -> None:
    try:
        httpx.post(f"{GRAPH}/{settings.wa_phone_number_id}/messages", timeout=10,
                   headers={"Authorization": f"Bearer {settings.wa_access_token}"},
                   json={"messaging_product": "whatsapp", "to": to, "type": "text",
                         "text": {"preview_url": False, "body": body[:4096]}}).raise_for_status()
    except httpx.HTTPError as e:
        log.error("WhatsApp send failed: %s", e)


def _wa_process(payload: dict, demo: bool) -> list[dict]:
    replies = []
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            for m in ch.get("value", {}).get("messages", []) or []:
                user, kind = m.get("from", "anon"), m.get("type", "text")
                text = (m.get("text") or {}).get("body") if kind == "text" else (m.get(kind) or {}).get("caption")
                reply = _handle_text("whatsapp", user, text, "text" if (kind == "text" or text) and text else kind)
                replies.append({"to": user, "body": reply})
                if demo or not (settings.wa_access_token and settings.wa_phone_number_id):
                    OUTBOX[user].append(reply)
                else:
                    _wa_send(user, reply)
    return replies


@router.post("/webhooks/whatsapp")
async def wa_webhook(request: Request, background: BackgroundTasks, demo: int = 0):
    body = await request.body()
    if not demo:
        _verify_sig(request, body)
    payload = await request.json()
    if demo:  # demo adapter: synchronous, reply returned in response, marked as not delivered via WhatsApp
        return {"mode": "demo — odpowiedź NIE została wysłana przez WhatsApp", "replies": _wa_process(payload, True)}
    background.add_task(_wa_process, payload, False)  # ack fast (Meta expects 200 quickly), work async
    return {"ok": True}


# ------------------------------------------------------------------ Messenger Platform
@router.get("/webhooks/messenger")
def fb_verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and settings.fb_verify_token and p.get("hub.verify_token") == settings.fb_verify_token:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


def _fb_process(payload: dict, demo: bool) -> list[dict]:
    replies = []
    for entry in payload.get("entry", []):
        for ev in entry.get("messaging", []):
            user = ev.get("sender", {}).get("id", "anon")
            msg = ev.get("message") or {}
            if msg.get("is_echo"):
                continue
            kind = "text" if msg.get("text") else ("image" if msg.get("attachments") else "unknown")
            reply = _handle_text("messenger", user, msg.get("text"), kind)
            replies.append({"to": user, "body": reply})
            if demo or not settings.fb_page_token:
                OUTBOX[user].append(reply)
            else:
                try:
                    httpx.post(f"{GRAPH}/me/messages", params={"access_token": settings.fb_page_token}, timeout=10,
                               json={"recipient": {"id": user}, "messaging_type": "RESPONSE",
                                     "message": {"text": reply.replace("*", "")[:2000]}}).raise_for_status()
                except httpx.HTTPError as e:
                    log.error("Messenger send failed: %s", e)
    return replies


@router.post("/webhooks/messenger")
async def fb_webhook(request: Request, background: BackgroundTasks, demo: int = 0):
    body = await request.body()
    if not demo:
        _verify_sig(request, body)
    payload = await request.json()
    if demo:
        return {"mode": "demo — odpowiedź NIE została wysłana przez Messenger", "replies": _fb_process(payload, True)}
    background.add_task(_fb_process, payload, False)
    return {"ok": True}


@router.get("/webhooks/demo-outbox/{user}")
def demo_outbox(user: str):
    return {"user": user, "messages": list(OUTBOX.get(user, []))}
