"""Collect Regional Warning System notices into official corpus records.

Regionalny System Ostrzegania (RSO) — current warnings shown by https://www.gov.pl/web/gov/ostrzezenia.

That page is a small Vue app (/static/rso/app.*.js); its data come from a public gov.pl JSON proxy:

  GET https://www.gov.pl/api/data/proxy/rso/komunikatyxml/{wojewodztwo|wszystkie}/{kategoria}/0?_format=json
      kategoria: meteorologiczne | hydrologiczne | informacje-drogowe | ogolne | stany-wod
      -> {"pagination": {...}, "newses": [{id, title, shortcut, content, rso_alarm, valid_from, valid_to,
                                            created_at, provinces{...}, river_name, location_name, water_level_*}]}

"wszystkie" returns every voivodeship at once, so one run = one request per category (4–5 requests).
gov.pl robots.txt: "User-Agent: * / Allow: /".
Deep link of one warning (used by the app): https://www.gov.pl/web/gov/ostrzezenia#/_/szczgoly/{id}; we add
?komunikat={id} so that each warning has its own canonical URL in the corpus (the page ignores the parameter).

params (optional):
  categories            default ["meteorologiczne", "hydrologiczne", "informacje-drogowe", "ogolne"]
  voivodeship           default "wszystkie" (e.g. "mazowieckie")
  include_water_levels  also store gauges above the warning level ("stany-wod"), default false

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import logging

from ._common import delay_of, get_json, iso_date, md_to_text, record

log = logging.getLogger("prawdowid.sources.rso_ostrzezenia")

API = "https://www.gov.pl/api/data/proxy/rso/komunikatyxml"
PAGE = "https://www.gov.pl/web/gov/ostrzezenia"
CATEGORY_LABEL = {
    "meteorologiczne": "Ostrzeżenie meteorologiczne",
    "hydrologiczne": "Ostrzeżenie hydrologiczne",
    "informacje-drogowe": "Ostrzeżenie drogowe",
    "ogolne": "Ostrzeżenie ogólne",
    "stany-wod": "Przekroczony stan wody",
}
DEFAULT_CATEGORIES = ["meteorologiczne", "hydrologiczne", "informacje-drogowe", "ogolne"]


def _provinces(n: dict) -> list[str]:
    prov = n.get("provinces") or {}
    vals = prov.values() if isinstance(prov, dict) else prov
    return [
        str(p.get("name") or p.get("slug_name") or "").strip().lower()
        for p in vals
        if isinstance(p, dict)
    ]


def _water_level_text(n: dict) -> str | None:
    try:
        val, warn, alarm = (
            float(n.get(k))
            for k in (
                "water_level_value",
                "water_level_warning_status_value",
                "water_level_alarm_status_value",
            )
        )
    except (TypeError, ValueError):
        return None
    if val < warn:
        return None
    state = "alarmowy" if val >= alarm else "ostrzegawczy"
    return (
        f"Przekroczony stan {state}: rzeka {n.get('river_name') or '?'}, wodowskaz {n.get('location_name') or '?'} "
        f"— {val:.0f} cm (stan ostrzegawczy {warn:.0f} cm, alarmowy {alarm:.0f} cm)."
    )


def fetch(source: dict) -> list[dict]:
    p = source.get("params") or {}
    delay = delay_of(source)
    region = (p.get("voivodeship") or "wszystkie").strip().lower()
    cats = list(p.get("categories") or DEFAULT_CATEGORIES)
    if p.get("include_water_levels") and "stany-wod" not in cats:
        cats.append("stany-wod")
    limit = int(p["max_items"]) if p.get("max_items") else None
    out: list[dict] = []
    seen: set = set()
    for cat in cats:
        try:
            data = get_json(f"{API}/{region}/{cat}/0?_format=json", delay=delay)
        except Exception as e:  # noqa: BLE001
            from ..sources.fetchers import Protected

            if isinstance(e, Protected):
                raise
            log.info("RSO %s/%s failed: %s", region, cat, e)
            continue
        for n in data.get("newses") or []:
            wid = n.get("id")
            if wid is None or wid in seen:
                continue
            seen.add(wid)
            provs = _provinces(n)
            label = CATEGORY_LABEL.get(cat, "Ostrzeżenie")
            if cat == "stany-wod":
                body = _water_level_text(n)
                if not body:
                    continue
                title = f"{label}: {n.get('river_name') or ''} — {n.get('location_name') or ''}"
            else:
                title = (n.get("title") or label).strip()
                sc, ct = md_to_text(n.get("shortcut") or ""), md_to_text(n.get("content") or "")
                sc = "" if sc == "0" else sc
                if (
                    sc and ct and (sc in ct or ct in sc)
                ):  # shortcut is often a copy/prefix of content
                    body = ct if len(ct) >= len(sc) else sc
                else:
                    body = "\n".join(x for x in (sc, ct) if x)
            alarm = str(n.get("rso_alarm") or "").strip()
            meta = [f"{label} (Regionalny System Ostrzegania, gov.pl/web/gov/ostrzezenia)"]
            if provs:
                meta.append("województwa: " + ", ".join(provs))
            if n.get("valid_from"):
                meta.append(
                    f"obowiązuje od {n['valid_from'][:16]}"
                    + (f" do {n['valid_to'][:16]}" if n.get("valid_to") else "")
                )
            if alarm and alarm not in ("0", "None"):
                meta.append(f"stopień alarmu RSO: {alarm}")
            text = "; ".join(meta) + ".\n" + f"{title}. {body}".strip()
            published = iso_date(n.get("created_at")) or iso_date(n.get("valid_from"))
            route = "stany-wod" if cat == "stany-wod" else "_"
            url = f"{PAGE}?komunikat={wid}#/{route}/szczgoly/{wid}"
            out.append(
                record(
                    source,
                    sid=str(wid),
                    url=url,
                    title=f"{title} — {', '.join(provs)}" if provs else title,
                    text=text,
                    published_at=published,
                    tags=["RSO", label.lower(), *provs],
                )
            )
            if limit is not None and len(out) >= limit:
                return out
    return out
