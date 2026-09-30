"""Trusted extension CDP readback candidate; inventory/clock proof remains UNKNOWN."""

from __future__ import annotations

import hashlib
import json
import math
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


CLOCK_JS = """(() => ({epoch_ms:Date.now(),performance_ms:performance.now(),
  time_origin_ms:performance.timeOrigin}))()"""


def observed_clock(read, realm):
    """Actual bounded observations, never a clock mapping or target permission."""
    samples = []
    for _ in range(2):
        before = time.monotonic_ns()
        value = read()
        after = time.monotonic_ns()
        if (
            type(value) is not dict
            or set(value) != {"epoch_ms", "performance_ms", "time_origin_ms"}
            or type(value["epoch_ms"]) is not int
            or any(type(v) not in {int, float} or not math.isfinite(v) for v in value.values())
            or any(v < 0 for v in value.values())
            or after < before
        ):
            raise Unknown("clock_observation_invalid")
        samples.append({**value, "host_before_ns": before, "host_after_ns": after})
    if (
        samples[1]["epoch_ms"] < samples[0]["epoch_ms"]
        or samples[1]["performance_ms"] < samples[0]["performance_ms"]
    ):
        raise Unknown("clock_observation_reversed")
    return {"realm": realm, "samples": samples, "mapping": "UNKNOWN"}


