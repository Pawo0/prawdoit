#!/usr/bin/env python3
"""Harvest gov.pl: MSZ news + strategic-communication pages, ministry myth/debunk
pages (vaccines, energy prices, CPK, migration, food, drones...), RCB alerts and
"prawdziwe czy fałszywe komunikaty", UdSC migration statistics.

gov.pl robots.txt: "User-Agent: * / Allow: /" (checked at runtime anyway).
Licence: gov.pl text content CC BY-SA 4.0 (https://www.gov.pl/web/gov/warunki-korzystania).

Outputs:
  data/corpus/official_govpl_msz.jsonl    (MSZ news, comms pages)
  data/corpus/official_govpl_myths.jsonl  (debunk / myth pages of ministries + RCB + UdSC)

Usage: python ingest/official_govpl.py [--msz-max 400] [--since 2025-01-01] [--only msz|myths]
"""
from __future__ import annotations

import argparse
import re
import sys

from official_common import (JsonlWriter, RobotsDisallowed, fetch_text, html_to_text, log,
                             make_record, pl_date)

BASE = "https://www.gov.pl"
LICENSE = "CC BY-SA 4.0 — treści gov.pl (gov.pl/web/gov/warunki-korzystania); podać źródło"

PUBLISHERS = {
    "dyplomacja": "Ministerstwo Spraw Zagranicznych",
    "rcb": "Rządowe Centrum Bezpieczeństwa",
    "gis": "Główny Inspektorat Sanitarny",
    "zdrowie": "Ministerstwo Zdrowia",
    "klimat": "Ministerstwo Klimatu i Środowiska",
    "infrastruktura": "Ministerstwo Infrastruktury",
    "obrona-narodowa": "Ministerstwo Obrony Narodowej",
    "rolnictwo": "Ministerstwo Rolnictwa i Rozwoju Wsi",
    "edukacja": "Ministerstwo Edukacji Narodowej",
    "udsc": "Urząd do Spraw Cudzoziemców",
    "cyfryzacja": "Ministerstwo Cyfryzacji",
    "premier": "Kancelaria Prezesa Rady Ministrów",
    "fundusze-regiony": "Ministerstwo Funduszy i Polityki Regionalnej",
    "mswia": "Ministerstwo Spraw Wewnętrznych i Administracji",
    "sluzby-specjalne": "Minister Koordynator Służb Specjalnych",
}

