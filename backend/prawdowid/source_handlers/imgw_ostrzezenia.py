"""Convert current IMGW warning data into official corpus records.

IMGW-PIB weather and hydrological warnings from the official open-data API (danepubliczne.imgw.pl).

meteo.imgw.pl / hydro.imgw.pl are JS map apps; the same warnings are published as open data:

  GET https://danepubliczne.imgw.pl/api/data/warningsmeteo
      [{id, nazwa_zdarzenia, stopien, prawdopodobienstwo, obowiazuje_od, obowiazuje_do, opublikowano, tresc,
        komentarz, biuro, teryt: [powiat codes]}]
  GET https://danepubliczne.imgw.pl/api/data/warningshydro
      [{numer, zdarzenie, stopień, data_od, data_do, opublikowano, prawdopodobienstwo, przebieg, komentarz, biuro,
        obszary: [{wojewodztwo, opis, kod_zlewni}]}]

robots.txt: none (404) => no restrictions; 2 requests per run.
Licence: IMGW-PIB open data — free re-use with attribution "Źródłem pochodzenia danych jest Instytut Meteorologii
i Gospodarki Wodnej – Państwowy Instytut Badawczy" (danepubliczne.imgw.pl, regulamin).
Each warning gets its own canonical URL: the human warnings map plus ?ostrzezenie=<id> (ignored by the app).

params (optional): kinds = ["meteo", "hydro"] (default both)

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import logging

from ._common import TERYT_WOJ, delay_of, get_json, iso_date, md_to_text, record, short_hash

log = logging.getLogger("prawdowid.sources.imgw_ostrzezenia")

API = "https://danepubliczne.imgw.pl/api/data"
METEO_PAGE = "https://meteo.imgw.pl/dyn/?osmet=true"
HYDRO_PAGE = "https://hydro.imgw.pl/"


def _woj_from_teryt(codes) -> list[str]:
    seen: dict[str, None] = {}
    for c in codes or []:
        name = TERYT_WOJ.get(str(c)[:2])
        if name:
            seen.setdefault(name, None)
    return list(seen)


def _meteo(source: dict, delay: float) -> list[dict]:
    out = []
    for w in get_json(f"{API}/warningsmeteo", delay=delay) or []:
        wid = str(
            w.get("id")
            or short_hash(w.get("nazwa_zdarzenia"), w.get("obowiazuje_od"), w.get("teryt"))
        )
        event = (w.get("nazwa_zdarzenia") or "Ostrzeżenie meteorologiczne").strip()
        level = str(w.get("stopien") or "").strip()
        woj = _woj_from_teryt(w.get("teryt"))
        lines = [
            f"Ostrzeżenie meteorologiczne IMGW-PIB{f' {level}. stopnia' if level else ''}: {event}."
        ]
        lines.append(
            f"Obowiązuje od {(w.get('obowiazuje_od') or '')[:16]} do {(w.get('obowiazuje_do') or '')[:16]}"
            + (
                f", prawdopodobieństwo {w['prawdopodobienstwo']}%"
                if w.get("prawdopodobienstwo")
                else ""
            )
            + "."
        )
        if woj:
            lines.append(
                f"Obszar: województwa {', '.join(woj)} ({len(w.get('teryt') or [])} powiatów)."
            )
        lines.append(md_to_text(w.get("tresc") or ""))
        com = md_to_text(w.get("komentarz") or "")
        if com and com.lower().rstrip(".") != "brak":
            lines.append("Komentarz: " + com)
        if w.get("biuro"):
            lines.append(f"Wydał: {w['biuro']}, opublikowano {(w.get('opublikowano') or '')[:16]}.")
        title = (
            f"IMGW: {event}"
            + (f" — {level}. stopień" if level else "")
            + (f" ({', '.join(woj)})" if woj else "")
        )
        out.append(
            record(
                source,
                sid=f"meteo:{wid}",
                url=f"{METEO_PAGE}&ostrzezenie={wid}",
                title=title,
                text="\n".join(x for x in lines if x),
                published_at=iso_date(w.get("opublikowano")) or iso_date(w.get("obowiazuje_od")),
                tags=["IMGW", "ostrzeżenie meteorologiczne", event.lower(), *woj],
            )
        )
    return out


def _hydro(source: dict, delay: float) -> list[dict]:
    out = []
    for w in get_json(f"{API}/warningshydro", delay=delay) or []:
        event = (w.get("zdarzenie") or "Ostrzeżenie hydrologiczne").strip()
        level = str(w.get("stopień") or w.get("stopien") or "").strip()
        areas = w.get("obszary") or []
        woj = list(
            dict.fromkeys(
                (a.get("wojewodztwo") or "").strip() for a in areas if a.get("wojewodztwo")
            )
        )
        wid = short_hash(w.get("biuro"), w.get("numer"), w.get("data_od"), event)
        to = (w.get("data_do") or "")[:16]
        lines = [
            f"Ostrzeżenie hydrologiczne IMGW-PIB nr {w.get('numer') or '?'}"
            + (f", stopień {level}" if level and level != "-1" else "")
            + f": {event}."
        ]
        lines.append(
            f"Obowiązuje od {(w.get('data_od') or '')[:16]}"
            + (" do odwołania" if to.startswith("9999") else f" do {to}")
            + (
                f", prawdopodobieństwo {w['prawdopodobienstwo']}%"
                if w.get("prawdopodobienstwo")
                else ""
            )
            + "."
        )
        if areas:
            lines.append(
                "Obszar: "
                + "; ".join(md_to_text(a.get("opis") or a.get("wojewodztwo") or "") for a in areas)
                + "."
            )
        lines.append(md_to_text(w.get("przebieg") or ""))
        com = md_to_text(w.get("komentarz") or "")
        if com:
            lines.append("Komentarz: " + com)
        if w.get("biuro"):
            lines.append(f"Wydał: {w['biuro']}, opublikowano {(w.get('opublikowano') or '')[:16]}.")
        title = f"IMGW: {event}" + (f" ({', '.join(woj)})" if woj else "")
        out.append(
            record(
                source,
                sid=f"hydro:{wid}",
                url=f"{HYDRO_PAGE}?ostrzezenie={wid}",
                title=title,
                text="\n".join(x for x in lines if x),
                published_at=iso_date(w.get("opublikowano")) or iso_date(w.get("data_od")),
                tags=["IMGW", "ostrzeżenie hydrologiczne", event.lower(), *woj],
            )
        )
    return out


def fetch(source: dict) -> list[dict]:
    p = source.get("params") or {}
    delay = delay_of(source)
    kinds = p.get("kinds") or ["meteo", "hydro"]
    out: list[dict] = []
    if "meteo" in kinds:
        out += _meteo(source, delay)
    if "hydro" in kinds:
        out += _hydro(source, delay)
    if p.get("max_items"):
        out = out[: int(p["max_items"])]
    return out
