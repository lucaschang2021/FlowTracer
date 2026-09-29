"""Trusted extension CDP readback candidate; inventory/clock proof remains UNKNOWN."""

from __future__ import annotations

import math
import re
from pathlib import Path

from contract import FLAGS, MANIFEST, MOUNT, SESSION, Rejected, check_static, fingerprint
from validator import finite_time

RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "session",
        "extension_id",
        "ruleset_id",
        "rule_id",
        "action",
        "resource_type",
        "request_id",
        "timestamp",
        "sequence",
        "observer_epoch",
        "safe_request_fingerprint",
        "tab_id",
        "frame_id",
        "document_id",
        "initiator",
        "initiator_note",
    }
)
ARM_FINGERPRINTS = frozenset(
    fingerprint(actor, scheme) for actor in ("page", "worker") for scheme in ("ws", "wss")
)


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
        if not self.anchors:
            raise Unknown("clock_anchors_missing")
        for anchor in self.anchors:
            for key in ("before_monotonic_ms", "browser_epoch_ms", "after_monotonic_ms"):
                value = anchor.get(key)
                if type(value) not in (int, float):
                    raise Unknown("clock_anchor_invalid")
                try:
                    if not math.isfinite(value):
                        raise Unknown("clock_anchor_invalid")
                except OverflowError:
                    raise Unknown("clock_anchor_invalid") from None
            if anchor["before_monotonic_ms"] > anchor["after_monotonic_ms"]:
                raise Unknown("clock_anchor_order_invalid")
        # No frozen version/source/unit/error authority exists in this candidate.
        raise Unknown("clock_mapping_unreviewed")


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
            snapshot.get("schema_version") != "r3-dnr-audit-v1"
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
            if (
                type(row) is not dict
                or set(row) != RECEIPT_FIELDS
                or any(
                    type(row.get(key)) is not str
                    for key in (
                        "schema_version",
                        "session",
                        "extension_id",
                        "ruleset_id",
                        "action",
                        "resource_type",
                        "request_id",
                        "observer_epoch",
                        "safe_request_fingerprint",
                        "initiator_note",
                    )
                )
                or type(row.get("sequence")) is not int
                or row.get("sequence") != ordinal
                or not finite_time(row.get("timestamp"))
                or row.get("observer_epoch") != epoch
                or row.get("session") != SESSION
                or row.get("extension_id") != self.extension_id
                or row.get("schema_version") != "r3-dnr-receipt-v1"
                or row.get("ruleset_id") != "ws_default_deny_v1"
                or type(row.get("rule_id")) is not int
                or row.get("rule_id") != 1
                or row.get("action") != "block"
                or row.get("resource_type") != "websocket"
                or not isinstance(row.get("request_id"), str)
                or not row["request_id"]
                or row["request_id"] in seen
                or row.get("safe_request_fingerprint") not in ARM_FINGERPRINTS
                or any(
                    row.get(key) is not None and type(row[key]) is not int
                    for key in ("tab_id", "frame_id")
                )
                or (row.get("document_id") is not None and type(row["document_id"]) is not str)
                or row.get("initiator") is not None
                or row.get("initiator_note") != "omitted_to_prevent_origin_secret_exposure"
            ):
                raise Unknown("audit_receipt_invalid")
            seen.add(row["request_id"])
            # All validated fields are immutable scalars. Preserve values AND types;
            # never alias the returned CDP snapshot or equate bool/int/float values.
            history.append(tuple((key, type(row[key]), row[key]) for key in sorted(row)))
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

    def require_target_permission(self, clock: ClockEvidence) -> None:
        self.readback()
        self.require_inventory()
        clock.require_mapping()
