"""Parse robots.txt rules using longest-match and Allow-tie semantics.

robots.txt parser with RFC 9309 semantics (stdlib only, so ingest/ scripts can load it by file path too).

Why not urllib.robotparser: it applies the *first* matching rule and ends a group at a blank line, so e.g.
moje.cert.pl (`Disallow: /`, blank line, `Allow: /komunikaty/`) is wrongly read as "everything blocked".
RFC 9309 §2.2.2: the most specific (longest) matching rule wins, and Allow wins a tie; `*` matches any
sequence of characters and a trailing `$` anchors the end of the path.

Drop-in for the parts of RobotFileParser we use: parse(lines), can_fetch(ua, url), crawl_delay(ua),
site_maps(), and the allow_all / disallow_all flags.

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import quote, urlsplit

_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_KEEP = "/?#[]@!$&'()*+,;=:%-._~"  # reserved + unreserved + '%': left as they are by quote()


def _norm(s: str) -> str:
    """Percent-encoding normalization for comparison (RFC 9309 §2.2.2): non-ASCII/space -> %XX, %XX of an
    unreserved char -> the char, other %xx -> upper-case."""
    s = quote(s, safe=_KEEP)
    return re.sub(
        r"%([0-9A-Fa-f]{2})",
        lambda m: (
            chr(int(m.group(1), 16))
            if chr(int(m.group(1), 16)) in _UNRESERVED
            else "%" + m.group(1).upper()
        ),
        s,
    )


@lru_cache(maxsize=4096)
def _rx(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    body = re.escape(pattern[:-1] if anchored else pattern).replace(r"\*", ".*")
    return re.compile(body + (r"\Z" if anchored else ""), re.S)


def _product_token(ua: str) -> str:
    return ua.split("/", 1)[0].strip().lower()


class RobotsTxt:
    def __init__(self) -> None:
        self.allow_all = False
        self.disallow_all = False
        # groups: (user-agents, rules [(allow, normalized pattern)], crawl-delay)
        self._groups: list[tuple[list[str], list[tuple[bool, str]], float | None]] = []
        self._sitemaps: list[str] = []

    # ---------------------------------------------------------------- parsing
    def parse(self, lines) -> None:
        if isinstance(lines, str):
            lines = lines.splitlines()
        groups: list[tuple[list[str], list[tuple[bool, str]], list[float]]] = []
        cur: tuple[list[str], list[tuple[bool, str]], list[float]] | None = None
        last_was_agent = False
        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:  # blank lines and junk do NOT end a group (RFC 9309 §2.1)
                continue
            key, val = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key in ("user-agent", "useragent", "user agent"):
                if cur is None or not last_was_agent:
                    cur = ([], [], [])
                    groups.append(cur)
                cur[0].append(val.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key == "sitemap":
                if val:
                    self._sitemaps.append(val)
            elif cur is None:  # rules before any user-agent line belong to no group
                continue
            elif key in ("allow", "disallow"):
                if (
                    val
                ):  # empty Disallow = allow everything = no rule; empty Allow means nothing either
                    cur[1].append((key == "allow", _norm(val)))
            elif key == "crawl-delay":
                try:
                    cur[2].append(float(val))
                except ValueError:
                    pass
        self._groups = [(a, r, max(d) if d else None) for a, r, d in groups]

    def _chosen(self, ua: str):
        """Groups for this crawler: every group naming our product token (merged, RFC 9309 §2.2.1), else every
        `*` group. Substring match like urllib.robotparser (so `User-agent: PrawdowidBot` also applies).
        """
        token = _product_token(ua)
        specific = [g for g in self._groups if any(a != "*" and a and a in token for a in g[0])]
        return specific or [g for g in self._groups if "*" in g[0]]

    # ---------------------------------------------------------------- queries
    def can_fetch(self, useragent: str, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        p = urlsplit(url)
        path = p.path or "/"
        if path == "/robots.txt":
            return True  # implicitly allowed (RFC 9309 §2.2.2)
        if p.query:
            path += "?" + p.query
        path = _norm(path)
        best_len, best_allow = -1, True
        for _agents, rules, _delay in self._chosen(useragent):
            for allow, pat in rules:
                if _rx(pat).match(path):
                    n = len(pat)
                    if n > best_len or (n == best_len and allow):
                        best_len, best_allow = n, allow
        return best_allow

    def crawl_delay(self, useragent: str) -> float | None:
        delays = [d for _a, _r, d in self._chosen(useragent) if d is not None]
        return max(delays) if delays else None

    def site_maps(self) -> list[str] | None:
        return list(self._sitemaps) or None
