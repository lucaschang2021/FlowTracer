"""Only v2 readiness interpretation; retain proven non-returning v1 guard mechanics."""

from contract_v2 import AUDIT_SCHEMA, Rejected
from harness import Guard as BaseGuard


class Guard(BaseGuard):
    def setup(self, inspect, close):
        if not self.started or self.denied or self.ready:
            self.terminal()
        preflight = self.arm(15, self.terminal)
        started = self.clock()
        try:
            snapshot, identity = inspect()
            if (
                snapshot.get("schema_version") != AUDIT_SCHEMA
                or snapshot.get("ok") is not True
                or snapshot.get("flushed") is not True
                or identity.get("trusted_cdp") is not True
                or identity.get("inventory_proven") is not True
                or identity.get("clock_equivalence_proven") is not True
                or self.clock() - started >= 15
            ):
                raise Rejected("preflight_v2_unproven")
        except Exception:
            preflight.cancel()
            self.reject_and_close(close)
        preflight.cancel()
        if self.denied:
            self.terminal()
        self.ready = True
