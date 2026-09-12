# Browser R1C full-Chromium compatibility evidence

This directory is an isolated remediation artifact. It does not change or
import the historical R1/R2/R3 harnesses, default Compose, API, worker, Router,
RawItem pipeline, schema, or migrations.

Locked inputs inherited unchanged from R1:

- Python base digest: `python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca`
- Python 3.13.15; Scrapling 0.4.15; Patchright 1.62.3; Playwright 1.62.0
- Debian Bookworm snapshot `20260824T000000Z`
- BuildKit v0.32.2 image digest
  `sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8`
- Dockerfile frontend 1.7 digest
  `sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e`

R1C changes only the engine artifact selection from `--only-shell chromium` to
the complete, revision-locked `chromium` payload. The expected executable is
`/opt/browser-r1c/chromium-1234/chrome-linux64/chrome` and its reported version
must be `Google Chrome for Testing 151.0.7922.34`.

Run once from the repository root:

```powershell
py -3.13 backend/experiments/browser-r1c/run_r1c.py
```

The archived first attempt stopped after its successful lock-export because the
Windows-host Debian lock used CRLF while the container verifier emitted LF.
That failure is retained under `attempts/attempt-1-blocked-20260912T114447Z/`.
Its continuation reuses the byte-identical archived browser manifest and the
same Debian lock normalized to LF, without repeating the successful bootstrap:

```powershell
py -3.13 backend/experiments/browser-r1c/run_r1c.py --resume-from-archived-locks
```

The next blocked attempt is retained under
`attempts/attempt-2-blocked-root-inspection/`; it proved both final builds but
incorrectly ran the filesystem identity tool as the image's UID 10001 and
therefore could not read `/etc/.pwd.lock`. The command above now uses a fresh
`flowtracer-r1c-20260912-rootinspect-*` namespace for the authorized correction.

That correction exposed a second contract error before Browser launch and is
retained under `attempts/attempt-3-blocked-retries-contract/`. The final
contract run then reached the full Chromium process but stopped fail-closed
when its Crashpad handler had no database; that evidence is retained under
`attempts/attempt-4-blocked-crashpad-database/`. The P1 remediation run uses
the unique `flowtracer-r1c-20260913-p1-runtime-dirs-*` namespace. Both
DynamicFetcher calls use `retries=1`, explicitly select
`/opt/browser-r1c/chromium-1234/chrome-linux64/chrome`, and use distinct
controlled profiles below `/tmp`. For each call it also creates fresh mode
`0700` runtime-only `HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME` directories
under `/tmp`, rejects symlinks or path escape, captures the actual Chromium
Crashpad database path/owner/mode, and removes every controlled directory.
The runtime container supplies `/tmp` as a 256 MiB `rw,nosuid,noexec` tmpfs.
Docker execution retains a separate 120-second outer deadline in addition to
Scrapling page timeouts. No guessed crash-reporting flag or direct handler
`--database` argument is used.

The runner creates only the `flowtracer-r1c-20260913-p1-runtime-dirs-*` builder,
tags,
containers, state/cache and evidence. It performs a lock-export build followed
by two independent final `--no-cache --pull=false` builds, then removes those
exact objects. It never uses a global prune. Both final images run with network
none, UID 10001, read-only rootfs, all capabilities dropped and
no-new-privileges. The runtime probe calls Scrapling DynamicFetcher against a
deterministic in-process loopback fixture; direct Patchright is not used as a
substitute.

Normalized filesystem identity is a separate root-only inspection because it
must hash root-owned files such as `/etc/.pwd.lock`. The runner invokes that
inspection with explicit `docker run --user 0`, network none, read-only rootfs,
all capabilities dropped and no-new-privileges. This does not relax candidate
runtime execution: both real DynamicFetcher probes are separately created and
machine-validated as UID `10001:10001` with the same network/read-only/
capability/no-new-privileges restrictions.

All ten raw build outputs use the Git-visible `.txt` extension. The original
ignored `.log` path, replacement path, byte count, and identical before/after
SHA-256 are recorded in `log-rename-sha256.json`; `validate_sbom.py` verifies
that proof together with the rest of the R1C evidence package.

The package-tree identity is locale independent. It includes every regular
file recursively below this `browser-r1c` directory with no ignore-file,
extension, hidden-file, evidence, or attempt exclusions; symlinks and other
unsupported entry types fail closed. Each relative path uses `/`, and entries
are sorted by Python's locale-independent Unicode code-point string order.
For each entry, the validator hashes the exact file bytes and appends this
UTF-8 record without a BOM:

```text
<relative-path> <lowercase-content-sha256>\n
```

The last record also ends in LF. The SHA-256 of the concatenated payload is
compared with the single `R1C_PACKAGE_TREE_V1` declaration in the repository-
root `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`, outside this package
tree so the identity does not contain itself. Reproduce the full lightweight
validation without creating `__pycache__` using:

```powershell
py -3.13 -B backend/experiments/browser-r1c/scripts/validate_sbom.py `
  backend/experiments/browser-r1c/evidence `
  --package-tree-doc docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md
```
