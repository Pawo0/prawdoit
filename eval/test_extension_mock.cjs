// Background transport regression: mock mode must never call the backend.
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let onMessage;
const stored = {};
let fetches = 0;
const context = {
  setTimeout, AbortSignal,
  fetch: async () => { fetches++; return {ok: true, json: async () => ({status: 'ok', demo: false})}; },
  chrome: {
    storage: {local: {get: async () => stored, set: async data => Object.assign(stored, data)}},
    runtime: {onMessage: {addListener: fn => onMessage = fn}, onInstalled: {addListener() {}}},
    tabs: {onRemoved: {addListener() {}}}, action: {}
  }
};
vm.runInNewContext(readFileSync(resolve(__dirname, '../extension/background.js'), 'utf8'), context);
const send = msg => new Promise(resolve => onMessage(msg, {}, resolve));
(async () => {
  assert.equal((await send({type: 'settings'})).data.mockMode, false);
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
  assert.equal(fetches, 0, 'No API requests in demo mode');
  await send({type: 'setSettings', data: {mockMode: false}});
  await send({type: 'check', text: 'Real check'});
  assert.equal(fetches, 1, 'Turning demo off restores the normal API path');
  console.log('PASS: persisted switch, mock loading/result, no network in demo, API restored when disabled.');
})().catch(e => { console.error(e); process.exitCode = 1; });
