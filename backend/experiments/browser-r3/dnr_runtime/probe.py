"""Real close and DynamicFetcher adapters, no authorized Browser entrypoint."""

from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Timer

from collector import Unknown
from contract import FLAGS, Rejected
from harness import Guard

REAL_SESSION_AUTHORIZED = False
EXECUTABLE = "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
PROXY = "http://198.51.100.20:18080"
PRESERVED_FLAGS = [
    "--ignore-certificate-errors",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
]


def child_guard() -> Guard:
    def arm(seconds, callback):
        timer = Timer(seconds, callback)
        timer.daemon = True
        timer.start()
        return timer

    return Guard(arm, lambda: os._exit(78), time.monotonic)


def close_confirmed(page) -> bool:
    """Use only under independently armed 5s child/parent supervision.

    context.close alone is not proof; disconnected event and browser/page state
    must agree. Parent still verifies natural exit and no residual Chrome.
    """
    disconnected = []
    context, browser = page.context, page.context.browser
    if browser is None:
        raise Unknown("close_browser_identity_missing")
    browser.on("disconnected", lambda: disconnected.append(True))
    try:
        context.close()
        if not disconnected or browser.is_connected() or not page.is_closed():
            raise Unknown("close_confirmation_missing")
        return True
    except Exception:
        raise Unknown("close_confirmation_unknown") from None


def guarded_setup(guard: Guard, collector, page, clock) -> None:
    """Refusal closes whole persistent browser and always exits the probe child."""

    def inspect():
        collector.discover()
        audit = page.context.new_page()
        audit.goto(f"chrome-extension://{collector.extension_id}/audit.html", timeout=15000)
        collector.bind_audit_page(audit)
        collector.readback(configure=True)
        # These two unreviewed sources ALWAYS refuse in this offline candidate.
        collector.require_target_permission(clock)
        raise Unknown("real_allow_path_not_admitted")

    guard.setup(inspect, lambda: close_confirmed(page))


def invoke_dynamic_fetch(profile: Path, setup, action, *, enabled: bool):
    if not REAL_SESSION_AUTHORIZED:
        raise Rejected("real_session_not_authorized")
    # Frozen actual DynamicFetcher -> Playwright, never Stealth/Patchright.
    from scrapling.fetchers import DynamicFetcher

    return DynamicFetcher.fetch(
        "https://navigation-r3.test:8443/dnr",
        headless=True,
        proxy=PROXY,
        retries=1,
        timeout=8000,
        page_setup=setup,
        page_action=action,
        google_search=False,
        disable_resources=False,
        network_idle=False,
        executable_path=EXECUTABLE,
        user_data_dir=str(profile),
        additional_args={"ignore_https_errors": True},
        extra_flags=PRESERVED_FLAGS + (FLAGS if enabled else []),
    )


def fetch_once(guard: Guard, fetch, setup, action):
    # Independent parent must already be armed before child starts this function.
    guard.start()
    return fetch(setup=setup, action=action, retries=1)


if __name__ == "__main__":
    raise SystemExit("NO_GO: real_session_not_authorized")
