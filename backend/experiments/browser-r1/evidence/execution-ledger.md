# R1 execution ledger

This ledger records only observed execution facts. It contains no credentials,
connection strings, request bodies, or browser content. Relative BuildKit times
below are recorded exactly as printed by `docker buildx history ls` at
`2026-09-08T00:50:43.5578766Z`; no unrecorded timestamp is inferred.

| Time / source | Actual command | Exit | Safe result |
| --- | --- | --- | --- |
| `2026-09-08T00:38:19Z` (BuildKit inspect) | `docker buildx create --name flowtracer-r1-review-builder --driver docker-container --driver-opt network=bridge,image=moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8 --use` | 0 | Dedicated builder created. |
| `2026-09-08T00:41:57.137887215Z` (image metadata) | `docker buildx build --builder flowtracer-r1-review-builder --platform=linux/amd64 --no-cache --pull=false --load --build-arg VERIFY_BROWSER_TREE=0 -t flowtracer-browser-r1:r1-seed .` | 0 | Historical seed-only extraction before the final Dockerfile policy; exported 301 tree entries, 206 Debian notices, SBOM. The final Dockerfile no longer accepts this bypass. |
| pre-ledger session (exact timestamp unavailable) | pre-review Build 2, quiet mode | 1 | Saved summary only: combined Dockerfile `RUN` exited 1. No cause is asserted. |
| BuildKit `q238wqwyta3rto3cvpv509xx8`, `4 minutes ago` | normal Build 1, quiet mode | 1 | Combined Dockerfile `RUN` exited 1; no subcommand detail in quiet output. |
| BuildKit `gvy4ezdkl25hnf03c6viys76m`, `2 minutes ago` | normal Build 1, `--progress=plain` | 1 | `snapshot.debian.org` security InRelease returned HTTP 502; APT exit 100. |
| BuildKit `c4fj03pr6ru5np6p41891g5q8`, `about a minute ago` | normal Build 1, quiet mode after tree-order fix | 1 | Combined Dockerfile `RUN` exited 1; no subcommand detail in quiet output. |
| `2026-09-08T00:50:43.5578766Z` | `docker run --rm --user 0 --entrypoint python flowtracer-browser-r1:r1-seed ...browser_tree_manifest.py --verify ...` | 78 | `R1_BROWSER_TREE_MISMATCH`; seed predates the later Dockerfile chmod-order fix. |
| `2026-09-08T00:50:43.5578766Z` | `docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,nosuid,noexec,size=128m --pids-limit 128 --memory 512m --cpus 1 flowtracer-browser-r1:r1-seed` | 0 | UID 10001, read-only rootfs, no network, offline render `ok`. |
| current source verification | `py -m uv run --project backend ruff check ...; ruff format --check ...; py ...validate_sbom.py ...; git diff --check` | 0 | Ruff passes; 6 scripts formatted; SBOM static validation `components=231 debian=206`; diff clean. |
| `2026-09-08T01:00:40.7765532Z` (recorded immediately after command) | `curl.exe --verbose --silent --show-error --dump-header - --output NUL --max-time 30 --connect-timeout 10 --proto '=https' --tlsv1.2 https://snapshot.debian.org/archive/debian-security/20260824T000000Z/dists/bookworm-security/InRelease` | 35 | DNS resolved `198.18.0.94`; before HTTP, Windows Schannel failed certificate revocation validation with `CRYPT_E_REVOCATION_OFFLINE`; HTTP `000`, redirects `0`. No Dockerfile source change and no build retry followed. |
| 2026-09-08 (after official-equivalence authorization) | `docker run --rm --network bridge python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca sh -ec "... deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot-cloudflare.debian.org/archive/debian-security/20260824T000000Z bookworm-security main ...; apt-get -o Acquire::Check-Valid-Until=false update"` | 0 | Official HTTPS front end fetched exact `InRelease` (34.8 kB) and `main amd64 Packages` (335 kB); APT completed signature verification without `--insecure`, HTTP downgrade, or signature bypass. |
| `2026-09-08T01:06:48.2223019Z` (recorded immediately after command) | `docker buildx create --name flowtracer-r1-equivalence-builder --driver docker-container --driver-opt network=bridge,image=moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8 --use; ... build --platform=linux/amd64 --no-cache ...` | 1 | Builder bootstrap failed before Dockerfile execution: Docker Hub OAuth token request for the fixed BuildKit image ended in EOF. No acceptance image or cache was created. |
| `2026-09-08T01:06:48.2223019Z` | `docker buildx rm flowtracer-r1-equivalence-builder` | 0 | Inactive failed builder removed; post-cleanup list contains only pre-existing `default` and `desktop-linux` builders. |
| `2026-09-08T03:23:36.8906417Z` (recorded immediately after command) | `docker buildx build --builder flowtracer-r1-final-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=quiet -f Dockerfile -t flowtracer-browser-r1:r1-final-build1 .` | 1 | Fixed dedicated builder bootstrapped, but the Dockerfile's combined install/verification `RUN` exited 1. Quiet output records no failing subcommand, so no cause is asserted. Per bounded-attempt instruction, Build 2 was not started and the builder is preserved for inspection. |
| `2026-09-08T05:21:19.4769041Z` (recorded immediately after command) | `docker buildx build --builder flowtracer-r1-final-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=plain -f Dockerfile -t flowtracer-browser-r1:r1-final-build1 .` | 1 | Exact failure: APT archive fetches from the unchanged `http://snapshot.debian.org/archive/debian/20260824T000000Z` main source failed for `fonts-unifont` with HTTP 502 and `libasound2` with HTTP 500 / unexpected EOF; APT exit 100. The HTTPS Cloudflare security source successfully fetched its InRelease, index, and security packages. Full safe log: `final-build1-plain-resumed.txt`, SHA-256 `e928067bcd4659a8f2ed3e1c5eeb9adb6e8bd64274c02d668c53b8221be4c8a5`. |
| persisted in `main-snapshot-apt-diagnostic.json` | `docker run --rm --network bridge python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca sh -ec "... deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot-cloudflare.debian.org/archive/debian/20260824T000000Z bookworm main ...; apt-get -o Acquire::Check-Valid-Until=false update"` | 0 | Main HTTPS front end APT/GPG diagnostic passed. Complete safe log `main-snapshot-apt-diagnostic.txt`, SHA-256 `75697d6c2038cdd4f89823b65225663b3da00bd4adb4157c93076a3880a89eb1`; exact timestamps and command metadata are persisted in the adjacent JSON. |
| `2026-09-08T05:32:46.949258331Z` (image metadata) | `docker buildx build --builder flowtracer-r1-final-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=quiet -f Dockerfile -t flowtracer-browser-r1:r1-final-build1 .` | 0 | Final Build 1 completed with default browser-tree verification enabled; image ID `b904bc6da3a5fee38d688ff583f891389405538dc39f11eeba1dc0398d1c7ef2`. |
| `2026-09-08T05:36:45.965659273Z` (image metadata) | `docker buildx build --builder flowtracer-r1-final-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=quiet -f Dockerfile -t flowtracer-browser-r1:r1-final-build2 .` | 0 | Final Build 2 completed with the same locked input; image ID `46a5012320c3a81f519ee56f29b78f3a60b527273d7e85a707a7eb89528248eb`. |
| superseded final candidate verification | `image_identity.py`; `browser_tree_manifest.py --verify`; `generate_sbom.py | sha256sum`; constrained runtime probe | 0 | The earlier final images matched at normalized identity `3209b58dde854124c096aa95986a18dfa7a74a4dbc76364fdf76375f83d2ba40` and SBOM stream `099c69b5d51fcf65cd9f998fedbddbdd3acf413bd405f186cd481297aebb1b11`; they are retained only as historical evidence and do not replace the final-fix license-policy candidates below. |
| `2026-09-08 19:34:35 +08:00` (BuildKit history `soujawxnhetmybkrvgyeue3z7`) | `docker buildx build --builder flowtracer-r1-final-fix-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=quiet -f Dockerfile -t flowtracer-browser-r1:r1-final-fix-build1 .` | 0 | Final-fix Build 1 completed 13/13 steps in 3m02s with 0% cached; image ID `3440b61564a038df1397affe331ded16e42fc4b25de8c453b7ca129b567f01b9`. |
| `2026-09-08 19:38:08 +08:00` (BuildKit history `vdapte1t78gwtgbd1dlcfsjs4`) | `docker buildx build --builder flowtracer-r1-final-fix-builder --platform=linux/amd64 --no-cache --pull=false --load --progress=quiet -f Dockerfile -t flowtracer-browser-r1:r1-final-fix-build2 .` | 0 | Final-fix Build 2 completed 13/13 steps in 2m53s with 15% content reuse reported but `No Cache: true`; image ID `258cf127308b9bb825340f6cfbac17ddef62452f725fa24584acfeb3e288d12c`. |
| `2026-09-08T16:29:26.6554353Z` (recorded after final verification) | two-image `image_identity.py`; `browser_tree_manifest.py --verify`; `generate_sbom.py \| sha256sum`; `generate_sbom.py --debian-license-inventory \| sha256sum`; actual notice `sha256sum`; constrained runtime probe | 0 | Both final-fix images: normalized identity `2a255b61087479d73706e85601713398ed73387b53fb68690cd16dc75ae1a9c5`; SBOM stream/file `ff1918f042833280e5e45b3f25da5159eed9b63e0c24d347b7f9628730eeadaa`; Debian inventory stream/file `bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da`; 301-entry tree PASS; Chromium/FFmpeg notice hashes match persisted bytes; UID 10001 / read-only / network-none offline render PASS. |
| `2026-09-08T16:37:22.0101334Z` | `docker image rm flowtracer-browser-r1:r1-final-fix-build2 flowtracer-browser-r1:r1-final-fix-build1`; `docker buildx rm flowtracer-r1-final-fix-builder`; exact post-cleanup inspections | 0 | Both final-fix images, builder/container, and its attributable 2.88 GB state volume/cache are absent. Pinned BuildKit image `sha256:28a898...1d8` and earlier `flowtracer-r1-final-builder` remain. No global prune or unrelated removal. |

