# 02 — Fact-check and disinformation sources for the Prawdowid corpus

*Research and harvest date: 21 Nov 2026. Scope: fact-checker corpora and disinformation-incident databases for grounding verdicts. Official/state sources are covered by the `official_*` pipeline.*

*Markers:*
- ***[V]*** = verified today by probing the site with our bot (robots.txt, HTTP status, API, markup).
- ***[3P]*** = desk research from a secondary source or search snippet.
- ***[UNVERIFIED]*** = not confirmed.

All probes used User-Agent `PrawdowidHackathonBot/0.1 (research prototype)`. We did **not** retry blocked sites with a browser User-Agent. A 403 or challenge served to our bot counts as "no".

---

## TL;DR

| # | Source | Machine access for our bot | Licence / terms (short) | IFCN / EFCSN | In corpus |
|---|---|---|---|---|---|
| 1 | **Demagog** (demagog.org.pl) | **Yes.** Sitemaps + HTML with **ClaimReview JSON-LD**. WP REST API closed (401). [V] | Own "Ogólne Warunki Licencji": non-commercial reuse, no modification, attribution + link. Content-Signal `ai-train=no, use=reference`. [V] | EFCSN verified (to May 2027) [3P]; IFCN since 2019 [3P] | **380** |
| 2 | **FakeNews.pl** (Fundacja „Przeciwdziałamy Dezinformacji") | **Yes.** Open WP REST API with ACF fields `teza/autor/ocena`. Also ClaimReview in HTML. [V] | © fakenews.pl, no open licence [V] | IFCN application 2021–22, status [UNVERIFIED]; not in EFCSN [3P] | **500** |
| 3 | **Stowarzyszenie Pravda** (pravda.org.pl) | **Yes.** Ghost sitemap + HTML. Claim/verdict via the Google ClaimReview feed. [V] | No licence stated, so all rights reserved [V] | EFCSN verified (to Feb 2028) [3P] | **269** |
| 4 | **Konkret24** (TVN24) | **Partly.** Section pages + NewsArticle JSON-LD. No sitemap; RSS is empty; `?page=` is disallowed; no ClaimReview; no verdict labels. [V] | © TVN. Reuse needs consent; art. 25 reservation [3P]. **Short excerpts only.** | Not in EFCSN; IFCN [UNVERIFIED]; CEDMO partner [3P] | **120** |
| 5 | **EUvsDisinfo** (EEAS) | **Partly.** Listing is OK, but robots forbids `/page/`, so we use keyword × date slices. Case pages hit a **Cloudflare challenge** after about 70 requests. We fell back to the HF mirror. [V] | "Reuse is authorised, provided the source is acknowledged" (EEAS legal notice, Decision 2011/833/EU) [3P] | n/a (EU institution) | **300** (EN) |
| 6 | **CheckFirst** (checkfirst.network) | **Yes.** Open WP REST API; llms.txt explicitly welcomes RAG with attribution. [V] | © CheckFirst; "read, index and cite… attribute + link" [V] | n/a (OSINT firm) | **31** (EN) |
| 7 | **AFP Sprawdzam** (sprawdzam.afp.com) | **No.** Akamai **403 on every URL, including robots.txt**. Not in the Google ClaimReview feed either. [V] | AFP terms [UNVERIFIED] | IFCN [3P]; AFP is EFCSN-verified (FR) [3P] | 0 |
| 8 | **PAP FakeHunter** (now pap.pl/fact-checking) | **No.** Imperva JS challenge. `x-robots-tag: noai`, `tdm-reservation: 1`. [V] | Personal use only; TDM opt-out (art. 26³) [3P] | Claims IFCN principles; not a signatory [3P] | 0 |
| 9 | **OKO.press** | **Poor.** Headless Next.js (no WP API); sitemaps exist; no fact-check category in the sitemap. Only 1 ClaimReview in the Google feed. [V] | Regulamin §10.3: no copying without consent [3P] | Methodology "zgodne z IFCN" [3P] | 0 |
| 10 | **EDMO** (edmo.eu) / **CEDMO** (cedmohub.eu) | **No.** 403 to our bot, including robots.txt. [V] The repository is search-UI only, no API. [3P] | "© All Rights Reserved" [3P] | — | 0 |
| 11 | **Google Fact Check Tools API** | Needs an **API key** (we have none) [3P] | Google APIs ToS [3P] | — | 0 (option) |
| 12 | **Data Commons / Google ClaimReview feed** | **Yes.** A 201 MB JSON was refreshed today; we stream it. [V] | Was CC BY on the old page [3P] | — | used for Pravda |
| 13 | **MultiClaim** (Pikuliak et al. 2023) | Zenodo, **request form, research-only, no re-sharing** [3P] | restricted | — | 0 |

**Result.** We harvested **1,600 records** in 6 JSONL files, from 6 publishers and 6 domains:
- 1,269 `factcheck` records (Polish) and 331 `incident` records (English).
- `verdict` counts: false 976, misleading 120, true 91, unverifiable 49, mixed 29, null 335.

Every record has both `published_at` and `retrieved_at`; 1,283 records carry an explicit `claim`. The auditable per-file manifest, with licences, access method, date ranges and counts, is `data/corpus/manifest_factchecks.json`.

---

## 1. Source-by-source

### 1.1 Demagog — demagog.org.pl (Stowarzyszenie Demagog)

**Machine access [V]**
- `/wp-json/` responds, but every content route returns `401 itsec_rest_api_access_restricted` (Kadence Security). Interesting custom post types exist anyway: `wypowiedzi`, `fake_news`, `obietnice`, `analizy_i_raporty`, plus taxonomies `ocena_wypowiedzi`, `tematy`, `osoby` and `partie`.
- Yoast sitemap index `/sitemap_index.xml` works. It lists `fake_news-sitemap{,2..4}.xml` (**3,903 PL URLs**) and `wypowiedzi-sitemap{,2..7}.xml` (**6,545 PL URLs**), plus EN and UA translations.
- There is no `lastmod`. The order is ascending by post ID, so the tail of the last sitemap holds the newest items.
- Every fact-check embeds **schema.org `ClaimReview`** JSON-LD with these fields:
  - `claimReviewed`
  - `itemReviewed.author.name` (politician, or "Wiele źródeł")
  - `itemReviewed.appearance[].url`
  - `reviewRating.alternateName` (the verdict)
  - `datePublished`
- Yoast `WebPage` JSON-LD carries the title and dates. Topic tags are in `.dg-post-content__tags--desktop a[href*="/tematy/"]`.

**robots.txt [V]**
- `User-agent: * Allow: /` with Cloudflare **Content-Signal `search=yes, ai-train=no, use=reference`**, declared an Art. 4 DSM reservation.
- Named AI crawlers (ClaudeBot, GPTBot, CCBot…) are disallowed. Our own UA is not named.
- How we read it: retrieval-augmented answers that cite and link Demagog = "reference" use, which is OK. Training on the content is not allowed.

**Licence [V]** — demagog.org.pl/zasady-udostepniania-tresci, "Ogólne Warunki Licencji":
- All works © Stowarzyszenie Demagog.
- **Non-commercial reuse is allowed without modification.** Shortening that does not distort the meaning is allowed.
- Attribution is mandatory, e.g. "Źródło informacji: www.demagog.org.pl", plus a link to the original page.
- Derivatives must be shared on the same non-commercial terms. Commercial use needs written consent. Statutory "dozwolony użytek" (quotation, short excerpts) also applies.
- **What this means for us:** store claim + verdict + an unmodified excerpt (≤3,000 chars) + link; always show "Źródło: demagog.org.pl"; non-commercial prototype only.

**Volume and coverage**
- About 10.4k Polish fact-checks.
- Statements ("wypowiedzi") go back to 2014; fake-news debunks run from 2020 to today.
- Topics: Ukraine, health/vaccines, security, Russia, EU, migration, climate/energy, AI scams.

**Verdict scale [V/3P]**
- Statements: **Prawda / Częściowa prawda / Fałsz / Manipulacja / Nieweryfikowalne**.
- Fake news, as seen in ClaimReview: Fałsz, Manipulacja, Brakujący kontekst, Brak kontekstu, Częściowy fałsz, Przerobione zdjęcie/wideo, Prawda, Satyra.

**IFCN/EFCSN [3P]:** EFCSN-verified 2023, renewed to 25 May 2027; IFCN signatory since 2019.

**Harvest:** `ingest/harvest_demagog.py` → **380 records**.
- Selection: the 130 newest items per section, plus 60 older items per section whose slug matches popular-myth topics (szczepionki, 5G, uchodźcy, Zielony Ład, pakt migracyjny, ceny prądu, wybory, …).
- Date span 2014–2026.
- Verdicts: false 224, misleading 73, true 36, mixed 20, unverifiable 3, null 24 (explainers with no rating).

### 1.2 FakeNews.pl — Fundacja „Przeciwdziałamy Dezinformacji"

**Machine access [V]**
- Open WP REST API at `/wp-json/wp/v2/posts`, **949 posts** (`X-WP-Total`).
- Posts expose ACF fields: `teza` (claim), `autor` (claim author), `ocena` (verdict), `url` (where the claim appeared), `data` (claim date). This is the same data as the ClaimReview JSON-LD in the HTML.
- Fact-check categories: polityka (184), społeczeństwo (371), zdrowie (207), środowisko (72), technologia (36), rozrywka (19). We skip blog and badania.

**robots.txt [V]:** `Disallow:` (nothing disallowed).

**Licence [V]:** footer "© COPYRIGHT 2026 fakenews.pl"; no CC licence; the regulamin covers only donations. **What this means for us:** claim + verdict + excerpt (≤2,500 chars) + link.

**Verdict scale [V]:** Fałsz, Manipulacja, Brak kontekstu, Brak dowodów, W większości fałsz / prawda, Prawda, Nieweryfikowalne, Satyra / Żart, Scam. Non-verdict types: "Analiza", "Raport".

**IFCN [3P]:** application assessed 2021–22, current status [UNVERIFIED]. Not an EFCSN member.

**Harvest:** `ingest/harvest_fakenews_pl.py` → **500 records** (2021–2026).
- 5 API pages + tag lookups, ~15 requests in total.
- Verdicts: false 339, misleading 31, unverifiable 15, mixed 9, true 6, null 100 (analyses/reports).

### 1.3 Stowarzyszenie Pravda — pravda.org.pl

**Machine access [V]**
- Ghost CMS; `sitemap-posts.xml` lists **477 posts**.
- Article HTML has `Article` JSON-LD: headline, datePublished, and a `description` that is usually the verdict rationale. There is **no ClaimReview in the HTML**.
- Pravda enters its ClaimReviews through Google's Fact Check Markup Tool, so they appear in the Google/Data Commons ClaimReview feed (**211 reviews**, 2020–2025; see §2.2). We join them by URL.

**robots.txt [V]:** allows everything except `/ghost/`, `/members/…`, `/r/`, `/email/`.

**Licence [V]:** none stated, so all rights reserved by default. We store an excerpt (≤2,500 chars) + link.

**Verdict scale [V]:** Prawda / Fałsz / Manipulacja / Nieweryfikowalne (sometimes "Niedające się zweryfikować").

**Caveat:** about 15 % of Pravda's `claimReviewed` strings in the feed are written in English. The article text is always Polish.

**EFCSN [3P]:** verified 23 Feb 2024, renewed to Feb 2028.

**Harvest:** `ingest/harvest_pravda.py` → **269 records**: 211 with claim and verdict, plus the 60 newest 2026 articles (explainers, verdict null).

### 1.4 Konkret24 — konkret24.tvn24.pl (TVN24)

**Machine access [V]**
- No sitemap (`/sitemap.xml` and `/sitemap_index.xml` return 404; `/sitemaps/sitemap.xml` returns 403).
- The RSS feed `najwazniejsze.xml` is an empty channel.
- `?page=` pagination is disallowed by robots.
- Articles carry `NewsArticle` JSON-LD (headline, datePublished, description, author) but **no ClaimReview and no verdict labels**. Only teasers show "FAŁSZ" [3P].
- We crawl the landing pages (/, polska, polityka, swiat, zdrowie, tech, nauka; about 133 seed links) and follow related-article links with a bounded BFS.

**robots.txt [V]:** disallows GPTBot entirely; `*?page=*` and `/_e/p/playlist/*` for everyone.

**Licence [3P]:** "Korzystanie z materiałów redakcyjnych TVN… wymaga wcześniejszej zgody", plus an art. 25 ust. 1 pkt 1 lit. b reservation. **What this means for us:** title + lead + ≤700-character excerpt + link only. The verdict must come from reading the source.

**Harvest:** `ingest/harvest_konkret24.py` → **120 records** (109 from 2026).
- `verdict = null`.
- The tag `debunk-signal-in-headline` is set on 53 records whose headline or lead signals a debunk. It is only a heuristic for retrieval ranking, never shown as a verdict.

### 1.5 EUvsDisinfo — euvsdisinfo.eu (EEAS East StratCom Task Force)

**Database [V]**
- `/disinformation-cases/` reports **19,873 cases**.
- The database is officially "only available in English" and updated weekly.
- Case pages are at `/report/<slug>/`. Each has SUMMARY (the pro-Kremlin claim), RESPONSE (the disproof), outlet with archive links, date, countries discussed, and tags.
- **Case pages also exist as EUvsDisinfo's own AI translations at `/pl/report/<slug>/`** (and in 15 other languages), with the banner "Ten artykuł został przetłumaczony za pomocą AI". This is the best Polish source, if reachable.

**Machine access [V]**
- WP REST API returns 401. The listing export is a JS-only form; no CSV/JSON export or public API found.
- Sitemaps cover only articles, not cases. There is an `llms.txt`.
- The country and language filters returned 0 results for us. **Free-text + date filters work:** `?text=Poland` gives **2,145 cases**.
- robots.txt disallows `*/page/*`, `*sort=`, `*type=`, `*/?numberposts=`, `*/feed/`. So **no pagination**. We slice by `text=Poland` × monthly `date=dd.mm.yyyy - dd.mm.yyyy` windows: 2022–2026 monthly, older quarterly. We also run 30 topical first-page queries (Tusk, Duda, Warsaw, refugees, Green Deal, 5G, vaccines…).
- Some months overflow 20 results (e.g. 31 in Oct 2024), so a few cases are invisible.
- **Blocker:** after about 70 requests at a 1.5 s delay, Cloudflare started serving `cf-mitigated: challenge` (403) on `/report/` pages. It is intermittent: it cleared for a few minutes, then returned even at a 5 s delay. We did not try to get around it.

**Fallback mirror [V]:** HF dataset `NLP-UniBW/eu_vs_disinfo`.
- One 44 MB parquet, **19,202 cases** dated 2015-01-06 to 2025-07-15, with `article_language` and `countries` fields.
- **1,714 cases** are about Poland or originally in Polish.
- No licence of its own; the content is EUvsDisinfo's, which is reusable with attribution.
- Related: the `joaoaleite/euvsdisinfo` collector (Apache-2.0, CIKM 2024) [3P].

**Licence [3P]:** EEAS legal notice — "Reuse is authorised, provided the source is acknowledged" (Commission Decision 2011/833/EU). Third-party material (quoted outlets, images) is excluded.

**Harvest:** `ingest/harvest_euvsdisinfo.py` → **300 records**.
- **English**, cases about Poland, newest first: 2016–2025, 237 of them from 2024–25.
- Mapping: `source_type=incident`, `verdict=false`, `verdict_raw="Disinformation (EUvsDisinfo)"`, `claim`=SUMMARY, `text`=RESPONSE, `claim_author`=outlet(s).
- When the site is reachable, the script fetches `/pl/report/` first (language `pl`, tag `ai-translation`).
  - It stops after 3 consecutive refusals, or after `--max-site` requests (default 80).
  - It then falls back to the mirror.
- The ~100 cases from Aug 2025 to Nov 2026 seen in the listings (e.g. the Kraków shooting narratives) are **not in the corpus yet**. They need a slow, polite re-run later, e.g. `--delay 8 --max-site 60`, or a request to EUvsDisinfo for data access.

### 1.6 CheckFirst — checkfirst.network

**Access [V]:** open WP REST API (72 posts). robots.txt and `llms.txt` explicitly say "AI assistants, RAG pipelines … welcome to read, index and cite. Attribute to CheckFirst and link". Quoted propaganda in their reports is evidence, not CheckFirst's own claim.

**Relevant content:**
- **Pravda / Portal Kombat network**: the 2025 report with DFRLab; the Nov 2026 dataset of 15 M articles in 47 languages. The Polish node is `pravda-pl.com` [3P].
- **Operation Overload / Matryoshka**: 2024 and 2025 reports; it floods fact-checkers, including Polish ones.
- **Meta ads from the sanctioned SDA** (Doppelgänger).

**Datasets [3P]:**
- GitHub `CheckFirstHQ/pravda-network`: about 40 GB, no licence. Too big for us.
- `pravda-network-dissemination-data` and `Overload-June-2025-report`: MPL-2.0.
- The VIGINUM Portal-Kombat domain CSV is useful for a **source-credibility blocklist**.

**Harvest:** `ingest/harvest_checkfirst.py` → **31 investigation posts** (EN, `incident`). Events and replays are filtered out.

### 1.7 AFP Sprawdzam — sprawdzam.afp.com

**Access [V]**
- Akamai returns **403 for everything, including `/robots.txt`, `/rss.xml` and `/sitemap.xml`**.
- **Zero** AFP items in the Google ClaimReview feed: AFP does not use the Markup Tool.

**Remaining routes:**
1. **Google Fact Check Tools API** with a key: `claims:search?languageCode=pl&reviewPublisherSiteFilter=sprawdzam.afp.com`. It returns claim, rating, URL and date, not article text.
2. Ask AFP for a feed.
3. MultiClaim, which has 458 sprawdzam.afp.com fact-checks but is research-only [3P].

**Status [3P]:** AFP is IFCN-signatory and EFCSN-verified (France). Polish verdict labels [UNVERIFIED].

### 1.8 PAP FakeHunter — fakehunter.pap.pl → www.pap.pl/fact-checking

**Access [V]:** `fakehunter.pap.pl` 301-redirects to pap.pl, which serves an Imperva JS challenge to bots.

**Headers [V]:** `x-robots-tag: noarchive, noai, noimageai` and **`tdm-reservation: 1`** — an explicit TDM opt-out. robots.txt blocks AI crawlers except `/mediaroom`.

**Terms [3P]:** personal use only.

**What this means for us:** **do not harvest.** At most, link out. Since 7 May 2026, PAP, TVP and Polskie Radio run "Sprawdzam to" (pap.pl/fact-checking/sprawdzamto) [3P].

**Verdict scale [3P]:** prawda / fałsz / nieweryfikowalne.

### 1.9 OKO.press

**Access [V]:**
- The site is headless Next.js; `/wp-json/` returns 404.
- `sitemap_index.xml` has 59 sub-sitemaps, but there is no fact-check category; the closest are "przeswietlamy" and "obietnice-wyborcze".
- The Google feed has only 1 OKO ClaimReview.

**Scale [3P]:** Prawda / Prawie prawda / Półprawda / Raczej fałsz / Fałsz. Methodology at oko.press/jak-sprawdzamy.

**Terms [3P]:** regulamin §10.3 forbids copying without consent.

**What this means for us:** skip; low yield and restrictive.

### 1.10 EDMO / CEDMO

**Access [V]:** `edmo.eu` and `cedmohub.eu` both return **403** to our bot (52-byte "403 - Forbidden"), including robots.txt.

**What they offer [3P]:**
- EDMO's fact-checking repository (since Dec 2023): web search + filters only, no API or licence.
- EDMO publishes monthly fact-checking briefs.
- CEDMO (CZ/SK/PL hub) Polish partners: Demagog (fact-checking lead), NASK, SWPS. CEDMO also lists Konkret24 and AFP as daily fact-checking contributors.

**What this means for us:** CEDMO's Polish fact-check output **is Demagog's**, which we harvest directly. For the EDMO repository, request access.

### 1.11 Others checked

- **"Demaskator" / Demaskator24:** no evidence that it exists as a fact-checker [3P].
- **Wojownicy Klawiatury** (Geremek/Schuman foundations): IFCN application in Feb 2023 [3P]. Not probed. Candidate for later.
- **"Sprawdzam to"** (state media, 2026): recent, PAP-hosted, so the same restrictions apply.

---

## 2. Aggregators and datasets

### 2.1 Google Fact Check Tools API [3P]
- Endpoint: `GET https://factchecktools.googleapis.com/v1alpha1/claims:search`.
- Parameters: `query`, `languageCode=pl`, `reviewPublisherSiteFilter`, `maxAgeDays`, `pageSize`, `pageToken`.
- **Requires an API key** (free GCP project). Governed by the Google APIs ToS; quotas [UNVERIFIED].
- Google removed ClaimReview rich results from Search in mid-2025, but the Explorer and API remain.
- **Recommended as a live fallback in the backend.** At query time: search `languageCode=pl`, then cite the publisher URL. It is also the only clean route to AFP Sprawdzam claims.

### 2.2 Data Commons / Google ClaimReview feed [V]
- `datacommons.org/factcheck/download` now 301-redirects to `toolbox.google.com/factcheck`, which shows no download.
- **But the raw feed is still live:** `https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json`.
  - Size 201,424,479 B; `last-modified` 21 Nov 2026 (daily).
  - 100,668 ClaimReviews; `sdPublisher` = "Google Fact Check Tools", i.e. Markup-Tool submissions only.
- **Polish content:** pravda.org.pl 211, oko.press 1.
- Polish-language ClaimReviews on other `.pl` domains are **SEO spam** (seo-sreo.pl, synergiczni.pl). The allowlist is mandatory.
- Licence: CC BY on the old Data Commons page [3P]. The HF mirror `datacommonsorg/datacommons_factcheck` is CC BY-NC 4.0 [3P].
- Script `ingest/harvest_claimreview_feed.py` streams it with ijson (nothing big on disk) and writes `data/raw/claimreview_feed_pl.jsonl`.

### 2.3 MultiClaim (Pikuliak et al., 2023) [3P]
- v1 on Zenodo 7737983: 205,751 fact-checks and 28,092 posts. **Polish:** 6,912 fact-checks and 453 posts.
  - By source: demagog.org.pl 4,292; oko.press 1,872; sprawdzam.afp.com 458; fakenews.pl 320.
- Access is by request form with an institutional email, research-only, no redistribution.
- v2 is Zenodo 15413169 (74 GB). SemEval-2025 Task 7 used Polish as a surprise language (500 posts, 8,796 claims).
- **What this means for us:** useful only as an offline **eval set** (claim↔fact-check pairs), if the team qualifies. Not for the demo corpus, and too big for our disk.

### 2.4 Other Polish datasets [3P]
- **ZCU Demagog corpus** (corpora.kiv.zcu.cz/fact-checking): 2.8k Polish claims with reasoning; labels TRUE/FALSE/MISLEADING/UNVERIFIABLE; **CC BY-NC-SA 4.0**. A small zip and a good **eval set**.
- **POLygraph** (WASSA 2024): 11,360 URL+label items and 5,082 tweet items, from FakeHunter, Demagog and AFP. Hosting and licence [UNVERIFIED].
- **CLEF CheckThat! 2025 Task 2** (claim normalisation): Polish split 163 / 41 / 100.
- No Polish fake-news dataset of note on Hugging Face.

### 2.5 Official and other sources (for the `official_*` pipeline; probed only)
- **gov.pl:** robots `Allow: /` [V]. The footer licence is CC BY-SA 4.0 for text and CC BY-NC-ND 4.0 for media, unless stated otherwise [3P].
- **MSZ** strategic-communication and disinformation pages exist [3P]. The Ministry of Digital Affairs has the explainer "dezinformacja — co warto wiedzieć". `gov.pl/web/sluzby-specjalne/dezinformacja` returns 404 [V]. "Zrozumieć dezinformację" was not found [3P].
- **NASK:** dezinfo hub nask.pl/en/institute/for-you/dezinfo; reporting form at zglos-dezinformacje.nask.pl; "all rights reserved"; 2025 platform-response report on gov.pl [3P].
- **CERT Polska Warning List:** `https://hole.cert.pl/domains/v2/domains.txt` (2.6 MB, 200 OK [V]), also in csv/json/xml/hosts variants. **Free for any use, no attribution required** [3P]. Ideal for a **"known phishing domain" check** on links in user-submitted content.

---

## 3. Verdict normalisation (`ingest/common.py: map_verdict`)

Labels are normalised (lower-case, diacritics stripped) and the first matching rule wins:

| Normalised `verdict` | Raw labels seen |
|---|---|
| `true` | Prawda, „informację uznajemy za prawdziwą…" |
| `false` | Fałsz, Fałśz (typo), Fake news, Przerobione zdjęcie/wideo, Przeróbka, Zmanipulowane…, Scam/Oszustwo, Disinformation (EUvsDisinfo) |
| `misleading` | Manipulacja, Wprowadza w błąd, Brak kontekstu, Brakujący kontekst |
| `mixed` | Częściowa prawda, Częściowy fałsz, W większości fałsz, W większości prawda |
| `unverifiable` | Nieweryfikowalne, Niedające się zweryfikować, Brak dowodów |
| `null` | Satyra / Żart, Wyjaśniamy, Analiza, Raport, Fact-Checked, Zrealizowane, missing |

Two details:
- `verdict_raw` keeps the original label. Trailing dots are trimmed, and when a whole sentence was typed into the rating field we keep its first clause (e.g. "Fałsz. Polska nie kupiła…" becomes "Fałsz").
- **Design note:** "Przerobione zdjęcie/wideo" (doctored media) maps to `false`, not `misleading`, because the content itself is fabricated.

---

## 4. Corpus produced (run of 21 Nov 2026)

| File | Records | Type | Lang | Published range | Text policy |
|---|---|---|---|---|---|
| `demagog.jsonl` | 380 | factcheck | pl | 2014-04 → 2026-11 | ≤3,000 chars, unmodified excerpt |
| `fakenews_pl.jsonl` | 500 | factcheck | pl | 2021-09 → 2026-11 | ≤2,500 chars |
| `pravda.jsonl` | 269 | factcheck | pl | 2020-08 → 2026-11 | ≤2,500 chars |
| `konkret24.jsonl` | 120 | factcheck | pl | 2024-09 → 2026-11 | **≤700 chars** (TVN copyright) |
| `euvsdisinfo.jsonl` | 300 | incident | en | 2016-01 → 2025-07 | disproof ≤4,000 chars (reuse allowed) |
| `checkfirst.jsonl` | 31 | incident | en | 2020-09 → 2026-11 | ≤4,000 chars (RAG welcome) |
| **Total** | **1,600** | 2 types | pl 1,269 / en 331 | | |

**Commands**
- Run everything: `ingest/run_factchecks.sh` (or `ingest/run_factchecks.sh demagog pravda`).
- Validate and rebuild the manifest: `ingest/.venv/bin/python ingest/validate_corpus.py`.
- Raw pages are cached gzip'ed in `data/raw/<source>/` (≈38 MB, plus the 42 MB HF parquet), so re-runs are offline-fast and do not hit the servers again.

**Politeness:**
- Every fetch passes a robots.txt check; the matcher supports `*`/`$` wildcards.
- Per-host delay is ≥1.2 s (3–5 s for EUvsDisinfo).
- On a 403 from a host that earlier served us, the script backs off once for 60 s and then gives up.

## 5. Blockers and next steps

1. **EUvsDisinfo Cloudflare challenge.** Polish AI translations and post-July-2025 cases are missing. Re-run later with `--delay 8 --max-site 60`, or email EUvsDisinfo (they mention data access on request [3P]).
2. **AFP Sprawdzam is unreachable.** Get a Google Fact Check Tools API key and query `reviewPublisherSiteFilter=sprawdzam.afp.com`, storing only claim/rating/URL. Alternatively, contact AFP Poland.
3. **PAP / FakeHunter:** TDM reservation, so link-out only unless PAP grants permission.
4. **EDMO / CEDMO:** 403. Ask for repository access. For Poland, Demagog already covers CEDMO's Polish fact-checks.
5. **Licences:** Demagog is non-commercial with attribution and no modification. The UI must show "Źródło: demagog.org.pl" with a link and must not rewrite quoted excerpts. Paraphrase in our own words only *outside* the quoted fragment.
6. **Eval:** the ZCU Demagog corpus (CC BY-NC-SA) and, if available to the team, MultiClaim's Polish pairs make good retrieval/verdict test sets.
