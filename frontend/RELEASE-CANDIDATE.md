# FlowTracer Alpha v0.1 · Windows Release Candidate

## Candidate identity

- Product: FlowTracer Alpha v0.1
- Platform/format: Windows x64, NSIS installer
- Install mode: current Windows user; no administrator elevation requested
- Auto-update: disabled
- System service: none
- New runtime permissions or network capabilities: none

## Locked toolchain

| Tool | Version |
| --- | --- |
| Node.js | 24.19.0 |
| npm | 11.17.0 |
| Tauri CLI | 2.12.2 |
| Rust | rustc 1.99.0 / cargo 1.99.0 |

JavaScript and Rust dependencies remain pinned by the existing lockfiles. This increment does not change dependencies or lockfiles. Tauri's bundler may obtain its pinned NSIS tooling through its built-in verified download path when the local cache is empty; no global package installation, proxy change, or security-setting change is permitted.

## Reproduce the candidate

From `frontend/`:

```powershell
npm run typecheck
npm run test:unit
npm run build
$env:FLOWTRACER_TEST_EDGE = '1'
npm exec -- playwright test tests/memory.spec.ts tests/entry.spec.ts --workers=1 --retries=0 --max-failures=1 --output=test-results/g4-rc-01
$env:CARGO_NET_OFFLINE = 'true'
npm run build:desktop:nsis -- -- --locked --offline
```

Expected installer directory: `src-tauri/target/release/bundle/nsis/`.

## Artifact

- Product code: `679b03210ae8710a1dc7fab697543e3cdb0cd9ad` (subsequent evidence-only commits do not change the binary inputs)
- Installer path: `src-tauri/target/release/bundle/nsis/FlowTracer_0.1.0_x64-setup.exe`
- Size: 3,158,992 bytes
- SHA-256: `095141123C5A18CC1C860C35584F195F99FE4EE736DBC4FFE383E7A7DF81C437`

## Smoke status

- Installer execution: **NOT_RUN**
- Installed-app launch: **NOT_RUN**
- Exit/reopen/uninstall: **NOT_RUN**

Installation and startup smoke require a separate controller-signed operation. The current operation does not install, launch, elevate, uninstall, or publish the package.

## Verification record

- RC01 typecheck, 23/23 unit tests, and 60-module Web build: **PASS**.
- RC01 targeted Edge run: **3 passed, 1 failed, 5 not run**. The new live Settings test filled the login form while the login scene was still entering and inert, then timed out waiting for Settings. This failure remains part of the record and is not described as a passing run.
- REPAIR02 updated the live Settings test to wait for the login scene to become idle, assert both controlled input values, and require the live workspace before opening Settings. Its one targeted command failed before test execution with Playwright `No tests found`; therefore Memory remained unrun and the locked NSIS build remained **NOT_RUN**. No command adjustment or retry was performed.
- Controller entry03 selected the same test by file/line: **1/1 PASS**, zero retries. Memory03 then passed one test and failed the new bookmarked-only test because its query was filled during page entry; the failure snapshot showed an empty query and the expected validation error. No production authentication or search behavior was weakened.
- Controller memory04 waits for page idle and asserts the query value, then changes the draft checkbox after submitting to prove that the applied filter snapshot is retained. The entire Memory file passed **5/5**, zero retries, including one DELETE and preservation of unrelated results. Original failures remain in their separate output directories.
- Independent source review FE-G4-CODE-REVIEW04: **ALLOW_WITH_P2**, P0/P1/P2=0/0/1 for the new production diff. It verified currentUser NSIS, no updater/new permissions, unchanged Backend/locks and account fencing. Installation remains NOT_RUN; this is not G4 acceptance.
- Controller NSIS03 compiled the optimized Release app successfully (3m01s), validated/extracted official NSIS 3.11, then failed while downloading the official nsis-tauri-utils v0.5.3 DLL with `unexpected end of file`; no installer was produced by that attempt. One separately bounded retry, NSIS04, passed using the same locked source and Cargo cache. Both official downloads passed Tauri's hash validation; makensis produced the installer identified above. Logs are retained under `logs/g4-nsis-controller03.log` and `logs/g4-nsis-controller04.log`.
- Controller's one final full UI regression at exact product commit `679b03210ae8710a1dc7fab697543e3cdb0cd9ad`: **71/71 PASS**, zero retries, 6.5m. Evidence: `logs/g4-controller-679b032.log` and `frontend/test-results/g4-controller-679b032/`. This does not relabel the earlier failed targeted runs as passing.

## Known limits

- The installer is unsigned; Windows may show an unknown-publisher warning.
- The local Backend must be migrated and ready at `http://127.0.0.1:8000/api/v1` before live sign-in.
- Authentication tokens remain only in native memory; app restart requires sign-in.
- Dynamic/Advanced Browser collection is disabled; PLUGIN-1 is deferred.
- The desktop Source form creates ordinary RSS/URL sources for Signals; it does not configure the Backend opportunity-family required to generate new Opportunity facts.
- Offline Fake Provider and local fixture evidence is not public-internet or production-provider evidence.
- Opportunity action payloads are read-only and are never automatically executed.
- P2 display consistency: overlapping a bookmark DELETE with a new search can apply the initiating callback's older filter flag to the newer search result. This is same-account display state only; no database fact or ownership boundary is changed. Repeat the search to refresh; the independent review did not run a runtime reproduction of this edge.
- The inherited native date-filter check is heuristic; the Backend remains the strict validator.
- This candidate is not INT-001 or Release acceptance.
