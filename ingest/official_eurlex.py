#!/usr/bin/env python3
"""EUR-Lex: key EU acts that recur in Polish disinformation (migration pact, AI Act, DSA,
2035 combustion-car phase-out, ETS2, nature restoration, tethered caps, cricket powder,
eIDAS wallet, EPBD, AML cash limit...).

1) Metadata + Polish title + link to the official Polish summary ("Streszczenia aktów
   prawnych UE", LEGISSUM) via the Publications Office CELLAR SPARQL endpoint
   https://publications.europa.eu/webapi/rdf/sparql
2) Polish summary text fetched from CELLAR (machine channel of the Publications Office):
   https://publications.europa.eu/resource/cellar/{uuid}.{expr}.{manif}/DOC_1  (xhtml5)
   NOTE: eur-lex.europa.eu itself answers automated clients with an AWS-WAF JS challenge
   (HTTP 202, empty body) — we do NOT try to bypass it; CELLAR is the documented route.
   Fallback when no summary exists: start + Art. 1 of the act's Polish XHTML from CELLAR.

Licence: EUR-Lex reuse under Commission Decision 2011/833/EU; summaries CC BY 4.0, metadata CC0.
Output: data/corpus/official_eurlex.jsonl
"""
from __future__ import annotations

import re
import sys
import urllib.parse

from official_common import JsonlWriter, fetch, fetch_json, html_to_text, log, make_record

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
LIC = ("© Unia Europejska, EUR-Lex — ponowne wykorzystanie wg decyzji 2011/833/UE; streszczenia CC BY 4.0, "
       "metadane CC0; autentyczne są tylko teksty opublikowane w Dz.U. UE")
PUB = "Unia Europejska — EUR-Lex (Urząd Publikacji UE)"

# CELEX -> tags
ACTS = {
    # Pact on Migration and Asylum (2024)
    "32024R1351": ["pakt migracyjny", "migracja", "solidarność", "relokacja"],
    "32024R1348": ["pakt migracyjny", "azyl", "procedura graniczna"],
    "32024R1349": ["pakt migracyjny", "powroty"],
    "32024R1356": ["pakt migracyjny", "kontrola przesiewowa", "granica"],
    "32024R1358": ["pakt migracyjny", "Eurodac"],
    "32024R1359": ["pakt migracyjny", "sytuacja kryzysowa", "instrumentalizacja"],
    "32024L1346": ["pakt migracyjny", "warunki przyjmowania"],
    "32024R1347": ["pakt migracyjny", "ochrona międzynarodowa"],
    "32001L0055": ["ochrona czasowa", "Ukraina", "uchodźcy"],
    "32022D0382": ["ochrona czasowa", "Ukraina", "uchodźcy"],
    # Digital
    "32024R1689": ["AI Act", "sztuczna inteligencja"],
    "32022R2065": ["DSA", "platformy", "cenzura", "dezinformacja"],
    "32024R0900": ["reklama polityczna", "wybory", "dezinformacja"],
    "32024R1083": ["wolność mediów", "media"],
    "32024R1183": ["eIDAS", "cyfrowa tożsamość", "portfel EUDI"],
    "32021R0953": ["COVID", "certyfikat", "szczepienia"],
    # Climate / energy / environment
    "32023R0851": ["samochody spalinowe", "2035", "CO2", "Zielony Ład"],
    "32023L0959": ["ETS", "ETS2", "ceny energii", "Zielony Ład"],
    "32023R0956": ["CBAM", "cło węglowe"],
    "32024R1991": ["odbudowa przyrody", "Zielony Ład", "rolnictwo"],
    "32023R1115": ["wylesianie", "EUDR", "rolnictwo"],
    "32024L1275": ["budynki", "EPBD", "piece", "Zielony Ład"],
    "32021R1119": ["prawo klimatyczne", "neutralność klimatyczna", "Zielony Ład"],
    "32019L0904": ["plastik", "nakrętki", "jednorazowe tworzywa"],
    # Food
    "32023R0005": ["owady w żywności", "świerszcz", "nowa żywność"],
    "32015R2283": ["nowa żywność", "owady w żywności"],
    # Money / funds / sanctions
    "32024R1624": ["gotówka", "limit płatności gotówkowych", "AML"],
    "32021R0241": ["KPO", "fundusze UE", "Instrument na rzecz Odbudowy"],
    "32020R2092": ["praworządność", "warunkowość", "fundusze UE"],
    "32014R0833": ["sankcje", "Rosja"],
}


