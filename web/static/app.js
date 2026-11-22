// Prawdowid — shared front-end helpers (no framework, no build step).
const VERDICT_ICON = {falszywe: "✕", wprowadzajace_w_blad: "!", potwierdzone: "✓", brak_dowodow: "?", nie_podlega_weryfikacji: "—"};
const STANCE = {przeczy: "Przeczy twierdzeniu", popiera: "Potwierdza twierdzenie", kontekst: "Kontekst / temat pokrewny", neutralne: "Neutralne"};
const TIER = {1: "Źródło pierwotne / urzędowe", 2: "Fact-checking / zweryfikowana baza", 3: "Media"};
const STATUS = {blad_techniczny: "Błąd techniczny — to nie jest ocena treści", doprecyzuj: "Potrzebujemy doprecyzowania", poza_zakresem: "Poza zakresem"};
const GENERIC_STAGE = "Analizujemy treść i szukamy źródeł…";

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }
function fmtDate(s) { if (!s) return "brak daty"; const [y, m, d] = s.slice(0, 10).split("-"); return d ? `${d}.${m}.${y}` : s; }
function shortLic(l) { if (!l) return "—"; const x = l.split(/[;(]|\. /)[0].trim(); return x.length > 70 ? x.slice(0, 68) + "…" : x; }
function safeUrl(u) { try { const x = new URL(u); return ["http:", "https:"].includes(x.protocol) ? x.href : "#"; } catch { return "#"; } }
function cut(s, n) { s = String(s ?? ""); return s.length <= n ? s : s.slice(0, n - 1).replace(/\s+\S*$/, "") + "…"; }

function chrome_() {
  const h = document.createElement("header");
  h.className = "top";
  h.innerHTML = `<div class="wrap"><a class="logo" href="/" aria-label="Prawdowid — strona główna"><span class="brand-mark" aria-hidden="true"></span>Prawdowid</a>
    <nav class="site-nav" aria-label="Menu główne"><a href="/" ${location.pathname === "/" ? 'aria-current="page"' : ""}>Sprawdź</a><a href="/zrodla">Źródła</a><a class="nav-method" href="/metodologia">Jak to działa</a>
    <details class="nav-more"><summary>Więcej</summary><div><a href="/metodologia">Jak to działa</a><a href="/czat">Czat demonstracyjny</a><a href="/o-projekcie">O projekcie</a><a href="/moderator">Panel analityka</a></div></details></nav><span class="nav-tail" aria-hidden="true"></span><span class="header-tag">Oparte na źródłach.</span></div>`;
  const skip = document.createElement("a"); skip.className = "skip-link"; skip.href = "#main"; skip.textContent = "Przejdź do treści";
  document.body.prepend(skip);
  if (!document.querySelector("main").id) document.querySelector("main").id = "main";
  document.body.prepend(h);
  const f = document.createElement("footer");
  f.innerHTML = `Prawdowid — prototyp do sprawdzania informacji. Wyniki dotyczą dostępnych materiałów i mogą wymagać uzupełnienia. <a href="/metodologia">Jak to działa?</a> · <a href="/zrodla">Katalog źródeł</a>`;
  document.body.append(f);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  const m = document.createElement("link"); m.rel = "manifest"; m.href = "/manifest.webmanifest"; document.head.append(m);
}

function sessionId() {
  let s = null;
  try { s = localStorage.getItem("prawdowid_session"); } catch {}
  if (!s) { s = crypto.randomUUID().replace(/-/g, "").slice(0, 16); try { localStorage.setItem("prawdowid_session", s); } catch {} }
  return s;
}

// ------------------------------------------------------------------ API: async job with progress, sync fallback
const SYNC_TIMEOUT_MS = 45000;
function checkBody(input, channel = "web") {
  const t = input.trim();
  return /^https?:\/\/\S+$/.test(t) ? {url: t, channel, session: sessionId()} : {text: input, channel, session: sessionId()};
}
function postJSON(url, body, signal) {
  return fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body), signal});
}
async function errDetail(r) {
  const d = await r.json().catch(() => ({}));
  const det = typeof d.detail === "string" ? d.detail : d.detail ? JSON.stringify(d.detail) : "";
  return det || `Serwer odpowiedział kodem ${r.status}.`;
}
function sleep(ms, signal) {
  return new Promise((ok, fail) => {
    const t = setTimeout(ok, ms);
    signal?.addEventListener("abort", () => { clearTimeout(t); fail(new DOMException("Anulowano", "AbortError")); }, {once: true});
  });
}

