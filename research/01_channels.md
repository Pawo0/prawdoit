# 01 — Messaging channels for Prawdowid (decision report)

*Research date: 21 Nov 2026. Scope: second channel (beyond the web UI) for the MSZ "Prawdowid" challenge at HackNation.*
*Markers: **[V]** = verified today against the primary doc or source; **[3P]** = third-party source only; **[UNVERIFIED]** = could not confirm, so test it early.*

---

## TL;DR: the decision

| Priority | Channel | Why | Effort in 24 h |
|---|---|---|---|
| **1 (must)** | **Discord bot** (discord.py, Gateway) | Nothing to approve, no public URL, free, and the jury can use it at once. The challenge's own mentoring channel is on Discord. A right-click **"Sprawdź w Prawdowidzie"** message command checks any message in place. | 1–2 h |
| **2 (showcase)** | **WhatsApp Cloud API** (Meta, direct) | Largest messenger reach in PL after Messenger: 62% of internet users 16+, 18.4 M real users. Supplies a `forwarded` / `frequently_forwarded` flag. For a government operator, service messages are free through 2027. | 2–4 h |
| **3 (always-on fallback)** | **Demo adapter**: a simulated WhatsApp chat in the web app | Sends **byte-identical Cloud API webhook JSON**, HMAC-signed, through the real webhook route, and catches outbound Graph calls in a mock. The jury can run it locally without any keys, and it doubles as the cross-channel consistency test harness. | 1–2 h |
| Roadmap (document, adapter stub only) | Messenger, SMS (SMSAPI/SerwerSMS), Instagram | Messenger has the best reach among 65+ but needs App Review before the public can use it. SMS is the only channel that reaches offline seniors, but costs money. | – |

**Recommendation in one sentence:** demo **Discord + WhatsApp** on the hosted instance, ship the **WhatsApp-format demo adapter** for the jury's local run, and present **Messenger + SMS as the production path for older users**, with costs and approvals already worked out (section 4).

**Key numbers**

- WhatsApp (PL) since 1 Oct 2026: **1,000 free service messages per month per business number**, then about **US$0.0122 per message** **[3P, Meta CSV]**. Inbound is free. **Eligible government bodies pay nothing for service messages through 31 Dec 2027** **[V]**.
- Messenger, Instagram and Discord charge **no platform fee** **[V]**.
- SMS via SMSAPI: **0.17 PLN net per segment**, plus a dedicated inbound number at **99–149 PLN net/month** **[V]**. A typical reply costs **0.17–0.34 PLN**, so **about 170–340 PLN net per 1,000 queries**.
- SerwerSMS: shared keyword number at **1 PLN/month**, **100 free SMS** on trial **[V]**.

---

## 0. What the challenge requires (from `opis_wyzwania_prawdowid.pdf`)

- "responsywny interfejs WWW oraz co najmniej jeden dodatkowy kanał komunikacji albo adapter demonstracyjny, np. SMS, WhatsApp, Messenger, Instagram, Discord lub rozwiązanie równoważne (z wyłączeniem platform niszowych oraz Telegram i WeChat)".
- "Organizator nie zapewnia kont, numerów testowych lub kluczy, dlatego w uzasadnionych przypadkach dopuszczalny jest adapter demonstracyjny. Obsługa zapytania od odebrania wiadomości do wysłania odpowiedzi musi odbywać się automatycznie."
- "Interfejs WWW i drugi kanał albo adapter demonstracyjny powinny korzystać z tej samej logiki weryfikacji" plus the **channel consistency KPI: verdict and evidence agree 100%** across channels.
- "Zespół powinien oszacować koszt 1 000 zapytań, koszt utrzymania wybranego kanału"; "Dostęp do demonstracji ma być bezpłatny po stronie usługi; ewentualne standardowe opłaty operatora, np. za SMS, muszą być jasno wskazane."
- The prototype must be runnable by the jury from team instructions, end-to-end and without manual intervention. The jury cannot receive our Meta tokens, so a **keyless demo adapter is effectively mandatory** for the jury's local run.
- The median time from input to response must be **≤ 30 s**. WhatsApp's typing indicator lasts 25 s, so the reply must land well inside that.
- Forbidden: deciding truth "na podstawie … kanału, popularności, liczby udostępnień". WhatsApp's `frequently_forwarded` flag may therefore appear only as context or analytics, **never as a verdict input**.

---

## 1. Popularity in Poland (2024–2026)

### 1.1 Headline table

| Platform | GWI Q2 2026, % of internet users 16+ using it in the past month (DataReportal *Digital 2027 Poland*, 5 Nov 2026) [V] | Gemius **Mediapanel** Q4 2025, real users, mobile **app**, ages 7–75 (PBI) [V] | **CBOS** June 2026, % of adult social-media users [V] | **NASK "Nastolatki"** (survey Oct–Nov 2024), share of teens naming it in their top-5 platforms [V] | Ad reach, Oct 2026 (DataReportal) [V] |
|---|---|---|---|---|---|
| Facebook | **83.6%** | 22.4 M | **87%** (with Messenger) | 20% | 18.1 M |
| Messenger | **75.1%** | **21.3 M** | (bundled with FB) | **77%** | n/a (NapoleonCat: 19.36 M, Oct 2026 [3P]) |
| WhatsApp | **62.1%** | **18.4 M** (WhatsApp group: 19.3 M) | not listed; the "other" platform named most often (4%) | 12% | n/a |
| YouTube | 62.3% | 19.5 M | 71% | 66% | 28.0 M |
| Instagram | 62.2% | 12.0 M | 44% | 62% | 11.2 M |
| TikTok | 54.5% | 11.7 M | 31% | 71% | 13.3 M (18+) |
| X | 28.0% | – | 15% | – | 3.23 M (−30% YoY) |
| Telegram (excluded) | 19.1% | – | – | – | – |
| Discord | **16.4%** | – | – | **28%** (boys 44% vs girls 10%) | – |
| Signal | not in GWI top 15 (<9.1%) | – | – | – | – |
| SMS | 36.8 bn domestic SMS in 2025 (38.7 bn in 2024); 53.2 M mobile subscriptions (GUS via Telepolis) [V] | | | | |

Other context [V]:
- 82% of adults use the internet regularly (CBOS 2026), and 85% of internet users chatted through a messenger in the past month.
- Internet population: 34.2 M users, 90.5% penetration, 3.59 M people offline (DataReportal).

### 1.2 Older and low-digital-skill users (the target audience)

- **Internet use by age** (CBOS 61/2026, fieldwork June 2026) [V]:
  - 55–64: **77%**
  - 65–74: **62%**
  - 75+: **37%**
  - Among people 65+, education is the strongest predictor of being online. Only 51% of people with primary education use the internet.
- **Messenger use among online seniors is high.** 80% of internet users 65+ chatted through a messenger in the past month, compared with 70% at 55–64 (CBOS 61/2026, Table 5) [V].
- **Social media among seniors** (CBOS 86/2026, N=991, June 2026) [V]:
  - Only **30% of people 65+** use social media at all, against 63% of all adults.
  - Among 65+ social-media users: **Facebook/Messenger 75%**, YouTube 59%, Instagram 17%, TikTok 17%, X 6%.
