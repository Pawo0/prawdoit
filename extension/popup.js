const api = globalThis.browser ?? globalThis.chrome;
const send = msg => globalThis.browser ? browser.runtime.sendMessage(msg) : new Promise(r => chrome.runtime.sendMessage(msg, r));
(async () => {
  const [tab] = await api.tabs.query({active: true, currentWindow: true});
  const s = (await send({type: "settings"})).data;
  const mock = document.getElementById("mock");
  mock.checked = !!s.mockMode;
  const mockStatus = document.getElementById("mock-status");
  mockStatus.textContent = s.mockMode ? "Włączony — wyniki są fikcyjne." : "Wyłączony — sprawdzanie wymaga serwera.";
  mock.onchange = async () => {
    mock.disabled = true;
    const enabled = mock.checked;
    try {
      const result = await send({type: "setSettings", data: {mockMode: enabled}});
      if (!result?.ok) throw new Error("save failed");
      s.mockMode = enabled;
      mockStatus.textContent = enabled ? "Włączony — wyniki są fikcyjne." : "Wyłączony — sprawdzanie wymaga serwera.";
    } catch {
      mock.checked = !!s.mockMode;
      mockStatus.textContent = "Nie udało się zapisać ustawienia. Spróbuj ponownie.";
    } finally { mock.disabled = false; }
  };
  document.getElementById("auto").checked = s.autoScan;
  document.getElementById("mode").checked = s.mode === "zaslon";
  document.getElementById("api").value = s.apiBase;
  document.getElementById("demo-web").value = s.demoWebBase || "http://localhost:5500";
  const st = (await send({type: "stats", tabId: tab?.id})).data;
  document.getElementById("st").textContent = `Na tej karcie sprawdzono ${st.scanned} fragmentów, oznaczono ${st.flagged}.`;
  document.getElementById("auto").onchange = e => send({type: "setSettings", data: {autoScan: e.target.checked}});
  document.getElementById("mode").onchange = e => send({type: "setSettings", data: {mode: e.target.checked ? "zaslon" : "oznacz"}});
  document.getElementById("save").onclick = async () => {
    const status = document.getElementById("save-status");
    const data = {apiBase: document.getElementById("api").value.trim() || "http://localhost:8000", demoWebBase: document.getElementById("demo-web").value.trim() || "http://localhost:5500"};
    try {
      for (const value of Object.values(data)) if (!/^https?:$/.test(new URL(value).protocol)) throw new Error();
      if (!(await send({type: "setSettings", data}))?.ok) throw new Error();
      status.textContent = "Zapisano adresy.";
    } catch { status.textContent = "Nie udało się zapisać. Podaj poprawne adresy http:// lub https://."; }
  };
  document.getElementById("web").onclick = () => send({type: "openWebsite", demo: !!s.mockMode});
  async function activate(type) {
    try {
      await api.scripting.executeScript({target: {tabId: tab.id}, files: ["content.js"]});
      await api.tabs.sendMessage(tab.id, {type});
      window.close();
    } catch { document.getElementById("action-status").textContent = "Na tej stronie przeglądarka nie pozwala wyświetlić lupki. Otwórz zwykłą stronę internetową i spróbuj ponownie."; }
  }
  document.getElementById("show").onclick = () => activate("startPicker");
  document.getElementById("pick").onclick = () => activate("startPicker");
})();
