"""Trusted extension CDP readback candidate; inventory/clock proof remains UNKNOWN."""

from __future__ import annotations

import re
import time
from pathlib import Path

from contract_v2 import (
    AUDIT_SCHEMA,
    FLAGS,
    MANIFEST,
    MOUNT,
    SESSION,
    Rejected,
    check_static,
    receipt_identity,
)
from validator_v2 import validate_clock_samples


class Unknown(Rejected):
    """Unproven evidence is a refusal, not an inferred capability."""


def evaluate(cdp, expression: str):
    try:
        response = cdp.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
    except Exception:
        raise Unknown("audit_transport_unknown") from None
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("result"), dict)
        or response.get("exceptionDetails")
        or response["result"].get("type") != "object"
    ):
        raise Unknown("audit_evaluation_unknown")
    value = response["result"].get("value")
    if not isinstance(value, dict):
        raise Unknown("audit_value_unknown")
    return value


class ClockEvidence:
    """Evidence boundary, deliberately no accepted real clock conversion yet.

    DNR request.timeStamp and controller monotonic/CDP clocks must not be compared
    without source, units, synchronization and error proof independently reviewed.
    Merely finite anchors or a caller-supplied offset/True are insufficient.
    """

    def __init__(self, anchors: list[dict]) -> None:
        self.anchors = anchors

    def require_mapping(self) -> None:
        try:
            validate_clock_samples(self.anchors)
        except Rejected:
            raise Unknown("clock_mapping_unreviewed") from None


