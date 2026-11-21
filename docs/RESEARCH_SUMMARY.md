# Prawdowid — research summary (decision-ready)

Full reports: `research/01_channels.md`, `02_factcheck_sources.md`, `03_official_sources.md`, `04_methodology.md`,
`05_oss_models_prior_art.md`. Claims marked [unverified] in those reports were not confirmed against primary docs.

## 1. Channels (what Polish citizens use, what is easy to build)
- Reach: WhatsApp ≈ 62% of Polish internet users (GWI Q2 2026), ~18.4 M real users (Mediapanel). Messenger has the best
  reach among seniors (≈75% of social-media users 65+, CBOS 2026). SMS is the only channel for offline 75+ users.
- **Allowed by the brief:** SMS, WhatsApp Business Platform, Messenger, Instagram, Discord, or another justified channel.
  Telegram, WeChat and niche platforms are excluded.
- **Recommendation:**
  1. **Discord bot** for the demo: no business verification, free, no public URL needed, the jury can test it
     immediately (`bots/discord_bot.py`).
  2. **WhatsApp Cloud API** as the showcase: register a real number in hour 0. Fallbacks are the test number
     (≤5 allow-listed recipients) or a demo adapter with identical webhook JSON (`/czat`).
  3. **Messenger + SMS** are the production path for seniors. Messenger needs App Review.
- **Policy:** Meta's January 2026 WhatsApp rule targets general-purpose AI assistants. A purpose-built fact-checker
  that stays strictly on topic should be fine. Government bodies onboard through a reseller (BSP), and bots must offer a
  human escalation path. EU AI Act Art. 50 requires an "automated system" notice; it is in the bot replies.
