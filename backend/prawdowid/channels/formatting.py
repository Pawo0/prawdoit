"""Render a CheckResult as a short chat message (WhatsApp / Messenger / Discord / SMS)."""
from __future__ import annotations

from ..config import settings
from ..schemas import CheckResult
from ..textutil import short

ICON = {"falszywe": "❌", "wprowadzajace_w_blad": "⚠️", "potwierdzone": "✅", "brak_dowodow": "❔",
        "nie_podlega_weryfikacji": "💬"}


def _date(s: str | None) -> str:
    if not s:
        return "b.d."
    y, m, d = (s[:10].split("-") + ["", ""])[:3]
    return f"{d}.{m}.{y}" if d else s


def chat_text(res: CheckResult, bold: str = "*", max_len: int = 3500, sms: bool = False) -> str:
    b = lambda s: f"{bold}{s}{bold}" if bold else s  # noqa: E731
    link = f"{settings.public_base_url}/analiza/{res.id}"
    if res.status != "ok":
        head = {"blad_techniczny": "Błąd techniczny (to nie jest ocena treści)",
                "doprecyzuj": "Potrzebuję doprecyzowania", "poza_zakresem": "Poza zakresem"}[res.status]
        return f"{b('Prawdowid')} — {head}\n{res.status_message or ''}".strip()
    lines = [f"{b('Prawdowid')} — wynik sprawdzenia"]
    for i, c in enumerate(res.claims, 1):
        lines.append("")
        lines.append(f"{ICON[c.verdict]} {b(c.verdict_label)}" + (f" (siła podstaw: {c.strength_label})"
                                                                  if c.verdict not in ("brak_dowodow", "nie_podlega_weryfikacji") else ""))
        lines.append(f"Twierdzenie: „{short(c.claim, 160)}”")
        lines.append(short(c.explanation, 160 if sms else 420))
        decisive = [e for e in c.evidence if e.stance in ("przeczy", "popiera")]
        srcs = decisive or ([] if c.verdict == "nie_podlega_weryfikacji" else c.evidence[:2])
        if srcs and not sms:
            lines.append("Źródła:" if decisive else "Najbliższe materiały (nie rozstrzygają sprawy):")
            for j, e in enumerate(srcs[:3], 1):
                lines.append(f"{j}. {e.publisher}, {_date(e.published_at)} — {short(e.title, 80)}\n   {e.url}")
        if c.what_unknown and not sms:
            lines.append(f"Czego nie ustaliliśmy: {short(c.what_unknown, 200)}")
    for w in res.warnings[:2]:
        lines.append(f"\nℹ️ {short(w, 220)}")
    if res.case_id:
        lines.append(f"\n📨 Sprawa {res.case_id} trafiła do kolejki analityka.")
    lines.append(f"\nPełna analiza: {link}")
    if not sms:
        lines.append("Prawdowid pomaga ocenić informacje, ale nie jest sędzią prawdy — zajrzyj do źródeł.")
    txt = "\n".join(lines)
    return txt if len(txt) <= max_len else txt[: max_len - 1] + "…"
