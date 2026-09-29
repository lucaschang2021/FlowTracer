"use strict";
const nativeDateNow = Date.now.bind(Date);
// Called only from trusted extension CDP context; no polling/keepalive.
Object.defineProperty(globalThis, "r3Audit", {
  value: Object.freeze({
    configure: session => chrome.runtime.sendMessage({kind: "configure", session}),
    snapshot: () => chrome.runtime.sendMessage({kind: "snapshot"}),
    clock: () => ({source: "trusted_extension_native_date_now_epoch_ms", epoch_ms: nativeDateNow()}),
  }), writable: false, configurable: false,
});