# Curated from the units' /mapa-strony (site maps) on 2026-11-21: pages whose slug
# signals debunking (mity, fakty, dezinformacja, nieprawdziwe, prostujemy, fake news).
# (path, topic tags)
MYTH_PAGES: list[tuple[str, list[str]]] = [
    # MSZ strategic communication / FIMI
    ("/web/dyplomacja/komunikacja-strategiczna", ["dezinformacja", "FIMI"]),
    ("/web/dyplomacja/pelnomocnik", ["dezinformacja", "FIMI"]),
    ("/web/dyplomacja/zespol-miedzyresortowy", ["dezinformacja", "FIMI"]),
    ("/web/dyplomacja/przyklady-negatywnych-dzialan-i-mowy-nienawisci-rosji2", ["dezinformacja", "Rosja", "FIMI"]),
    ("/web/dyplomacja/zlosliwe-boty-w-sluzbie-dezinformacji-miedzynarodowej", ["dezinformacja", "boty", "FIMI"]),
    ("/web/dyplomacja/kampania-informacyjna-resilient-together", ["dezinformacja", "odporność"]),
    ("/web/dyplomacja/dzialania-miedzynarodowe", ["dezinformacja", "UE"]),
    # RCB
    ("/web/rcb/prawdziwe-czy-falszywe-komunikaty", ["fałszywe komunikaty", "alert RCB", "bezpieczeństwo"]),
    ("/web/rcb/alertrcb", ["alert RCB", "bezpieczeństwo"]),
    ("/web/rcb/odporni-na-dezinformacje--kolejny-odcinek-akademii-rcb", ["dezinformacja", "RCB"]),
    ("/web/rcb/stopnie-alarmowe2", ["stopnie alarmowe", "bezpieczeństwo"]),
    ("/web/rcb/sygnaly-alarmowe3", ["syreny", "bezpieczeństwo"]),
    # Health / vaccines
    ("/web/gis/mity-na-temat-szczepien", ["szczepienia", "zdrowie", "mity"]),
    ("/web/gis/poznaj-fakty-i-mity-o-szczepieniach", ["szczepienia", "zdrowie", "mity"]),
    ("/web/gis/najczesciej-powielane-nieprawdziwe-informacje-dot-szczepien-ochronnych", ["szczepienia", "zdrowie", "mity"]),
    ("/web/gis/poznaj-przyklady-falszywych-informacji--fake-newsow", ["zdrowie", "fake news"]),
    ("/web/gis/jak-przeciwdzialac-dezinformacji", ["zdrowie", "dezinformacja"]),
    ("/web/gis/co-to-jest-dezinformacja--badz-swiadomy-i-nie-daj-sie-zwiesc", ["zdrowie", "dezinformacja"]),
    ("/web/gis/gis-i-nask-lacza-sily-przeciw-dezinformacji-medycznej", ["zdrowie", "dezinformacja"]),
    ("/web/gis/europejski-tydzien-szczepien-2026-razem-dla-zdrowia-i-odpornosci-na-dezinformacje", ["szczepienia", "zdrowie"]),
    ("/web/gis/e-papierosy-to-manipulacja---briefing-prasowy", ["zdrowie", "e-papierosy"]),
    ("/web/zdrowie/fakty-i-mity", ["zdrowie", "mity"]),
    ("/web/zdrowie/fakty-i-mity-dotyczace-krwiodawstwa", ["zdrowie", "krwiodawstwo", "mity"]),
    ("/web/zdrowie/zaufanie-do-systemu-ochrony-zdrowia-zaczyna-sie-od-rzetelnych-informacji-w-swiatowym-dniu-zdrowia-mowimy-stop-dezinformacji", ["zdrowie", "dezinformacja"]),
    ("/web/zdrowie/nie-okradaj-sie-ze-zdrowia-falszywe-leki-to-prawdziwe-zagrozenie", ["zdrowie", "fałszywe leki"]),
    # Energy / climate
    ("/web/klimat/ostrzegamy-przed-falszywymi-informacjami-o-ogromnych-podwyzkach-cen-energii", ["ceny energii", "energia", "fake news"]),
    ("/web/klimat/ostrzegamy-kolejna-fala-falszywych-informacji-na-temat-podwyzek-cen-pradu-i-gazu", ["ceny energii", "gaz", "fake news"]),
    ("/web/klimat/dezinforadar-fakty-i-mity-na-temat-pomp-ciepla", ["pompy ciepła", "energia", "mity"]),
    ("/web/klimat/fakty-i-mity-na-temat-pomp-ciepla-pod-lupa-ekspertow-i-praktykow", ["pompy ciepła", "energia", "mity"]),
    ("/web/klimat/dezinformacja-na-temat-pomp-ciepla-na-radarze-ministerstwa-klimatu-i-srodowiska", ["pompy ciepła", "dezinformacja"]),
    ("/web/klimat/dezinformacja-na-temat-systemu-kaucyjnego-jak-rozpoznawac-mity-i-oddzielac-je-od-faktow", ["system kaucyjny", "mity"]),
    ("/web/klimat/dezinformacja-kontra-fakty-eksperci-i-administracja-wspolnie-o-systemie-kaucyjnym", ["system kaucyjny", "mity"]),
    ("/web/klimat/11-pojemnikow-na-smieci-w-naszych-domach-to-mit", ["odpady", "UE", "mity"]),
    ("/web/klimat/dezinfo-narracje", ["klimat", "dezinformacja", "narracje"]),
    ("/web/klimat/dezinfo-qa", ["klimat", "dezinformacja"]),
    ("/web/klimat/dezinfo-techniki", ["dezinformacja", "techniki manipulacji"]),
    ("/web/klimat/dezinfo-sprawdzam", ["dezinformacja", "weryfikacja"]),
    ("/web/klimat/dezinfolab-oze-pod-ostrzalem-dezinformacji-jak-falszywe-narracje-wykorzystuja-lek-koszty-i-brak-zaufania", ["OZE", "energia", "dezinformacja"]),
    ("/web/klimat/dezinforadar-plaga-fake-newsow-na-temat-wilkow-i-niedzwiedzi", ["przyroda", "fake news"]),
    ("/web/klimat/nie-wierz-fakenewsom-o-zatrzymaniu-zeglugi-na-odrze", ["Odra", "fake news"]),
    ("/web/klimat/odbudowa-zasobow-przyrody-nrl-dezinfo", ["Nature Restoration Law", "UE", "dezinformacja"]),
    ("/web/klimat/fala-dezinformacji-o-koniach-nad-morskim-okiem", ["przyroda", "dezinformacja"]),
    # Infrastructure / CPK / airspace
    ("/web/infrastruktura/mi-dementuje-nieprawdziwe-informacje-ws-rozmow-nt-cpk", ["CPK", "dementi"]),
    ("/web/infrastruktura/prostujemy-klamstwa-i-manipulacje", ["CPK", "infrastruktura", "dementi"]),
    ("/web/infrastruktura/komunikat-w-zwiazku-z-nieprawdziwymi-informacjami-na-temat-zamkniecia-przestrzeni-powietrznej", ["przestrzeń powietrzna", "dementi"]),
    ("/web/infrastruktura/uwaga-na-dezinformacje-zwiazana-z-naruszeniem-polskiej-przestrzeni-powietrznej-przez-drony", ["drony", "Rosja", "dezinformacja"]),
    # Defence
    ("/web/obrona-narodowa/oswiadczenie-mon-w-sprawie-falszywych-informacji-o-planowanych-cieciach-wydatkow-na-obronnosc", ["obronność", "budżet", "dementi"]),
    ("/web/obrona-narodowa/kontrakt-na-wisle-sukcesem-prostujemy-przeklamania-opozycji-", ["obronność", "Wisła", "dementi"]),
    ("/web/obrona-narodowa/sprostowanie", ["obronność", "sprostowanie"]),
    ("/web/obrona-narodowa/musimy-budowac-odpornosc-spoleczenstwa-na-dezinformacje", ["obronność", "dezinformacja"]),
    # Agriculture / food
    ("/web/rolnictwo/stop-dezinformacji-nowe-przepisy-o-srodkach-ochrony-roslin-nie-dotycza-dzialkowcow", ["rolnictwo", "działkowcy", "dementi"]),
    ("/web/rolnictwo/przeciw-dezinformacji-o-polskiej-zywnosci", ["żywność", "dezinformacja"]),
    ("/web/rolnictwo/stop-dezinformacji-zywnosciowej", ["żywność", "dezinformacja"]),
    ("/web/rolnictwo/uwaga-na-manipulacje-ws-badan-zawartosci-azotynow-i-azotanow-w-zywnosci-pochodzenia-zwierzecego", ["żywność", "manipulacja"]),
    # Education
    ("/web/edukacja/oswiadczenie-mein-w-sprawie-nieprawdziwych-informacji-dotyczacych-wynagrodzen-nauczycieli", ["edukacja", "wynagrodzenia nauczycieli", "dementi"]),
    ("/web/edukacja/uwaga-na-dezinformacje-zwiazana-z-naruszeniem-polskiej-przestrzeni-powietrznej-przez-drony", ["drony", "dezinformacja"]),
    ("/web/edukacja/dezinformacja", ["dezinformacja", "edukacja medialna"]),
    # Migration / foreigners (UdSC)
    ("/web/udsc/stop-dezinformacji", ["migracja", "cudzoziemcy", "dezinformacja"]),
    ("/web/udsc/uwaga-na-falszywe-wiadomosci", ["cudzoziemcy", "fałszywe wiadomości"]),
    ("/web/udsc/ostrzezenie-przed-falszywymi-wezwaniami-do-sluzby-wojskowej", ["Ukraina", "fałszywe wezwania"]),
    ("/web/udsc/obywatele-ukrainy-w-polsce--aktualne-dane-migracyjne", ["Ukraina", "migracja", "statystyka"]),
    ("/web/udsc/bialorusini-w-polsce--aktualne-dane-statystyczne", ["Białoruś", "migracja", "statystyka"]),
    ("/web/udsc/300-tys-obywateli-ukrainy-z-waznymi-kartami-pobytu", ["Ukraina", "migracja", "statystyka"]),
    # Digital affairs
    ("/web/cyfryzacja/dezinformacja--co-warto-wiedziec", ["dezinformacja", "cyfryzacja"]),
    ("/web/cyfryzacja/powiedz-sprawdzam-nie-daj-sie-manipulacjom-w-internecie", ["dezinformacja", "weryfikacja"]),
    ("/web/sluzby-specjalne/trolle-w-natarciu", ["dezinformacja", "trolle", "Rosja"]),
]

