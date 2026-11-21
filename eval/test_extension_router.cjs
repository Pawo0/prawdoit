/** Extension as a ROUTER client (mock transport; no models/server required).
 * Covers: candidate is never shown; match badge names fact-checker, rating, date and link; background checks are
 * capped at 3 per page, run one at a time in priority order, and earn a badge only for a decisive verdict that cites
 * a source; overlay is off by default (opt-in); stage messages from job polling; batching, deduplication, back-off
 * on 429; only text leaves the page; older servers (no `state`) never trigger background checks.
 *   npm install --no-save playwright
 *   node eval/test_extension_router.cjs
 * Optional: CHROME_PATH=/path/to/chrome, SCREENSHOT_DIR=/tmp/prawdowid-ui
 */
const {chromium} = require('playwright');
const {readFileSync, mkdirSync} = require('node:fs');
const {resolve} = require('node:path');
const assert = require('node:assert/strict');
const root = resolve(__dirname, '..');
const script = readFileSync(resolve(root, 'extension/content.js'), 'utf8');
const feed = readFileSync(resolve(root, 'web/demo/feed.html'), 'utf8');

const match = (publisher, verdict_raw, published_at, url, level = 'wysokie') => ({state: 'match', level, risk: 0.9, reasons: ['RATED_CLAIM_MATCH'],
  match: {claim: 'Twierdzenie ocenione przez redakcję', publisher, verdict: 'false', verdict_raw, url, title: 'Tytuł publikacji', published_at, similarity: 0.93, sentence: ''}});
const candidate = (priority, extra = {}) => ({state: 'candidate', level: 'brak', risk: 0, priority, reasons: ['NEAR_MISS'], ...extra});
const claim = (verdict, evidence = [], extra = {}) => ({claim: 'Sprawdzone twierdzenie', verdict, verdict_label: verdict, strength_label: 'mocna', explanation: 'Uzasadnienie.',
  limitations: [], evidence, main_evidence: evidence.length ? 0 : null, ...extra});
const source = {stance: 'przeczy', publisher: 'FakeNews.pl', title: 'Nie ma cudownego leku na cukrzycę', published_at: '2025-05-14', url: 'https://fakenews.pl/zdrowie/lek-na-cukrzyce/', fragment: 'Dosłowny fragment.'};

// Ten posts of web/demo/feed.html, by a distinctive substring → what tier 1 (router) answers.
const QUICK = [
  ['Ukraina w ogóle nie płaci Orlenowi', match('Demagog', 'Fałsz', '2026-03-02', 'https://demagog.org.pl/fake_news/orlen-ukraina/')],
  ['Chorwacki lekarz', candidate(0.9)],
  ['Niemieckie służby', candidate(0.8)],
  ['490 miliardów', candidate(0.7)],
  ['robota, który ma rodzić', candidate(0.65)],
  ['mikrochipy', candidate(0.3, {match: {claim: 'Najbliższe ocenione twierdzenie', publisher: 'Demagog', verdict: 'false', verdict_raw: 'Fałsz', url: 'https://demagog.org.pl/x/', published_at: '2021-01-05'},
    conflict: {claim: 'Twierdzenie ocenione jako prawda', publisher: 'Stowarzyszenie Pravda', verdict_raw: 'Prawda', url: 'https://pravda.org.pl/y/', published_at: '2021-02-01', similarity: 0.9}})],
  ['Wilk rzucił się', match('Stowarzyszenie Pravda', 'Manipulacja', '2024-08-19', 'https://pravda.org.pl/wilk-toskania/', 'srednie')],
];
// What the background (auto) check answers for the candidates that get one.
const CHECK = [
  ['Chorwacki lekarz', {claims: [claim('falszywe', [source])]}], // decisive + cited source → badge
  ['Niemieckie służby', {claims: [claim('brak_dowodow', [{...source, stance: 'kontekst'}])]}], // related sources but no verdict → nothing
  ['490 miliardów', {claims: [claim('falszywe', [])]}], // decisive but no source → nothing
  ['robota, który ma rodzić', {claims: [claim('falszywe', [source])]}], // never requested: budget is 3
  ['Ukraina w ogóle nie płaci Orlenowi', {claims: [claim('falszywe', [{...source, publisher: 'Demagog'}])]}], // manual check from the match badge
];

