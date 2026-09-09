# R2 execution ledger

- Gate: R2 controlled egress proxy/namespace
- Result: `R2 PASS — READY FOR INDEPENDENT REVIEW`
- P0/P1/P2: `0/0/0`
- Branch: `feat/acq-1b-browser-remediation-evidence`
- Execution base: `b6275cd4633207d23cff047d2b612aa4893a2888`
- Host: Windows 11 x64; Docker client/engine 29.7.2; Compose v5.4.0
- Browser image: `flowtracer-browser-r1:r1-final-build2`
- Browser image ID: `sha256:83464fd58248b3af79903c3d4ce3d33140f498bdfef4d9efec9c4552718a3eec`
- Image platform/user: `linux/amd64`, `10001:10001`
- Evidence interval: 2026-09-09 09:56:48 UTC
- Public network/credentials: none

## Commands and results

```powershell
py -3.13 -B backend/experiments/browser-r2/validate_policy.py
# {"cases": 14, "result": "PASS", "system_dns_calls": 0}

$env:R2_PROJECT_NAME = "flowtracer-r2-review4-20260909"
$env:R2_BROWSER_IMAGE = "flowtracer-browser-r1:r1-final-build2"
docker compose -f backend/experiments/browser-r2/compose.yaml config --quiet
# exit 0

py -3.13 -B backend/experiments/browser-r2/run_r2.py
# {"allow_events":4,"deny_events":14,"result":"R2_PASS",...}
```

The runner used the unique Compose project `flowtracer-r2-review4-20260909`,
refused pre-existing attributable objects, and created eight isolated
containers (`browser-probe`, `control-client`, `proxy`, `fixture`, `decoy`,
`redis`, `dns-canary`, `host-canary`). The Browser and fixture networks were
internal. Host canary and control client used separate networks, neither shared
with Browser. The canary exposed only the temporary host loopback port
`127.0.0.1:49175`. It created no Docker volume, mounted no Docker socket, used
no host network or privileged mode, dropped all capabilities, and used
read-only root filesystems with tmpfs for writable state.

## Security evidence

- Browser namespace: UID 10001; only proxy and declared Redis share its front
  network. Fixture and decoy exist only on the separate internal fixture
  network reached by the proxy.
- Host gateway: a bounded host readiness probe reached `127.0.0.1:49175` on
  attempt 1 and received `R2_HOST_CANARY`. An independent control client then
  reached the same mapped endpoint `192.168.65.254:49175` and received the same
  marker. Browser received Linux `ENETUNREACH` (errno 101) for that exact
  endpoint.
- DNS: Browser HostConfig points to the local DNS canary. Exactly one A and one
  AAAA query for `fixture-r2.test` received authoritative NXDOMAIN with
  `recursion_available=false` and `upstream_queries=0`; both evidence networks
  are internal. The proxy alone used its deterministic offline resolver.
- CONNECT: four allowed decisions; every allowed target received two DNS
  resolution passes, all A/AAAA answers were validated, and the connected peer
  IP was checked before tunnelling.
- Redirects: safe and unsafe redirect targets each required a fresh CONNECT;
  the metadata target was denied.
- Denials: exactly 14 probe-originated decisions with no healthcheck traffic.
  They cover `connect_required`, `dangerous_port`,
  `direct_ip`, `dns_rebinding`, `link_local`, `loopback`, `metadata`,
  `mixed_answer`, `multicast`, `not_declared_fixture`, `private`, `reserved`,
  and `unspecified`.
- Network layer: direct fixture, undeclared decoy, live host gateway canary and
  isolated control-network canary all failed with `ENETUNREACH`; no
  `ECONNREFUSED` or arbitrary `OSError` was accepted.
- Runtime inspect: all eight services persisted `Config.User=10001:10001`,
  `ReadonlyRootfs=true`, `CapDrop=[ALL]`,
  `SecurityOpt=[no-new-privileges:true]`, exact non-host `NetworkMode`, and exact
  `PortBindings`. Only host-canary had a binding, fixed to loopback port 49175.

## Exact cleanup

The runner always executed:

```powershell
docker container rm -f flowtracer-r2-review4-20260909-browser-probe `
  flowtracer-r2-review4-20260909-control-client
docker compose --project-name flowtracer-r2-review4-20260909 `
  -f backend/experiments/browser-r2/compose.yaml down --remove-orphans
```

Post-run label-filtered inspection found zero attributable containers, zero
networks and zero volumes. Exclusive bind of `127.0.0.1:49175` succeeded on
attempt 1, proving the host port was released. Post-cleanup image inspect
retained the accepted R1 tag at ID
`sha256:83464fd58248b3af79903c3d4ce3d33140f498bdfef4d9efec9c4552718a3eec`.
No global prune was run. See `cleanup.json`.

R3–R5 were not executed. This R2 result does not admit WP-3 implementation.