- **Meta ad audience, Oct 2026** (NapoleonCat) [3P]:
  - Messenger: 65+ make up 10.8% (about 2.1 M) and 55–64 make up 10.6% (about 2.05 M).
  - Facebook: 65+ make up 9.8% (about 2.4 M).
- **WhatsApp by age:** **I found no reliable Polish age split** (searched Mediapanel, CBOS, UKE). WhatsApp is ranked third among apps by real users. Its strength among seniors is plausible (families abroad) but **[UNVERIFIED]**.
- **The offline population (about 3.6 M, mostly 75+) can only be reached by SMS or voice.**
- **The SMS habit already exists.** Poles forward suspicious SMS to CERT Polska's **8080**: about 355k reports in 2024, and 70.8k in Jan–May 2026 [3P]. That is the same "forward it to a short number" gesture Prawdowid needs.

### 1.3 Implications

1. **Messenger is the best channel for the target audience**: about 75% of online 65+, and the in-app share flow is native (FB post → "Wyślij w Messengerze").
2. **WhatsApp is the best channel we can actually open to the public in 24 h.** Meta Messenger needs App Review, and WhatsApp does not need it for user-initiated chats.
3. **Discord** is a demo and jury convenience with youth reach (28% of teens, mostly boys), not a reach channel for seniors.
4. **SMS** is the inclusion channel for the offline and least-skilled users, and the production path for them.

---

## 2. Channels, one by one

### 2.1 WhatsApp Business Platform — Cloud API (Meta, direct)

**24 h setup steps** [V], per Meta's Get Started guide:
1. Create a Meta developer account. Create an app with the use case **"Connect with customers through WhatsApp"** and choose or create a business portfolio.
2. **API Setup → "Start using the API"**: this auto-creates a **test WhatsApp account, a test Messaging account and a test business phone number**. Test numbers have relaxed limits and need no payment method.
3. Generate the temporary token (it "expires quickly"). Add the recipient phone numbers, which are verified with an OTP sent over WhatsApp, and send the `hello_world` template. **The user must reply**, which opens the 24 h window.
4. Create a **System User** in Business Settings and generate a permanent token with `whatsapp_business_messaging`, `whatsapp_business_management` and `business_management`.
5. **Webhook** (App Dashboard → Use cases → Customize → Configuration): enter the callback URL and verify token, then subscribe to the `messages` field.
6. Optional, for public access: **register a real number**. It must not be active on any WhatsApp app (delete the account first). Verify it by SMS or voice, set a 2-step PIN and a display name, and call `/register`. New portfolios are capped at **2 registered numbers** [V]. Whether display-name review blocks messaging, and how long it takes, is **[UNVERIFIED]**. Do this first thing in the morning.

**Dev/test limits**
- On the test number, only allow-listed numbers can receive messages: **up to 5 recipients**. The cap is shown in API Setup and in third-party guides but is **not stated in the current Meta doc text** **[3P]**. The jury therefore cannot simply message the test number.
- With a **real registered number**, anyone can message us and receive replies. **Messaging limits** (250 unique users per 24 h for new portfolios) **apply only to business-initiated messages outside the customer service window** [V]. Replies to user messages are not capped by tier. Business verification only raises those business-initiated tiers [V].
- **Throughput** [V]: 80 msg/s per number by default (up to 1,000).
  - Pair rate limit: **1 message per 6 s to the same user** (burst of 45, error 131056). Send one consolidated answer, not a stream of messages.
- Without a payment method, service messages **within the 1,000/month free tier are delivered**; anything beyond is not [V]. **No card is needed for the demo.**

**Webhook requirements** [V]
- Public HTTPS with a valid certificate; **self-signed is not supported**. mTLS is optional.
- GET verification: answer `hub.mode=subscribe`, `hub.verify_token` and `hub.challenge` by returning the challenge with HTTP 200.
- POST requests carry `X-Hub-Signature-256` (HMAC-SHA256 of the raw body, keyed with the app secret).
- Batches hold up to 1,000 updates. **Retries continue for 7 days**, so deduplicate by `message.id`.
- **Latency standard: median ≤ 250 ms, <1% over 1 s.** Acknowledge immediately and process in the background.

**Inbound message types** [V]:
- `text`, `image`, `video`, `audio`, `document`, `sticker`, `location`, `contacts`, `interactive`, `button`, `reaction`, `edit`, `revoke`, `unsupported`.
- **Forwarded content** carries `context.forwarded: true` when forwarded 5 times or fewer, and `context.frequently_forwarded: true` when forwarded more than 5 times.
- Media arrives as a media ID. Fetch the URL with `GET /<MEDIA_ID>`; the URL **expires after 5 minutes**, and webhook media IDs expire after 7 days.
- Identity: every message carries a **BSUID** (`user_id` / `from_user_id`). If the user has adopted a username, `wa_id`/`from` (the phone number) may be absent. Key users on the BSUID; it is also better for privacy.

**Outbound** [V]:
- Text up to **4,096 chars**, with an optional `preview_url` link preview (only the first URL is previewed).
- **Typing indicator plus read receipt**: send `status: "read"` with `typing_indicator`. It is dismissed when we reply or **after 25 s**.

**Pricing in 2026** [V unless marked]
- Per-message pricing since 1 Jul 2025. **Inbound messages are free.**
- **Since 1 Oct 2026, service (non-template) messages are chargeable** after a **free tier of 1,000 service messages per month per business phone number**. The tier does not roll over.
  - The service rate equals the market's utility rate (per respond.io and vendors). For **Poland (+48)** that is **US$0.0122 per message**: Poland has been a standalone market since 1 Jul 2026 (utility dropped 42%), and the rate card is dated 1 Oct 2026 **[3P: formbeep, ycloud transcriptions of the Meta CSV]**.
- Utility templates sent inside the window are chargeable since 1 Oct 2026 too.
- **Free Entry Point windows** (Click-to-WhatsApp ads, up to 72 h / 7 days) are free.
- **"Service messages remain free beyond the monthly free tier only for eligible government and non-profit organizations… through December 31, 2027."** Eligibility shows in the `service_pricing_policy` field: `PAID_EXEMPT` vs `REGULAR`. **MSZ, as a government department, would very likely qualify** (Meta explicitly lists "Government departments and agencies").
- Meta can change rates only on the first day of a quarter.

**Policy: the "AI chatbot ban" (precise reading)** [V]
- **The clause** (Meta terms, effective 15 Jan 2026, for existing users): "Providers and developers of artificial intelligence or machine learning technologies, including but not limited to large language models, generative artificial intelligence platforms, general-purpose artificial intelligence assistants… ('AI Providers'), are strictly prohibited from accessing or using the WhatsApp Business Solution… when such technologies are the **primary (rather than incidental or ancillary) functionality** being made available…, as determined by Meta in its sole discretion."
- **Meta's statement:** Meta told TechCrunch the change does not affect businesses using AI to serve their own customers.
- **Prawdowid's position:** it is a purpose-specific public-information service. It verifies claims against a defined source corpus, and the LLM is a component of that service. That is the "ancillary" case, not a general assistant.
- **Mitigations:**
  - Hard-scope the bot: refuse off-topic chat with "Pomagam tylko sprawdzać doniesienia…".
  - Present it as a service of an identifiable organisation.
  - Provide the **human escalation path** the Business Messaging Policy requires for automation: in-chat agent, phone, email, web form or support form.
