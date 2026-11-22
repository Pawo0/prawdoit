// Records the Discord scene in the real Discord web client, with the session saved by discord-login.mjs.
//
//   node capture/discord.mjs --dry    types the command, checks every step, clears the box, sends NOTHING
//   node capture/discord.mjs          sends ONE /sprawdz command and records the bot's reply
//
// It only ever writes in the server and channel named below, and only through the bot's own slash command.
import {launch, Recorder, sleep} from './lib.mjs';
import {DISCORD_PROFILE} from './discord-login.mjs';

const SERVER = process.env.PRAWDOWID_DISCORD_SERVER || 'HackNation2026';
const CHANNEL = process.env.PRAWDOWID_DISCORD_CHANNEL || 'ogólny';
const BOT = process.env.PRAWDOWID_DISCORD_BOT || 'Prawdowid';
const CLAIM = process.env.PRAWDOWID_DISCORD_CLAIM || 'Ukraina w ogóle nie płaci Orlenowi za paliwo';
const DRY = process.argv.includes('--dry');

const {ctx, page} = await launch({profile: DISCORD_PROFILE});
try {
  await page.goto('https://discord.com/channels/@me', {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('[data-list-id="guildsnav"]', {timeout: 60000});
  await sleep(2500);

  // The server is matched by its exact name, so a similarly named one cannot be picked by accident.
  const guildId = await page.evaluate(name => {
    const items = [...document.querySelectorAll('[data-list-id="guildsnav"] [data-list-item-id^="guildsnav___"]')];
    // the accessible name is a visually hidden span, optionally prefixed with an unread/mention count
    const label = e => (e.querySelector(':scope > span')?.textContent || e.getAttribute('aria-label') || '').replace(/^.*,\s*/, '').trim();
    const exact = items.filter(e => label(e) === name);
    return exact.length === 1 ? exact[0].getAttribute('data-list-item-id') : null;
  }, SERVER);
  if (!guildId) throw new Error(`Server "${SERVER}" not found exactly once in the server list.`);
  await page.click(`[data-list-item-id="${guildId}"]`);
  await sleep(2500);
  if (!(await page.title()).includes(CHANNEL)) {
    await page.locator('a[href^="/channels/"]:not([href*="@me"])').filter({hasText: CHANNEL}).first().click({timeout: 15000});
  }
  const box = page.locator('div[role="textbox"][data-slate-editor="true"]').first();
  await box.waitFor({timeout: 30000});
  await sleep(2000);
  const title = await page.title();
  if (!title.includes(CHANNEL) || !title.includes(SERVER)) throw new Error(`Not in #${CHANNEL} of ${SERVER}: "${title}"`);

  // Private surroundings stay out of the recording: the list of the account's other servers is hidden.
  await page.evaluate(() => {
    const rail = document.querySelector('[data-list-id="guildsnav"]')?.closest('nav');
    if (rail) rail.style.display = 'none';
  });
  await sleep(800);

  const messages = page.locator('li[id^="chat-messages-"]');
  const seen = new Set(await messages.evaluateAll(els => els.map(e => e.id)));

  const rec = new Recorder(page, DRY ? 'discord-dry' : 'discord'); await rec.start();
  await rec.mark('channel');
  await rec.wait(900);
  await rec.clickOn(box, {fx: 0.15});
  await rec.mark('composer', box);
  await rec.wait(300);
  await rec.type('/sprawdz', {cps: 14});
  const option = page.locator('[role="option"]').filter({hasText: 'sprawdz'}).filter({hasText: BOT}).first();
  await rec.realtime(() => option.waitFor({timeout: 15000}));
  await rec.wait(500);
  await rec.mark('command-list', option);
  await rec.wait(900);
  await rec.mark('command-pressed');  // the list closes here; outlines of it must end at this mark
  await page.keyboard.press('Tab');
  await rec.wait(600);
  await rec.mark('command-chosen', box);
  await rec.type(CLAIM, {cps: 28});
  await rec.wait(400);
  await rec.mark('typed', box);
  await rec.wait(700);

  if (DRY) {
    await page.keyboard.press('Control+A'); await page.keyboard.press('Backspace');
    await sleep(300);
    await page.keyboard.press('Control+A'); await page.keyboard.press('Backspace');
    await page.keyboard.press('Escape');
    await rec.wait(300);
    await rec.mark('cleared', box);
    console.log('DRY RUN: nothing was sent. Box now reads:', JSON.stringify((await box.innerText()).trim()));
  } else {
    await page.keyboard.press('Enter');
    await rec.mark('sent');
    const fresh = () => messages.evaluateAll((els, seenIds) => els.filter(e => !seenIds.includes(e.id)).map(e => ({id: e.id, text: e.innerText})), [...seen]);
    await rec.realtime(async () => {
      const deadline = Date.now() + 90000;
      let thinking = false;
      for (;;) {
        const list = await fresh();
        const last = list.at(-1);
        if (last && !thinking) { thinking = true; await rec.mark('thinking', page.locator(`#${last.id}`)); }
        if (last && /Automatyczny system/.test(last.text)) { await rec.mark('reply', page.locator(`#${last.id}`), {text: last.text}); break; }
        if (Date.now() > deadline) throw new Error(`No reply from the bot within 90 s. Last new message: ${JSON.stringify(last?.text?.slice(0, 200))}`);
        await sleep(150);
      }
    });
    await rec.wait(900);
    const reply = page.locator(`#${(await fresh()).at(-1).id}`);
    await rec.mark('reply-settled', reply);
    const verdict = reply.locator('strong').first();
    if (await verdict.count()) await rec.mark('reply-verdict', verdict);
    const link = reply.locator('a[href^="http"]').first();
    if (await link.count()) {
      await rec.mark('reply-link', link);
      await rec.moveToRect(await rec.rect(link), {fx: 0.3});
    }
    await rec.wait(4500);
  }
  await rec.stop();
} finally {
  await ctx.close();
}
