# R3 DNR candidate — OFFLINE ONLY

Base: `fc58ea9eb9d7c723a4608c57be3495db8ea796b6`.
Branch: `feat/acq1-wp3-r3-dnr-offline`. No commit/push/PR/session authorized.

The five extension files implement exactly docs/51's manifest and static rule.
`execution_plan.json` separates old image identity from proposed readonly mount
and two extra flags. Actual extension ID, ruleset readback, observer epoch and
effective Chromium argv are **null/unverified**, not synthesized from Node tests.

`observer.js` registers the debug listener synchronously, uses only trusted
`storage.session`, and accepts messages only from this extension's exact internal
audit page. No content script, external message, webpage console or URL/body log.
Each async hash/storage step has a 1s deadline; debug writes and audit commands
are serialized with a 100-operation/receipt bound. A restart preserves prior
receipts but poisons the new epoch. Unknown request, timeout, overflow, changed
rules or non-confirmed flush fail closed. No keepalive or infinite observer loop.
The native rule does not require a continuously awake service worker. Missing
diagnostic evidence still forbids a successful capability classification.

`audit.html` loads only local `audit.js`, which exposes configure/snapshot on the
extension page. A future trusted browser-side CDP collector must discover and
verify the actual extension target/ID/path and read this page, not trust fixture
messages. The collector is deliberately **not implemented or executed here**.

`harness.py` is a non-launching lifecycle candidate and simulation entry. The
120s timer must be armed **before** the injected fetch/DynamicSession start;
15s setup and 5s confirmed-close timers are independent. Reject latches before
closing the entire persistent context/browser. The close adapter may return
literal True only after trusted closure confirmation. Rejection always invokes
a nonreturning terminal, even after confirmed close; a normal Exception alone
is never the safety barrier. `child_guard_candidate()` defines (but does not
invoke) a daemon Timer + `os._exit(78)` fallback, avoiding Scrapling's swallowed
Exception and callback-to-goto fallthrough. External independent parent/container
stop-before-launch is still mandatory to bound hung child setup and reap Chrome.
No caller retry; no successful model result overrides R3 BLOCKED.

Tests use injected timers/close/kill and a Node VM Chrome API double only.
They **do not prove** real context closure, DNR execution, extension loading,
container reaping or trusted receipt provenance. No actual Scrapling import,
Docker call, Browser, network, dependency install or formal/full regression.

Model validator separates Chrome DNR IDs from CDP IDs. Fingerprint + arm + time
window must uniquely associate four ws/wss page/worker receipts. Mock/ACK,
fixture authority, missing liveness/terminal, wrong/duplicate/ambiguous records,
epoch/flush loss, proxy attempt/relay/allow, missing independent 403 or fixture WS
acceptance all reject. Its best result is OFFLINE_MODEL=ACCEPTED, never R3 PASS.

Real-start decision: **NO-GO** pending controller hash review, exact runtime
collector/close/parent-supervisor input freeze and separate session permission.
Current CONNECT-only proxy's plain-ws baseline semantics must be adjudicated
before stage 2 if it cannot produce the frozen controlled deny; no proxy change
or ws port exception is made here. New HTTP worker fixture/path producer is not
implemented; stage-2 code/input must be separately frozen, not substituted with
the historical cooperative blob worker. No claim about Shared/Nested/SW, cache,
first-script barrier or formal nine-surface R3 coverage.

Offline commands (repository root, using installed tools only):

```powershell
py -3.13 -m unittest discover -s backend/experiments/browser-r3/dnr_offline -p test_dnr_offline.py -v
backend/.venv/Scripts/ruff.exe check --no-cache backend/experiments/browser-r3/dnr_offline
backend/.venv/Scripts/ruff.exe format --check --no-cache --quiet backend/experiments/browser-r3/dnr_offline
git diff --check
```

`execution-inputs.json` lists real path/SHA256 of new static inputs and existing
R3 Python/config dependencies (fixture/proxy included). It excludes itself to
avoid circular hashing; report its independent SHA separately. No old image
authority or historical evidence/seal is altered.
