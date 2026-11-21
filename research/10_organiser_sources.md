# 10 — Organisers' sources: what they expect, what we hold, what a restriction costs

Date: 2026-11-21 (evening). Scope of work: the source registry (`data/sources/`), the corpus of organiser sources
(`data/corpus/`), the Google Fact Check provider and feeds, and three eval sets run under five registry variants
before the merge with `integration-2026-11-21` (cde02c9). The final run on the merged tree was stopped at the
owner's request before it finished. `data/corpus/demagog.jsonl` was not edited
here; it comes from the integration branch (2,973 records, page harvest).

Certainty tags: **[M]** measured today (command, request or eval run), **[D]** read in an organiser document,
**[I]** inferred, **[?]** could not be verified.

## 0. Bottom line

1. **The organisers name more than `resources.txt`.** Four documents carry their expectations: `resources.txt`
   (government sites + the Google fact-check database), the reference scenarios (Demagog, Odyseusz, PAP), the
   EUvsDisinfo instructions, and section 7 of the task text, which recommends dane.gov.pl, BIP, ISAP, EUR-Lex,
   IFCN/EFCSN fact-check corpora, EDMO, EUvsDisinfo, Check First and NASK material **[D]**. So ISAP/ELI, EUR-Lex and
   dane.gov.pl are *not* outside the organisers' list; only GUS, NBP, Eurostat, PKW and the EC Representation are.
   Demagog is the only fact-checker the organisers name. FakeNews.pl, AFP Sprawdzam, Konkret24 and Pravda are
   covered only by the general IFCN/EFCSN recommendation (`organiser_recommended`); no organiser document mentions
   them, even though FakeNews.pl and AFP reviews sit in the listed Google database **[D]**.
2. **Every registry entry now says where it stands** (`scope` + `scope_basis`), the catalogue shows it, and
   `python -m prawdowid.sources scope` fails when the knowledge base holds anything outside the scope.
3. **Recency:** every fetchable organiser news source now reaches back at least three months (to 21 Aug 2026 or
   earlier), most about six; see section 4 for counts by month **[M]**. Thirteen sources were followed back
   through the pagination the sites offer, with the existing fetchers. The two that fell short (KWP Radom, KGSOK)
   got a second pass. Sources that serve only their current state (RSO, IMGW warnings, the RCB daily report,
   Odyseusz) cannot be filled backwards.
4. **"Demagog through the API" is real.** The Google Fact Check Tools API lists Demagog's reviews, newest first,
   current to 20 Nov 2026 **[M]**. It now feeds the registry (`demagog_google_api`, `afp_sprawdzam`,
   `fakenews_google_api`). The live provider was corrected against real responses: it sent whole sentences,
   which the API does not answer. The page harvest already holds every Demagog review of the last 200 days that the
   API lists, so the API route adds one record. Its value is the organiser-named access path. The same handler
   also reaches AFP Sprawdzam, whose site refuses robots (39 records), and FakeNews.pl (0 records; its harvest
   holds them all).
5. **Restriction (GUS and NBP off) costs 8 of 145 eval cases [M]**: 129 → 121 correct, all of them numeric
   claims whose only decisive source is an official data card. It also removes 2 wrong verdicts. Recommendation:
   do not include it (section 8). The commit sits alone on the side branch `worktree-agent-a1cfe47c76fe0204b-restriction`, so merging this branch does
   not apply it.

## 1. Where the organisers say what they expect

| Document | What it names | Scope value |
|---|---|---|
| `rules/resources.txt` | 40 government URLs ("examples; you need not implement all") + "Baza weryfikatorów faktów": Google Fact Check Explorer and the Fact Check Tools API | `organiser_listed` |
| `rules/Czy we Włoszech…docx` (scenarios A–J) | Demagog in 8 of 10 example answers (three article links), the MSZ Odyseusz portal, a PAP dispatch as primary source, "indeks Google" in scenario J | `organiser_implied` |
| `rules/How_to_grab_all_Articles_and_Cases_from_disinfo.pdf` | EUvsDisinfo through the organisers' MCP server (token required) | `organiser_implied` |
| Task text, section 7 "Dostępne zasoby" | "Rekomendowane punkty odniesienia": dane.gov.pl, BIP, ISAP, EUR-Lex; corpora of IFCN/EFCSN organisations; EDMO, EUvsDisinfo, Check First, NASK material | `organiser_recommended` |
| Task text, section 5 | minimums: ≥ 100 documents, ≥ 10 domains, ≥ 2 source types, primary/official + credible secondary, publication and retrieval timestamps, current data preferred, auditable list | — |

`organiser_implied` is also used for the same site or institution as a listed URL (MSZ news next to the listed MSZ
page, cert.pl next to moje.cert.pl, the ums.gov.pl news feed, gov.pl myth-busting pages — about half of the latter
come from listed gov.pl sections, the rest from other ministries; `resources.txt` calls its list "examples" of
government domains). These four are judgement calls and are marked as such in `scope_basis`.

## 2. Mapping: organiser source → registry entry (measured)

"Before" is commit d4a73f0, "after" is this branch after the merge with integration. 30/90 days are counted from
2026-11-21 on `published_at`.

