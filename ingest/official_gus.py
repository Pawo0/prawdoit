#!/usr/bin/env python3
"""GUS fact cards.

1) Monthly: "Wybrane miesięczne wskaźniki makroekonomiczne – część I" (XLSX linked from
   https://stat.gov.pl/wskazniki-makroekonomiczne/): CPI total + COICOP groups, registered
   unemployment, wages, pensions.
2) Newest monthly CPI from the DBW API (api-dbw.stat.gov.pl, CC BY 4.0) when fresher than the XLSX.
3) Annual (Poland level): BDL API https://bdl.stat.gov.pl/api/v1 (anonymous: 5 req/s,
   100/15 min, 1000/12 h, 10 000/7 days; licence CC BY 4.0 per api.stat.gov.pl).

Output: data/corpus/official_gus.jsonl  (one short factual card per indicator/period)
"""
from __future__ import annotations

import io
import re
import sys
import time

from official_common import (PL_MONTHS, PL_MONTHS_LOC, JsonlWriter, fetch, fetch_json, fetch_text, fmt_num,
                             log, make_record)

GUS_PAGE = "https://stat.gov.pl/wskazniki-makroekonomiczne/"
LIC_GUS = "GUS — wykorzystanie dozwolone z podaniem źródła (stat.gov.pl/copyright)"
LIC_BDL = "CC BY 4.0 — GUS, Bank Danych Lokalnych (api.stat.gov.pl); podać źródło"
PUB = "Główny Urząd Statystyczny"
BDL = "https://bdl.stat.gov.pl/api/v1"

# BDL variable id -> (description used in the card, unit label, decimals, tags)
BDL_VARS = {
    72305: ("Liczba ludności Polski (stan na 31 grudnia)", "osób", 0, ["ludność", "demografia"]),
    59: ("Liczba urodzeń żywych w Polsce", "", 0, ["urodzenia", "demografia"]),
    65: ("Liczba zgonów w Polsce", "", 0, ["zgony", "demografia"]),
    450540: ("Urodzenia żywe na 1000 ludności w Polsce", "‰", 2, ["urodzenia", "demografia"]),
    59049: ("Współczynnik dzietności (ogólny) w Polsce", "", 3, ["dzietność", "demografia"]),
    60569: ("Zgony niemowląt na 1000 urodzeń żywych w Polsce", "", 2, ["zdrowie", "demografia"]),
    80108: ("Saldo migracji zagranicznych na pobyt stały w Polsce", "osób", 0, ["migracja", "demografia"]),
    60270: ("Stopa bezrobocia rejestrowanego w Polsce (stan na 31 grudnia)", "%", 1, ["bezrobocie", "rynek pracy"]),
    64428: ("Przeciętne miesięczne wynagrodzenie brutto w gospodarce narodowej w Polsce", "zł", 2, ["wynagrodzenia"]),
    398594: ("Przestępstwa stwierdzone przez Policję na 1000 mieszkańców w Polsce", "", 2, ["przestępczość", "bezpieczeństwo"]),
}

# monthly sheet -> list of (row-name prefix, code, card builder key)
CPI_GROUPS = [
    "żywność i napoje bezalkoholowe", "napoje alkoholowe i wyroby tytoniowe", "odzież i obuwie",
    "użytkowanie mieszkania", "wyposażenie mieszkania", "zdrowie", "transport",
    "informacja i komunikacja", "rekreacja, sport i kultura", "edukacja",
    "restauracje i usługi zakwaterowania", "ubezpieczenia i usługi finansowe", "higiena osobista",
]


def find_xlsx_url() -> str:
    html = fetch_text(GUS_PAGE)
    m = re.search(r'href="([^"]*wybrane_miesieczne_wskazniki_makroekonomiczne[^"]*\.xlsx)"', html)
    if not m:
        raise RuntimeError("monthly XLSX link not found on " + GUS_PAGE)
    href = m.group(1)
    return href if href.startswith("http") else "https://stat.gov.pl" + href


