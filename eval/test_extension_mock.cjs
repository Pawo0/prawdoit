// Background transport regression: mock mode must never call the backend; real mode starts a job and polls it,
// falls back to the synchronous endpoint only for manual checks, and reports rate limits to the page.
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let onMessage;
const stored = {};
let fetches = 0;
const opened = [];
const requests = [];
// Scripted server. asyncApi: 'job' (current server) | 'missing' (no job API) | 'old' (job API that ignores `mode`) | 'limited'
const server = {asyncApi: 'job', polls: 0, quickStatus: 200};
const reply = (status, body, headers = {}) => ({ok: status >= 200 && status < 300, status, headers: {get: k => headers[k] ?? null}, json: async () => body});
const context = {
  setTimeout, AbortSignal, URL,
  fetch: async (url, opts = {}) => {
    fetches++;
    const path = new URL(url).pathname, body = opts.body ? JSON.parse(opts.body) : null;
    requests.push({path, method: opts.method, body, credentials: opts.credentials});
    if (path === '/api/check/async') {
      if (server.asyncApi === 'missing') return reply(404, {detail: 'Not Found'});
      if (server.asyncApi === 'limited') return reply(429, {detail: 'Za dużo zapytań'}, {'Retry-After': '17'});
      return reply(200, server.asyncApi === 'old' ? {job_id: 'job1'} : {job_id: 'job1', mode: body.mode});
    }
    if (path === '/api/jobs/job1') {
      return ++server.polls < 2 ? reply(200, {state: 'running', stage: 'baza', stage_label: 'Szukam w bazie sprawdzonych informacji…'})
        : reply(200, {state: 'done', stage: 'gotowe', result: {status: 'ok', demo: false, via: 'job'}});
    }
    if (path === '/api/jobs/gone') return reply(404, {detail: 'Nie znaleziono zadania'});
    if (path === '/api/check') return reply(200, {status: 'ok', demo: false, via: 'sync'});
    if (path === '/api/quick') {
      return server.quickStatus === 200 ? reply(200, body.items.map(i => ({id: i.id, level: 'brak', risk: 0, state: 'candidate', priority: 0.5})))
        : reply(server.quickStatus, {detail: 'limit'}, {'Retry-After': '7'});
    }
    return reply(500, {});
  },
  chrome: {
    storage: {local: {get: async () => stored, set: async data => Object.assign(stored, data)}},
    runtime: {onMessage: {addListener: fn => onMessage = fn}, onInstalled: {addListener() {}}},
    tabs: {onRemoved: {addListener() {}}, create: async ({url}) => opened.push(url)}, action: {}
  }
};
vm.runInNewContext(readFileSync(resolve(__dirname, '../extension/background.js'), 'utf8'), context);
const send = msg => new Promise(resolve => onMessage(msg, {}, resolve));
const paths = () => requests.splice(0).map(r => r.path);
const plain = value => JSON.parse(JSON.stringify(value)); // replies are objects of the vm realm
(async () => {
  const defaults = (await send({type: 'settings'})).data;
  assert.equal(defaults.mockMode, false);
  assert.equal(defaults.mode, 'oznacz', 'covering posts is opt-in: the default is a badge');
  assert.equal(defaults.autoVerify, true);
  await send({type: 'setSettings', data: {mockMode: true}});
  assert.equal((await send({type: 'settings'})).data.mockMode, true);
  const quick = await send({type: 'quick', items: [{id: 'one', text: 'test'}]});
  assert.equal(quick.data[0].level, 'brak');
  const start = Date.now();
  const result = await send({type: 'check', text: 'Wybrany tekst do testu interfejsu.'});
  assert.ok(Date.now() - start >= 1000, 'Mock must allow the loading state to be visible');
  assert.equal(result.data.demo, true);
  assert.equal(result.data.claims[0].claim, 'Wybrany tekst do testu interfejsu.');
  assert.match(result.data.warnings[0], /TRYB DEMONSTRACYJNY/);
  assert.equal((await send({type: 'check', text: 'Tekst z tła.', mode: 'auto'})).ok, false, 'no background checks and no fake badges in demo mode');
  assert.equal(fetches, 0, 'No API requests in demo mode');
  await send({type: 'openWebsite', demo: true});
  assert.equal(opened.at(-1), 'http://localhost:5500/');
  await send({type: 'setSettings', data: {demoWebBase: 'http://localhost:5600'}});
  await send({type: 'openWebsite', demo: true});
  assert.equal(opened.at(-1), 'http://localhost:5600/');
  await send({type: 'openAnalysis', id: 'real-result'});
  assert.equal(opened.at(-1), 'http://localhost:8000/analiza/real-result');
  await send({type: 'setSettings', data: {mockMode: false}});

  // Manual check = start a job, then short polls (no request stays open while the server works).
  const started = await send({type: 'check', text: 'Real check'});
  assert.equal(fetches, 1, 'Turning demo off restores the normal API path');
  assert.deepEqual(plain(started), {ok: true, job: 'job1'});
  assert.deepEqual(requests[0], {path: '/api/check/async', method: 'POST', body: {text: 'Real check', channel: 'extension', mode: 'manual'}, credentials: 'omit'});
  const first = await send({type: 'job', id: 'job1'});
  assert.equal(first.data.state, 'running');
  assert.match(first.data.stage_label, /Szukam w bazie/);
  const second = await send({type: 'job', id: 'job1'});
  assert.equal(second.data.state, 'done');
  assert.equal(second.data.result.via, 'job');
  assert.deepEqual(paths(), ['/api/check/async', '/api/jobs/job1', '/api/jobs/job1']);
  const gone = await send({type: 'job', id: 'gone'});
  assert.deepEqual([gone.ok, gone.status], [false, 404]);
  paths();

  // Background check: same job API with mode "auto".
  assert.deepEqual(plain(await send({type: 'check', text: 'Kandydat', mode: 'auto'})), {ok: true, job: 'job1'});
  assert.equal(requests[0].body.mode, 'auto');
  paths();

  // Server without the job API: a manual check falls back to the synchronous endpoint …
  server.asyncApi = 'missing';
  const sync = await send({type: 'check', text: 'Real check'});
  assert.equal(sync.data.via, 'sync');
  assert.deepEqual(paths(), ['/api/check/async', '/api/check']);
  // … a background check never does: an old server would run it as a normal check (live search, case, stored text).
  assert.equal((await send({type: 'check', text: 'Kandydat', mode: 'auto'})).ok, false);
  assert.deepEqual(paths(), ['/api/check/async']);
  server.asyncApi = 'old';
  assert.equal((await send({type: 'check', text: 'Kandydat', mode: 'auto'})).ok, false, 'a job that was not accepted as "auto" is not used');
  assert.equal((await send({type: 'check', text: 'Real check'})).job, 'job1', 'manual checks work with the older job API');
  paths();

  // Rate limits reach the page with the server's Retry-After; they are errors, never results.
  server.asyncApi = 'limited';
  const limited = await send({type: 'check', text: 'Real check'});
  assert.deepEqual([limited.ok, limited.status, limited.retryAfter], [false, 429, 17]);
  assert.deepEqual(paths(), ['/api/check/async'], 'a rate limit is not answered with another request');
  server.asyncApi = 'job';
  await send({type: 'quick', items: [{id: 'a', text: 'Tekst posta', extra: undefined}]});
  assert.deepEqual(requests[0].body, {items: [{id: 'a', text: 'Tekst posta'}], page_url: null}, 'only text; the page address is never sent');
  server.quickStatus = 429;
  const busy = await send({type: 'quick', items: [{id: 'a', text: 'Tekst posta'}]});
  assert.deepEqual([busy.ok, busy.status, busy.retryAfter], [false, 429, 7]);
  console.log('PASS: persisted switch, mock loading/result, no network in demo, job start + polling, sync fallback (manual only), auto mode, rate limits.');
})().catch(e => { console.error(e); process.exitCode = 1; });
