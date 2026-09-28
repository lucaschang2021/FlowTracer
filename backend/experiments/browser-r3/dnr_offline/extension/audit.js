"use strict";
// Called only from trusted extension CDP context; no polling/keepalive.
Object.defineProperty(globalThis, "r3Audit", {
  value: Object.freeze({
    configure: session => chrome.runtime.sendMessage({kind: "configure", session}),
    snapshot: () => chrome.runtime.sendMessage({kind: "snapshot"}),
  }), writable: false, configurable: false,
});