# Listing pages harvested for recent items: (unit, listing slug, max items, tags)
LISTINGS = [
    ("rcb", "komunikaty", 25, ["RCB", "komunikat", "bezpieczeństwo"]),
    ("udsc", "aktualnosci", 10, ["cudzoziemcy", "migracja"]),
]


def parse_listing(html: str) -> list[dict]:
    """News-list items (date, href, title, optional intro). The intro search is bounded to the current item —
    an unbounded `.*?<div class="intro">` swallowed every following item when an item had no intro (kgpsp: 1 of 20)."""
    items = []
    for m in re.finditer(
            r'<span class="date">\s*([\d.]+)\s*</span>.*?<div class="title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>'
            r'(?:(?:(?!<span class="date">).)*?<div class="intro">(.*?)</div>)?', html, flags=re.S):
        date, href, title, intro = m.groups()
        items.append({"date": pl_date(date), "href": href, "title": html_to_text(title),
                      "intro": html_to_text(intro or "")})
    return items


def parse_article(html: str) -> dict:
    out = {}
    m = re.search(r'<meta property="og:site_name" content="([^"]+)"', html)
    out["site_name"] = m.group(1) if m else None
    m = re.search(r'<article[^>]*id="main-content"[^>]*>(.*?)</article>', html, flags=re.S) or \
        re.search(r'<article[^>]*>(.*?)</article>', html, flags=re.S)
    art = m.group(1) if m else ""
    t = re.search(r"<h2[^>]*>(.*?)</h2>", art, flags=re.S)
    out["title"] = html_to_text(t.group(1)) if t else None
    if not out["title"]:
        t = re.search(r'<meta property="og:title"\s+content="([^"]+)"', html)
        out["title"] = t.group(1).split(" - ")[0] if t else None
    d = re.search(r'<p class="event-date">\s*([^<]+)</p>', art)
    out["date"] = pl_date(d.group(1)) if d else None
    if not out["date"]:
        d = re.search(r'class="date"[^>]*>\s*([\d.]{8,10})', art)
        out["date"] = pl_date(d.group(1)) if d else None
    intro = re.search(r'<p class="intro">(.*?)</p>', art, flags=re.S)
    out["intro"] = html_to_text(intro.group(1)) if intro else ""
    # body: all editor-content blocks; fall back to whole article
    bodies = re.findall(r'<div class="editor-content">(.*?)</div>\s*</div>', art, flags=re.S)
    body = "\n".join(html_to_text(b) for b in bodies) if bodies else ""
    if len(body) < 200:
        cleaned = re.sub(r'<h2[^>]*>.*?</h2>', ' ', art, flags=re.S)
        cleaned = re.sub(r'<p class="event-date">.*?</p>', ' ', cleaned, flags=re.S)
        body = html_to_text(cleaned)
    out["body"] = body
    # list-type pages (e.g. "komunikacja-strategiczna"): keep child links titles
    return out