class Collector:
    def __init__(
        self, root_cdp, context, extension: Path, hashes: dict[str, str], profile_evidence: dict
    ) -> None:
        self.root, self.context = root_cdp, context
        self.extension, self.hashes = extension, hashes
        self.profile = profile_evidence
        self.extension_id = None
        self.cdp = None
        self.epoch = None
        self.last_sequence = 0
        self.seen = set()
        self.receipt_history = ()

    def discover(self) -> str:
        check_static(self.extension, self.hashes)
        if (
            self.profile.get("exclusive_new_profile") is not True
            or self.profile.get("initial_entries") != []
            or self.profile.get("readonly_mount") is not True
            or self.profile.get("approved_extension_flags") != FLAGS
            or self.profile.get("mount_target") != MOUNT
        ):
            raise Unknown("profile_or_flags_unverified")
        try:
            targets = self.root.send("Target.getTargets")["targetInfos"]
        except Exception:
            raise Unknown("extension_discovery_unknown") from None
        matches = [
            item
            for item in targets
            if item.get("type") == "service_worker"
            and re.fullmatch(r"chrome-extension://[a-p]{32}/observer\.js", item.get("url", ""))
        ]
        if len(matches) != 1:
            raise Unknown("extension_target_not_unique")
        self.extension_id = matches[0]["url"].split("/")[2]
        return self.extension_id

    def bind_audit_page(self, page) -> None:
        if self.extension_id is None:
            raise Unknown("extension_not_discovered")
        expected = f"chrome-extension://{self.extension_id}/audit.html"
        # Caller may create/navigate ONLY this internal page before fixture goto.
        if page.url != expected:
            raise Unknown("audit_origin_invalid")
        self.cdp = self.context.new_cdp_session(page)
        identity = evaluate(
            self.cdp,
            "({origin:location.origin,id:chrome.runtime.id,manifest:chrome.runtime.getManifest()})",
        )
        if (
            identity.get("origin") != f"chrome-extension://{self.extension_id}"
            or identity.get("id") != self.extension_id
            or identity.get("manifest") != MANIFEST
        ):
            raise Unknown("audit_identity_invalid")

    def readback(self, *, configure: bool = False) -> dict:
        if self.cdp is None:
            raise Unknown("audit_context_missing")
        expression = f"r3Audit.configure('{SESSION}')" if configure else "r3Audit.snapshot()"
        snapshot = evaluate(self.cdp, expression)
        if (
            snapshot.get("schema_version") != AUDIT_SCHEMA
            or snapshot.get("extension_id") != self.extension_id
            or snapshot.get("session") != SESSION
            or snapshot.get("ok") is not True
            or snapshot.get("fatal") is not None
            or snapshot.get("configured") is not True
            or snapshot.get("enabled_rulesets") != ["ws_default_deny_v1"]
            or snapshot.get("dynamic_rules") != []
            or snapshot.get("session_rules") != []
            or snapshot.get("observer_registered") is not True
            or snapshot.get("flushed") is not True
            or snapshot.get("storage_access_level") != "TRUSTED_CONTEXTS"
        ):
            raise Unknown("rule_or_observer_readback_invalid")
        epoch, sequence, rows = (
            snapshot.get(key) for key in ("observer_epoch", "sequence", "receipts")
        )
        if (
            not isinstance(epoch, str)
            or not epoch
            or type(sequence) is not int
            or not isinstance(rows, list)
            or not 0 <= sequence <= 100
            or len(rows) != sequence
        ):
            raise Unknown("audit_collection_invalid")
        if self.epoch is not None and epoch != self.epoch:
            raise Unknown("audit_epoch_changed")
        if sequence < self.last_sequence:
            raise Unknown("audit_sequence_lost")
        seen = set()
        history = []
        for ordinal, row in enumerate(rows, 1):
            try:
                identity = receipt_identity(row, self.extension_id, epoch, ordinal)
            except Rejected:
                raise Unknown("audit_receipt_invalid") from None
            if row["request_id"] in seen:
                raise Unknown("audit_receipt_invalid")
            seen.add(row["request_id"])
            # All validated fields are immutable scalars. Preserve values AND types;
            # never alias the returned CDP snapshot or equate bool/int/float values.
            history.append(identity)
        if not self.seen.issubset(seen):
            raise Unknown("audit_receipts_lost")
        if tuple(history[: self.last_sequence]) != self.receipt_history:
            raise Unknown("audit_receipt_rewritten")
        self.epoch, self.last_sequence, self.seen = epoch, sequence, seen
        self.receipt_history = tuple(history)
        return snapshot

    def require_inventory(self) -> None:
        # Target list + profile + flags + origin are necessary, NOT complete.
        # No reviewed component/non-component inventory source is frozen yet.
        raise Unknown("extension_inventory_source_unreviewed")

    def read_inventory_candidate(self, page):
        """Only the approved diagnostic page; no schema guessed after source failure."""
        if page.url != "chrome://extensions/":
            raise Unknown("inventory_origin_invalid")
        try:
            version = self.root.send("Browser.getVersion")
            if version.get("product") not in {
                "Chrome/151.0.7922.34",
                "HeadlessChrome/151.0.7922.34",
            }:
                raise Unknown("inventory_version_invalid")
            cdp = self.context.new_cdp_session(page)
            value = evaluate(
                cdp,
                """new Promise(resolve => {
              if (location.href !== 'chrome://extensions/' || !chrome.developerPrivate) {
                resolve({ok:false}); return;
              }
              chrome.developerPrivate.getExtensionsInfo(
                {includeDisabled:true,includeTerminated:true}, entries => {
                  resolve(chrome.runtime.lastError ? {ok:false} : {ok:true,entries});
                });
            })""",
            )
            if value.get("ok") is not True or type(value.get("entries")) is not list:
                raise Unknown("inventory_read_invalid")
        except Exception:
            raise Unknown("inventory_read_unknown") from None
        # HEAD/tag145 UI-filtered data cannot certify pinned151 registry coverage.
        # No projection/state/type/location interpretation without exact schema.
        raise Unknown("inventory_151_schema_and_filter_coverage_unknown")

    def require_target_permission(self, clock: ClockEvidence) -> None:
        self.readback()
        self.require_inventory()
        clock.require_mapping()

    def sample_clock(self):
        if self.cdp is None:
            raise Unknown("audit_context_missing")
        before = time.monotonic_ns()
        value = evaluate(self.cdp, "r3Audit.clock()")
        after = time.monotonic_ns()
        if set(value) != {"source", "epoch_ms"}:
            raise Unknown("clock_source_invalid")
        return {**value, "host_before_ns": before, "host_after_ns": after}
