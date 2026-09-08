# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM --platform=linux/amd64 python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca

ARG DEBIAN_SNAPSHOT=20260824T000000Z

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browser-r1 \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000 \
    PLAYWRIGHT_SKIP_BROWSER_GC=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/.cache

COPY requirements.lock /tmp/requirements.lock
COPY debian-packages.lock browser-files.sha256 browser-tree.manifest.json /opt/flowtracer-r1/locks/
COPY scripts /opt/flowtracer-r1/scripts

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
    && python -m patchright install --with-deps --only-shell chromium \
    && rm -f /tmp/requirements.lock \
    && chmod -R a+rX /opt/browser-r1 /opt/flowtracer-r1 \
    && find /opt/browser-r1 -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > /tmp/browser-files.actual \
    && diff -u /opt/flowtracer-r1/locks/browser-files.sha256 /tmp/browser-files.actual \
    && python /opt/flowtracer-r1/scripts/browser_tree_manifest.py --verify /opt/flowtracer-r1/locks/browser-tree.manifest.json \
    && dpkg-query -W | tr '\t' '=' | LC_ALL=C sort > /tmp/debian-packages.actual \
    && diff -u /opt/flowtracer-r1/locks/debian-packages.lock /tmp/debian-packages.actual \
    && rm -f /tmp/browser-files.actual /tmp/debian-packages.actual \
    && find /usr/local/lib/python3.13/site-packages -type d -name __pycache__ -prune -exec rm -rf '{}' + \
    && rm -rf /var/cache/fontconfig/* /var/cache/ldconfig/aux-cache /var/log/apt/* \
    && rm -f /var/log/alternatives.log /var/log/dpkg.log \
    && useradd --create-home --uid 10001 flowtracer

USER 10001:10001
WORKDIR /work
ENTRYPOINT ["python", "/opt/flowtracer-r1/scripts/entrypoint.py"]
CMD ["python", "/opt/flowtracer-r1/scripts/runtime_probe.py"]
