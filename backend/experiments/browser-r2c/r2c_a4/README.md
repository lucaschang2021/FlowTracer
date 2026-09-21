# R2C-A4 controlled-egress regression harness

This harness is isolated from the default FlowTracer Compose stack and product
code. `../run_r2c_a4.py` builds the merged R1E Dockerfile twice with independent
builders and `--no-cache --pull=false --platform=linux/amd64`, proves both full
Runtime Identity v2 manifests are byte-identical to each other and the accepted
R1E manifest, and only then starts the controlled-egress matrix.

The runtime topology uses two internal networks for Browser/proxy/fixture,
an authoritative no-forward DNS canary, a declared Redis, and one unique
loopback host canary with an independent control client. The proxy has a
deterministic offline resolver, checks every A and AAAA answer twice, and
verifies the connected peer. It accepts CONNECT only. All target names are
synthetic and all addresses are fixture, private, link-local, metadata, or
IANA special-purpose ranges; the harness does not query public DNS or contact
public/real targets.

The browser probe calls Scrapling `DynamicFetcher` with the explicit full
Chromium executable, `retries=1`, the controlled proxy, and dedicated HOME,
XDG, Crashpad, and profile directories on the 256 MiB tmpfs. It records an
allowed deterministic render, a redirect chain, safe failure, policy denials,
direct-route denials, and zero terminal process/directory residue.

The formal evidence path is `../evidence/r2c-a4/`. The runner refuses to
overwrite it and precisely removes only its two unique builders and images,
containers, networks, and builder volumes. It never invokes a global prune.
