"""Real close and DynamicFetcher adapters, no authorized Browser entrypoint."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from threading import Timer

from collector import Unknown, observe_sources
from contract_v2 import FLAGS, Rejected
from harness_v2 import Guard

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
        inventory = page.context.new_page()
        inventory.goto("chrome://extensions/", timeout=15000)
        collector.read_inventory_candidate(inventory)
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


def four_native_arms(page):
    """Candidate action; never reached while preflight/entrypoints refuse."""
    results = []
    for scheme in ("ws", "wss"):
        results.append(page.evaluate("scheme => r3Fixture.page(scheme)", scheme))
    for scheme in ("ws", "wss"):
        row = page.evaluate(
            """scheme => new Promise((resolve, reject) => {
          const worker = r3Fixture.worker(); let arm = null;
          const timer = setTimeout(() => {
            worker.terminate(); reject(Error('worker_timeout'));
          }, 5000);
          worker.onmessage = event => {
            if (event.data.kind === 'ready') {worker.postMessage({kind:'start',scheme}); return;}
            if (['error','close','timeout','open'].includes(event.data.kind)) {
              arm = event.data; worker.postMessage({kind:'ping'}); return;
            }
            if (event.data.kind === 'pong' && arm) {
              clearTimeout(timer); worker.terminate();
              resolve({...arm,pong:true,terminated:true,http_script_alive:true});
            }
          };
        })""",
            scheme,
        )
        results.append(row)
    return results


def control_ping():
    """Only existing isolated Redis; no general target/client configurability."""
    import socket

    try:
        with socket.create_connection(("198.51.100.30", 6379), timeout=2) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            if connection.recv(64) != b"+PONG\r\n":
                raise Unknown("control_ping_invalid")
    except Exception:
        raise Unknown("control_ping_unknown") from None


class SourcePreflightCompleted(BaseException):
    """The sole setup-completion signal, NEVER a successful fetch Response."""

    def __init__(self, facts):
        self.facts = facts


def source_fetch_options(profile, phase, setup):
    if phase not in {"baseline", "enabled"} or profile.as_posix() != (
        f"/tmp/r3-source/{phase}/profile"  # noqa: S108 - isolated new container tmpfs
    ):
        raise Unknown("source_phase_profile_invalid")
    return {
        "headless": True,
        "retries": 1,
        "timeout": 8000,
        "page_setup": setup,
        "google_search": False,
        "disable_resources": False,
        "network_idle": False,
        "executable_path": EXECUTABLE,
        "user_data_dir": profile.as_posix(),
        "extra_flags": PRESERVED_FLAGS + (FLAGS if phase == "enabled" else []),
    }


def source_fetch_once(fetch, phase, profile, session, guard, extension):
    """Setup performs diagnosis, closes, then interrupts before driver goto."""
    guard.start()
    entered = False
    issued = None

    def setup(page):
        nonlocal entered, issued
        if entered or guard.denied:
            guard.terminal()
        entered = True
        timer = guard.arm(15, guard.terminal)
        started = guard.clock()
        try:
            if page.url != "about:blank":
                raise Unknown("source_initial_origin_invalid")
            hashes = (
                {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in extension.iterdir()}
                if phase == "enabled"
                else {}
            )
            facts = observe_sources(page, phase == "enabled", extension, hashes, profile)
            if guard.denied or guard.clock() - started >= 15:
                guard.terminal()
        except Exception:
            timer.cancel()
            guard.reject_and_close(lambda: close_confirmed(page))
        timer.cancel()
        close_timer = guard.arm(5, guard.terminal)
        closing = guard.clock()
        try:
            confirmed = close_confirmed(page)
        except Exception:
            guard.terminal()
        if confirmed is not True or guard.denied or guard.clock() - closing >= 5:
            guard.terminal()
        guard.closed = True
        close_timer.cancel()
        if guard.denied:
            guard.terminal()
        issued = SourcePreflightCompleted(
            {
                "schema_version": "r3-source-observation-v1",
                "status": "SOURCE_OBSERVED",
                "session": session,
                "phase": phase,
                "target_permission": "DENIED",
                "close_confirmed": True,
                "fetch_returned": False,
                "facts": facts,
            }
        )
        raise issued

    try:
        fetch("about:blank", **source_fetch_options(profile, phase, setup))
    except SourcePreflightCompleted as completed:
        if (
            type(completed) is not SourcePreflightCompleted
            or completed is not issued
            or not entered
            or guard.denied
            or not guard.closed
        ):
            guard.terminal()
        facts = completed.facts
        if (
            type(facts) is not dict
            or facts.get("status") != "SOURCE_OBSERVED"
            or facts.get("target_permission") != "DENIED"
            or facts.get("close_confirmed") is not True
            or facts.get("fetch_returned") is not False
            or type(facts.get("facts")) is not dict
            or facts["facts"].get("target_permission") != "DENIED"
        ):
            guard.terminal()
        guard.total_timer.cancel()
        return facts
    # Swallowed signal, normal fetch return, or skipped hook is NEVER success.
    guard.terminal()


def source_child(phase, profile, session):
    if sys.platform != "linux" or os.getuid() != 10001:
        raise Unknown("source_child_identity_invalid")
    source_fetch_options(profile, phase, None)
    profile.mkdir(parents=True, exist_ok=False)
    if list(profile.iterdir()):
        raise Unknown("source_profile_not_new")
    from importlib.metadata import version

    scrapling_version, playwright_version = version("scrapling"), version("playwright")
    if scrapling_version != "0.4.15" or playwright_version != "1.62.0":
        raise Unknown("source_driver_version_invalid")
    from scrapling.fetchers import DynamicFetcher

    result = source_fetch_once(
        DynamicFetcher.fetch, phase, profile, session, child_guard(), Path("/opt/flowtracer-r3-dnr")
    )
    result["facts"].update(
        scrapling_version=scrapling_version, playwright_version=playwright_version
    )
    return result


if __name__ == "__main__":
    # Operation arguments are NOT authorization. Only the separately reviewed
    # host source_preflight entry may create this exact network-none child.
    if (
        len(sys.argv) != 8
        or sys.argv[1:2] != ["--source-preflight"]
        or sys.argv[2::2] != ["--phase", "--profile", "--session"]
    ):
        raise SystemExit("NO_GO: real_session_not_authorized")
    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result = source_child(sys.argv[3], Path(sys.argv[5]), sys.argv[7])
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except BaseException:
        # Includes signals: fixed safe failure only, NEVER success.
        print('{"status":"BLOCKED","target_permission":"DENIED"}')
        raise SystemExit(78) from None
