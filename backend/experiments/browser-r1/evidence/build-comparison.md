# R1 independent no-cache build comparison

## Current status: PASS — READY FOR INDEPENDENT REVIEW

Two independent normal final-fix candidate builds completed with the final R1 inputs:
digest-pinned Dockerfile frontend, explicit `linux/amd64` platform, full browser
tree manifest, binary-vs-notice SBOM hashes, persistent Debian notices, and the
official HTTPS Cloudflare Snapshot front end for both Debian main and security.

## Declared environment

- Host Docker client/engine: 29.7.2 / 29.7.2
- Buildx: v0.36.1-desktop.1 (`83d819cf8237b52ef45a2a9857eeb83a7b10977f`)
- Dedicated BuildKit: v0.32.2, image digest
  `sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8`
- Dockerfile frontend: `docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e`
- Target platform: `linux/amd64`
- Debian snapshot: `20260824T000000Z`, Bookworm main/security, APT/GPG verified
  against the official `https://snapshot-cloudflare.debian.org/` front end.

## Final acceptance results

| Evidence | Build 1 | Build 2 |
| --- | --- | --- |
| Local image ID | `sha256:3440b61564a038df1397affe331ded16e42fc4b25de8c453b7ca129b567f01b9` | `sha256:258cf127308b9bb825340f6cfbac17ddef62452f725fa24584acfeb3e288d12c` |
| Created (UTC) | `2026-09-08T11:36:14.629638542Z` | `2026-09-08T11:39:41.440701829Z` |
| Docker-reported size | 418,605,773 bytes | 418,605,936 bytes |
| Normalized file identity | `2a255b61087479d73706e85601713398ed73387b53fb68690cd16dc75ae1a9c5` | same |
| Generated SBOM stream/file SHA-256 | `ff1918f042833280e5e45b3f25da5159eed9b63e0c24d347b7f9628730eeadaa` | same |
| Generated Debian license inventory stream/file SHA-256 | `bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da` | same |
| Browser tree verifier | PASS | PASS |
| Offline render | PASS | PASS |
| Runtime UID/rootfs/network | 10001 / read-only / none | 10001 / read-only / none |

The OCI image IDs, layer diff IDs, timestamps, and compressed sizes differ due
to build-time OCI/tar metadata. The content identity hashes every non-volatile
filesystem entry's path, kind, mode, UID, GID, symlink target, and regular-file
bytes while excluding container-injected and volatile mounts. Its equality,
together with equal generated SBOMs, successful full tree verification, and
offline runtime probes, demonstrates identical declared runtime content without
claiming byte-identical OCI artifacts.

## Historical failures

Pre-final failures and the superseded earlier final candidates are retained in
`execution-ledger.md` and the tracked plain-text (`.txt`) diagnostics.
They were caused by transient HTTP Snapshot failures and infrastructure setup
issues before both main and security were moved to their authorized official
HTTPS equivalent. They are not used as acceptance evidence.

## Seed extraction context

The earlier `r1-seed` image was used only to export the 301-entry browser tree,
206 persistent Debian notices, and notice inventory. It predates the chmod-order
correction and is not used as final acceptance evidence.

## Final-fix acceptance cleanup

After both final-fix no-cache builds and all candidate validations complete, the
only authorized cleanup is:

```powershell
docker image rm flowtracer-browser-r1:r1-final-fix-build2 flowtracer-browser-r1:r1-final-fix-build1
docker buildx rm flowtracer-r1-final-fix-builder
```

Cleanup completed at `2026-09-08T16:37:22.0101334Z`. Both final-fix image tags,
the final-fix builder/container, and its dedicated state volume/cache (2.88 GB
before removal) are absent. The earlier `flowtracer-r1-final-builder`,
user-owned pinned BuildKit image
`moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8`,
default builders, unrelated images, networks, volumes, and project containers
were retained. No global prune was run.