// POST /api/check/async → {job_id}; poll GET /api/jobs/{id} every ~700 ms. Returns null when the server has no
// async endpoint (404/405/501, or a reply without job_id), so the caller can fall back to the synchronous call.
async function checkAsync(body, ui, signal) {
  const r = await postJSON("/api/check/async", body, signal);
  if ([404, 405, 501].includes(r.status)) return null;
  if (!r.ok) throw new Error(await errDetail(r));
  const {job_id} = await r.json().catch(() => ({}));
  if (!job_id) return null;
  for (;;) {
    await sleep(700, signal);
    const j = await fetch("/api/jobs/" + encodeURIComponent(job_id), {signal, cache: "no-store"});
    if (!j.ok) throw new Error(await errDetail(j));
    const s = await j.json();
    ui?.update(s);
    if (s.state === "done") { if (!s.result) throw new Error("Serwer nie zwrócił wyniku."); return s.result; }
    if (s.state === "error") throw new Error(s.error || s.detail || "Analiza nie powiodła się.");
  }
}

// ui: the object returned by openWait() (or null) — receives stage labels and gets its "Anuluj" wired to the request.
// image: optional data URL of a screenshot (read with OCR on the server, never stored); input is then the question.
async function checkWithProgress(input, channel = "web", ui = null, image = null) {
  const ctrl = new AbortController();
  if (ui) ui.onCancel = () => ctrl.abort();
  const body = image ? {text: input, image_b64: image, channel, session: sessionId()} : checkBody(input, channel);
  const res = await checkAsync(body, ui, ctrl.signal);
  if (res) return res;
  ui?.update({stage_label: GENERIC_STAGE});
  const signal = AbortSignal.any ? AbortSignal.any([ctrl.signal, AbortSignal.timeout(SYNC_TIMEOUT_MS)]) : ctrl.signal;
  const r = await postJSON("/api/check", body, signal);
  if (!r.ok) throw new Error(await errDetail(r));
  return r.json();
}

// kept for other callers: plain synchronous check
async function runCheck(input, channel = "web") {
  const r = await postJSON("/api/check", checkBody(input, channel), AbortSignal.timeout(SYNC_TIMEOUT_MS));
  if (!r.ok) throw new Error(await errDetail(r));
  return r.json();
}

function techMessage(e) {
  if (e?.name === "AbortError") return null;
  if (e?.name === "TimeoutError") return "Serwer nie odpowiedział na czas. Spróbuj ponownie za chwilę.";
  if (e instanceof TypeError) return "Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.";
  return e?.message || "Nieznany błąd.";
}
function renderTechError(el, e) {
  const msg = techMessage(e);
  el.innerHTML = msg === null
    ? `<section class="window result-error" role="status"><h2>Anulowano sprawdzenie.</h2><p>Nic nie zostało ocenione — możesz spróbować ponownie.</p></section>`
    : `<section class="window result-error" role="alert"><h2>Nie udało się sprawdzić informacji.</h2><p>${esc(msg)}</p><p><b>To błąd techniczny, a nie ocena treści.</b> Spróbuj ponownie za chwilę.</p></section>`;
}

