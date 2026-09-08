# Browser R1 locked-image evidence

This directory is an isolated remediation artifact. It is not referenced by the
default backend image, Compose services, API, worker, or acquisition pipeline.

## Locked inputs

- Python base: `python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca`
- Python: 3.13.15; pip: 26.2.1
- Scrapling: `scrapling[fetchers]==0.4.15`
- Patchright: 1.62.3; Playwright: 1.62.0
- Chromium headless shell: Chrome for Testing 151.0.7922.34, revision 1234
- FFmpeg: Playwright revision 1011
- Debian snapshot: `20260824T000000Z` (Bookworm)
- Debian main and security snapshot frontend:
  `https://snapshot-cloudflare.debian.org/` (same Debian
  archive/timestamp/suite/component; HTTPS APT/GPG verified)
- BuildKit: v0.32.2, image `moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8`
- Dockerfile frontend: `docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e`

`uv.lock` is the dependency resolver lock. `requirements.lock` is the
hash-checking installation projection. The Debian and browser manifests are
verified during the image build.

## Reproduce

Run from this directory. The dedicated builder makes the build cache attributable
and removable without pruning shared Docker state.

```powershell
docker buildx create --name flowtracer-r1-builder --driver docker-container `
  --driver-opt network=bridge,image=moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8 --use
docker buildx inspect flowtracer-r1-builder --bootstrap
docker buildx build --builder flowtracer-r1-builder --platform=linux/amd64 --no-cache --pull=false --load `
  -f Dockerfile -t flowtracer-browser-r1:r1-final-build1 .
docker buildx build --builder flowtracer-r1-builder --platform=linux/amd64 --no-cache --pull=false --load `
  -f Dockerfile -t flowtracer-browser-r1:r1-final-build2 .
```

Validate each image using the same hardening flags:

```powershell
docker run --rm --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges --tmpfs /tmp:rw,nosuid,noexec,size=128m `
  --pids-limit 128 --memory 512m --cpus 1 `
  flowtracer-browser-r1:r1-final-build1
docker run --rm --user 0 --entrypoint python flowtracer-browser-r1:r1-final-build1 `
  /opt/flowtracer-r1/scripts/image_identity.py
```

The root-only identity command is an inspection operation: it must read files
such as `/etc/.pwd.lock`. The candidate runtime remains UID 10001.

## Cleanup

```powershell
docker image rm flowtracer-browser-r1:r1-final-build1 flowtracer-browser-r1:r1-final-build2
docker buildx rm flowtracer-r1-builder
```

Do not run a global builder prune: it can delete unrelated developer cache.