def observe_sources(page, enabled, extension, hashes, profile):
    """Only internal pages; UNKNOWN sources are facts, identity violations refuse."""
    if page.url != "about:blank":
        raise Unknown("source_initial_origin_invalid")
    context = page.context
    browser = context.browser
    if browser is None:
        raise Unknown("source_browser_identity_missing")
    root = browser.new_browser_cdp_session()
    version = root.send("Browser.getVersion")
    if type(version) is not dict or version.get("product") not in {
        "Chrome/151.0.7922.34",
        "HeadlessChrome/151.0.7922.34",
    }:
        raise Unknown("source_browser_version_invalid")
    result = {
        "browser_product": version["product"],
        "target_permission": "DENIED",
        "inventory_complete": False,
        "schema_status": "UNKNOWN",
        "dns_status": "NOT_TESTED_NETWORK_NONE",
        "cross_realm_equivalence": "UNKNOWN",
        "extension_status": "NOT_LOADED" if not enabled else "UNKNOWN",
        "argv_status": "UNKNOWN",
        "clocks": [],
        "inventory_status": "UNKNOWN",
    }
    try:
        argv = root.send("Browser.getBrowserCommandLine")["arguments"]
    except Exception:
        argv = None
    if argv is not None:
        if (
            type(argv) is not list
            or not argv
            or len(argv) > 200
            or any(type(a) is not str or len(a) > 4096 for a in argv)
        ):
            raise Unknown("source_argv_invalid")
        expected = FLAGS if enabled else []
        extension_flags = [
            a for a in argv if a.startswith(("--load-extension", "--disable-extensions-except"))
        ]
        if (
            sorted(extension_flags) != sorted(expected)
            or len(extension_flags) != len(expected)
            or argv[0] != "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
            or "--remote-debugging-pipe" not in argv
            or f"--user-data-dir={profile.as_posix()}" not in argv
            or any(a.startswith(("--proxy", "--remote-debugging-port")) for a in argv)
        ):
            raise Unknown("source_argv_boundary_invalid")
        result.update(
            argv_status="OBSERVED",
            argv_sha256=hashlib.sha256(
                json.dumps(argv, separators=(",", ":")).encode()
            ).hexdigest(),
            approved_extension_flags=extension_flags,
            profile=profile.as_posix(),
        )
    try:
        result["clocks"].append(
            observed_clock(lambda: evaluate(context.new_cdp_session(page), CLOCK_JS), "about_blank")
        )
    except Unknown:
        result["about_blank_clock_status"] = "UNKNOWN"
    targets = root.send("Target.getTargets")["targetInfos"]
    if type(targets) is not list or len(targets) > 100:
        raise Unknown("source_targets_invalid")
    if any(type(t) is not dict for t in targets):
        raise Unknown("source_targets_invalid")
    if any(t.get("type") == "page" and t.get("url") != "about:blank" for t in targets):
        raise Unknown("source_unapproved_page_present")
    candidates = [
        t
        for t in targets
        if t.get("type") == "service_worker"
        and re.fullmatch(r"chrome-extension://[a-p]{32}/observer\.js", t.get("url", ""))
    ]
    if not enabled and candidates:
        raise Unknown("source_baseline_extension_present")
    if enabled and len(candidates) == 1:
        extension_id = candidates[0]["url"].split("/")[2]
        reader = Collector(
            root,
            context,
            extension,
            hashes,
            {
                "exclusive_new_profile": True,
                "initial_entries": [],
                "readonly_mount": True,
                "approved_extension_flags": FLAGS,
                "mount_target": MOUNT,
            },
        )
        reader.discover()
        audit = context.new_page()
        audit.goto(f"chrome-extension://{extension_id}/audit.html", timeout=15000)
        reader.bind_audit_page(audit)
        try:
            snapshot = reader.readback(configure=True)
        except Unknown:
            snapshot = None
        # Read static rules as bytes AND runtime ruleset enablement. No receipt/arm.
        rules = json.loads((extension / "rules.json").read_bytes())
        result.update(
            extension_status="OBSERVED" if snapshot else "UNKNOWN_DNR_READBACK",
            extension_id=extension_id,
            enabled_rulesets=snapshot["enabled_rulesets"] if snapshot else [],
            static_rules=rules,
        )
        audit_clock = """(() => ({epoch_ms:r3Audit.clock().epoch_ms,
          performance_ms:performance.now(),time_origin_ms:performance.timeOrigin}))()"""
        try:
            result["clocks"].append(
                observed_clock(lambda: evaluate(reader.cdp, audit_clock), "trusted_audit")
            )
        except Unknown:
            result["audit_clock_status"] = "UNKNOWN"
        workers = [w for w in context.service_workers if w.url == candidates[0]["url"]]
        if len(workers) == 1:
            try:
                result["clocks"].append(
                    observed_clock(lambda: workers[0].evaluate(CLOCK_JS), "extension_worker")
                )
            except Exception:
                result["worker_clock_status"] = "UNKNOWN"
        else:
            result["worker_clock_status"] = "UNKNOWN"
    elif enabled:
        result["extension_status"] = "UNKNOWN_TARGET_NOT_UNIQUE"
    inventory = context.new_page()
    inventory.goto("chrome://extensions/", timeout=15000)
    if inventory.url != "chrome://extensions/":
        raise Unknown("source_inventory_origin_invalid")
    try:
        value = evaluate(
            context.new_cdp_session(inventory),
            """new Promise(resolve => {
          if(!chrome.developerPrivate) {resolve({ok:false});return;}
          chrome.developerPrivate.getExtensionsInfo(
            {includeDisabled:true,includeTerminated:true}, entries => {
            if(chrome.runtime.lastError || !Array.isArray(entries) || entries.length>100) {
              resolve({ok:false});return;
            }
            resolve({ok:true,entries:entries.map(e=>({id:e.id,state:e.state,type:e.type,location:e.location}))});
          });
        })""",
        )
        if value.get("ok") is True and type(value.get("entries")) is list:
            projected = []
            for item in value["entries"]:
                if type(item) is not dict or not re.fullmatch(r"[a-p]{32}", item.get("id", "")):
                    raise Unknown("inventory_fields_unknown")
                # Enum labels only, not inferred component/filter semantics.
                safe = {"id": item["id"]}
                for key in ("state", "type", "location"):
                    labels = {
                        "ENABLED",
                        "DISABLED",
                        "TERMINATED",
                        "BLOCKLISTED",
                        "EXTENSION",
                        "THEME",
                        "HOSTED_APP",
                        "PLATFORM_APP",
                        "COMPONENT",
                        "INTERNAL",
                        "UNPACKED",
                        "EXTERNAL_PREF",
                        "EXTERNAL_REGISTRY",
                        "EXTERNAL_POLICY",
                        "EXTERNAL_POLICY_DOWNLOAD",
                    }
                    safe[key] = item.get(key) if item.get(key) in labels else "UNRECOGNIZED"
                projected.append(safe)
            result.update(inventory_status="UI_FILTERED_OBSERVED", inventory=projected)
    except Exception:
        result["inventory_status"] = "UNKNOWN"
    result["conclusion"] = "STILL_HAS_SOURCE_GAPS"
    return result