- **Safety net for Poland specifically:**
  - Meta's AI-Provider page lists **Poland (+48)** among the EEA markets where "AI Providers can send service messages". There was an AI-Provider surcharge from 11 Mar to 12 May 2026, and **none since 13 May 2026**.
  - The **European Commission imposed interim measures on 9 Jun 2026** ordering Meta to restore free access for rival AI assistants. Meta is appealing and the antitrust case is ongoing.
  - Even a strict reading therefore would not bar a Polish deployment today. **Watch the outcome of the case.**
- **Other policy points** [V], from the WhatsApp Business Messaging Policy (updated 23 Sep 2026):
  - "We permit the use of the WhatsApp Business Platform for government entities and **require access through a Solution Provider**." A production MSZ deployment must go through a BSP (e.g. Twilio, Infobip, Vonage, LINK Mobility); a hackathon team account is fine.
  - Political parties, politicians, campaigns, law enforcement, military and intelligence agencies are prohibited. MSZ is none of these, but **frame Prawdowid as a public-information service**, not a security operation.
  - The privacy-policy obligation applies.
  - "Using unauthorized third-party tools is prohibited." **Do not use whatsapp-web.js, Baileys or similar unofficial libraries.**

**Data location** [V]
- Meta acts as **data processor** for the Cloud API.
- Processing happens in Meta data centres. **Optional "local storage" for data at rest in `DE` ("EU (Germany)")**, set at registration with `data_localization_region`.
- Message retention is **at most 30 days**. EU→US transfers are covered by the *WhatsApp Business Data Transfer Addendum*. SOC 2 Type II and ISO 27001.

### 2.2 WhatsApp via the Twilio Sandbox (hackathon shortcut) [V]

- **Anyone can join** by sending `join <code>` to **+1 415 523 8886**, or by scanning a QR code. Sessions **expire after 72 h**.
- The whole sandbox sends **at most 1 message per 3 s**. Trial accounts get **100 free WhatsApp messages**. No custom templates; production use is not allowed.
- **Payload format:** Twilio sends form-encoded webhooks signed with `X-Twilio-Signature`, not Meta JSON, so it needs its own small adapter. The number is US-hosted and unbranded.
- **Use** it if the jury must try WhatsApp on their own phones and our real-number registration fails.

### 2.3 Messenger Platform (Facebook Page)

- **Requirements** [V]:
  - A developer account, an app with the Messenger use case, a **Facebook Page**, and Page-token permissions `pages_messaging`, `pages_manage_metadata`, `pages_show_list`, `pages_read_engagement` and `business_management`.
  - "The Messenger Platform is free to use." The user must initiate the conversation. The **standard window is 24 h**; message tags are needed outside it.
- **The access gap** [V]:
  - "Until your app has been submitted and approved for public use… through Meta's App Review, Page tokens only allow your Page to interact with… accounts that have been granted the Administrator, Developer, or Tester role."
  - Webhooks: **Standard Access only delivers events from people with a role on the app**. **Advanced Access (App Review) is needed for ordinary users**, plus **Business Verification** when people without a role use the app.
  - The overview says App Review is "not required if you only send and receive messages for your own Facebook Page". That sentence conflicts with the webhook doc, so **plan for the conservative reading [UNVERIFIED which applies to a Live-mode own-Page app]**.
  - App Review and Business Verification take days to weeks, so they are **not achievable in 24 h**.
- **Demo option:**
  - Add jury members as **Testers**: up to 50 for most apps; regular FB users are allowed. Each one must accept under *Facebook Settings → Apps and Websites* and agree to the Meta Platform Terms [V]. That is real friction; collect FB profiles from the jury in advance.
- **Webhook** [V]:
  - Same GET verification and `X-Hub-Signature-256` HMAC as WhatsApp.
  - Retries happen immediately. After **15 min** of failures you get an alert; after **1 h** the **app is unsubscribed** and you must resubscribe the Page.
- **Inbound** [V]:
  - `text`, plus attachments of type `image`, `audio`, `video`, `file`, `reel`, `ig_reel`, and per the messages reference also `post`, `ig_post` and `fallback`.
  - **A shared FB post may arrive as `post` or `fallback`, and the payload may be empty** [3P forum]. Ask the user for a screenshot if the content cannot be read.
- **Outbound:** text up to about 2,000 chars **[UNVERIFIED in current docs]**, `sender_action: typing_on`.
- **Policy** [V]: where applicable law requires it, automated experiences must disclose that they are automated (CA/DE are called out). The **EU AI Act Art. 50(1)** has required this since 2 Aug 2026 anyway (section 6).
- **Data:** Meta Platforms Ireland is the controller of its own platform data, with transfers to the US. Under the Platform Terms we are an independent controller of what we receive **[UNVERIFIED wording]**.

### 2.4 Instagram Messaging API

- Needs an **Instagram Professional account**. Instagram Login no longer requires a FB Page [V].
- App Review table [V]:
  - "My app is only for a business I own or manage": **Standard Access, no App Review**.
  - However, "Your app testers must have a role on your app… and have a role on the Instagram professional account". As with Messenger, **assume only role-holders get through until Advanced Access** [UNVERIFIED for own-account Live apps].
- First messages from non-followers land in **Requests** [V]. Shared posts arrive with a URL; on Instagram the `share` attachment type is being replaced by `ig_post` [3P].
- **Low value for the target audience**: 17% of social-media users 65+ (CBOS). **Skip it for the demo.**

### 2.5 Discord bot

**24 h setup steps** [V]:
1. Developer Portal → New Application → **Bot** → copy the token.
2. Enable **Message Content** under *Privileged Gateway Intents*. **Apps with <10,000 users can enable privileged intents with no review**; review is only required above that threshold. This replaces the old 100-server verification gate.
3. **Installation**: tick **Guild Install** (scopes `bot`, `applications.commands`) **and User Install** (`applications.commands`).
4. Create a "Prawdowid Demo" server and post the invite link plus the Discord-provided install link in the README.

**Facts and limits** [V]
- **No public HTTPS endpoint is needed.** The bot keeps an outbound WebSocket to the Gateway, so it runs from a laptop or container with no tunnel.
  - An HTTP Interactions Endpoint is optional; it uses Ed25519 signatures.
- **Message content is visible even without the intent** for DMs with the bot, messages that mention it, and **"the message a message context menu command is used on"**. The right-click **"Sprawdź w Prawdowidzie"** command therefore works even if the intent is off.
- Interactions must be acknowledged **within 3 s**: use `defer`, then follow up **within 15 min**.
- Global limit **50 requests/s**. Invalid-request limit 10,000 per 10 min per IP (Cloudflare ban).
- Message limit 2,000 chars; embeds allow 4,096 in the description.
- **Data:** Discord stores data in the **US**. Discord Netherlands BV is the EEA controller, with SCCs and EU-US DPF.

### 2.6 SMS (Polish gateways)

