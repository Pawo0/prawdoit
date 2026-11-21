#!/usr/bin/env python3
"""PKW election-result fact sheets from the official announcements ("Obwieszczenie
Państwowej Komisji Wyborczej o wynikach ...") published in Dziennik Ustaw, fetched via the
Sejm ELI API (stable, machine-readable; wybory.gov.pl result pages are a JS app).

For each announcement we keep the national-level key passages: turnout, valid votes,
per-candidate / per-committee results, seats, who was elected.

Licence: official documents — not subject to copyright (art. 4 pr. aut.).
Output: data/corpus/official_pkw.jsonl
"""
from __future__ import annotations

import re
import sys

from official_common import JsonlWriter, log, make_record
from official_eli import get_meta, get_text, isap_url

LIC = "Dokument urzędowy (obwieszczenie PKW, Dz.U.) — nie podlega prawu autorskiemu (art. 4 pr. aut.)"
PUB = "Państwowa Komisja Wyborcza"

ANNOUNCEMENTS = [
    ("DU/2025/652", "wybory prezydenckie 2025, I tura", ["wybory prezydenckie", "2025"], "https://wybory.gov.pl/prezydent2025/pl/"),
    ("DU/2025/714", "wybory prezydenckie 2025, II tura", ["wybory prezydenckie", "2025", "Nawrocki", "Trzaskowski"], "https://wybory.gov.pl/prezydent2025/pl/"),
    ("DU/2024/853", "wybory do Parlamentu Europejskiego 2024", ["Parlament Europejski", "2024"], "https://wybory.gov.pl/pe2024/pl/"),
    ("DU/2023/2234", "wybory do Sejmu 2023", ["Sejm", "wybory parlamentarne", "2023"], "https://wybory.gov.pl/sejmsenat2023/pl/"),
    ("DU/2023/2235", "wybory do Senatu 2023", ["Senat", "wybory parlamentarne", "2023"], "https://wybory.gov.pl/sejmsenat2023/pl/"),
    ("DU/2023/2236", "referendum ogólnokrajowe 2023", ["referendum", "2023"], "https://wybory.gov.pl/sejmsenat2023/pl/"),
    ("DU/2020/1163", "wybory prezydenckie 2020, I tura", ["wybory prezydenckie", "2020"], "https://prezydent20200628.pkw.gov.pl/"),
    ("DU/2020/1238", "wybory prezydenckie 2020, II tura", ["wybory prezydenckie", "2020", "Duda", "Trzaskowski"], "https://prezydent20200628.pkw.gov.pl/"),
    ("DU/2019/1955", "wybory do Sejmu 2019", ["Sejm", "wybory parlamentarne", "2019"], "https://sejmsenat2019.pkw.gov.pl/"),
    ("DU/2019/989", "wybory do Parlamentu Europejskiego 2019", ["Parlament Europejski", "2019"], "https://pe2019.pkw.gov.pl/"),
]

# (pattern, chars before, chars after)
PATTERNS = [
    (r"[Ll]iczba (?:osób|wyborców) uprawnionych do głosowania", 0, 160),
    (r"[Ff]rekwencja(?: wyborcza)? wyniosła", 0, 60),
    (r"[Ll]iczba głosów ważnych", 0, 160),
    (r"kandydaci otrzymali następujące liczby", 0, 1900),
    (r"Na poszczególne listy kandydatów oddano", 0, 2300),
    (r"następującą liczbę mandatów", 0, 1300),
    (r"został wybran[ya]|zostali wybrani|wybrany został", 250, 120),
    (r"ponowne głosowanie|ponownego głosowania", 0, 0),
    (r"(?:wynik referendum|referendum) (?:nie )?(?:jest|był) wiążący|wzięło udział|uczestniczyło w referendum", 300, 250),
    (r"[Nn]a pytanie (?:pierwsze|drugie|trzecie|czwarte|nr)", 0, 450),
]


def key_passages(text: str) -> str:
    flat = re.sub(r"\s*\n\s*", " ", text)
    flat = re.sub(r"\s{2,}", " ", flat)
    spans = []
    for pat, before, after in PATTERNS:
        if after == 0:
            continue
        for m in list(re.finditer(pat, flat))[:2]:
            spans.append((max(0, m.start() - before), min(len(flat), m.end() + after)))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1] + 20:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return "\n[…] ".join(flat[s:e].strip() for s, e in merged)


def main():
    with JsonlWriter("pkw") as w:
        for eli, label, tags, page in ANNOUNCEMENTS:
            try:
                meta = get_meta(eli)
                text, turl = get_text(eli, meta)
            except Exception as e:
                log("  FAIL", eli, e)
                continue
            head = (f"{meta['title']} ({meta.get('displayAddress')}). Oficjalne wyniki — {label}. "
                    f"Źródło: obwieszczenie PKW w Dzienniku Ustaw, ELI {eli}, tekst: {turl}; "
                    f"serwis wyników PKW: {page}")
            body = key_passages(text)
            rec = make_record(source="pkw", sid=eli, publisher=PUB, url=isap_url(meta), title=meta["title"],
                              text=head + "\nKluczowe dane:\n" + body,
                              published_at=meta.get("promulgation") or meta.get("announcementDate"),
                              license=LIC, domain="isap.sejm.gov.pl",
                              tags=["PKW", "wybory", "wyniki wyborów", "fact-card"] + tags)
            w.write(rec)
            log(f"  {eli}: {len(rec['text'])} chars")


if __name__ == "__main__":
    sys.exit(main())