// ------------------------------------------------------------------ waiting window
// The "Sprawdzanie informacji" window with the live stage from GET /api/jobs/{id}, elapsed seconds and "Anuluj".
// {inline: el}    — rendered in place of el's content (main page, /sprawdz); the caller overwrites it with the result.
// {container: el} — accessible modal dialog over el (chat demo); with neither option: over the whole page.
function openWait({inline = null, container = null, title = "Sprawdzanie informacji", label = "Analizujemy treść i szukamy dowodów. Poczekaj chwilę."} = {}) {
  const prev = document.activeElement;
  const id = "w" + Math.random().toString(36).slice(2, 8);
  const win = `<section class="window wait-window"${inline ? "" : ` role="dialog" aria-modal="true" aria-labelledby="${id}-t" aria-describedby="${id}-s"`}>
      <div class="window-bar blue-bar"><span class="window-square" aria-hidden="true"></span><span class="bar-title">${esc(title)}</span><span class="window-lines" aria-hidden="true"></span></div>
      <div class="loading-window"><h2 id="${id}-t">${esc(title)}</h2>
        <p id="${id}-s" class="wait-stage" role="status">${esc(label)}</p>
        <div class="loading-track" role="progressbar" aria-label="Trwa sprawdzanie"><span></span></div>
        <p class="small muted wait-time"><span data-sec>0</span> s · zwykle trwa to od 5 do 20 sekund</p>
        <button type="button" class="secondary" data-cancel>Anuluj</button></div></section>`;
  let root;
  if (inline) { inline.innerHTML = win; root = inline.firstElementChild; }
  else {
    root = document.createElement("div");
    root.className = "wait-ov" + (container ? " in-box" : "");
    root.innerHTML = win;
    (container || document.body).append(root);
  }
  const sec = root.querySelector("[data-sec]"), stage = root.querySelector(".wait-stage"), btn = root.querySelector("[data-cancel]");
  const t0 = Date.now();
  let server = 0;
  const tick = setInterval(() => { sec.textContent = Math.max(Math.floor((Date.now() - t0) / 1000), server); }, 250);
  const key = e => {
    if (e.key === "Escape") { e.preventDefault(); ui.onCancel?.(); }
    else if (e.key === "Tab") { e.preventDefault(); btn.focus(); }  // focus stays in the dialog
  };
  const ui = {
    onCancel: null,
    update(s) {
      if (s.stage_label && s.stage_label !== stage.textContent) stage.textContent = s.stage_label;
      if (typeof s.elapsed_s === "number") server = Math.floor(s.elapsed_s);
    },
    close(restore = false) {
      clearInterval(tick);
      if (inline) return;  // the inline window is replaced by whatever the caller renders next
      document.removeEventListener("keydown", key, true); root.remove(); if (restore) prev?.focus?.();
    },
  };
  btn.onclick = () => ui.onCancel?.();
  if (!inline) { document.addEventListener("keydown", key, true); btn.focus(); }
  return ui;
}

// ------------------------------------------------------------------ evidence chain
// Data cards written by Prawdowid from an institution's dataset (ingest/official_gus.py, official_nbp.py,
// official_eurostat.py; doc_id "<source>:…"): their text is not the publisher's own words, so it is not labelled
// as a quote. Changes, r/r and m/m rates and EU rankings in them are computed by the ingest from the data.
const DATA_CARD = {gus: "GUS", nbp: "NBP", eurostat: "Eurostatu"};
const COMPUTED = /zmiana [+−-]?\d|\d% (r\/r|m\/m)|m\/m\)|\d+\. (miejsc|najniższ|najwyższ)/;
function fragmentBlock(e) {
  const src = DATA_CARD[String(e.doc_id || "").split(":")[0]];
  if (!src) return `<blockquote><span class="small muted">Fragment źródła (cytat):</span><br>„${esc(e.fragment)}”</blockquote>`;
  const calc = COMPUTED.test(e.fragment || "")
    ? `<br><span class="small muted">Zmiany, stopy r/r i m/m oraz miejsca w rankingu to wyliczenie Prawdowida z tych danych.</span>` : "";
  return `<blockquote><span class="small muted">Opis automatyczny na podstawie danych ${src} (<a href="${safeUrl(e.url)}" target="_blank" rel="noopener noreferrer">zbiór danych</a>):</span><br>${esc(e.fragment)}${calc}</blockquote>`;
}
const COMPUTED_PREMISE = /^Porównanie liczb/;  // engine.numeric_stance: the comparison is Prawdowid's own arithmetic

function renderEvidence(e) {
  const fc = e.factcheck_verdict_raw ? `<div class="small">Sprawdzane twierdzenie: „${esc(e.factcheck_claim || e.title)}” — ocena źródła: <b>${esc(e.factcheck_verdict_raw)}</b>${e.same_claim === false ? " (Twoje twierdzenie jest jego zaprzeczeniem)" : ""}</div>` : "";
  return `<div class="ev">
    <div><span class="chip ${esc(e.stance)}">${STANCE[e.stance] || esc(e.stance)}</span><span class="chip tier${e.tier}">${TIER[e.tier] || ""}</span></div>
    <div class="evidence-title" style="margin-top:6px"><a href="${safeUrl(e.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(e.title)}</b></a></div>
    <div class="small muted">${esc(e.publisher)} · ${esc(e.domain)} · opublikowano ${fmtDate(e.published_at)}${e.age_days != null ? ` (${e.age_days} dni temu)` : ""}</div>
    ${fc}
    ${fragmentBlock(e)}
    <details><summary>Dane źródła i analizy</summary><div class="small muted">Podobieństwo do twierdzenia: ${(e.similarity * 100).toFixed(0)}% · ${e.stance !== "kontekst" ? `pewność oceny fragmentu: ${(e.stance_score * 100).toFixed(0)}% · ` : ""}pobrano ${fmtDate(e.retrieved_at)} · <span title="${esc(e.license)}">${esc(shortLic(e.license))}</span> (<a href="/zrodla">warunki</a>)</div></details>
  </div>`;
}

