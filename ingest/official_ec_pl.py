#!/usr/bin/env python3
"""European Commission Representation in Poland (poland.representation.ec.europa.eu):
news items on disinformation / EU myths and on topics that attract disinformation
(migration pact, Green Deal, energy, EU funds/KPO, Ukraine, sanctions, DSA, agriculture).

There is no dedicated "Euromity / Fakty i mity" section any more (sitemap checked
2026-11-21), so we scan the news listing and keep matching items, plus the classic
"Fake news czy prawda? Sprawdź!" myth-busting article (2019).

The site rate-limits aggressively (HTTP 429 after a few quick hits) → 6 s per request.
Licence: © European Union, CC BY 4.0 (Commission legal notice), reuse with attribution.
Output: data/corpus/official_ec_pl.jsonl
Usage: python ingest/official_ec_pl.py [--pages 25] [--max 45]
"""
from __future__ import annotations

import argparse
import re
import sys

from official_common import JsonlWriter, fetch_text, html_to_text, log, make_record

BASE = "https://poland.representation.ec.europa.eu"
LIC = "© Unia Europejska, CC BY 4.0 (informacja prawna Komisji Europejskiej); podać źródło"
PUB = "Przedstawicielstwo Komisji Europejskiej w Polsce"
DELAY = 6.0
MONTHS = {m: i + 1 for i, m in enumerate(["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
                                          "sierpnia", "września", "października", "listopada", "grudnia"])}
SEEDS = ["/aktualnosci-i-wydarzenia/aktualnosci/fake-news-czy-prawda-sprawdz-2019-05-10_pl"]
KEYWORDS = {
    "dezinformacja": r"dezinform|fake|fałsz|falsz|mit[yóu]?\b|mity|manipul|prawd[ay]|fakty|propagand|fimi",
    "migracja": r"migra|azyl|pakt o migracji|uchodź|uchodz|ochrona granic|granic zewnętrznych",
    "Zielony Ład": r"zielon|klimat|ets|emisj|energ|prąd|prad|gaz|ciepł|ciepl|samochod",
    "fundusze UE": r"kpo|fundusz|budżet|budzet|odbudow|spójnoś|spojnos",
    "Ukraina": r"ukrain|rosj|sankcj",
    "DSA": r"usługach cyfrowych|uslugach-cyfrowych|dsa|tiktok|platform|meta|\bx\b",
    "rolnictwo": r"rolni|mercosur|wpr\b|żywnoś|zywnos",
    "praworządność": r"praworządn|praworzadn|tsue|trybunał",
}


def pl_date_words(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", s or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"


def topics(text: str) -> list[str]:
    t = text.lower()
    return [k for k, rx in KEYWORDS.items() if re.search(rx, t)]


def parse(html: str) -> tuple[str, str | None, str]:
    t = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    title = html_to_text(t.group(1)) if t else ""
    meta = re.search(r'ecl-page-header__meta">(.*?)</ul>', html, re.S)
    date = pl_date_words(html_to_text(meta.group(1))) if meta else None
    desc = re.search(r'<meta property="og:description" content="([^"]+)"', html)
    i = html.find('id="main-content"')
    seg = html[i:] if i > 0 else html
    cuts = [j for j in (seg.find(mk) for mk in ("Szczegóły</h2>", '<dl\n', "<dl ", "<footer")) if j > 0]
    if cuts:
        seg = seg[:min(cuts)]
    body = html_to_text(seg.split(">", 1)[1] if ">" in seg else seg)
    if desc and not body.startswith(html_to_text(desc.group(1))[:60]):
        body = html_to_text(desc.group(1)) + "\n" + body
    return title, date, body


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=25)
    ap.add_argument("--max", type=int, default=45)
    a = ap.parse_args(argv)
    cands: list[tuple[str, str]] = [(s, "") for s in SEEDS]
    for p in range(a.pages):
        url = f"{BASE}/aktualnosci-i-wydarzenia/aktualnosci_pl" + (f"?page={p}" if p else "")
        try:
            h = fetch_text(url, min_delay=DELAY)
        except Exception as e:
            log("  listing failed", url, e)
            break
        for href, label in re.findall(r'<a[^>]+href="(/aktualnosci-i-wydarzenia/aktualnosci/[^"]+_pl)"[^>]*>(.*?)</a>', h, re.S):
            lab = html_to_text(label)
            if topics(href.replace("-", " ") + " " + lab):
                cands.append((href, lab))
    seen, uniq = set(), []
    for href, lab in cands:
        if href not in seen:
            seen.add(href)
            uniq.append((href, lab))
    # disinformation items first, then other topical ones
    uniq.sort(key=lambda x: 0 if "dezinformacja" in topics(x[0].replace("-", " ") + " " + x[1]) else 1)
    log(f"  candidates: {len(uniq)}")
    with JsonlWriter("ec_pl") as w:
        for href, lab in uniq[: a.max]:
            url = BASE + href
            try:
                title, date, body = parse(fetch_text(url, min_delay=DELAY))
            except Exception as e:
                log("  skip", url, e)
                continue
            w.write(make_record(source="ec_pl", sid=href.rsplit("/", 1)[-1], publisher=PUB, url=url,
                                title=title or lab, text=body, published_at=date, license=LIC,
                                domain="poland.representation.ec.europa.eu",
                                tags=["Komisja Europejska", "UE"] + topics(title + " " + body[:1500]) +
                                     (["tłumaczenie maszynowe"] if "tłumaczeniem maszynowym" in body else [])))


if __name__ == "__main__":
    sys.exit(main())