| | **SMSAPI.pl** [V] | **SerwerSMS.pl** [V] | **Twilio** [V] |
|---|---|---|---|
| Outbound PL | prepaid **0.17 PLN** net/segment (top-ups 49–499 PLN), down to 0.11; postpaid 0.16/0.14 → 0.08 | post-paid plans **0.19 / 0.17 / 0.15 / 0.10 PLN** with 49–299 PLN/month fee | **US$0.0457**/segment |
| Inbound (user → us) | **dedicated 9-digit number 99 PLN/month (12-month) or 149 PLN/month (open-ended)**; with MMS 149/199; short code with prefix 199/299 | **shared 9-digit number with keyword: 1 PLN activation + 1 PLN/month**; dedicated 9-digit number 99 PLN/month; dedicated MMS number 149 PLN/month | inbound **US$0.0075**; PL number availability and price **[UNVERIFIED]** |
| Free start | "Wypróbuj za darmo" (amount not stated) | **100 SMS + 14 days** | trial credit |
| Inbound delivery | HTTP POST callback (`sms_from`, `sms_to`, `sms_text`, `sms_date`, `MsgId`, `username`). **Must reply with the literal string `OK`**, otherwise it retries | forward to API URL or email, free | webhook, form-encoded |

- **Segment maths (cost driver)** [V, SMSAPI docs]:
  - GSM-7 allows 160 chars in 1 segment and 306 in 2.
  - **Any Polish diacritic switches to Unicode**: 70 chars in 1 segment, 134 in 2. The maximum is 10 parts (1,530 / 670 chars).
  - Use `normalize=1` (ą→a …) and keep replies to **≤306 chars plus a short link** to the full result page. Only link a recognisable domain, because users are trained (rightly) to distrust links in SMS.
- **User-side cost** [V, SerwerSMS]: "Nadawca płaci za wysłanie wiadomości jak za zwykły SMS/MMS, według cennika swojego operatora." Texting a **9-digit** number is usually inside the user's plan. Avoid premium short codes. **State this in the UI**, as the challenge requires.
- **Polish law** [3P, verify for production]:
  - The *Ustawa o zwalczaniu nadużyć w komunikacji elektronicznej* (Dz.U. 2023 poz. 1703; consolidated 2024 poz. 1803) establishes a UKE register of reserved sender IDs ("nadpis").
  - A **public body may send SMS only through an integrator on the UKE list** (Art. 14).
  - For MSZ: register the sender ID and choose a listed integrator.
- **Account activation / KYC** (company data, sending to non-own numbers before verification) is **[UNVERIFIED]** for both Polish gateways. Register in the first hour.
- **Latency:** typically seconds **[UNVERIFIED]**. Inbound is text only unless you have an MMS number.

### 2.7 Other options

- **RCS (RBM):** **not feasible in 2026 PL**. Play's RCS is closed and interoperates partially at best (Apr 2026); Orange is launching its own RCS from Oct 2026; iPhone RCS in PL was still not available as of May 2026 [3P]. Google RBM agent launch needs Google and carrier approval, which takes weeks. Google Messages has 12.5 M real users (Mediapanel), so revisit in 2027.
- **E-mail** as an "equivalent solution" (needs justification):
  - The user forwards a suspicious e-mail or newsletter to `sprawdz@<domain>`.
  - **Cloudflare Email Routing plus an Email Worker** can `message.reply()`: one reply per inbound email, and the sender must pass DMARC [V]. Pricing and Worker wall-time for a ~20 s check are **[UNVERIFIED]**; an async reply through a transactional mail API is safer.
  - It needs no Meta approval and the jury can test it immediately. It is a good *third* channel if time remains.
- **Signal:** no official bot API (signal-cli is unofficial), so it is not viable. **iMessage (Apple Messages for Business):** needs an MSP and Apple approval, so it is not viable in 24 h. **Telegram and WeChat:** excluded by the rules.

### 2.8 Comparison matrix

| | Reach of older users (PL) | Public access in 24 h | Jury can test without us | Public HTTPS needed | Rich input (image / forward) | Platform cost per 1,000 queries | Data location |
|---|---|---|---|---|---|---|---|
| **WhatsApp Cloud (real number)** | high (62% of internet users; age split unknown) | **likely** (no review for user-initiated chats) **[verify early]** | yes, after scanning a `wa.me` QR | yes | yes, with forward flags | **$0** (≤1,000 msgs/month), then $0.0122/msg | Meta DCs, optional DE at rest |
| WhatsApp Cloud (test number) | – | no (5 allow-listed numbers) | only if pre-registered with OTP | yes | yes | $0 | as above |
| WhatsApp via Twilio Sandbox | – | yes (join code) | yes, but unbranded and 72 h | yes | yes | trial: 100 free msgs | US |
| **Messenger** | **highest** (75% of 65+ SM users) | **no** (App Review + BV) | only as Testers (≤50) | yes | yes (post, fallback, image) | $0 | Meta (IE/US) |
| Instagram | low | no | only role-holders | yes | yes | $0 | Meta |
| **Discord** | low (16% of internet users; 28% of teens) | **yes** | **yes** (invite / Add App) | **no** | yes (attachments, message command) | $0 | US |
| **SMS** (SMSAPI/SerwerSMS) | **universal, incl. offline** | yes, after gateway KYC | **yes** (any phone) | yes | text only | **~170–340 PLN** + number fee | PL/EU |
| E-mail (CF Workers) | medium | yes | yes | no (CF) | yes (attachments) | ~0 | CF global |

---

## 3. Cost of 1,000 queries and channel upkeep

The assumptions:
- One inbound message and **one consolidated reply** per query; the typing indicator replaces an "I'm checking…" message.
- Channel costs only. LLM and retrieval are costed separately.
- Prices are net of VAT (23%).
- FX of **3.70 PLN/USD is an assumption**; check the NBP rate.

| Channel | 1,000 queries (demo month) | Same with 2 bot messages per query | 100k queries/month (production illustration) | Fixed upkeep |
|---|---|---|---|---|
| WhatsApp Cloud API | **$0** (inside 1,000 free service msgs) | 1,000 free + 1,000 × $0.0122 = **$12.20 (~45 PLN)** | 99,000 × $0.0122 ≈ **$1,208 (~4.5k PLN)/month**; **≈ $0 if MSZ qualifies for the government exemption (to end-2027)** | SIM for the number (prepaid, a few PLN/month top-ups); BSP fee in production (vendor-specific, **[UNVERIFIED]**) |
| WhatsApp via Twilio Sandbox | covered by trial units for ~100 msgs; standard rates after | – | n/a (sandbox only) | – |
| Messenger / Instagram | **0** | 0 | 0 | FB Page; one-off App Review and Business Verification |
| Discord | **0** | 0 | 0 (maybe sharding / hosting) | bot process hosting |
| SMS via SMSAPI | 1 seg: **170 PLN**; 2 seg (≤306 chars, normalised): **340 PLN**; with diacritics, ~400 chars = 6 seg ≈ 1,020 PLN | – | 2 seg × 0.08–0.10 (volume pricing) ≈ **16–20k PLN/month** | **dedicated inbound number 99–149 PLN/month** |
| SMS via SerwerSMS | 0.10–0.19 PLN/seg → **100–380 PLN** | – | – | plan fee 49–299 PLN/month; **shared keyword number 1 PLN/month** |
| SMS via Twilio | 1 in + 2 out: $7.5 + $91.4 ≈ **$99 (~365 PLN)** | – | – | PL number **[UNVERIFIED]** |
| Webhook hosting | `cloudflared` quick tunnel free; small VPS ~20–50 PLN/month **[UNVERIFIED current prices]** | | | |

