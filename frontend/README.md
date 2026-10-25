# FlowTracer Alpha v0.1 desktop

## Current status · 2026-10-24

G1–G3 passed local product acceptance at `7789fac068915d1846cfcc4d266a1da95b715f5b`: authentication, Radar/Source/collection/Signals, account-isolated Galaxy/layout persistence, Memory, Opportunities and REST notifications. The controller's final UI run passed 69/69 with zero retries; unchanged production input retains 23 unit/22 Rust tests and the locked offline desktop build. Native restart and nonempty backend/native product evidence are recorded in [G3 acceptance](../docs/FE-001-G3-ADMISSION.md). Trial users should follow the [Windows Quick Start](QUICKSTART.md); package identity, hashes and smoke status are recorded in [Release Candidate](RELEASE-CANDIDATE.md).

Browser is disabled; PLUGIN-1 is deferred. A current-user Windows NSIS candidate is configured, but installation/start smoke, Integration and Release acceptance are not claimed. Credentials remain native-memory-only; restart requires sign-in. Demo and real data stay isolated.

Current debug EXE SHA256: `3BFE40C7853FA61F8AE70FE89F678DD7302E11D0F652136C14FA058695608B1B`. This is a debug executable, not an installer.

## Historical G2 candidate record

The G2 status and older unimplemented-scope statements in this section are historical and superseded by the current status above.

Tauri 2 + React 19 + TypeScript desktop client. AUTH-01 adds a restricted native
HTTP bridge for local readiness, register/login/logout/refresh, `users/me`, Radar
create/read/edit/pause/resume/delete, and RSS/URL Source create/bind/unbind,
pagination, collect and CollectionRun polling, plus Signals list/detail/filtering.
Access and Refresh
Tokens remain in native process memory and are never returned to the WebView. The
default path is real local mode; the G1 fixture universe remains available only
through an explicit, continuously labeled Demo entry. Backend code and frozen
contracts are unchanged.

Current local branch: `feat/fe-001-g2-api`. Exact code candidate:
`74059db8d9c5f2e62e027f89c6b5b8f4d9cf49bb` (status documentation may follow in a
separate commit). CollectionRun wire, background motion/pointer and CAMERA53 are
committed locally. No push or merge.
The exact current scope and named evidence are in
[G2 admission](../docs/FE-001-G2-ADMISSION.md) and
[Current Gate](../docs/CURRENT-GATE.md); historical records below do not grant authority.

VERIFY62 on `755ba90205a1b13f8215e32c620efe941535bffb` passed all 45 Web UI
tests in one run (4.1m, zero retries). VERIFY59 on its parent had 10 passed,
1 failed and 34 not run because one older entry test expected 230s instead of the
approved 120s rotation; the single expectation fix passed before VERIFY62.
TypeScript, 15 unit tests, 20 native-bridge Rust tests and locked/offline desktop
build passed on `670c61d`. The final code candidate changes only Vitest and its dev
lock chain from `755ba90`; VERIFY67 passed 15 unit tests on Vitest 4.1.11,
typecheck/build, and full plus production-only npm audits (both zero findings).
Production dependency versions/integrities are unchanged; tinypool was removed.
No automatic audit-fix/force or install scripts were used. Real native
evidence separately includes isolated authentication and Radar operations plus FLOW31's
Source binding → collect → successful run polling → Signals list/detail path.
It uses a guarded offline fetcher and Fake AI, not live Internet collection or
proof of every worker, ownership, failure and lifecycle branch.

The latest locked/offline debug package includes background-pointer and CAMERA53;
SHA-256: `AC2A2361B02A7BBFC053C27F0AA647F26E9EFBAC809A013FE74BDB41103ACD14`.
It was built in VERIFY59, not launched for another native/auth test. Older
PACKAGE42 was used for the native pause/resume/keyboard evidence. Web tests quantify
pointer offsets and camera behavior; neither is claimed as new full native
acceptance. No test database or credentials are required to view explicit Demo.

Underlying HTTP requests cannot be truly aborted, but disposal/session generation
prevents late writeback and timer revival. Native51 has verified pause/resume,
keyboard selection/cancellation and logical focus restoration against the isolated
Backend and database; its temporary resources have been cleaned up. A small
first-Radar camera visibility fix (CAMERA53) is now included in the package and
VERIFY62. REVIEW57 closed its regression-precondition finding. SECURITY-CLOSURE69
independently confirmed the dependency P1 closed and accepted the unchanged
UI/Rust/native evidence. DOC70 identity/reference checks passed. The code candidate
is READY_FOR_G2_PRODUCT_REVIEW, not G2 product acceptance.
Memory, Opportunity pages and Galaxy
persistence remain unimplemented G3 scope. Browser acquisition stays disabled;
PLUGIN-1 is deferred and does not block frontend. Browser preview cannot use the
native bridge and never substitutes a dev proxy or CORS change. G2 product
acceptance, G3, INT-001 and Release remain unadmitted. Tutorials follow software
completion; no new onboarding flow is implemented here.

