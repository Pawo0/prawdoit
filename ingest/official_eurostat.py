#!/usr/bin/env python3
"""Eurostat fact cards comparing Poland with the EU (claims like "Polska ma najwyższą
inflację / najdroższy prąd / największy dług w UE", asylum numbers...).

API: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?{filters}&format=JSON
(JSON-stat 2.0, no auth). Licence: CC BY 4.0 (Eurostat copyright notice).

Output: data/corpus/official_eurostat.jsonl
"""
from __future__ import annotations

import sys
import urllib.parse

from official_common import JsonlWriter, fetch_json, fmt_num, log, make_record

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
LIC = "CC BY 4.0 — © European Union, Eurostat; podać źródło (kod zbioru, data dostępu)"
PUB = "Eurostat (Komisja Europejska)"
EU27 = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IT",
        "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]
GEO_PL = {"PL": "Polska", "EU27_2020": "UE-27", "DE": "Niemcy", "CZ": "Czechy", "SK": "Słowacja",
          "HU": "Węgry", "LT": "Litwa", "FR": "Francja", "IT": "Włochy", "ES": "Hiszpania", "RO": "Rumunia",
          "EL": "Grecja", "PT": "Portugalia", "NL": "Holandia", "SE": "Szwecja", "AT": "Austria",
          "BE": "Belgia", "BG": "Bułgaria", "HR": "Chorwacja", "CY": "Cypr", "DK": "Dania", "EE": "Estonia",
          "FI": "Finlandia", "IE": "Irlandia", "LU": "Luksemburg", "LV": "Łotwa", "MT": "Malta", "SI": "Słowenia"}


