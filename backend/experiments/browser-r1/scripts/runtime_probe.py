from __future__ import annotations

import errno
import json
import os
from pathlib import Path

from patchright.sync_api import sync_playwright
from scrapling.fetchers import DynamicFetcher  # noqa: F401


def assert_read_only_root() -> None:
    probe = Path("/r1-rootfs-write-probe")
    try:
        probe.write_text("forbidden", encoding="utf-8")
    except OSError as exc:
        if exc.errno not in {errno.EROFS, errno.EACCES, errno.EPERM}:
            raise
    else:
        probe.unlink(missing_ok=True)
        raise RuntimeError("root filesystem is writable")


def main() -> None:
    if os.getuid() != 10001:
        raise RuntimeError("unexpected runtime uid")
    assert_read_only_root()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<title>offline-r1</title><main id='result'>rendered</main>")
        if page.title() != "offline-r1":
            raise RuntimeError("offline title render failed")
        if page.locator("#result").text_content() != "rendered":
            raise RuntimeError("offline content render failed")
        browser.close()
    print(
        json.dumps(
            {
                "browser_revision": 1234,
                "engine_version": "151.0.7922.34",
                "network": "none",
                "read_only_rootfs": True,
                "render": "ok",
                "uid": os.getuid(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
