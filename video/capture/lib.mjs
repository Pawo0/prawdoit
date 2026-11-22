// Screen capture for the demo video: real browser, real backend.
//
// A recording is the Chromium screencast (device-pixel frames with their own timestamps, written to a
// constant-frame-rate MP4) plus an event log on the same clock: cursor samples, clicks and named marks
// with element rectangles. The Remotion composition draws the cursor and aims the camera from that log,
// so nothing in the video is positioned by hand-measured pixels.
//
// Chromium cannot deliver 2560x1440 frames in real time (about 8-11 per second here), so the browser is
// driven in slow motion: our own input, pauses and the page's CSS animations run SLOW times slower and the
// recording is retimed by the same factor ("scene time"). Waiting for the backend is the exception — the
// server cannot be slowed, so those stretches are recorded at factor 1 and keep their true duration.
import {chromium} from 'playwright-core';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const REPO = path.resolve(ROOT, '..');
export const OUT = path.join(ROOT, 'public', 'captures');
export const BASE = (process.env.PRAWDOWID_BASE || 'http://localhost:8000').replace(/\/$/, '');
export const VIEW = {width: 1280, height: 720};
export const SCALE = 2;
export const FPS = 30;
export const SLOW = Number(process.env.PRAWDOWID_CAPTURE_SLOW || 5);

export function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const cache = path.join(os.homedir(), '.cache', 'ms-playwright');
  const builds = fs.existsSync(cache)
    ? fs.readdirSync(cache).filter(d => /^chromium-\d+$/.test(d)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
    : [];
  for (const b of builds) {
    const exe = path.join(cache, b, 'chrome-linux64', 'chrome');
    if (fs.existsSync(exe)) return exe;
  }
  throw new Error('No Chromium found. Set CHROME_PATH or run: npx playwright install chromium');
}

/** Set to a directory to get a small screenshot at every mark (for checking a run without watching it). */
const DEBUG = process.env.PRAWDOWID_CAPTURE_DEBUG || '';
if (DEBUG) fs.mkdirSync(DEBUG, {recursive: true});

export const sleep = ms => new Promise(r => setTimeout(r, ms));
const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

const GPU = process.env.PRAWDOWID_CAPTURE_GPU === '0' ? []
  : ['--enable-gpu', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=gl-egl'];

/**
 * A real device scale factor (not an emulated one): only then are screencast frames delivered in device pixels.
 * `profile` keeps a browser profile between runs (a signed-in session); otherwise a throwaway one is used.
 */
export async function launch({extension = null, profile = null, headless = true, view = VIEW, scale = SCALE} = {}) {
  const args = ['--hide-scrollbars', '--force-color-profile=srgb', `--force-device-scale-factor=${scale}`,
    `--window-size=${view.width},${view.height + 87}`, ...GPU];
  if (extension) args.push(`--disable-extensions-except=${extension}`, `--load-extension=${extension}`);
  const dir = profile || fs.mkdtempSync(path.join(os.tmpdir(), 'prawdowid-video-'));
  const ctx = await chromium.launchPersistentContext(dir, {
    executablePath: chromePath(), headless, args, viewport: null,
    locale: 'pl-PL', timezoneId: 'Europe/Warsaw', colorScheme: 'light',
    ignoreDefaultArgs: extension ? ['--disable-extensions'] : [],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await fitViewport(page, view);
  return {ctx, page, dir};
}

/** The window is sized from outside, so correct it until the page itself measures exactly `view`. */
export async function fitViewport(page, view = VIEW) {
  const cdp = await page.context().newCDPSession(page);
  for (let i = 0; i < 4; i++) {
    const inner = await page.evaluate(() => ({w: innerWidth, h: innerHeight}));
    if (inner.w === view.width && inner.h === view.height) break;
    const {windowId, bounds} = await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds', {windowId, bounds: {
      width: bounds.width + view.width - inner.w, height: bounds.height + view.height - inner.h}});
    await sleep(250);
  }
  const inner = await page.evaluate(() => ({w: innerWidth, h: innerHeight, dpr: devicePixelRatio}));
  if (inner.w !== view.width || inner.h !== view.height) throw new Error(`Viewport is ${inner.w}x${inner.h}, wanted ${view.width}x${view.height}`);
  await cdp.detach().catch(() => {});
  return inner;
}

export class Recorder {
  constructor(page, name, {view = VIEW, slow = SLOW} = {}) {
    this.page = page; this.name = name; this.view = view; this.baseSlow = slow;
    this.segs = [{r: Date.now() / 1000, v: 0, slow}];
    this.frames = []; this.events = []; this.shots = 0; this.locked = null; this.onFrame = null; this.pos = {x: VIEW.width / 2, y: VIEW.height / 2};
    this.dir = fs.mkdtempSync(path.join(os.tmpdir(), `frames-${name}-`));
  }