def parse_sheet(ws):
    """-> (update_date, {name: {code: [(year, month, value), ...]}})"""
    rows = list(ws.iter_rows(values_only=True))
    upd = None
    for r in rows[:4]:
        if r[1] and str(r[1]).startswith("Aktualizacja") and r[2]:
            upd = r[2].date().isoformat() if hasattr(r[2], "date") else str(r[2])
    years, months = rows[3], rows[4]
    out: dict[str, dict[str, list]] = {}
    cur = None
    for r in rows[5:]:
        if r[1]:
            cur = re.sub(r"\s+", " ", str(r[1])).strip()
            out.setdefault(cur, {})
        if cur is None or r[2] is None:
            continue
        code = str(r[2]).strip()
        series = []
        for i in range(3, len(r)):
            v = r[i]
            if v in (None, ".", "", "x", "-"):
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            series.append((int(years[i]), int(months[i]), v))
        out[cur][code] = series
    return upd, out


def get(d: dict, prefix: str) -> dict | None:
    for k, v in d.items():
        if k.lower().startswith(prefix.lower()):
            return v
    return None


def month_pl(y: int, m: int) -> str:
    return f"{PL_MONTHS_LOC[m - 1]} {y} r."


def month_nom(y: int, m: int) -> str:
    return f"{PL_MONTHS[m - 1]} {y}"


def chg(idx: float) -> str:
    d = idx - 100
    word = "wzrost" if d > 0 else ("spadek" if d < 0 else "brak zmiany")
    return f"{word} o {fmt_num(abs(d), 1)}%" if d else word


