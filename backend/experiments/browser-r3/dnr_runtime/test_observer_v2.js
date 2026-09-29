"use strict";
// Node VM only: realistic debug request does NOT contain timeStamp.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const {webcrypto} = require("node:crypto"), path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "extension-v2/observer.js"), "utf8");
const session = "flowtracer-r3-dnr-capability-20260928-01", id = "a".repeat(32);
function candidate() {
  let matched, message, store = {}, now = 1700000000000, release;
  const clock = {now: () => now};
  const clone = value => JSON.parse(JSON.stringify(value));
  const chrome = {
    runtime: {id, getURL: file => `chrome-extension://${id}/${file}`,
      onMessage: {addListener: fn => {message = fn;}}},
    declarativeNetRequest: {onRuleMatchedDebug: {addListener: fn => {matched = fn;}},
      getEnabledRulesets: async () => ["ws_default_deny_v1"],
      getDynamicRules: async () => [], getSessionRules: async () => []},
    storage: {session: {setAccessLevel: async () => {},
      get: async () => clone(store), set: async values => Object.assign(store, clone(values))}},
  };
  const crypto = {randomUUID: () => "SYNTHETIC-v2-epoch", subtle: {
    digest: (...args) => new Promise(resolve => {release = () => webcrypto.subtle.digest(...args).then(resolve);})}};
  vm.runInNewContext(source, {chrome, crypto, Date: clock, URL, TextEncoder, setTimeout, clearTimeout});
  return {match: matched, clock, setNow: n => {now = n;},
    release: () => release(),
    call: payload => new Promise(resolve => message(payload,
      {id, url:`chrome-extension://${id}/audit.html`}, resolve))};
}
function event() {
  return {rule: {ruleId: 1, rulesetId: "ws_default_deny_v1"}, request: {
    requestId: "SYNTHETIC-dnr-1", type: "websocket", method: "GET",
    url: "wss://websocket-r3.test:8443/dnr-worker-wss", tabId: -1,
    frameId: -1, parentFrameId: -1, initiator: "https://navigation-r3.test:8443"}};
}
async function configure(c) {return c.call({kind:"configure", session});}
(async () => {
  let count = 0;
  const c = candidate();
  assert.equal((await configure(c)).schema_version, "r3-dnr-audit-v2"); count++;
  assert.equal(Object.hasOwn(event().request, "timeStamp"), false);
  c.match(event());
  c.setNow(1700000004000); c.clock.now = () => 42;
  await new Promise(resolve => setImmediate(resolve));
  c.release();
  const snapshot = await c.call({kind:"snapshot"});
  const row = snapshot.receipts[0];
  assert.equal(snapshot.ok, true);
  assert.equal(row.timestamp, 1700000000000); // entry, not hash/flush/modified Date.now
  assert.equal(row.timestamp_source, "trusted_observer_callback_epoch_ms");
  assert.equal(row.schema_version, "r3-dnr-receipt-v2");
  assert.equal(Object.keys(row).length, 18);
  assert.equal(row.initiator, null); assert.equal(Object.hasOwn(row, "url"), false); count++;
  for (const bad of [NaN, Infinity, true, 1700000000000.5, 1700000000]) {
    const d = candidate(); await configure(d); d.setNow(bad); d.match(event());
    const state = await d.call({kind:"snapshot"});
    assert.equal(state.ok, false); assert.equal(state.receipts.length, 0); count++;
  }
  const reverse = candidate(); await configure(reverse); reverse.match(event());
  await new Promise(resolve => setImmediate(resolve)); reverse.release();
  await reverse.call({kind:"snapshot"});
  reverse.setNow(1699999999999); reverse.match({...event(), request:{...event().request,requestId:"second"}});
  assert.equal((await reverse.call({kind:"snapshot"})).ok, false); count++;
  const empty = candidate(); await configure(empty);
  assert.equal((await empty.call({kind:"snapshot"})).receipts.length, 0); count++;
  console.log(`OFFLINE_V2_NODE=${count}; runtime_verified=false`);
})().catch(() => {console.error("offline_v2_node_failed"); process.exitCode=1;});
