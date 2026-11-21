// Prawdowid — shared front-end helpers (no framework, no build step).
const VERDICT_ICON = {falszywe: "✕", wprowadzajace_w_blad: "!", potwierdzone: "✓", brak_dowodow: "?", nie_podlega_weryfikacji: "—"};
const STANCE = {przeczy: "Przeczy twierdzeniu", popiera: "Potwierdza twierdzenie", kontekst: "Kontekst / temat pokrewny", neutralne: "Neutralne"};
const TIER = {1: "Źródło pierwotne / urzędowe", 2: "Fact-checking / zweryfikowana baza", 3: "Media"};
const STATUS = {blad_techniczny: "Błąd techniczny — to nie jest ocena treści", doprecyzuj: "Potrzebujemy doprecyzowania", poza_zakresem: "Poza zakresem"};

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }
function fmtDate(s) { if (!s) return "brak daty"; const [y, m, d] = s.slice(0, 10).split("-"); return d ? `${d}.${m}.${y}` : s; }
function shortLic(l) { if (!l) return "—"; const x = l.split(/[;(]|\. /)[0].trim(); return x.length > 70 ? x.slice(0, 68) + "…" : x; }
function safeUrl(u) { try { const x = new URL(u); return ["http:", "https:"].includes(x.protocol) ? x.href : "#"; } catch { return "#"; } }

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
  let s = localStorage.getItem("prawdowid_session");
  if (!s) { s = crypto.randomUUID().replace(/-/g, "").slice(0, 16); localStorage.setItem("prawdowid_session", s); }
  return s;
}

async function runCheck(input, channel = "web") {
  const isUrl = /^https?:\/\/\S+$/.test(input.trim());
  const body = isUrl ? {url: input.trim(), channel, session: sessionId()} : {text: input, channel, session: sessionId()};
  const r = await fetch("/api/check", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body), signal: AbortSignal.timeout(45000)});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

function renderEvidence(e) {
  const fc = e.factcheck_verdict_raw ? `<div class="small">Sprawdzane twierdzenie: „${esc(e.factcheck_claim || e.title)}” — ocena źródła: <b>${esc(e.factcheck_verdict_raw)}</b>${e.same_claim === false ? " (Twoje twierdzenie jest jego zaprzeczeniem)" : ""}</div>` : "";
  return `<div class="ev">
    <div><span class="chip ${esc(e.stance)}">${STANCE[e.stance] || esc(e.stance)}</span><span class="chip tier${e.tier}">${TIER[e.tier] || ""}</span></div>
    <div class="evidence-title" style="margin-top:6px"><a href="${safeUrl(e.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(e.title)}</b></a></div>
    <div class="small muted">${esc(e.publisher)} · ${esc(e.domain)} · opublikowano ${fmtDate(e.published_at)}${e.age_days != null ? ` (${e.age_days} dni temu)` : ""}</div>
    ${fc}
    <blockquote><span class="small muted">Fragment źródła (cytat):</span><br>„${esc(e.fragment)}”</blockquote>
    <details><summary>Dane źródła i analizy</summary><div class="small muted">Podobieństwo do twierdzenia: ${(e.similarity * 100).toFixed(0)}% · ${e.stance !== "kontekst" ? `pewność oceny fragmentu: ${(e.stance_score * 100).toFixed(0)}% · ` : ""}pobrano ${fmtDate(e.retrieved_at)} · <span title="${esc(e.license)}">${esc(shortLic(e.license))}</span> (<a href="/zrodla">warunki</a>)</div></details>
  </div>`;
}

const REASON = {BRAK_MATERIALOW: "brak materiałów w katalogu źródeł", TYLKO_MATERIALY_POKREWNE: "są tylko materiały na pokrewny temat",
  ZRODLA_SPRZECZNE: "źródła są ze sobą sprzeczne", FACTCHECK_NIEWERYFIKOWALNE: "fact-checkerzy uznali to za nieweryfikowalne",
  NIEAKTUALNE_DOWODY: "dowody są nieaktualne"};
const CTX = {NIEAKTUALNE: "materiał nieaktualny / przedstawiony jako bieżący", MIESZANE: "część twierdzenia jest fałszywa i zmienia jego sens",
  WYBIORCZOSC_LUB_KONTEKST: "brakujący kontekst lub wybiórcze przedstawienie faktów"};
const KIND = {fakt: "twierdzenie o faktach", opinia: "opinia / ocena", prognoza: "przewidywanie", pytanie: "pytanie"};