(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1280, height: 2400}, locale: 'pl-PL'}); // tall: every post is on screen
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('http://localhost:8000/**', route => route.fulfill({contentType: 'text/html', body: feed}));
  await page.route('**/fonts/GeistPixel-Square.woff2', route => route.fulfill({contentType: 'font/woff2', body: readFileSync(resolve(root, 'extension/fonts/GeistPixel-Square.woff2'))}));
  const screenshot = async name => {
    if (process.env.SCREENSHOT_DIR) { mkdirSync(process.env.SCREENSHOT_DIR, {recursive: true}); await page.screenshot({path: resolve(process.env.SCREENSHOT_DIR, name + '.png')}); }
  };

  // Loads the demo feed with a scripted background page. cfg: {settings, quick, check, router, quickFail}
  async function load(cfg) {
    await page.goto('http://localhost:8000/demo/feed.html');
    await page.evaluate(cfg => {
      Object.assign(window, {calls: [], jobs: {}, jobSeq: 0, autoActive: 0, autoPeak: 0, quickFail: cfg.quickFail || 0, holdManual: false});
      window.chrome = {runtime: {
        getURL: path => 'http://localhost:8000/' + path,
        onMessage: {addListener: fn => window.extensionMessage = fn},
        sendMessage: (msg, cb) => {
          window.calls.push({...JSON.parse(JSON.stringify(msg)), at: Date.now()});
          if (msg.type === 'settings') return cb({ok: true, data: cfg.settings});
          if (msg.type === 'quick') {
            if (window.quickFail-- > 0) return setTimeout(() => cb({ok: false, error: 'HTTP 429', status: 429, retryAfter: 2}), 20);
            const data = msg.items.map(it => {
              const hit = cfg.quick.find(([part]) => it.text.includes(part));
              const r = {id: it.id, level: 'brak', risk: 0, match: null, state: 'none', priority: 0, reasons: [], ...(hit ? hit[1] : {})};
              if (!cfg.router) { delete r.state; delete r.priority; delete r.reasons; delete r.conflict; } // server before the router
              return r;
            });
            return setTimeout(() => cb({ok: true, data}), 30);
          }
          if (msg.type === 'check') {
            const id = 'job' + (++window.jobSeq), hit = cfg.check.find(([part]) => msg.text.includes(part));
            window.jobs[id] = {polls: 0, mode: msg.mode, result: {id: 'res-' + id, status: 'ok', mode: msg.mode, warnings: [], claims: [], ...(hit ? hit[1] : {})}};
            if (msg.mode === 'auto') window.autoPeak = Math.max(window.autoPeak, ++window.autoActive);
            return setTimeout(() => cb({ok: true, job: id}), 10);
          }
          if (msg.type === 'job') {
            const j = window.jobs[msg.id];
            if (++j.polls < 2 || (j.mode !== 'auto' && window.holdManual)) return cb({ok: true, data: {state: 'running', stage: 'baza', stage_label: 'Szukam w bazie sprawdzonych informacji…'}});
            if (j.mode === 'auto' && !j.done) { j.done = true; window.autoActive--; }
            return cb({ok: true, data: {state: 'done', stage: 'gotowe', result: j.result}});
          }
          cb({ok: true});
        }
      }, storage: {onChanged: {addListener() {}}}};
    }, cfg);
    await page.addScriptTag({content: script});
  }
  const calls = type => page.evaluate(type => window.calls.filter(m => m.type === type), type);
  const post = part => page.locator('[role="article"], article[data-testid="tweet"]').filter({hasText: part});
  const tag = part => post(part).locator('prawdowid-ui');
  const uiText = () => page.evaluate(() => [...document.querySelectorAll('prawdowid-ui')].map(h => [...h.shadowRoot.children].filter(e => e.tagName !== 'STYLE')
    .map(e => e.innerText + ' ' + [...e.querySelectorAll('[title]'), e].map(x => x.title || '').join(' ')).join(' ')).join(' '));
  const autoDone = n => page.waitForFunction(n => window.calls.filter(m => m.type === 'check' && m.mode === 'auto').length === n && window.autoActive === 0, n, {timeout: 20000});
  const defaults = {autoScan: true, autoVerify: true, noticeSeen: true, mode: 'oznacz', mockMode: false, disabledSites: []};

  // ---------------------------------------------------------------- 1. router server, default settings
  await load({settings: defaults, quick: QUICK, check: CHECK, router: true});
  await tag('Ukraina w ogóle nie płaci Orlenowi').locator('.badge').waitFor();
  // only text leaves the page, in one batch of at most 16 items
  const quick = await calls('quick');
  assert.equal(quick.length, 1, 'ten visible posts fit one batch');
  assert.ok(quick[0].items.length <= 16 && quick[0].items.length === 10);
  for (const it of quick[0].items) assert.deepEqual(Object.keys(it).sort(), ['id', 'text']);
  assert.doesNotMatch(JSON.stringify(quick), /localhost|demo\/feed|http/);
  // match → badge at once: fact-checker, rating, date, link, and a button that runs the full check
  const badge = tag('Ukraina w ogóle nie płaci Orlenowi').locator('.badge');
  assert.match(await badge.innerText(), /Demagog/);
  assert.match(await badge.innerText(), /„Fałsz”/);
  assert.match(await badge.innerText(), /02\.03\.2026/);
  assert.equal(await badge.locator('a').getAttribute('href'), 'https://demagog.org.pl/fake_news/orlen-ukraina/');
  assert.equal(await badge.locator('a').getAttribute('target'), '_blank');
  assert.match(await badge.getAttribute('title'), /dopasowanie treści, a nie pełna weryfikacja/);
  assert.equal(await badge.locator('button[data-a="analiza"]').count(), 1);
  const second = tag('Wilk rzucił się').locator('.badge');
  assert.match(await second.innerText(), /Stowarzyszenie Pravda.*„Manipulacja”.*19\.08\.2024/s);
  // overlay is opt-in: a strong match is NOT covered by default
  assert.equal(await page.locator('prawdowid-ui .ov').count(), 0);
  // candidates and "none" show nothing — also the candidate whose answer carries a nearest claim and a conflict
  for (const part of ['Chorwacki lekarz', 'Niemieckie służby', '490 miliardów', 'robota, który ma rodzić', 'mikrochipy', 'Piękna pogoda', 'Moim zdaniem', 'świetny mecz'])
    assert.equal(await tag(part).count(), 0, `nothing may be shown yet for: ${part}`);
  await screenshot('router-match-badges');

  // background checks: 3 at most, best priority first, one at a time
  await autoDone(3);
  await tag('Chorwacki lekarz').locator('.badge').waitFor();
  await page.waitForTimeout(1200); // a fourth check would have started by now
  const auto = (await calls('check')).filter(m => m.mode === 'auto');
  assert.equal(auto.length, 3, 'background checks are capped at 3 per page');
  assert.deepEqual(auto.map(m => QUICK.find(([part]) => m.text.includes(part))[0]), ['Chorwacki lekarz', 'Niemieckie służby', '490 miliardów']);
  assert.equal(await page.evaluate(() => window.autoPeak), 1, 'one background check at a time');
  for (const m of auto) assert.deepEqual(Object.keys(m).sort(), ['at', 'mode', 'text', 'type']);
  // a badge only for a decisive verdict with a cited source
  const verified = tag('Chorwacki lekarz').locator('.badge');
  assert.match(await verified.innerText(), /Źródła przeczą tej informacji: FakeNews\.pl, 14\.05\.2025/);
  assert.equal(await verified.locator('a').getAttribute('href'), 'https://fakenews.pl/zdrowie/lek-na-cukrzyce/');
  assert.equal(await tag('Niemieckie służby').count(), 0, 'no evidence → nothing shown');
  assert.equal(await tag('490 miliardów').count(), 0, 'verdict without a source → nothing shown');
  assert.equal(await tag('robota, który ma rodzić').count(), 0, 'beyond the budget → not checked, nothing shown');
  assert.equal(await tag('mikrochipy').count(), 0);
  assert.equal(await page.locator('prawdowid-ui .badge').count(), 3);
  assert.equal(await page.locator('prawdowid-ui .fab .n').innerText(), '3');
  // wording: no "podejrzane", no percentage, no risk score anywhere in the UI
  const visible = await uiText();
  assert.doesNotMatch(visible, /podejrzan|%|ryzyk|prawdopodob/i);
  await screenshot('router-after-background-checks');

  // click on a match badge → the full (manual) check as a job; the window shows the server's stage while polling
  await page.evaluate(() => { window.holdManual = true; });
  await badge.locator('button[data-a="analiza"]').click();
  const sheet = page.locator('prawdowid-ui .sheet');
  await page.waitForFunction(() => window.calls.some(m => m.type === 'job' && window.jobs[m.id].mode === 'manual'));
  const manual = (await calls('check')).filter(m => m.mode === 'manual');
  assert.equal(manual.length, 1);
  assert.match(manual[0].text, /Ukraina w ogóle nie płaci Orlenowi/);
  await page.waitForFunction(() => /Szukam w bazie sprawdzonych informacji/.test(document.querySelector('prawdowid-ui:not([data-kind])').shadowRoot.querySelector('[data-stage]')?.textContent || ''));
  assert.equal(await sheet.getAttribute('aria-busy'), 'true');
  await screenshot('router-stage-message');
  await page.evaluate(() => { window.holdManual = false; });
  await sheet.locator('[data-s="full"]').waitFor();
  assert.match(await sheet.innerText(), /Fałsz/);
  assert.ok((await calls('job')).length >= 2, 'the result arrived through polling');
  await page.keyboard.press('Escape');

  // deduplication and caching: new DOM with a known text is answered from the page cache; nothing is re-sent
  await page.evaluate(() => {
    const copy = document.querySelector('[role="article"]').cloneNode(true);
    copy.querySelector('prawdowid-ui')?.remove(); copy.id = 'copy';
    document.body.append(copy);
  });
  await page.locator('#copy prawdowid-ui .badge').waitFor();
  assert.equal((await calls('quick')).filter(m => m.items[0].id !== 'pick').length, 1, 'a text seen before is not sent again');
  assert.equal((await calls('check')).filter(m => m.mode === 'auto').length, 3);

  // ---------------------------------------------------------------- 2. overlay only as an opt-in setting
  await load({settings: {...defaults, mode: 'zaslon', autoVerify: false}, quick: QUICK, check: CHECK, router: true});
  await tag('Ukraina w ogóle nie płaci Orlenowi').locator('.ov').waitFor();
  const card = tag('Ukraina w ogóle nie płaci Orlenowi').locator('.ov');
  assert.match(await card.innerText(), /Demagog/);
  assert.match(await card.locator('.meta a').innerText(), /02\.03\.2026/);
  assert.equal(await card.locator('.meta a').getAttribute('href'), 'https://demagog.org.pl/fake_news/orlen-ukraina/');
  assert.equal(await tag('Wilk rzucił się').locator('.ov').count(), 0, 'a weaker match is never covered');
  await card.locator('[data-a="pokaz"]').click();
  assert.equal(await card.count(), 0);
  assert.match(await tag('Ukraina w ogóle nie płaci Orlenowi').locator('.badge').innerText(), /Demagog.*„Fałsz”.*02\.03\.2026/s);
  assert.doesNotMatch(await uiText(), /podejrzan|%/i);
  // background checks switched off in the popup → none are sent
  await page.waitForTimeout(1500);
  assert.equal((await calls('check')).length, 0);

  // ---------------------------------------------------------------- 3. server before the router (no `state`)
  await load({settings: defaults, quick: QUICK, check: CHECK, router: false});
  await tag('Ukraina w ogóle nie płaci Orlenowi').locator('.badge').waitFor(); // level + match still give the sourced badge
  await page.waitForTimeout(1500);
  assert.equal((await calls('check')).length, 0, 'no `candidate` state → no background checks against an old server');
  assert.equal(await page.locator('prawdowid-ui .badge').count(), 2);

  // ---------------------------------------------------------------- 4. rate limited: wait, re-send, render nothing meanwhile
  await load({settings: {...defaults, autoVerify: false}, quick: QUICK, check: CHECK, router: true, quickFail: 1});
  await page.waitForFunction(() => window.calls.some(m => m.type === 'quick'));
  await page.waitForTimeout(600);
  assert.equal(await page.locator('prawdowid-ui .badge').count(), 0, 'an error never renders a tag');
  assert.equal((await calls('quick')).length, 1, 'no retry before Retry-After');
  await tag('Ukraina w ogóle nie płaci Orlenowi').locator('.badge').waitFor({timeout: 6000});
  const retried = await calls('quick');
  assert.equal(retried.length, 2);
  assert.ok(retried[1].at - retried[0].at >= 2000, 'waited as long as the server asked');
  assert.deepEqual(retried[1].items.map(i => i.text), retried[0].items.map(i => i.text), 'the same items are sent again');

  // ---------------------------------------------------------------- 5. background results that must stay silent
  await load({settings: defaults, quick: QUICK, router: true, check: [
    ['Chorwacki lekarz', {claims: [claim('potwierdzone', [{...source, stance: 'popiera'}])]}], // confirmed: not what a tag is for
    ['Niemieckie służby', {claims: [claim('falszywe', [source], {conflicting: true})]}], // sources disagree: not decisive
    ['490 miliardów', {status: 'blad_techniczny', status_message: 'Błąd techniczny.', claims: []}], // failure is not a verdict
  ]});
  await autoDone(3);
  await page.waitForTimeout(500);
  assert.equal(await page.locator('prawdowid-ui .badge').count(), 2, 'only the two tier-1 matches are marked');
  for (const part of ['Chorwacki lekarz', 'Niemieckie służby', '490 miliardów']) assert.equal(await tag(part).count(), 0, `must stay unmarked: ${part}`);

  assert.deepEqual(errors, []);
  await browser.close();
  console.log('PASS: router states, sourced match badge, background checks capped at 3 and silent unless decisive+sourced, opt-in overlay, stage polling, dedup, old server, back-off.');
})().catch(e => { console.error(e); process.exit(1); });
