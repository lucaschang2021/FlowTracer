"""Only v2 readiness interpretation; retain proven non-returning v1 guard mechanics."""

from contract_v2 import Rejected, check_snapshot
from harness import Guard as BaseGuard


class Guard(BaseGuard):
    def setup(self, inspect, close):
        if not self.started or self.denied or self.ready:
            self.terminal()
        preflight = self.arm(15, self.terminal)
        started = self.clock()
        try:
            snapshot, identity = inspect()
            check_snapshot(snapshot, identity)
            if self.clock() - started >= 15:
                raise Rejected("preflight_timeout")
            # No reviewed inventory/clock authority exists. NEVER consume caller
            # "proven" booleans as evidence, even after a fully valid snapshot.
            raise Rejected("inventory_and_clock_sources_unproven")
        except Exception:
            preflight.cancel()
            self.reject_and_close(close)
