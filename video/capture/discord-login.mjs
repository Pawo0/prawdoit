// One-time sign-in for the Discord scene. Opens a visible Chromium window on discord.com/login and waits
// until you are signed in; the session stays in a browser profile outside the repository, so the
// recording itself can run without asking again. Delete that directory to sign this browser out.
import {chromium} from 'playwright-core';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {chromePath} from './lib.mjs';

export const DISCORD_PROFILE = process.env.PRAWDOWID_DISCORD_PROFILE
  || path.join(os.homedir(), '.cache', 'prawdowid-video', 'discord-profile');

if (import.meta.url === `file://${process.argv[1]}`) {
  fs.mkdirSync(DISCORD_PROFILE, {recursive: true, mode: 0o700});
  const ctx = await chromium.launchPersistentContext(DISCORD_PROFILE, {
    executablePath: chromePath(), headless: false, viewport: null, locale: 'pl-PL',
    args: ['--window-size=1100,820'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://discord.com/login');
  console.log('Waiting for sign-in in the Chromium window (up to 20 minutes)…');
  try {
    await page.waitForURL(/discord\.com\/channels\//, {timeout: 20 * 60 * 1000});
    await page.waitForTimeout(4000);  // let the client store its session
    console.log('SIGNED_IN', page.url().replace(/\d{6,}/g, '<id>'));
  } catch (e) {
    console.log('NOT_SIGNED_IN', String(e).split('\n')[0]);
  }
  await ctx.close();
}