def sparql_meta(celexes: list[str]) -> dict:
    vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes)
    q = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?w ?date ?force ?title ?s ?sumid ?sumdate WHERE {{
  VALUES ?celex {{ {vals} }}
  ?w cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?w cdm:work_date_document ?date }}
  OPTIONAL {{ ?w cdm:resource_legal_in-force ?force }}
  OPTIONAL {{ ?e cdm:expression_belongs_to_work ?w ;
               cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/POL> ;
               cdm:expression_title ?title . }}
  OPTIONAL {{ ?s cdm:summary_summarizes_work ?w ; cdm:summary_legislation_eu_id_legissum ?sumid .
             OPTIONAL {{ ?s cdm:work_date_document ?sumdate }} }}
}}"""
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q})
    d = fetch_json(url, accept="application/sparql-results+json", min_delay=2)
    out: dict[str, dict] = {}
    for b in d["results"]["bindings"]:
        c = b["celex"]["value"]
        m = out.setdefault(c, {"sums": {}, "work": b["w"]["value"]})
        for k in ("date", "force", "title"):
            if k in b and not m.get(k):
                m[k] = b[k]["value"]
        if "sumid" in b:
            m["sums"][b["sumid"]["value"]] = (b.get("sumdate", {}).get("value", ""), b["s"]["value"])
    return out


def _sparql(q: str) -> list[dict]:
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q})
    d = fetch_json(url, accept="application/sparql-results+json", min_delay=2)
    return [{k: v["value"] for k, v in b.items()} for b in d["results"]["bindings"]]


def pl_items(work_uri: str, types=("xhtml5", "xhtml", "html")) -> list[str]:
    rows = _sparql(f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?type ?item WHERE {{
  ?e cdm:expression_belongs_to_work <{work_uri}> ;
     cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/POL> .
  ?m cdm:manifestation_manifests_expression ?e ; cdm:manifestation_type ?type .
  ?item cdm:item_belongs_to_manifestation ?m .
}}""")
    order = {t: i for i, t in enumerate(types)}
    rows = [r for r in rows if r["type"] in order]
    rows.sort(key=lambda r: (order[r["type"]], r["item"]))
    return [r["item"].replace("http://", "https://", 1) for r in rows]


def cellar_text(item_url: str) -> str:
    h = fetch(item_url, timeout=180).decode("utf-8", "replace")
    return html_to_text(re.sub(r"(?is)<head.*?</head>", " ", h))


def summary_text(sum_work: str) -> tuple[str, str]:
    items = pl_items(sum_work)
    if not items:
        return "", ""
    t = cellar_text(items[0])
    for marker in ("DOKUMENTY POWIĄZANE", "Ostatnia aktualizacja:"):
        j = t.find(marker)
        if j > 1500:
            t = t[:j + 80]
            break
    return t, items[0]


def act_article1(work_uri: str) -> tuple[str, str]:
    items = pl_items(work_uri)
    if not items:
        return "", ""
    t = cellar_text(items[0])
    m = re.search(r"Artykuł\s+1\s", t)
    seg = t[m.start(): m.start() + 2500] if m else ""
    n = re.search(r"\sArtykuł\s+2\s", seg)
    art = (seg[: n.start()] if n else seg)[:1300]
    return t[: 3900 - len(art)] + ("\n[…]\n" + art if art else ""), items[0]


def main():
    celexes = list(ACTS)
    meta = {}
    for i in range(0, len(celexes), 15):
        meta.update(sparql_meta(celexes[i:i + 15]))
    with JsonlWriter("eurlex") as w:
        for c in celexes:
            m = meta.get(c, {"sums": {}, "work": None})
            title = m.get("title") or c
            act_url = f"https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:{c}"
            head = [f"Akt UE: {title}", f"CELEX: {c}; data dokumentu: {m.get('date', 'b.d.')}; "
                    f"w mocy (CELLAR): {'tak' if m.get('force') in ('1', 'true') else ('nie' if m.get('force') else 'b.d.')}",
                    f"Tekst aktu (PL): {act_url}"]
            body, used, sum_url = "", "", None
            try:
                if m["sums"]:
                    sid, (sdate, swork) = sorted(m["sums"].items(), key=lambda kv: kv[1][0] or "")[-1]
                    body, used = summary_text(swork)
                    sum_url = f"https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=LEGISSUM:{sid}"
                    head.append(f"Streszczenie EUR-Lex LEGISSUM:{sid} (wersja z {sdate or 'b.d.'}): {sum_url}")
                if not body and m.get("work"):
                    body, used = act_article1(m["work"])
                    head.append("Brak oficjalnego streszczenia w języku polskim — poniżej początek aktu i art. 1.")
            except Exception as e:
                log(f"  text failed {c}: {e}")
            if used:
                head.append(f"Pobrano z CELLAR: {used}")
            rec = make_record(source="eurlex", sid=c, publisher=PUB, url=sum_url or act_url,
                              title=title, text="\n".join(head) + "\n" + body, published_at=m.get("date"),
                              license=LIC, domain="eur-lex.europa.eu",
                              tags=["UE", "prawo UE", "EUR-Lex", "rozporządzenie" if "R" in c[5:6] else
                                    ("dyrektywa" if "L" in c[5:6] else "decyzja")] + ACTS[c])
            w.write(rec)
            log(f"  {c}: {len(rec['text'])} chars, summary={'yes' if m['sums'] else 'no'}")


if __name__ == "__main__":
    sys.exit(main())
