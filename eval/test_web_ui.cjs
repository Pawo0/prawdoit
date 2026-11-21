/** Frontend E2E with a controlled API. No models/backend required.
 * NODE_PATH=... CHROME_PATH=... SCREENSHOT_DIR=/tmp/prawdowid-web node eval/test_web_ui.cjs
 */
const {chromium} = require('playwright');
const {readFileSync, existsSync, mkdirSync} = require('node:fs');
const {resolve, extname} = require('node:path');
const assert = require('node:assert/strict');
const web = resolve(__dirname, '../web');
const fixture = {
 id: 'abc123', status: 'ok', summary: 'Sprawdzono informację.', input_excerpt: 'Przykładowe twierdzenie do testu.', created_at: '2026-11-21', channel: 'web', warnings: [], signals: [], security_events: [],
 claims: [{claim: 'Przykładowe twierdzenie do testu.', kind: 'fakt', verdict: 'falszywe', verdict_label: 'Fałszywe', explanation: 'Podana liczba jest niezgodna z materiałem źródłowym. W dokumencie wskazano 3%, a nie 8%.', strength_label: 'mocna', premises: [{label: 'Źródło', value: 'Dokument urzędowy', effect: '+'}], rules_fired: [], limitations: [], evidence: [{title: 'Dokument źródłowy', publisher: 'Wydawca testowy', domain: 'example.org', url: 'https://example.org', published_at: '2026-11-20', retrieved_at: '2026-11-21', fragment: 'Wartość wynosiła 3%.', stance: 'przeczy', tier: 1, similarity: .9, stance_score: .9, license: 'Dane testowe'}]}]
};
(async () => {
 const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
 const page = await browser.newPage({viewport: {width: 1440, height: 1000}, locale: 'pl-PL'});
 const errors = []; page.on('pageerror', e => errors.push(e.message));
 const types = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2'};
 let release, response = fixture, requests = [];
 await page.route('http://localhost:5500/**', async route => {
  const url = new URL(route.request().url());
  if (url.pathname === '/api/check' && route.request().method() === 'POST') {
   requests.push(route.request().postDataJSON()); await new Promise(r => release = r);
   return route.fulfill({json: response});
  }
  if (url.pathname.startsWith('/api/check/')) return route.fulfill({json: fixture});
  if (url.pathname === '/api/feedback') return route.fulfill({json: {ok: true}});
  let path = url.pathname === '/' ? '/index.html' : url.pathname.startsWith('/analiza/') || url.pathname === '/sprawdz' ? '/analiza.html' : url.pathname;
  if (!extname(path)) path += '.html';
  const file = resolve(web, '.' + path);
  if (!file.startsWith(web + '/') || !existsSync(file)) return route.fulfill({status: 404, body: 'Not found'});
  await route.fulfill({contentType: types[extname(file)] || 'application/json', body: readFileSync(file)});
 });
 const shot = async name => { if (process.env.SCREENSHOT_DIR) { mkdirSync(process.env.SCREENSHOT_DIR, {recursive: true}); await page.screenshot({path: resolve(process.env.SCREENSHOT_DIR, name + '.png'), fullPage: true}); }};
 await page.goto('http://localhost:5500/'); await page.locator('.hero-art').evaluate(img => img.decode()); await page.evaluate(() => document.fonts.ready);
 assert.ok((await page.locator('#go').boundingBox()).y < 850, 'Primary action must be visible immediately');
 await shot('home-desktop');
 for (const width of [768, 390, 320]) {
  await page.setViewportSize({width, height: 844});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No horizontal page overflow at ' + width);
  await shot('home-' + width);
 }
 await page.setViewportSize({width: 1440, height: 1000});
 await page.locator('#tab-url').click(); await page.locator('#q').fill('not a URL'); await page.locator('#go').click();
 assert.equal(await page.locator('#form-error').isVisible(), true); assert.equal(requests.length, 0);
 await page.locator('#q').fill('https://example.org'); await page.locator('#go').click();
 await page.locator('[role="progressbar"]').waitFor();
 assert.equal(requests.length, 1); assert.equal(requests[0].url, 'https://example.org');
 await shot('loading'); release();
 await page.locator('.claim-card').waitFor();
 assert.equal(await page.locator('.verdict-hero h2').innerText(), 'Fałsz');
 assert.ok((await page.locator('.verdict-hero').boundingBox()).y < 300, 'Verdict must be first, above the fold');
 assert.equal(await page.locator('.premises').isVisible(), false);
 assert.equal(await page.locator('.ev blockquote').isVisible(), true);
 await shot('result-desktop');
 await page.setViewportSize({width: 390, height: 844}); await shot('result-mobile');
 assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
 await page.locator('#again').click();
 await page.locator('#preview').click(); assert.equal(requests.length, 1); assert.equal(await page.locator('.demo-banner').isVisible(), true);
 // Preserve every verdict, including mixed passages and a safe abstention.
 const mixed = structuredClone(fixture);
 mixed.claims = [fixture.claims[0], {...fixture.claims[0], verdict: 'brak_dowodow', verdict_label: 'Brak wystarczających dowodów', explanation: 'Nie można rozstrzygnąć tej informacji. <script>window.injected=true</script>', premises: [], evidence: []}];
 await page.evaluate(data => renderResult(data, document.getElementById('out')), mixed);
 assert.equal(await page.locator('.claim-card').count(), 2); assert.equal(await page.locator('#out script').count(), 0);
 await page.locator('#again').click(); await page.locator('#tab-text').click(); await page.locator('#q').fill('Pytanie testowe');
 response = {status: 'doprecyzuj', status_message: 'Podaj datę wydarzenia.'};
 await page.locator('#go').click(); await page.locator('[role="progressbar"]').waitFor(); release();
 await page.locator('.result-error').waitFor(); assert.equal(await page.locator('.claim-card').count(), 0);
 // Direct links from the extension still render saved analyses.
 await page.goto('http://localhost:5500/analiza/abc123'); await page.locator('.verdict-hero').waitFor();
 assert.equal(await page.locator('.verdict-hero h2').innerText(), 'Fałsz');
 await page.setViewportSize({width: 320, height: 844});
 for (const [verdict, label] of Object.entries({falszywe: 'Fałszywe', potwierdzone: 'Potwierdzone', wprowadzajace_w_blad: 'Wprowadzające w błąd', brak_dowodow: 'Brak wystarczających dowodów', nie_podlega_weryfikacji: 'Nie podlega weryfikacji'})) {
  const data = structuredClone(fixture); data.claims[0].verdict = verdict; data.claims[0].verdict_label = label;
  await page.evaluate(data => renderResult(data, document.getElementById('out')), data);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Verdict fits at 320px: ' + verdict);
 }
 assert.deepEqual(errors, []);
 await browser.close(); console.log('PASS: responsive layout, URL validation, loading, API payload, verdict-first result, sources, preview, mixed claims, escaping, technical status and saved analysis.');
})().catch(e => { console.error(e); process.exit(1); });