def unit_of(path: str) -> str:
    m = re.match(r"/web/([^/]+)/", path)
    return m.group(1) if m else "gov"


def harvest_article(path: str, tags: list[str], source: str, listing_item: dict | None = None):
    url = BASE + path
    try:
        html = fetch_text(url)
    except RobotsDisallowed:
        log("  robots disallow", url)
        return None
    except Exception as e:
        log(f"  skip {url}: {e}")
        return None
    a = parse_article(html)
    unit = unit_of(path)
    title = a["title"] or (listing_item or {}).get("title") or path.rsplit("/", 1)[-1]
    intro = a["intro"] or (listing_item or {}).get("intro", "")
    body = a["body"]
    if intro and body.startswith(intro[:80]):
        intro = ""
    text = (intro + "\n" + body).strip() if intro else body
    pub = a["date"] or (listing_item or {}).get("date")
    publisher = PUBLISHERS.get(unit) or a["site_name"] or "gov.pl"
    slug = path.rsplit("/", 1)[-1]
    return make_record(source=source, sid=f"{unit}/{slug}", publisher=publisher, url=url,
                       title=title, text=text, published_at=pub, license=LICENSE,
                       tags=["gov.pl", unit] + tags, domain="gov.pl")


def harvest_msz(since: str, max_items: int):
    with JsonlWriter("govpl_msz") as w:
        page, seen = 1, 0
        stop = False
        while not stop and seen < max_items and page <= 40:
            url = f"{BASE}/web/dyplomacja/aktualnosci?page={page}&size=10"
            try:
                items = parse_listing(fetch_text(url))
            except Exception as e:
                log("listing failed", url, e)
                break
            if not items:
                break
            for it in items:
                if it["date"] and it["date"] < since:
                    stop = True
                    break
                if seen >= max_items:
                    break
                rec = harvest_article(it["href"], ["MSZ", "aktualności", "polityka zagraniczna"],
                                      "govpl_msz", it)
                if rec and w.write(rec):
                    seen += 1
            log(f"  MSZ listing page {page}: total {seen}")
            page += 1


