#!/usr/bin/env python3
"""Harvest key Polish statutes (ISAP data via the Sejm ELI API) relevant to frequent
disinformation topics: metadata + status + latest consolidated text + Art. 1 scope +
keyword-focused excerpts.  Also exports helpers used by official_pkw.py.

API (no auth, JSON): https://api.sejm.gov.pl/eli
  GET /eli/acts/{publisher}/{year}/{pos}               metadata, references, texts
  GET /eli/acts/{publisher}/{year}/{pos}/text.html     HTML text (when textHTML=true)
  GET /eli/acts/{publisher}/{year}/{pos}/text.pdf      PDF text
  GET /eli/acts/search?title=..&type=Ustawa&year=..    search
Licence: legal acts are not subject to copyright (art. 4 pkt 1 ustawy o prawie autorskim).

Output: data/corpus/official_eli.jsonl
"""
from __future__ import annotations

import re
import sys

from official_common import (JsonlWriter, clean_ws, fetch, fetch_json, html_to_text, log,
                             make_record, pdf_to_text)

API = "https://api.sejm.gov.pl/eli/acts"
LICENSE = ("Akt normatywny — nie podlega prawu autorskiemu (art. 4 pkt 1 pr. aut.); "
           "metadane: ELI API Sejmu RP (api.sejm.gov.pl), podać źródło")

# (ELI, focus terms, tags) — topics recurring in Polish disinformation
ACTS: list[tuple[str, list[str], list[str]]] = [
    ("DU/1997/483", ["Art. 90.", "Art. 227.", "Art. 55."], ["Konstytucja", "UE", "NBP", "złoty"]),
    ("DU/2016/195", ["800 zł", "cudzoziem", "Ukrain"], ["800+", "świadczenie wychowawcze", "rodzina"]),
    ("DU/2022/583", ["800", "numer PESEL", "pobyt"], ["Ukraina", "uchodźcy", "pomoc"]),
    ("DU/2026/203", ["wygas", "świadcze", "PESEL"], ["Ukraina", "uchodźcy", "pomoc", "2026"]),
    ("DU/2025/1301", ["aktywności zawodowej", "świadczenie wychowawcze", "cudzoziem"], ["800+", "cudzoziemcy", "Ukraina"]),
    ("DU/2013/1650", ["zezwolenia na pobyt czasowy", "wiz"], ["cudzoziemcy", "migracja"]),
    ("DU/2025/1794", ["cudzoziem"], ["cudzoziemcy", "migracja", "2025"]),
    ("DU/2003/1176", ["ochrony międzynarodowej", "czasowe ograniczenie"], ["azyl", "migracja", "pakt migracyjny"]),
    ("DU/2025/389", ["czasowe ograniczenie", "60 dni", "instrumentalizac"], ["azyl", "granica", "Białoruś", "migracja"]),
    ("DU/2008/1570", ["obowiązkowym szczepieniom", "szczepień ochronnych"], ["szczepienia", "zdrowie"]),
    ("DU/2018/1089", ["Centralny Port Komunikacyjny", "lotnisk"], ["CPK", "infrastruktura"]),
    ("DU/2026/1514", ["Centralny Port"], ["CPK", "infrastruktura", "2026"]),
    ("DU/2022/2243", ["cena maksymalna", "limit"], ["ceny energii", "energia"]),
    ("DU/2024/1831", ["cena", "2025"], ["ceny energii", "energia"]),
    ("DU/2025/565", ["cena", "500 zł/MWh", "2025"], ["ceny energii", "energia"]),
    ("DU/1998/1118", ["60 lat", "65 lat", "waloryz"], ["emerytury", "ZUS", "wiek emerytalny"]),
    ("DU/1998/887", ["Fundusz Ubezpieczeń Społecznych", "gwarant"], ["ZUS", "ubezpieczenia społeczne"]),
    ("DU/2023/1407", ["kwoty najniższej emerytury", "wypłac"], ["13. emerytura", "emerytury"]),
    ("DU/2024/858", ["1500 zł", "aktywny rodzic", "babci"], ["babciowe", "rodzina"]),
    ("DU/2011/112", ["głosowani", "korespondencyjn", "ważność wyborów"], ["wybory", "PKW", "Kodeks wyborczy"]),
    ("DU/2022/655", ["zasadniczej służby wojskowej", "kwalifikacji wojskowej", "mobilizac"], ["wojsko", "pobór", "obronność"]),
    ("DU/2024/1907", ["schron", "budowli ochronn", "1 %"], ["obrona cywilna", "schrony", "bezpieczeństwo"]),
    ("DU/2018/1560", ["CSIRT", "incydent"], ["cyberbezpieczeństwo", "CERT"]),
    ("DU/2022/835", ["sankcj", "wykaz"], ["sankcje", "Rosja", "Białoruś"]),
    ("DU/1997/553", ["Art. 130.", "dezinformac", "Art. 256.", "Art. 257."], ["Kodeks karny", "dezinformacja", "szpiegostwo", "mowa nienawiści"]),
    ("DU/2016/961", ["odległoś", "500 m"], ["wiatraki", "OZE", "energia"]),
    ("DU/2018/305", ["zakaz handlu", "niedziel"], ["niedziele handlowe", "handel"]),
    ("DU/2024/1965", ["24 grudnia", "Wigili"], ["Wigilia", "dni wolne", "praca"]),
    ("DU/2026/1213", ["minimalne wynagrodzenie", "zł"], ["płaca minimalna", "wynagrodzenia", "2027"]),
    ("DU/2025/1242", ["minimalne wynagrodzenie", "zł"], ["płaca minimalna", "wynagrodzenia", "2026"]),
    ("DU/2025/620", ["zasiłek", "bezrobotn"], ["rynek pracy", "bezrobocie"]),
    ("DU/2026/1296", ["usunięci", "nielegalnych treści", "dostawc"], ["DSA", "internet", "cenzura"]),
    ("DU/2002/1204", ["usługodawc", "nielegaln"], ["internet", "DSA"]),
]


