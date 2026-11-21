# 03 — Official & primary sources for Prawdowid (research + harvest report)

_Status: 2026-11-21. Author: data-ingestion workstream. Every endpoint marked ✅ was called with
`curl`/Python from this machine on 2026-11-21 with UA `PrawdowidHackathonBot/0.1 (research prototype)`._

## TL;DR

* **Best machine-readable primaries (no auth, JSON):** Sejm **ELI API** (all of Dziennik Ustaw/ISAP incl. consolidated
  texts), **Sejm API** (MPs, votes, prints, interpellations), **GUS BDL** + **GUS DBW** APIs, **NBP API**,
  **Eurostat** dissemination API, **CELLAR SPARQL/REST** (EUR-Lex content incl. Polish summaries), **dane.gov.pl API**.
* **Scrape-only but stable HTML:** gov.pl (all ministries share one CMS → one parser), CERT Polska, KE w Polsce.
* **Blocked / not automatable (respected, not bypassed):** `eur-lex.europa.eu` (AWS-WAF JS challenge → used CELLAR),
  `isap.sejm.gov.pl` (`robots.txt: Disallow: /` for `*` → used ELI API), MSZ travel advisories (moved to
  `odyseusz.gov.pl`, an Angular SPA with an undocumented, credentialed API), `wybory.gov.pl` (JS app → used the PKW
  announcements in Dz.U. via ELI).
* **Harvested now: 685 official documents in 11 JSONL files across 10 domains** (table in §5). Fact cards (GUS, NBP,
  Eurostat, PKW) cite the exact API URL and the data date.