def monthly_cards(w: JsonlWriter):
    import openpyxl
    url = find_xlsx_url()
    log("  GUS xlsx:", url)
    wb = openpyxl.load_workbook(io.BytesIO(fetch(url, timeout=120)), read_only=True, data_only=True)
    cite = (f"Źródło: GUS, „Wybrane miesięczne wskaźniki makroekonomiczne – część I”, plik {url} "
            f"(strona {GUS_PAGE}).")

    # --- prices (current COICOP 2018 sheet + older COICOP 1999 sheet for months before 2026)
    done: set = set()
    for sheet, label, nmax in [("WSKAŹNIKI CEN", "", 13), ("WSKAŹNIKI CEN - COICOP 1999", ", COICOP 1999", 15)]:
        if sheet not in wb.sheetnames:
            continue
        upd_s, d_s = parse_sheet(wb[sheet])
        c = get(d_s, "Wskaźniki cen towarów i usług konsumpcyjnych")
        if not c or not c.get("A"):
            continue
        mm = {(y, m): v for y, m, v in c.get("B", [])}
        dec = {(y, m): v for y, m, v in c.get("C", [])}
        for y, m, v in c["A"][-nmax:]:
            if (y, m) in done:
                continue
            done.add((y, m))
            upd = upd_s
            extra = []
            if (y, m) in mm:
                extra.append(f"w porównaniu z poprzednim miesiącem: {fmt_num(mm[(y, m)], 1)} ({chg(mm[(y, m)])} m/m)")
            if (y, m) in dec:
                extra.append(f"w porównaniu z grudniem roku poprzedniego: {fmt_num(dec[(y, m)], 1)}")
            text = (f"Inflacja CPI w Polsce w {month_pl(y, m)} wyniosła {fmt_num(v - 100, 1)}% r/r "
                    f"(wskaźnik cen towarów i usług konsumpcyjnych {fmt_num(v, 1)}, analogiczny miesiąc "
                    f"roku poprzedniego = 100){'; ' + '; '.join(extra) if extra else ''}. "
                    f"Dane GUS; wartość za ostatni miesiąc może być wstępna lub szybkim szacunkiem. "
                    f"Stan danych: aktualizacja tablicy {upd}. {cite}")
            w.write(make_record(source="gus", sid=f"cpi:{y}-{m:02d}", publisher=PUB, url=url,
                                title=f"Inflacja CPI w Polsce — {month_nom(y, m)}: {fmt_num(v - 100, 1)}% r/r (GUS{label})",
                                text=text, published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                                tags=["GUS", "fact-card", "inflacja", "CPI", "ceny", f"{y}"]))
    upd, d = parse_sheet(wb["WSKAŹNIKI CEN"])
    cpi = get(d, "Wskaźniki cen towarów i usług konsumpcyjnych")
    if cpi and cpi.get("A"):
        ly, lm, _ = cpi["A"][-1]
        lines = []
        for g in CPI_GROUPS:
            s = get(d, g)
            if s and s.get("A") and s["A"][-1][:2] == (ly, lm):
                v = s["A"][-1][2]
                lines.append(f"- {g}: {fmt_num(v, 1)} ({chg(v)} r/r)")
                name = [k for k in d if k.lower().startswith(g.lower())][0]
                w.write(make_record(
                    source="gus", sid=f"cpi-group:{re.sub(r'[^a-z]+', '-', g.lower())}:{ly}-{lm:02d}",
                    publisher=PUB, url=url,
                    title=f"Ceny — {name} — {month_nom(ly, lm)}: {chg(v)} r/r (GUS)",
                    text=(f"Wskaźnik cen w grupie „{name}” w Polsce w {month_pl(ly, lm)} wyniósł "
                          f"{fmt_num(v, 1)} (analogiczny miesiąc roku poprzedniego = 100), tj. {chg(v)} r/r. "
                          f"Ogólny wskaźnik CPI: {fmt_num(cpi['A'][-1][2], 1)}. Aktualizacja tablicy {upd}. {cite}"),
                    published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                    tags=["GUS", "fact-card", "ceny", "CPI", g.split()[0]]))
        # PPI
        ppi = get(d, "Wskaźniki cen produkcji sprzedanej w przemyśle")
        if ppi and ppi.get("A"):
            y, m, v = ppi["A"][-1]
            w.write(make_record(source="gus", sid=f"ppi:{y}-{m:02d}", publisher=PUB, url=url,
                                title=f"Ceny produkcji sprzedanej przemysłu (PPI) — {month_nom(y, m)}: {chg(v)} r/r (GUS)",
                                text=(f"Wskaźnik cen produkcji sprzedanej przemysłu w Polsce w {month_pl(y, m)}: "
                                      f"{fmt_num(v, 1)} (rok wcześniej = 100), tj. {chg(v)} r/r. Aktualizacja {upd}. {cite}"),
                                published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                                tags=["GUS", "fact-card", "ceny", "PPI", "przemysł"]))

    # --- labour market
    upd, d = parse_sheet(wb["RYNEK PRACY"])
    ur = get(d, "Stopa bezrobocia rejestrowanego")
    un = get(d, "Bezrobotni zarejestrowani")
    unemp = {(y, m): v for y, m, v in (un or {}).get("w tys.", [])}
    if ur:
        series = ur.get("w %") or next(iter(ur.values()))
        for y, m, v in series[-13:]:
            extra = f" Liczba zarejestrowanych bezrobotnych: {fmt_num(unemp[(y, m)], 1)} tys." if (y, m) in unemp else ""
            w.write(make_record(source="gus", sid=f"unemployment-rate:{y}-{m:02d}", publisher=PUB, url=url,
                                title=f"Stopa bezrobocia rejestrowanego w Polsce — {month_nom(y, m)}: {fmt_num(v, 1)}% (GUS)",
                                text=(f"Stopa bezrobocia rejestrowanego w Polsce na koniec okresu ({month_pl(y, m)}) "
                                      f"wyniosła {fmt_num(v, 1)}%.{extra} Uwaga: to bezrobocie rejestrowane (urzędy pracy), "
                                      f"nie stopa bezrobocia BAEL/Eurostat. Aktualizacja tablicy {upd}. {cite}"),
                                published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                                tags=["GUS", "fact-card", "bezrobocie", "rynek pracy", f"{y}"]))
    emp = get(d, "Przeciętne zatrudnienie w sektorze przedsiębiorstw")
    if emp and emp.get("w tys."):
        y, m, v = emp["w tys."][-1]
        a = {(yy, mm): vv for yy, mm, vv in emp.get("A", [])}.get((y, m))
        w.write(make_record(source="gus", sid=f"employment:{y}-{m:02d}", publisher=PUB, url=url,
                            title=f"Przeciętne zatrudnienie w sektorze przedsiębiorstw — {month_nom(y, m)} (GUS)",
                            text=(f"Przeciętne zatrudnienie w sektorze przedsiębiorstw (podmioty >9 osób) w {month_pl(y, m)}: "
                                  f"{fmt_num(v, 1)} tys. osób" + (f" ({chg(a)} r/r)" if a else "") + f". Aktualizacja {upd}. {cite}"),
                            published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                            tags=["GUS", "fact-card", "zatrudnienie", "rynek pracy"]))

    # --- wages & pensions
    upd, d = parse_sheet(wb["WYNAGR. I ŚWIADCZ. SPOŁ"])
    wage = get(d, "Przeciętne miesięczne nominalne wynagrodzenie brutto")
    real = get(d, "Przeciętne miesięczne realne wynagrodzenie brutto")
    realA = {(y, m): v for y, m, v in (real or {}).get("A", [])}
    if wage and wage.get("w zł"):
        nomA = {(y, m): v for y, m, v in wage.get("A", [])}
        for y, m, v in wage["w zł"][-7:]:
            parts = [f"Przeciętne miesięczne nominalne wynagrodzenie brutto w sektorze przedsiębiorstw "
                     f"(podmioty >9 osób) w {month_pl(y, m)} wyniosło {fmt_num(v, 2)} zł"]
            if (y, m) in nomA:
                parts.append(f"nominalnie {chg(nomA[(y, m)])} r/r")
            if (y, m) in realA:
                parts.append(f"realnie {chg(realA[(y, m)])} r/r")
            w.write(make_record(source="gus", sid=f"wage:{y}-{m:02d}", publisher=PUB, url=url,
                                title=f"Przeciętne wynagrodzenie w sektorze przedsiębiorstw — {month_nom(y, m)}: {fmt_num(v, 2)} zł (GUS)",
                                text=", ".join(parts) + f". To NIE jest przeciętne wynagrodzenie w całej gospodarce "
                                     f"(publikowane kwartalnie). Aktualizacja {upd}. {cite}",
                                published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                                tags=["GUS", "fact-card", "wynagrodzenia", f"{y}"]))
    for prefix, label, tag in [("Przeciętna miesięczna nominalna emerytura i renta brutto z pozarolniczego",
                                "Przeciętna emerytura i renta brutto z pozarolniczego systemu (ZUS)", "ZUS"),
                               ("Przeciętna miesięczna nominalna emerytura i renta rolników",
                                "Przeciętna emerytura i renta rolników indywidualnych brutto (KRUS)", "KRUS")]:
        s = get(d, prefix)
        if s and s.get("w zł"):
            y, m, v = s["w zł"][-1]
            a = {(yy, mm): vv for yy, mm, vv in s.get("A", [])}.get((y, m))
            w.write(make_record(source="gus", sid=f"pension-{tag.lower()}:{y}-{m:02d}", publisher=PUB, url=url,
                                title=f"{label} — {month_nom(y, m)}: {fmt_num(v, 2)} zł (GUS)",
                                text=f"{label} w {month_pl(y, m)}: {fmt_num(v, 2)} zł" +
                                     (f" (nominalnie {chg(a)} r/r)" if a else "") + f". Aktualizacja {upd}. {cite}",
                                published_at=upd, license=LIC_GUS, domain="stat.gov.pl",
                                tags=["GUS", "fact-card", "emerytury", tag]))
    return done