## Earlier intermediate cleanup

Before the final two-build evidence run, the earlier seed and review-builder
objects were removed with:

```powershell
docker image rm flowtracer-browser-r1:r1-seed
docker buildx rm flowtracer-r1-review-builder
docker image rm moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8
```

At that point the fixed BuildKit image was also removed as part of the
intermediate cleanup. It was subsequently pulled manually by the user for the
final dedicated builder and is intentionally retained by the final cleanup
below. No global prune, default builder, volume, or project container was
removed.

## Earlier final-candidate cleanup record

After both final no-cache builds and all candidate validations completed, the
following exact acceptance artifacts were removed:

```powershell
docker image rm flowtracer-browser-r1:r1-final-build2 flowtracer-browser-r1:r1-final-build1
docker buildx rm flowtracer-r1-final-builder
```

That earlier run reported no `flowtracer-browser-r1` image and no
`flowtracer-r1-final-builder` immediately after its cleanup. Current inspection
finds the earlier `flowtracer-r1-final-builder` present again; it is not owned by
this final-fix run and remains untouched. The user-owned, manually pulled fixed
BuildKit image `moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8`
is retained. No global prune, default builder, unrelated volume, project
container, or unrelated image is in scope.

## Final-fix cleanup

The exact final-fix images, `flowtracer-r1-final-fix-builder`, and its dedicated
state volume/cache were removed after static evidence checks. Post-cleanup
inspection confirmed all four scoped object classes absent while the pinned
BuildKit image and earlier final builder remain.
