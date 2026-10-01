# R3 composite v1 — OFFLINE ONLY

Control: main@6128d4c3bbdbcdfa036be745d35dc37117004495, GOVERNANCE-V2 section 11.
Artifact parent: 0de2d5658832b667aa00a5a8e73350a06b285bbb. No old dirty runtime imports.

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

## Real wiring still required before any execution permit

1. Host pins exact published candidate, raw input/plan/fixture/validator digests, unique
   execution ID, concrete image and unchanged R1E PR66/R2C A4 PR68 identity/topology.
   Payload 5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b;
   manifest f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8.
   Host verifies actual process/executable/runtime and supplies trusted immutable evidence;
   a page, constant, Boolean or synthetic collector cannot issue that authority.
2. Implement a separately reviewed host adapter for genuine DynamicFetcher.fetch only.
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
   fixture-r3.test:443 is a proposed label, NOT a license or topology change. All other hosts
   deny. Budget 20 requests/4 pages/5 MiB are proposed experiment bounds, not operator policy.
   Approve actual limits against Network/Site/Resource policy before running. Native port
   interface is referenced only, never imported from dirty files or modified.
6. Add trusted host network-audit completion and owned cleanup adapters with bounded deadlines.
   Current supervisor is pure rules, not a working process reaper. No real PASS path exists.
   Exact runtime permit and these adapters require independent review/new written task.

## Hash closure and publication

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