**User side:** WhatsApp, Messenger and Discord cost only mobile data. SMS to a 9-digit number costs the **standard operator rate**, usually included in Polish plans; disclose this.

---

## 4. Recommendation and architecture

### 4.1 Decision and rationale

1. **Discord: guaranteed, jury-testable, zero approvals.**
   - Commands: `/sprawdz`, DMs and @mentions, plus the **message command "Sprawdź w Prawdowidzie"**.
   - It is the only channel where the jury can verify a rumour **in place**, inside an existing conversation, the way a citizen would in a family group.
2. **WhatsApp Cloud API: impact for Polish users.**
   - Try to register a **real prepaid number** in the morning so anyone can message it; print a `wa.me` QR on the demo slide.
   - If that fails, use the test number with up to 5 allow-listed phones (team plus one jury member), and/or the Twilio Sandbox.
3. **WhatsApp-format demo adapter: always works, including for the jury's local run with no keys.**
   - The web app gets a "Symulacja WhatsApp" tab. It builds the **exact Cloud API webhook JSON**, signs it with HMAC, and POSTs it to the real `/webhooks/whatsapp` route.
   - `GRAPH_BASE` points the sender at a local mock Graph endpoint that stores replies in an outbox, which the UI displays.
   - This exercises the identical parsing, dedupe, core and rendering path.
   - It is also the harness for the **channel consistency KPI**: run the same N queries through web, demo-WhatsApp and Discord-core and assert equal verdict and evidence IDs.
4. **Messenger and SMS:** implement thin adapters if time permits (Messenger works for team testers). Present them as the **production plan for seniors**:
   - Messenger: App Review plus Business Verification.
   - SMS: UKE-listed integrator, registered *nadpis*, 9-digit number or zero-rated short code agreed with operators, the way **8080** works.

### 4.2 24 h plan (channels only)

| Hour | Task |
|---|---|
| 0–1 | Create the Meta app and business portfolio, get the WA test number, and **start real-number registration**. Create the Discord app and token. Register SerwerSMS/SMSAPI only if doing SMS. |
| 1–3 | Core `Inbound` → `check()` → `Verdict`. Discord bot running. Demo adapter plus mock Graph. |
| 3–5 | WhatsApp webhook behind `cloudflared`; verification; text + image + forward flags; typing indicator. |
| 5–6 | Rate limits, dedupe, PII masking, `/usun` deletion command, AI disclosure message, escalation link. |
| later | Messenger tester flow; consistency test suite; cost logging per channel. |

### 4.3 Channel-agnostic core (the same logic everywhere)

- Each adapter does only four things: **parse → `Inbound` → `core.check()` → `render_<channel>()` → send**.
- Raw channel IDs (phone, BSUID, PSID, Discord ID) are used **only in memory to address the reply**. Only an HMAC pseudonym is persisted.
- Renderers differ only in formatting and length (WA 4,096, Messenger 2,000, Discord 2,000, SMS ≤306). **Never in content**: same verdict label, same top sources, plus a link to the full web result.

```python
# backend/channels/common.py
import hashlib, hmac, os
from dataclasses import dataclass, field

PEPPER = os.environ["USER_ID_PEPPER"].encode()          # rotate => old pseudonyms unlinkable

def pseudonymize(channel: str, raw_id: str) -> str:
    return hmac.new(PEPPER, f"{channel}:{raw_id}".encode(), hashlib.sha256).hexdigest()[:32]

@dataclass
class Inbound:
    channel: str                    # web | whatsapp | messenger | discord | sms | demo
    user_ref: str                   # pseudonym, never the phone/PSID
    text: str
    media: list[str] = field(default_factory=list)      # channel media refs, fetched lazily
    forwarded: bool = False         # context only, NEVER a verdict input (challenge rule)
    frequently_forwarded: bool = False
    msg_id: str = ""

_seen: set[str] = set()             # use Redis SET NX + TTL 7 d in prod (Meta retries 7 days)
def already_seen(msg_id: str) -> bool:
    if msg_id in _seen:
        return True
    _seen.add(msg_id)
    return False
```

### 4.4 WhatsApp Cloud API: verification plus reply (FastAPI)

```python
# backend/channels/whatsapp.py
import hashlib, hmac, os, httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from .common import Inbound, pseudonymize, already_seen
from ..core import check, render_whatsapp

router = APIRouter()
GRAPH = os.getenv("GRAPH_BASE", "https://graph.facebook.com/v27.0")   # demo adapter overrides this
APP_SECRET = os.environ["META_APP_SECRET"].encode()
VERIFY_TOKEN = os.environ["META_VERIFY_TOKEN"]
WA_TOKEN, PHONE_ID = os.environ["WA_TOKEN"], os.environ["WA_PHONE_NUMBER_ID"]

def verify_signature(body: bytes, header: str | None) -> None:
    good = "sha256=" + hmac.new(APP_SECRET, body, hashlib.sha256).hexdigest()
    if not header or not hmac.compare_digest(good, header):
        raise HTTPException(401, "bad signature")

@router.get("/webhooks/whatsapp")           # identical handshake for Messenger/Instagram
def subscribe(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403)

@router.post("/webhooks/whatsapp")
async def inbound(request: Request, bg: BackgroundTasks):
    body = await request.body()
    verify_signature(body, request.headers.get("X-Hub-Signature-256"))
    for entry in (await request.json()).get("entry", []):
        for change in entry.get("changes", []):
            for m in change["value"].get("messages", []):   # statuses[] ignored here
                bg.add_task(handle, m)
    return {"ok": True}                                      # ACK fast: median < 250 ms

async def handle(m: dict) -> None:
    if already_seen(m["id"]):
        return
    t, ctx = m["type"], m.get("context", {})
    text = m["text"]["body"] if t == "text" else m.get(t, {}).get("caption", "")
    inb = Inbound("whatsapp", pseudonymize("wa", m.get("from_user_id") or m["from"]), text,
                  media=[m[t]["id"]] if t in ("image", "video", "document") else [],
                  forwarded=ctx.get("forwarded", False),
                  frequently_forwarded=ctx.get("frequently_forwarded", False), msg_id=m["id"])
    async with httpx.AsyncClient(timeout=15, headers={"Authorization": f"Bearer {WA_TOKEN}"}) as c:
        await c.post(f"{GRAPH}/{PHONE_ID}/messages", json={          # read receipt + typing (<=25 s)
            "messaging_product": "whatsapp", "status": "read", "message_id": m["id"],
            "typing_indicator": {"type": "text"}})
        verdict = await check(inb)                                  # SAME core as the web UI
        to = {"to": m["from"]} if "from" in m else {"recipient": m["from_user_id"]}  # BSUID fallback
        await c.post(f"{GRAPH}/{PHONE_ID}/messages", json={
            "messaging_product": "whatsapp", **to, "type": "text",
            "text": {"preview_url": False, "body": render_whatsapp(verdict)[:4096]}})
```

### 4.5 Messenger: reply (it reuses `verify_signature` and the GET handshake)