## Start on Windows

Prerequisites: Node 24 / npm 11, Rust MSVC toolchain, Visual Studio C++ Build Tools,
Windows SDK and WebView2. The task environment has these prerequisites installed.
Open a fresh PowerShell terminal if Cargo is not on PATH.

Run commands from this worktree's `frontend` directory:

```powershell
npm ci
npm run dev                 # local browser development at 127.0.0.1:1420
npm run dev:desktop         # native Tauri development window
```

Dependencies are pinned in `package.json` / `package-lock.json`, and
`src-tauri/Cargo.lock` freezes Rust dependencies. The only AUTH-01 npm addition is
`@tauri-apps/api`; direct Rust additions are the approved minimal reqwest/serde/
serde_json/tokio set. No global installs are needed.

## Current interactions

- Click a planet to open its detail panel; Escape / close returns focus to it.
- Drag a planet; a 5-pixel threshold prevents accidental click selection.
- Wheel zoom is cursor-anchored, clamped to 35–240%; node labels and hit areas
  remain screen-sized. Initial fit is computed from node bounds and viewport.
- Focus the canvas and hold Space + drag to pan; arrow keys also pan; F fits all.
- Tab + Enter selects a planet; Alt + arrow keys moves the focused planet.
- Marquee/keyboard selection creates Galaxy groups; membership, names, positions
  and view persist locally by account UUID. Disbanding never deletes a Radar.
- Real mode supports Signals, Memory bookmarks/search, read-only Opportunities
  and REST notifications. Demo remains explicitly isolated from real data.
- The shared startup/login/workspace background retains slow grid rotation and
  no mouse-follow parallax. Foreground controls and Radar coordinates do not
  follow the pointer. Quiet/system reduced motion disables decorative movement.
  Hidden-window canvas work is paused; frames/listeners are cleaned up.
- Header reset restores the isolated Demo layout. Valid stored layouts survive
  reload and native restart; real mode requires sign-in after process restart.

G1–G3 have passed local product acceptance at the code SHA above. G4 installer,
Integration and Release remain incomplete; GitHub delivery follows exact PR/merge records.
The empty demo loads fixtures; it does not create backend records.

## Architecture and original assets

`src/features/universe/model.ts` contains pure camera/coordinate functions.
`Universe.tsx` uses pointer capture and an imperative camera transform coalesced
with requestAnimationFrame; dragging does not re-render the whole React app every
frame. React receives node positions at the end of a drag. ResizeObserver fits
the viewport. Listeners and animation frames are cleaned up on unmount.

Planet textures, stars and the compass mark use lightweight SVG/CSS; the approved
background artwork is packaged locally. The main canvas is DOM/SVG
and remains sharp at desktop display scaling. Native icons derive from
`src/assets/app-icon.svg` using the installed Tauri icon command.

The WebView production CSP still denies network connections. API traffic exists
only inside typed native commands; no filesystem/network plugin permission or
arbitrary URL command is exposed. The configured origin must be explicit loopback
HTTP on `/api/v1`; redirects and proxy use are disabled.

## Targeted verification

```powershell
npm run typecheck
npm run test:unit
npm run build
$env:CARGO_HOME = "$PWD\.cache\cargo"
cargo test --manifest-path src-tauri/Cargo.toml --locked
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.cache\ms-playwright"
npx playwright install chromium
npm run test:e2e
npm run build:desktop:debug -- -- --locked
```

Native tests use owned loopback fixture servers to cover the origin/path boundary,
redirect and size refusal, safe error envelopes, rotating-refresh single flight,
logout fencing, and the ready/auth/user/Radar/logout transport path. Fixture proof
is not evidence that a real Backend and isolated `_test` database were available.

E2E tests run serially with no retries and stop on the first failure. They cover
1366×768, 1600×900 and 1920×1080, node selection/dragging, zoom anchoring and limits,
Space pan, fit/reset, navigation, empty state, modal focus and reduced motion.
Browser console errors and non-local requests fail the tests. Screenshots and
traces are generated under ignored `test-results/`; report under
`playwright-report/`. Native output is `src-tauri/target/debug/flowtracer-desktop.exe`.

Passing web tests alone does not prove native startup. The desktop executable
must additionally be launched and checked in WebView2. No installer/signing,
release, real-backend integration or full Alpha acceptance is claimed by G1.

## Historical verification checkpoints

The following entries preserve their original scope, failures and at-the-time
status. Use the current overview and named G2 admission checkpoints above for
the latest candidate; do not interpret historical pending statements as live gates.

