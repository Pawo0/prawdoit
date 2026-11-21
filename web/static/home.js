// Main page: the verification flow stays in one place, including on a plain static server.
(() => {
  const form = document.getElementById('f'), q = document.getElementById('q');
  const results = document.getElementById('results'), out = document.getElementById('out');
  const submit = document.getElementById('go'), error = document.getElementById('form-error');
  const copy = document.getElementById('copy-link'), copied = document.getElementById('copied');
  let mode = 'text', busy = false;
  function hideLinks() { document.getElementById('result-link').hidden = true; copy.hidden = true; copied.textContent = ''; }
  function setMode(next) {
    mode = next;
    for (const key of ['text', 'url']) {
      const button = document.getElementById('tab-' + key);
      button.classList.toggle('active', next === key); button.setAttribute('aria-pressed', String(next === key));
    }
    document.getElementById('q-label').textContent = next === 'url' ? 'Wklej adres strony z informacją' : 'Wklej tekst, który chcesz sprawdzić';
    q.placeholder = next === 'url' ? 'https://…' : 'Wklej wiadomość lub fragment posta…';
    q.inputMode = next === 'url' ? 'url' : 'text'; error.hidden = true; q.focus();
  }
  document.getElementById('tab-text').onclick = () => setMode('text');
  document.getElementById('tab-url').onclick = () => setMode('url');
  function showResults() {
    results.hidden = false; document.body.classList.add('has-result');
    results.focus({preventScroll: true}); results.scrollIntoView({block: 'start', behavior: 'instant'});
  }
  form.addEventListener('submit', async e => {
    e.preventDefault(); if (busy) return;
    const text = q.value.trim(); if (!text) { q.focus(); return; }
    if (mode === 'url' && !/^https?:\/\/\S+$/.test(text)) { error.textContent = 'Wklej pełny adres zaczynający się od https:// lub http://.'; error.hidden = false; q.focus(); return; }
    busy = true; submit.disabled = true; error.hidden = true;
    document.getElementById('again').disabled = true;
    hideLinks();
    out.setAttribute('aria-busy', 'true');
    // "Sprawdzanie informacji" window (app.js): live stage from the async job, elapsed time and "Anuluj".
    const wait = openWait({inline: out});
    showResults();
    try {
      const res = await checkWithProgress(text, new URLSearchParams(location.search).get('ch') || 'web', wait); renderResult(res, out);
      if (res.status === 'ok' && res.id) { const link = document.getElementById('result-link'); link.href = '/analiza/' + encodeURIComponent(res.id); link.hidden = false; copy.hidden = false; }
    }
    catch (err) { renderTechError(out, err); }  // technical error or "Anuluj" — never shown as an assessment of the content
    finally { wait.close(); busy = false; submit.disabled = false; document.getElementById('again').disabled = false; out.setAttribute('aria-busy', 'false'); results.focus({preventScroll: true}); }
  });
  copy.onclick = async () => {
    const url = document.getElementById('result-link').href;
    try { await navigator.clipboard.writeText(url); copied.textContent = 'Skopiowano link.'; }
    catch { copied.textContent = url; }
  };
  document.getElementById('again').onclick = () => {
    if (busy) return;
    results.hidden = true; document.body.classList.remove('has-result'); q.focus();
  };
  document.getElementById('preview').onclick = () => {
    hideLinks();
    const evidence = {title: 'Przykładowy komunikat źródłowy', publisher: 'Instytucja demonstracyjna', domain: 'example.org', url: 'https://example.org', published_at: '2026-11-20', retrieved_at: '2026-11-21', fragment: 'Wartość w omawianym okresie wynosiła 3%, a nie 8%. To fikcyjny cytat na potrzeby podglądu.', stance: 'przeczy', tier: 1, similarity: .9, stance_score: .95, license: 'Fikcyjne dane demonstracyjne'};
    renderResult({demo: true, status: 'ok', id: 'podglad', created_at: '2026-11-21', channel: 'podglad', input_excerpt: 'Przykładowa wiadomość podaje wartość 8%.', warnings: [], signals: [], security_events: [], claims: [{claim: 'Przykładowa wiadomość podaje wartość 8%.', kind: 'fakt', verdict: 'falszywe', verdict_label: 'Fałszywe', explanation: 'Podana liczba jest niezgodna z materiałem źródłowym. W dokumencie wskazano 3%, a nie 8%.', strength_label: 'mocna', premises: [], rules_fired: [], evidence: [evidence], limitations: ['To wyłącznie podgląd. Nie oceniono rzeczywistej informacji.']}]}, out);
    showResults();
  };
})();
