"""Safe URL fetching + main-content extraction. Fetched content is untrusted data."""
from __future__ import annotations

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
        with httpx.Client(timeout=settings.fetch_timeout_s, follow_redirects=False,
                          headers={"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"}) as client:
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

    meta = trafilatura.extract_metadata(html)
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
    return {
        "url": url,
        "domain": urlparse(url).hostname or "",
        "title": (meta.title if meta else None) or "",
        "sitename": (meta.sitename if meta else None) or "",
        "date": (meta.date if meta else None),
        "author": (meta.author if meta else None),
        "text": text[: settings.max_input_chars],
    }
