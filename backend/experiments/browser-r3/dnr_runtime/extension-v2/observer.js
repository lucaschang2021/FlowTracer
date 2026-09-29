"use strict";
// Candidate only: no Chrome execution/extension ID/receipt verified offline.
const KEY = "r3DnrAuditV2", MAX = 100, RULESET = "ws_default_deny_v1";
const epoch = crypto.randomUUID();
const nativeDateNow = Date.now.bind(Date);
let lastObserved = null;
let session = null, sequence = 0, fatal = null, configured = false;
let receipts = [], pending = 0, tail = Promise.resolve(), commands = Promise.resolve();
const bounded = promise => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("audit_timeout")), 1000);
  Promise.resolve(promise).then(value => {clearTimeout(timer); resolve(value);},
    () => {clearTimeout(timer); reject(new Error("audit_failed"));});
});
const poison = code => {fatal ||= code;};
const state = () => ({schema_version: "r3-dnr-audit-v2", session,
  extension_id: chrome.runtime.id, observer_epoch: epoch, sequence,
  fatal, configured, observer_registered: true, receipts: [...receipts]});
const persist = () => bounded(chrome.storage.session.set({[KEY]: state()}));
const enqueue = operation => {
  if (pending >= MAX) {poison("audit_overflow"); return;}
  pending++;
  tail = tail.then(operation).catch(() => poison("audit_failed"))
    .finally(() => {pending--;});
};

// Registered synchronously before storage awaits. Native execution is independent
// of listener lifetime. Any unaccounted sleep/restart is diagnostic UNKNOWN.
chrome.declarativeNetRequest.onRuleMatchedDebug.addListener(info => {
  const observed = nativeDateNow(); // synchronous callback entry before enqueue/await
  if (!Number.isSafeInteger(observed) || observed < 1e12 ||
      (lastObserved !== null && observed < lastObserved)) {poison("clock_invalid"); return;}
  lastObserved = observed;
  if (fatal) return;
  if (++sequence > MAX) {poison("audit_overflow"); return;}
  const ordinal = sequence, request = info.request || {}, rule = info.rule || {};
  if (!configured || rule.ruleId !== 1 || rule.rulesetId !== RULESET ||
      request.type !== "websocket" || typeof request.requestId !== "string" ||
      !Number.isSafeInteger(observed)) {poison("unexpected_match"); return;}
  let url;
  try {
    url = new URL(request.url);
    if (!["ws:", "wss:"].includes(url.protocol) || url.username || url.password || request.url.includes("@") ||
        request.url.includes("?") || request.url.includes("#") ||
        url.search || url.hash || url.hostname !== "websocket-r3.test" ||
        url.port !== "8443" || !/^\/dnr-(page|worker)-(ws|wss)$/.test(url.pathname) ||
        !url.pathname.endsWith("-" + url.protocol.slice(0, -1))) {
      poison("unexpected_request"); return;
    }
  } catch (_) {poison("unexpected_request"); return;}
  // Raw URL never leaves trusted observer. Query/fragment rejected, not logged.
  const fingerprintInput = url.origin + url.pathname;
  enqueue(async () => {
    if (fatal) return;
    const bytes = await bounded(crypto.subtle.digest("SHA-256",
      new TextEncoder().encode(fingerprintInput)));
    const fingerprint = [...new Uint8Array(bytes)].map(x => x.toString(16).padStart(2, "0")).join("");
    receipts.push({schema_version: "r3-dnr-receipt-v2", session,
      extension_id: chrome.runtime.id, ruleset_id: RULESET, rule_id: 1,
      action: "block", resource_type: "websocket", request_id: request.requestId,
      timestamp: observed, timestamp_source: "trusted_observer_callback_epoch_ms", sequence: ordinal, observer_epoch: epoch,
      safe_request_fingerprint: fingerprint,
      tab_id: Number.isInteger(request.tabId) ? request.tabId : null,
      frame_id: Number.isInteger(request.frameId) ? request.frameId : null,
      document_id: typeof request.documentId === "string" ? request.documentId : null,
      initiator: null, initiator_note: "omitted_to_prevent_origin_secret_exposure"});
    await persist();
  });
});

enqueue(async () => {
  await bounded(chrome.storage.session.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"}));
  const previous = (await bounded(chrome.storage.session.get(KEY)))[KEY];
  if (previous) {
    poison("observer_epoch_changed"); // keep old receipts, never silently reset
    receipts = Array.isArray(previous.receipts) ? previous.receipts.slice(0, MAX) : [];
    session = previous.session ?? null;
  }
  await persist();
});

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("audit.html") ||
      !message || !["configure", "snapshot"].includes(message.kind)) {
    reply({ok: false, code: "untrusted_sender"}); return false;
  }
  const run = async () => {
    await bounded(tail);
    if (message.kind === "configure") {
      if (configured || sequence || !/^flowtracer-r3-dnr-[a-z0-9-]{1,64}$/.test(message.session || "")) {
        poison("invalid_configuration");
      } else {session = message.session; configured = true; await persist();}
    }
    const enabled = await bounded(chrome.declarativeNetRequest.getEnabledRulesets());
    const dynamic = await bounded(chrome.declarativeNetRequest.getDynamicRules());
    const sessionRules = await bounded(chrome.declarativeNetRequest.getSessionRules());
    if (enabled.length !== 1 || enabled[0] !== RULESET || dynamic.length || sessionRules.length) {
      poison("rule_state_changed");
    }
    // Rejoin after awaits. New events must finish async hash and storage writes.
    await bounded(tail);
    await persist();
    const stored = (await bounded(chrome.storage.session.get(KEY)))[KEY];
    if (!stored || JSON.stringify(stored) !== JSON.stringify(state()) || pending) {
      poison("flush_not_confirmed");
    }
    return {ok: !fatal && configured, code: fatal, ...state(),
      enabled_rulesets: enabled, dynamic_rules: dynamic, session_rules: sessionRules,
      flushed: !fatal && pending === 0, storage_access_level: "TRUSTED_CONTEXTS"};
  };
  if (pending >= MAX) {
    poison("audit_overflow"); reply({ok: false, code: "audit_overflow"}); return false;
  }
  pending++;
  // Commands serialized separately; debug callback writes retain their own queue.
  commands = commands.then(async () => {
    pending--;
    try {reply(await bounded(run()));}
    catch (_) {poison("audit_failed"); reply({ok: false, code: "audit_failed"});}
  });
  return true;
});