- **Costs:** WhatsApp gives 1,000 free service messages per month per number, then about $0.0122 per message (PL)
  [3rd-party copy of Meta's rate card]. SMS costs about 170–340 PLN per 1,000 replies plus 99–149 PLN/month for an
  inbound number. Discord, Messenger and web are free.
- **Phones without an extension:** the PWA Web Share Target (Android: Share → Prawdowid) is implemented. iOS needs a
  Shortcut. Facebook links usually hit a login wall, so the bot asks for a screenshot or pasted text instead.

## 2. Browser extension (real-time, on-screen content)
- **Feasible and prototyped.** An MV3 content script scans *visible* posts and headlines via IntersectionObserver.
  - Site adapters: Facebook `div[role=article]`; X `article[data-testid=tweet]`; generic headlines and paragraphs for
    onet / o2 / wp / interia / tvrepublika / wpolityce / gazeta / tvn24 / rmf24 and others.
  - Only the text is sent (no URL, cookies or IDs), in batches, to `/api/quick`.
  - High risk: compact click-to-reveal overlay. Medium risk: badge with a percentage. Below that, nothing.
  - Floating bottom-right button: uBlock-style element picker or a check of selected text, giving a result sheet in
    ~2 s with a link to the full analysis page on the website.
- **"Probability of fake" is defined honestly** as the probability that the content *repeats a claim already rated
  false or misleading* by an IFCN/EFCSN fact-checker. It combines calibrated similarity with NLI, which checks that the
  post asserts the claim rather than denies it. This is the only defensible real-time signal. The brief forbids
  verdicts based on domain, author or popularity, so we **never flag outlets** (e.g. tvrepublika.pl) as such, and a
  post that debunks a myth is not flagged.
- **Mobile:** Chrome for Android has no extensions. The same WebExtension runs on **Firefox for Android** (publish on
  AMO as Android-compatible) and on Chromium forks such as Vivaldi (and Edge Android, after Microsoft's review).
  iOS Safari needs an App Store wrapper. For native apps (FB/X), use the share-to-PWA path and the chat bot.
- Prior art: InVID-WeVerify (AFP) and Meedan Check (open-source WhatsApp tipline). B.S. Detector's domain blacklist
  was widely criticised, which supports our content-level approach.

## 3. Sources and how verdicts are grounded
- **Corpus** (all JSONL, one schema, published and retrieved timestamps, licence per record; `docs/SOURCES.md`):
  - Size: 2,285 documents, 16 domains, 48 publishers.
  - Fact-checkers: Demagog 380 (ClaimReview), FakeNews.pl 500, Stowarzyszenie Pravda 269 (EFCSN), Konkret24 120,
    EUvsDisinfo 300, CheckFirst 31.
  - Official: MSZ 310, gov.pl myth/FIMI pages and RCB 95, GUS 72 fact cards (CPI per month, unemployment, BDL),
    dane.gov.pl 47, KE w Polsce 45, ISAP/ELI acts 33, EUR-Lex 30, CERT 17, NBP 13, Eurostat 13, PKW 10.
- **Not harvested (respecting the sites' terms):**
  - AFP Sprawdzam: 403. The legitimate route is the Google Fact Check Tools API with a key.
  - PAP FakeHunter: explicit text-and-data-mining (TDM) opt-out.
  - EDMO/CEDMO: 403.
  - ISAP: robots.txt disallows bots, so we use the ELI API instead.
  - eur-lex.europa.eu: bot challenge, so we use CELLAR instead.
- **Verified live endpoints, no key needed:**
  - `api.sejm.gov.pl/eli/acts/...`
  - GUS BDL `bdl.stat.gov.pl/api/v1` (100 requests per 15 min anonymous) and GUS DBW API (CC BY 4.0)
  - `api.nbp.pl`, Eurostat `prc_hicp_minr`, EUR-Lex CELLAR SPARQL, `api.dane.gov.pl/1.4`
- **MCP:** there is no official MCP server for dane.gov.pl, Sejm, GUS, NBP or KRS. Community servers exist:
  `cyanheads/eur-lex-mcp-server`, `cyanheads/eurostat-mcp-server`, `pkolawa/parliament-poland-mcp-server`,
  `appunite/dane-gov-pl-mcp`. Recommendation: our own read-only MCP server wrapping the verified endpoints (next
  step), so analysts can query sources from any MCP client.
- **Engine (local, CPU, no API keys):**
  - Hybrid BM25 plus Polish dense retrieval (`sdadas/mmlw-retrieval-e5-small`).
  - Previously-fact-checked-claim matching.
  - NLI stance (`mDeBERTa-v3 XNLI`) in the user→claim direction.
  - Deterministic checks for official fact cards: numbers for the same period, act entry-into-force and adoption
    dates, currency and measure compatibility.
  - Ordered rules R1–R6, verbatim quote gate, reason codes for abstention.

## 4. Organisers' methodology
- **SPRAWDŹ is real:** it is NASK's 7-step checklist from the campaign „Sprawdź, zanim udostępnisz” (Nov 2023, with
  the Ministry of Digital Affairs and UK GCSI). The letters are Sensacyjność, Prowokowanie, Racjonalność, Autor,
  Wadliwy kontekst, Dyskredytacja, Źródła.
  - Current NASK version (2025): **SPRAWDZAM** (nask.pl/dezinfo).
  - The old campaign domain sprawdzam.info has lapsed, so don't link it.
  - We show SPRAWDŹ as an educational "prebunking" panel that **never affects the verdict**.
- **IFCN, EFCSN, EDMO and NASK** translate into these features: a public methodology page, a source catalogue with
  licences, a corrections channel ("Zgłoś błąd"), non-partisan rules, a human-in-the-loop queue, privacy (RODO),
  accessibility, neutral wording (no "fake news" or "kłamstwo" for a user's item) and no actor attribution.
- **Research on warning labels:**
  - Specific, claim-level labels work and rarely backfire.
  - Generic warnings reduce trust in true news.
  - Interstitials (click-through) change behaviour more than passive labels.
  - Our design therefore uses an overlay only for content matched to a fact-check, always with "Pokaż mimo to".

## 5. Website and response time
- Website pages: check, result with evidence cards (verbatim fragment, publisher, date, link, licence), "Dlaczego
  taki wynik?" checklist, what could not be established and what would settle it, SPRAWDŹ panel, error report,
  audit drawer, methodology, sources, moderator panel (clustered cases, metrics, security events, CSV/JSON export),
  demo chat.
- **Speed:** full analysis takes a median of ~0.5 s (p95 ~2 s) on a loaded 4-core laptop CPU. From the extension, the
  "Dlaczego?" button opens the analysis page, which renders in ~1–2 s.

## 6. Evaluation (honest numbers)
- Dev set (38 cases, written by us while building): all mandatory metrics pass. Because the engine was tuned on it,
  this number is optimistic.
- **Blind held-out set** (57 cases, written by an independent agent from the corpus without seeing the engine): see
  `eval/results_heldout/results.md`. The first blind run gave macro-F1 0.774 and injection resistance 0.6; the latest
  numbers are in that file. Each fix was a general rule (e.g. statistical definitions, injection forms, greetings),
  not a per-case patch, but the held-out set is no longer fully blind after this round.