DBW = "https://api-dbw.stat.gov.pl/api"
LIC_DBW = "CC BY 4.0 — GUS, Dziedzinowa Baza Wiedzy (api-dbw.stat.gov.pl); podać źródło"
# DBW ids (discovered 2026-11-21): variable 305 = "Wskaźniki cen towarów i usług konsumpcyjnych",
# section 1698 = "Polska; COICOP 2018; grupa gospodarstw domowych — dane od 2026 r.",
# positions: COICOP "0 - OGÓŁEM" = 14916914, household group "Ogółem" = 6902025,
# presentation: 2 = poprzedni okres=100, 5 = analogiczny okres roku poprzedniego=100, 8 = grudzień=100,
# periods: 247..258 = M01..M12.
DBW_CPI = {"var": 305, "sec": 1698, "pos2": 14916914, "pos3": 6902025}


def dbw_cpi_latest(year: int):
    """Newest monthly CPI (total) from the DBW API — usually 1 month fresher than the XLSX."""
    for m in range(12, 0, -1):
        okres = 246 + m
        base = (f"{DBW}/variable/variable-data-section?id-zmienna={DBW_CPI['var']}&id-przekroj={DBW_CPI['sec']}"
                f"&id-rok={year}&id-okres={okres}&lang=pl")
        try:
            probe = fetch_json(base + "&ile-na-stronie=1&numer-strony=0", min_delay=1.5, retries=1)
        except Exception:  # months not yet published answer 404
            continue
        total = probe.get("page-count") or 0  # with page size 1 == number of rows
        if not total:
            continue
        pages = (total + 4999) // 5000
        for pg in range(pages - 1, -1, -1):  # the national total sits near the end
            url = base + f"&ile-na-stronie=5000&numer-strony={pg}"
            rows = [r for r in fetch_json(url, min_delay=1.5, timeout=120).get("data", [])
                    if r.get("id-pozycja-2") == DBW_CPI["pos2"] and r.get("id-pozycja-3") == DBW_CPI["pos3"]]
            if rows:
                vals = {r["id-sposob-prezentacji-miara"]: r["wartosc"] for r in rows}
                return year, m, vals, url
        return None
    return None


