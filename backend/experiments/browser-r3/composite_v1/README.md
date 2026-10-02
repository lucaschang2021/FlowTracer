# R3 composite v1 — OFFLINE ONLY

H1 control: main@a215051d2a2f53b41d9b22339f1bab52a27dbdf7, GOV-2.1.
Increment parent: a3980682b7fd306f130250978c3ef6dade224233. No old dirty runtime imports.

## Boundary and commands

Import and default CLI do not read files or start external I/O. Run only:
`backend/.venv/Scripts/python.exe -B backend/experiments/browser-r3/composite_v1/test_composite.py`
from repository root. Standard-library unittest, no installation, no business suite.
Every positive sample is SYNTHETIC. `SYNTHETIC_ACCEPTED_NOT_R3_PASS` is not runtime evidence.
Real validator and launch remain NO_GO even for caller-supplied authorized=true.
This artifact can only be reviewed as OFFLINE HARNESS READY; R3 stays BLOCKED.

## Closed schema and semantics

contract.py and validator.py are the internal schema, not public DTOs. Unknown fields,
duplicate JSON keys, invalid types/IDs, non-finite numbers, cross-execution/request receipts,
repeated/conflicting IDs, clock sequence collisions, wrong driver/source, missing matrix,
timeout and incomplete cleanup/audit reject with closed safe codes. IDs are bounded tokens;
hashes are lowercase SHA hex. No URLs/query, body, argv, credentials or raw inventory fields.
All observations explicitly join execution, trigger, decision, actor and request. Vendor
transport IDs are distinct mappings, never assumed equal to application/DNR/CDP IDs.
Order is checked within app clock only; network clocks are separate and not compared by time.
Denied SW registration prevents update/fetch: no fabricated child request/transport exists.
Default-deny direct surfaces require application denial plus host-owned no-egress mapping;
proxy independent denial, JS error or absence alone cannot satisfy them.

## Code wiring and remaining host boundary

`launch_real` first calls argument-free host_session, which unconditionally refuses because
no exact host record has been frozen. Only after that boundary would it lazy-import locked
Scrapling DynamicFetcher and call the shared driver wiring. Nothing imports the runtime at
module level. Internal `_execute_driver` is a hook unit, not a permission entrypoint: offline
tests inject only StubHost/fetch; its result WIRING_RETURNED_NOT_R3_PASS is not runtime evidence.

Implemented: host runtime verification and parent-deadline ports before fetch, policy hook
installation before normal driver navigation, local URL scope, mandatory Operator policy
checks, cumulative request/page/fixture-byte reservation before forwarding, application IDs
in headers with explicit redirect-object linkage, HTTP download rejection, page WS close,
normal page_action composite operations, worker ready/attempt verification port, native
parent linkage, coverage check, host network verification, and finally owned cleanup port.
Each absent observation/adapter, scope/Operator failure, timeout, swallowed callback fault,
duplicate mapping or cleanup fault refuses. No Browser process is run by the offline suite.

Critical remaining host implementations are deliberately not claimed complete:
- install_native_denials must actually enforce/observe dedicated-worker WS, popup and SW
  pre-creation denial. Context HTTP/WS routes do not prove worker/native coverage. No DNR
  loader is invented; any existing DNR code must be supplied as exact reviewed Git bytes.
- attest_worker_attempt must bind real worker ready+attempt+native denial to the actual actor.
- network_receipts must supply host-verified proxy/fixture/denial receipts. Implemented
  join_network_receipts enforces exact execution, request, route, parent, actor, byte count,
  source/outcome and unique vendor mapping; it validates linkage, not authority authenticity.
  Accepted CONNECT proxy logs do not provide per-decrypted-request identity; absence, timing,
  JS exception and proxy fallback are insufficient. It must refuse until that join is available.
- host-owned exact permit, runtime observation, bounded supervision and reap remain external
  HostPort responsibilities. There is no self-signed authority or Boolean permission bridge.

Current fixed driver options come from accepted R2C-A4 browser_probe and tracked dnr_runtime
probe Git blobs: full Chromium executable, controlled proxy, retries=1, lazy DynamicFetcher,
page_setup/page_action and ignore_https_errors for local fixture. The four R2C flags are
preserved verbatim. No extension is inferred or silently enabled; exact native inputs remain
to be frozen. Because
native guards and HTTP tunnel correlation lack actual host bindings, this is a partial real
adapter candidate, not a ready-to-run session or closed R3 invariant.

## Before any execution permit

1. Host pins exact published candidate, raw input/plan/fixture/validator digests, unique
   execution ID, concrete image and unchanged R1E PR66/R2C A4 PR68 identity/topology.
   Payload 5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b;
   manifest f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8.
   Host verifies actual process/executable/runtime and supplies trusted immutable evidence;
   a page, constant, Boolean or synthetic collector cannot issue that authority.
