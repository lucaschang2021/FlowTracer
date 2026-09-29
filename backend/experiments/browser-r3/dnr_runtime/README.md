# R3 DNR runtime adapters — OFFLINE ONLY / NO-GO

Actual branch base is `7d95a87cf6d1a5fd905cb30014be6a5d16723c2a`, tree
`bcf58afbbe77ea8fe67a1ea3cc76ba16fcba3c4f`. Controller authorized same-tree startup
against remote merge `5b0f3cab93845265cf10e495e2301f124a3151de`. During startup,
shared local origin/main was observed at that exact merge and its tree/ancestry
verified read-only; this task did not fetch again or alter refs. Future delivery
must still recheck then-current main/merge compatibility.

Seven implementation files only: collector/probe/supervisor/fixture/proxy,
compose and injected offline tests. No generic Browser framework or new product
API. Original five extension files, prior candidate code and evidence unchanged.

Collector uses browser CDP pipe target discovery followed by an actual extension
audit page CDP session, trusted origin/runtime.id/manifest, enabled ruleset,
empty dynamic/session rules, observer/flush/epoch and bounded cumulative receipts.
Target enumeration is NOT complete installed extension inventory. Independent
exclusive-profile/RO-mount/flags evidence is a necessary interface precondition,
not computed kernel evidence. Inventory's frozen system source is still absent;
`require_inventory()` always UNKNOWN. DNR/system/controller clock mapping has no
reviewed unit/synchronization/error proof; `ClockEvidence` validates finite typed
anchors but always refuses conversion. Thus no actual target permission exists.
No arbitrary clock tolerance, fake component list or caller-supplied True grants it.

The actual close adapter requires context.close completion, disconnected event,
browser.is_connected false and page.is_closed true. It must be used under Guard's
independent 5s timer, preceded by 15s preflight and child guard before DynamicSession.
The host ParentSupervisor arms before create/start, bounds Docker CLI time/output,
checks exact ID/name/session ownership, kills only owned running container and
requires rm plus exact daemon-view absence. All current tests inject a fake daemon;
no real cleanup or process-reap proof exists. Real Docker launch is refused because
full approved create argv/image/mount inputs are not yet frozen. Natural exit/ACK
never upgrades receipt/identity/R3 result. Child and proxy/fixture entrypoints are
explicitly non-runnable NO-GO until orchestration is reviewed; no environment switch
or CLI flag currently enables the real Browser path.

The proxy adaptation is experiment auditing only, not a formal product contract
change. Non-CONNECT returns original 405+close. Valid plain WS absolute request
requires exact host/8443, unique/unfolded ASCII headers, matching Host and upgrade,
known safe path, no userinfo/query/fragment. Audit exports actual method, validated
host/port and SHA256 of canonical safe path, never raw URL/headers. Invalid requests
stay denied and uncorrelated. Controlled WS CONNECT remains 403 with no socket or
relay. Other syntactically valid CONNECT delegates only to the explicitly mounted
tracked R2C-A4 source (same fixed-fixture double-pass/peer policy), with the already
frozen R3 navigation fixture hostname; no WS forwarding/allow/new port.

Fixture serves only navigation and genuine HTTP(S) worker script. Page and Worker
source uses native new WebSocket and bounded 5s terminal; no constructor wrapper,
Blob worker or JS deny injection. It never accepts WS upgrade; any received upgrade
is counted as an adverse fact. These are NOT DNR-authoritative receipts.

New input closure excludes every old untracked r3/r3_a2 file, all 45 historical
diagnostic dependencies, caches and evidence. Approved old contract/harness/validator
and five extension sources are separately listed; the only additional executable
base dependency is tracked R2C-A4 proxy. Runtime mounts are explicit flat module
names, not hidden sys.path. Host fake tests use explicit PYTHONPATH for approved
offline modules, because source directories are not installed packages.

Remaining NO-GO items: reliable system component/non-component inventory; reviewed
clock-unit/anchor/mapping proof; actual measured identity/close/reap/receipt evidence;
complete real phase/create-argv/image checking and dependency/TLS/DNS/control-client
orchestration. Compose is an offline, hardening-preserving mount proposal, not a
usable startup recipe. TLS cert generation/input authority and actual phase env
are null. No old image authority is claimed to cover new source/mount/argv. Hash
review and independent real-session permission are still mandatory.

Affected offline command (only existing tools, repository root):

```powershell
$env:PYTHONPATH=(Resolve-Path backend/experiments/browser-r3/dnr_offline).Path
py -3.13 -m unittest discover -s backend/experiments/browser-r3/dnr_runtime -p test_runtime_adapters.py -q
backend/.venv/Scripts/ruff.exe check --no-cache backend/experiments/browser-r3/dnr_runtime
backend/.venv/Scripts/ruff.exe format --check --no-cache --quiet backend/experiments/browser-r3/dnr_runtime
```

Do not run Compose/Docker/Browser on the basis of this file. No local commit yet
authorized until controller approves the proposed exact whitelist.
