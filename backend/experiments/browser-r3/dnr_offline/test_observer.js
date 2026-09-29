"use strict";
// Offline Node VM Chrome-API doubles. NOT extension/browser enforcement evidence.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const {webcrypto} = require("node:crypto"), path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "extension/observer.js"), "utf8");
const session = "flowtracer-r3-dnr-capability-20260928-01";
const id = "a".repeat(32), auditURL = `chrome-extension://${id}/audit.html`;
function candidate(options = {}) {
  let matched, message, store = options.store || {}, access;
  const clone = value => JSON.parse(JSON.stringify(value));
  const chrome = {
    runtime: {id, getURL: file => `chrome-extension://${id}/${file}`,
      onMessage: {addListener: fn => {message = fn;}}},
    declarativeNetRequest: {
      onRuleMatchedDebug: {addListener: fn => {matched = fn;}},
      getEnabledRulesets: async () => options.enabled || ["ws_default_deny_v1"],
      getDynamicRules: async () => options.dynamic || [],
      getSessionRules: async () => options.sessionRules || [],
    },
    storage: {session: {
      setAccessLevel: async value => {access = value.accessLevel;},
      get: async () => clone(store),
      set: async values => {
        if (options.failWrite) throw new Error("secret_do_not_export");
        if (options.hangWrite) return new Promise(() => {});
        if (!options.dropWrite) Object.assign(store, clone(values));
      },
    }},
  };
  vm.runInNewContext(source, {chrome, crypto: webcrypto, URL, TextEncoder,
    setTimeout, clearTimeout, console: {log: () => {throw Error("no console");}}});
  return {
    match: matched, store,
    access: () => access,
    call: (payload, sender = {id, url: auditURL}) => new Promise(resolve => message(payload, sender, resolve)),
  };
}
function event(index = 1, overrides = {}) {
  return {rule: {ruleId: 1, rulesetId: "ws_default_deny_v1"}, request: {
    requestId: `dnr-${index}`, type: "websocket", timeStamp: 1000 + index,
    url: "wss://websocket-r3.test:8443/dnr-worker-wss", tabId: -1, frameId: -1,
    ...overrides,
  }};
}
async function configure(c) {return c.call({kind: "configure", session});}
let count = 0;
async function test(name, fn) {await fn(); count++;}
(async () => {
  await test("configure and trusted readback", async () => {
    const c = candidate(), ready = await configure(c);
    assert.equal(ready.ok, true); assert.equal(ready.receipts.length, 0);
    assert.equal(c.access(), "TRUSTED_CONTEXTS");
  });
  await test("match flush and sanitized receipt", async () => {
    const c = candidate(); await configure(c); c.match(event());
    const result = await c.call({kind: "snapshot"});
    assert.equal(result.ok, true); assert.equal(result.flushed, true);
    assert.equal(result.receipts.length, 1); assert.equal(result.receipts[0].sequence, 1);
    assert.match(result.receipts[0].safe_request_fingerprint, /^[0-9a-f]{64}$/);
    assert.equal(JSON.stringify(result).includes("websocket-r3.test"), false);
    assert.equal(result.receipts[0].initiator, null);
  });
  await test("before configured event rejects", async () => {
    const c = candidate(); c.match(event()); assert.equal((await configure(c)).ok, false);
  });
  await test("untrusted sender cannot configure", async () => {
    const c = candidate();
    assert.equal((await c.call({kind: "configure", session}, {id, url: "https://fixture.test"})).ok, false);
    assert.equal((await configure(c)).ok, true);
  });
  await test("dynamic session extra or missing static rules reject", async () => {
    for (const options of [{enabled: []}, {enabled: ["ws_default_deny_v1", "extra"]},
      {dynamic: [{}]}, {sessionRules: [{}]}]) {
      assert.equal((await configure(candidate(options))).ok, false);
    }
  });
  await test("unknown URL query credentials type and rule reject", async () => {
    for (const change of [{url: "wss://websocket-r3.test:8443/dnr-worker-wss?secret=x"},
      {url: "ws://user:secret@websocket-r3.test:8443/dnr-page-ws"},
      {url: "wss://other.test:8443/dnr-worker-wss"}, {type: "script"}, {timeStamp: Infinity}]) {
      const c = candidate(); await configure(c); c.match(event(1, change));
      assert.equal((await c.call({kind: "snapshot"})).ok, false);
    }
    const c = candidate(); await configure(c);
    c.match({...event(), rule: {ruleId: 2, rulesetId: "ws_default_deny_v1"}});
    assert.equal((await c.call({kind: "snapshot"})).ok, false);
  });
  await test("101 matches overflow with bounded collection", async () => {
    const c = candidate(); await configure(c);
    for (let i = 1; i <= 101; i++) c.match(event(i));
    const result = await c.call({kind: "snapshot"});
    assert.equal(result.ok, false);
    assert.ok((result.receipts || c.store.r3DnrAuditV1.receipts).length <= 100);
  });
  await test("write failure and loss reject safely", async () => {
    for (const options of [{failWrite: true}, {dropWrite: true}]) {
      const result = await configure(candidate(options)); assert.equal(result.ok, false);
      assert.equal(JSON.stringify(result).includes("secret_do_not_export"), false);
    }
  });
  await test("write hang bounded", async () => {
    const start = Date.now(), result = await configure(candidate({hangWrite: true}));
    assert.equal(result.ok, false); assert.ok(Date.now() - start < 2500);
  });
  await test("observer restart cannot erase or accept prior epoch", async () => {
    const old = candidate(); await configure(old); old.match(event());
    await old.call({kind: "snapshot"});
    const current = candidate({store: old.store}), result = await configure(current);
    assert.equal(result.ok, false); assert.equal(result.receipts.length, 1);
    assert.equal(result.fatal, "observer_epoch_changed");
  });
  await test("reconfigure/caller retry refuses", async () => {
    const c = candidate(); await configure(c); assert.equal((await configure(c)).ok, false);
  });
  console.log(JSON.stringify({offline_vm_tests: count, chrome_verified: false}));
})().catch(error => {console.error(error); process.exitCode = 1;});