def harvest_myths():
    with JsonlWriter("govpl_myths") as w:
        for path, tags in MYTH_PAGES:
            src = "govpl_msz" if path.startswith("/web/dyplomacja/") else "govpl_myths"
            rec = harvest_article(path, tags + ["debunk"], src)
            if rec:
                w.write(rec)
        for unit, slug, n, tags in LISTINGS:
            try:
                items = parse_listing(fetch_text(f"{BASE}/web/{unit}/{slug}"))
            except Exception as e:
                log("listing failed", unit, slug, e)
                continue
            for it in items[:n]:
                rec = harvest_article(it["href"], tags, "govpl_" + unit, it)
                if rec:
                    w.write(rec)
            # second page for RCB alerts
            if len(items) >= 10 and n > 10:
                try:
                    items2 = parse_listing(fetch_text(f"{BASE}/web/{unit}/{slug}?page=2&size=10"))
                except Exception:
                    items2 = []
                for it in items2[: n - 10]:
                    rec = harvest_article(it["href"], tags, "govpl_" + unit, it)
                    if rec:
                        w.write(rec)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--msz-max", type=int, default=400)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--only", choices=["msz", "myths"])
    a = ap.parse_args(argv)
    if a.only in (None, "msz"):
        harvest_msz(a.since, a.msz_max)
    if a.only in (None, "myths"):
        harvest_myths()


if __name__ == "__main__":
    sys.exit(main())
