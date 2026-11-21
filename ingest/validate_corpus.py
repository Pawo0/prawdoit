#!/usr/bin/env python3
"""Validate data/corpus/*.jsonl against the corpus schema and write an auditable manifest.

By default only the fact-check/incident files produced by this harvester set (FACTCHECK_SOURCES)
are validated; pass --all to include every *.jsonl in data/corpus (e.g. official_* from other
pipelines). Checks: exact key set, enums (source_type, verdict), date formats, text length <= 4000,
unique ids. Writes data/corpus/manifest_factchecks.json (per-file counts, publishers, domains,
licences, date ranges, retrieval window, access method) and prints a summary table.
Exit code 1 if any record is invalid.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

from common import CORPUS_DIR, MAX_TEXT, SCHEMA_KEYS, SOURCE_TYPES, VERDICTS

ACCESS = {
    "demagog": "Yoast sitemaps + article HTML (schema.org ClaimReview JSON-LD); WP REST API closed (401)",
    "fakenews_pl": "WordPress REST API /wp-json/wp/v2/posts (ACF fields teza/autor/ocena)",
    "pravda": "Ghost sitemap-posts.xml + article HTML; claim/verdict joined from Google Fact Check Tools "
              "(Data Commons) ClaimReview feed",
    "konkret24": "section landing pages + related-article links (NewsArticle JSON-LD); short excerpts only",
    "euvsdisinfo": "euvsdisinfo.eu database listing (keyword x date slices, no pagination per robots) + "
                   "HF mirror NLP-UniBW/eu_vs_disinfo for case text (site served Cloudflare challenge)",
    "checkfirst": "WordPress REST API /wp-json/wp/v2/posts",
}
FACTCHECK_SOURCES = list(ACCESS)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")


def main() -> int:
    all_files = "--all" in sys.argv
    bad = 0
    ids: set[str] = set()
    manifest = {"files": {}, "totals": {}}
    tot_types: Counter = Counter()
    tot_domains: Counter = Counter()
    tot_lang: Counter = Counter()
    tot_verdict: Counter = Counter()
    n_all = 0
    files = sorted(CORPUS_DIR.glob("*.jsonl"))
    if not all_files:
        files = [f for f in files if f.stem in FACTCHECK_SOURCES]
    for fp in files:
        src = fp.stem
        agg = defaultdict(Counter)
        pub_dates, ret_dates = [], []
        n = 0
        for ln, line in enumerate(fp.open(encoding="utf-8"), 1):
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"{fp.name}:{ln} JSON error {e}")
                bad += 1
                continue
            errs = []
            if list(r.keys()) != SCHEMA_KEYS:
                errs.append(f"keys {sorted(set(r) ^ set(SCHEMA_KEYS))}")
            if r.get("source_type") not in SOURCE_TYPES:
                errs.append(f"source_type {r.get('source_type')}")
            if r.get("verdict") not in VERDICTS:
                errs.append(f"verdict {r.get('verdict')}")
            if r.get("published_at") is not None and not DATE.match(str(r["published_at"])):
                errs.append(f"published_at {r['published_at']}")
            if not ISO.match(str(r.get("retrieved_at"))):
                errs.append(f"retrieved_at {r.get('retrieved_at')}")
            if not r.get("title") or not r.get("url") or not r.get("text"):
                errs.append("empty title/url/text")
            if len(r.get("text") or "") > MAX_TEXT:
                errs.append(f"text too long {len(r['text'])}")
            if not isinstance(r.get("tags"), list):
                errs.append("tags not list")
            if r.get("id") in ids:
                errs.append(f"duplicate id {r.get('id')}")
            ids.add(r.get("id"))
            if errs:
                bad += 1
                print(f"{fp.name}:{ln} {r.get('id')}: {'; '.join(errs)}")
                continue
            n += 1
            for k in ("publisher", "domain", "source_type", "language", "license", "verdict"):
                agg[k][str(r[k])] += 1
            if r["published_at"]:
                pub_dates.append(r["published_at"])
            ret_dates.append(r["retrieved_at"])
        n_all += n
        tot_types.update(agg["source_type"])
        tot_domains.update(agg["domain"])
        tot_lang.update(agg["language"])
        tot_verdict.update(agg["verdict"])
        manifest["files"][fp.name] = {
            "records": n,
            "access_method": ACCESS.get(src, ""),
            "publishers": dict(agg["publisher"]),
            "domains": dict(agg["domain"]),
            "source_types": dict(agg["source_type"]),
            "languages": dict(agg["language"]),
            "verdicts": dict(agg["verdict"]),
            "licenses": list(agg["license"]),
            "published_range": [min(pub_dates), max(pub_dates)] if pub_dates else None,
            "retrieved_range": [min(ret_dates), max(ret_dates)] if ret_dates else None,
        }
    manifest["totals"] = {"records": n_all, "source_types": dict(tot_types), "domains": dict(tot_domains),
                          "n_domains": len(tot_domains), "languages": dict(tot_lang),
                          "verdicts": dict(tot_verdict), "invalid_records": bad}
    (CORPUS_DIR / ("manifest_all.json" if all_files else "manifest_factchecks.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
    print(f"{'file':28} {'n':>5}  types / languages / published range")
    for f, m in manifest["files"].items():
        print(f"{f:28} {m['records']:>5}  {m['source_types']} {m['languages']} {m['published_range']}")
    t = manifest["totals"]
    print(f"TOTAL {t['records']} records, {t['n_domains']} domains, source_types={t['source_types']}, "
          f"languages={t['languages']}, verdicts={t['verdicts']}, invalid={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