```python
# backend/channels/messenger.py
PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]

@router.post("/webhooks/messenger")
async def messenger(request: Request, bg: BackgroundTasks):
    body = await request.body()
    verify_signature(body, request.headers.get("X-Hub-Signature-256"))
    data = await request.json()
    for entry in data.get("entry", []) if data.get("object") == "page" else []:
        for ev in entry.get("messaging", []):
            msg = ev.get("message")
            if msg and not msg.get("is_echo"):
                bg.add_task(handle_messenger, ev["sender"]["id"], msg)
    return {"ok": True}

async def handle_messenger(psid: str, msg: dict) -> None:
    if already_seen(msg["mid"]):
        return
    urls = [a.get("payload", {}).get("url") for a in msg.get("attachments", [])]  # image/post/fallback
    inb = Inbound("messenger", pseudonymize("fb", psid), msg.get("text", ""),
                  media=[u for u in urls if u], msg_id=msg["mid"])
    async with httpx.AsyncClient(timeout=15, params={"access_token": PAGE_TOKEN}) as c:
        url = f"{GRAPH}/me/messages"
        await c.post(url, json={"recipient": {"id": psid}, "sender_action": "typing_on"})
        verdict = await check(inb)
        await c.post(url, json={"recipient": {"id": psid}, "messaging_type": "RESPONSE",
                                "message": {"text": render_messenger(verdict)[:2000]}})
```

### 4.6 Discord with discord.py ≥ 2.4 (no webhook, no tunnel)

```python
# backend/channels/discord_bot.py
import os, discord
from discord import app_commands
from .common import Inbound, pseudonymize
from ..core import check, render_discord

intents = discord.Intents.default()
intents.message_content = True        # privileged: toggle in Dev Portal (no review < 10k users)

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync()        # global sync; first propagation can take a while

bot = Bot()
EVERYWHERE = dict(guilds=True, dms=True, private_channels=True)

async def answer(user_id: int, text: str, attachments=()) -> str:
    v = await check(Inbound("discord", pseudonymize("dc", str(user_id)), text,
                            media=[a.url for a in attachments]))
    return render_discord(v)[:2000]

@bot.tree.command(name="sprawdz", description="Sprawdź doniesienie w wiarygodnych źródłach")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(**EVERYWHERE)
async def sprawdz(inter: discord.Interaction, tresc: str):
    await inter.response.defer(thinking=True)      # ACK within 3 s; 15 min for the follow-up
    await inter.followup.send(await answer(inter.user.id, tresc))

@bot.tree.context_menu(name="Sprawdź w Prawdowidzie")   # right-click / long-press any message
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(**EVERYWHERE)
async def sprawdz_wiadomosc(inter: discord.Interaction, message: discord.Message):
    await inter.response.defer(ephemeral=True, thinking=True)
    await inter.followup.send(await answer(inter.user.id, message.content, message.attachments),
                              ephemeral=True)

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot or not (isinstance(msg.channel, discord.DMChannel) or bot.user in msg.mentions):
        return
    async with msg.channel.typing():
        reply = await answer(msg.author.id, msg.clean_content, msg.attachments)
    await msg.reply(reply)

# in FastAPI lifespan:  asyncio.create_task(bot.start(os.environ["DISCORD_TOKEN"]))
```

### 4.7 SMS via SMSAPI (only if doing SMS)

```python
# backend/channels/sms.py  (requires python-multipart)
from fastapi import Form
from fastapi.responses import PlainTextResponse

@router.post("/webhooks/smsapi/{path_secret}")    # set in SMSAPI panel -> Adresy Callback
async def smsapi_in(path_secret: str, bg: BackgroundTasks,
                    sms_from: str = Form(...), sms_text: str = Form(...)):
    if not hmac.compare_digest(path_secret, os.environ["SMS_PATH_SECRET"]):
        raise HTTPException(404)                   # no request signature documented -> secret URL + IP allowlist
    bg.add_task(handle_sms, sms_from, sms_text)
    return PlainTextResponse("OK")                 # anything else => SMSAPI retries

async def handle_sms(number: str, text: str) -> None:
    v = await check(Inbound("sms", pseudonymize("sms", number), text))
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post("https://api.smsapi.pl/sms.do",
                     headers={"Authorization": f"Bearer {os.environ['SMSAPI_TOKEN']}"},
                     data={"to": number, "message": render_sms(v, max_chars=306),
                           "normalize": "1", "format": "json"})   # normalize: ą->a => 160-char segments
```

### 4.8 Demo adapter (identical WhatsApp contract, no Meta account)

```python
# backend/channels/demo_adapter.py   (run with GRAPH_BASE=http://localhost:8000/demo/graph)
import hashlib, hmac, json, os, time, uuid, httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix="/demo")
OUTBOX: dict[str, list[dict]] = {}
SELF = os.getenv("SELF_URL", "http://localhost:8000")
SECRET = os.environ["META_APP_SECRET"].encode()      # a dummy value is fine for local runs

@router.post("/wa/send")                              # called by the "Symulacja WhatsApp" chat UI
async def simulate_user(p: dict):
    msg = {"from": p["phone"], "id": f"wamid.DEMO{uuid.uuid4().hex}",
           "timestamp": str(int(time.time())), "type": "text", "text": {"body": p["text"]}}
    if p.get("forwarded"):
        msg["context"] = {"forwarded": True}
    body = json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "DEMO", "changes": [{
        "field": "messages", "value": {"messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "48000000000", "phone_number_id": "DEMO"},
            "contacts": [{"profile": {"name": "Demo"}, "wa_id": p["phone"]}],
            "messages": [msg]}}]}]}).encode()
    sig = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(base_url=SELF) as c:     # through the REAL webhook route
        r = await c.post("/webhooks/whatsapp", content=body,
                         headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    return {"status": r.status_code, "id": msg["id"]}

@router.post("/graph/{phone_id}/messages")             # mock of graph.facebook.com
async def fake_graph(phone_id: str, req: Request):
    out = await req.json()
    if out.get("type") == "text":
        OUTBOX.setdefault(out["to"], []).append({"ts": time.time(), "body": out["text"]["body"]})
    return {"messaging_product": "whatsapp", "messages": [{"id": f"wamid.OUT{uuid.uuid4().hex}"}]}

@router.get("/wa/outbox/{phone}")                      # UI polls this (or switch to SSE)
def outbox(phone: str):
    return OUTBOX.get(phone, [])
```

The chat UI is a WhatsApp-like bubble view with a "przekazana dalej" toggle and an image upload; for images, add a `type: "image"` variant served by the mock media endpoint. **Label it clearly as "adapter demonstracyjny"**, with no Meta logos (no impersonation). A CLI variant is about 10 lines: `httpx.post(.../demo/wa/send)` and then poll the outbox.

### 4.9 Exposing webhooks during the hackathon

- `cloudflared tunnel --url http://localhost:8000` gives a free `https://<random>.trycloudflare.com` with a valid certificate and no account. **The URL changes on every restart**, which means re-entering the callback URL in the Meta dashboard (GET re-verification). Use a **named tunnel on your own domain**, or deploy the backend to a small VPS or PaaS with HTTPS, for the final demo.
- ngrok works too. A stable free domain and the browser-interstitial behaviour for webhook POSTs are **[UNVERIFIED]**.
- Discord needs no tunnel.

---

## 5. Mobile "share to check" path

### 5.1 Android: an installed PWA as a share target [V]

