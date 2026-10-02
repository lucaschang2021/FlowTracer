"""Copy-safe SYNTHETIC collector; cannot sign runtime authority."""

from contract import canonical, reject, strict_json


class DriverRecords:
    """Application-only records; no manufactured proxy/runtime authority."""

    def __init__(self) -> None:
        self._events = []
        self._routes = set()
        self._request_ids = set()

    def add(self, route: str, request_id: str, action: str, parent_id: str | None) -> None:
        from contract import MATRIX, identifier

        if route not in MATRIX or route in self._routes or action != MATRIX[route][2]:
            reject("ambiguous_application_mapping")
        identifier(request_id)
        if request_id in self._request_ids:
            reject("duplicate_application_request")
        self._request_ids.add(request_id)
        if parent_id is not None:
            identifier(parent_id)
        self._routes.add(route)
        self._events.append(
            {"route": route, "request_id": request_id, "action": action, "parent_id": parent_id}
        )

    def snapshot(self) -> dict:
        return strict_json(canonical({"application_records": self._events}))


def _join_network_receipts(records: dict, raw: bytes, execution_id: str) -> None:
    """Join host-provided receipts, NOT authenticate their host provenance.

    Only the later frozen host boundary may supply real receipts. Stub bytes are SYNTHETIC.
    Never infer tunnel/request equality or non-forwarding from timing/empty logs.
    """
    from contract import MATRIX, identifier, integer, object_fields
    from fixture import response

    graph = object_fields(strict_json(raw), {"execution_id", "kind", "receipts"})
    if graph["execution_id"] != identifier(execution_id):
        reject("network_cross_execution")
    if graph["kind"] not in {"SYNTHETIC", "HOST_VERIFIED"}:
        reject("network_source_unknown")
    if type(graph["receipts"]) is not list or len(graph["receipts"]) > 100:
        reject("network_receipts_unknown")
    by_id = {r["request_id"]: r for r in records["application_records"]}
    joined = {key: set() for key in by_id}
    vendor_ids = set()
    for value in graph["receipts"]:
        receipt = object_fields(
            value,
            {
                "request_id",
                "route",
                "parent_id",
                "actor",
                "source",
                "transport_id",
                "outcome",
                "body_bytes",
            },
        )
        request_id = identifier(receipt["request_id"])
        if request_id not in by_id:
            reject("network_request_unknown")
        app = by_id[request_id]
        if (receipt["route"], receipt["parent_id"], receipt["actor"]) != (
            app["route"],
            app["parent_id"],
            MATRIX[app["route"]][1],
        ):
            reject("network_mapping_conflict")
        expected = (
            {"proxy": "forwarded", "fixture": "received"}
            if app["action"] == "allow"
            else {
                "host-network": "application_prevented",
            }
        )
        source = receipt["source"]
        if type(source) is not str or source not in expected or source in joined[request_id]:
            reject("network_source_unknown")
        if receipt["outcome"] != expected[source]:
            reject("application_denial_not_proven")
        expected_bytes = len(response(app["route"])[1]) if app["action"] == "allow" else 0
        if integer(receipt["body_bytes"]) != expected_bytes:
            reject("network_bytes_mismatch")
        if app["action"] == "allow":
            vendor = (source, identifier(receipt["transport_id"]))
            if vendor in vendor_ids:
                reject("network_vendor_conflict")
            vendor_ids.add(vendor)
        elif receipt["transport_id"] is not None:
            reject("denied_forwarding")
        joined[request_id].add(source)
    for key, sources in joined.items():
        expected = {"proxy", "fixture"} if by_id[key]["action"] == "allow" else {"host-network"}
        if sources != expected:
            reject("network_receipt_missing")


def join_network_receipts(records: dict, raw: bytes, execution_id: str) -> None:
    try:
        _join_network_receipts(records, raw, execution_id)
    except (TypeError, KeyError, OverflowError):
        reject("network_receipt_type_invalid")


class Collector:
    def __init__(self, binding: dict, execution_id: str) -> None:
        self._graph = {
            "schema": "r3-composite-v1",
            "kind": "SYNTHETIC",
            "execution_id": execution_id,
            "binding": strict_json(canonical(binding)),
            "triggers": [],
            "decisions": [],
            "observations": [],
            "completion": None,
        }

    def append(self, category: str, record: dict) -> None:
        if category not in {"triggers", "decisions", "observations"}:
            reject("invalid_category")
        if len(self._graph[category]) >= 100:
            reject("record_limit")
        self._graph[category].append(strict_json(canonical(record)))

    def finish(self, completion: dict) -> bytes:
        result = strict_json(canonical(self._graph))
        result["completion"] = strict_json(canonical(completion))
        return canonical(result)