def eli_url(eli: str) -> str:
    return f"{API}/{eli}"


def isap_url(meta: dict) -> str:
    return f"https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id={meta['address']}"


def get_meta(eli: str) -> dict:
    return fetch_json(eli_url(eli))


def _clean_pdf(t: str) -> str:
    t = re.sub(r"(?m)^\s*Dziennik Ustaw\s*[–-]\s*\d+\s*[–-]\s*Poz\.\s*\d+\s*$", "", t)
    t = re.sub(r"(?m)^\s*\d+\s*$", "", t)
    t = re.sub(r"-\n(?=[a-ząćęłńóśźż])", "", t)  # hyphenation
    t = re.sub(r"(?m)^(\d+[a-z]?\)|[a-z]{1,2}\)|–)\s*\n\s*", r"\1 ", t)  # "1)\n tekst"
    t = re.sub(r"(?<![.:;])\n(?=[a-ząćęłńóśźż(])", " ", t)
    return clean_ws(t)


def get_text(eli: str, meta: dict) -> tuple[str, str]:
    """Return (plain text, url used). Prefers HTML, falls back to PDF."""
    if meta.get("textHTML"):
        u = eli_url(eli) + "/text.html"
        try:
            return html_to_text(fetch(u).decode("utf-8", "replace")), u
        except Exception as e:
            log("  html failed", eli, e)
    if meta.get("textPDF"):
        u = eli_url(eli) + "/text.pdf"
        try:
            return _clean_pdf(pdf_to_text(fetch(u, timeout=120))), u
        except Exception as e:
            log("  pdf failed", eli, e)
    return "", ""


def latest_consolidated(meta: dict) -> str | None:
    refs = (meta.get("references") or {}).get("Inf. o tekście jednolitym") or []
    if not refs:
        return None

    def key(r):
        y, p = r["id"].split("/")[1:3]
        return (int(y), int(p))
    return sorted(refs, key=key)[-1]["id"]