2. Bind the reviewed host ports for genuine DynamicFetcher.fetch only.
   page_setup installs NetworkPolicy/SitePolicy/scope and cumulative budget before driver
   navigation; page_action triggers fixture operations. No about:blank early completion,
   direct Playwright driver, inventory-page prerequisite or public target URL.
3. B: driver navigation, iframe/script automatic loads, explicit XHR/fetch and redirect-start
   -> redirect-end. Each hop gets an actual trigger/request ID. C: page and dedicated-worker
   WS, download click, popup creation, SW registration. Reject popup/SW before capability
   creation; update/fetch get PREVENTED_BY_DENIED_PARENT only with verified registration deny.
   Worker script startup/readiness and WS attempt must be attested, not just HTML existence.
4. Freeze adapter mapping of app hooks and any DNR/native events to transport/fixture IDs.
   Observe application prevention separately from proxy safety backstop. If DNR is necessary,
   require actually bound runtime/extension observations; do not assume it is loaded.
   Per-request host correlation includes explicit parent/hop, no timing-only inference.
5. R2C isolated local fixture and exclusive controlled proxy, no host socket/network/direct
   Internet/system DNS. Fixed host/route allowlist and fixture exception approved separately;
   navigation-r3.test:8443 aligns with existing local R3 fixture; it is NOT a license. Other hosts
   deny. Budget 20 requests/4 pages/5 MiB are proposed experiment bounds, not operator policy.
   Approve actual limits against Network/Site/Resource policy before running. Native port
   interface is referenced only, never imported from dirty files or modified.
6. Supply trusted host network-audit completion and owned cleanup ports with bounded deadlines.
  Current supervisor provides an offline-tested reaper protocol, not an actual host executor.
  No real PASS path exists.
   Exact runtime permit and these adapters require independent review/new written task.

## Hash closure and publication

## H1 offline increment (IMPLEMENT-03)

H1Host is connected to the same internal driver interface: verify_runtime before fetch,
root Browser.getVersion/getBrowserCommandLine in page_setup before hooks/navigation,
and owned cleanup in finally including prelaunch rejection. It delegates H2 ports without
claiming they exist. The host-input projection checks exact raw record digest, candidate
Git/raw ten-file equality, manifest leaf SHA256/Git blob closure, plan/input hashes,
image, container ID/name/session, R1E payload/manifest and R1E/R2C references, purpose,
and typed consume-once acknowledgement. Legacy purpose and Boolean input reject.
This projection is NOT a newly approved host record format or permission issuer.
Actual host record path, candidate, concrete image and topology remain unfrozen.
host_session/launch_real still reject unconditionally, regardless of args/environment.

OwnedWatchdog arms independently before prelaunch reads. Composite deadline includes
setup/action/receipt reads, at most 15 seconds; guarded callbacks/reads get remaining
budget minus 1 second, capped at 5 seconds. Root CDP stays on driver thread; watchdog
only operates on the exact owned container. Parent cap is 120 seconds including
cleanup at most 30 seconds; every host operation receives remaining timeout capped
at 5 seconds. Identity is rechecked before kill and remove; wait and absence are
required, not context close or a caller closed flag. Cleanup failure stays unknown,
never successful and never automatically retried. Executor MUST enforce its operation
timeouts; no concrete host executor is supplied or attested by these synthetic tests.
The timer cannot make an arbitrary blocking Python executor safe. That remains a
host binding/review requirement before any execution permit.

Synthetic tests exercise driver integration, replay refusal, input/raw drift, old
purpose refusal, two-stage root identity, wrong profile/context/thread/transport,
independent timer cleanup, foreign-owner no-delete, kill/wait/remove/absence failure,
remaining deadline and prelaunch-failure cleanup. All injected facts are SYNTHETIC.
Native worker/popup/SW observation and trusted proxy/fixture correlation remain H2 gaps.

### Hash closure

execution-inputs.json hashes eight leaf files by raw SHA256 and Git blob SHA1 (LF bytes).
execution-plan.json binds the raw input manifest SHA256. To avoid circular self-hashes,
manifest/plan are NOT self-listed; exact candidate Git tree binds all ten, and their raw
digests are reported separately. Verify staged Git blobs against leaf raw bytes before commit.
No external imports beyond stdlib/local whitelist; old Plan A and historical assets excluded.
GitHub must cherry-pick ONLY the artifact increment onto a clean latest-main publication
branch, verify ten paths/raw bytes, then independently review that exact head. No push/PR here.

## Telemetry

Implementation/review/wait/governance timing is reported by the developer, not measured by
runtime code. Unknown intervals UNKNOWN. Runtime executions=0; authority reproofs=0;
business full-suite runs=0. Never derive resource/runtime success from synthetic unit tests.
