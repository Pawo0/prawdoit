// Prawdowid — background (service worker in Chrome, event page in Firefox).
// All network calls go through here: content scripts never talk to the API directly (CORS/CSP-safe),
// and only the text of the checked fragment is sent — no cookies, no user identifiers, no page HTML.
const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = {apiBase: "http://localhost:8000", autoScan: true, mode: "zaslon", minLevel: "srednie", disabledSites: [], noticeSeen: false};

async function settings() { return Object.assign({}, DEFAULTS, await api.storage.local.get(Object.keys(DEFAULTS))); }

async function post(path, body) {
  const {apiBase} = await settings();
  const r = await fetch(apiBase.replace(/\/$/, "") + path, {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body), credentials: "omit"});
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
      if (msg.type === "check") return sendResponse({ok: true, data: await post("/api/check", {text: msg.text, channel: "extension"})});
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
