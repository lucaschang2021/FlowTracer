# R3 observation v2 — OFFLINE ONLY / BLOCKED

Internal source-preflight base: 8f5fcc6d70c152616440eb340c7186bd64b690ba.
Branch: feat/acq1-wp3-r3-internal-source. docs52/docs53 and the controller's
specific host-interface/setup-completion decisions govern this offline delivery.

The fixed internal-page runner is implemented but has no issued execution approval.
Do not run Docker/Browser or the old network-mode Compose using this delivery.
Legacy target/four-arm entry gates remain disabled; source-preflight always returns
target_permission=DENIED. Native execution needs independent review and a separate
exact controller approval. Offline doubles do not prove Browser behavior.

## Fixed internal source-preflight

The sole host entry is `supervisor.source_preflight(approval: HostApproval) -> dict`.
`HostApproval(record_path, record_raw_sha256, control_commit, record_data)` is a
frozen consumption object created ONLY by the independently reviewed controller
program `D:\FlowTracer\.r3-control\source_preflight_controller.py`. It reads ONLY
`D:\FlowTracer\.r3-control\source_preflight_approval.json`; raw SHA256 is checked
before strict JSON parsing, then exact schema/types/session/phase/plan are bound.
The approved host program fixes these constants in its source, never CLI/env.
Backend neither generates those two files nor invents their digest or control commit.
Python object type does not authenticate hostile same-user callers; the trust root
is the separately frozen host source and constants. No reflection/signature framework
or prod test-double activation exists. A missing record rejects before Docker calls.

The record schema is exactly `r3-source-preflight-approval-v1`, mode source-preflight,
candidate_commit, manifest_raw_sha256, plan_raw_sha256, image_id, both frozen R1E
digests, control_commit, session, phases=[baseline,enabled], launches_per_phase=1
(never bool), and target_permission=DENIED. Extra fields, duplicate JSON keys,
non-finite JSON, wrong hashes/phase/session/commits and changed Git blobs reject.
The controller fills the final candidate SHA, manifest/plan raw digests, exact image
ID, its independent control commit, unique session and approval raw digest after review.
The image is selected solely from this independently approved value: `$IMAGE` is
not embedded as a new self-hashed image authority in the candidate. R1E recipe and
full CfT151/Playwright1.62/Scrapling0.4.15 remain locked; no build occurs here.

`execution_plan.json` is a deterministic fixed command/mount/options template;
only `$ROOT`, `$SESSION`, `$IMAGE` substitutions exist, with no shell. The manifest
hashes source/test/config bytes; plan mount hashes cover only mounted runtime inputs,
avoiding a plan/manifest self-hash cycle. Host checks raw bytes against approved
Git blobs and the exact Backend repository root before launching anything.

Each predeclared baseline/enabled phase creates one fresh container/profile, using
network=none, UID10001, read-only root, cap-drop ALL, no-new-privileges, PID128,
768MiB, 1CPU, restart=no and bounded /tmp tmpfs. Baseline mounts seven Python
inputs and no extension; enabled adds only the five unchanged extension-v2 files,
all read-only. No proxy/DNS/Redis/fixture/TLS/HTTP Worker/WS arms are started.
The two allowed Docker Desktop mount source representations are fixed per-file
in the plan; any other representation rejects rather than guessing equivalence.

Parent 120s supervision precedes create. The parent calls real create/inspect/
start/wait/logs, cross-checks image/argv/resources/namespace/mount bytes, requires
natural exit0 with stopped PID namespace, reads a bounded safe observation, then
removes only exact session-owned IDs and verifies absence. Preexisting names or
foreign labels are never cleaned. A lost create response is resolved only by the
prechecked exact name plus matching labels/ID. Failures never start the next phase.
A session cannot be reused in the same host process; the single-use reviewed host
entry must also prevent relaunch across host processes. There is no automatic retry.

The child calls the locked `DynamicFetcher.fetch('about:blank', retries=1, ...)`.
Only its real page_setup hook performs observation (initial URL must be about:blank).
The source hook has a 15s watchdog and a 5s confirmed whole-browser close. Only after
close may the exact internally issued `SourcePreflightCompleted(BaseException)`
escape the driver's Exception-only handlers, preventing later goto/action/Response
parsing. This is a setup-interrupted diagnosis, not a normally returned fetch Response.
Skipped/swallowed/forged/subclass signals, unexpected fetch return, deadline latch,
ordinary exceptions, other signals and failed close cannot produce success.

Safe observations include locked Browser product, argv digest and approved flag/
profile subset when readable, extension ID/static rule and runtime ruleset readback,
UI-filtered inventory id/state/type/location projection, and repeated native clock
samples in about:blank/audit/accessible extension Worker with host monotonic bounds.
No full argv, raw inventory, target URI/body, prompt or secret is exported.
Inventory/schema completeness and cross-realm equivalence stay UNKNOWN; DNS stays
NOT_TESTED_NETWORK_NONE. SOURCE_OBSERVED means observations plus verified cleanup;
UNKNOWN source facts can be retained, while identity/boundary/timeouts/cleanup violations
produce BLOCKED. Both outcomes keep target_permission=DENIED and R3 BLOCKED.

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

The legacy network-target supervisor can render limited phase/create candidates, but dependency
mounts, dual-network attachment, actual phase/profile sequencing, full actual
effective argv, kernel DNS bind, identity and real lifecycle proof are unfinished.
Those network-mode candidates are not executable launch manifests. Their Compose
and dependency entrypoints still reject. The separate source-preflight runner above
does not consume that Compose or attempt to resolve its DNS/network prerequisites.

Phase rendering additionally requires an independent controller-approved manifest
raw digest BEFORE JSON parsing. The external approval reader currently hard-refuses;
record path/bytes/controlcommit/session binding are not issued. Offline tests alone
inject a SYNTHETIC authority; manifest self/caller hash/proven flags are not approval.
Root, manifest and every source parent/leaf must be link/reparse-free and resolve
strictly inside the approved root; same-byte external files are not authorized.
The static path/hash manifest does not replace the unissued host/image/session
authority or actual inspect/clock/inventory/cleanup observations.

## Offline verification only

Use explicit PYTHONPATH including this directory and the approved dnr_offline
contract/guard modules. New tests cover realistic debug API, before-await frozen
time, strict source/order rejection, inventory refusal, alias/reader failure,
command candidates and hard-disabled entry. Old unchanged v1 suites are not rerun.
Node VM/fake CDP/process/streams do not prove native DNR, clock/inventory or cleanup.

R3 remains BLOCKED. No R4/formal WP3/downstream admission. Independent review,
source/schema resolution, exact runtime closure and a new controller session
license are all required before any real execution.