def window(text: str, term: str, before=200, after=600, max_hits=1) -> list[str]:
    out = []
    for m in re.finditer(re.escape(term), text, flags=re.I):
        s = max(0, m.start() - before)
        # snap start to the beginning of an article/paragraph if close
        art = text.rfind("Art. ", s, m.start())
        if art != -1 and m.start() - art < before + 200:
            s = art
        out.append(text[s: m.end() + after].strip())
        if len(out) >= max_hits:
            break
    return out


def art1(text: str) -> str:
    m = re.search(r"Art\.\s*1\.\s", text)
    if not m:
        return text[:900]
    seg = text[m.start(): m.start() + 1200]
    n = re.search(r"\sArt\.\s*[23]\.\s", seg[10:])
    return seg[: n.start() + 10] if n else seg


def describe(meta: dict) -> list[str]:
    refs = meta.get("references") or {}
    zm = refs.get("Akty zmieniające") or []
    lines = [
        f"Akt: {meta['title']}",
        f"Publikator: {meta.get('displayAddress')} | ELI: {meta.get('ELI')} | typ: {meta.get('type')}",
        f"Status (ISAP): {meta.get('status')}; inForce={meta.get('inForce')}; "
        f"wejście w życie: {meta.get('entryIntoForce') or 'b.d.'}; ogłoszono: {meta.get('promulgation') or 'b.d.'}",
    ]
    if meta.get("keywords") or meta.get("keywordsNames"):
        lines.append("Hasła ISAP: " + ", ".join((meta.get("keywords") or []) + (meta.get("keywordsNames") or [])))
    if zm:
        last = sorted(zm, key=lambda r: r.get("date") or "")[-3:]
        lines.append(f"Liczba aktów zmieniających: {len(zm)}; ostatnie: " +
                     ", ".join(f"{r['id']} (od {r.get('date')})" for r in last))
    if refs.get("Akty uchylające"):
        lines.append("Uchylony przez: " + ", ".join(r["id"] for r in refs["Akty uchylające"][:3]))
    if meta.get("comments"):
        lines.append("Uwagi ISAP: " + clean_ws(meta["comments"])[:500])
    return lines


def build_record(eli: str, focus: list[str], tags: list[str]):
    meta = get_meta(eli)
    cons = latest_consolidated(meta)
    src_eli, src_meta = eli, meta
    if cons:
        try:
            src_meta = get_meta(cons)
            src_eli = cons
        except Exception as e:
            log("  consolidated meta failed", cons, e)
    text, text_url = get_text(src_eli, src_meta)
    if not text and src_eli != eli:
        text, text_url = get_text(eli, meta)
    lines = describe(meta)
    if cons:
        lines.append(f"Najnowszy tekst jednolity: {src_meta.get('displayAddress')} ({cons}) — {src_meta.get('title', '')[:160]}")
    lines.append(f"Źródło danych: {eli_url(eli)}" + (f" ; tekst: {text_url}" if text_url else ""))
    body = []
    if text:
        body.append("Przedmiot (art. 1): " + art1(text))
        m1 = re.search(r"Art\.\s*1\.\s", text)
        core = text[m1.start():] if m1 else text
        for term in focus:
            for w in window(core, term):
                body.append(f"[fragment: „{term}”] " + w)
    full = "\n".join(lines) + "\n" + "\n".join(body)
    return make_record(source="eli", sid=eli, publisher="Sejm RP — ISAP / Dziennik Ustaw (ELI API)",
                       url=isap_url(meta), title=meta["title"], text=full,
                       published_at=meta.get("promulgation") or meta.get("announcementDate"),
                       license=LICENSE, tags=["prawo", "ustawa" if meta.get("type") == "Ustawa" else meta.get("type", "akt"),
                                              "ISAP", "ELI"] + tags,
                       domain="isap.sejm.gov.pl")


def main():
    with JsonlWriter("eli") as w:
        for eli, focus, tags in ACTS:
            try:
                rec = build_record(eli, focus, tags)
                w.write(rec)
                log(f"  {eli}: {len(rec['text'])} chars")
            except Exception as e:
                log(f"  FAIL {eli}: {e}")


if __name__ == "__main__":
    sys.exit(main())