function renderClaim(c, i, n) {
  const pe = p => p.effect === "+" ? `<span class="pe pe-plus" aria-label="wzmacnia">+</span>` : p.effect === "-" ? `<span class="pe pe-minus" aria-label="osłabia">−</span>` : `<span class="pe pe-0">•</span>`;
  const strength = !["brak_dowodow", "nie_podlega_weryfikacji"].includes(c.verdict)
    ? `<div style="margin-top:10px">Siła podstaw odpowiedzi: <b>${esc(c.strength_label)}</b></div>` : (c.verdict === "brak_dowodow" ? `<div style="margin-top:10px">Podstawa: <b>niewystarczająca</b>${c.reason_codes?.length ? " — " + c.reason_codes.map(r => REASON[r] || r).join("; ") : ""}</div>` : "");
  const shown = c.verdict === "brak_dowodow" && !c.conflicting ? c.evidence.slice(0, 3) : c.evidence;
  const evid = shown.length ? shown.map(renderEvidence).join("") + (shown.length < c.evidence.length ? `<p class="small muted">+${c.evidence.length - shown.length} dalszych materiałów pokrewnych pominięto.</p>` : "") : `<p class="muted">Brak materiałów źródłowych do pokazania.</p>`;
  return `<section class="card claim-card b-${c.verdict}" aria-label="Twierdzenie ${i + 1}"><div class="window-bar blue-bar"><span class="window-square" aria-hidden="true"></span><span class="bar-title">Wynik sprawdzenia${n > 1 ? ` · ${i + 1} z ${n}` : ""}</span><span class="window-lines" aria-hidden="true"></span></div><div class="claim-body">
    <div class="verdict-hero"><span class="verdict-icon" aria-hidden="true">${VERDICT_ICON[c.verdict] || "?"}</span><div><div class="eyebrow">${n > 1 ? `Informacja ${i + 1} z ${n}` : "Co mówią źródła"}</div><h2>${esc(c.verdict === "falszywe" ? "Fałsz" : c.verdict_label)}</h2></div></div>
    <p class="verdict-explanation">${esc(c.explanation)}</p>
    <div class="claim-q"><small>Sprawdzana informacja</small>„${esc(c.claim)}”</div>
    ${c.missing_context ? `<div class="warn"><b>Brakujący kontekst:</b> ${esc(c.missing_context)}</div>` : ""}
    ${c.context_type && !c.missing_context ? `<div class="warn"><b>Rodzaj problemu:</b> ${esc(CTX[c.context_type] || c.context_type)}</div>` : ""}
    ${c.what_unknown ? `<div class="info"><b>Czego nie udało się ustalić:</b> ${esc(c.what_unknown)}${c.would_settle ? `<br><b>Co mogłoby to rozstrzygnąć:</b> ${esc(c.would_settle)}.` : ""}</div>` : ""}
    ${c.premises.length || strength ? `<details><summary>Dlaczego taki wynik?</summary>${strength}<ul class="premises">${c.premises.map(p => `<li>${pe(p)} <b>${esc(p.label)}:</b> ${esc(p.value)}</li>`).join("")}</ul>
      <div class="small muted">Reguły: ${c.rules_fired.map(esc).join(", ") || "—"} · <a href="/metodologia#reguly">opis reguł</a></div></details>` : ""}
    <h3 class="evidence-heading">Źródła i dowody</h3>
    <p class="small muted">Dosłowne fragmenty źródeł — oddzielone od naszej interpretacji powyżej.</p>
    ${evid}
    ${c.limitations.length ? `<details><summary>Ograniczenia tej odpowiedzi</summary><ul>${c.limitations.map(l => `<li>${esc(l)}</li>`).join("")}</ul></details>` : ""}
  </div></section>`;
}

