/** Isolated extension UI regression test (mock transport; no models/server required).
 * npm install --no-save playwright
 * node eval/test_extension_ui.cjs
 * Optional: CHROME_PATH=/path/to/chrome, SCREENSHOT_DIR=/tmp/prawdowid-ui
 */
const {chromium} = require('playwright');
const {readFileSync, mkdirSync} = require('node:fs');
const {resolve} = require('node:path');
const assert = require('node:assert/strict');
const root = resolve(__dirname, '..');
const script = readFileSync(resolve(root, 'extension/content.js'), 'utf8');
const result = {
  id: 'test-result', status: 'ok', summary: 'Nie ma wystarczających dowodów, by rozstrzygnąć to twierdzenie.', warnings: ['Katalog źródeł ma ograniczony zakres.'],
  claims: [{claim: 'W Suwałkach otwarto pierwszą w Polsce fabrykę baterii grafenowych.', verdict: 'brak_dowodow', verdict_label: 'Brak wystarczających dowodów', explanation: 'Dostępne materiały nie pozwalają potwierdzić daty otwarcia ani miejsca inwestycji.', what_unknown: 'Czy inwestycja została uruchomiona.', would_settle: 'Komunikat inwestora lub urzędu miasta.', limitations: [], evidence: []}]
};
(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1280, height: 900}, locale: 'pl-PL'});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('http://localhost:8000/**', route => route.fulfill({contentType: 'text/html', body: readFileSync(resolve(root, 'web/demo/feed.html'), 'utf8')}));
  await page.goto('http://localhost:8000/demo/feed.html');
  await page.evaluate(() => {
    window.calls = []; window.replies = []; window.fail = false;
    window.chrome = {runtime: {
      getURL: () => 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30"><path d="M5 5h20v20H5z" fill="white"/></svg>'),
      onMessage: {addListener: fn => window.extensionMessage = fn},
      sendMessage: (msg, cb) => {
        window.calls.push(msg);
        if (msg.type === 'settings') return cb({ok: true, data: {autoScan: false, noticeSeen: true}});
        if (msg.type === 'quick') return; // Deliberately stalled: full result must not wait for this.
        if (msg.type === 'check') return window.replies.push(cb);
        cb({ok: true});
      }
    }, storage: {onChanged: {addListener() {}}}};
  });
  await page.addScriptTag({content: script});
  const sheet = page.locator('prawdowid-ui .sheet');
  const start = () => page.evaluate(() => window.extensionMessage({type: 'startPicker'}));
  const pick = async () => { await start(); await page.locator('[data-testid="tweetText"]').first().click(); };
  const reply = data => page.evaluate(data => window.replies.shift()({ok: true, data}), data);
  const screenshot = async name => {
    if (process.env.SCREENSHOT_DIR) { mkdirSync(process.env.SCREENSHOT_DIR, {recursive: true}); await page.screenshot({path: resolve(process.env.SCREENSHOT_DIR, name + '.png')}); }
  };
  await pick();
  assert.equal(await page.locator('prawdowid-ui .pbar').count(), 0);
  assert.equal(await sheet.getAttribute('aria-busy'), 'true');
  assert.equal(await sheet.locator('[role="progressbar"]').count(), 1);
  assert.equal(await page.evaluate(() => window.calls.filter(m => m.type === 'check').length), 1);
  await screenshot('loading-desktop');
  await reply(result);
  await sheet.locator('[data-s="full"]').waitFor();
  assert.equal(await sheet.getAttribute('aria-busy'), 'false');
  assert.match(await sheet.innerText(), /Brak wystarczających dowodów/);
  await screenshot('result-desktop');
  await sheet.locator('[data-s="full"]').click();
  assert.equal(await page.evaluate(() => window.calls.at(-1).id), 'test-result');
  await page.keyboard.press('Escape');
  assert.equal(await sheet.count(), 0);
  // Dismissing a pending check must not resurrect it when the server replies.
  await pick(); await page.keyboard.press('Escape'); await reply(result);
  assert.equal(await sheet.count(), 0);
  // An older reply must not overwrite a newer selected fragment.
  await pick(); await pick(); await reply(result);
  assert.equal(await sheet.getAttribute('aria-busy'), 'true');
  await page.evaluate(() => window.replies.shift()({ok: false, error: 'HTTP 500'}));
  await sheet.locator('[data-s="retry"]').waitFor();
  assert.match(await sheet.innerText(), /błąd techniczny/);
  await sheet.locator('[data-s="retry"]').click();
  assert.equal(await sheet.getAttribute('aria-busy'), 'true');
  const withEvidence = structuredClone(result);
  withEvidence.summary = 'Przykładowy wynik testu interfejsu — nie jest rzeczywistą weryfikacją.';
  withEvidence.claims[0] = {...withEvidence.claims[0], verdict: 'falszywe', verdict_label: 'Fałszywe', strength_label: 'mocna', explanation: 'Przykładowe uzasadnienie wyniku na potrzeby testu interfejsu.', what_unknown: null, would_settle: null, evidence: [{stance: 'przeczy', publisher: 'Źródło testowe', published_at: '2026-11-20', title: 'Tytuł materiału źródłowego', url: 'https://example.org/dowod', fragment: 'Dosłowny fragment materiału. <script>window.pwned=true</script>'}]};
  await reply(withEvidence);
  assert.match(await sheet.locator('.source').innerText(), /20.11.2026/);
  assert.equal(await sheet.locator('script').count(), 0);
  assert.equal(await sheet.locator('.source a').getAttribute('href'), 'https://example.org/dowod');
  await screenshot('evidence-desktop');
  // Small viewports: window and footer stay on-screen; the body scrolls.
  for (const width of [390, 320]) {
    await page.setViewportSize({width, height: 700});
    const box = await sheet.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= width, 'Window must fit horizontally');
    assert.ok(box.y >= 0 && box.y + box.height <= 700, 'Window must fit vertically');
    assert.equal(await sheet.evaluate(el => el.scrollWidth > el.clientWidth), false);
    await screenshot('evidence-mobile-' + width);
  }
  await page.keyboard.press('Escape');
  // Technical API statuses stay distinct from factual verdicts.
  await pick(); await reply({status: 'doprecyzuj', status_message: 'Podaj datę wydarzenia.'});
  assert.match(await sheet.innerText(), /Doprecyzuj pytanie/);
  assert.equal(await sheet.locator('.claim-result').count(), 0);
  await sheet.locator('[data-s="pick"]').click();
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('prawdowid-ui .pbar').count(), 0);
  // Demonstration results must be clearly labelled and never link to a nonexistent backend analysis.
  await pick();
  await reply({...result, demo: true, warnings: ['TRYB DEMONSTRACYJNY — fikcyjny wynik i źródła.']});
  assert.match(await sheet.getAttribute('aria-label'), /Demo/);
  assert.match(await sheet.innerText(), /Dane testowe/);
  assert.equal(await sheet.locator('[data-s="full"]').count(), 0);
  await sheet.locator('[data-s="pick"]').click();
  assert.equal(await sheet.count(), 0);
  await page.keyboard.press('Escape');
  // Popup switch saves the preference and displays its saved value after reopening.
  await page.route('http://localhost:8000/popup.html', route => route.fulfill({contentType: 'text/html', body: readFileSync(resolve(root, 'extension/popup.html'), 'utf8').replace('<script src="popup.js"></script>', '')}));
  await page.goto('http://localhost:8000/popup.html');
  await page.evaluate(() => {
    window.savedSettings = {mockMode: false, autoScan: true, mode: 'zaslon', apiBase: 'http://localhost:8000'};
    window.chrome = {
      tabs: {query: async () => [{id: 1}]},
      runtime: {sendMessage: (msg, cb) => {
        if (msg.type === 'settings') return cb({ok: true, data: window.savedSettings});
        if (msg.type === 'setSettings') { Object.assign(window.savedSettings, msg.data); return cb({ok: true}); }
        cb({ok: true, data: {scanned: 0, flagged: 0}});
      }}
    };
  });
  const popupScript = readFileSync(resolve(root, 'extension/popup.js'), 'utf8');
  await page.addScriptTag({content: popupScript});
  await page.locator('#mock').check();
  assert.equal(await page.evaluate(() => window.savedSettings.mockMode), true);
  assert.match(await page.locator('#mock-status').innerText(), /Włączony/);
  await screenshot('mock-popup');
  // Re-run popup setup with the saved settings, as on reopening the extension popup.
  await page.addScriptTag({content: `(() => { ${popupScript} })()`});
  assert.equal(await page.locator('#mock').isChecked(), true);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('PASS: immediate checking, loading, result, evidence, errors/retry, stale replies, keyboard, mobile layout.');
})().catch(e => { console.error(e); process.exit(1); });
