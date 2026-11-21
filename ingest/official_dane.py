#!/usr/bin/env python3
"""dane.gov.pl (Polish open-data portal) — dataset "pointer cards" for topics that recur in
disinformation (foreigners/migration, border, 800+, ZUS, vaccinations, elections, crime,
energy, state budget, Ukraine aid...). Each card = dataset title, publisher institution,
description, update frequency, licence, last modification and its resources (format + URL),
so the RAG layer can cite *where* the official numbers live and the live-tools layer can
fetch them.

API: https://api.dane.gov.pl/1.4  (JSON:API, no auth)
  GET /datasets?q=..&per_page=..&sort=-verified
  GET /datasets/{id}/resources
Terms: dane.gov.pl Regulamin §5 — reuse of data & metadata; per-dataset licence (mostly CC0 1.0).
Output: data/corpus/official_dane.jsonl
"""
from __future__ import annotations

import re
import sys
import urllib.parse

from official_common import JsonlWriter, fetch_json, html_to_text, log, make_record

API = "https://api.dane.gov.pl/1.4"
TOPICS = {
    "cudzoziemcy": ["migracja", "cudzoziemcy"],
    "Straż Graniczna": ["granica", "migracja"],
    "ochrona międzynarodowa": ["azyl", "migracja"],
    "obywatele Ukrainy": ["Ukraina", "uchodźcy"],
    "świadczenie wychowawcze": ["800+", "rodzina"],
    "emerytury": ["ZUS", "emerytury"],
    "szczepienia": ["szczepienia", "zdrowie"],
    "Dane Wyborcze": ["wybory", "PKW"],
    "przestępstwa": ["przestępczość", "bezpieczeństwo"],
    "energia elektryczna": ["ceny energii", "energia"],
    "budżet państwa": ["budżet", "finanse publiczne"],
    "Krajowy Plan Odbudowy": ["KPO", "fundusze UE"],
}
PER_TOPIC = 4
LOCAL_BODY = re.compile(r"Urząd Miasta|Urząd Miejski|Miejski|Gmin|Powiat|Starostw|Miasto ", re.I)
# keep only datasets published by public bodies (the portal also hosts thousands of
# developer price lists published under the 2025 housing-price transparency rules)
PUBLIC_BODY = re.compile(r"Ministerstw|Minister|Urząd|Urzad|Komenda|Główn|Glown|Narodow|Zakład Ubezpieczeń|Centrum|Państwow|"
                         r"Kancelari|Instytut|Agencj|Biuro|Rzecznik|Krajow|Sejm|Senat|Inspektor|Straż|Policj|Fundusz|"
                         r"Wojewod|Marszał|Prezes|Rada|Bank Polski|Sąd|Prokuratur|Krajowe Biuro Wyborcze|Kasa Rolniczego", re.I)


def strip_mark(s: str) -> str:
    return html_to_text(re.sub(r"</?mark>", "", s or ""))


def main():
    with JsonlWriter("dane") as w:
        for q, tags in TOPICS.items():
            url = f"{API}/datasets?" + urllib.parse.urlencode({"q": q, "per_page": 30, "sort": "relevance",
                                                                "include": "institution"})
            try:
                d = fetch_json(url)
            except Exception as e:
                log("  search failed", q, e)
                continue
            inst = {i["id"]: i["attributes"].get("title") for i in d.get("included", []) if i.get("type") == "institution"}
            kept = 0
            for it in d.get("data", []):
                a = it["attributes"]
                iid = ((it.get("relationships", {}).get("institution") or {}).get("data") or {}).get("id")
                publisher = inst.get(iid) or "dane.gov.pl"
                if (kept >= PER_TOPIC or not PUBLIC_BODY.search(publisher) or LOCAL_BODY.search(publisher)
                        or re.search(r"(?i)ceny ofertowe|dewelop", a.get("title") or "")):
                    continue
                kept += 1
                ds_url = f"https://dane.gov.pl/pl/dataset/{it['id']},{a.get('slug', '')}"
                try:
                    r = fetch_json(f"{API}/datasets/{it['id']}/resources?per_page=8&sort=-data_date")
                    res = r.get("data", [])
                except Exception:
                    res = []
                lines = []
                for x in res[:8]:
                    ra = x["attributes"]
                    lines.append(f"- {strip_mark(ra.get('title'))} [{ra.get('format') or ra.get('media_type') or '?'}; "
                                 f"dane z {str(ra.get('data_date') or '')[:10] or 'b.d.'}; zm. {str(ra.get('modified') or '')[:10]}]: "
                                 f"{ra.get('download_url') or ra.get('link') or ''}")
                text = (f"Zbiór danych publicznych (dane.gov.pl): {strip_mark(a.get('title'))}. Udostępnia: {publisher}. "
                        f"Częstotliwość aktualizacji: {a.get('update_frequency') or 'b.d.'}; ostatnia modyfikacja: "
                        f"{str(a.get('modified') or '')[:10]}; licencja: {a.get('license_name') or a.get('license_chosen') or 'b.d.'}.\n"
                        f"Opis: {strip_mark(a.get('notes'))[:1600]}\n"
                        f"Słowa kluczowe: {', '.join(a.get('keywords') or [])}\n"
                        f"Zasoby (najnowsze):\n" + "\n".join(lines) + f"\nAPI: {API}/datasets/{it['id']}")
                w.write(make_record(source="dane", sid=str(it["id"]), publisher=publisher, url=ds_url,
                                    title=strip_mark(a.get("title")), text=text,
                                    published_at=str(a.get("modified") or "")[:10] or None,
                                    license=f"{a.get('license_name') or 'licencja wg zbioru'} — dane.gov.pl (Regulamin §5, ustawa o otwartych danych)",
                                    domain="dane.gov.pl", tags=["dane.gov.pl", "dane publiczne", "zbiór danych"] + tags))


if __name__ == "__main__":
    sys.exit(main())
