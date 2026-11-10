# FlowTracer Alpha v0.1 · Windows Quick Start

FlowTracer is a local Windows desktop client. Live sign-in and collection require a separately started local Backend at `http://127.0.0.1:8000/api/v1`. The guided practice is local sample data and can be used without a Backend.

## Before you start

- Windows x64 with Microsoft Edge WebView2 Runtime.
- The unsigned Alpha installer described in [Release Candidate](RELEASE-CANDIDATE.md). Windows may show an unknown-publisher warning.
- For live mode only: Docker Desktop, Docker Compose, this repository, and the Backend configuration in [Alpha Operations](../backend/ALPHA-OPERATIONS.md).

The repository's stock Compose file is for local development and offline evaluation. It uses test AI providers by default and publishes port 8000 on all host interfaces. Do not expose that configuration to an untrusted network. Review and restrict the port binding, replace example credentials, and configure an admitted production provider before any non-local use.

## Learn the interface without a Backend

1. Install and open FlowTracer.
2. Choose **开始交互教程 / Start interactive tutorial** on the sign-in screen.
3. Follow the seven on-screen steps to create a practice Radar, bind a sample Source, collect a sample Signal, bookmark it, search Memory and save a note, inspect a read-only Opportunity payload, and mark the practice notification as read.
4. Practice data stays in the isolated local practice space. It is labeled as sample data and is not written to a real account.

The complete seven-step flow passed the Edge regression suite. The installed Windows candidate was also checked for practice entry, Radar creation, exit and resume; that Windows smoke was not a complete seven-step native run.

## Live mode for developers

The stock Compose configuration is not an end-user deployment recipe: API 8000, PostgreSQL 5432 and Redis 6379 are published on all host interfaces, development credentials are present, and the default AI provider is for testing. Do not start it as a public or shared-network service.

Developers who need live mode must first create a locally restricted configuration and follow [Alpha Operations](../backend/ALPHA-OPERATIONS.md) and the [Backend development guide](../backend/DEVELOPMENT.md). Start the desktop app only after the local API, database, Redis and Worker are healthy. Then register a local account and sign in. Tokens stay in native process memory, so reopening the app requires signing in again.

## First live workflow

1. Create a Radar.
2. Open its Sources panel, choose **Signals** or **Opportunity** as the Source purpose, create a supported RSS or static URL Source, and bind it.
3. Start one collection and wait for the run result.
4. Review Signals, bookmark a document, search Memory, and save notes.
5. Review Opportunities and their read-only action payloads. FlowTracer never submits, bids, purchases, messages, or executes those payloads automatically.
6. Review and mark in-app notifications as read.

## Evidence boundaries

- The verified local Integration run used controlled local fixtures and test AI. It does not prove public-internet collection or a production AI provider.
- Dynamic/Advanced Browser collection is disabled; use only admitted static RSS/URL paths.
- Opportunities and action payloads are read-only. External execution is disabled.
- The installer is unsigned and is not attached to a public GitHub Release.
- This branch is Alpha release preparation, not a formal public release.

## Troubleshoot

If the app reports that the local API is unavailable, verify both health endpoints, confirm migrations completed before API/Worker startup, confirm the Worker is healthy, then restart the desktop app and sign in again. Do not weaken the fixed loopback address, native command allowlist, redirect refusal, or CSP as a workaround.
