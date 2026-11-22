"""Fetch one user-supplied URL safely and extract its article text and ClaimReview metadata.

Safe URL fetching + main-content extraction. Fetched content is untrusted data.

Reading guide: docs/backend/REQUEST_FLOW.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import httpx

from .config import settings
from .security import ResolveError, UnsafeURL, check_public_url

UA = "PrawdowidBot/0.1 (+weryfikacja informacji; prototyp HackNation)"


class FetchError(RuntimeError):
    pass


def fetch_url(url: str) -> dict:
    url = check_public_url(url)
    try:
        with httpx.Client(
            timeout=settings.fetch_timeout_s,
            follow_redirects=False,
            headers={"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"},
        ) as client:
            for _ in range(4):  # manual redirects so every hop is SSRF-checked
                with client.stream("GET", url) as r:
                    if r.is_redirect:
                        url = check_public_url(urljoin(url, r.headers.get("location", "")))
                        continue
                    if r.status_code >= 400:
                        raise FetchError(f"Strona zwróciła błąd HTTP {r.status_code}.")
                    ctype = r.headers.get("content-type", "")
                    if "html" not in ctype and "text" not in ctype:
                        raise FetchError(f"Nieobsługiwany typ treści: {ctype or 'nieznany'}.")
                    buf = bytearray()
                    for chunk in r.iter_bytes():
                        buf.extend(chunk)
                        if len(buf) > settings.max_fetch_bytes:
                            break
                    html = buf.decode(r.encoding or "utf-8", errors="replace")
                    break
            else:
                raise FetchError("Zbyt wiele przekierowań.")
    except (UnsafeURL, ResolveError):
        raise
    except httpx.HTTPError as e:
        raise FetchError(f"Nie udało się pobrać strony ({type(e).__name__}).") from e

    import trafilatura

    cr = claim_review(html)
    meta = trafilatura.extract_metadata(html)
    text = (
        trafilatura.extract(
            html, include_comments=False, include_tables=False, favor_precision=True
        )
        or ""
    )
    return {
        "url": url,
        "domain": urlparse(url).hostname or "",
        "title": (meta.title if meta else None) or "",
        "sitename": (meta.sitename if meta else None) or "",
        "date": (meta.date if meta else None),
        "author": (meta.author if meta else None),
        "text": text[: settings.max_input_chars],
        "claim_review": cr,  # schema.org ClaimReview (fact-checkers), untrusted like the rest of the page
    }


_LD_RX = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


def claim_review(html: str) -> dict | None:
    """First schema.org ClaimReview in the page's JSON-LD — the machine-readable record fact-checkers (IFCN/EFCSN,
    Google Fact Check markup) publish with every review: the reviewed claim, its author and the rating label.
    """
    for m in _LD_RX.finditer(html or ""):
        try:
            stack = [json.loads(m.group(1).strip())]
        except ValueError:
            continue
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
                continue
            if not isinstance(x, dict):
                continue
            t = x.get("@type")
            if t == "ClaimReview" or (isinstance(t, list) and "ClaimReview" in t):
                rating = x.get("reviewRating") or {}
                rating = rating[0] if isinstance(rating, list) and rating else rating
                item = x.get("itemReviewed") or {}
                author = item.get("author") if isinstance(item, dict) else None
                author = author[0] if isinstance(author, list) and author else author
                out = {
                    "claim": str(x.get("claimReviewed") or "").strip(),
                    "rating": str(
                        (rating.get("alternateName") or rating.get("name") or "")
                        if isinstance(rating, dict)
                        else ""
                    ).strip(),
                    "author": (
                        str(author.get("name") or "").strip() if isinstance(author, dict) else ""
                    ),
                    "date": str(x.get("datePublished") or "")[:10],
                }
                if out["claim"] and out["rating"]:
                    return out
            if "@graph" in x:
                stack.append(x["@graph"])
    return None
