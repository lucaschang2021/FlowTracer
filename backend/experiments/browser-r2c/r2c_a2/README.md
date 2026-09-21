# R2C-A2 controlled-egress regression harness

This harness is isolated from the default FlowTracer Compose stack and product
code. `../run_r2c_a2.py` builds the merged R1D Dockerfile once with
`--no-cache --pull=false --platform=linux/amd64`, proves the candidate's full
Runtime Identity v2 manifest is byte-identical to the accepted R1D manifest,
and only then starts the controlled-egress matrix.

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

The formal evidence path is `../evidence/r2c-a2/`. The runner refuses to
overwrite it and precisely removes only its unique builder, image, containers,
networks, and builder volume. It never invokes a global prune.
