"""Collect MSZ Odyseusz travel notices into the shared corpus format.

MSZ "Informacje dla podróżujących" — country profiles and travel warnings for every country.

gov.pl/web/dyplomacja/informacje-dla-podrozujacych (and the old per-country pages such as
gov.pl/web/dyplomacja/wlochy) now redirect to https://odyseusz.gov.pl/, an Angular app. Its content comes from a
public, unauthenticated JSON API (the same one the browser calls; found in the app bundle, chunk with
INFO_FOR_TRAVELERS endpoints):

  GET /api/v1/informacje/profile-panstw          all profiles: kodIso, nazwa, dataZatwierdzenia (= last update),
                                                 trescPowiadomieniaDluga (current notice), base warning level
                                                 (~8.6 MB because of base64 flags; ~1 s with gzip)
  GET /api/v1/informacje/profile-panstw/mini     [{kodIso, nazwa}] (fallback list)
  GET /api/v1/informacje/profile-panstw/{ISO}    full profile: notice, warnings (incl. regional), sections
                                                 BEZPIECZENSTWO / PODROZOWANIE / ZDROWIE / PRAWO with subsections,
                                                 emergency numbers
Human page of a country: https://odyseusz.gov.pl/{ISO} (e.g. /IT = Włochy).
robots.txt: none (the app serves its index.html) => no restrictions; we still go slowly (>= 1.5 s/request).

Records per country (ids are stable, so a refresh replaces the section texts):
  {ISO}:{date}        notice + warning levels for the profile version of that date (history is kept: a new
                      version gets a new id/url, e.g. the 20.11.2026 general strike notice for Italy stays
                      citable after MSZ updates the page)
  {ISO}:{SECTION}     one record per section (summary first, then subsections), max_chars each

Incremental: a country is re-downloaded only when its update date changed (its dated notice URL is not yet in
the corpus) unless params.refresh_all is true.

params (all optional):
  countries     list of ISO codes to restrict to (default: all ~239)
  max_items     max countries downloaded per run (default: all); most recently updated first
  refresh_all   re-download unchanged countries too (default false)
  sections      include section records (default true)

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import logging

from ._common import canonical, delay_of, get_json, iso_date, known_urls, md_to_text, record

log = logging.getLogger("prawdowid.sources.msz_odyseusz")

BASE = "https://odyseusz.gov.pl"
API = BASE + "/api/v1/informacje"
TRIVIAL_NOTICES = {
    "opublikowano profil kraju.",
    "profil kraju aktualny.",
    "profil kraju zaktualizowany.",
}
SECTION_SLUG = {
    "BEZPIECZENSTWO": "bezpieczenstwo",
    "PODROZOWANIE": "podrozowanie",
    "ZDROWIE": "zdrowie",
    "PRAWO": "prawo",
}


def _pl_date(iso: str | None) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso and len(iso) >= 10 else (iso or "")


def _country_list(delay: float) -> list[dict]:
    try:
        rows = get_json(f"{API}/profile-panstw", max_bytes=25_000_000, delay=delay)
        if isinstance(rows, list) and rows:
            return [
                {
                    "iso": r.get("kodIso"),
                    "name": r.get("nazwa"),
                    "date": iso_date(r.get("dataZatwierdzenia")),
                }
                for r in rows
                if r.get("kodIso")
            ]
    except Exception as e:  # noqa: BLE001 — fall back to the small list
        log.info("full profile list failed (%s), using /mini", e)
    rows = get_json(f"{API}/profile-panstw/mini", delay=delay)
    return [
        {"iso": r.get("kodIso"), "name": r.get("nazwa"), "date": None}
        for r in rows
        if r.get("kodIso")
    ]


def _warnings_text(prof: dict, page: str) -> list[str]:
    lines = []
    for w in prof.get("ostrzezenia") or []:
        level = ((w.get("poziomZagrozenia") or {}).get("opis") or "").strip()
        scope = ((w.get("zakresTerytorialnyOstrzezenia") or {}).get("opis") or "").strip()
        since = iso_date(w.get("dataObowiazywaniaOd"))
        head = f"Ostrzeżenie MSZ: {level}" + (f" ({scope.lower()})" if scope else "")
        if since:
            head += f", obowiązuje od {_pl_date(since)}"
        body = md_to_text(w.get("tresc") or "", page)
        lines.append(f"{head}. {body}".strip())
    return lines


def _notice_record(source: dict, prof: dict, iso: str, name: str, date: str | None) -> dict:
    page = f"{BASE}/{iso}"
    notice = md_to_text(prof.get("trescPowiadomieniaDluga") or "", page)
    title_n = md_to_text(prof.get("tytulPowiadomieniaDluga") or "")
    parts = [
        f"{name} — informacje MSZ dla podróżujących (odyseusz.gov.pl), aktualizacja z {_pl_date(date)}."
    ]
    if notice and notice.lower() not in TRIVIAL_NOTICES:
        parts.append(f"Komunikat MSZ{': ' + title_n if title_n else ''}: {notice}")
    parts += _warnings_text(prof, page)
    nums = [
        f"{n.get('nazwa')}: {n.get('wartosc')}"
        for n in prof.get("miejscoweNumeryAlarmowe") or []
        if n.get("nazwa") and n.get("wartosc")
    ]
    if nums:
        parts.append("Miejscowe numery alarmowe — " + "; ".join(nums) + ".")
    url = f"{page}?aktualizacja={date}" if date else page
    return record(
        source,
        sid=f"{iso}:{date or 'aktualny'}",
        url=url,
        title=f"{name}: komunikat i ostrzeżenia MSZ dla podróżujących ({_pl_date(date)})",
        text="\n".join(parts),
        published_at=date,
        tags=["MSZ", "ostrzeżenia dla podróżujących", name, iso],
    )


def _section_records(source: dict, prof: dict, iso: str, name: str, date: str | None) -> list[dict]:
    page = f"{BASE}/{iso}"
    out = []
    for sec in prof.get("sekcje") or []:
        code = ((sec.get("zakresInformacyjny") or {}).get("kod") or "").strip()
        label = ((sec.get("zakresInformacyjny") or {}).get("opis") or code.title()).strip()
        if not code:
            continue
        parts = [
            f"{name} — {label.lower()} (MSZ, informacje dla podróżujących, aktualizacja z {_pl_date(date)})."
        ]
        summary = md_to_text(sec.get("podsumowanie") or "", page)
        body = md_to_text(sec.get("tresc") or "", page)
        if summary:
            parts.append("Najważniejsze: " + summary)
        if body and body[:200] not in summary:
            parts.append(body)
        for sub in sec.get("podsekcje") or []:
            t = md_to_text(sub.get("tresc") or "", page)
            if t:
                parts.append(f"{(sub.get('tytul') or '').strip()}: {t}")
        if len(parts) == 1:
            continue
        slug = SECTION_SLUG.get(code, code.lower())
        out.append(
            record(
                source,
                sid=f"{iso}:{code}",
                url=f"{page}?sekcja={slug}",
                title=f"{name}: {label} — MSZ, informacje dla podróżujących",
                text="\n".join(parts),
                published_at=date,
                tags=["MSZ", "informacje dla podróżujących", name, iso, label.lower()],
            )
        )
    return out


def fetch(source: dict) -> list[dict]:
    p = source.get("params") or {}
    delay = delay_of(source)
    known = known_urls(source)
    want = {c.upper() for c in p.get("countries") or []}
    rows = _country_list(delay)
    if want:
        rows = [r for r in rows if r["iso"].upper() in want]
    rows.sort(key=lambda r: r["date"] or "", reverse=True)
    limit = int(p["max_items"]) if p.get("max_items") else None
    out: list[dict] = []
    done = 0
    for r in rows:
        if limit is not None and done >= limit:
            break
        iso = r["iso"].upper()
        if (
            r["date"]
            and not p.get("refresh_all")
            and canonical(f"{BASE}/{iso}?aktualizacja={r['date']}") in known
        ):
            continue  # unchanged since the last run
        try:
            prof = get_json(f"{API}/profile-panstw/{iso}", delay=delay)
        except Exception as e:  # noqa: BLE001 — one country must not kill the run
            from ..sources.fetchers import Protected

            if isinstance(e, Protected):
                raise
            log.info("profile %s failed: %s", iso, e)
            continue
        done += 1
        name = (prof.get("nazwa") or r["name"] or iso).strip()
        date = iso_date(prof.get("dataAktualizacji")) or r["date"]
        out.append(_notice_record(source, prof, iso, name, date))
        if p.get("sections", True):
            out += _section_records(source, prof, iso, name, date)
    return out