const REASON = {BRAK_MATERIALOW: "brak materiałów w katalogu źródeł", TYLKO_MATERIALY_POKREWNE: "są tylko materiały na pokrewny temat",
  ZRODLA_SPRZECZNE: "źródła są ze sobą sprzeczne", FACTCHECK_NIEWERYFIKOWALNE: "fact-checkerzy uznali to za nieweryfikowalne",
  NIEAKTUALNE_DOWODY: "dowody są nieaktualne", ROZNE_DEFINICJE: "wynik zależy od przyjętej miary wskaźnika",
  BRAK_DOPASOWANIA_MATERIALU: "nagłówek lub data strony nie zgadzają się z żadną analizą w katalogu źródeł"};
const CTX = {NIEAKTUALNE: "materiał nieaktualny / przedstawiony jako bieżący", MIESZANE: "część twierdzenia jest fałszywa i zmienia jego sens",
  WYBIORCZOSC_LUB_KONTEKST: "brakujący kontekst lub wybiórcze przedstawienie faktów",
  FALSZYWY_KONTEKST: "materiał z innego czasu przedstawiony jako bieżący"};
const KIND = {fakt: "twierdzenie o faktach", opinia: "opinia / ocena", prognoza: "przewidywanie", pytanie: "pytanie"};
const DECISIVE = ["falszywe", "potwierdzone", "wprowadzajace_w_blad"];

// Short-answer layer (backend answer.py) with fallbacks for results saved before it existed.
function mainEvidence(c) {
  if (c.main_evidence != null) return c.evidence[c.main_evidence] || null;
  if (!DECISIVE.includes(c.verdict)) return null;
  return c.evidence.find(e => e.stance === (c.verdict === "falszywe" ? "przeczy" : "popiera")) || null;
}
function basisLine(c) {
  if (c.basis_line) return c.basis_line;
  if (c.verdict === "brak_dowodow") return "Podstawa: niewystarczająca" + (c.reason_codes?.length ? " — " + c.reason_codes.map(r => REASON[r] || r).join("; ") : "");
  return DECISIVE.includes(c.verdict) && c.strength_label ? `Podstawa: ${c.strength_label}` : "";
}
function labelled(line) {  // "Podstawa: mocna — …" → <b>Podstawa:</b> mocna — …
  const m = String(line).match(/^([^:]{3,20}):\s*(.*)$/);
  return m ? `<b>${esc(m[1])}:</b> ${esc(m[2])}` : esc(line);
}

