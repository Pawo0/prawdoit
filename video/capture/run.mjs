// Records the scenes of the demo video against the running application.
//   node capture/run.mjs            → web + extension
//   node capture/run.mjs web        → one scene
// The Discord scene is separate (capture/discord.mjs): it posts a real message.
import path from 'node:path';
import {launch, Recorder, BASE, REPO, sleep} from './lib.mjs';

const CLAIM_FALSE = 'Ukraina w ogóle nie płaci Orlenowi za paliwo';
const CLAIM_UNKNOWN = 'W Suwałkach otwarto pierwszą w Polsce fabrykę baterii grafenowych';

async function ready(page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  // The browser's spell-check underlines are not part of the application.
  await page.evaluate(() => document.querySelectorAll('textarea, input').forEach(e => { e.spellcheck = false; }));
}

/** Website: one claim the sources refute, one they cannot settle. */
async function web() {
  const {ctx, page} = await launch();
  await page.goto(BASE + '/'); await ready(page);
  const rec = new Recorder(page, 'web'); await rec.start();
  await rec.mark('home', '.check-window');
  await rec.wait(1200);

  await rec.clickOn('#q', {fx: 0.3, fy: 0.4});
  await rec.wait(250);
  await rec.type(CLAIM_FALSE);
  await rec.mark('a-typed', '.check-window');
  await rec.wait(500);
  await rec.moveToRect(await rec.rect('#go'));
  await rec.wait(200);
  await rec.mark('a-submit', '#go');
  await rec.click();
  await rec.realtime(async () => {
    await page.waitForSelector('.claim-card', {timeout: 90000});
    await rec.mark('a-result', '.claim-card');
  });
  await rec.wait(600);
  await rec.mark('a-verdict', '.verdict-hero');
  await rec.mark('a-explanation', '.verdict-explanation');
  await rec.mark('a-source', '.mainsrc');
  await rec.mark('a-source-link', '.mainsrc a');
  await rec.wait(2600);
  await rec.moveToRect(await rec.rect('.mainsrc a'), {fx: 0.35});
  await rec.wait(2600);
  // further down: the quoted evidence
  const ev = page.locator('.ev').first();
  const before = await rec.rect(ev);
  await rec.scrollBy(Math.max(0, before.y - 150), 900);
  await rec.wait(300);
  await rec.mark('a-evidence', ev);
  await rec.mark('a-quote', page.locator('.ev blockquote').first());
  await rec.moveToRect(await rec.rect(page.locator('.ev blockquote').first()), {fx: 0.2});
  await rec.wait(3600);

  // second check: no evidence → the system says so instead of guessing
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await rec.wait(250);
  await rec.mark('b-again', '#again');
  await rec.clickOn('#again');
  await rec.wait(500);
  await page.keyboard.press('Control+A');
  await rec.wait(200);
  await rec.type(CLAIM_UNKNOWN, {cps: 34});
  await rec.mark('b-typed', '.check-window');
  await rec.wait(400);
  await rec.moveToRect(await rec.rect('#go'));
  await rec.mark('b-submit', '#go');
  await rec.click();
  await rec.realtime(async () => {
    await page.waitForSelector('.loading-window', {timeout: 10000}).catch(() => {});
    await rec.mark('b-waiting', '.loading-window');
    await page.waitForSelector('.claim-card', {timeout: 90000});
    await rec.mark('b-result', '.claim-card');
  });
  await rec.wait(500);
  await rec.mark('b-verdict', '.verdict-hero');
  await rec.mark('b-explanation', '.verdict-explanation');
  await rec.moveToRect(await rec.rect('.verdict-explanation'), {fx: 0.6, fy: 0.9});
  await rec.wait(3000);
  const unknown = page.locator('.claim-card .info').first();  // "what could not be established / what would settle it"
  if (await unknown.count()) {
    await unknown.scrollIntoViewIfNeeded();
    await rec.mark('b-unknown', unknown);
    await rec.moveToRect(await rec.rect(unknown), {fx: 0.5, fy: 0.75});
  }
  await rec.wait(3800);
  await rec.stop();
  await ctx.close();
}

