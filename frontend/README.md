# FlowTracer desktop · G2 AUTH-01

Tauri 2 + React 19 + TypeScript desktop client. AUTH-01 adds a restricted native
HTTP bridge for local readiness, register/login/logout/refresh, `users/me`, Radar
listing and the current branch-local Radar-create candidate. Access and Refresh
Tokens remain in native process memory and are never returned to the WebView. The
default path is real local mode; the G1 fixture universe remains available only
through an explicit, continuously labeled Demo entry. Backend code and frozen
contracts are unchanged.

The local AUTH/visual checkpoint is
`551d29f54aa530b6a9fc2329358c1861b42c24a5` (not pushed), with the current dirty
Radar-create candidate layered above it. Its typed native `POST /api/v1/radars`
path has Rust `api::tests` 9/9 and targeted Web coverage 4/4. One isolated native
creation returned 201, matched its database owner, and remained visible after
logout and a second login; its dedicated resources were cleaned up. This is a
bounded create/re-login result, not FE-G2 product acceptance.

Radar edit/delete/pause/resume, Sources, collection and Signals remain
unimplemented. Memory, Opportunity features and Galaxy persistence remain G3.
Native visual evidence still lacks the ink-dissolve intermediate frame, so the
visual path is not a full PASS. Accessibility debt remains P2: RadarCreatePanel
declares `aria-modal`, but background navigation can still receive keyboard focus;
future work must enforce a focus boundary and remove that dependency from the
session-race test. This is not classified as a P1 data-security defect. Browser
preview cannot use the native bridge and never substitutes a dev proxy or CORS
change. INT-001 and Release remain unadmitted.

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

## G1 interactions

- Click a planet to open its detail panel; Escape / close returns focus to it.
- Drag a planet; a 5-pixel threshold prevents accidental click selection.
- Wheel zoom is cursor-anchored, clamped to 35–240%; node labels and hit areas
  remain screen-sized. Initial fit is computed from node bounds and viewport.
- Focus the canvas and hold Space + drag to pan; arrow keys also pan; F fits all.
- Tab + Enter selects a planet; Alt + arrow keys moves the focused planet.
- The dashed Galaxy is a **static example structure**, not saved user grouping.
- Navigation switches between the Canvas and clearly labeled G1 placeholder
  pages. Settings exposes reduced motion and empty-canvas demonstration.
- System reduced-motion preferences are respected. No perpetual animation loop.
- Header reset restores the demo. Changes are session-only and disappear on reload.

G2 authentication / real Radar data and G3 grouping / persistence are deliberately
not implemented. The empty demo loads fixtures; it does not create backend records.

## Architecture and original assets

`src/features/universe/model.ts` contains pure camera/coordinate functions.
`Universe.tsx` uses pointer capture and an imperative camera transform coalesced
with requestAnimationFrame; dragging does not re-render the whole React app every
frame. React receives node positions at the end of a drag. ResizeObserver fits
the viewport. Listeners and animation frames are cleaned up on unmount.

Planet textures, stars and the compass mark are original lightweight SVG/CSS,
with no external images/fonts or copied game artwork. The main canvas is DOM/SVG
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

