# R3 observation v2 — OFFLINE ONLY / BLOCKED

Base: ff70c198acb74b764435485611ec67484bcc7262. Branch:
feat/acq1-wp3-r3-dnr-v2. docs52 is effective by controller's precise PR74 merge
permission; its proposal text is historical, not a real-session license.

This is a PARTIAL offline candidate, not a runnable session or complete runtime
closure. The immutable real entry gates remain disabled. Do not run Compose,
Docker, Browser, dependency entrypoints or network probes using this delivery.

## Receipt and provenance

Independent extension-v2 has exactly five source files. Manifest permissions and
the sole static WS block rule are unchanged; only one approved extension path may
be loaded. v1 dnr_offline files/hash/history are preserved, not reinterpreted.
Snapshot schema is r3-dnr-audit-v2. Receipt has exactly eighteen fields, including
timestamp_source=trusted_observer_callback_epoch_ms. Its timestamp is captured by
a bound native Date.now at synchronous trusted onRuleMatchedDebug callback entry,
before enqueue/hash/await. It denotes observation, NEVER request/match time.
The real-shaped API double has no request.timeStamp.

Typed collector rejects v1, unknown/secret fields, invalid types/sources/fingerprints,
and cumulative sequence/request receipt rewrites. Safe metadata remains nullable;
no WorkerID is invented and CDP/DNR IDs are not assumed equal. Model validator
requires strict start <= receipt_observed <= terminal <= end and <=5000ms.
Late callbacks/time reversal/wrong units/float/bool/NaN or ambiguous associations
are refused, never rescued by flush time or tolerance.

Observer/fixture epoch milliseconds, CDP monotonic seconds and host monotonic
nanoseconds remain distinct domains. Host-bracketed trusted audit clock samples
prove only ordering; cross-realm epoch consistency remains UNKNOWN. Neither a
finite anchor nor a caller Boolean grants a real clock mapping.

## Inventory source limit

Only the controller-approved chrome://extensions/ diagnostic path is implemented
as a read-only CDP candidate with disabled/terminated options and fixed version
check. Raw results are neither logged nor accepted as complete inventory.
Pinned151 schema lookup failed once; HEAD IDL was also unavailable. No failed
request was retried and no id/state/type/location schema was guessed. The
HEAD implementation does not prove pinned151 coverage; UI filtering cannot
prove all installed objects. The adapter therefore safely returns UNKNOWN.
This is an explicit hard blocker, not a completed inventory implementation.

Official evidence consulted:
- [DNR API](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest):
  debug request and MatchedRuleInfo are different structures.
- [developerPrivate HEAD](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/browser/extensions/api/developer_private/developer_private_functions.cc):
  mechanism only, not pinned151 schema or filter coverage.
- [CDP Network](https://chromedevtools.github.io/devtools-protocol/tot/Network/):
  separate protocol time domains, not synchronized epoch proof.

## Runtime closure limits

Native fixture Page/HTTP Worker arms now record controlled application epoch
points; their timestamps are not DNR authority. Existing 5s terminal budgets and
pong/terminate remain. TLS generation source uses the prior local fixture mode,
fixed image-local openssl argv, isolated /tmp/r3-tls and 0600 key; key bytes are
never committed/logged. Actual cert hash/key file identity and image identity
remain null, not generated offline.

Tracked R2C-A4 DNS pure interfaces are reused, with audit omitting raw query names.
No new dns.py is needed. Prior R2C DNS used sysctl=0; this candidate does NOT copy
it. Non-root port53 binding without root/cap/sysctl is UNKNOWN and must refuse if
not established. Existing internal Redis PING is the only control connection.
Proxy remains 405+close for plain WS, independent CONNECT403, zero WS upstream/
relay; no new port/allow. Reader failure latch and bounded CLI output are retained.

Supervisor can render limited exact phase/create candidates, but dependency
mounts, dual-network attachment, actual phase/profile sequencing, full actual
effective argv, kernel DNS bind, identity and real lifecycle proof are unfinished.
These candidates are not executable launch manifests. Compose preserves hardening
and uses only the new five-file extension path; all process entrypoints reject.

Phase rendering additionally requires an independent controller-approved manifest
raw digest BEFORE JSON parsing. The external approval reader currently hard-refuses;
record path/bytes/controlcommit/session binding are not issued. Offline tests alone
inject a SYNTHETIC authority; manifest self/caller hash/proven flags are not approval.
Root, manifest and every source parent/leaf must be link/reparse-free and resolve
strictly inside the approved root; same-byte external files are not authorized.
The static path/hash manifest is not complete admitted executable closure. Known
missing actual inputs remain null/UNKNOWN in execution_plan.json, not fake values.

## Offline verification only

Use explicit PYTHONPATH including this directory and the approved dnr_offline
contract/guard modules. New tests cover realistic debug API, before-await frozen
time, strict source/order rejection, inventory refusal, alias/reader failure,
command candidates and hard-disabled entry. Old unchanged v1 suites are not rerun.
Node VM/fake CDP/process/streams do not prove native DNR, clock/inventory or cleanup.

R3 remains BLOCKED. No R4/formal WP3/downstream admission. Independent review,
source/schema resolution, exact runtime closure and a new controller session
license are all required before any real execution.