- The manifest `share_target` is supported in **Chrome Android 76+**, Samsung Internet and Opera Android, and on desktop Chrome/Edge 89+.
- **Not supported:** Firefox (parses the property, no effect), Android WebView, **Safari / iOS** (WebKit bug 194593).
- **The PWA must be installed** ("Dodaj do ekranu głównego"), which is an extra step for low-skill users.

```json
"share_target": {
  "action": "/share", "method": "POST", "enctype": "multipart/form-data",
  "params": { "title": "title", "text": "text", "url": "url",
              "files": [{ "name": "screenshot", "accept": ["image/*", ".png", ".jpg"] }] }
}
```

Handle `POST /share` on the server: create the check, then answer **303 → `/wynik/{id}`** (avoids resubmission on refresh, per MDN).

**Can users share a Facebook or X post from the native app to the PWA?**
- **Yes on Android:** Share → "Więcej…" / system share sheet → Prawdowid.
- **What arrives is usually just a link, often inside `text` rather than `url`**, so always regex URLs out of `text`. The exact FB link format, e.g. `facebook.com/share/p/…`, is **[UNVERIFIED]**.

**What can then legally be fetched server-side**
| Source | What we get |
|---|---|
| **X posts** | `https://publish.twitter.com/oembed?url=<post>` returns the post text **without auth**. Tested today, works [V]. |
| **Facebook / Instagram links** | Usually a login wall for anonymous fetches. Meta's oEmbed requires an app token and the "oEmbed Read" feature (App Review) **[UNVERIFIED current terms]**. **Do not spoof crawler user-agents**: the challenge forbids "obchodzenie zabezpieczeń serwisów". |
| **TikTok / YouTube** | Public oEmbed gives title/caption only **[UNVERIFIED for TikTok]**. |

UX consequence: the share flow should **ask for a screenshot** whenever URL content cannot be read ("Nie widzę treści posta — dołącz zrzut ekranu"). Screenshot sharing via `files` works on Android.

### 5.2 iOS

- **No Web Share Target**: an iOS PWA cannot appear in the share sheet [V].
- **iOS Shortcuts workaround** [V, Apple Shortcuts guide]:
  1. Build a shortcut with **"Show in Share Sheet"** and accepted types URLs, Text and Images.
  2. Action **Get Contents of URL**: `POST https://…/api/check` with a JSON or form body. Known quirk: nested JSON is awkward, so send a flat form or a text variable.
  3. **Open URLs** on the returned `/wynik/{id}`, or **Show Result**.
  4. Distribute it as an **iCloud link**. On iOS 15+ the user taps "Add Shortcut". Whether the "Allow Untrusted Shortcuts" toggle is still needed is disputed **[partially verified]**. The first run asks permission to connect to our domain.
- **Too fiddly for the target audience.** Offer it as a power-user option.
- **The realistic path for iPhone seniors is the messaging channel:**
  - FB app → "Wyślij w Messengerze" to the Prawdowid Page; Messenger needs App Review for the public.
  - Or share or forward into the **WhatsApp chat with Prawdowid**, which is already in every share sheet.
  - **This is the strongest argument for the messaging channel.**
- Universal fallback on both platforms: a big **"Wklej"** (paste) button in the web UI using the Clipboard API; iOS shows its paste prompt.

---

## 6. Risks and mitigations

| Risk | Detail | Mitigation |
|---|---|---|
| **Cost abuse ("denial of wallet")** | Each query triggers paid LLM calls; WA beyond 1,000 msgs/month and every SMS cost money | Per-pseudonym quotas (e.g. 20/day), a global daily budget breaker, a cache of identical claims (also helps consistency), and no replies to non-text spam bursts |
| **SMS pumping / toll fraud** | Bots generating inbound traffic to trigger paid replies | Reply only to PL +48 mobile ranges, cap per number, no outbound to premium/international ranges, alert on spikes |
| **Platform quality and bans** | WA quality rating drops if users block or report; pair limit 1 msg/6 s; Messenger unsubscribes the app after 1 h of webhook failures | One concise reply, clear opt-out ("STOP"/"USUŃ"), health checks, fast ACK |
| **Prompt injection via forwarded content** | Forwarded chain letters contain instructions | Treat all user and fetched content as data; separate system prompt; output schema validation (covered in the security research) |
| **Impersonation** | Fake "Prawdowid/MSZ" accounts | Production: Meta Verified / Official Business Account, a verified Discord app, a UKE-registered SMS *nadpis*. Demo: label as prototype; no gov.pl/MSZ branding in the hackathon build |
| **Personal data (RODO)** | Phone numbers, BSUIDs, PSIDs and Discord IDs are personal data. Message content may reveal **political opinions or health (Art. 9 special categories)** | **Minimise:** persist only the HMAC pseudonym and the extracted claim, never raw numbers. **Mask** PESEL, phone, e-mail and IBAN before any LLM call (a challenge requirement). **TTL** of 30 days for the demo. **`/usun` / "USUŃ"** deletes the session (a challenge requirement). Publish a privacy notice (klauzula informacyjna, Art. 13). Production: MSZ needs a legal basis (Art. 6(1)(e) public task; Art. 9(2)(g) needs a statutory basis) **[legal review]** and a DPIA |
| **Processing location** | WhatsApp: Meta as processor, ≤30-day retention, optional DE at-rest storage. Messenger/IG: Meta IE/US. Discord: **US** (SCCs + DPF). Twilio: US. SMSAPI/SerwerSMS: PL | Document it per channel on the "Zależności zewnętrzne" page. Prefer EU options for production: WA local storage `DE`, a Polish SMS integrator |
| **Meta policy volatility** | Prices change quarterly (service messages became chargeable 1 Oct 2026); the AI terms are "sole discretion"; the EU antitrust case is ongoing | Thin adapters; the core does not depend on channel features; budget for the paid case; apply for the government exemption (`PAID_EXEMPT`); BSP for production |
| **AI Act transparency** | **Art. 50(1) applies from 2 Aug 2026** and was not delayed by the Digital Omnibus (Reg. (EU) 2026/1744) [3P law-firm analyses] | First message in each new conversation and after inactivity: "Jestem automatycznym asystentem (SI) … nie zastępuję …" plus a human contact link (this also satisfies the WA escalation rule) |
| **Verdict contamination by channel signals** | `frequently_forwarded` and share counts are tempting signals | Log them for the admin dashboard (an alert on viral unanswered rumours) but **exclude them from the verdict**; the challenge forbids it |
| **Setup failure during the hackathon** | Real WA number registration or a new Meta business account gets flagged or delayed; gateway KYC delays | Start these in hour 0; keep the test number, Twilio Sandbox and the demo adapter as fallbacks; Discord has no approval dependency |
| **Secrets** | WA system-user token, app secret, Discord token | Environment variables only, never in the repo; the jury's local run uses the demo adapter with dummy secrets |
| **Minors** | Discord has many teens (NASK: 28%) | Age-appropriate tone; no profiling; same minimisation rules |

---

## 7. Open items / not verified (test these early)