| Organiser source | Registry entry / corpus file | Method | Docs before → after | Newest | Last 30 d | Last 90 d (before → after) | Status | Note |
|---|---|---|---|---|---|---|---|---|
| odyseusz.gov.pl; gov.pl/web/dyplomacja/informacje-dla-podrozujacych | `msz_odyseusz` | `custom (msz_odyseusz)` | 200 → 1,195 | 2026-11-20 | 295 | 200 → 470 | covered | public JSON API of the portal; notice + 4 sections for each of 239 countries (before: the 40 most recently updated); each record is the advice in force, last updated Jun–Nov 2026 |
| gov.pl/web/gov/ostrzezenia (+ #/_/mazowieckie/wszystkie) | `rso_ostrzezenia` | `custom (rso_ostrzezenia)` | 96 → 100 | 2026-11-21 | 37 | 49 → 53 | covered | JS app; its public JSON API; only current alerts are served, history accumulates from now on |
| gov.pl/web/mswia/regionalny-system-ostrzegania | `mswia_rso_informacje` | `custom (static_pages)` | 1 | 2024-10-16 | 0 | 0 | covered (static page) | one descriptive page; its own date is 2024 |
| gov.pl/web/rcb/raport-dobowy3 | `rcb_raport_dobowy` | `custom (static_pages)` | 1 | 2026-11-21 | 1 | 1 | thin | page is overwritten daily; no archive is offered, so one snapshot per day from now on |
| gov.pl/web/kgpsp/aktualnosci | `kgpsp_aktualnosci` | `govpl_list` | 30 → 200 | 2026-11-20 | 35 | 30 → 103 | covered |  |
| policja.pl/pol/aktualnosci | `policja_aktualnosci` | `rss` | 15 → 214 | 2026-11-21 | 174 | 15 → 190 | covered | listing goes back only ~6 weeks densely; older listing pages hold 2013–2023 items (not kept) |
| mazowiecka.policja.gov.pl/ra/aktualnosci/aktualnosci | `kwp_radom_aktualnosci` | `rss` | 10 → 325 | 2026-11-21 | 94 | 10 → 281 | covered | back to 2026-08-10 |
| gov.pl/web/obrona-narodowa/aktualnosci5 | `mon_aktualnosci` | `govpl_list` | 30 → 200 | 2026-11-20 | 40 | 30 → 130 | covered |  |
| gov.pl/web/gis/ostrzezenia | `gis_ostrzezenia` | `govpl_list` | 30 → 48 | 2026-11-18 | 7 | 20 | covered |  |
| gov.pl/web/paa/panstwowa-agencja-atomistyki | `paa_aktualnosci` | `govpl_list` | 30 → 47 | 2026-11-20 | 11 | 25 | covered |  |
| monitoring.paa.gov.pl | `paa_monitoring` | `reference_only` | 0 | — | 0 | 0 | not fetchable | JS map of dose-rate measurements, no text; trusted link only |
| powietrze.gios.gov.pl/pjp/ | `gios_powietrze` | `reference_only` | 0 | — | 0 | 0 | not fetchable | maps and charts, no text notices; trusted link only (daily PM10 summary is in the RCB report) |
| moje.cert.pl/komunikaty/ | `cert_komunikaty` | `html_list` | 20 → 119 | 2026-11-19 | 22 | 20 → 66 | covered | robots.txt allows only /komunikaty/ |
| gov.pl/web/infrastruktura (+ /aktualnosci) | `mi_aktualnosci` | `govpl_list` | 30 → 131 | 2026-11-18 | 24 | 30 → 57 | covered |  |
| gov.pl/web/infrastruktura/prawa-pasazerow, /infolinia-dla-obywatela, /dane-kontaktowe | `mi_informacje_dla_obywateli` | `custom (static_pages)` | 3 | 2022-11-24 | 0 | 0 | covered (static pages) | three reference pages; their own dates are 2015–2022 |
| drogi.gddkia.gov.pl (informacje-drogowe, mapa, lista-utrudnien) | `gddkia_drogi` | `reference_only` | 0 | — | 0 | 0 | not fetchable | Imperva/Incapsula bot protection; road alerts reach us through RSO |
| gov.pl/web/gddkia/informacja-drogowa---19-111 | `gddkia_informacja_drogowa` | `custom (static_pages)` | 1 | 2025-07-10 | 0 | 0 | covered (static page) | one descriptive page dated 2025 |
| ulc.gov.pl (+ /prawa-pasazera, /poradnik-dla-pasazerow) | `ulc_prawa_pasazera` | `reference_only` | 0 | — | 0 | 0 | not fetchable | Imperva/Incapsula bot protection |
| portalpasazera.pl | `portal_pasazera` | `reference_only` | 0 | — | 0 | 0 | not fetchable | incomplete TLS certificate chain (verification not disabled) and dynamic content |
| utk.gov.pl/pl/pasazerowie | `utk_pasazerowie` | `reference_only` | 0 | — | 0 | 0 | not fetchable | robots.txt: Disallow: / for every robot but Googlebot |
| kgsok.pl | `kgsok_aktualnosci` | `rss` | 10 → 190 | 2026-11-18 | 57 | 10 → 174 | covered | back to 2026-08-05 |
| sar.gov.pl | `sar_morska_sluzba` | `reference_only` | 0 | — | 0 | 0 | not fetchable | Imperva/Incapsula bot protection |
| umgdy.gov.pl | `umgdy_aktualnosci` | `html_list` | 10 → 35 | 2026-11-05 | 4 | 10 → 16 | covered | low-volume source (~5 items a month) |
| ums.gov.pl/bezpieczenstwo-morskie/warunki-zeglugi | `ums_warunki_zeglugi` | `custom (static_pages)` | 1 | 2026-07-08 | 0 | 0 | covered | list of harbour-master notices (content in PDF) + the site's news feed |
|  | `ums_aktualnosci` | `rss` | 19 | 2026-11-03 | 1 | 5 |  |  |
| gov.pl/web/wody-polskie/komunikaty-nawigacyjne | `wody_polskie_komunikaty_nawigacyjne` | `custom (static_pages)` | 10 | 2026-11-20 | 9 | 9 | covered | 10 regional 'notices in force' pages |
| meteo.imgw.pl, hydro.imgw.pl, baltyk.imgw.pl | `imgw_ostrzezenia` | `custom (imgw_ostrzezenia)` | 36 | 2026-11-21 | 6 | 9 | covered (warnings) | JS maps; warnings come from IMGW's public data API; only current warnings are served |
|  | `imgw_meteo` | `reference_only` | 0 | — | 0 | 0 |  |  |
|  | `imgw_hydro` | `reference_only` | 0 | — | 0 | 0 |  |  |
|  | `imgw_baltyk` | `reference_only` | 0 | — | 0 | 0 |  |  |
| gov.pl/web/rcb/strona-glowna-rzadowego-centrum-bezpieczenstwa | `rcb_komunikaty` | `govpl_list` | 30 → 160 | 2026-10-27 | 6 | 30 → 113 | covered | the 20 newest alerts (to 2026-11-21) are the same pages as in `official_govpl_myths` and are kept there only (`dedupe_against`) |
| gov.pl/web/mswia | `mswia_aktualnosci` | `govpl_list` | 30 → 127 | 2026-11-16 | 13 | 30 → 54 | covered |  |
| gov.pl/web/premier | `kprm_wydarzenia` | `govpl_list` | 30 → 122 | 2026-11-20 | 23 | 30 → 58 | covered |  |
| Google Fact Check Explorer / Fact Check Tools API | `google_factcheck` | `google_factcheck` | 0 | — | 0 | 0 | covered (needs the key at runtime) | live keyword queries per claim + three feed sources listing one publisher's recent reviews; the Explorer web UI is not scraped |
|  | `demagog_google_api` | `custom (google_factcheck_feed)` | 0 → 1 | 2026-07-02 | 0 | 0 |  |  |
|  | `afp_sprawdzam` | `custom (google_factcheck_feed)` | 0 → 39 | 2026-11-19 | 8 | 0 → 16 |  | scope `organiser_recommended`: AFP is not named by the organisers |
|  | `fakenews_google_api` | `custom (google_factcheck_feed)` | 0 → 0 | — | 0 | 0 |  | scope `organiser_recommended`; all 19 reviews of the last 200 days are held by `fakenews_pl` |
| Demagog (scenarios; 'through the API') | `demagog` | `legacy_script` | 1,294 → 2,973 | 2026-11-20 | 54 | 178 | covered | page harvest from integration (adds 2024 and early 2025); complete for the last 200 days by the API cross-check |
| EUvsDisinfo (organisers' PDF) | `euvsdisinfo` | `legacy_script` | 300 | 2025-07-13 | 0 | 0 | stale | case pages return HTTP 403 (bot protection); the organisers' MCP server needs a token |
|  | `euvsdisinfo_mcp` | `custom (euvsdisinfo_mcp)` | 0 | — | 0 | 0 |  |  |
| PAP dispatches (scenarios A, F, I) | `pap` | `reference_only` | 0 | — | 0 | 0 | not fetchable (link only) | robots.txt blocks AI crawlers site-wide; rights reserved |

Sources outside `resources.txt`:

| Source | Scope | Enabled | Docs | Newest | Last 90 d |
|---|---|---|---|---|---|
| `demagog` (page harvest) | organiser_implied | yes | 2,973 | 2026-11-20 | 178 |
| `official_govpl_msz` — MSZ news | organiser_implied | yes | 310 | 2026-11-20 | 86 |
| `official_govpl_myths` — gov.pl myth-busting pages | organiser_implied | yes | 95 | 2026-11-21 | 29 |
| `official_cert` — cert.pl | organiser_implied | yes | 17 | 2026-11-03 | 6 |
| `euvsdisinfo` (HF mirror) | organiser_implied | yes | 300 | 2025-07-13 | 0 |
| `live_web` — records saved by the live search | organiser_implied | yes | 15 (10 duplicates of harvested pages removed) | 2026-10-27 | 1 |
| `fakenews_pl` | organiser_recommended | yes | 883 | 2026-11-13 | 10 |
| `afp_sprawdzam`, `fakenews_google_api` (via the Google database) | organiser_recommended | yes | 39 / 0 | 2026-11-19 | 16 / 0 |
| `konkret24` | organiser_recommended | yes | 290 | 2026-11-20 | 74 |
| `pravda` | organiser_recommended | yes | 269 | 2026-11-13 | 7 |
| `official_dane` — dane.gov.pl | organiser_recommended | yes | 47 | 2026-07-09 | 0 |
| `official_eli` — ISAP/ELI | organiser_recommended | yes | 33 | 2026-11-17 | 3 |
| `checkfirst` | organiser_recommended | yes | 31 | 2026-11-06 | 2 |
| `official_eurlex` — EUR-Lex | organiser_recommended | yes | 30 | 2024-06-24 | 0 |
| `official_gus` — GUS data cards | **outside** | yes | 72 | 2026-10-23 | 46 |
| `official_nbp` — NBP rates | **outside** | yes | 13 | 2026-11-20 | 12 |
| `official_eurostat` | **outside** | no (team, earlier) | 13 | 2026-11-20 | 12 |
| `official_pkw` | **outside** | no (team, earlier) | 10 | 2025-06-02 | 0 |
| `official_ec_pl` — EC Representation | **outside** | no (team, earlier) | 45 | 2026-11-07 | 6 |

## 3. What was fetched, and what could not be

All fetching used the registry fetchers (robots.txt per URL, fixed User-Agent, ≥ 1.5 s per host, one process per host,
no protection bypass, excerpt cap 4,000 characters). The run is reproducible with
`ingest/backfill_organiser_sources.py <group>`; about 2,200 page requests in total, plus ~240 to the Odyseusz API **[M]**.

| Source | Docs before → after | Oldest kept | Requests | How |
|---|---|---|---|---|
| `rcb_komunikaty` | 30 → 180 | 2026-07-04 | 168 | gov.pl listing, 18 pages |
| `kgpsp_aktualnosci` | 30 → 200 | 2026-05-09 | 181 | gov.pl listing, 20 pages |
| `mon_aktualnosci` | 30 → 200 | 2026-06-19 | 185 | gov.pl listing, 20 pages |
| `mswia_aktualnosci` | 30 → 127 | 2026-05-05 | 136 | gov.pl listing (150 fetched, 23 older than the cut-off dropped) |
| `kprm_wydarzenia` | 30 → 122 | 2026-05-05 | 190 | gov.pl listing (200 fetched, 78 older dropped) |
| `mi_aktualnosci` | 30 → 131 | 2026-05-05 | 135 | gov.pl listing (150 fetched, 19 older dropped) |
| `gis_ostrzezenia` | 30 → 48 | 2026-05-13 | 53 | gov.pl listing to its end (74 items in all) |
| `paa_aktualnosci` | 30 → 47 | 2026-05-06 | 36 | gov.pl listing to its end (59 items in all) |
| `policja_aktualnosci` | 15 → 214 | 2026-05-28 | 376 + 40 | listing pages 1–25 (`?page=N`); pages 18–25 hold 2013–2023 items — 136 dropped |
| `kwp_radom_aktualnosci` | 10 → 263 → 325 | 2026-08-10 | 270 + 16, then 82 | listing pages 1–16; second pass 1–20 |
| `cert_komunikaty` | 20 → 119 | 2026-06-12 | 111 + 3 | listing pages 1–12 |
| `kgsok_aktualnosci` | 10 → 150 → 190 | 2026-08-05 | 154, then 58 | WordPress feed pages 2–15; second pass 2–19 |
| `umgdy_aktualnosci` | 10 → 35 | 2026-06-09 | 56 | listing pages 1–6 (23 older dropped) |
| `afp_sprawdzam` (new) | 0 → 39 | 2026-05-07 | 1 API call | Google Fact Check Tools API, last 200 days |
| `demagog_google_api` (new) | 0 → 1 | 2026-07-02 | 5 API calls per run | same API: 429 reviews (408 pages) listed, 404 held by the page harvest, 1 kept here, 3 older than the cut-off |
| `fakenews_google_api` (new) | 0 → 0 | — | 1 API call | same API: 19 reviews, all 19 held by `fakenews_pl` (one only after decoding `%E2%82%82` = `%e2%82%82`) |
| `msz_odyseusz` (scheduled run) | 200 → 1,195 | 2026-06-30 | ~240 API calls | the portal's JSON API, every country |

Cut-off: newly fetched records older than 200 days (before 2026-05-05) are not kept — the owner asked for recent
material, and some listings also carry old items.

Data problems found and fixed on the way **[M]**:
- Police article pages carry no publication date; 16 of 263 (KWP Radom) got "1997-01-01" from the body text. Dates of
  both police sources are now taken from the listing's `<time datetime>`.
- `moje.cert.pl`: 3 of 119 advisories got the year of the vulnerability; the entry now has a `date_regex` for the date
  printed under the title (format DD-MM-YYYY, which `to_date` did not parse).
- gov.pl shows "02.09.2029" on a text about 2 Sep 2026. A publication date later than the retrieval date is now
  stored as "no date" rather than as the newest document in the base.

Not fetchable, with the reason **[M unless noted]**:

| Source | Reason | What we do instead |
|---|---|---|
| EUvsDisinfo, 2026 content | The site's listing answers (16 Poland-related cases Sep–Nov 2026) but every case page returns HTTP 403 (bot protection), also the sitemap. The organisers' MCP server answers 401 without a token. The HF mirror ends 2025-07-15. | Nothing new stored: a listing row is a title without the disproof, and a claim alone cannot be evidence. Needs `PRAWDOWID_EUVSDISINFO_TOKEN` (from the organisers) in the backend environment, then `python -m prawdowid.sources run euvsdisinfo_mcp` (~260 calls, ~5 min **[I]**). |
| PAP (pap.pl) | robots.txt blocks AI crawlers on the whole site except `/mediaroom`; rights reserved; the fact-checking section carries a TDM reservation (research/02) | New entry `pap`, `reference_only`: a trusted link target, no corpus, no live search |
| drogi.gddkia.gov.pl, ulc.gov.pl, sar.gov.pl | Imperva/Incapsula bot protection (earlier finding, not re-tested) | `reference_only`; road alerts arrive through RSO |
| utk.gov.pl | robots.txt `Disallow: /` for every robot but Googlebot (earlier finding) | `reference_only` |
| portalpasazera.pl | incomplete TLS chain + dynamic content (earlier finding) | `reference_only` |
| monitoring.paa.gov.pl, powietrze.gios.gov.pl, meteo/hydro/baltyk.imgw.pl | JS maps without text | `reference_only`; IMGW warnings come from its public data API |
| RCB daily report, RSO and IMGW warnings | only the current state is served, no archive | one snapshot per run; history accumulates from now on |
| Demagog's own REST API | `wp-json/wp/v2/posts` → HTTP 401 | Google Fact Check Tools API (section 9) + the page harvest |

## 4. Recency by month

Documents by publication month in the corpus files the index loads (enabled sources), on this branch after the
merge, counted on `published_at` **[M]**. "Last 90 d" = from 2026-08-23. Sources without any document are omitted
(the `reference_only` entries).

| Scope | Documents | Sep 2026 | Oct 2026 | Nov 2026 (to 21st) |
|---|---|---|---|---|
| organiser_listed | 3,267 | 458 | 759 | 513 |
| organiser_implied | 3,729 | 103 | 101 | 78 |
| organiser_recommended | 1,622 | 19 | 41 | 48 |
| outside (GUS, NBP) | 85 | 0 | 46 | 12 |
| **all enabled** | **8,703** | **580** | **947** | **651** |

Before this work (d4a73f0) the enabled sources held 4,382 documents, 1,017 of them from the last 90 days. Now: 8,703
and 2,304. The growth in older material comes from the integration branch's Demagog harvest: 2,973 records, 1,101
of them from 2024. Every organiser news source with a listing reaches back at least to 21 Aug 2026.
Odyseusz, RSO, IMGW and the RCB daily report hold the state in force, not an archive.

| Source | Scope | On | Docs | Sep 2026 | Oct 2026 | Nov 2026 (to 21st) | Last 90 d | Oldest | Newest |
|---|---|---|---|---|---|---|---|---|---|
| `msz_odyseusz` | organiser_listed | yes | 1195 | 60 | 265 | 135 | 470 | 2026-06-30 | 2026-11-20 |
| `kwp_radom_aktualnosci` | organiser_listed | yes | 325 | 92 | 102 | 65 | 281 | 2026-08-10 | 2026-11-21 |
| `policja_aktualnosci` | organiser_listed | yes | 214 | 9 | 58 | 121 | 190 | 2026-05-28 | 2026-11-21 |
| `kgpsp_aktualnosci` | organiser_listed | yes | 200 | 30 | 48 | 21 | 103 | 2026-05-09 | 2026-11-20 |
| `mon_aktualnosci` | organiser_listed | yes | 200 | 51 | 50 | 26 | 130 | 2026-06-19 | 2026-11-20 |
| `kgsok_aktualnosci` | organiser_listed | yes | 190 | 62 | 56 | 37 | 174 | 2026-08-05 | 2026-11-18 |
| `rcb_komunikaty` | organiser_listed | yes | 160 | 53 | 48 | 0 | 113 | 2026-07-04 | 2026-10-27 |
| `mi_aktualnosci` | organiser_listed | yes | 131 | 19 | 16 | 18 | 57 | 2026-05-05 | 2026-11-18 |
| `mswia_aktualnosci` | organiser_listed | yes | 127 | 17 | 22 | 8 | 54 | 2026-05-05 | 2026-11-16 |
| `kprm_wydarzenia` | organiser_listed | yes | 122 | 18 | 25 | 14 | 58 | 2026-05-05 | 2026-11-20 |
| `cert_komunikaty` | organiser_listed | yes | 119 | 23 | 22 | 13 | 66 | 2026-06-12 | 2026-11-19 |
| `rso_ostrzezenia` | organiser_listed | yes | 100 | 7 | 19 | 26 | 53 | 2026-01-28 | 2026-11-21 |
| `gis_ostrzezenia` | organiser_listed | yes | 48 | 5 | 7 | 5 | 20 | 2026-05-13 | 2026-11-18 |
| `paa_aktualnosci` | organiser_listed | yes | 47 | 9 | 9 | 7 | 25 | 2026-05-06 | 2026-11-20 |
| `imgw_ostrzezenia` | organiser_listed | yes | 36 | 0 | 2 | 5 | 9 | 2026-04-17 | 2026-11-21 |
| `umgdy_aktualnosci` | organiser_listed | yes | 35 | 3 | 10 | 2 | 16 | 2026-06-09 | 2026-11-05 |
| `wody_polskie_komunikaty_nawigacyjne` | organiser_listed | yes | 10 | 0 | 0 | 9 | 9 | 2026-05-05 | 2026-11-20 |
| `mi_informacje_dla_obywateli` | organiser_listed | yes | 3 | 0 | 0 | 0 | 0 | 2015-04-03 | 2022-11-24 |
| `demagog_google_api` | organiser_listed | yes | 1 | 0 | 0 | 0 | 0 | 2026-07-02 | 2026-07-02 |
| `gddkia_informacja_drogowa` | organiser_listed | yes | 1 | 0 | 0 | 0 | 0 | 2025-07-10 | 2025-07-10 |
| `mswia_rso_informacje` | organiser_listed | yes | 1 | 0 | 0 | 0 | 0 | 2024-10-16 | 2024-10-16 |
| `rcb_raport_dobowy` | organiser_listed | yes | 1 | 0 | 0 | 1 | 1 | 2026-11-21 | 2026-11-21 |
| `ums_warunki_zeglugi` | organiser_listed | yes | 1 | 0 | 0 | 0 | 0 | 2026-07-08 | 2026-07-08 |
| `demagog` | organiser_implied | yes | 2973 | 61 | 61 | 38 | 178 | 2014-04-29 | 2026-11-20 |
| `official_govpl_msz` | organiser_implied | yes | 310 | 33 | 33 | 15 | 86 | 2026-01-07 | 2026-11-20 |
| `euvsdisinfo` | organiser_implied | yes | 300 | 0 | 0 | 0 | 0 | 2016-01-04 | 2025-07-13 |
| `official_govpl_myths` | organiser_implied | yes | 95 | 2 | 4 | 23 | 29 | 2018-03-28 | 2026-11-21 |
| `ums_aktualnosci` | organiser_implied | yes | 19 | 3 | 1 | 1 | 5 | 2026-02-23 | 2026-11-03 |
| `official_cert` | organiser_implied | yes | 17 | 4 | 1 | 1 | 6 | 2026-06-12 | 2026-11-03 |
| `live_web` | organiser_implied | yes | 15 | 0 | 1 | 0 | 1 | 2017-05-16 | 2026-10-27 |
| `fakenews_pl` | organiser_recommended | yes | 883 | 4 | 2 | 2 | 10 | 2019-09-16 | 2026-11-13 |
| `konkret24` | organiser_recommended | yes | 290 | 5 | 31 | 36 | 74 | 2022-11-18 | 2026-11-20 |
| `pravda` | organiser_recommended | yes | 269 | 3 | 1 | 3 | 7 | 2020-08-02 | 2026-11-13 |
| `official_dane` | organiser_recommended | yes | 47 | 0 | 0 | 0 | 0 | 2019-08-28 | 2026-07-09 |
| `afp_sprawdzam` | organiser_recommended | yes | 39 | 5 | 6 | 5 | 16 | 2026-05-07 | 2026-11-19 |
| `official_eli` | organiser_recommended | yes | 33 | 1 | 1 | 1 | 3 | 1997-04-02 | 2026-11-17 |
| `checkfirst` | organiser_recommended | yes | 31 | 1 | 0 | 1 | 2 | 2021-12-10 | 2026-11-06 |
| `official_eurlex` | organiser_recommended | yes | 30 | 0 | 0 | 0 | 0 | 2001-07-20 | 2024-06-24 |
| `official_gus` | outside | yes | 72 | 0 | 46 | 0 | 46 | 2026-03-24 | 2026-10-23 |
| `official_nbp` | outside | yes | 13 | 0 | 0 | 12 | 12 | 2026-03-05 | 2026-11-20 |
| **enabled total** | | | **8703** | **580** | **947** | **651** | **2304** | | |

## 5. Sources outside the list and what depends on them

Measured in the `open` eval run (145 cases of `eval/cases*.jsonl`; branch corpus, no restriction). "Decisive" means
the source supplied the supporting or refuting fragment of the verdict **[M]**.

| Source (scope) | Enabled | Docs | Decisive in | Other dependencies |
|---|---|---|---|---|
| `official_gus` — GUS data cards (outside) | yes | 72 | 9 cases: A1, A2, H17, H18, H44, H50, H52, H53, B2-27 (CPI inflation, registered unemployment, births) | engine's deterministic number check against an official data card (`engine.numeric_stance`); the "where to look" hint names GUS, NBP, Eurostat; `docs/DEMO.md` and `web/metodologia.html` cite GUS examples |
| `official_nbp` — NBP rates (outside) | yes | 13 | 4 cases: A3, H19, B2-23, B2-26 (EUR/USD mid rate, reference rate) | same number check |
| `official_eurostat` (outside) | no (team, earlier) | 13 | in `all_on` it would decide A6, B2-24, B2-29 (all now abstentions) | — |
| `official_pkw` — election results (outside) | no (team, earlier) | 10 | in `all_on` it would decide H21, B2-28 (now abstentions) | — |
| `official_ec_pl` — EC Representation (outside) | no (team, earlier) | 45 | none | — |
| `official_eli` — ISAP/ELI (recommended) | yes | 33 | 4 cases: A4, H22, B2-21, B2-22 | — |
| `official_eurlex` (recommended) | yes | 30 | 3 cases: A5, H24, B2-25 | — |
| `fakenews_pl` (recommended) | yes | 883 | 15 cases (e.g. F2, F3, F5, H02, H03, B2-01, B2-03) | — |
| `pravda` (recommended) | yes | 269 | 8 cases (B1, T2, H04, H06, H11, B2-10, B2-47, H26) | — |
| `konkret24`, `checkfirst`, `official_dane` (recommended) | yes | 290 / 31 / 47 | none (cited as context in 22 / 2 / 0 cases) | — |

For comparison: Demagog is decisive in 32 cases. Of the organiser news sources only `kprm_wydarzenia` (H27) and
`official_govpl_msz` (I1) decide a case. The ~1,500 documents of the backfill changed no outcome: `pre` (the
corpus before it) and `open` give identical results case by case. The organisers' reference scenarios name no
statistics source. Scenario A of the task text ("Fakt prosty": a correct verdict and an exact quote from a
*primary* source) is where every GUS/NBP case sits **[D]**.

## 6. Scope in the registry, and the restriction commit

- `scope`: `organiser_listed` | `organiser_implied` | `organiser_recommended` | `outside`; anything unmarked is
  `outside`. `scope_basis` (required for the first three) names the document and place. Contract:
  `docs/SOURCE_REGISTRY.md`; shown in `/zrodla`, `/api/sources`, `docs/SOURCES.md`.
- `python -m prawdowid.sources scope [--strict]` prints the sources by scope and exits 1 when the knowledge base holds
  something outside it: an enabled `outside` source, a corpus file without a registry entry (the index loads those),
  or live-search records that came from a source now disabled. `--strict` narrows the scope to list + scenarios.
- `python -m prawdowid.sources scope --restrict [--strict]` disables (never deletes) the offending sources and writes
  the reason to `notes`. The restriction commit is exactly that command without `--strict` (GUS and NBP switched
  off). It is one commit on the side branch `worktree-agent-a1cfe47c76fe0204b-restriction`, on top of this branch, and merging it is the owner's decision.
- `demagog.json` now carries its scope keys itself; `registry.DEFAULT_SCOPE` stays as the fallback.

## 7. Measured effect of restricting the knowledge base

Eval run of 21 Nov 2026, 20:43–21:40, under the shared model lock, before the merge with integration (engine of
d4a73f0, branch corpus of fa90358/cef9e9e) **[M]**. `eval/run_eval.py` with `PRAWDOWID_LIVE_SEARCH=0`, one registry
copy per variant, same corpus and embedding cache. Scripts and outputs:
`scratchpad/orgsrc/{run_evals.sh,mkcfg.py,compare.py,minimums.py}` and `evalout/<variant>/<set>/`.

- `pre`: corpus and registry of d4a73f0 (before the backfill).
- `open`: this branch, no restriction.
- `restricted`: `outside` sources off (GUS, NBP).
- `strict`: also `organiser_recommended` off (FakeNews.pl, Konkret24, Pravda, ISAP/ELI, EUR-Lex, dane.gov.pl, Check
  First).
- `all_on`: also the three sources the team had switched off earlier (Eurostat, PKW, EC Representation).

"Wrong verdict" = a decisive verdict (true / false / misleading) that is not an accepted answer. "Wrong
abstention" = "no evidence" where a decisive verdict was expected. Nothing else failed.

| Variant | `cases` (38) | `cases_heldout` (57) | `cases_blind2` (50) | All 145: correct / wrong verdicts / wrong abstentions |
|---|---|---|---|---|
| `pre` | 37 / 0 / 1 | 50 / 2 / 5 | 42 / 0 / 8 | 129 / 2 / 14 |
| `open` | 37 / 0 / 1 | 50 / 2 / 5 | 42 / 0 / 8 | **129 / 2 / 14** |
| `restricted` | 34 / 0 / 4 | 48 / 0 / 9 | 39 / 0 / 11 | **121 / 0 / 24** |
| `strict` | 27 / 1 / 10 | 39 / 1 / 17 | 31 / 0 / 19 | 97 / 2 / 46 |
| `all_on` | 38 / 0 / 0 | 53 / 0 / 4 | 45 / 0 / 5 | 136 / 0 / 9 |

**`open` → `restricted`: 13 cases change** (`compare.py`).
- 10 correct answers become abstentions: A1, A2, H17, H18 and B2-27 (GUS CPI inflation), H50 (GUS inflation in a
  multi-claim post), A3, H19, B2-23 and B2-26 (NBP EUR/USD rate, reference rate). In each the GUS/NBP data card
  was the only supporting or refuting document; without it only Demagog/Pravda context remains.
- 2 wrong verdicts become correct abstentions: H52 and H53 (unemployment and inflation for September 2026, which
  the expected answer leaves open). The GUS card refuted them with a figure for a different period.
- H44 (an injection case whose births claim accepts either answer) stays correct (confirmed → no evidence).
- Net: −8 correct, −2 wrong verdicts.

**`open` → `strict`: 40 changes, −32 correct.** 34 cases lost: FakeNews.pl decisive in 7, GUS 6, Pravda 5, NBP 4,
ISAP/ELI 4, EUR-Lex 3, Demagog+Pravda 1, and 4 by changed ranking. H52 and H53 are gained as above. One new wrong
verdict each appears in B1 and H02.

**`open` → `all_on`: 7 changes, +7 correct, −2 wrong verdicts.** Eurostat decides A6, B2-24 and B2-29, PKW decides H21
and B2-28, and H52/H53 become correct abstentions. Shown for completeness: it points the other way from the owner's
instruction.

**Corpus minimums of the task (section 5) [M]** (`minimums.py`, files the index loads):

| Variant | Documents | Domains | Source types | Primary (official) + secondary (fact-check) | Last 90 d |
|---|---|---|---|---|---|
| `open` | 5,956 | 24 | factcheck 2,794 · official 2,831 · incident 331 | yes | 2,011 |
| `restricted` | 5,871 | 21 | factcheck 2,794 · official 2,746 · incident 331 | yes | 1,953 |
| `strict` | 4,288 | 15 | factcheck 1,352 · official 2,636 · incident 300 | yes | 1,857 |

Every variant satisfies ≥ 100 documents, ≥ 10 domains, ≥ 2 source types and primary + secondary sources.
**Does any expected case lose its only source? Yes.** Under `restricted`, the 10 cases above lose their only decisive
document: no organiser source publishes CPI, unemployment or NBP rates. Under `strict`, 34 do.
The minimums hold; the scenario-A coverage does not.

## 8. Recommendation

**Do not include the restriction commit (GUS and NBP off). Keep the scope field and the `scope` check.**

1. *It costs exactly the material scenario A needs.* The task text's mandatory scenario A asks for a correct verdict
   and an exact quote from a primary source **[D]**. All 10 lost cases are of that kind, and no organiser-listed
   source publishes the figures: GUS for inflation, unemployment and wages, NBP for rates. Without them the system
   abstains on every official-statistics claim **[M]**.
2. *The organisers' list does not exclude them.* `resources.txt` calls its government sites "examples; you need not
   implement all". The task text requires primary/official sources and recommends dane.gov.pl, BIP, ISAP and EUR-Lex
   for them **[D]**. GUS and NBP are the publishers of the data those portals carry: unnamed primary sources, not
   unreliable ones **[I]**.
3. *The two wrong verdicts it removes have a cheaper cause.* H52/H53 are a GUS card for another period refuting a
   September claim. `all_on` fixes them without losing anything (the extra sources change which card the engine
   picks) **[M]**. Whether that is robust is untested; the period mismatch in the number check is worth its own fix
   **[I]**.
4. *If the owner reads "only the organisers' sources" literally*, the restriction commit is ready on `worktree-agent-a1cfe47c76fe0204b-restriction`. It only flips
   `enabled` on two registry entries and writes the reason into `notes`; no corpus file is touched, and dropping or
   reverting the commit restores both sources. Expect −8 of 145 on these sets and abstention on every
   official-statistics claim. `strict` (−32) is not advisable under any reading.

The decision is the owner's: the instruction ("only those") and the measured effect point in different
directions.

## 9. Demagog "through the API"

**What exists [M].** Demagog's own WordPress REST API is closed (HTTP 401). The route that exists and is named by the
organisers is the Google Fact Check Tools API, `claims:search`. With `reviewPublisherSiteFilter=demagog.org.pl` and no
query it lists Demagog's reviews, newest first (roughly — not strictly sorted), 100 per page with `nextPageToken`:
429 reviews in the last 200 days, the newest dated 2026-11-20. With the same filter and period: `fakenews.pl` 19
reviews, `sprawdzam.afp.com` 39 (74 in 400 days). konkret24.tvn24.pl, pravda.org.pl and euvsdisinfo.eu return
nothing. Every review in these listings has `languageCode` `pl` **[M]**. Each
review carries the claim, claimant, claim date, review URL, title, review date, `textualRating` and language — no
article text. About 110 calls were made today, 0.2–1.5 s each; no HTTP 429 and no quota headers were returned, so
the quota is visible only in the Google Cloud console **[?]**.

**Cross-check of the page harvest [M].** The 429 Demagog reviews of the last 200 days point to 408 pages; one page
can review several claims. 404 are in `demagog.jsonl`, 1 (`analizy_i_raporty`, a section the harvest does not
cover) is in `demagog_google_api.jsonl`, and 3 are re-reviews of 2016–2024 articles, below the review-date cut-off. The
Demagog corpus is complete for that period. FakeNews.pl: all 19 reviews are in `fakenews_pl.jsonl`. One matched
only after decoding percent-escapes: the harvests store `co%e2%82%82`, the API sends `co%E2%82%82`.

**What was wrong in our provider, found with real responses [M], now fixed:**
1. *Queries.* The provider sent the whole claim sentence. The API returns nothing for sentences or questions
   ("Czy PAP usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią?" → 0) and answers keyword queries ("Donalda
   Tuska PAP wypowiedzi" → the Demagog review). `google_search` now sends keyword rounds (4 most distinctive words;
   the claim's opening words; 3 words; pairs) and stops at the first round that returns a review from a registry
   domain. Real results: scenario G (65-year-olds in Wrocław) → Demagog, "Fałsz", 2024-03-12, 1 call; scenario A
   (PAP dispatch) → Demagog, "Fałsz", 2024-09-16, 1 call; scenario C (700 mln) → a Demagog review on Wrocław's
   transport spending, 2 calls; an AFP claim → AFP, 2 calls. **Not found:** scenario J's wording ("darmowymi
   przejazdami") → 0 results after 6 calls, because the review says "darmowa komunikacja" — that answer must come
   from the local corpus.
2. *Rating labels.* The live mapping was a shorter copy of the corpus mapping: "Częściowy fałsz" became `false`
   instead of `mixed`, "Przerobione zdjęcie/film" had no class — 104 of 1,294 Demagog labels mapped differently.
   The API also returns lower-case and free-text variants ("fałsz", "przerobione zdjęcie", "brakujący kontekst") and
   AFP's "Obraz AI" and "Mylące". One rule list now serves both paths; a test fails if they drift apart. Every
   distinct label the API returned today maps to the class the corpus gives the same wording. That is 26 for
   Demagog (12 of them lower-case variants), 4 for FakeNews.pl ("fałsz", "Fałsz", "manipulacja", "Brak kontekstu")
   and 5 for AFP. `backend/tests/test_google_factcheck.py::API_LABELS` holds the full list.
3. *Key in the URL.* The key was a query parameter, and httpx logs request URLs at INFO level. It now travels in the
   `X-Goog-Api-Key` header (accepted by the API).
4. *Site filter.* Not used before. It returned the same reviews as the general query in every test, so it is now
   sent only when a general result page is full of other publishers.
- Unchanged and confirmed: `languageCode=pl`; only reviews on a domain of an **enabled** registry source become
  evidence (others are counted); an outage gives "Nie mogę teraz sprawdzić indeksu Google…", never "no such article".

**Ingest as registry sources.** `google_factcheck_feed` (custom handler) lists one publisher's reviews, newest
first, last 200 days by review date, each into its own corpus file. Entries: `demagog_google_api` (every 6 h, 5
calls), `afp_sprawdzam` (every 12 h, 1 call) and `fakenews_google_api` (every 12 h, 1 call; 0 records today, since
the page harvest holds all 19). Demagog records carry the page harvest's id (`demagog:<section>/<slug>`, with the
harvest's lower-case escapes), so the index keeps one copy whichever route delivers it first. FakeNews.pl's harvest
uses post ids the API cannot give. There `dedupe_against` decides: URLs held by a corpus the index loads are skipped
at fetch time and removed from the feed's file at every merge. If the harvest is switched off, the feed delivers
the reviews itself.

**Which publishers, and how that was decided [D].** No organiser document names FakeNews.pl or AFP Sprawdzam:
`resources.txt`, the task text, the scenarios and the EUvsDisinfo instructions have 0 mentions. The organisers name
Demagog (scenarios, and "Demagog through the API") and list the Google database itself: the Explorer's recent
Polish reviews and the API. The database holds FakeNews.pl and AFP reviews, but pointing to a database is not naming
its publishers. Both feeds are therefore `organiser_recommended`, on the task text's general recommendation of
IFCN/EFCSN fact-check corpora, like the FakeNews.pl page harvest. They stay in under the default scope and drop out
under the strict one. (They were first marked `organiser_listed`. That overstated the list and was corrected in a
separate commit.) AFP's site refuses robots (403), so nothing is fetched from it directly. AFP is decisive in no eval
case; it is cited as context in one.

**What may be quoted from an API record.** The record's text is two verbatim strings written by the fact-checker:
the review title and the claim it reviewed. A quotation from it is one of those two, shown with the rating label
and the link; it proves that the publisher checked this claim and how it rated it. It is not a passage of the
article's reasoning, and the record is tagged `claimreview-only`. Where the article is in the corpus (Demagog), the
fuller record is used. One trap, measured: 2 of 74 AFP reviews put the *conclusion* into the claim field ("Nagranie
nie pokazuje…", rated "Fałsz"); attaching the rating to that sentence would call the debunk false. Such records
(claim ≈ declarative headline) are stored without a claim and without a verdict class.

**What the owner must do.** The key exists in the main checkout's `.env`, but the application does not read `.env`:
start the backend with `PRAWDOWID_GOOGLE_FACTCHECK_KEY` in its environment (and pass it to the container). `compose.yaml` passes
only the moderator token today, and `.env.example` does not list the Google key. Then the live provider is active
for every factual claim and the three feed sources run on schedule. Without the variable the
provider stays silent — no request and **no notice to the user that Google was not consulted**, which sits badly
with scenario J ("brak klucza… ujawnienie ograniczenia"); that message lives in the service layer and was left alone.

## 10. Final run on the merged tree

Skipped: the owner stopped all model runs before the final eval of the merged tree finished, so there are no numbers for it.

## 11. Not verified

- Google's quota for the key (no headers; console only) and whether pair queries under load stay inside the 4 s budget
  (zero-result calls took up to 1.5 s).
- How the engine ranks `claimreview-only` records in a live demo. In the three eval sets they changed no result
  (section 7), but those sets contain no AFP claims.
- The merged tree is unmeasured. The final run was stopped before it finished (section 10), so nothing measures
  the integration engine together with the 2024 Demagog records, the 1,195 Odyseusz records, the deeper KWP/KGSOK
  backfill and the dedupe. All eval numbers in this report predate the merge.
- Duplicates can return. The index loads records by id, not URL, and live search can save a page that a harvest
  picks up later (10 such pairs were removed after the merge). `dedupe_against` covers only sources that merge
  through the registry fetchers, not legacy scripts or `live_web`.
- EUvsDisinfo through the MCP server (no token). The `id_prefix` fix for it was checked on a sample record only.
- IFCN/EFCSN status of the fact-checkers is taken from research/02, not re-checked.
- Whether `web/metodologia.html` and `docs/DEMO.md` should stop mentioning GUS/NBP if the restriction is kept —
  those files belong to other work and were not edited.