  get slow() { return this.segs.at(-1).slow; }

  /** Scene time (seconds) of a wall-clock instant: wall time divided by the slow-motion factor then in force. */
  now(r = Date.now() / 1000) {
    let seg = this.segs[0];
    for (const s of this.segs) if (s.r <= r) seg = s;
    return seg.v + Math.max(0, r - seg.r) / seg.slow;
  }

  async setSlow(slow) {
    const r = Date.now() / 1000;
    this.segs.push({r, v: this.now(r), slow});
    await this.cdp.send('Animation.setPlaybackRate', {playbackRate: 1 / slow}).catch(() => {});
  }

  /** Run `fn` at true speed — for anything whose duration is the backend's, not ours. */
  async realtime(fn) {
    await this.setSlow(1);
    try { return await fn(); } finally { await this.setSlow(this.baseSlow); }
  }

  /** Pause for `ms` of scene time. */
  wait(ms) { return sleep(ms * this.slow); }

  async start() {
    this.cdp = await this.page.context().newCDPSession(this.page);
    this.cdp.on('Page.screencastFrame', f => {
      const file = path.join(this.dir, `f${String(this.frames.length).padStart(6, '0')}.jpg`);
      fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
      this.frames.push({file, t: f.metadata.timestamp, v: this.locked});
      this.onFrame?.();
      this.cdp.send('Page.screencastFrameAck', {sessionId: f.sessionId}).catch(() => {});
    });
    await this.cdp.send('Animation.enable');
    await this.cdp.send('Animation.setPlaybackRate', {playbackRate: 1 / this.slow});
    await this.cdp.send('Page.startScreencast', {
      format: 'jpeg', quality: 94, everyNthFrame: 1, maxWidth: this.view.width * SCALE, maxHeight: this.view.height * SCALE,
    });
    await this.page.mouse.move(this.pos.x, this.pos.y);
    this.log('cursor', {...this.pos});
    await this.wait(300);
  }

  log(type, data = {}) { this.events.push({type, t: this.now(), ...data}); }

  /** Named moment, optionally with the rectangle of what the camera should look at. */
  async mark(name, target = null, extra = {}) {
    let rect = null;
    if (target) rect = await this.rect(target);
    this.log('mark', {name, rect, ...extra});
    if (DEBUG) await this.page.screenshot({path: path.join(DEBUG, `${this.name}-${String(this.shots++).padStart(2, '0')}-${name}.jpg`), type: 'jpeg', quality: 70, scale: 'css'}).catch(() => {});
    return rect;
  }

  async rect(target) {
    if (typeof target === 'function') return target();
    if (target && typeof target.x === 'number') return target;
    const loc = typeof target === 'string' ? this.page.locator(target).first() : target;
    const b = await loc.boundingBox();
    return b ? {x: b.x, y: b.y, w: b.width, h: b.height} : null;
  }

  /** Hand-like move: eased, slightly arced, sampled every frame so hover states are real. */
  async moveTo(x, y, ms = null) {
    const from = {...this.pos}, dist = Math.hypot(x - from.x, y - from.y);
    if (dist < 1) return;
    const dur = (ms ?? Math.min(1100, 320 + dist * 0.9)) * this.slow;
    const bow = Math.min(40, dist * 0.08) * (x > from.x ? -1 : 1);
    const nx = -(y - from.y) / dist, ny = (x - from.x) / dist;
    const t0 = Date.now();
    for (;;) {
      const p = Math.min(1, (Date.now() - t0) / dur), e = ease(p), arc = Math.sin(Math.PI * e) * bow;
      this.pos = {x: from.x + (x - from.x) * e + nx * arc, y: from.y + (y - from.y) * e + ny * arc};
      await this.page.mouse.move(this.pos.x, this.pos.y);
      this.log('cursor', {...this.pos});
      if (p >= 1) break;
      await sleep(12);
    }
  }

  async moveToRect(r, {fx = 0.5, fy = 0.5, ms = null} = {}) {
    await this.moveTo(r.x + r.w * fx, r.y + r.h * fy, ms);
  }

  async click({pause = 140} = {}) {
    await this.wait(pause);
    this.log('click', {...this.pos});
    await this.page.mouse.down(); await this.wait(70); await this.page.mouse.up();
  }

