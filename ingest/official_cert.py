#!/usr/bin/env python3
"""CERT Polska (NASK) warnings: non-CVE posts from https://cert.pl/rss.xml (scam/phishing/
APT/disinformation-related analyses) + thematic scam guides (fałszywe inwestycje, sklepy,
konsultanci, płatności, CAPTCHA, załączniki...) + the "Lista ostrzeżeń" description page.

robots.txt: disallows only /telefon/, /szukaj/, /en/search/ (checked at runtime).
Licence: cert.pl content © NASK — no open licence stated; each record keeps title, date and link plus
ONE verbatim excerpt of at most 300 chars (the opening after the headline; textutil.opening_excerpt),
quoted with attribution (quotation right, art. 29 pr. aut.). The hole.cert.pl domain list itself
is free for any use (cert.pl/en/warning-list).

Output: data/corpus/official_cert.jsonl
"""
from __future__ import annotations

import re
import sys

from pathlib import Path

from official_common import JsonlWriter, fetch_text, html_to_text, log, make_record, pl_date

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from prawdowid.textutil import opening_excerpt  # noqa: E402  (stdlib-only module)

LIC = ("© NASK / CERT Polska — brak otwartej licencji; zapisane: tytuł, data, link i jeden dosłowny fragment "
       "(do 300 znaków) z przypisem (prawo cytatu, art. 29 pr. aut.); lista hole.cert.pl: dowolne użycie")
EXCERPT_CHARS = 300
PUB = "CERT Polska (NASK)"
GUIDES = [
    ("/falszywe-inwestycje/", ["oszustwa", "fałszywe inwestycje", "deepfake"]),
    ("/falszywe-sklepy/", ["oszustwa", "fałszywe sklepy"]),
    ("/baza-wiedzy/falszywi-konsultanci", ["oszustwa", "fałszywi konsultanci", "vishing"]),
    ("/baza-wiedzy/niebezpieczne-platnosci", ["oszustwa", "płatności", "phishing"]),
    ("/falszywe-captcha/", ["złośliwe oprogramowanie", "CAPTCHA"]),
    ("/falszywe-zalaczniki/", ["phishing", "załączniki"]),
    ("/szybkie-przelewy/", ["phishing", "przelewy"]),
    ("/bezpieczny-telefon/", ["bezpieczeństwo", "telefon", "SMS"]),
    ("/lista-ostrzezen/", ["lista ostrzeżeń", "phishing", "domeny"]),
]


def parse(html: str) -> tuple[str, str, str | None]:
    t = re.search(r'<meta property="og:title" content="([^"]+)"', html) or re.search(r"<title>(.*?)</title>", html, re.S)
    title = html_to_text(t.group(1)) if t else ""
    s = re.search(r'<div class="(?:main cell entry|kb-[a-z-]+|article)"', html)
    start = s.start() if s else 0
    ends = [i for i in (html.find(mk, start + 10) for mk in
                        ('<div class="project-icons"', 'class="footer-main"', "<footer", '<div class="sidebar'))
            if i != -1]
    body = html_to_text(html[start: min(ends) if ends else len(html)])
    d = re.search(r'(\d{4}-\d{2}-\d{2})', re.search(r'<time[^>]*>.*?</time>', html, re.S).group(0)) \
        if re.search(r'<time[^>]*>.*?</time>', html, re.S) else None
    return title, body, d.group(1) if d else None


def main():
    with JsonlWriter("cert") as w:
        rss = fetch_text("https://cert.pl/rss.xml")
        posts = []
        for it in re.findall(r"<item>(.*?)</item>", rss, flags=re.S):
            title = html_to_text(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
            link = re.search(r"<link>(.*?)</link>", it, re.S).group(1).strip()
            date = pl_date(re.search(r"<pubDate>(.*?)</pubDate>", it, re.S).group(1))
            if re.search(r"Podatno|CVE-", title + link):
                continue  # vulnerability advisories are out of scope for citizen fact-checking
            posts.append((link, title, date))
        for link, title, date in posts:
            try:
                t, body, _ = parse(fetch_text(link))
            except Exception as e:
                log("  skip", link, e)
                continue
            w.write(make_record(source="cert", sid=link.rstrip("/").split("/posts/")[-1], publisher=PUB, url=link,
                                title=t or title, text=opening_excerpt(body, t or title, EXCERPT_CHARS),
                                published_at=date, license=LIC, domain="cert.pl",
                                tags=["CERT Polska", "cyberbezpieczeństwo", "ostrzeżenie"] +
                                     (["dezinformacja", "APT"] if re.search(r"UNC1151|Ghostwriter|dezinform", t + body) else [])))
        for path, tags in GUIDES:
            url = "https://cert.pl" + path
            try:
                t, body, d = parse(fetch_text(url))
            except Exception as e:
                log("  skip", url, e)
                continue
            w.write(make_record(source="cert", sid="guide" + path.rstrip("/"), publisher=PUB, url=url,
                                title=t, text=opening_excerpt(body, t, EXCERPT_CHARS), published_at=d, license=LIC,
                                domain="cert.pl",
                                tags=["CERT Polska", "poradnik", "ostrzeżenie"] + tags))


if __name__ == "__main__":
    sys.exit(main())
