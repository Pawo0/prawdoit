/** Source catalogue paging with a controlled API; no models or credentials required.
 * NODE_PATH=... CHROME_PATH=... node eval/test_source_pagination.cjs
 */
const {chromium} = require('playwright');
const {readFileSync, existsSync, mkdirSync} = require('node:fs');
const {resolve, extname} = require('node:path');
const assert = require('node:assert/strict');
const web = resolve(__dirname, '../web');
const sources = Array.from({length: 53}, (_, i) => ({
 id: `source_${i}`, name: `Źródło ${i}`, publisher: `Wydawca ${i}`, url: `https://example.org/${i}`,
 tier: 1, category: 'official', method: 'rss', params: {}, topics: [], language: 'pl',
 enabled: i % 2 === 0, schedule_hours: 6, docs: i, problems: [],
 license: 'Warunki testowe', qualification: 'Źródło testowe',
 scope: i === 10 ? 'outside' : 'organiser_listed', scope_basis: `Podstawa ${i}`
}));
const stats = {documents: 53, domains: 1, publishers: 53, factchecked_claims: 0, by_type: {official: 53}, embed_model: 'test'};
const publishers = sources.map(s => ({publisher: s.publisher, tier_label: 'urzędowe', domains: ['example.org'], documents: 1, licenses: ['Test']}));
(async () => {
 const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
 try {
 const page = await browser.newPage({viewport: {width: 1440, height: 1000}, locale: 'pl-PL'});
 const errors = [], mutations = [];
 page.on('pageerror', e => errors.push(e.message));
 let current = sources, fail = false;
 await page.route('http://localhost:5500/**', async route => {
  const url = new URL(route.request().url());
  if (url.pathname === '/api/sources') return route.fulfill(fail ? {status: 503, json: {}} : {json: {stats, sources: current, publishers: current.length ? publishers : []}});
  if (url.pathname === '/api/admin/sources') return route.fulfill({json: {sources: current, scheduler: {}, index: {excluded_files: []}, vocab: {methods: ['rss'], topics: []}}});
  if (url.pathname === '/api/admin/runs') return route.fulfill({json: {runs: []}});
  if (url.pathname === '/api/admin/changes') return route.fulfill({json: {changes: []}});
  if (url.pathname.match(/^\/api\/admin\/sources\/source_\d+$/)) return route.fulfill({json: {source: sources.find(s => s.id === url.pathname.split('/').pop())}});
  if (url.pathname.startsWith('/api/admin/sources/')) { mutations.push(url.pathname); return route.fulfill({json: {message: 'OK'}}); }
  const path = extname(url.pathname) ? url.pathname : url.pathname + '.html';
  const file = resolve(web, '.' + path);
  if (!file.startsWith(web + '/') || !existsSync(file)) return route.fulfill({status: 404, body: 'Not found'});
  const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2'};
  return route.fulfill({contentType: types[extname(file)] || 'application/octet-stream', body: readFileSync(file)});
 });
 const nav = label => page.getByRole('navigation', {name: 'Paginacja: ' + label, exact: true});
 const shot = async name => { if (process.env.SCREENSHOT_DIR) { mkdirSync(process.env.SCREENSHOT_DIR, {recursive: true}); await page.screenshot({path: resolve(process.env.SCREENSHOT_DIR, name + '.png'), fullPage: true}); }};
 await page.goto('http://localhost:5500/zrodla');
 const reg = nav('Rejestr źródeł'), pubs = nav('Wydawcy w indeksie');
 await page.locator('#reg tbody tr').first().waitFor();
 assert.equal(await page.locator('#reg tbody tr').count(), 10);
 assert.equal(await reg.getByLabel('Poprzednia strona', {exact: true}).isDisabled(), true);
 const regBottom = nav('Rejestr źródeł (dół tabeli)');
 await reg.getByLabel('Strona 2', {exact: true}).click();
 assert.equal(await regBottom.locator('[aria-current="page"]').innerText(), '2');
 assert.match(await page.locator('#reg tbody tr').first().innerText(), /Źródło 10/);
 assert.match(await page.locator('#reg tbody tr').first().innerText(), /spoza listy organizatora/);
 assert.match(await reg.getByRole('status').innerText(), /11–20 z 53/);
 assert.match(await pubs.getByRole('status').innerText(), /1–10 z 53/);
 await reg.getByLabel('Ostatnia strona', {exact: true}).click();
 assert.equal(await page.locator('#reg tbody tr').count(), 3);
 assert.equal(await reg.getByLabel('Następna strona', {exact: true}).isDisabled(), true);
 await regBottom.getByRole('combobox').selectOption('25');
 assert.equal(await reg.getByRole('combobox').inputValue(), '25');
 assert.equal(await page.locator('#reg tbody tr').count(), 25);
 assert.match(await reg.getByRole('status').innerText(), /Strona 1 z 3/);
 await pubs.getByLabel('Następna strona', {exact: true}).click();
 assert.match(await page.locator('#t tbody tr').first().innerText(), /Wydawca 10/);
 await shot('sources-desktop');
 for (const width of [390, 320]) {
  await page.setViewportSize({width, height: 844});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await shot('sources-' + width);
 }
 current = [];
 await page.reload(); await page.getByText('0 pozycji · Strona 1 z 1').first().waitFor();
 assert.equal(await page.locator('#reg tbody').innerText(), 'Brak pozycji.');
 fail = true; await page.reload(); await page.getByRole('alert').waitFor(); fail = false; current = sources;
 await page.goto('http://localhost:5500/admin');
 await page.evaluate(() => sessionStorage.setItem('admtok', 'test'));
 await page.reload(); await page.locator('#src tbody tr').first().waitFor();
 const adm = nav('Źródła administratora');
 await adm.getByLabel('Następna strona', {exact: true}).click();
 await page.locator('[data-edit="source_10"]').click();
 await page.waitForFunction(() => document.getElementById('f-id').value === 'source_10');
 assert.equal(await page.locator('#f-id').inputValue(), 'source_10');
 await page.locator('[data-run="source_10"]').click();
 await page.locator('[data-toggle="source_10"]').uncheck();
 assert.deepEqual(mutations, ['/api/admin/sources/source_10/run', '/api/admin/sources/source_10/disable']);
 await page.evaluate(() => load());
 assert.match(await adm.getByRole('status').innerText(), /11–20 z 53/);
 assert.equal(await nav('Źródła administratora (dół tabeli)').locator('[aria-current="page"]').innerText(), '2');
 await adm.getByRole('combobox').selectOption('50');
 await adm.getByLabel('Ostatnia strona', {exact: true}).click();
 assert.equal(await page.locator('#src tbody tr').count(), 3);
 current = sources.slice(0, 10); await page.evaluate(() => load());
 assert.match(await adm.getByRole('status').innerText(), /1–10 z 10 · Strona 1 z 1/);
 await page.setViewportSize({width: 1440, height: 1000}); await shot('admin-desktop');
 for (const width of [390, 320]) {
  await page.setViewportSize({width, height: 844});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await shot('admin-' + width);
 }
 current = []; await page.evaluate(() => load());
 assert.equal(await page.locator('#src tbody').innerText(), 'Brak pozycji.');
 assert.equal(await adm.getByLabel('Następna strona', {exact: true}).isDisabled(), true);
 assert.deepEqual(errors, []);
 console.log('PASS: public/admin paging, limits, independent tables, refresh, row actions, empty/error states, mobile.');
 } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode = 1;});
