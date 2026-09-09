# Browser R2 controlled-egress evidence

This directory is an isolated, disposable R2 harness. It is not referenced by
the default API, worker, Compose stack, acquisition pipeline, or public contract.

## Topology

```text
browser namespace (198.51.100.10, internal front network)
  +--> controlled CONNECT proxy (198.51.100.20:18080)
  +--> declared Redis (198.51.100.30:6379)
  +--> authoritative no-forward DNS canary (198.51.100.40:53)
  X--> fixture/decoy, host gateway, control network, public/reserved targets

proxy
  +--> front network
  +--> internal fixture network
        +--> declared fixture (192.0.2.10:8443)
        +--> policy-undeclared decoy (192.0.2.30:9090)

host-only control
  +--> 127.0.0.1:49175 -> host canary on a separate control network
  +--> independent control client -> same host-gateway IP:49175 (allow)
  X--> browser namespace (no shared network)
```

The Browser and fixture Docker networks are `internal: true`. The host canary
and independent control client use separate networks that are not connected to
Browser. The canary publishes only the unique loopback control port
`127.0.0.1:49175`; the runner proves that listener is live, then proves the
control client can reach the exact host-gateway IP/port that Browser cannot.
Every container drops all capabilities, runs without privilege or Docker socket,
and uses a read-only root filesystem (Redis data is tmpfs). Browser resolver
queries terminate at the local authoritative NXDOMAIN canary, which has no
upstream/recursive path and records only the queried synthetic name. The proxy
uses a separate deterministic offline resolver and performs two
resolution passes, validates every A/AAAA answer, then verifies the connected
peer IP. Only the declared fixture identity/port is eligible.

## Run

Prerequisite: an independently accepted R1 image is locally available. The
recorded R2 execution used `flowtracer-browser-r1:r1-final-build2`, image ID
`sha256:83464fd58248b3af79903c3d4ce3d33140f498bdfef4d9efec9c4552718a3eec`.
Rebuild it only from the locked R1 Dockerfile and inputs, using the R1
instructions and an attributable builder.

```powershell
$env:R2_PROJECT_NAME = "flowtracer-r2-review4-20260909"
$env:R2_BROWSER_IMAGE = "flowtracer-browser-r1:r1-final-build2"
python run_r2.py
```

The runner refuses pre-existing project objects, verifies Compose, launches the
isolated topology, records only sanitized decisions/topology, validates positive
and negative paths, and precisely removes its named containers and networks in a
`finally` block. It creates no volume and never invokes a global prune.

Evidence files are written under `evidence/`:

- `browser-probe.json`: namespace allow/deny summary;
- `control-client.json`: same host-gateway endpoint positive control;
- `dns-events.jsonl`: local authoritative no-forward DNS decisions;
- `proxy-events.jsonl`: per-CONNECT policy decisions without URL queries/body;
- `topology.json`: actual container inspect security/network facts and host
  canary control result;
- `cleanup.json`: attributable objects remaining after exact cleanup.