## G1 verification checkpoint

Validation completed on 2026-10-11; handoff record finalized on 2026-10-12 after
the tool usage limit recovered. Scope: `feat/fe-001-g1`, baseline
`fc180a1d2eba32935fba6ee6c128f9b2d7015574`. No new commit, push, PR or merge.
The user removed the deadline and authorized continuing G1 defect repair and
verification. G2/G3/G4 remain out of scope.

| Check | Result |
| --- | --- |
| TypeScript | PASS (`tsc --noEmit`) |
| Camera/fixture unit tests | PASS, 10 tests |
| Production web build | PASS; 34 modules; JS 243.25 kB / gzip 77.20 kB |
| Playwright G1 interactions | PASS, 6 tests, 12.9 seconds, no retries |
| Viewports | PASS: 1366×768, 1600×900, 1920×1080; screenshots visually inspected |
| Browser console / requests | No console errors or non-local requests during E2E |
| Tauri Windows debug | PASS, locked/offline dependencies, 2m 11s initial native build |
| Native WebView2 startup | PASS: actual star-map rendering and accessible controls observed |
| Native interaction / lifecycle | PASS: Market Observatory opens, Escape closes, normal exit, reopen restores demo |
| Backend / migration | Not run / none; no backend or contract changes |

The first E2E run failed because it measured the old camera immediately after
`setViewportSize`, before ResizeObserver's rendering step. The repaired test
waits for the expected fitted camera before measuring **the same** node bounds;
the assertions were not relaxed. Original failure artifacts remain under
`test-results/universe-layout-and-screenshots-1366x768/`; passing screenshots
are under `test-results/g1-r2/`. Native rendering and interaction were verified
through the desktop window, not inferred from the browser build. Desktop overlay
apps temporarily obstructed automation; no unrelated apps or settings were
changed. The app was reopened and left visible at the end of the native check.

Native executable SHA-256, rechecked on 2026-10-12:
`D4C99E2D898E4D981684ABC397463442A8CFFF380473A91F147E9B5DF0A1B563`.
Native stdout/stderr and reopen logs are empty. Test profile and logs stay in
`.cache/`; set `WEBVIEW2_USER_DATA_FOLDER` to `.cache/webview2-g1` to keep native
verification data in this worktree. G1 does not persist user layouts.

Visual differences from the reference: original procedural SVG planets, fewer
dim stars, larger readable labels, computed initial fit instead of fixed 30%,
and no rename/disband controls masquerading as implemented features. Galaxy
details may overlay unselected planets; “适配全部行星” fits the map into the
remaining space. Formal product review is still pending.

### Changed file list (all within `frontend/`)

```text
README.md
.gitignore
index.html
package.json
package-lock.json
tsconfig.json
vite.config.ts
vitest.config.ts
playwright.config.ts
src/main.tsx
src/vite-env.d.ts
src/app/App.tsx
src/app/Icon.tsx
src/assets/app-icon.svg
src/assets/starfield.svg
src/styles/app.css
src/features/universe/Planet.tsx
src/features/universe/Universe.tsx
src/features/universe/demo.ts
src/features/universe/model.ts
src/features/universe/model.test.ts
tests/universe.spec.ts
src-tauri/Cargo.toml
src-tauri/Cargo.lock
src-tauri/build.rs
src-tauri/tauri.conf.json
src-tauri/src/main.rs
src-tauri/icons/icon.ico
src-tauri/icons/icon.png
```

G1 implementation and scoped checks complete. STOP for review; this checkpoint
does not authorize G2, commit/push/PR, merge, packaging or release.

## Frontend demo V2 — 2026-10-12

Direct user scope: preview only, no backend. This is not G2/API integration.
The startup, preview sign-in and universe now run in one app. Sign-in is an
explicit local demo identity, with no credential inputs, tokens or auth calls.
Chinese/English and reduced motion are the only persisted preferences
(`flowtracer.demo.preferences.v1`); denied/corrupt storage falls back safely.
Radar names remain unchanged. Layout changes remain session-only.

Visual direction: a quiet celestial atlas, navy mineral fields, muted brass
coordinates and ivory labels. Different planet scales establish hierarchy;
orbital lines and a planetary horizon add depth without a 3D dependency.
The existing intro emblem and its two approved segment removals are preserved;
pixel diffusion reveals letters before the emblem. All artwork stays local.
System/app reduced motion disables ambient movement and completes ink instantly.

G1 backup: `.cache/g1-before-demo-v2-20261012/` contains 30 source files and
`flowtracer-g1.exe` (same SHA-256 as the G1 checkpoint above). Original prototype
HTML was read only, not modified. No new dependencies, backend, migrations or
contracts changed. No commit, push or PR in this preview scope.

V2 changed files relative to the G1 checkpoint:

```text
README.md
playwright.config.ts
src/main.tsx
src/app/App.tsx
src/app/Entry.tsx
src/app/Preferences.tsx
src/app/Preferences.test.ts
src/app/ink.ts
src/assets/intro-emblem.webp
src/styles/demo.css
src/features/universe/Universe.tsx
src/features/universe/Planet.tsx
src/features/universe/demo.ts
src/features/universe/model.ts
src/features/universe/model.test.ts
tests/entry.spec.ts
tests/universe.spec.ts
```

Verification: TypeScript PASS; 13 unit tests PASS; production web build PASS;
8 Playwright tests PASS (30.1s) at 1366×768, 1600×900 and 1920×1080. Covers
entry sequence, bilingual persistence, denied storage, reduced motion,
drag/zoom/fit, detail panels, empty canvas and dialog focus. No external
requests/page errors in those checks. Final screenshots in
`test-results/demo-v2-final/`; earlier V2 screenshots retained separately.
The initial typecheck exposed a missing `competitive` translation, corrected
without changing the RadarType contract. Sandbox child-process EPERM required
scoped permission for local tests/builds. Visual review also corrected CSS
load order and larger-node camera padding before final regression.

Native G1 verification above does not establish V2 native UI acceptance.
V2 Windows x64 debug compilation succeeded with locked/offline dependencies
(native compile: 23.98s). The executable is updated; native V2 click-through
and reopen acceptance have not been repeated. The browser demo is the verified
interactive preview for this iteration.
This preview awaits user visual feedback; no downstream phase is opened.

### Original entry canvas restored — 2026-10-12

User correction: preserve the approved original startup canvas; do not replace
it with the upgraded workspace background. Entry now uses the original embedded
stone JPEG and orbit WebP byte-for-byte, original polar geometry/rotation timing,
145-point flowing star field, breathing highlights and original title placement.
The existing demo sign-in, language settings and workspace remain connected.
No original prototype file was overwritten; no backend connection was added.

Files in this correction: `src/app/Entry.tsx`, `src/app/OriginalBackdrop.tsx`,
`src/main.tsx`, `src/styles/original-intro.css`, `src/assets/intro-stone.jpg`,
`src/assets/intro-orbits.webp`, `tests/entry.spec.ts`, and this README.
Animation cleanup, visibility pausing and reduced-motion handling follow the
animation/UI guidance without adding GSAP or other dependencies.

Validation: TypeScript PASS, web build PASS, 3 targeted Playwright tests PASS
(25.3s). Includes original image decoding, 280s/230s rotations, changing star
pixels, intro/login/workspace boundaries, both languages and reduced motion.
Screenshot: `test-results/restored-intro/entry-approved-original-ba-d2ec7-erved-only-on-entry-screens/restored-original-intro.png`.
The workspace's existing implementation and assets were not changed by this
correction. No new commit, push or PR; visual preview remains pending user review.
Windows debug executable rebuilt successfully with locked/offline dependencies
(26.98s native compile). This correction was visually tested in the browser;
native click-through acceptance was not repeated.

### Holographic transitions — 2026-10-12

Local demo increment only: preserve the restored original entry canvas and all
backend boundaries. After demo sign-in, the star map unfolds from its center
with staggered planet reveals, expanding rings and one restrained cyan scan.
Projection finishes in 1.7 seconds; camera geometry and drag/zoom remain intact.
Page transitions use a short exit/entry fade with subtle depth. Navigation uses
the latest selected destination, cleans timers on unmount, and settles when
hidden or when reduced motion is enabled. Detail panels have a quiet projection
entrance; there is no repeated flash or loading loop. Animation/UI skill guidance
informed lifecycle cleanup and reduced-motion behavior; no dependencies added.

Changed files for this increment:

```text
README.md
src/app/App.tsx
src/app/motion.ts
src/features/universe/Universe.tsx
src/main.tsx
src/styles/motion.css
tests/entry.spec.ts
tests/universe.spec.ts
tests/motion.spec.ts
```

Verification: TypeScript PASS, production web build PASS, first full browser
regression 12/12 PASS (1.2m). After correcting login animation fill so that exit
can fade, final targeted motion checks 4/4 PASS (17.8s), including the new
mid-transition opacity assertion. These overlap the initial suite; they are not
16 distinct tests. Screenshots: `test-results/hologram-final/`. No backend,
migration, contract, dependency or original entry artwork changes. No new commit,
push or PR; this is a visual demo awaiting user feedback, not a downstream gate.
Windows x64 debug build also PASS with locked/offline dependencies (native
compile 6.88s). Native click-through/reopen was not repeated; browser interaction
is the verified preview for this increment. Baseline HEAD remains
`fc180a1d2eba32935fba6ee6c128f9b2d7015574` (no new commit).

