#!/usr/bin/env python3
"""NBP fact cards: average exchange rates (table A), gold price, NBP interest rates.

API: https://api.nbp.pl (no auth; max 93 days per query; JSON with ?format=json)
  /api/exchangerates/rates/A/{code}/?format=json            latest mid rate
  /api/exchangerates/rates/A/{code}/{start}/{end}/          range
  /api/cenyzlota/last/1/?format=json                        gold price (PLN/g)
  https://static.nbp.pl/dane/stopy/stopy_procentowe.xml     base interest rates
Terms: reuse requires citing the source with a link to www.nbp.pl (regulamin nbp.pl).

Output: data/corpus/official_nbp.jsonl
"""
from __future__ import annotations

import datetime as dt
import re
import sys

from official_common import JsonlWriter, fetch_json, fetch_text, fmt_num, log, make_record

API = "https://api.nbp.pl/api"
LIC = "NBP — dane publiczne; wymagane podanie źródła z linkiem do www.nbp.pl"
PUB = "Narodowy Bank Polski"
CURRENCIES = ["EUR", "USD", "CHF", "GBP", "UAH", "CZK", "NOK", "SEK", "JPY", "CNY", "HUF"]


def rate_on_or_before(code: str, day: dt.date):
    start = day - dt.timedelta(days=10)
    url = f"{API}/exchangerates/rates/A/{code}/{start}/{day}/?format=json"
    try:
        d = fetch_json(url)
        r = d["rates"][-1]
        return r["effectiveDate"], r["mid"], url
    except Exception:
        return None


def pct(a: float, b: float) -> str:
    ch = (a / b - 1) * 100
    return ("+" if ch > 0 else "") + fmt_num(ch, 1) + "%"


def fx_cards(w: JsonlWriter):
    for code in CURRENCIES:
        url = f"{API}/exchangerates/rates/A/{code}/?format=json"
        try:
            d = fetch_json(url)
        except Exception as e:
            log("  NBP fail", code, e)
            continue
        r = d["rates"][-1]
        day = dt.date.fromisoformat(r["effectiveDate"])
        mid = r["mid"]
        hist = []
        for label, delta in [("miesiąc wcześniej", 30), ("rok wcześniej", 365)]:
            p = rate_on_or_before(code, day - dt.timedelta(days=delta))
            if p:
                hist.append(f"{label} ({p[0]}): {fmt_num(p[1], 4)} zł — zmiana {pct(mid, p[1])}")
        text = (f"Średni kurs NBP {d['currency']} ({code}) z dnia {r['effectiveDate']} (tabela A nr {r['no']}): "
                f"1 {code} = {fmt_num(mid, 4)} zł. " + ("; ".join(hist) + ". " if hist else "") +
                f"Kursy średnie NBP publikowane są w dni robocze (ok. 11:45–12:15). Źródło (API): {url} ; "
                f"archiwum tabel: https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/")
        w.write(make_record(source="nbp", sid=f"fx:{code}:{r['effectiveDate']}", publisher=PUB, url=url,
                            title=f"Kurs średni NBP {code}/PLN z {r['effectiveDate']}: {fmt_num(mid, 4)} zł",
                            text=text, published_at=r["effectiveDate"], license=LIC, domain="nbp.pl",
                            tags=["NBP", "fact-card", "kurs walut", code, "złoty"]))


def gold_card(w: JsonlWriter):
    url = f"{API}/cenyzlota/last/1/?format=json"
    d = fetch_json(url)[-1]
    day = dt.date.fromisoformat(d["data"])
    old = None
    try:
        ou = f"{API}/cenyzlota/{day - dt.timedelta(days=375)}/{day - dt.timedelta(days=365)}/?format=json"
        old = fetch_json(ou)[-1]
    except Exception:
        pass
    text = (f"Cena 1 g złota (próba 1000) wyliczona przez NBP z dnia {d['data']}: {fmt_num(d['cena'], 2)} zł."
            + (f" Rok wcześniej ({old['data']}): {fmt_num(old['cena'], 2)} zł — zmiana {pct(d['cena'], old['cena'])}." if old else "")
            + f" Źródło (API): {url}")
    w.write(make_record(source="nbp", sid=f"gold:{d['data']}", publisher=PUB, url=url,
                        title=f"Cena złota NBP z {d['data']}: {fmt_num(d['cena'], 2)} zł/g", text=text,
                        published_at=d["data"], license=LIC, domain="nbp.pl",
                        tags=["NBP", "fact-card", "złoto", "ceny"]))


def rates_card(w: JsonlWriter):
    url = "https://static.nbp.pl/dane/stopy/stopy_procentowe.xml"
    x = fetch_text(url)
    pub = re.search(r'data_publikacji="([\d-]+)"', x)
    pub = pub.group(1) if pub else None
    tab = re.search(r'<tabela\s+id="stoproc".*?</tabela>', x, flags=re.S)
    items = re.findall(r'<pozycja\s+id="(\w+)"\s+nazwa="([^"]+)".*?oprocentowanie="([^"]+)".*?obowiazuje_od="([\d-]+)"',
                       tab.group(0) if tab else x, flags=re.S)
    if not items:
        log("  NBP rates: no items parsed")
        return
    lines = [f"- {n}: {o}% (obowiązuje od {od})" for _, n, o, od in items]
    ref = next((i for i in items if i[0] == "ref"), items[0])
    text = (f"Podstawowe stopy procentowe NBP (stan wg pliku NBP opublikowanego {pub}):\n" + "\n".join(lines) +
            "\nStopy ustala Rada Polityki Pieniężnej (RPP). Źródło: " + url +
            " ; komunikaty RPP: https://nbp.pl/polityka-pieniezna/decyzje-rpp/komunikaty-rpp/")
    w.write(make_record(source="nbp", sid=f"rates:{ref[3]}", publisher=PUB, url=url,
                        title=f"Stopy procentowe NBP — stopa referencyjna {ref[2]}% (od {ref[3]})",
                        text=text, published_at=pub, license=LIC, domain="nbp.pl",
                        tags=["NBP", "RPP", "fact-card", "stopy procentowe", "kredyty"]))


def main():
    with JsonlWriter("nbp") as w:
        for f in (fx_cards, gold_card, rates_card):
            try:
                f(w)
            except Exception as e:
                log(f"  {f.__name__} failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