// One claim in the result window: verdict first, then the short answer, its basis / limitation lines and the main
// source, the checked claim and the quoted evidence. Premises, rules and the longer interpretation sit behind
// "Dlaczego taki wynik?" — folded on the main page, open on the explanation page (full = true).
function renderClaim(c, i, n, full = false) {
  const pe = p => p.effect === "+" ? `<span class="pe pe-plus" aria-label="wzmacnia">+</span>` : p.effect === "-" ? `<span class="pe pe-minus" aria-label="osłabia">−</span>` : `<span class="pe pe-0">•</span>`;
  const shown = c.verdict === "brak_dowodow" && !c.conflicting ? c.evidence.slice(0, 3) : c.evidence;
  const evid = shown.length ? shown.map(renderEvidence).join("") + (shown.length < c.evidence.length ? `<p class="small muted">+${c.evidence.length - shown.length} dalszych materiałów pokrewnych pominięto.</p>` : "") : `<p class="muted">Brak materiałów źródłowych do pokazania.</p>`;
  const main = mainEvidence(c);
  const facts = [basisLine(c), c.limitation_line].filter(Boolean);
  // an abstention that names related material links it too, labelled as not settling the claim (answer.py)
  const shownSrc = main || (c.related_evidence != null ? c.evidence[c.related_evidence] || null : null);
  const src = shownSrc ? `<div class="mainsrc"><small>${main ? "Główne źródło" : "Materiał pokrewny (nie rozstrzyga)"}</small>
      <a href="${safeUrl(shownSrc.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(shownSrc.title)}</b></a>
      <div class="small muted">${esc(shownSrc.publisher)} · ${fmtDate(shownSrc.published_at)}${shownSrc.domain ? ` · ${esc(shownSrc.domain)}` : ""}</div></div>` : "";
  const kind = [KIND[c.kind] || esc(c.kind), c.high_risk ? '<span class="chip przeczy">temat wysokiego ryzyka</span>' : ""].filter(Boolean).join(" · ");
  const interp = c.short_answer && c.explanation && c.explanation !== c.short_answer
    ? `<div class="interp"><div class="small muted">Nasza interpretacja (na podstawie źródeł poniżej):</div><p style="margin:4px 0 0">${esc(c.explanation)}</p></div>` : "";
  const premises = c.premises || [], open = full ? " open" : "";
  const why = premises.length || interp
    ? `<details${open}><summary>Dlaczego taki wynik?</summary>${interp}
      ${kind ? `<p class="small muted">Rodzaj wypowiedzi: ${kind}</p>` : ""}
      ${premises.length ? `<ul class="premises">${premises.map(p => `<li>${pe(p)} <b>${esc(p.label)}${COMPUTED_PREMISE.test(p.label) ? " — wyliczenie Prawdowida" : ""}:</b> ${esc(p.value)}</li>`).join("")}</ul>
      <div class="small muted">Reguły: ${(c.rules_fired || []).map(esc).join(", ") || "—"} · <a href="/metodologia#reguly">opis reguł</a></div>` : ""}</details>` : "";
  return `<section class="card claim-card b-${c.verdict}" aria-label="Twierdzenie ${i + 1}"><div class="window-bar blue-bar"><span class="window-square" aria-hidden="true"></span><span class="bar-title">Wynik sprawdzenia${n > 1 ? ` · ${i + 1} z ${n}` : ""}</span><span class="window-lines" aria-hidden="true"></span></div><div class="claim-body">
    <div class="verdict-hero"><span class="verdict-icon" aria-hidden="true">${VERDICT_ICON[c.verdict] || "?"}</span><div><div class="eyebrow">${n > 1 ? `Informacja ${i + 1} z ${n}` : "Co mówią źródła"}</div><h2>${esc(c.verdict === "falszywe" ? "Fałsz" : c.verdict_label)}</h2></div></div>
    <p class="verdict-explanation">${esc(c.short_answer || c.explanation)}</p>
    ${facts.length ? `<ul class="facts">${facts.map(f => `<li>${labelled(f)}</li>`).join("")}</ul>` : ""}
    ${src}
    <div class="claim-q"><small>Sprawdzana informacja</small>„${esc(c.claim)}”</div>
    ${c.missing_context ? `<div class="warn"><b>Brakujący kontekst:</b> ${esc(c.missing_context)}</div>` : ""}
    ${c.context_type && !c.missing_context ? `<div class="warn"><b>Rodzaj problemu:</b> ${esc(CTX[c.context_type] || c.context_type)}</div>` : ""}
    ${c.what_unknown ? `<div class="info"><b>Czego nie udało się ustalić:</b> ${esc(c.what_unknown)}${c.would_settle ? `<br><b>Co mogłoby to rozstrzygnąć:</b> ${esc(c.would_settle)}.` : ""}</div>` : ""}
    ${why}
    <h3 class="evidence-heading">Źródła i dowody</h3>
    <p class="small muted">Dosłowne fragmenty źródeł — oddzielone od naszej interpretacji powyżej.</p>
    ${evid}
    ${c.limitations?.length ? `<details${open}><summary>Ograniczenia tej odpowiedzi</summary><ul>${c.limitations.map(l => `<li>${esc(l)}</li>`).join("")}</ul></details>` : ""}
  </div></section>`;
}

