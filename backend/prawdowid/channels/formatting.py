"""Render a CheckResult as a short chat message (WhatsApp / Messenger / Discord / SMS).

Channel consistency (challenge scenario G): the message is built from the SAME fields the website shows first —
`short_answer`, the decisive source (`main_evidence`), `basis_line` / `limitation_line` — plus a link to the full
analysis. web/czat.html mirrors this function for its async demo mode (chatReply in that page).
"""
from __future__ import annotations

from ..config import settings
from ..schemas import CheckResult, ClaimResult
from ..textutil import short

ICON = {"falszywe": "❌", "wprowadzajace_w_blad": "⚠️", "potwierdzone": "✅", "brak_dowodow": "❔",
        "nie_podlega_weryfikacji": "💬"}
HEAD = {"blad_techniczny": "Błąd techniczny (to nie jest ocena treści)", "doprecyzuj": "Potrzebuję doprecyzowania",
        "poza_zakresem": "Poza zakresem"}


def _date(s: str | None) -> str:
    if not s:
        return "b.d."
    y, m, d = (s[:10].split("-") + ["", ""])[:3]
    return f"{d}.{m}.{y}" if d else s


def _answer(c: ClaimResult, sms: bool) -> str:
    # results stored before answer.py existed have no short_answer — fall back to the engine explanation
    return c.short_answer or short(c.explanation, 160 if sms else 420)


def _source(c: ClaimResult) -> str | None:
    """The decisive source; for an abstention that names related material, that item, labelled as not decisive."""
    i, label = c.main_evidence, "Źródło"
    if i is None:
        i, label = getattr(c, "related_evidence", None), "Materiał pokrewny (nie rozstrzyga)"
    if i is None or i >= len(c.evidence):
        return None
    e = c.evidence[i]
    return f"{label}: {e.publisher}, {_date(e.published_at)} — {short(e.title, 90)}\n{e.url}"

def _sources_long(c: ClaimResult) -> list[str]:
    """Discord (markdown, split into several messages, no length cap): every decisive source with its verbatim
    quote, the decisive one (main_evidence) first. Empty when nothing is decisive — an abstention then keeps the
    single related item from _source, labelled as not decisive, never another claim's rating."""
    decisive = [e for e in c.evidence if e.stance in ("przeczy", "popiera")]
    if c.main_evidence is not None and c.main_evidence < len(c.evidence):
        main = c.evidence[c.main_evidence]
        decisive = [main] + [e for e in decisive if e is not main]
    out = []
    for j, e in enumerate(decisive[:3], 1):
        out.append(f"{j}. {e.publisher}, {_date(e.published_at)} — {short(e.title, 80)}\n   {e.url}")
        if e.fragment:
            out.append(f"   Cytat: „{short(e.fragment, 220)}”")
    return ["Źródła:"] + out if out else []



def chat_text(res: CheckResult, bold: str = "*", max_len: int | None = 3500, sms: bool = False) -> str:
    b = lambda s: f"{bold}{s}{bold}" if bold else s  # noqa: E731
    link = f"{settings.public_base_url}/analiza/{res.id}"
    if res.status != "ok":
        return f"{b('Prawdowid')} — {HEAD[res.status]}\n{res.short_answer or res.status_message or ''}".strip()
    multi = len(res.claims) > 1
    lines: list[str] = []
    for i, c in enumerate(res.claims, 1):
        if lines:
            lines.append("")
        if multi:
            lines.append(f"{i}. „{short(c.claim, 120)}”")
        lines.append(f"{ICON[c.verdict]} {b(c.verdict_label)}")
        lines.append(_answer(c, sms))
        long = _sources_long(c) if bold == "**" and not sms else []
        src = None if long else _source(c)
        if src and not sms:
            lines.append(src)
        lines.extend(long)
        if c.basis_line and not sms and c.verdict != "nie_podlega_weryfikacji":
            lines.append(c.basis_line)
            if c.limitation_line:
                lines.append(c.limitation_line)
    if res.security_events:
        lines.append("\nℹ️ W treści była instrukcja skierowana do systemu — zignorowałem ją i zapisałem zdarzenie. "
                     "Nie wpływa na ocenę.")
    live_notice = res.live_search.notice if getattr(res, "live_search", None) else ""  # already in limitation_line
    other = [w for w in res.warnings if not w.startswith("W treści wykryto") and w != live_notice]
    if other and not sms:
        lines.append(f"\nℹ️ {short(other[0], 200)}")
    off = res.engine.get("unavailable") or []
    if off and not sms and any(c.verdict == "brak_dowodow" for c in res.claims):  # absence must not read as a result
        lines.append(f"\nℹ️ {short(off[0], 200)}")
    if res.case_id:
        lines.append(f"\n📨 Sprawa {res.case_id} trafiła do kolejki analityka.")
    lines.append(f"\nPełna analiza i wszystkie źródła: {link}")
    if not sms:
        lines.append("(Odpowiedź automatyczna — zajrzyj do źródła.)")
    txt = "\n".join(lines)
    return txt if max_len is None or len(txt) <= max_len else txt[: max_len - 1] + "…"