def dbw_cards(w: JsonlWriter, have: set):
    import datetime as dt
    res = dbw_cpi_latest(dt.date.today().year)
    if not res:
        log("  DBW: no CPI data found")
        return
    y, m, vals, url = res
    if (y, m) in have or 5 not in vals:
        log(f"  DBW CPI {y}-{m:02d} already covered by XLSX")
        return
    v = vals[5]
    extra = []
    if 2 in vals:
        extra.append(f"w porównaniu z poprzednim miesiącem: {fmt_num(vals[2], 1)} ({chg(vals[2])} m/m)")
    if 8 in vals:
        extra.append(f"w porównaniu z grudniem roku poprzedniego: {fmt_num(vals[8], 1)}")
    text = (f"Inflacja CPI w Polsce w {month_pl(y, m)} wyniosła {fmt_num(v - 100, 1)}% r/r (wskaźnik cen towarów "
            f"i usług konsumpcyjnych ogółem {fmt_num(v, 1)}, analogiczny miesiąc roku poprzedniego = 100; COICOP 2018)"
            + ("; " + "; ".join(extra) if extra else "") +
            f". Źródło: GUS, Dziedzinowa Baza Wiedzy (DBW), zmienna 305, przekrój 1698, API: {url} . "
            f"Dane mogą zostać zrewidowane w kolejnych publikacjach GUS.")
    w.write(make_record(source="gus", sid=f"cpi:{y}-{m:02d}", publisher=PUB + " — Dziedzinowa Baza Wiedzy",
                        url=url, title=f"Inflacja CPI w Polsce — {month_nom(y, m)}: {fmt_num(v - 100, 1)}% r/r (GUS DBW)",
                        text=text, published_at=None, license=LIC_DBW, domain="stat.gov.pl",
                        tags=["GUS", "DBW", "fact-card", "inflacja", "CPI", "ceny", f"{y}"]))


def bdl_cards(w: JsonlWriter):
    for vid, (desc, unit, dec, tags) in BDL_VARS.items():
        url = f"{BDL}/data/by-variable/{vid}?unit-level=0&format=json"
        d = meta = None
        for attempt in range(3):  # anonymous BDL quota: 5/s, 100/15 min, 1000/12 h
            try:
                d = fetch_json(url, min_delay=1.5, retries=1)
                meta = fetch_json(f"{BDL}/variables/{vid}?format=json", min_delay=1.5, retries=1)
                break
            except Exception as e:
                log(f"  BDL {vid}: {e} — waiting 120 s (quota)")
                time.sleep(120)
        if d is None or meta is None:
            continue
        vals = [(int(x["year"]), x["val"]) for x in d["results"][0]["values"] if x.get("val") is not None]
        if not vals:
            continue
        vals.sort()
        y, v = vals[-1]
        hist = "; ".join(f"{yy}: {fmt_num(vv, dec)}" for yy, vv in vals[-6:-1][::-1])
        u = f" {unit}" if unit else ""
        text = (f"{desc} w {y} r.: {fmt_num(v, dec)}{u} (GUS, Bank Danych Lokalnych, zmienna {vid}: "
                f"{meta.get('n1') or ''}{' / ' + meta['n2'] if meta.get('n2') else ''}, jednostka: "
                f"{meta.get('measureUnitName')}). Wcześniejsze lata: {hist}. "
                f"Źródło (API): {url}. Dane roczne; ostatni rok może podlegać rewizji.")
        w.write(make_record(source="gus", sid=f"bdl:{vid}:{y}", publisher=PUB + " — Bank Danych Lokalnych",
                            url=url, title=f"{desc} — {y}: {fmt_num(v, dec)}{u} (GUS BDL)", text=text,
                            published_at=None, license=LIC_BDL, domain="bdl.stat.gov.pl",
                            tags=["GUS", "BDL", "fact-card", f"{y}"] + tags))


def main():
    with JsonlWriter("gus") as w:
        have: set = set()
        try:
            have = monthly_cards(w) or set()
        except Exception as e:
            log("  monthly cards failed:", e)
        try:
            dbw_cards(w, have)
        except Exception as e:
            log("  DBW cards failed:", e)
        bdl_cards(w)


if __name__ == "__main__":
    sys.exit(main())