function renderSignals(sig) {
  if (!sig?.length) return "";
  return `<section class="card"><h2 style="margin-top:0">Sprawdź sam — metoda SPRAWDŹ (NASK)</h2>
    <p class="small muted">Wskazówki edukacyjne na podstawie metody z kampanii NASK „Sprawdź, zanim udostępnisz”. <b>Nie wpływają na ocenę</b> — ta wynika wyłącznie ze źródeł.</p>
    <ul class="premises">${sig.map(s => `<li><span class="pe ${s.flagged ? "pe-minus" : "pe-0"}" style="width:28px">${esc(s.letter)}</span><b>${esc(s.name)}:</b> ${esc(s.note)}${s.hits?.length ? ` <span class="small muted">(np. ${s.hits.map(h => "„" + esc(h) + "”").join(", ")})</span>` : ""}</li>`).join("")}</ul>
    <p class="small">Więcej: <a href="https://www.nask.pl/dezinfo" target="_blank" rel="noopener">nask.pl/dezinfo</a> · Zgłoś dezinformację: <a href="https://zglos-dezinformacje.nask.pl" target="_blank" rel="noopener">zglos-dezinformacje.nask.pl</a> · Podejrzany SMS prześlij na numer <b>8080</b> (CERT Polska).</p></section>`;
}

