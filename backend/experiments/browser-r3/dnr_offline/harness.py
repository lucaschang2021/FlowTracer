"""Non-launching lifecycle adapter/model. No Scrapling/Browser/runner imports."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from threading import Timer
from typing import NoReturn

from contract import Rejected, check_readback


class Terminal(BaseException):
    """Offline supervisor termination, not catchable by Scrapling's Exception."""


class Guard:
    """Timer factory/close/kill are injected; NOT a verified container supervisor.

    Future actual child termination must be non-returning (os._exit/SIGKILL), and
    parent 120s container stop must be armed before launch. This model has no runner.
    """

    def __init__(self, arm: Callable, terminate: Callable, clock: Callable) -> None:
        self.arm, self.terminate, self.clock = arm, terminate, clock
        self.started = False
        self.denied = False
        self.ready = False
        self.closed = False
        self.total_timer = None

    def terminal(self) -> NoReturn:
        self.denied = True
        self.terminate()
        # If termination adapter ever returns, NEVER return to swallowed callback.
        raise Terminal("probe_terminated")

    def start(self) -> None:
        if self.started:
            raise Rejected("caller_retry_forbidden")
        self.total_timer = self.arm(120, self.terminal)
        self.started = True

    def reject_and_close(self, close: Callable) -> NoReturn:
        self.denied = True
        timer = self.arm(5, self.terminal)
        started = self.clock()
        try:
            # Contract: close entire persistent context/browser, await confirmation;
            # must return literal True only after independent closure confirmation.
            confirmed = close()
        except Exception:
            self.terminal()
        if confirmed is not True or self.clock() - started >= 5:
            self.terminal()
        self.closed = True
        timer.cancel()
        # Stronger than raising Exception: simulated callback can never fall through.
        # Actual non-returning child kill remains mandatory even after clean close.
        self.terminal()

    def setup(self, inspect: Callable, close: Callable) -> None:
        if not self.started or self.denied or self.ready:
            self.terminal()
        preflight = self.arm(15, self.terminal)
        started = self.clock()
        try:
            snapshot, identity = inspect()
            check_readback(snapshot, identity)
            if self.clock() - started >= 15:
                raise Rejected("preflight_timeout")
        except Exception:
            preflight.cancel()
            self.reject_and_close(close)
        preflight.cancel()
        if self.denied:
            self.terminal()
        self.ready = True

    def before_target(self) -> None:
        if not self.started or not self.ready or self.denied:
            self.terminal()


def child_guard_candidate() -> Guard:
    """Not invoked offline. Entire child exits even if close/API hangs.

    It does not replace independent parent/container supervision or prove process
    reaping. A future admitted caller must also arm that parent before child start.
    """

    def arm(seconds, callback):
        timer = Timer(seconds, callback)
        timer.daemon = True
        timer.start()
        return timer

    return Guard(arm, lambda: os._exit(78), time.monotonic)


def model_fetch_once(guard: Guard, fetch: Callable, inspect: Callable, close: Callable):
    """Test double entry only. Actual runner deliberately absent in OFFLINE ONLY."""
    guard.start()  # precedes injected fetch/any DynamicSession launch

    def setup():
        guard.setup(inspect, close)

    result = fetch(setup, guard.before_target, retries=1)
    guard.before_target()  # disallows returning a result after lost policy
    return result
