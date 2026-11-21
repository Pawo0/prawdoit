// Prawdowid — background (service worker in Chrome, event page in Firefox).
// All network calls go through here: content scripts never talk to the API directly (CORS/CSP-safe),
// and only the text of the checked fragment is sent — no cookies, no user identifiers, no page HTML.
const api = globalThis.browser ?? globalThis.chrome;
// mode: "oznacz" = badge with the source (default); "zaslon" = cover strongly matched posts — opt-in in the popup.
// autoVerify: let the page send up to 3 unmarked fragments per page view to a background check (mode "auto").
// Off by default: measured on repo data, the full check still gives a wrong "sources contradict" result for 3.7 % of
// ordinary official sentences and 26 % of hard negatives (eval/results/router_measure.md) — acceptable when a person
// asks and reads the sources, not as an unrequested mark. Switch on in the popup, or here once that rate is down.
const DEFAULTS = {apiBase: "http://localhost:8000", demoWebBase: "http://localhost:5500", mockMode: false, autoScan: true, autoVerify: false, mode: "oznacz", minLevel: "srednie", disabledSites: [], noticeSeen: false};

async function settings() { return Object.assign({}, DEFAULTS, await api.storage.local.get(Object.keys(DEFAULTS))); }

function mockResult(text) {
  return {
    id: "demo-local", demo: true, status: "ok", channel: "extension", input_excerpt: text,
    summary: "Przykładowa analiza do testowania wyglądu wtyczki.",
    warnings: ["TRYB DEMONSTRACYJNY — fikcyjny wynik i źródła. Wybrany tekst nie został zweryfikowany ani wysłany na serwer."],
    claims: [{
      claim: text, verdict: "wprowadzajace_w_blad", verdict_label: "Wprowadzające w błąd",
      strength_label: "umiarkowana (przykład)",
      explanation: "Tak może wyglądać uzasadnienie: informacja pomija istotny kontekst, a przywołane dane dotyczą innego okresu. To wyłącznie przykładowa treść interfejsu, niezależna od wybranego fragmentu.",
      limitations: ["Dane demonstracyjne służą wyłącznie do pracy nad interfejsem."],
      evidence: [
        {stance: "przeczy", publisher: "Przykładowa instytucja · DEMO", title: "Komunikat źródłowy — fikcyjny materiał testowy", published_at: "2026-11-20", url: "https://example.org/komunikat-demo", fragment: "Przedstawione dane odnoszą się do wcześniejszego okresu i nie opisują obecnej sytuacji. [Fikcyjny cytat demonstracyjny]"},
        {stance: "kontekst", publisher: "Przykładowa redakcja · DEMO", title: "Kontekst informacji — fikcyjna analiza", published_at: "2026-11-21", url: "https://example.org/analiza-demo", fragment: "Do oceny informacji potrzebne są data publikacji oraz pełny kontekst wypowiedzi. [Fikcyjny cytat demonstracyjny]"}
      ]
    }]
  };
}

// POST when a body is given, GET otherwise. A failed request carries the HTTP status and the server's Retry-After.
async function call(path, body, timeoutMs = 45000) {
  const {apiBase} = await settings();
  const r = await fetch(apiBase.replace(/\/$/, "") + path, {method: body === undefined ? "GET" : "POST", cache: "no-store", credentials: "omit",
    signal: AbortSignal.timeout(timeoutMs), ...(body === undefined ? {} : {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)})});
  if (!r.ok) throw Object.assign(new Error(`HTTP ${r.status}`), {status: r.status, retryAfter: Number(r.headers?.get?.("Retry-After")) || 0});
  return r.json();
}
const failed = e => ({ok: false, error: String(e.message || e), status: e.status || 0, retryAfter: e.retryAfter || 0});
const isMatch = d => d.state ? d.state === "match" : d.level !== "brak"; // `state` comes from servers with the router

