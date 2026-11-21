// Prawdowid — background (service worker in Chrome, event page in Firefox).
// All network calls go through here: content scripts never talk to the API directly (CORS/CSP-safe),
// and only the text of the checked fragment is sent — no cookies, no user identifiers, no page HTML.
const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = {apiBase: "http://localhost:8000", demoWebBase: "http://localhost:5500", mockMode: false, autoScan: true, mode: "zaslon", minLevel: "srednie", disabledSites: [], noticeSeen: false};

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

async function post(path, body) {
  const {apiBase} = await settings();
  const r = await fetch(apiBase.replace(/\/$/, "") + path, {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body), credentials: "omit", signal: AbortSignal.timeout(45000)});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const stats = {}; // per tab: scanned / flagged

api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "settings") return sendResponse({ok: true, data: await settings()});
      if (msg.type === "setSettings") { await api.storage.local.set(msg.data); return sendResponse({ok: true}); }
      if (msg.type === "quick") {
        if ((await settings()).mockMode) return sendResponse({ok: true, data: msg.items.map(i => ({id: i.id, level: "brak", risk: 0, match: null}))});
        const data = await post("/api/quick", {items: msg.items, page_url: null}); // page URL deliberately not sent
        const tab = sender.tab?.id;
        if (tab != null) {
          const s = stats[tab] = stats[tab] || {scanned: 0, flagged: 0};
          s.scanned += msg.items.length; s.flagged += data.filter(d => d.level !== "brak").length;
          api.action.setBadgeText({tabId: tab, text: s.flagged ? String(s.flagged) : ""});
          api.action.setBadgeBackgroundColor?.({tabId: tab, color: "#b42318"});
        }
        return sendResponse({ok: true, data});
      }
      if (msg.type === "check") {
        if ((await settings()).mockMode) {
          await new Promise(resolve => setTimeout(resolve, 1200));
          return sendResponse({ok: true, data: mockResult(msg.text)});
        }
        return sendResponse({ok: true, data: await post("/api/check", {text: msg.text, channel: "extension"})});
      }
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
    } catch (e) { sendResponse({ok: false, error: String(e.message || e)}); }
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
