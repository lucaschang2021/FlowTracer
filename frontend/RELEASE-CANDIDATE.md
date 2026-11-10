# FlowTracer Alpha v0.1 · Windows Release Candidate

## Candidate identity

- Product: FlowTracer Alpha v0.1
- Platform: Windows x64
- Package: per-user NSIS installer
- Signature: **unsigned**
- Auto-update: disabled
- System service: none
- Public GitHub Release: **not published**

This is a locally verified release candidate. The installer is not stored in the repository and is not currently offered as a public download.

## Local artifact

- Filename: `FlowTracer_0.1.0_x64-interactive-tutorial-setup.exe`
- SHA-256: `DF3BC951A18E22EF0F09FD9A60E2CB032490DFB3BAC379E0CC7E83629BC6AA80`
- Code signing: `NotSigned`

The accepted installer corresponds to the pre-publication frontend worktree snapshot recorded in a 89-file provenance manifest. That manifest includes source, tests and documentation; it is not a list of compiler inputs. All 89 paths were rechecked by size and SHA-256. README, Quick Start and this release-candidate note were then updated for publication clarity; those later documentation-only edits do not change the verified installer.

## Verified behavior

- The complete guided-practice regression passed all seven steps in Edge.
- The installed Windows candidate launched with the fixed frosted sign-in panel over the star field.
- From the installed app, guided practice created a practice Radar, preserved progress after exit, and resumed at the expected step.
- A separately controlled local Integration run passed one collection, produced both analysis and opportunity notifications, changed both from unread to read, and completed strict cleanup.

The Windows smoke did not execute the complete seven-step tutorial natively. The Integration run used local fixtures and test AI; it is not evidence of public-internet acquisition or a production AI provider.

## Local live-mode requirements

Live sign-in requires a separately started local Backend at `http://127.0.0.1:8000/api/v1`. The stock Compose configuration is for trusted local development: it uses test AI providers by default and publishes port 8000 on all host interfaces. Do not expose it to an untrusted network without first restricting the binding, replacing example credentials, and configuring an admitted production provider.

Guided practice is isolated local sample data and does not require the Backend.

## Known limits

- Windows may display an unknown-publisher warning because the installer is unsigned.
- Authentication tokens remain only in native memory; reopening the app requires sign-in.
- Dynamic/Advanced Browser collection is disabled.
- Offline Fake Provider and local fixture evidence is not production-provider evidence.
- Opportunity action payloads are read-only and are never executed automatically.
- No clean-machine, uninstall, fresh WebView2 provisioning, automatic update, or code-signing validation is claimed.
- No installer upload, Git tag, GitHub Release, or formal public release has been performed.

## Reproduce source checks

From `frontend/`:

```powershell
npm run typecheck
npm run test:unit
npm run build
$env:FLOWTRACER_TEST_EDGE = '1'
npm exec -- playwright test tests/tutorial.spec.ts tests/auth-layout.spec.ts tests/source-collect.spec.ts --workers=1 --retries=0
$env:CARGO_NET_OFFLINE = 'true'
cargo test --manifest-path src-tauri/Cargo.toml --locked
```

These commands validate source behavior; producing and signing a distributable installer is a separate release operation.