// Full check without one long request: Chrome stops an extension service worker whose fetch() takes more than 30 s
// to answer, and a check with a page fetch and live search can. So the check is started as a job and the page polls
// it through short "job" messages (each one also wakes the worker if the browser has suspended it meanwhile).
// A server without the job API gets the old synchronous request — manual checks only: a background ("auto") check
// must never fall back to a request that the server would treat as a normal check.
async function startCheck(text, mode) {
  let started;
  try { started = await call("/api/check/async", {text, channel: "extension", mode}, 20000); }
  catch (e) { if (![404, 405, 501].includes(e.status)) throw e; }
  if (started?.job_id && (mode !== "auto" || started.mode === "auto")) return {ok: true, job: started.job_id};
  if (mode === "auto") return {ok: false, error: "background checks are not supported by this server", status: 0, retryAfter: 0};
  return {ok: true, data: await call("/api/check", {text, channel: "extension"})};
}

const stats = {}; // per tab: scanned / flagged

api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "settings") return sendResponse({ok: true, data: await settings()});
      if (msg.type === "setSettings") { await api.storage.local.set(msg.data); return sendResponse({ok: true}); }
      if (msg.type === "quick") {
        if ((await settings()).mockMode) return sendResponse({ok: true, data: msg.items.map(i => ({id: i.id, level: "brak", risk: 0, match: null}))});
        const data = await call("/api/quick", {items: msg.items, page_url: null}, 20000); // page URL deliberately not sent
        const tab = sender.tab?.id;
        if (tab != null) {
          const s = stats[tab] = stats[tab] || {scanned: 0, flagged: 0};
          s.scanned += msg.items.length; s.flagged += data.filter(isMatch).length;
          api.action.setBadgeText({tabId: tab, text: s.flagged ? String(s.flagged) : ""});
          api.action.setBadgeBackgroundColor?.({tabId: tab, color: "#443cf2"}); // a count of sourced tags, not an alarm
        }
        return sendResponse({ok: true, data});
      }
      if (msg.type === "check") {
        const mode = msg.mode === "auto" ? "auto" : "manual";
        if ((await settings()).mockMode) {
          if (mode === "auto") return sendResponse({ok: false, error: "demo mode", status: 0, retryAfter: 0});
          await new Promise(resolve => setTimeout(resolve, 1200));
          return sendResponse({ok: true, data: mockResult(msg.text)});
        }
        return sendResponse(await startCheck(msg.text, mode));
      }
      if (msg.type === "job") return sendResponse({ok: true, data: await call("/api/jobs/" + encodeURIComponent(msg.id), undefined, 10000)});
      if (msg.type === "openWebsite") {
        const s = await settings();
        const url = new URL(msg.demo ? s.demoWebBase : s.apiBase);
        if (!/^https?:$/.test(url.protocol)) throw new Error("Nieprawidłowy adres strony");
        await api.tabs.create({url: url.href});
        return sendResponse({ok: true});
      }
      if (msg.type === "openAnalysis") {
        const {apiBase} = await settings();
        const url = msg.id ? `${apiBase}/analiza/${msg.id}` : `${apiBase}/sprawdz?ch=extension#t=${encodeURIComponent(msg.text.slice(0, 1800))}`;
        await api.tabs.create({url});
        return sendResponse({ok: true});
      }
      if (msg.type === "stats") return sendResponse({ok: true, data: stats[msg.tabId] || {scanned: 0, flagged: 0}});
      sendResponse({ok: false, error: "unknown message"});
    } catch (e) { sendResponse(failed(e)); }
  })();
  return true; // async response
});

// Desktop: right-click → "Sprawdź w Prawdowidzie" on selected text (context menus are not available on Android).
function setupMenus() {
  if (!api.contextMenus) return;
  api.contextMenus.removeAll(() => api.contextMenus.create({id: "prawdowid-check", title: "Sprawdź w Prawdowidzie: „%s”", contexts: ["selection"]}));
}
api.runtime.onInstalled?.addListener(setupMenus);
api.contextMenus?.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "prawdowid-check" || !info.selectionText) return;
  const {apiBase} = await settings();
  api.tabs.create({url: `${apiBase}/sprawdz?ch=extension#t=${encodeURIComponent(info.selectionText.slice(0, 1800))}`});
});
api.tabs?.onRemoved.addListener(id => delete stats[id]);