/** Extension on the demo feed: source badges next to posts, then the picker and a full check. */
async function extension() {
  const ext = path.join(REPO, 'extension');
  const {ctx, page} = await launch({extension: ext});
  const sw = ctx.serviceWorkers()[0] || await ctx.waitForEvent('serviceworker', {timeout: 20000});
  await sw.evaluate(base => chrome.storage.local.set({noticeSeen: true, apiBase: base}), BASE);  // skip the first-run notice
  const badges = () => page.locator('prawdowid-ui .badge');

  const rec = new Recorder(page, 'extension'); await rec.start();
  await rec.setSlow(1);  // the scan after page load takes as long as it takes
  await page.goto(BASE + '/demo/feed.html');
  await rec.mark('feed-loaded');
  await badges().first().waitFor({timeout: 60000});
  await rec.mark('badge-first', badges().first());
  await sleep(1500);
  await rec.setSlow(rec.baseSlow);
  await rec.mark('badges-top', badges().first());
  await rec.wait(800);
  const firstPost = page.locator('[role=article]').first();
  await rec.mark('post-first', firstPost);
  await rec.moveToRect(await rec.rect(badges().first()), {fx: 0.3, fy: 0.6});
  await rec.wait(3000);

  // scroll through the feed: more posts get a badge, neutral ones stay untouched
  await rec.scrollBy(430, 1100);
  await rec.realtime(() => sleep(1800));
  await rec.mark('feed-middle');
  await rec.wait(1400);
  await rec.scrollBy(600, 1200);
  await rec.realtime(() => sleep(1800));
  await rec.mark('feed-bottom');
  await rec.wait(900);

  // the on-demand check: floating button → pick a post → result window
  const fab = page.locator('prawdowid-ui .fab');
  await rec.mark('fab', fab);
  await rec.clickOn(fab);
  await rec.wait(500);
  await rec.mark('picker', page.locator('prawdowid-ui .pbar'));
  const tweets = page.locator('article[data-testid=tweet]');
  await rec.moveToRect(await rec.rect(tweets.nth(1)), {fx: 0.4});
  await rec.wait(450);
  const target = tweets.nth(3);  // "Wilk rzucił się na dwuletnie dziecko w Toskanii"
  const text = target.locator('[data-testid=tweetText]');
  await rec.moveToRect(await rec.rect(text), {fx: 0.45});
  await rec.wait(700);
  await rec.mark('pick-target', target);
  await rec.click();
  const sheet = page.locator('prawdowid-ui .sheet');
  await rec.realtime(async () => {
    await sheet.waitFor({timeout: 15000});
    await rec.mark('sheet-loading', sheet);
    await page.locator('prawdowid-ui .sheet .compact-result').first().waitFor({timeout: 90000});
    await rec.mark('sheet-result', sheet);
  });
  await rec.wait(700);
  await rec.mark('sheet-verdict', page.locator('prawdowid-ui .sheet .verdict-heading').first());
  await rec.mark('sheet-sources', page.locator('prawdowid-ui .sheet .compact-sources').first());
  await rec.moveToRect(await rec.rect(page.locator('prawdowid-ui .sheet .compact-sources .source a').first()), {fx: 0.6});
  await rec.wait(3000);
  const details = page.locator('prawdowid-ui .sheet .result-details summary').first();
  await rec.clickOn(details, {fx: 0.25});
  await rec.wait(500);
  await rec.mark('sheet-details', sheet);
  await rec.wait(900);
  await rec.moveToRect(await rec.rect(page.locator('prawdowid-ui .sheet .sheet-body')), {fx: 0.5, fy: 0.6});
  await rec.wheel(260, 800);
  await rec.wait(300);
  await rec.mark('sheet-quotes', sheet);
  await rec.wait(3200);
  await rec.stop();
  await ctx.close();
}

const scenes = {web, extension};
const want = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(scenes);
for (const name of want) {
  if (!scenes[name]) throw new Error(`Unknown scene "${name}". Available: ${Object.keys(scenes).join(', ')}`);
  console.log(`— ${name}`);
  await scenes[name]();
}
