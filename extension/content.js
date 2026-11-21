// Prawdowid — content script.
// 1) Real-time: scans what is VISIBLE on screen (IntersectionObserver) on social media & news portals, sends only the
//    text of each post/headline/paragraph to the Prawdowid server, and marks content that matches a claim already
//    rated false/misleading by fact-checkers: a click-to-reveal overlay (high) or a badge with probability (medium).
// 2) On demand: floating button (bottom-right) → "Wybierz fragment" element picker (like uBlock) → full analysis.
// Never judges by domain/author/popularity — only by content matched to verified fact-checks (challenge rule).
(() => {
  if (window.__prawdowid) return;
  window.__prawdowid = true;
  const api = globalThis.browser ?? globalThis.chrome;
  // Font faces declared only inside a shadow stylesheet are ignored by some browsers.
  new FontFace("Geist Pixel", `url("${api.runtime.getURL("fonts/GeistPixel-Square.woff2")}")`).load()
    .then(font => document.fonts.add(font)).catch(() => {});
  const send = msg => globalThis.browser ? browser.runtime.sendMessage(msg) : new Promise(res => chrome.runtime.sendMessage(msg, res));
  const host = location.hostname.replace(/^www\./, "");
  const isMobile = matchMedia("(pointer: coarse)").matches;
  let S = {autoScan: true, mockMode: false, mode: "zaslon", disabledSites: [], noticeSeen: false, apiBase: ""};

  // ------------------------------------------------------------------ site adapters
  const txt = el => (el?.innerText || "").replace(/\s+/g, " ").trim();
  const ADAPTERS = [
    { name: "facebook", test: h => /(^|\.)facebook\.com$/.test(h),
      items: root => [...root.querySelectorAll('div[role="article"]')].map(a => {
        const msg = a.querySelector('[data-ad-preview="message"],[data-ad-comet-preview="message"],[data-ad-rendering-role="story_message"]');
        const t = msg ? txt(msg) : [...a.querySelectorAll('div[dir="auto"]')].filter(d => !d.closest('[role="article"]') || d.closest('[role="article"]') === a).map(txt).join(" ");
        return {target: a, text: t};
      }) },
    { name: "x", test: h => /(^|\.)(x|twitter)\.com$/.test(h),
      items: root => [...root.querySelectorAll('article[data-testid="tweet"]')].map(a => ({target: a, text: txt(a.querySelector('[data-testid="tweetText"]'))})) },
    { name: "instagram", test: h => /(^|\.)instagram\.com$/.test(h),
      items: root => [...root.querySelectorAll("article")].map(a => ({target: a, text: txt(a.querySelector("h1, ul li span"))})) },
    { name: "generic-news", test: () => true,
      items: root => {
        const out = [];
        // article body paragraphs + headline/lead
        const body = root.querySelector('[itemprop="articleBody"], article, .article-body, .article__body, .entry-content, main') || root;
        const h1 = root.querySelector("h1");
        if (h1) { const lead = root.querySelector('[class*="lead"], [class*="Lead"], article p'); out.push({target: h1.parentElement || h1, text: txt(h1) + (lead ? ". " + txt(lead) : "")}); }
        body.querySelectorAll("p, blockquote").forEach(p => { const t = txt(p); if (t.length >= 60 && t.length < 1500) out.push({target: p, text: t}); });
        // teaser headlines on portal home pages
        const seenT = new Set();
        root.querySelectorAll("h2, h3, h4, a[class*='title' i], [class*='title' i] > a, [class*='headline' i]").forEach(e => {
          if (e.closest("nav, footer, [role='navigation'], [aria-hidden='true']")) return;
          const t = txt(e); if (t.length < 25 || t.length > 240 || seenT.has(t)) return;
          seenT.add(t);
          out.push({target: e.closest("article, li") || e.closest("a") || e, text: t});
        });
        return out;
      } },
  ];
  // local demo pages mimic several site structures at once
  const isDemo = /^(localhost|127\.0\.0\.1)$/.test(host);
  const adapter = isDemo ? {name: "demo", items: root => ADAPTERS.slice(0, 2).flatMap(a => a.items(root))} : ADAPTERS.find(a => a.test(host));

  // ------------------------------------------------------------------ UI (shadow DOM, isolated from page CSS)
  const AUTO_SCAN_HOSTS = ["bankier.pl", "businessinsider.com.pl", "dorzeczy.pl", "dziennik.pl", "facebook.com", "fakt.pl", "gazeta.pl", "instagram.com", "interia.pl", "money.pl", "natemat.pl", "nczas.info", "niezalezna.pl", "o2.pl", "oko.press", "onet.pl", "pap.pl", "pch24.pl", "polsatnews.pl", "pudelek.pl", "radiozet.pl", "rmf24.pl", "rp.pl", "se.pl", "tvn24.pl", "tvp.info", "tvrepublika.pl", "twitter.com", "wp.pl", "wpolityce.pl", "wprost.pl", "wyborcza.pl", "wykop.pl", "x.com"];
  const supportsAutoScan = isDemo || AUTO_SCAN_HOSTS.some(d => host === d || host.endsWith("." + d));

  const CSS = `
  @font-face{font-family:"Geist Pixel";src:url("${api.runtime.getURL("fonts/GeistPixel-Square.woff2")}") format("woff2");font-display:swap;}
  :host{all:initial}
  *{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  button{font:650 15px/1.4 system-ui,sans-serif;min-height:44px;border:1.5px solid #191919;border-radius:0;padding:9px 12px;cursor:pointer;background:#f4f3eb;color:#191919}
  button:hover{background:#e3e7d5}button.p{background:#443cf2;color:#fff;border-color:#443cf2}button.p:hover{background:#3027cf}
  :focus-visible{outline:3px solid #443cf2;outline-offset:3px}
  .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  .ov{position:absolute;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:8px;overflow:auto;background:#eae9e2;border:1px solid #191919;
    background-image:radial-gradient(#c4c3ba .6px,transparent .8px);background-size:4px 4px}
  .card{background:#f4f3eb;border:2px solid #191919;border-radius:0;padding:16px;max-width:520px;width:100%;color:#191919;box-shadow:4px 4px 0 #191919;font-size:15px;line-height:1.5;overflow-wrap:anywhere}
  .card .hd{font-size:20px;font-weight:750;color:#815000;line-height:1.25;display:flex;align-items:center;gap:10px}
  .card .hd img{display:none}
  .card .mini-title{font:14px "Geist Pixel",ui-monospace,monospace;border-bottom:1px solid #191919;padding-bottom:8px;margin-bottom:12px;color:#3027cf}
  .card.c{padding:10px 12px;font-size:13px;box-shadow:2px 2px 0 #191919}.card.c .hd{font-size:17px}.card.c .mini-title{margin-bottom:6px;padding-bottom:4px}
  .card.c .row{margin-top:8px}.card.c button{font-size:13px;min-height:40px;padding:7px 9px}
  .q{margin:10px 0;padding:8px 10px;border-left:3px solid #443cf2;background:#eae9e2;font-size:14px}
  .meta{color:#55554f;font-size:13px}.bar{height:8px;background:#d2d1c7;margin:8px 0}.bar>span{display:block;height:100%;background:#815000}
  .badge{position:absolute;top:6px;right:6px;z-index:2147483000;cursor:pointer;font-size:13px;min-height:36px;padding:6px 10px;border-radius:0;background:#f4f3eb;color:#815000;border:2px solid #191919;box-shadow:2px 2px 0 #191919}
  .pop{position:absolute;top:48px;right:6px;z-index:2147483001;width:min(420px,90vw)}
  .fab{position:fixed;right:18px;bottom:18px;z-index:2147483603;min-height:56px;display:flex;align-items:center;justify-content:center;gap:9px;padding:10px 14px;background:#443cf2;color:white;border:2px solid #191919;box-shadow:4px 4px 0 #191919}
  .fab svg{width:28px;height:28px;shape-rendering:crispEdges}.fab-label{font-size:16px}.fab .n{position:absolute;top:-10px;right:-5px;background:#f4f3eb;color:#191919;border:1px solid #191919;font:700 12px system-ui;padding:2px 6px}
  .fab:hover{background:#3027cf;color:white}
  .menu{position:fixed;right:18px;bottom:88px;z-index:2147483600;background:#f4f3eb;border:2px solid #191919;box-shadow:5px 5px 0 #191919;width:min(350px,calc(100vw - 36px));max-height:calc(100dvh - 110px);overflow:auto;font-size:15px;color:#191919}
  .menu-header{display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:2px solid #191919;font:16px "Geist Pixel",monospace}
  .menu-header:after{content:"";flex:1;height:13px;background:repeating-linear-gradient(#191919 0 1px,transparent 1px 3px)}
  .menu-body{padding:18px}.menu-body p{margin:0 0 16px;line-height:1.5}.menu button{display:block;width:100%;text-align:left;margin-top:8px}
  .menu .t{font-size:13px;color:#55554f;line-height:1.5}.menu-status{margin:14px 0;border-top:1px solid #c4c3ba;padding-top:12px}.menu details{border-top:1px solid #c4c3ba;margin-top:16px;padding-top:6px}.menu summary{cursor:pointer;min-height:44px;padding:10px 0;font-weight:650}
  .hl{position:fixed;z-index:2147483500;pointer-events:none;border:2px solid #443cf2;background:rgba(68,60,242,.1)}
  .pbar{position:fixed;left:50%;transform:translateX(-50%);bottom:88px;z-index:2147483601;background:#f4f3eb;color:#191919;border:2px solid #191919;box-shadow:4px 4px 0 #191919;
    padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;width:max-content;max-width:calc(100vw - 36px);font-size:15px}
  .notice{position:fixed;left:18px;bottom:88px;z-index:2147483600;max-width:min(380px,calc(100vw - 36px))}
  .sheet{--ink:#191919;--paper:#f4f3eb;--blue:#443cf2;--sage:#e3e7d5;position:fixed;z-index:2147483602;
    right:24px;bottom:90px;width:min(620px,calc(100vw - 48px));max-height:calc(100dvh - 120px);
    display:flex;flex-direction:column;overflow:visible;border:2px solid var(--ink);color:var(--ink);background:var(--paper);
    box-shadow:7px 7px 0 var(--ink);font-size:14px;line-height:1.5;color-scheme:light;isolation:isolate}
  .sheet *{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  .sheet button,.sheet a{touch-action:manipulation}
  .sheet button{border:1.5px solid var(--ink);border-radius:0;background:var(--paper);color:var(--ink);font-size:13px;padding:10px 14px;min-height:42px}
  .sheet button:hover{background:var(--sage)}
  .sheet button.p{background:var(--blue);color:#fff;border-color:var(--blue)}
  .sheet button.p:hover{background:#3027cf}
  .sheet :focus-visible,.pbar :focus-visible,.menu :focus-visible{outline:3px solid #443cf2;outline-offset:3px}
  .sheet .window-bar{display:flex;align-items:center;gap:10px;padding:7px 9px;border-bottom:2px solid var(--ink);flex-shrink:0}
  .sheet .window-name{font:400 15px/1.2 "Geist Pixel",ui-monospace,monospace;letter-spacing:.02em;white-space:nowrap}
  .sheet .window-stripes{flex:1;height:14px;background:repeating-linear-gradient(to bottom,var(--ink) 0 1px,transparent 1px 3px)}
  .sheet .window-close{padding:0;min-height:28px;width:28px;display:grid;place-items:center;font:22px/1 monospace}
  .sheet .window-mark{width:14px;height:14px;border:2px solid var(--ink);box-shadow:inset 3px 3px 0 var(--paper);background:var(--blue)}
  .sheet .sheet-body{overflow:auto;overscroll-behavior:contain;min-height:0;padding:24px;overflow-wrap:anywhere}
  .sheet .eyebrow{font:700 11px/1.5 ui-monospace,"Courier New",monospace;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px}
  .sheet .elapsed{white-space:nowrap}
  .sheet .result-intro{display:flex;gap:18px;align-items:center;margin-bottom:20px}
  .sheet .pixel-art{flex-shrink:0;width:76px;height:76px;color:var(--blue);display:grid;place-items:center;
    background-color:var(--sage);background-image:radial-gradient(var(--blue) .65px,transparent .8px);background-size:4px 4px}
  .sheet .pixel-art svg{width:58px;height:58px;shape-rendering:crispEdges;background:var(--paper)}
  .sheet h2{color:var(--blue);font-size:27px;line-height:1.15;letter-spacing:-.035em;margin:0;font-weight:750}
  .sheet h3{font-size:22px;line-height:1.2;letter-spacing:-.025em;margin:7px 0 12px;color:var(--blue)}
  .sheet p{margin:10px 0}
  .sheet .selected-text{margin:16px 0;padding:12px 14px;border-left:3px solid var(--blue);background:#eae9e2;font-size:13px;max-height:104px;overflow:auto}
  .sheet .selected-label{font:700 10px/1.5 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:5px}
  .sheet .loader-track{height:18px;border:1px solid var(--ink);padding:3px;overflow:hidden;margin:20px 0 10px}
  .sheet .loader-blocks{width:36%;height:100%;background:repeating-linear-gradient(to right,var(--blue) 0 8px,transparent 8px 11px);animation:scan 1.6s steps(12) infinite}
  .sheet .muted{color:#55554f;font-size:12px}
  .sheet .claim-result{border-top:1px solid var(--ink);padding:18px 0}
  .sheet .claim-result:last-child{padding-bottom:0}
  .sheet .claim-text{margin:8px 0 12px;font-size:13px;color:#55554f}
  .sheet .verdict-label{display:inline-block;font:700 11px/1.5 ui-monospace,monospace;letter-spacing:.04em;text-transform:uppercase;background:var(--sage);padding:3px 7px}
  .sheet .strength{font-size:12px;margin:12px 0}
  .sheet .sources-label{font:700 11px/1.5 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em;margin:16px 0 7px}
  .sheet .source{border:1px solid #c4c3ba;padding:10px 12px;margin-top:8px;font-size:12px;background:#faf9f3}
  .sheet .source a{display:block;color:#3027cf;font-weight:650;text-decoration:underline;text-underline-offset:3px;margin:5px 0}
  .sheet .source blockquote{margin:8px 0 0;border-left:2px solid #c4c3ba;padding-left:10px;color:#55554f}
  .sheet .caveat{font-size:12px;padding:10px 12px;background:var(--sage);margin:12px 0}
  .sheet .sheet-footer{padding:14px 24px 18px;border-top:1px solid var(--ink);flex-shrink:0}
  .sheet .sheet-footer .row{margin:10px 0 0}
  .sheet:has(.compact-result){width:min(510px,calc(100vw - 48px))}
  .sheet .compact-result{border-top:0;padding:0 0 18px}
  .sheet .compact-result + .compact-result{border-top:1px solid #c4c3ba;padding-top:18px}
  .sheet .verdict-heading{display:flex;gap:16px;align-items:center;--verdict-color:#55554f}
  .sheet .tone-false{--verdict-color:#a32424}.sheet .tone-true{--verdict-color:#17623b}.sheet .tone-warning{--verdict-color:#815000}
  .sheet .verdict-heading h2{color:var(--verdict-color);font-size:32px;letter-spacing:-.025em}
  .sheet .verdict-symbol{display:grid;place-items:center;flex-shrink:0;width:58px;height:58px;border:2px solid currentColor;color:var(--verdict-color);font:700 42px/1 ui-monospace,monospace}
  .sheet .verdict-hint{font-size:17px;line-height:1.5;margin:16px 0}
  .sheet .compact-sources .source{padding:8px 0;border:0;border-top:1px solid #d2d1c7;background:none;margin:0}
  .sheet .compact-sources .source a{font-size:16px;margin:2px 0}
  .sheet .compact-sources .source .muted{display:block;font-size:13px}
  .sheet .result-details{border-top:1px solid #d2d1c7;margin-top:10px;font-size:15px}
  .sheet .result-details summary{cursor:pointer;padding:12px 0;min-height:44px;font-size:15px;font-weight:650}
  .sheet .demo-note{font-size:13px;background:var(--sage);padding:8px 10px;margin-bottom:18px}
  .sheet:has(.compact-result) .sheet-footer .row{margin:0}
  .sheet:has(.compact-result) .sheet-footer button{font-size:15px;min-height:48px}
  .sheet:has(.compact-result) .sheet-footer .row{display:grid;grid-template-columns:1fr}
  .sheet:has(.compact-result) .sheet-footer button[data-s="x"]{border-color:transparent;min-height:40px;padding:6px}
  @keyframes scan{from{transform:translateX(-110%)}to{transform:translateX(290%)}}
  @media(max-width:520px){.sheet{right:12px;bottom:82px;width:calc(100vw - 24px);max-height:calc(100dvh - 104px);box-shadow:4px 4px 0 var(--ink)}
    .sheet:has(.compact-result){width:calc(100vw - 24px)}.sheet .verdict-heading h2{font-size:28px}.sheet .verdict-symbol{width:48px;height:48px;font-size:34px}
    .sheet .sheet-body{padding:18px}.sheet .sheet-footer{padding:12px 18px}.sheet h2{font-size:24px}
    .sheet .pixel-art{width:54px;height:54px}.sheet .pixel-art svg{width:42px;height:42px}.sheet .result-intro{gap:12px}
    .sheet .row button{flex:1}.sheet .window-name{font-size:12px}}
  @media(prefers-reduced-motion:reduce){.sheet .loader-blocks{animation:none;width:100%;opacity:.65}}
  `;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const fmtDate = s => { if (!s) return "b.d."; const [y, m, d] = s.slice(0, 10).split("-"); return d ? `${d}.${m}.${y}` : s; };
  const safeUrl = u => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : "#"; } catch { return "#"; } };

  function shadowHost(parent, fixed = false) {
    const h = document.createElement("prawdowid-ui");
    h.style.cssText = fixed ? "position:fixed;inset:auto;z-index:2147483600" : "position:absolute;inset:0;z-index:2147483000;pointer-events:none";
    const root = h.attachShadow({mode: "open"});
    const st = document.createElement("style"); st.textContent = CSS; root.append(st);
    parent.append(h);
    return {host: h, root};
  }
  const isOurs = el => !!el?.closest?.("prawdowid-ui");

  // ------------------------------------------------------------------ result rendering on page elements
  const results = new Map(); // text hash -> QuickResult
  const pending = new Map(); // id -> {target, text, hash}
  const seen = new WeakMap(); // element -> hash
  let flaggedCount = 0;

  function hash(s) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36) + s.length; }

  function matchCard(r, text, cls, compact = false) {
    const m = r.match;
    return `<div class="card ${cls}${compact ? " c" : ""}">
      <div class="mini-title">Prawdowid · ostrzeżenie</div><div class="hd">! Treść wymaga uwagi</div>
      <p style="margin:8px 0">Podobną informację ${esc(m.publisher)} ocenił(a) jako <b>${esc(m.verdict_raw || (m.verdict === "false" ? "fałszywą" : "wprowadzającą w błąd"))}</b>.</p>
      ${compact ? "" : `<div class="meta">To dopasowanie treści, a nie pełna weryfikacja. Sprawdź kontekst.</div><div class="meta">Źródło: ${esc(m.publisher)} · ${esc(fmtDate(m.published_at))}</div>`}
      <div class="row"><button class="p" data-a="analiza">Sprawdź szczegóły</button><button data-a="${cls === "h" ? "pokaz" : "zamknij"}">${cls === "h" ? "Odsłoń treść" : "Zamknij"}</button></div></div>`;
  }

  function render(target, r, text) {
    if (!target.isConnected || r.level === "brak" || target.querySelector(":scope > prawdowid-ui")) return;
    if (getComputedStyle(target).position === "static") target.style.position = "relative";
    const {host: h, root} = shadowHost(target);
    flaggedCount++; updateFab();
    const wire = (scope) => scope.querySelectorAll("[data-a]").forEach(b => b.addEventListener("click", ev => {
      ev.preventDefault(); ev.stopPropagation();
      const a = b.dataset.a;
      if (a === "analiza") checkText(text, target);
      if (a === "zrodlo") window.open(safeUrl(r.match.url), "_blank", "noopener");
      if (a === "pokaz" || a === "zamknij") { root.querySelector(".ov, .pop")?.remove(); if (a === "pokaz") showBadge(); }
    }));
    function showBadge() {
      const b = document.createElement("button");
      b.className = "badge" + (r.level === "wysokie" ? " h" : "");
      b.style.pointerEvents = "auto";
      b.textContent = "! Sprawdź tę treść";
      b.title = "Prawdowid: kliknij, aby zobaczyć szczegóły";
      b.onclick = ev => { ev.preventDefault(); ev.stopPropagation();
        const ex = root.querySelector(".pop"); if (ex) { ex.remove(); return; }
        const p = document.createElement("div"); p.className = "pop"; p.style.pointerEvents = "auto"; p.innerHTML = matchCard(r, text, "m"); root.append(p); wire(p); };
      root.append(b);
    }
    if (r.level === "wysokie" && S.mode === "zaslon") {
      // the card must fit INSIDE the post, never spill over neighbouring content
      const hgt = target.getBoundingClientRect().height;
      const compact = hgt < 270;
      if (hgt < 210) target.style.minHeight = "210px";
      const ov = document.createElement("div"); ov.className = "ov"; ov.style.pointerEvents = "auto";
      ov.innerHTML = matchCard(r, text, "h", compact); root.append(ov); wire(ov);
      ov.addEventListener("click", e => e.stopPropagation());
    } else showBadge();
  }

  // ------------------------------------------------------------------ real-time scanning of visible content
  const io = new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { queue(e.target); io.unobserve(e.target); }
  }, {threshold: 0.2});
  const targetText = new WeakMap();
  let batch = [], timer = null, seq = 0;

  function queue(target) {
    const text = targetText.get(target);
    if (!text) return;
    const h = hash(text);
    if (results.has(h)) return render(target, results.get(h), text);
    const id = "i" + (seq++);
    pending.set(id, {target, text, h});
    batch.push({id, text: text.slice(0, 1500)});
    if (!timer) timer = setTimeout(flush, 500);
  }

  async function flush() {
    timer = null;
    const items = batch.splice(0, 16);
    if (batch.length) timer = setTimeout(flush, 300);
    if (!items.length) return;
    const r = await send({type: "quick", items});
    if (!r?.ok) { console.debug("[Prawdowid] quick failed", r?.error); items.forEach(i => pending.delete(i.id)); return; }
    for (const q of r.data) {
      const p = pending.get(q.id); pending.delete(q.id);
      if (!p) continue;
      results.set(p.h, q);
      if (q.level !== "brak") render(p.target, q, p.text);
    }
  }

  function scan() {
    if (!S.noticeSeen || !supportsAutoScan || !S.autoScan || S.disabledSites.includes(host) || !adapter) return;
    for (const {target, text} of adapter.items(document)) {
      if (!target || isOurs(target) || !text || text.length < 40) continue;
      const h = hash(text);
      if (seen.get(target) === h) continue;
      seen.set(target, h); targetText.set(target, text);
      io.observe(target);
    }
  }
  let scanTimer = null;
  const mo = new MutationObserver(() => { if (!scanTimer) scanTimer = setTimeout(() => { scanTimer = null; scan(); }, 700); });

  // ------------------------------------------------------------------ floating button + menu + picker
  const ui = shadowHost(document.documentElement, true);
  const fab = document.createElement("button");
  fab.className = "fab"; fab.title = "Prawdowid — sprawdź fragment"; fab.setAttribute("aria-label", "Prawdowid — sprawdź fragment");
  fab.innerHTML = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M8 3h12v3h4v4h3v10h-3v4h-4v3H8v-3H4v-4H1V10h3V6h4V3Z" stroke="currentColor" stroke-width="2"/><path d="m23 24 7 7M8 10h3V7h7" stroke="currentColor" stroke-width="3"/></svg><span class="fab-label">Sprawdź</span><span class="n" hidden></span>`;
  fab.setAttribute("aria-expanded", "false");
  // Keep the main entry point available even when a SPA replaces its DOM.
  new MutationObserver(() => { if (!ui.host.isConnected) document.documentElement.append(ui.host); }).observe(document.documentElement, {childList: true});
  ui.root.append(fab);
  function updateFab() { const n = fab.querySelector(".n"); n.hidden = !flaggedCount; n.textContent = flaggedCount; }

  let menu = null;
  fab.addEventListener("click", e => { e.stopPropagation(); menu ? closeMenu() : openMenu(); });
  function closeMenu() { menu?.remove(); menu = null; fab.setAttribute("aria-expanded", "false"); }
  function openMenu() {
    stopPicker(); closeSheet(false);
    closeMenu();
    menu = document.createElement("section"); menu.className = "menu"; menu.setAttribute("aria-label", "Sprawdzanie informacji");
    fab.setAttribute("aria-expanded", "true");
    const sel = String(getSelection() || "").trim();
    const disabled = S.disabledSites.includes(host);
    const paused = disabled || !S.autoScan;
    menu.innerHTML = `<div class="menu-header">Prawdowid</div><div class="menu-body">
      <p>Nie wiesz, czy wierzyć tej informacji?</p>
      <button class="p" data-m="pick">Wybierz fragment do sprawdzenia</button>
      <p class="t" style="margin-top:8px">Potem kliknij tekst na stronie. Resztą zajmiemy się my.</p>
      ${sel.length > 20 ? '<button data-m="sel">Sprawdź zaznaczony tekst</button>' : ""}
      <button data-m="web">Otwórz stronę Prawdowid ↗</button>
      <div class="menu-status t">${S.mockMode ? "Tryb demo · wyniki są przykładowe." : !supportsAutoScan ? "Na tej stronie sprawdzaj treści przez wybór fragmentu." : paused ? "Automatyczne ostrzeżenia są wstrzymane." : "Automatyczne ostrzeżenia są włączone."}</div>
      ${supportsAutoScan ? `<details><summary>Ostrzeżenia na tej stronie</summary><button data-m="toggle">${paused ? "Włącz ostrzeżenia tutaj" : "Wstrzymaj ostrzeżenia tutaj"}</button><p class="t" style="margin-top:10px">Lupka i ręczne sprawdzanie pozostają dostępne.</p></details>` : ""}
      <details><summary>Jak to działa?</summary><p class="t">${S.mockMode ? "W trybie demonstracyjnym tekst zostaje w przeglądarce. Wynik jest fikcyjny." : "Do sprawdzenia wysyłamy tekst fragmentu, bez adresu strony. Wynik opieramy na źródłach. Brak ostrzeżenia nie oznacza, że informacja jest prawdziwa."}</p><p class="t">Ustawienia znajdziesz pod ikoną Prawdowida na pasku przeglądarki.</p></details></div>`;
    menu.addEventListener("click", async e => {
      const m = e.target.closest("button")?.dataset.m; if (!m) return;
      closeMenu();
      if (m === "pick") startPicker();
      if (m === "sel") checkText(sel, null);
      if (m === "web") send({type: "openWebsite", demo: !!S.mockMode});
      if (m === "toggle") {
        const on = paused;
        S.disabledSites = on ? S.disabledSites.filter(h => h !== host) : [...S.disabledSites, host];
        if (on) S.autoScan = true;
        await send({type: "setSettings", data: {disabledSites: S.disabledSites, autoScan: S.autoScan}});
        if (on) scan();
        openMenu();
      }
    });
    menu.addEventListener("keydown", e => { if (e.key === "Escape") { closeMenu(); fab.focus(); } });
    ui.root.append(menu);
    menu.querySelector("button")?.focus({preventScroll: true});
  }
  document.addEventListener("click", e => { if (menu && !isOurs(e.target)) closeMenu(); }, true);

  // Element picker: one click/tap immediately starts verification.
  let picking = false, hovered = null, hl = null, pbar = null;
  function startPicker() {
    stopPicker(); closeMenu(); closeSheet(false);
    picking = true;
    hl = document.createElement("div"); hl.className = "hl"; hl.hidden = true; ui.root.append(hl);
    pbar = document.createElement("div"); pbar.className = "pbar";
    pbar.setAttribute("role", "status");
    pbar.innerHTML = `<span>${isMobile ? "Dotknij" : "Kliknij"} fragment — sprawdzanie rozpocznie się od razu.</span><button data-p="x">Anuluj · Esc</button>`;
    pbar.querySelector("button").addEventListener("click", stopPicker);
    ui.root.append(pbar);
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("click", onPick, true);
    document.addEventListener("keydown", onKey, true);
  }
  function stopPicker() {
    picking = false; hovered = null; hl?.remove(); pbar?.remove(); hl = pbar = null;
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("click", onPick, true);
    document.removeEventListener("keydown", onKey, true);
  }
  function onMove(e) {
    if (!picking || isOurs(e.target)) return;
    hovered = e.target;
    const r = hovered.getBoundingClientRect();
    hl.hidden = false;
    Object.assign(hl.style, {left: r.left - 3 + "px", top: r.top - 3 + "px", width: r.width + 6 + "px", height: r.height + 6 + "px"});
  }
  function onPick(e) {
    if (!picking || isOurs(e.target)) return;
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    let selected = e.target.closest("p, article, li, blockquote, h1, h2, h3, [role='article'], div") || e.target;
    while (selected.parentElement && txt(selected).length < 40 && selected.parentElement !== document.body) selected = selected.parentElement;
    stopPicker();
    checkElement(selected);
  }
  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); stopPicker(); fab.focus(); }
    if (e.key === "Enter" && hovered) { e.preventDefault(); onPick({target: hovered, preventDefault() {}, stopPropagation() {}, stopImmediatePropagation() {}}); }
  }

  // ------------------------------------------------------------------ on-demand check → Macintosh result window
  let sheet = null, checkVersion = 0, returnFocus = null;
  const PIXEL_ART = `<div class="pixel-art" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M10 3h12v3h4v4h3v12h-3v4h-4v3H10v-3H6v-4H3V10h3V6h4V3Z" stroke="currentColor" stroke-width="2"/><path d="M12 11v-3h8v3h3v5h-4v4h-5v-6h5v-3h-7Zm2 12h5v4h-5z" fill="currentColor"/></svg></div>`;
  function closeSheet(restoreFocus = true) {
    checkVersion++; // Late replies must not reopen a dismissed or superseded window.
    sheet?.remove(); sheet = null;
    document.removeEventListener("keydown", onSheetKey, true);
    if (restoreFocus) (returnFocus?.isConnected ? returnFocus : fab).focus();
    returnFocus = null;
  }
  function onSheetKey(e) {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeSheet(); }
  }
  function openSheet(html, {title = "Wynik sprawdzenia", loading = false, footer = ""} = {}) {
    const isNew = !sheet;
    const focusWasInside = sheet?.contains(ui.root.activeElement);
    if (!sheet) returnFocus = ui.root.activeElement || document.activeElement;
    sheet?.remove(); sheet = document.createElement("section"); sheet.className = "sheet";
    sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-label", `Prawdowid — ${title}`);
    sheet.setAttribute("aria-busy", String(loading)); sheet.tabIndex = -1;
    sheet.innerHTML = `<header class="window-bar"><span class="window-mark" aria-hidden="true"></span><span class="window-name">Prawdowid · ${esc(title)}</span><span class="window-stripes" aria-hidden="true"></span><button class="window-close" data-s="x" aria-label="Zamknij okno">×</button></header>
      <div class="sheet-body">${html}</div>${footer ? `<footer class="sheet-footer">${footer}</footer>` : ""}`;
    ui.root.append(sheet);
    sheet.addEventListener("click", e => {
      if (e.target.closest("[data-s]")?.dataset.s === "x") closeSheet();
    });
    document.addEventListener("keydown", onSheetKey, true);
    // Keep keyboard focus inside the replacement, without stealing it back from the page.
    if (isNew || focusWasInside) sheet.focus({preventScroll: true});
    return sheet;
  }
  function messageSheet(title, message, retry) {
    const sh = openSheet(`<div class="result-intro">${PIXEL_ART}<div><div class="eyebrow">Sprawdzanie informacji</div><h2>${esc(title)}</h2></div></div><p role="status">${esc(message)}</p>`, {
      title, footer: `<div class="row">${retry ? '<button class="p" data-s="retry">Spróbuj ponownie</button>' : '<button class="p" data-s="pick">Wybierz inny fragment</button>'}<button data-s="x">Zamknij</button></div>`
    });
    sh.querySelector('[data-s="retry"]')?.addEventListener("click", retry);
    sh.querySelector('[data-s="pick"]')?.addEventListener("click", startPicker);
  }
  function checkElement(el) {
    const t = txt(el);
    if (t.length < 15) {
      const hasImg = el.querySelector?.("img, video") || /^(IMG|VIDEO)$/.test(el.tagName);
      messageSheet("Wybierz fragment tekstu", hasImg ? "Ten fragment to głównie obraz lub wideo. Odczyt tekstu z obrazów (OCR) nie jest jeszcze włączony — to ograniczenie techniczne, a nie ocena treści. Wybierz tekst posta lub opis." : "Za mało tekstu do sprawdzenia. Wybierz większy fragment.");
      return;
    }
    checkText(t, el);
  }
  async function checkText(text, el) {
    const version = ++checkVersion;
    closeMenu();
    openSheet(`<div class="result-intro">${PIXEL_ART}<div><div class="eyebrow">Sprawdzanie informacji</div><h2>Sprawdzam, co mówią źródła.</h2></div></div>
      <div class="selected-text"><span class="selected-label">Wybrany fragment</span>${esc(text.slice(0, 280))}${text.length > 280 ? "…" : ""}</div>
      <div class="loader-track" role="progressbar" aria-label="Trwa sprawdzanie informacji"><div class="loader-blocks"></div></div>
      <p role="status">${S.mockMode ? "Ładowanie przykładowego wyniku…" : "Trwa analiza treści i wyszukiwanie dowodów."}</p><p class="muted">${S.mockMode ? "Tryb demonstracyjny · tekst pozostaje w przeglądarce." : "Wysyłamy tylko tekst fragmentu, bez adresu strony."}</p>`, {title: S.mockMode ? "Demo · sprawdzanie…" : "Sprawdzanie…", loading: true});
    // The optional quick annotation must never delay the full answer or turn its failure into an error.
    if (el) send({type: "quick", items: [{id: "pick", text: text.slice(0, 1500)}]}).then(quick => {
      if (version === checkVersion && quick?.ok && quick.data?.[0]?.level !== "brak" && quick.data?.[0]?.match) render(el, quick.data[0], text);
    }).catch(() => {});
    let full;
    try { full = await send({type: "check", text: text.slice(0, 6000)}); }
    catch { full = {ok: false}; }
    if (version !== checkVersion) return;
    if (!full?.ok) {
      messageSheet("Nie udało się sprawdzić", "Nie udało się połączyć z serwerem Prawdowida. Spróbuj ponownie za chwilę. To błąd techniczny, a nie ocena treści.", () => checkText(text, el));
      return;
    }
    const res = full.data;
    if (res.status !== "ok") {
      messageSheet(res.status === "blad_techniczny" ? "Błąd techniczny" : res.status === "doprecyzuj" ? "Doprecyzuj pytanie" : "Poza zakresem", res.status_message || "Nie można wykonać tego sprawdzenia.", res.status === "blad_techniczny" ? () => checkText(text, el) : null);
      return;
    }
    const verdictView = {
      falszywe: {label: "Fałsz", icon: "×", tone: "false", hint: "Źródła przeczą tej informacji."},
      potwierdzone: {label: "Potwierdzone", icon: "✓", tone: "true", hint: "Źródła potwierdzają tę informację."},
      wprowadzajace_w_blad: {label: "Wprowadza w błąd", icon: "!", tone: "warning", hint: "Informacja pomija ważny kontekst lub przedstawia go błędnie."},
      brak_dowodow: {label: "Brak dowodów", icon: "?", tone: "unknown", hint: "Nie można ustalić, czy to prawda. Brak dowodów nie oznacza fałszu."},
      nie_podlega_weryfikacji: {label: "To nie jest fakt do sprawdzenia", icon: "—", tone: "unknown", hint: "Opinii lub przewidywania nie można ocenić jako prawdy albo fałszu."}
    };
    const claims = res.claims.map((c, i) => {
      const v = verdictView[c.verdict] || verdictView.brak_dowodow;
      const src = c.evidence.slice(0, 2);
      // Keep every claim's verdict distinct; a mixed passage must not get a single red/green label.
      return `<article class="claim-result compact-result">
        ${res.claims.length > 1 ? `<div class="eyebrow">Informacja ${i + 1} z ${res.claims.length}</div>` : ""}
        <div class="verdict-heading tone-${v.tone}"><span class="verdict-symbol" aria-hidden="true">${v.icon}</span><h2>${esc(v.label)}</h2></div>
        <p class="verdict-hint">${esc(v.hint)}</p>
        ${res.claims.length > 1 ? `<div class="claim-text">„${esc(c.claim)}”</div>` : ""}
        ${src.length ? `<div class="compact-sources"><div class="sources-label">${res.demo ? "Przykładowe źródła" : "Źródła"}</div>${src.map(e => `<div class="source"><a href="${safeUrl(e.url)}" target="_blank" rel="noopener noreferrer nofollow">${esc(e.publisher)} ↗</a><span class="muted">${esc(fmtDate(e.published_at))} · ${esc(e.title)}</span></div>`).join("")}</div>` : ""}
        <details class="result-details"><summary>Pokaż uzasadnienie${src.length ? " i cytaty" : ""}</summary>
          <div class="claim-text">Sprawdzono: „${esc(c.claim)}”</div><p>${esc(c.explanation)}</p>
          ${!["brak_dowodow", "nie_podlega_weryfikacji"].includes(c.verdict) ? `<p class="strength">Siła podstaw: <b>${esc(c.strength_label)}</b></p>` : ""}
          ${c.what_unknown ? `<p>Nie ustalono: ${esc(c.what_unknown)}</p>` : ""}
          ${c.would_settle ? `<p>Co pomoże rozstrzygnąć: ${esc(c.would_settle)}</p>` : ""}
          ${src.map(e => e.fragment ? `<div class="source"><b>${esc(e.publisher)}</b><blockquote>„${esc(e.fragment)}”</blockquote></div>` : "").join("")}
          ${(c.limitations || []).map(l => `<p class="muted">${esc(l)}</p>`).join("")}
        </details></article>`;
    }).join("");
    const sh = openSheet(`${res.demo ? '<div class="demo-note" role="note">Dane testowe · przykładowy wynik, nie ocena wybranego tekstu.</div>' : ""}
      ${claims}${res.warnings.length ? `<details class="result-details"><summary>Ważne uwagi (${res.warnings.length})</summary>${res.warnings.map(w => `<p class="muted">${esc(w)}</p>`).join("")}</details>` : ""}`, {
      title: res.demo ? "Demo · przykładowy wynik" : "Wynik sprawdzenia",
      footer: `<div class="row"><button class="p" data-s="full">Więcej szczegółów na stronie ↗</button><button data-s="x">Zamknij</button></div>`
    });
    sh.querySelector('[data-s="full"]').addEventListener("click", () => send(res.demo ? {type: "openWebsite", demo: true} : {type: "openAnalysis", id: res.id}));
  }

  // ------------------------------------------------------------------ first-run privacy notice + start
  function notice() {
    const n = document.createElement("div"); n.className = "notice";
    n.innerHTML = `<div class="card"><div class="mini-title">Prawdowid · pierwsze uruchomienie</div><div class="hd">Sprawdź, zanim uwierzysz.</div>
      <p style="margin:8px 0">${S.mockMode ? "Włączony jest tryb demonstracyjny. Wyniki są fikcyjne, a tekst pozostaje w przeglądarce." : "Możemy ostrzegać o widocznych treściach podobnych do obalonych informacji. Wysyłamy sam tekst fragmentów na serwer, bez adresu strony. Brak ostrzeżenia nie oznacza, że treść jest prawdziwa."}</p>
      <div class="row"><button class="p" data-n="ok">Włącz ostrzeżenia</button><button data-n="off">Sprawdzam tylko ręcznie</button></div></div>`;
    n.addEventListener("click", async e => {
      const a = e.target.closest("button")?.dataset.n; if (!a) return;
      S.noticeSeen = true;
      S.autoScan = a === "ok";
      await send({type: "setSettings", data: {noticeSeen: true, autoScan: S.autoScan}});
      n.remove();
      if (S.autoScan) scan();
    });
    ui.root.append(n);
  }

  (async () => {
    const r = await send({type: "settings"});
    if (r?.ok) S = Object.assign(S, r.data);
    if (!S.noticeSeen && supportsAutoScan) notice();
    scan();
    mo.observe(document.body, {childList: true, subtree: true});
  })();
  api.storage?.onChanged?.addListener(ch => {
    for (const k in ch) S[k] = ch[k].newValue;
    if (menu) openMenu();
    if (ch.mockMode) closeSheet(); // Do not show a reply from the previous mode.
  });
  api.runtime.onMessage.addListener(msg => { if (msg?.type === "startPicker") startPicker(); if (msg?.type === "openMenu") openMenu(); });
})();
