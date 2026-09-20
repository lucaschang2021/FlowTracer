# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM --platform=linux/amd64 python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca AS runtime-base

ARG DEBIAN_SNAPSHOT=20260824T000000Z

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browser-r1c \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000 \
    PLAYWRIGHT_SKIP_BROWSER_GC=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.lock /tmp/requirements.lock
COPY runtime/entrypoint.py runtime/runtime_probe.py /opt/flowtracer-r1d/runtime/

RUN sed -i \
      -e "s|URIs: http://deb.debian.org/debian-security|URIs: https://snapshot-cloudflare.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|URIs: http://deb.debian.org/debian|URIs: https://snapshot-cloudflare.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
      'Acquire::Check-Valid-Until "false";' \
      'Acquire::Retries "10";' \
      'Acquire::http::Timeout "60";' \
      > /etc/apt/apt.conf.d/99snapshot \
    && python -m pip install --no-compile --require-hashes -r /tmp/requirements.lock \
    && python -m patchright install --with-deps chromium \
    && rm -f /tmp/requirements.lock \
    && test -x /opt/browser-r1c/chromium-1234/chrome-linux64/chrome \
    && test -f /opt/browser-r1c/chromium-1234/chrome-linux64/ABOUT \
    && test -x /opt/browser-r1c/ffmpeg-1011/ffmpeg-linux \
    && test -f /opt/browser-r1c/ffmpeg-1011/COPYING.LGPLv2.1 \
    && chmod -R a+rX /opt/browser-r1c /opt/flowtracer-r1d \
    && rm -rf /var/cache/fontconfig/* /var/cache/ldconfig/aux-cache /var/log/apt/* \
    && rm -f /var/log/alternatives.log /var/log/dpkg.log \
    && find /usr/local/lib/python3.13/site-packages -type d -name __pycache__ -prune -exec rm -rf '{}' + \
    && useradd --create-home --uid 10001 flowtracer

FROM runtime-base AS audit-verified
RUN --mount=type=bind,source=audit,target=/opt/flowtracer-r1d-audit,readonly \
    --mount=type=bind,source=browser-tree.manifest.json,target=/tmp/browser-tree.manifest.json,readonly \
    --mount=type=bind,source=debian-packages.lock,target=/tmp/debian-packages.lock,readonly \
    python /opt/flowtracer-r1d-audit/browser_tree_manifest.py --verify /tmp/browser-tree.manifest.json \
    && dpkg-query -W | tr '\t' '=' | LC_ALL=C sort > /tmp/debian-packages.actual \
    && diff -u /tmp/debian-packages.lock /tmp/debian-packages.actual \
    && rm -f /tmp/debian-packages.actual

FROM audit-verified AS final
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python", "/opt/flowtracer-r1d/runtime/entrypoint.py"]
CMD ["python", "/opt/flowtracer-r1d/runtime/runtime_probe.py"]