def query(dataset: str, filters: dict, last: int = 1):
    params = [(k, v) for k, vs in filters.items() for v in (vs if isinstance(vs, list) else [vs])]
    params += [("lastTimePeriod", str(last)), ("format", "JSON"), ("lang", "EN")]
    url = f"{API}/{dataset}?" + urllib.parse.urlencode(params)
    d = fetch_json(url, min_delay=1.5)
    ids, sizes = d["id"], d["size"]
    cats = {k: d["dimension"][k]["category"]["index"] for k in ids}
    inv = {k: {v: c for c, v in idx.items()} for k, idx in cats.items()}
    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    out = {}
    for flat, val in d["value"].items():
        flat = int(flat)
        key = {}
        for i, k in enumerate(ids):
            key[k] = inv[k][(flat // strides[i]) % sizes[i]]
        out[(key["geo"], key["time"])] = val
    return url, d, out


def latest_common(out: dict, geo="PL") -> str | None:
    times = sorted({t for (g, t) in out if g == geo})
    return times[-1] if times else None


def rank_eu(out: dict, t: str, reverse=True):
    vals = [(g, out[(g, t)]) for g in EU27 if (g, t) in out]
    vals.sort(key=lambda x: x[1], reverse=reverse)
    pos = next((i + 1 for i, (g, _) in enumerate(vals) if g == "PL"), None)
    return pos, len(vals), vals


def card(w, sid, title, text, url, d, tags, t):
    text += (f" Źródło: Eurostat, zbiór {d.get('extension', {}).get('id', '') or ''}"
             f" ({d['label']}), aktualizacja {str(d.get('updated', ''))[:10]}. API: {url}")
    w.write(make_record(source="eurostat", sid=sid, publisher=PUB, url=url, title=title, text=text,
                        published_at=str(d.get("updated", ""))[:10] or None, license=LIC,
                        domain="ec.europa.eu", tags=["Eurostat", "UE", "fact-card", "porównanie"] + tags))


def top3(vals, dec=1, unit=""):
    return ", ".join(f"{GEO_PL.get(g, g)} {fmt_num(v, dec)}{unit}" for g, v in vals[:3])


def hicp(w):
    url, d, out = query("prc_hicp_minr", {"unit": "RCH_A", "coicop18": "TOTAL"}, last=3)
    times = sorted({t for (g, t) in out if g == "PL"})
    for t in times:
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        if pl is None:
            continue
        text = (f"Zharmonizowany wskaźnik cen konsumpcyjnych (HICP) — roczna stopa zmian w {t}: Polska {fmt_num(pl, 1)}%"
                + (f", średnia UE-27 {fmt_num(eu, 1)}%" if eu is not None else "")
                + f". Polska zajmuje {pos}. miejsce na {n} państw UE (od najwyższej inflacji). "
                f"Najwyższa inflacja HICP: {top3(vals, 1, '%')}; najniższa: {top3(vals[::-1], 1, '%')}. "
                f"Uwaga: HICP (Eurostat) różni się metodologicznie od CPI GUS.")
        card(w, f"hicp:{t}", f"Inflacja HICP {t}: Polska {fmt_num(pl, 1)}% vs UE {fmt_num(eu, 1) if eu is not None else 'b.d.'}% (Eurostat)",
             text, url, d, ["inflacja", "HICP", "ceny"], t)


def unemployment(w):
    url, d, out = query("une_rt_m", {"s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT"}, last=4)
    t = latest_common(out)
    if not t:
        return
    pos, n, vals = rank_eu(out, t, reverse=False)
    pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
    text = (f"Stopa bezrobocia (metodologia BAEL/ILO, wyrównana sezonowo) w {t}: Polska {fmt_num(pl, 1)}%"
            + (f", UE-27 {fmt_num(eu, 1)}%" if eu is not None else "") +
            f". Polska ma {pos}. najniższe bezrobocie wśród {n} państw UE z danymi. Najniższe: {top3(vals, 1, '%')}; "
            f"najwyższe: {top3(vals[::-1], 1, '%')}. Uwaga: to inna miara niż stopa bezrobocia rejestrowanego GUS.")
    card(w, f"unemployment:{t}", f"Bezrobocie (Eurostat) {t}: Polska {fmt_num(pl, 1)}% vs UE {fmt_num(eu, 1) if eu is not None else 'b.d.'}%",
         text, url, d, ["bezrobocie", "rynek pracy"], t)


def gov_finance(w):
    url, d, out = query("gov_10dd_edpt1", {"unit": "PC_GDP", "sector": "S13", "na_item": "GD"}, last=2)
    t = latest_common(out)
    if t:
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Dług sektora instytucji rządowych i samorządowych (dług publiczny wg definicji UE/EDP) w {t}: "
                f"Polska {fmt_num(pl, 1)}% PKB" + (f", UE-27 {fmt_num(eu, 1)}% PKB" if eu is not None else "") +
                f". Polska na {pos}. miejscu na {n} (od najwyższego długu). Najwyższy: {top3(vals, 1, '% PKB')}. "
                f"Próg z Traktatu (kryterium z Maastricht): 60% PKB. Uwaga: definicja krajowa (konstytucyjna, art. 216 ust. 5) "
                f"różni się od unijnej.")
        card(w, f"gov-debt:{t}", f"Dług publiczny (EDP) {t}: Polska {fmt_num(pl, 1)}% PKB (Eurostat)", text, url, d,
             ["dług publiczny", "finanse publiczne"], t)
    url, d, out = query("gov_10dd_edpt1", {"unit": "PC_GDP", "sector": "S13", "na_item": "B9"}, last=2)
    t = latest_common(out)
    if t:
        pos, n, vals = rank_eu(out, t, reverse=False)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Wynik sektora instytucji rządowych i samorządowych (deficyt „-” / nadwyżka „+”) w {t}: Polska "
                f"{fmt_num(pl, 1)}% PKB" + (f", UE-27 {fmt_num(eu, 1)}% PKB" if eu is not None else "") +
                f". Polska ma {pos}. najgłębszy deficyt wśród {n} państw UE. Największe deficyty: {top3(vals, 1, '% PKB')}. "
                f"Próg z Traktatu: deficyt 3% PKB.")
        card(w, f"gov-deficit:{t}", f"Deficyt sektora finansów publicznych {t}: Polska {fmt_num(pl, 1)}% PKB (Eurostat)",
             text, url, d, ["deficyt", "finanse publiczne"], t)


def gdp(w):
    url, d, out = query("tec00115", {"unit": "CLV_PCH_PRE", "na_item": "B1GQ"}, last=3)
    for t in sorted({t for (g, t) in out if g == "PL"})[-2:]:
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Realny wzrost PKB w {t}: Polska {fmt_num(pl, 1)}%" + (f", UE-27 {fmt_num(eu, 1)}%" if eu is not None else "")
                + f". Polska na {pos}. miejscu na {n} państw UE. Najszybszy wzrost: {top3(vals, 1, '%')}.")
        card(w, f"gdp-growth:{t}", f"Wzrost PKB {t}: Polska {fmt_num(pl, 1)}% vs UE {fmt_num(eu, 1) if eu is not None else 'b.d.'}% (Eurostat)",
             text, url, d, ["PKB", "gospodarka"], t)
    url, d, out = query("tec00114", {"indic_ppp": "VI_PPS_EU27_2020_HAB", "ppp_cat18": "GDP"}, last=2)
    t = latest_common(out)
    if t:
        pos, n, vals = rank_eu(out, t)
        pl = out.get(("PL", t))
        near = sorted(vals, key=lambda gv: abs(gv[1] - pl))[1:5]
        text = (f"PKB na mieszkańca według parytetu siły nabywczej (PPS) w {t}: Polska {fmt_num(pl, 0)} (UE-27 = 100). "
                f"Polska na {pos}. miejscu na {n}. Kraje o zbliżonym poziomie: " +
                ", ".join(f"{GEO_PL.get(g, g)} {fmt_num(v, 0)}" for g, v in near) + ".")
        card(w, f"gdp-pps:{t}", f"PKB per capita (PPS) {t}: Polska {fmt_num(pl, 0)}% średniej UE (Eurostat)", text, url, d,
             ["PKB", "zamożność", "gospodarka"], t)