// ≤ 3 trusted pages for the topic (backend resources.py) — pointers for the reader, never evidence.
function renderResources(list) {
  if (!list?.length) return "";
  return `<section class="card result-secondary"><h2 style="margin-top:0">Przydatne, zaufane strony</h2>
    <ul class="res-list">${list.slice(0, 3).map(r => `<li><a href="${safeUrl(r.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(r.title)}</b></a> — ${esc(r.why)}</li>`).join("")}</ul>
    <p class="small muted">Te strony nie były podstawą oceny — to miejsca, w których sam sprawdzisz podobne informacje.</p></section>`;
}

const SPRAWDZ_STATIC = `<section class="card"><h2 style="margin-top:0">Sprawdź samodzielnie — zanim udostępnisz</h2>
  <ol class="sprawdz">
    <li><b>Zatrzymaj się.</b> Silne emocje (strach, oburzenie) to sygnał, by zwolnić.</li>
    <li><b>Kto jest autorem?</b> Czy źródło jest znane i podpisane? Czy to oficjalne konto?</li>
    <li><b>Poszukaj tej informacji gdzie indziej</b> — w kilku niezależnych, wiarygodnych źródłach (np. komunikat urzędu, serwis fact-checkingowy).</li>
    <li><b>Sprawdź datę i miejsce.</b> Czy zdjęcie/wiadomość nie pochodzi z innego czasu lub kraju?</li>
    <li><b>Dotrzyj do źródła pierwotnego</b> — dokumentu, danych, pełnej wypowiedzi.</li>
    <li><b>Odróżnij fakt od opinii.</b> Opinii nie da się „sprawdzić”, ale fakty, na których się opiera — tak.</li>
  </ol></section>`;

// full = false: main result view (index) — verdict, short answer and sources; the reasoning is folded.
// full = true: explanation page (analiza) — the same windows with the reasoning open, every warning, the claims
// overview and the useful trusted pages.
function renderResult(res, el, {full = false} = {}) {
  if (res.status !== "ok") {
    const tech = res.status === "blad_techniczny";
    el.innerHTML = `<section class="window result-error" role="${tech ? "alert" : "status"}"><h2>${esc(STATUS[res.status] || res.status)}</h2><p>${esc(res.short_answer || res.status_message)}</p></section>`;
    return;
  }
  const t = res.timings_ms?.total_ms;
  const priority = {falszywe: 0, wprowadzajace_w_blad: 1, brak_dowodow: 2, nie_podlega_weryfikacji: 3, potwierdzone: 4};
  const orderedClaims = [...res.claims].sort((a, b) => (priority[a.verdict] ?? 2) - (priority[b.verdict] ?? 2));
  // the live-search notice is already summarised in each claim's "Ograniczenie" line — full text only on the analysis page
  const warnings = (res.warnings || []).filter(w => full || w !== res.live_search?.notice);
  const meta = res.url_meta;
  el.innerHTML = `
    ${res.demo ? '<div class="demo-banner"><b>Przykładowy wynik.</b> Dane są fikcyjne — to podgląd wyglądu, bez sprawdzania przez serwer.</div>' : ""}
    ${warnings.map(w => `<div class="warn">${esc(w)}</div>`).join("")}
    ${full && orderedClaims.length > 1 && res.claims_overview ? `<p class="muted">${esc(res.claims_overview)}</p>` : ""}
    ${orderedClaims.map((c, i) => renderClaim(c, i, orderedClaims.length, full)).join("")}
    ${full ? renderResources(res.resources) : ""}
    ${res.case_status ? `<div class="info"><b>Pętla informacji:</b> ${esc(res.case_status)}</div>` : ""}
    <details class="card result-secondary"><summary>Jak samodzielnie rozpoznawać manipulację?</summary>${renderSignals(res.signals) || SPRAWDZ_STATIC}</details>
    <details class="card result-secondary"><summary>Zgłoś błąd w wyniku</summary>
      <p class="small">Jeśli uważasz, że wynik jest błędny lub źródło zostało źle zrozumiane — daj nam znać. Zgłoszenie trafi do analityka, a poprawki publikujemy w rejestrze korekt.</p>
      <form id="fb" class="row"><label class="sr-only" for="fbm">Opisz błąd</label><input id="fbm" maxlength="1000" required placeholder="Co jest nie tak?" style="flex:1;font:inherit;padding:10px;border-radius:10px;border:1px solid #d0d5dd"><button>Zgłoś błąd</button></form>
      <p id="fbok" class="small" role="status" hidden>Dziękujemy — zgłoszenie zapisano.</p></details>
    <p class="small muted">Odpowiedź przygotował automatyczny system wykorzystujący modele sztucznej inteligencji do wyszukiwania i porównywania źródeł. Ocena wynika z jawnych reguł, nie z „opinii” modelu.</p>
    <details class="card result-secondary"><summary>Przebieg sprawdzenia i dane techniczne</summary>
      <p class="result-meta">Sprawdzana treść${meta?.domain ? ` (${esc(meta.domain)})` : ""}: ${esc(res.input_excerpt)}${meta?.title ? `<br>Tytuł strony: ${esc(meta.title)} · data: ${esc(meta.date || "brak")}` : ""}<br>${res.summary ? `Wynik: ${esc(res.summary)} · ` : ""}ID: ${esc(res.id)}${t ? ` · Czas: ${(t / 1000).toFixed(1)} s` : ""}</p>
      <table><tr><th>Czas utworzenia</th><td>${esc(res.created_at)}</td></tr>
      <tr><th>Kanał</th><td>${esc(res.channel)}</td></tr>
      <tr><th>Czasy etapów [ms]</th><td>${Object.entries(res.timings_ms || {}).map(([k, v]) => `${esc(k)}: ${Math.round(v)}`).join(" · ")}</td></tr>
      <tr><th>Modele</th><td>embedding: ${esc(res.engine?.embed_model)} · NLI: ${esc(res.engine?.nli_model)} · LLM: ${esc(res.engine?.llm || "nieużywany (wyjaśnienia z szablonów)")}</td></tr>
      <tr><th>Korpus</th><td>${esc(res.engine?.corpus_documents)} dokumentów (wczytano ${esc(res.engine?.corpus_loaded_at)})</td></tr>
      <tr><th>Wersja reguł / przetwarzanie</th><td>${esc(res.engine?.rules_version)} · ${esc(res.engine?.processing)}</td></tr>
      <tr><th>Zdarzenia bezpieczeństwa</th><td>${res.security_events?.length ? res.security_events.map(e => esc(e.kind + " — " + e.where)).join("<br>") : "brak"}</td></tr></table>
      <p class="small"><button type="button" class="secondary" id="delsess">Usuń historię moich sprawdzeń</button></p>
    </details>`;
  el.querySelector("#fb")?.addEventListener("submit", async e => { e.preventDefault();
    const fbok = el.querySelector("#fbok"), say = msg => { fbok.textContent = msg; fbok.hidden = false; };
    if (res.demo) { say("To podgląd demonstracyjny. Zgłoszenie nie zostało wysłane."); return; }
    try {
      const response = await postJSON("/api/feedback", {check_id: res.id, message: el.querySelector("#fbm").value});
      if (!response.ok) throw new Error(await errDetail(response));
      el.querySelector("#fb").hidden = true; say("Dziękujemy — zgłoszenie zapisano.");
    } catch { say("Nie udało się zapisać zgłoszenia (błąd techniczny). Spróbuj ponownie."); } });
  el.querySelector("#delsess")?.addEventListener("click", async () => {
    if (res.demo) { alert("Podgląd nie zapisuje historii na serwerze."); return; }
    const r = await fetch("/api/session/" + sessionId(), {method: "DELETE"}); const d = await r.json();
    alert(`Usunięto ${d.deleted_checks} zapisanych sprawdzeń z tej przeglądarki.`); });
}

document.addEventListener("DOMContentLoaded", chrome_);