* **MCP:** no *official* MCP server exists for any of these Polish sources (dane.gov.pl, Sejm, GUS, NBP, KRS).
  Community servers exist (best: `cyanheads/eur-lex-mcp-server`, `cyanheads/eurostat-mcp-server`,
  `pkolawa/parliament-poland-mcp-server`, `numikel/law-scrapper-mcp`, WMDE's official Wikidata MCP). Recommendation:
  wrap **our own** read-only "live tools" as a small Python MCP server (§7) instead of depending on 3rd-party ones.

---

## 1. Source catalogue

| Source | Access (verified) | Auth | Rate limits | Licence / reuse | Freshness | Value for viral claims |
|---|---|---|---|---|---|---|
| **ELI API (Sejm) – acts = ISAP data** | REST JSON `api.sejm.gov.pl/eli` ✅ | none | none published, no headers; robots `Allow: /` | acts not copyrighted (art. 4 pkt 1 pr. aut.); cite ELI/ISAP | same day as Dz.U./M.P. publication; consolidated texts when the Marshal announces them | ★★★ "ustawa X wprowadza Y", "od 1 stycznia obowiązuje…", status/in force/amendments |
| **Sejm API** | REST JSON `api.sejm.gov.pl/sejm/term10/...` ✅ | none | none published | public information; cite Sejm | live (votes minutes after sitting) | ★★ "posłowie X głosowali za…", projects (prints), legislative process, interpellations |
| **isap.sejm.gov.pl** | HTML | — | **robots: `User-agent: * Disallow: /`** | — | — | human links only (we link, never crawl) |
| **dane.gov.pl** | JSON:API `api.dane.gov.pl/1.4` ✅ | none | none published | Regulamin §5 + per-dataset licence (mostly CC0 1.0) | per dataset (daily…yearly) | ★ pointer to raw datasets (UdSC, SG, ZUS 800+, KBW, Policja, MF); noisy search (thousands of developer price lists) |
| **GUS BDL** | REST JSON `bdl.stat.gov.pl/api/v1` ✅ | optional `X-ClientId` key | anon: 5/s, 100/15 min, 1000/12 h, 10 000/7 d (headers `X-Rate-Limit-*`); key: 10/s, 500, 5000, 50 000 | CC BY 4.0 (api.stat.gov.pl) | annual, regional (NUTS/gminy); last year ≈ T+5–10 months | ★★★ population, births, migration balance, unemployment, wages, crime per 1000 |
| **GUS DBW** (Dziedzinowa Baza Wiedzy) | REST JSON `api-dbw.stat.gov.pl/api` ✅ (OpenAPI at `/apidocs/pl/dbw.json`) | none | none published | CC BY 4.0 (stated in API docs footer) | monthly; **newest CPI (Oct 2026) already there** | ★★★ monthly CPI by COICOP, HICP, many domain series |
| **GUS "Wskaźniki makroekonomiczne"** XLSX | file linked from `stat.gov.pl/wskazniki-makroekonomiczne/` ✅ | none | — | GUS: reuse allowed with source (stat.gov.pl/copyright) | monthly, ~T+3–4 weeks (file of 2026-10-23 → data to Sep 2026) | ★★★ CPI + 12 COICOP groups, registered unemployment, wages, pensions |
| **NBP API** | REST JSON `api.nbp.pl/api` ✅ + XML `static.nbp.pl/dane/stopy/stopy_procentowe.xml` ✅ | none | ≤93 days per query; heavy scraping may be treated as DoS (regulamin); occasional HTTP 500 → retry | cite source + link to nbp.pl | table A each business day ~11:45–12:15; rates when RPP changes them | ★★★ "euro kosztuje…", "złoty się załamał", gold, reference rate |
| **Eurostat** | REST JSON-stat `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}` ✅ | none | none published (large extractions go async) | CC BY 4.0 | monthly/quarterly/annual | ★★★ EU comparisons: "najwyższa inflacja/najdroższy prąd/największy dług/najwięcej azylantów w UE" |
| **EUR-Lex / CELLAR** | SPARQL `publications.europa.eu/webapi/rdf/sparql` ✅, content items `publications.europa.eu/resource/cellar/{uuid}.{expr}.{manif}/DOC_1` ✅ | none | none published | Decision 2011/833/EU; summaries CC BY 4.0, metadata CC0; only OJ text authentic | same day | ★★★ EU-myths: migration pact, 2035 cars, ETS2, insect food, tethered caps, cash limit, AI Act, DSA |
| **eur-lex.europa.eu (website)** | HTML — **AWS WAF challenge (HTTP 202, empty body) for our client**; robots `Crawl-delay: 10` | — | — | — | — | link target only |
| **gov.pl (all ministries, KPRM, RCB, UdSC, MSZ)** | HTML, uniform CMS; listing `/web/{unit}/{aktualnosci|wiadomosci|komunikaty}?page=N&size=10` ✅; per-unit site map `/web/{unit}/mapa-strony` | none | robots `Allow: /` | **CC BY-SA 4.0** for text (gov.pl/web/gov/warunki-korzystania); audiovisual CC BY-NC-ND 4.0 | live; **listings keep only the current year** | ★★★ official statements, myth/debunk pages (GIS vaccines, MKiŚ "DezinfoRadar", MI CPK, MON, UdSC, RCB), RCB alerts |
| **MSZ travel advisories** ("Polak za granicą") | `gov.pl/web/dyplomacja/informacje-dla-podrozujacych` → **302 to odyseusz.gov.pl** (Angular SPA) | API behind app | — | — | — | ★★ (travel safety claims) — **blocked**, ask MSZ for a feed |
| **KE w Polsce** (poland.representation.ec.europa.eu) | HTML news listing `?page=N` ✅ | none | **aggressive 429** after a few hits → 6 s/request | CC BY 4.0 (Commission legal notice) | weekly | ★★ EU positions in Polish; **no "Euromity" section any more** (sitemap checked, `/euromity_pl` 404); many items are **machine-translated** (tagged) |
| **CERT Polska** | RSS `cert.pl/rss.xml` ✅ + guide pages; warning list `hole.cert.pl/domains/v2/domains.{txt,json,csv,xml}` ✅ | none | robots disallow only `/telefon/`, `/szukaj/` | articles © NASK (no open licence → excerpts + link); **warning list: free for any use** | RSS daily; list refreshed ~5 min | ★★★ scams/phishing ("inwestycja Orlen", fake shops, fake SMS), APT/Ghostwriter |
| **PKW** | results via **Dz.U. announcements (ELI)** ✅; wybory.gov.pl is JS; CSV zips on `{election}.pkw.gov.pl/.../data/csv/` (per sub-research) | none | — | official documents (art. 4); KBW dataset on dane.gov.pl CC0 | final results announced 1–3 days after vote | ★★★ "wybory sfałszowane", turnout, % per candidate/committee, seats |
| **BIP** | per institution (e.g. `gov.pl/web/dyplomacja/bip`), no common API | — | — | public information | varies | ★ procurement/organisation facts; low value for viral claims |
| **ZUS** | `zus.pl` robots allow all; data via dane.gov.pl (ZUS datasets: 800+, emerytury) ✅ | none | — | public information | monthly/quarterly | ★★ 800+/pension numbers (via GUS/dane.gov.pl) |
| **Wikidata / Wikipedia PL** | Wikidata SPARQL `query.wikidata.org/sparql` ✅; Wikipedia REST | none | WDQS 60 s query budget/min | Wikidata CC0; Wikipedia CC BY-SA 4.0 | community-edited | ★ entity disambiguation / background only — **never as verdict evidence** (e.g. Wikidata population of PL = 37 563 071 @2024-06-30 vs GUS BDL 37 489 087 @2024-12-31) |

## 2. Per-source notes

### 2.1 Sejm ELI API (ISAP data) — `official_eli.py`, `official_pkw.py`
* `GET https://api.sejm.gov.pl/eli/acts/{DU|MP}/{year}/{pos}` → metadata: `title, status, inForce, entryIntoForce,
  promulgation, keywords, references{Akty zmieniające, Inf. o tekście jednolitym, Akty uchylające…}, texts[]`.
* Text: `/text.html` (when `textHTML=true`, most acts ≥2012 and all consolidated texts) else `/text.pdf`
  (2025–2026 Dz.U. items are PDF-only → `pdftotext`).
* Search: `GET /eli/acts/search?title=..&type=Ustawa&publisher=DU&year=..&keyword=..&dateEffectFrom=YYYY-MM-DD&limit=..`
  ✅. Note: `inForce=1` appears to be **ignored** (returned acts with status "akt objęty tekstem jednolitym") —
  filter client-side on `status`/`inForce`.
* ISAP website forbids crawling (`robots.txt`), so the API is the only legitimate machine route. We store ISAP
  `DocDetails.xsp?id=WDU…` links for humans.
* **Usefulness:** legal claims are the #1 category of "ustawa wprowadza…" disinformation. The record we build per act
  = status + in-force date + latest consolidated text + Art. 1 scope + keyword-focused excerpts (e.g. 800+ eligibility
  of foreigners, 60-day asylum suspension, 60/65 retirement age, Art. 130 k.k. disinformation-espionage).

### 2.2 Sejm API (term 10)
✅ verified: `/sejm/term10/MP` (499 MPs), `/sejm/term10/votings/search?title=…`, `/sejm/term10/prints/{nr}`,
`/sejm/term10/processes?title=…`, `/sejm/term10/interpellations?title=…`, transcripts
`/sejm/term10/proceedings/{n}/{date}/transcripts/{nr}`. Use for "poseł/klub X głosował…" and "projekt Y jest w Sejmie"
claims (live tool, not pre-harvested — too volatile).

### 2.3 dane.gov.pl — `official_dane.py`
* `GET https://api.dane.gov.pl/1.4/datasets?q=..&sort=relevance&include=institution` ✅ (default sort is by id;
  `sort=relevance` is essential), `GET /1.4/datasets/{id}/resources` ✅, global `GET /1.4/search?q=..` ✅.
* Since 2025 the portal hosts thousands of **developer housing-price lists** that swamp search results → we filter
  publishers to public bodies (regex on institution name) and drop "ceny ofertowe".
* **No official MCP server** (MC GitHub org has 3 repos from 2017; the PulseMCP "official" listing is the 3rd-party
  Pipeworx gateway). Community: `appunite/dane-gov-pl-mcp` (PyPI `dane-gov-pl-mcp` 0.1.1, MIT, stale since 2026-01).
* Value: pointer cards ("gdzie są oficjalne dane o cudzoziemcach / 800+ / przestępczości") + resource URLs for live
  download; numbers themselves better from GUS/Eurostat.

### 2.4 GUS — `official_gus.py`
* **BDL** `GET /api/v1/data/by-variable/{varId}?unit-level=0&format=json` ✅;
  `GET /api/v1/data/by-unit/000000000000?var-id=72305&var-id=60270&year=2025&format=json` ✅;
  `GET /api/v1/variables/search?name=..` ✅; units `GET /api/v1/units/search?name=mazowieckie&level=2` ✅.
  Quota bites quickly when exploring (we hit 429 after ~100 calls/15 min) — use an `X-ClientId` key in production.
  Variable IDs used: 72305 population, 59 births, 65 deaths, 450540 births/1000, 59049 fertility, 60569 infant
  mortality, 80108 international net migration, 60270 registered unemployment (31 XII), 64428 average wage,
  398594 crimes/1000.
* **Monthly XLSX** (`wybrane_miesieczne_wskazniki_makroekonomiczne_cz_i.xlsx`): sheets `WSKAŹNIKI CEN` (COICOP 2018,
  from 2026), `WSKAŹNIKI CEN - COICOP 1999` (to 2025), `RYNEK PRACY`, `WYNAGR. I ŚWIADCZ. SPOŁ`. Codes A/B/C =
  r/r, m/m, vs December.
* **DBW** ✅ `GET https://api-dbw.stat.gov.pl/api/variable/variable-data-section?id-zmienna=305&id-przekroj=1698&id-rok=2026&id-okres=256&ile-na-stronie=5000&numer-strony=3`
  → CPI total Oct 2026: r/r **103,5**, m/m 99,6, vs Dec 103,3 (positions: COICOP "0 - OGÓŁEM" = 14916914, household
  group "Ogółem" = 6902025; presentation 2/5/8 = m/m, r/r, vs Dec; periods 247..258 = M01..M12). DBW is ~1 month
  fresher than the XLSX but needs paging (≈20k rows per month/section) — fine for a cached live tool.
* Pitfalls to surface to users: CPI (GUS) ≠ HICP (Eurostat); registered unemployment (GUS, ~5,8%) ≠ LFS/ILO
  unemployment (Eurostat, ~3,4%); enterprise-sector wage ≠ national-economy wage; COICOP 2018 break in Jan 2026.

### 2.5 NBP — `official_nbp.py`
✅ `GET https://api.nbp.pl/api/exchangerates/rates/A/EUR/?format=json` (EUR 2026-11-20: 4,4559 zł),
`/rates/A/EUR/2026-01-02/`, `/rates/A/USD/2026-11-16/2026-11-20/`, `/rates/C/EUR/` (bid/ask), `/tables/A/`,
`/cenyzlota/last/1/` (481,23 zł/g), `static.nbp.pl/dane/stopy/stopy_procentowe.xml` (reference rate 3,75% since
2026-03-05). Intermittent HTTP 500 → harvester retries with back-off.

### 2.6 Eurostat — `official_eurostat.py`
✅ JSON-stat queries; note **HICP dataset change**: `prc_hicp_manr` stops at 2025-12 (COICOP 1999); use
`prc_hicp_minr?unit=RCH_A&coicop18=TOTAL` (ECOICOP v2). Others used: `une_rt_m` (SA, PC_ACT),
`gov_10dd_edpt1` (na_item GD / B9, PC_GDP), `tec00115`, `tec00114` (GDP pc PPS), `nrg_pc_204` (household
electricity, I_TAX, EUR & PPS), `migr_asyappctza` (first-time asylum), `migr_asytpsm` (temporary protection —
newest month is partial, so the harvester picks the newest month with ≥20 EU countries).

### 2.7 EUR-Lex via CELLAR — `official_eurlex.py`
* SPARQL (one query for up to ~15 CELEX): Polish title (`cdm:expression_title` + language POL), date,
  `cdm:resource_legal_in-force`, summary work via `cdm:summary_summarizes_work` +
  `cdm:summary_legislation_eu_id_legissum`. Then a second SPARQL resolves the PL `xhtml5` manifestation item of the
  summary (or of the act) and we GET `…/DOC_1`.
* `eur-lex.europa.eu` answered our Python client with an **AWS-WAF challenge** (HTTP 202, `x-amzn-waf-action:
  challenge`). We did **not** try to get around it; CELLAR is the Publications Office's documented machine channel.
* 26/30 key acts have an official Polish summary (LEGISSUM); 4 fall back to title + recitals + Art. 1
  (2023/851 cars-2035, 2023/959 ETS2, 2023/5 cricket powder, 2022/382 temporary protection).

### 2.8 gov.pl — `official_govpl.py`
* Uniform markup: listing items `span.date` + `div.title a` + `div.intro`; article `article#main-content h2`,
  `p.event-date`, `p.intro`, `div.editor-content`. **No RSS** (`/web/{unit}/rss` 404).
* **MSZ** `gov.pl/web/dyplomacja/aktualnosci` — listing has only **2026** (32 pages, 2026-01-07…2026-11-20); 2025
  items are no longer paginated (and `/web/dyplomacja/mapa-strony` redirects to `/`). → 310 MSZ articles harvested;
  2025 coverage would need the MSZ to provide an archive/export.
* MSZ strategic communication / FIMI pages (`/web/dyplomacja/komunikacja-strategiczna`, `pelnomocnik`,
  `przyklady-negatywnych-dzialan-i-mowy-nienawisci-rosji2`, `zlosliwe-boty-…`) harvested.
* **Myth/debunk pages** were discovered from per-unit site maps (`/web/{unit}/mapa-strony`, 1–8 MB each; done once,
  list frozen in code): GIS (vaccines), MZ ("Fakty i mity"), MKiŚ ("DezinfoRadar": energy-price scams, heat pumps,
  deposit system, Nature Restoration Law), MI (CPK, airspace, drones), MON, MRiRW (food), MEN, UdSC
  (Ukrainians/Belarusians statistics, fake call-ups), Cyfryzacja, KSS ("Trolle w natarciu"), RCB ("Prawdziwe czy
  fałszywe komunikaty", Alert RCB, alarm levels) + latest 25 RCB communiqués/alerts.
* MSWiA / KPRM / Ministerstwo Rodziny have **no dedicated myth pages** for the migration pact or 800+ (searched
  site maps and web); for those topics rely on ELI acts, EUR-Lex summaries, UdSC/Eurostat numbers and fact-checkers.

### 2.9 KE w Polsce — `official_ec_pl.py`
News listing scanned (25 pages) and filtered by disinformation + hot-topic keywords (migration, Green Deal/energy,
EU funds/KPO, Ukraine/sanctions, DSA, agriculture/Mercosur, rule of law); 45 items incl. "Fake news czy prawda?
Sprawdź!" (2019 myth-buster), "Oblicza dezinformacji", "UE odporna na dezinformację", "Dezinformacja pod lupą".
Most 2025–26 items carry the banner "Tekst na tej stronie jest tłumaczeniem maszynowym" → tag
`tłumaczenie maszynowe` so the answer layer can lower confidence / prefer EN original.

### 2.10 CERT Polska — `official_cert.py`
RSS (100 items, ~92 are CVE advisories → skipped) + 9 thematic guides (fałszywe inwestycje, sklepy, konsultanci,
płatności, CAPTCHA, załączniki, szybkie przelewy, bezpieczny telefon, lista ostrzeżeń). **Live tool idea:**
download `https://hole.cert.pl/domains/v2/domains.txt` (2,6 MB, refreshed every ~5 min; JSON is 22 MB) and check
any URL a user submits — free for any use, no attribution required (must not imply endorsement).

### 2.11 PKW — `official_pkw.py`
Official result announcements from Dz.U. (via ELI): presidential 2025 (I & II round — Nawrocki 50,89% vs Trzaskowski
49,11%, turnout 71,63%), Sejm 2023 (turnout 74,38%, per-committee votes & seats), Senate 2023, referendum 2023,
EP 2024, presidential 2020 (both rounds), Sejm 2019, EP 2019. The harvester keeps the national-level passages
(eligible voters, turnout, valid votes, per candidate/committee, seats, who was elected).

## 3. Which source answers which claim type

| Claim type (example) | Primary (verdict-grade) | Secondary / context | Live tool? |
|---|---|---|---|
| **Statistics** – "inflacja w Polsce wynosi 10%", "bezrobocie rośnie", "rodzi się najmniej dzieci od wojny" | GUS DBW/XLSX (monthly), GUS BDL (annual) | Eurostat (EU comparison), NBP (inflation projection) | ✅ `gus_cpi`, `gus_bdl` |
| **EU comparisons** – "Polska ma najdroższy prąd w UE", "najwyższy dług" | Eurostat (`nrg_pc_204`, `gov_10dd_edpt1`, `prc_hicp_minr`) | GUS | ✅ `eurostat_compare` |
| **Migration numbers** – "Polska przyjęła X migrantów z paktu", "2 mln Ukraińców na 800+" | Eurostat asylum / temporary protection, UdSC statistics pages, dane.gov.pl SG/UdSC | MSWiA statements, ELI (DU/2025/1301 800+ for foreigners) | ✅ `eurostat_compare`, `dane_resource` |
| **Laws** – "ustawa X wprowadza Y", "od 2027 zakaz…" | ELI API (status, consolidated text, in-force date, amendments) | Sejm API (prints, votes), gov.pl explanations | ✅ `eli_search`, `eli_act` |
| **EU law myths** – "UE zakazuje gotówki / aut spalinowych od 2035 / każe jeść robaki / pakt zmusza do relokacji" | EUR-Lex/CELLAR text + PL summary | KE w Polsce, gov.pl | ✅ `eurlex_summary` |
| **Government statements** – "MSZ ogłosiło…", "RCB wysłało alert…" | gov.pl (MSZ, KPRM, RCB, ministries) | — | corpus + `govpl_search` (site listing) |
| **Election facts** – "wybory 2025 sfałszowane, Trzaskowski wygrał" | PKW announcements (Dz.U.), PKW CSV | SN ruling on validity (ELI/M.P.) | corpus |
| **Currency / prices** – "euro po 5 zł", "złoto tanieje" | NBP API | GUS CPI (prices of goods) | ✅ `nbp_rate` |
| **Scams / phishing** – "inwestuj w Baltic Pipe", "dopłata do paczki" | CERT Polska guides, hole.cert.pl list | KNF warnings list (not harvested) | ✅ `cert_domain_check` |
| **Vaccines / health** | GIS, MZ myth pages | ECDC/WHO (other workstream) | corpus |
| **Entities** (who is minister X, population of city Y) | GUS BDL (numbers), gov.pl (offices) | Wikidata (disambiguation only) | ✅ `wikidata_entity` (background, never verdict) |

## 4. Licences – what the answer layer must show
* gov.pl: CC BY-SA 4.0 → attribute "Źródło: gov.pl/{unit}, CC BY-SA 4.0"; derivative summaries inherit SA.
* GUS: CC BY 4.0 (BDL, DBW) / "z podaniem źródła" (stat.gov.pl). NBP: source + link to nbp.pl.
* Eurostat & KE: CC BY 4.0. EUR-Lex: Decision 2011/833/EU; summaries CC BY 4.0; only OJ is authentic → say so.
* Legal acts & PKW announcements: no copyright (art. 4 pr. aut.).
* CERT Polska articles: © NASK, no open licence → we store ≤4 000-char excerpts with link (quotation right); prefer
  linking. hole.cert.pl list: any use.
* Wikidata CC0, Wikipedia CC BY-SA 4.0.
Each JSONL record carries a short `license` note.

## 5. Harvest results (run 2026-11-21)

| File | Records | Domain(s) | Content |
|---|---:|---|---|
| `official_govpl_msz.jsonl` | 310 | gov.pl | MSZ news/communiqués 2026-01-07 … 2026-11-20 |
| `official_govpl_myths.jsonl` | 95 | gov.pl | 63 curated myth/debunk/FIMI pages (MSZ, RCB, GIS, MZ, MKiŚ, MI, MON, MRiRW, MEN, UdSC, MC, KSS) + 25 RCB alerts/communiqués + 7 UdSC news |
| `official_eli.jsonl` | 33 | isap.sejm.gov.pl | key statutes/regulations (800+, Ukraine aid + 2026 phase-out, foreigners, asylum suspension, vaccinations, CPK, energy price caps, pensions/ZUS, 13th pension, babciowe, Electoral Code, defence/conscription, civil protection, KSC, sanctions, Criminal Code art. 130/256/257, wind farms, Sunday trading, Wigilia day off, minimum wage 2026/2027, labour market, DSA implementation) |
| `official_pkw.jsonl` | 10 | isap.sejm.gov.pl | PKW official result announcements 2019–2025 |
| `official_gus.jsonl` | 72 | stat.gov.pl, bdl.stat.gov.pl | fact cards: CPI Oct 2024 – Oct 2026 (25), CPI groups Sep 2026 (13), PPI, registered unemployment (13 months), wages (7), pensions ZUS/KRUS, employment, 10 BDL annual indicators |
| `official_nbp.jsonl` | 13 | nbp.pl | 11 FX mid rates (with m/m and y/y change), gold, NBP interest rates |
| `official_eurostat.jsonl` | 13 | ec.europa.eu | HICP PL vs EU (3 months, ranking), unemployment, debt, deficit, GDP growth (2), GDP pc PPS, electricity prices EUR & PPS, asylum 2025, temporary protection |
| `official_eurlex.jsonl` | 30 | eur-lex.europa.eu | migration pact (8 acts), temporary protection, AI Act, DSA, political ads, EMFA, eIDAS 2, COVID cert, cars-2035, ETS2, CBAM, nature restoration, EUDR, EPBD, climate law, single-use plastics, novel food/cricket powder, AML cash limit, RRF/KPO, conditionality, Russia sanctions |
| `official_ec_pl.jsonl` | 45 | poland.representation.ec.europa.eu | disinformation items + hot-topic news |
| `official_dane.jsonl` | 47 | dane.gov.pl | dataset pointer cards (foreigners, SG, Ukraine, 800+, ZUS, vaccinations, KBW elections, crime, energy, budget, KPO) |
| `official_cert.jsonl` | 17 | cert.pl | 8 non-CVE analyses (Ghostwriter Gmail phishing, toll-fraud ads, energy-sector incident) + 9 scam guides |
| **Total** | **685** | **10 domains** | validated by `ingest/official_validate.py` (exact schema, ≤4 000 chars, unique ids) |

Run: `ingest/run_official.sh` (all, ~30 min) or `ingest/run_official.sh gus nbp eurostat` (fast fact cards — run
daily). Logs in `ingest/official_logs/`. Disk: 7 MB.

## 6. "Live tools" prototype design (query-time calls)

Pre-harvested fact cards go stale (FX daily, CPI monthly). For numeric/legal claims the verifier should call
read-only tools **after** claim extraction and **before** the verdict, and cite the tool URL + data date like any
document. Rules: allow-listed hosts only; GET only; 5 s timeout; response cached (FX 1 h, CPI/BDL 24 h, ELI 6 h);
tool output enters the prompt as quoted data (never instructions); if the tool fails → "nie udało się sprawdzić"
(technical failure, not a verdict).

| Tool | Request (✅ verified 2026-11-21) | Returns / how to use |
|---|---|---|
| `nbp_rate(code, date?)` | `GET https://api.nbp.pl/api/exchangerates/rates/A/{code}/{date or ''}/?format=json` → `{"code":"EUR","rates":[{"no":"226/A/NBP/2026","effectiveDate":"2026-11-20","mid":4.4559}]}`; range `…/rates/A/USD/2026-11-16/2026-11-20/` (≤93 days); bid/ask `…/rates/C/EUR/` | compare claimed rate; if date is weekend/holiday query a 10-day range and take last |
| `nbp_gold()` / `nbp_policy_rates()` | `GET https://api.nbp.pl/api/cenyzlota/last/1/?format=json` → `[{"data":"2026-11-20","cena":481.23}]`; `GET https://static.nbp.pl/dane/stopy/stopy_procentowe.xml` | |
| `gus_cpi(year, month)` | `GET https://api-dbw.stat.gov.pl/api/variable/variable-data-section?id-zmienna=305&id-przekroj=1698&id-rok=2026&id-okres=256&ile-na-stronie=5000&numer-strony={p}` → rows with `id-pozycja-2=14916914`, `id-pozycja-3=6902025`, `id-sposob-prezentacji-miara` 5 → `wartosc` 103.5 (=3,5% r/r) | fallback: monthly XLSX parse (see `official_gus.py`) |
| `gus_bdl(var_ids, years, unit='000000000000')` | `GET https://bdl.stat.gov.pl/api/v1/data/by-unit/000000000000?var-id=72305&var-id=60270&year=2024&year=2025&format=json` → `60270: 2024 5.1, 2025 5.7; 72305: 2024 37489087, 2025 37332510` | variable discovery: `GET /api/v1/variables/search?name=…`; regions: `GET /api/v1/units/search?name=mazowieckie&level=2` → `071400000000`. Use `X-ClientId` key |
| `eurostat_compare(dataset, filters)` | `GET https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?geo=PL&geo=EU27_2020&unit=RCH_A&coicop18=TOTAL&lastTimePeriod=1&format=JSON` → time `2026-10`, values EU 4.0, PL 3.7 | omit `geo` to get all countries → compute PL rank (as in `official_eurostat.py`) |
| `eli_search(title|keyword, year?, type?)` | `GET https://api.sejm.gov.pl/eli/acts/search?title=pomocy%20pa%C5%84stwa%20w%20wychowywaniu%20dzieci&type=Ustawa&limit=3`; `…/search?keyword=cudzoziemcy&year=2026&publisher=DU`; `…/search?publisher=DU&type=Ustawa&dateEffectFrom=2026-11-01` → `DU/2026/1518 (od 2026-12-03)…` | filter `status`/`inForce` client-side |
| `eli_act(eli)` | `GET https://api.sejm.gov.pl/eli/acts/DU/2016/195` → status "akt posiada tekst jednolity", 30 amending acts, latest consolidated `DU/2026/508`; text `GET …/DU/2026/508/text.pdf` or `/text.html` | grep the consolidated text for the claimed provision; quote article number |
| `sejm_votes(title)` / `sejm_print(nr)` | `GET https://api.sejm.gov.pl/sejm/term10/votings/search?title=pomocy%20obywatelom%20Ukrainy` → date, yes/no; `GET …/sejm/term10/prints/2172`; `GET …/sejm/term10/processes?title=Centralnym%20Porcie` | "kto głosował", "projekt istnieje?" |
| `eurlex_summary(celex)` | SPARQL as in `official_eurlex.py` → `GET https://publications.europa.eu/resource/cellar/{uuid}.0018.01/DOC_1` (PL xhtml) | EU-law myths |
| `dane_search(q)` | `GET https://api.dane.gov.pl/1.4/datasets?q=cudzoziemcy&sort=relevance&include=institution&per_page=10` | locate raw dataset; download resource only if small (<5 MB) |
| `cert_domain_check(url)` | `GET https://hole.cert.pl/domains/v2/domains.txt` (2,6 MB, cache 5 min) → exact/suffix match on hostname | "ta strona jest na Liście Ostrzeżeń CERT Polska" |
| `wikidata_entity(q)` (context only) | `GET https://query.wikidata.org/sparql?query=…` e.g. population of Q36 → 37 563 071 @2024-06-30 | disambiguation; never cited as verdict evidence |

Prototype skeleton (Python, ~150 LOC): one module `tools/official_live.py` with the functions above, each returning
`{"value":…, "unit":…, "as_of":…, "source_url":…, "publisher":…, "license":…}` — the same citation fields as corpus
records, so the answer composer treats tool results and documents uniformly. Router: claim classifier tags
(`stat`, `fx`, `law`, `eu_law`, `election`, `scam`) → tool list; LLM fills parameters from a constrained schema
(currency code enum, CELEX/ELI regex, BDL var-id whitelist).

## 7. MCP (Model Context Protocol) findings

Desk research 2026-11-21 (GitHub/npm/PyPI metadata; none of these are government-run):

| Source | Server | Notes |
|---|---|---|
| dane.gov.pl | `appunite/dane-gov-pl-mcp` (PyPI `dane-gov-pl-mcp` 0.1.1, MIT) | tools search_datasets, get_resources_details, get_tabular_data; last push 2026-01, ~50 dl/month. **No official MCP** from KPRM/MC/COI. |
| Sejm API | `pkolawa/parliament-poland-mcp-server` (npm, MIT, v2.1.0 2026-11-20) | ~30 tools (MPs, votings, prints, processes, transcripts, interpellations); active |
| ELI / ISAP | `numikel/law-scrapper-mcp` (Python, MIT, uvx from GitHub) | browse_acts, get_act_content, get_act_relationships, compare_acts; smaller: `matematicsolutions/mcp-isap`, `leniwyposel/sejm-mcp` |
| EUR-Lex | `cyanheads/eur-lex-mcp-server` (npm `@cyanheads/eur-lex-mcp-server` 0.21.0, Apache-2.0) | search, get_document, lookup_celex, relations, SPARQL; most mature. Alt: `Honeyfield-Org/eurlex-mcp-server` |
| Eurostat | `cyanheads/eurostat-mcp-server` (npm 0.11.4, Apache-2.0) | search_datasets, query_dataset |
| GUS BDL | `bartosz-kuc/honest-stat-gov-mcp` (MIT, 0★), `dvvbk/mcp-gus` (GPL-3.0) | immature; nothing for DBW |
| NBP / KRS / VAT | `auto-mate-pl/mcp-polska` (nbp_kurs, biala_lista_nip, krs_odpis), `pkolawa/krs-poland-mcp-server`, `emilpinski/mcp-polish-data` | tiny projects; **avoid Pipeworx packages** — they proxy via a 3rd-party gateway |
| Wikidata / Wikipedia | **official WMDE Wikidata MCP** (`https://wd-mcp.wmcloud.org/mcp/`, BSD-3); `Rudra-ravi/wikipedia-mcp` (PyPI, 310★) | background only |
| Fact-check | Google Fact Check Tools API wrappers (inactive, need key) | covered by the fact-check workstream |

**Recommendation:** do not put third-party MCP servers in the trust path (supply-chain + prompt-injection risk,
unknown maintenance). Instead expose **our own read-only MCP server** (`prawdowid-official-mcp`, Python `mcp` SDK /
FastMCP, stdio + streamable HTTP) with the tools from §6 plus `corpus_search(query, source_type='official')` over the
harvested JSONL. Benefits for the jury criteria: "architecture that allows plugging new sources", the same tools are
usable by our agent, by Claude Desktop/IDE demos, and by MSZ analysts. Guardrails: host allow-list, GET-only,
response size cap (≤50 kB), output wrapped as data with provenance fields, per-tool rate limiting & caching,
no secrets in tool args, audit log of every call (feeds the required "zapis przebiegu sprawdzenia").

## 8. Blockers, gaps, compliance notes
1. **MSZ travel advisories** (Polak za granicą) moved to `odyseusz.gov.pl` (SPA, `/api/v1/` behind app credentials). We
   did not probe the undocumented API. → Ask MSZ (challenge owner) for an export/feed of "ostrzeżenia dla
   podróżujących"; meanwhile link users to odyseusz.gov.pl.
2. **MSZ 2025 news** not reachable via pagination (gov.pl lists only the current year). → request archive export.
3. **EUR-Lex website** WAF challenge → CELLAR used (works well); do not scrape eur-lex.europa.eu.
4. **ISAP website** disallows bots → ELI API only.
5. **KE w Polsce**: 429 rate limiting (6 s/request needed) and machine-translated texts; no "Euromity" section.
6. **wybory.gov.pl** is JS; we use PKW announcements in Dz.U. (authoritative). Per-commune CSVs exist on
   `{election}.pkw.gov.pl/{election}/data/csv/…` (reported by sub-research; not downloaded — large zips).
7. **GUS BDL** anonymous quota is small (100/15 min) → register an `X-ClientId` key (free) before the demo.
8. **dane.gov.pl** search noise (developer price lists) → relevance sort + publisher filter.
9. **CERT Polska** content has no open licence → keep excerpts short, always link; the domain list is free to use.
10. **Data freshness:** GUS XLSX lags ~1 month (DBW fills the gap); Eurostat temporary-protection newest month is
    partial; NBP API has sporadic 500s (retry).
11. Old acts published only as scanned PDFs (e.g. Konstytucja 1997, `DU/1997/483`) carry OCR errors
    ("urnowy" for "umowy") — quote article numbers, and for verbatim citations link the ISAP PDF.
12. Data in this corpus reflects the live sites on 2026-11-21; re-run `run_official.sh gus nbp eurostat` daily and the
    full set weekly.