def electricity(w):
    for cur, label in [("EUR", "EUR/kWh"), ("PPS", "PPS/kWh")]:
        url, d, out = query("nrg_pc_204", {"siec": "E7000", "nrg_cons": "KWH2500-4999", "unit": "KWH",
                                           "tax": "I_TAX", "currency": cur}, last=2)
        t = latest_common(out)
        if not t:
            continue
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Ceny energii elektrycznej dla gospodarstw domowych (zużycie 2500–4999 kWh/rok, z podatkami i opłatami) "
                f"w {t}: Polska {fmt_num(pl, 4)} {label}" + (f", średnia UE-27 {fmt_num(eu, 4)} {label}" if eu is not None else "")
                + f". Polska na {pos}. miejscu na {n} (od najdroższej). Najdroższe: {top3(vals, 4, ' ' + label)}. "
                + ("PPS uwzględnia siłę nabywczą — porównanie „realnej” dotkliwości cen." if cur == "PPS" else
                   "W EUR — porównanie nominalne."))
        card(w, f"electricity-{cur.lower()}:{t}", f"Ceny prądu dla gospodarstw domowych {t} ({label}): Polska vs UE (Eurostat)",
             text, url, d, ["ceny energii", "energia", "prąd"], t)


def asylum(w):
    url, d, out = query("migr_asyappctza", {"citizen": "TOTAL", "sex": "T", "age": "TOTAL", "unit": "PER",
                                            "applicant": "FRST"}, last=2)
    t = latest_common(out)
    if t:
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Osoby ubiegające się po raz pierwszy o ochronę międzynarodową (azyl) w {t}: Polska {fmt_num(pl, 0)}"
                + (f", UE-27 łącznie {fmt_num(eu, 0)}" if eu is not None else "") +
                f". Polska na {pos}. miejscu na {n}. Najwięcej: {top3(vals, 0)}. Uwaga: dane nie obejmują osób "
                f"pod ochroną czasową z Ukrainy (osobna statystyka migr_asytpsm).")
        card(w, f"asylum-first:{t}", f"Wnioski azylowe (pierwszorazowe) {t}: Polska {fmt_num(pl, 0)} (Eurostat)", text, url, d,
             ["azyl", "migracja", "pakt migracyjny"], t)
    url, d, out = query("migr_asytpsm", {"citizen": "TOTAL", "sex": "T", "age": "TOTAL", "unit": "PER"}, last=4)
    # newest month with broad coverage (late reporters make the newest month partial)
    times = sorted({t for (g, t) in out if g == "PL"}, reverse=True)
    cov = {t: sum((g, t) in out for g in EU27) for t in times}
    t = next((t for t in times if cov[t] >= 20), max(times, key=lambda x: cov[x]) if times else None)
    if t:
        pos, n, vals = rank_eu(out, t)
        pl, eu = out.get(("PL", t)), out.get(("EU27_2020", t))
        text = (f"Osoby objęte ochroną czasową (głównie uchodźcy z Ukrainy), stan na koniec {t}: Polska {fmt_num(pl, 0)}"
                + (f", UE-27 {fmt_num(eu, 0)}" if eu is not None else "") +
                f". Polska na {pos}. miejscu na {n}. Najwięcej: {top3(vals, 0)}.")
        card(w, f"temp-protection:{t}", f"Ochrona czasowa (Ukraina) {t}: Polska {fmt_num(pl, 0)} osób (Eurostat)", text, url,
             d, ["Ukraina", "uchodźcy", "migracja"], t)


def main():
    with JsonlWriter("eurostat") as w:
        for f in (hicp, unemployment, gov_finance, gdp, electricity, asylum):
            try:
                f(w)
            except Exception as e:
                log(f"  {f.__name__} failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