1. Whether an **unverified** business portfolio can register a real number and reply to arbitrary users immediately, and the timing and blocking effect of **display-name review**.
2. **The 5-recipient cap** on the WA test number (dashboard UI; not in the current doc text).
3. Whether a **Live-mode Messenger or Instagram app for your own Page** receives webhooks from non-role users without Advanced Access (the docs conflict).
4. **Polish WhatsApp service rate** ($0.0122): confirm in Meta's USD rate-card CSV.
5. **SMS gateway KYC** (SMSAPI/SerwerSMS) for a private or student account, and the exact sender used for replies to a dedicated number.
6. Messenger text limit (2,000 chars) and current Send API rate limits; the old rate-limiting doc URL returns 404.
7. Facebook share-link format from the Android app, and whether any non-authenticated metadata is legitimately available.
8. Twilio Polish number availability and price; BSP fees for a production WA deployment.

---

## 8. Sources

**Challenge**
- `research/opis_wyzwania_prawdowid.pdf` (local)

**Popularity**
- DataReportal, *Digital 2027: Poland* (5 Nov 2026; GWI Q2 2026; ad reach Oct 2026) — https://datareportal.com/reports/digital-2027-poland
- DataReportal, *Digital 2026: Poland* (Nov 2025) — https://datareportal.com/reports/digital-2026-poland
- PBI / Gemius Mediapanel, *Polski internet Q4 2025* — https://pbi.org.pl/wp-content/uploads/2026/01/PBI_RAPORT_Polski-internet-Q4-2025.pdf
- CBOS Komunikat 61/2026, *Korzystanie z internetu w 2026 roku* — https://www.cbos.pl/PL/publikacje/raporty/open_file.php?id=7219
- CBOS Komunikat 86/2026, *Jak korzystamy z mediów społecznościowych?* — https://cbos.pl/PL/publikacje/raporty/open_file.php?id=7252
- CBOS Komunikat 60/2025, *Korzystanie z internetu w 2025 roku* — https://cbos.pl/PL/publikacje/raporty/open_file.php?id=7045
- NASK-PIB, *Nastolatki. Raport badawczy* (survey Oct–Nov 2024) — https://www.nask.pl/media/2026/06/Nastolatki_RAPORT_BADAWCZY.pdf
- NapoleonCat, Messenger users in Poland — https://napoleoncat.com/stats/messenger-users-in-poland/
- NapoleonCat, Facebook users in Poland — https://napoleoncat.com/stats/facebook-users-in-poland/
- Telepolis (GUS 2025 telecom data) — https://www.telepolis.pl/wiadomosci/wiecej-danych-mniej-sms-ow-telekomunikacja-w-polsce-w-2025-gus
- Telepolis on 8080 — https://www.telepolis.pl/tech/bezpieczenstwo/polacy-przeslali-300-tys-sms-ow-na-numer-8080
- RCS status: https://www.telepolis.pl/wiadomosci/ministerstwo-cyfryzacji-wiadomosci-rcs-w-sieci-play-kwiecien-2026 and https://www.telepolis.pl/wiadomosci/orange-wiadomosci-rcs-pazdziernik-2026

**WhatsApp** (Meta developer documentation)
- Pricing — https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
- AI Providers pricing — https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers
- Get started — https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started
- About the platform (test resources, pair rate limits) — https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform
- Messaging limits — https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits
- Throughput (webhook latency standard) — https://developers.facebook.com/documentation/business-messaging/whatsapp/throughput
- Create a webhook endpoint — https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint
- Text message webhook (forwarded flags, BSUID) — https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/text
- Media — https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media
- Typing indicators — https://developers.facebook.com/documentation/business-messaging/whatsapp/typing-indicators
- Text messages — https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/text-messages
- Phone numbers — https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/phone-numbers
- Registration (local storage regions) — https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/registration
- Data privacy & security — https://developers.facebook.com/documentation/business-messaging/whatsapp/data-privacy-and-security
- Local storage — https://developers.facebook.com/documentation/business-messaging/whatsapp/local-storage

**WhatsApp policy, rates and the EU case**
- WhatsApp Business Messaging Policy (updated 23 Sep 2026) — https://whatsappbusiness.com/policy/
- TechCrunch, AI terms clause text (18 Oct 2025) — https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/
- Engadget, EU interim measures (10 Jun 2026) — https://www.engadget.com/2191213/eu-orders-meta-to-stop-blocking-rival-ai-chatbots
- respond.io, Oct 2026 pricing explainer — https://respond.io/blog/whatsapp-pricing-change-2026
- formbeep, Poland rates [3P] — https://formbeep.com/whatsapp-api-pricing/
- ycloud, Poland rates [3P] — https://www.ycloud.com/blog/whatsapp-api-message-pricing-update-effective-july-1-2026
- Twilio WhatsApp Sandbox — https://www.twilio.com/docs/whatsapp/sandbox

**Messenger and Instagram**
- Messenger overview — https://developers.facebook.com/documentation/business-messaging/messenger-platform/overview
- Messenger quick start — https://developers.facebook.com/documentation/business-messaging/messenger-platform/getting-started/quick-start
- Messenger webhooks — https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks
- Messenger send messages — https://developers.facebook.com/documentation/business-messaging/messenger-platform/send-messages
- Messenger messages webhook reference — https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks/webhook-events/messages
- Meta app roles — https://developers.facebook.com/documentation/development/build-and-test/app-roles
- Instagram messaging API — https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/messaging-api
- Instagram App Review — https://developers.facebook.com/documentation/instagram-platform/app-review

**Discord** (docs source: https://github.com/discord/discord-api-docs)
- Gateway and privileged intents — https://discord.com/developers/docs/events/gateway
- Rate limits — https://discord.com/developers/docs/topics/rate-limits
- Receiving and responding to interactions — https://discord.com/developers/docs/interactions/receiving-and-responding
- Application commands (message commands) — https://discord.com/developers/docs/interactions/application-commands
- User-installable apps tutorial — https://discord.com/developers/docs/tutorials/developing-a-user-installable-app
- Privacy policy — https://discord.com/privacy

**SMS**
- SMSAPI pricing — https://www.smsapi.pl/cennik
- SMSAPI docs (segments, `normalize`, inbound callback) — https://www.smsapi.pl/docs
- SerwerSMS pricing — https://www.serwersms.pl/cennik
- SerwerSMS receiving SMS/MMS — https://serwersms.pl/uslugi/odbior-sms-i-mms
- Twilio SMS pricing for Poland — https://www.twilio.com/en-us/sms/pricing/pl
- Act on combating abuse in electronic communication (consolidated) — https://eli.gov.pl/eli/DU/2024/1803/ogl/pol/pdf

**Mobile share path**
- MDN, `share_target` — https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/share_target
- MDN browser-compat-data — https://github.com/mdn/browser-compat-data/blob/main/manifests/webapp/share_target.json
- Apple Shortcuts, request your first API — https://support.apple.com/guide/shortcuts/apd58d46713f/ios
- X oEmbed endpoint (tested) — https://publish.twitter.com/oembed

**E-mail and EU law**
- Cloudflare Email Workers reply — https://developers.cloudflare.com/email-routing/email-workers/reply-email-workers/
- EU AI Act Art. 50 timing: Goodwin — https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force
- EU AI Act Art. 50 timing: Morgan Lewis — https://www.morganlewis.com/blogs/sourcingatmorganlewis/2026/08/eu-ai-acts-transparency-rules-what-went-into-effect-on-2-august