function renderSignals(sig) {
  if (!sig?.length) return "";
  return `<section class="card"><h2 style="margin-top:0">Sprawdź sam — metoda SPRAWDŹ (NASK)</h2>
    <p class="small muted">Wskazówki edukacyjne na podstawie metody z kampanii NASK „Sprawdź, zanim udostępnisz”. <b>Nie wpływają na ocenę</b> — ta wynika wyłącznie ze źródeł.</p>
    <ul class="premises">${sig.map(s => `<li><span class="pe ${s.flagged ? "pe-minus" : "pe-0"}" style="width:28px">${esc(s.letter)}</span><b>${esc(s.name)}:</b> ${esc(s.note)}${s.hits?.length ? ` <span class="small muted">(np. ${s.hits.map(h => "„" + esc(h) + "”").join(", ")})</span>` : ""}</li>`).join("")}</ul>
    <p class="small">Więcej: <a href="https://www.nask.pl/dezinfo" target="_blank" rel="noopener">nask.pl/dezinfo</a> · Zgłoś dezinformację: <a href="https://zglos-dezinformacje.nask.pl" target="_blank" rel="noopener">zglos-dezinformacje.nask.pl</a> · Podejrzany SMS prześlij na numer <b>8080</b> (CERT Polska).</p></section>`;
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

function renderResult(res, el) {
  if (res.status !== "ok") {
    el.innerHTML = `<section class="window result-error" role="status"><h2>${esc(STATUS[res.status] || res.status)}</h2><p>${esc(res.status_message)}</p></section>`;
    return;
  }
  const t = res.timings_ms?.total_ms;
  const priority = {falszywe: 0, wprowadzajace_w_blad: 1, brak_dowodow: 2, nie_podlega_weryfikacji: 3, potwierdzone: 4};
  const orderedClaims = [...res.claims].sort((a, b) => (priority[a.verdict] ?? 2) - (priority[b.verdict] ?? 2));
  el.innerHTML = `
    ${res.demo ? '<div class="demo-banner"><b>Przykładowy wynik.</b> Dane są fikcyjne — to podgląd wyglądu, bez sprawdzania przez serwer.</div>' : ""}
    ${res.warnings.map(w => `<div class="warn">${esc(w)}</div>`).join("")}
    ${orderedClaims.map((c, i) => renderClaim(c, i, orderedClaims.length)).join("")}
    ${res.case_status ? `<div class="info"><b>Pętla informacji:</b> ${esc(res.case_status)}</div>` : ""}
    ${res.signals?.length ? `<details class="card result-secondary"><summary>Jak samodzielnie rozpoznawać manipulację?</summary>${renderSignals(res.signals)}</details>` : ""}
    <details class="card result-secondary"><summary>Zgłoś błąd w wyniku</summary>
      <p class="small">Jeśli uważasz, że wynik jest błędny lub źródło zostało źle zrozumiane — daj nam znać. Zgłoszenie trafi do analityka, a poprawki publikujemy w rejestrze korekt.</p>
      <form id="fb" class="row"><input id="fbm" maxlength="1000" required placeholder="Co jest nie tak?" style="flex:1;font:inherit;padding:10px;border-radius:10px;border:1px solid #d0d5dd"><button>Zgłoś błąd</button></form>
      <p id="fbok" class="small" role="status" hidden>Dziękujemy — zgłoszenie zapisano.</p></details>
    <p class="small muted">Odpowiedź przygotował automatyczny system wykorzystujący modele sztucznej inteligencji do wyszukiwania i porównywania źródeł. Ocena wynika z jawnych reguł, nie z „opinii” modelu.</p>
    <details class="card result-secondary"><summary>Przebieg sprawdzenia i dane techniczne</summary>
      <p class="result-meta">Sprawdzana treść: ${esc(res.input_excerpt)}<br>ID: ${esc(res.id)}${t ? ` · Czas: ${(t / 1000).toFixed(1)} s` : ""}</p>
      <table><tr><th>Czas utworzenia</th><td>${esc(res.created_at)}</td></tr>
      <tr><th>Kanał</th><td>${esc(res.channel)}</td></tr>
      <tr><th>Czasy etapów [ms]</th><td>${Object.entries(res.timings_ms || {}).map(([k, v]) => `${esc(k)}: ${Math.round(v)}`).join(" · ")}</td></tr>
      <tr><th>Modele</th><td>embedding: ${esc(res.engine?.embed_model)} · NLI: ${esc(res.engine?.nli_model)} · LLM: ${esc(res.engine?.llm || "nieużywany (wyjaśnienia z szablonów)")}</td></tr>
      <tr><th>Korpus</th><td>${esc(res.engine?.corpus_documents)} dokumentów (wczytano ${esc(res.engine?.corpus_loaded_at)})</td></tr>
      <tr><th>Wersja reguł / przetwarzanie</th><td>${esc(res.engine?.rules_version)} · ${esc(res.engine?.processing)}</td></tr>
      <tr><th>Zdarzenia bezpieczeństwa</th><td>${res.security_events.length ? res.security_events.map(e => esc(e.kind + " — " + e.where)).join("<br>") : "brak"}</td></tr></table>
      <p class="small"><button type="button" class="secondary" id="delsess">Usuń historię moich sprawdzeń</button></p>
    </details>`;
  el.querySelector("#fb")?.addEventListener("submit", async e => { e.preventDefault();
    if (res.demo) { el.querySelector("#fbok").hidden = false; el.querySelector("#fbok").textContent = "To podgląd demonstracyjny. Zgłoszenie nie zostało wysłane."; return; }
    const response = await fetch("/api/feedback", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({check_id: res.id, message: el.querySelector("#fbm").value})});
    if (!response.ok) { el.querySelector("#fbok").hidden = false; el.querySelector("#fbok").textContent = "Nie udało się zapisać zgłoszenia. Spróbuj ponownie."; return; }
    el.querySelector("#fb").hidden = true; el.querySelector("#fbok").hidden = false; });
  el.querySelector("#delsess")?.addEventListener("click", async () => {
    if (res.demo) { alert("Podgląd nie zapisuje historii na serwerze."); return; }
    const r = await fetch("/api/session/" + sessionId(), {method: "DELETE"}); const d = await r.json();
    alert(`Usunięto ${d.deleted_checks} zapisanych sprawdzeń z tej przeglądarki.`); });
}

document.addEventListener("DOMContentLoaded", chrome_);