  async clickOn(target, opts = {}) {
    const r = await this.rect(target);
    if (!r) throw new Error(`Nothing to click: ${target}`);
    await this.moveToRect(r, opts);
    await this.click(opts);
    return r;
  }

  /** Typing with uneven key timing; the text really goes through the keyboard. */
  async type(text, {cps = 26} = {}) {
    this.log('mark', {name: 'type-start', text});
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      const base = 1000 / cps;
      await this.wait(base * (ch === ' ' ? 1.5 : 0.55 + Math.random() * 0.9));
    }
    this.log('mark', {name: 'type-end'});
  }

  /** Resolves when the next screencast frame arrives (or after `timeout` ms if the page did not repaint). */
  nextFrame(timeout = 800) {
    return new Promise(resolve => {
      const timer = setTimeout(resolve, timeout);
      this.onFrame = () => { clearTimeout(timer); this.onFrame = null; resolve(); };
    });
  }

  /**
   * Scroll in exact steps, one captured frame per step. A full-page repaint at this resolution takes far
   * longer than a frame, so here scene time is assigned per step instead of being measured.
   */
  async scrollBy(dy, ms = 700) {
    const steps = Math.max(2, Math.round(ms / 1000 * FPS)), v0 = this.now();
    const y0 = await this.page.evaluate(() => window.scrollY);
    for (let i = 1; i <= steps; i++) {
      const got = this.nextFrame();
      this.locked = v0 + (i / steps) * ms / 1000;
      await this.page.evaluate(y => window.scrollTo({top: y, behavior: 'instant'}), y0 + dy * ease(i / steps));
      await got;
    }
    await sleep(120);
    this.locked = null;
    this.segs.push({r: Date.now() / 1000, v: v0 + ms / 1000, slow: this.slow});
    await this.page.mouse.move(this.pos.x, this.pos.y);  // hover state for the content now under the cursor
    this.log('mark', {name: 'scrolled', dy});
  }

  /** Wheel over whatever is under the cursor (an inner scroll area); small repaints keep up in slow motion. */
  async wheel(dy, ms = 600) {
    const t0 = Date.now(), dur = ms * this.slow;
    let done = 0;
    for (;;) {
      const p = Math.min(1, (Date.now() - t0) / dur), target = dy * ease(p), d = target - done;
      done = target;
      await this.page.mouse.wheel(0, d);
      if (p >= 1) break;
      await sleep(30);
    }
    this.log('mark', {name: 'wheeled', dy});
  }

  async stop() {
    await this.wait(400);
    await this.cdp.send('Page.stopScreencast').catch(() => {});
    await sleep(300);
    if (this.frames.length < 2) throw new Error(`${this.name}: only ${this.frames.length} frames captured`);
    fs.mkdirSync(OUT, {recursive: true});
    for (const f of this.frames) f.t = f.v ?? this.now(f.t);
    this.frames.sort((a, b) => a.t - b.t);
    const t0 = this.frames[0].t, end = Math.max(this.frames.at(-1).t, this.now());
    // One still per screencast frame, held until the next one: the page only repaints when it changes.
    const list = this.frames.map((f, i) => {
      const next = i + 1 < this.frames.length ? this.frames[i + 1].t : end + 1 / FPS;
      return `file '${f.file}'\nduration ${Math.max(0.001, next - f.t).toFixed(4)}`;
    }).join('\n') + `\nfile '${this.frames.at(-1).file}'\n`;
    const listFile = path.join(this.dir, 'frames.txt');
    fs.writeFileSync(listFile, list);
    const mp4 = path.join(OUT, `${this.name}.mp4`);
    const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-vf', `fps=${FPS},scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '15',
      '-g', String(FPS), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4], {encoding: 'utf8'});
    if (r.status !== 0) throw new Error(`ffmpeg failed: ${r.stderr}`);
    const vp = this.view;
    const meta = {
      name: this.name, video: `captures/${this.name}.mp4`, fps: FPS, duration: +(end - t0).toFixed(3),
      view: vp, scale: SCALE, slow: this.baseSlow, frames: this.frames.length, capturedAt: new Date().toISOString(), base: BASE,
      events: this.events.map(e => ({...e, t: +(e.t - t0).toFixed(3)})),
    };
    fs.writeFileSync(path.join(OUT, `${this.name}.json`), JSON.stringify(meta, null, 1));
    fs.rmSync(this.dir, {recursive: true, force: true});
    const fpsReal = (this.frames.length / meta.duration).toFixed(1);
    console.log(`${this.name}: ${meta.duration}s of scene time, ${this.frames.length} frames (~${fpsReal} per scene second) → ${path.relative(ROOT, mp4)}`);
    return meta;
  }
}
