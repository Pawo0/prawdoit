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
  const send = msg => globalThis.browser ? browser.runtime.sendMessage(msg) : new Promise(res => chrome.runtime.sendMessage(msg, res));
  const host = location.hostname.replace(/^www\./, "");
  const isMobile = matchMedia("(pointer: coarse)").matches;
  let S = {autoScan: true, mode: "zaslon", disabledSites: [], noticeSeen: false, apiBase: ""};

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
        root.querySelectorAll("a h2, a h3, h2 a, h3 a, a[class*='title'], [class*='title'] > a").forEach(e => {
          const t = txt(e); if (t.length >= 25 && t.length <= 240) out.push({target: e.closest("article, li") || e.closest("a") || e, text: t});
        });
        return out;
      } },
  ];
  // local demo pages mimic several site structures at once
  const isDemo = /^(localhost|127\.0\.0\.1)$/.test(host);
  const adapter = isDemo ? {name: "demo", items: root => ADAPTERS.slice(0, 2).flatMap(a => a.items(root))} : ADAPTERS.find(a => a.test(host));

  // ------------------------------------------------------------------ UI (shadow DOM, isolated from page CSS)
  const CSS = `
  :host{all:initial}
  *{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  .ov{position:absolute;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:8px;overflow:hidden;
      backdrop-filter:blur(9px) saturate(.6);-webkit-backdrop-filter:blur(9px);background:rgba(255,255,255,.55);border-radius:8px}
  .card{background:#fff;border:2px solid #b42318;border-radius:14px;padding:14px 16px;max-width:520px;width:100%;color:#101828;
        box-shadow:0 8px 24px rgba(16,24,40,.18);font-size:14px;line-height:1.45}
  .card.m{border-color:#b54708}
  .card.c{padding:8px 12px;font-size:13px}.card.c .q,.card.c .bar,.card.c .meta.x{display:none}.card.c .row{margin-top:6px}
  .hd{display:flex;align-items:center;gap:8px;font-weight:800;color:#b42318;font-size:15px}
  .card.m .hd{color:#b54708}
  .q{margin:8px 0;padding:6px 10px;border-left:3px solid #d0d5dd;background:#f9fafb;font-style:italic;font-size:13px}
  .meta{color:#475467;font-size:12px}
  .bar{height:8px;background:#eaecf0;border-radius:99px;overflow:hidden;margin:6px 0 2px}
  .bar>span{display:block;height:100%;background:#b42318}
  .card.m .bar>span{background:#b54708}
  .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  button{font:inherit;font-weight:650;font-size:13px;border-radius:10px;padding:8px 12px;cursor:pointer;border:1.5px solid #1d3557;background:#fff;color:#1d3557}
  button.p{background:#1d3557;color:#fff}
  .badge{position:absolute;top:6px;right:6px;z-index:2147483000;cursor:pointer;font-weight:800;font-size:12px;padding:4px 9px;
         border-radius:99px;background:#fffaeb;color:#b54708;border:1.5px solid #b54708;box-shadow:0 2px 6px rgba(0,0,0,.15)}
  .badge.h{background:#fef3f2;color:#b42318;border-color:#b42318}
  .pop{position:absolute;top:34px;right:6px;z-index:2147483001;width:min(420px,92vw)}
  .fab{position:fixed;right:18px;bottom:18px;z-index:2147483600;width:54px;height:54px;border-radius:50%;border:0;padding:0;
       background:#1d3557;box-shadow:0 6px 18px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;cursor:pointer}
  .fab img{width:30px;height:30px}
  .fab .n{position:absolute;top:-4px;right:-4px;background:#b42318;color:#fff;font-size:11px;font-weight:800;border-radius:99px;padding:2px 6px}
  .menu{position:fixed;right:18px;bottom:82px;z-index:2147483600;background:#fff;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.25);
        padding:8px;width:280px;font-size:14px;color:#101828}
  .menu button{display:block;width:100%;text-align:left;border:0;border-radius:8px;padding:10px 12px;font-weight:600}
  .menu button:hover{background:#f2f4f7}
  .menu .t{font-size:12px;color:#475467;padding:4px 12px 8px}
  .hl{position:fixed;z-index:2147483500;pointer-events:none;border:3px solid #f79009;background:rgba(247,144,9,.12);border-radius:6px;transition:all .06s}
  .hl.sel{border-color:#1d3557;background:rgba(29,53,87,.12)}
  .pbar{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;z-index:2147483601;background:#101828;color:#fff;border-radius:14px;
        padding:10px 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;max-width:94vw;font-size:14px;box-shadow:0 8px 24px rgba(0,0,0,.3)}
  .pbar button{border-color:#fff;background:transparent;color:#fff}
  .pbar button.p{background:#fff;color:#101828}
  .sheet{position:fixed;right:18px;bottom:82px;z-index:2147483602;width:min(440px,94vw);max-height:70vh;overflow:auto}
  .v{display:inline-block;font-weight:800;border-radius:99px;padding:3px 10px;border:2px solid currentColor;margin:4px 0}
  .v-falszywe{color:#b42318;background:#fef3f2}.v-wprowadzajace_w_blad{color:#b54708;background:#fffaeb}
  .v-potwierdzone{color:#067647;background:#ecfdf3}.v-brak_dowodow{color:#475467;background:#f2f4f7}.v-nie_podlega_weryfikacji{color:#6941c6;background:#f4f3ff}
  .src{font-size:12px;margin:6px 0;padding:6px 8px;background:#f9fafb;border-radius:8px}
  .src a{color:#2f5d8a}
  .spin{width:18px;height:18px;border:3px solid #d0d5dd;border-top-color:#1d3557;border-radius:50%;animation:s 1s linear infinite;display:inline-block;vertical-align:middle}
  @keyframes s{to{transform:rotate(360deg)}}
  .notice{position:fixed;left:18px;bottom:18px;z-index:2147483600;max-width:380px}
  `;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const fmtDate = s => { if (!s) return "b.d."; const [y, m, d] = s.slice(0, 10).split("-"); return d ? `${d}.${m}.${y}` : s; };
  const safeUrl = u => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : "#"; } catch { return "#"; } };
  const ICON = api.runtime.getURL("icons/icon48.png");

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
    const m = r.match; const pct = Math.round(r.risk * 100);
    const what = m.verdict === "false" ? (r.level === "wysokie" ? "prawdopodobny fałsz" : "możliwy fałsz") : "może wprowadzać w błąd";
    if (compact) return `<div class="card ${cls} c">
      <div class="hd"><img src="${ICON}" width="18" height="18" alt="">Prawdowid: ${pct}% — ${what}</div>
      <div>Zbieżne z: „${esc(m.claim.slice(0, 90))}${m.claim.length > 90 ? "…" : ""}” — <b>${esc(m.publisher)}: ${esc(m.verdict_raw || m.verdict)}</b></div>
      <div class="row"><button class="p" data-a="analiza">Dlaczego? →</button>${cls === "h" ? '<button data-a="pokaz">Pokaż</button>' : '<button data-a="zamknij">Zamknij</button>'}</div></div>`;
    return `<div class="card ${cls}">
      <div class="hd"><img src="${ICON}" width="20" height="20" alt="">Prawdowid: ${what}</div>
      <div style="margin-top:6px">Ta treść jest zbieżna z informacją, którą <b>${esc(m.publisher)}</b> ocenił(a) jako <b>„${esc(m.verdict_raw || m.verdict)}”</b> (${fmtDate(m.published_at)}).</div>
      <div class="q">Sprawdzone twierdzenie: „${esc(m.claim.slice(0, 220))}”</div>
      <div class="meta">Prawdopodobieństwo, że to powtórzenie obalonej informacji: <b>${pct}%</b></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
      <div class="meta x">Ocena dotyczy treści, nie autora ani portalu. Model może się mylić — sprawdź źródło.</div>
      <div class="row"><button class="p" data-a="analiza">Dlaczego? Zobacz analizę →</button>
        <a href="${safeUrl(m.url)}" target="_blank" rel="noopener nofollow"><button data-a="zrodlo">Źródło (${esc(m.publisher)})</button></a>
        ${cls === "h" ? '<button data-a="pokaz">Pokaż mimo to</button>' : '<button data-a="zamknij">Zamknij</button>'}</div></div>`;
  }

  function render(target, r, text) {
    if (!target.isConnected || r.level === "brak" || target.querySelector(":scope > prawdowid-ui")) return;
    if (getComputedStyle(target).position === "static") target.style.position = "relative";
    const {host: h, root} = shadowHost(target);
    flaggedCount++; updateFab();
    const wire = (scope) => scope.querySelectorAll("[data-a]").forEach(b => b.addEventListener("click", ev => {
      ev.preventDefault(); ev.stopPropagation();
      const a = b.dataset.a;
      if (a === "analiza") send({type: "openAnalysis", text});
      if (a === "zrodlo") window.open(safeUrl(r.match.url), "_blank", "noopener");
      if (a === "pokaz" || a === "zamknij") { root.querySelector(".ov, .pop")?.remove(); if (a === "pokaz") showBadge(); }
    }));
    function showBadge() {
      const b = document.createElement("div");
      b.className = "badge" + (r.level === "wysokie" ? " h" : "");
      b.style.pointerEvents = "auto";
      b.textContent = `⚠ ${Math.round(r.risk * 100)}% · ${r.match.verdict === "false" ? "możliwy fałsz" : "może wprowadzać w błąd"}`;
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
      if (hgt < 128) target.style.minHeight = "128px";
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
    if (!S.autoScan || S.disabledSites.includes(host) || !adapter) return;
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
  fab.innerHTML = `<img src="${ICON}" alt=""><span class="n" hidden></span>`;
  ui.root.append(fab);
  function updateFab() { const n = fab.querySelector(".n"); n.hidden = !flaggedCount; n.textContent = flaggedCount; }

  let menu = null;
  fab.addEventListener("click", e => { e.stopPropagation(); menu ? closeMenu() : openMenu(); });
  function closeMenu() { menu?.remove(); menu = null; }
  function openMenu() {
    menu = document.createElement("div"); menu.className = "menu";
    const sel = String(getSelection() || "").trim();
    const disabled = S.disabledSites.includes(host);
    menu.innerHTML = `<div class="t"><b>Prawdowid</b> · oznaczono na tej stronie: ${flaggedCount}</div>
      <button data-m="pick">🎯 Wybierz fragment do sprawdzenia</button>
      ${sel.length > 20 ? '<button data-m="sel">✂️ Sprawdź zaznaczony tekst</button>' : ""}
      <button data-m="toggle">${disabled || !S.autoScan ? "▶️ Włącz automatyczne oznaczanie tutaj" : "⏸ Wyłącz automatyczne oznaczanie tutaj"}</button>
      <button data-m="mode">${S.mode === "zaslon" ? "👁 Tryb: zasłaniaj (zmień na: tylko oznaczaj)" : "🏷 Tryb: tylko oznaczaj (zmień na: zasłaniaj)"}</button>
      <div class="t">Wysyłamy tylko tekst sprawdzanych fragmentów — bez danych o Tobie. Oceniamy treść, nie portal.</div>`;
    menu.addEventListener("click", async e => {
      const m = e.target.closest("button")?.dataset.m; if (!m) return;
      closeMenu();
      if (m === "pick") startPicker();
      if (m === "sel") checkText(sel, null);
      if (m === "toggle") {
        const on = disabled || !S.autoScan;
        S.disabledSites = on ? S.disabledSites.filter(h => h !== host) : [...S.disabledSites, host];
        if (on) S.autoScan = true;
        await send({type: "setSettings", data: {disabledSites: S.disabledSites, autoScan: S.autoScan}});
        if (on) scan();
      }
      if (m === "mode") { S.mode = S.mode === "zaslon" ? "oznacz" : "zaslon"; await send({type: "setSettings", data: {mode: S.mode}}); }
    });
    ui.root.append(menu);
  }
  document.addEventListener("click", e => { if (menu && !isOurs(e.target)) closeMenu(); }, true);

  // element picker (uBlock-style): hover highlights, click/tap selects, ⬆ expands to parent, Enter/Sprawdź confirms
  let picking = false, hovered = null, selected = null, hl = null, pbar = null;
  function startPicker() {
    picking = true; selected = null;
    hl = document.createElement("div"); hl.className = "hl"; ui.root.append(hl);
    pbar = document.createElement("div"); pbar.className = "pbar";
    pbar.innerHTML = `<span>${isMobile ? "Dotknij" : "Kliknij"} treść do sprawdzenia</span><button data-p="up">⬆ Większy obszar</button><button class="p" data-p="ok" disabled>Sprawdź</button><button data-p="x">Anuluj</button>`;
    pbar.addEventListener("click", e => {
      const p = e.target.closest("button")?.dataset.p;
      if (p === "x") stopPicker();
      if (p === "up" && selected?.parentElement && selected.parentElement !== document.body) { selected = selected.parentElement; box(selected, true); }
      if (p === "ok" && selected) { const el = selected; stopPicker(); checkElement(el); }
    });
    ui.root.append(pbar);
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("click", onPick, true);
    document.addEventListener("keydown", onKey, true);
  }
  function stopPicker() {
    picking = false; hl?.remove(); pbar?.remove(); hl = pbar = null;
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("click", onPick, true);
    document.removeEventListener("keydown", onKey, true);
  }
  function box(el, sel) {
    const r = el.getBoundingClientRect();
    Object.assign(hl.style, {left: r.left - 3 + "px", top: r.top - 3 + "px", width: r.width + 6 + "px", height: r.height + 6 + "px"});
    hl.classList.toggle("sel", !!sel);
    pbar.querySelector('[data-p="ok"]').disabled = !selected;
  }
  function onMove(e) {
    if (!picking || selected || isOurs(e.target)) return;
    hovered = e.target; box(hovered, false);
  }
  function onPick(e) {
    if (!picking || isOurs(e.target)) return;
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    selected = e.target.closest("p, article, li, blockquote, h1, h2, h3, [role='article'], div") || e.target;
    // grow tiny selections to something with enough text
    while (selected.parentElement && txt(selected).length < 40 && selected.parentElement !== document.body) selected = selected.parentElement;
    box(selected, true);
  }
  function onKey(e) {
    if (e.key === "Escape") stopPicker();
    if (e.key === "Enter" && selected) { const el = selected; stopPicker(); checkElement(el); }
  }

  // ------------------------------------------------------------------ on-demand check → result sheet
  let sheet = null;
  function openSheet(html) {
    sheet?.remove(); sheet = document.createElement("div"); sheet.className = "sheet";
    sheet.innerHTML = `<div class="card" style="border-color:#1d3557">${html}</div>`; ui.root.append(sheet);
    sheet.addEventListener("click", e => { const a = e.target.closest("[data-s]")?.dataset.s; if (a === "x") { sheet.remove(); sheet = null; } });
    return sheet;
  }
  function checkElement(el) {
    const t = txt(el);
    if (t.length < 15) {
      const hasImg = el.querySelector?.("img, video") || /^(IMG|VIDEO)$/.test(el.tagName);
      openSheet(`<div class="hd" style="color:#1d3557">Prawdowid</div><p>${hasImg ? "Ten fragment to głównie obraz/wideo. Odczyt tekstu z obrazów (OCR) nie jest jeszcze włączony w prototypie — to ograniczenie techniczne, a nie ocena treści. Zaznacz tekst posta lub opis." : "Za mało tekstu do sprawdzenia — wybierz większy obszar."}</p><div class="row"><button data-s="x">Zamknij</button></div>`);
      return;
    }
    checkText(t, el);
  }
  async function checkText(text, el) {
    const t0 = performance.now();
    openSheet(`<div class="hd" style="color:#1d3557"><span class="spin"></span> Sprawdzam…</div><div class="q">${esc(text.slice(0, 240))}${text.length > 240 ? "…" : ""}</div>`);
    const [quick, full] = await Promise.all([send({type: "quick", items: [{id: "pick", text: text.slice(0, 1500)}]}), send({type: "check", text: text.slice(0, 6000)})]);
    if (quick?.ok && el && quick.data[0].level !== "brak") render(el, quick.data[0], text);
    if (!full?.ok) {
      openSheet(`<div class="hd">Błąd techniczny</div><p>Nie udało się połączyć z serwerem Prawdowida (${esc(full?.error)}). To nie jest ocena treści.</p><div class="row"><button data-s="x">Zamknij</button></div>`);
      return;
    }
    const res = full.data; const secs = ((performance.now() - t0) / 1000).toFixed(1);
    if (res.status !== "ok") {
      openSheet(`<div class="hd" style="color:#1d3557">Prawdowid</div><p>${esc(res.status_message)}</p><div class="row"><button data-s="x">Zamknij</button></div>`);
      return;
    }
    const claims = res.claims.map(c => {
      const src = (c.evidence.filter(e => e.stance !== "kontekst").length ? c.evidence.filter(e => e.stance !== "kontekst") : c.evidence).slice(0, 2);
      return `<div style="margin:8px 0 12px"><span class="v v-${c.verdict}">${esc(c.verdict_label)}</span>
        ${!["brak_dowodow", "nie_podlega_weryfikacji"].includes(c.verdict) ? `<span class="meta"> · siła podstaw: ${esc(c.strength_label)}</span>` : ""}
        <div class="meta" style="margin:4px 0">„${esc(c.claim.slice(0, 200))}”</div>
        <div>${esc(c.explanation.slice(0, 420))}${c.explanation.length > 420 ? "…" : ""}</div>
        ${src.map(e => `<div class="src"><b>${esc(e.publisher)}</b>, ${fmtDate(e.published_at)} — <a href="${safeUrl(e.url)}" target="_blank" rel="noopener nofollow">${esc(e.title.slice(0, 90))}</a></div>`).join("")}</div>`;
    }).join("");
    const sh = openSheet(`<div class="hd" style="color:#1d3557"><img src="${ICON}" width="20" height="20" alt=""> Prawdowid · ${esc(res.summary)}</div>
      ${res.warnings.slice(0, 1).map(w => `<div class="meta" style="margin-top:6px">ℹ️ ${esc(w)}</div>`).join("")}
      ${claims}
      <div class="meta">Analiza: ${secs} s · źródła z jawnego katalogu · Prawdowid nie jest sędzią prawdy.</div>
      <div class="row"><button class="p" data-s="full">Zobacz pełną analizę →</button><button data-s="x">Zamknij</button></div>`);
    sh.querySelector('[data-s="full"]').addEventListener("click", () => send({type: "openAnalysis", id: res.id}));
  }

  // ------------------------------------------------------------------ first-run privacy notice + start
  function notice() {
    const n = document.createElement("div"); n.className = "notice";
    n.innerHTML = `<div class="card" style="border-color:#1d3557"><div class="hd" style="color:#1d3557"><img src="${ICON}" width="20" height="20" alt="">Prawdowid działa na tej stronie</div>
      <p style="margin:8px 0">Sprawdzamy widoczne posty i nagłówki, wysyłając <b>sam tekst</b> (bez Twoich danych, bez adresu strony) do serwera Prawdowida. Oznaczamy tylko treści zbieżne z informacjami obalonymi przez fact-checkerów — nigdy całe portale.</p>
      <div class="row"><button class="p" data-n="ok">Rozumiem</button><button data-n="off">Wyłącz automatyczne oznaczanie</button></div></div>`;
    n.addEventListener("click", async e => {
      const a = e.target.closest("button")?.dataset.n; if (!a) return;
      S.noticeSeen = true;
      if (a === "off") S.autoScan = false;
      await send({type: "setSettings", data: {noticeSeen: true, autoScan: S.autoScan}});
      n.remove();
      if (S.autoScan) scan();
    });
    ui.root.append(n);
  }

  (async () => {
    const r = await send({type: "settings"});
    if (r?.ok) S = Object.assign(S, r.data);
    if (!S.noticeSeen) notice();
    scan();
    mo.observe(document.body, {childList: true, subtree: true});
  })();
  api.storage?.onChanged?.addListener(ch => { for (const k in ch) S[k] = ch[k].newValue; });
  api.runtime.onMessage.addListener(msg => { if (msg?.type === "startPicker") startPicker(); });
})();
