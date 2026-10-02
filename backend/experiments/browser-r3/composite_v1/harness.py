"""Pure synthetic graph builder and explicit, non-executing runtime wiring plan."""

from typing import Protocol
from urllib.parse import urlsplit

from collector import Collector, DriverRecords, join_network_receipts
from contract import LIMITS, MATRIX, POLICY, Rejected, identifier, reject
from fixture import response
from supervisor import remaining_timeout_ms


class HostPort(Protocol):
    """Host runtime/authority boundary, not a page-authored or synthetic Boolean."""

    def verify_runtime(self) -> None: ...
    def verify_browser(self, page, timeout_ms: int) -> None: ...
    def run_callback(self, callback): ...
    def execution_id(self) -> str: ...
    def clock_ns(self) -> int: ...
    def arm_parent_deadline(self, milliseconds: int) -> None: ...
    def check_target(self, url: str) -> None: ...
    def install_native_denials(self, context, on_denial) -> None: ...
    def request_id(self, request, route: str, parent_id: str | None) -> str: ...
    def bind_forwarding(self, request, request_id: str, expected_bytes: int) -> None: ...
    def application_denied(self, route: str, request_id: str) -> None: ...
    def attest_worker_attempt(self, page) -> None: ...
    def verify_native_matrix(self) -> None: ...
    def network_receipts(self, application_records: dict) -> bytes: ...
    def close_and_reap_owned(self) -> None: ...


class PolicyHooks:
    """Fixed local fixture scope plus mandatory Operator checks, before forwarding."""

    def __init__(self, host: HostPort) -> None:
        self.host = host
        self.started = host.clock_ns()
        self.records = DriverRecords()
        self.request_ids = {}
        self.route_ids = {}
        self.used = dict.fromkeys(LIMITS, 0)
        self.failure = None
        self.installed = False
        self.action_finished = False

    def timeout(self) -> int:
        return remaining_timeout_ms(self.started, self.host.clock_ns())

    def classify(self, url: str, *, websocket: bool = False) -> str:
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme != ("wss" if websocket else "https")
                or parsed.hostname != "navigation-r3.test"
                or parsed.port != 8443
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.netloc != "navigation-r3.test:8443"
            ):
                reject("fixture_scope_denied")
            route = parsed.path.removeprefix("/")
            if route not in MATRIX:
                reject("fixture_scope_denied")
            return route
        except (TypeError, ValueError):
            reject("fixture_scope_denied")

    def setup(self, page) -> None:
        self.timeout()
        self.host.verify_browser(page, self.timeout())
        # Actual worker/popup/SW pre-creation enforcement must be installed and attested.
        # Missing native adapter raises; context routing is NOT claimed to cover workers.
        context = page.context
        self.host.install_native_denials(
            context, lambda *args: self.host.run_callback(lambda: self.native_denial(*args))
        )
        context.route(
            "**/*",
            lambda route, request: self.host.run_callback(lambda: self.http_route(route, request)),
        )
        context.route_web_socket(
            "**/*", lambda socket: self.host.run_callback(lambda: self.page_websocket(socket))
        )
        page.set_default_timeout(self.timeout())
        self.installed = True

    def mapping(self, request, route: str) -> tuple[str, str | None]:
        previous = getattr(request, "redirected_from", None)
        if previous is not None:
            if id(previous) not in self.request_ids or route != "redirect-end":
                reject("redirect_mapping_unknown")
            parent = self.request_ids[id(previous)]
        else:
            parent = None if route == "navigation" else self.route_ids.get("navigation")
        if route != "navigation" and parent is None:
            reject("parent_mapping_unknown")
        request_id = identifier(self.host.request_id(request, route, parent))
        if request_id in self.request_ids.values():
            reject("duplicate_request_mapping")
        self.request_ids[id(request)] = request_id
        self.route_ids[route] = request_id
        return request_id, parent

    def http_route(self, route, request) -> None:
        try:
            self.timeout()
            name = self.classify(request.url)
            self.host.check_target(request.url)  # Operator Network/Site policy cannot be bypassed
            request_id, parent = self.mapping(request, name)
            action = MATRIX[name][2]
            if name in {"page-ws", "worker-ws", "popup", "sw-register", "sw-update", "sw-fetch"}:
                reject("wrong_surface_observer")
            self.records.add(name, request_id, action, parent)
            if action == "deny":
                route.abort("blockedbyclient")
                self.host.application_denied(name, request_id)
                return
            body_size = len(response(name)[1])
            delta = {
                "requests": 1,
                "pages": int(name in {"navigation", "iframe", "redirect-start"}),
                "bytes": body_size,
            }
            for field, limit in LIMITS.items():
                if self.used[field] + delta[field] > limit:
                    reject("budget_exhausted")
            self.host.bind_forwarding(request, request_id, body_size)
            self.timeout()
            for field in self.used:
                self.used[field] += delta[field]
            route.continue_(headers={**request.headers, "x-r3-request-id": request_id})
        except Exception:
            self.failure = "application_route_failed"
            route.abort("blockedbyclient")
            reject(self.failure)

    def page_websocket(self, socket) -> None:
        try:
            self.timeout()
            name = self.classify(socket.url, websocket=True)
            if name != "page-ws":
                reject("worker_requires_native_observer")
            self.host.check_target(socket.url.replace("wss://", "https://", 1))
            request_id = identifier(
                self.host.request_id(socket, name, self.route_ids.get("navigation"))
            )
            self.records.add(name, request_id, "deny", self.route_ids.get("navigation"))
            socket.close(code=1008, reason="default_deny")
            self.host.application_denied(name, request_id)
        except Exception:
            self.failure = "websocket_denial_unknown"
            reject(self.failure)

    def native_denial(self, name: str, request_id: str, parent_id: str | None) -> None:
        try:
            self.timeout()
            if name not in {"worker-ws", "popup", "sw-register"}:
                reject("native_surface_unknown")
            expected_parent = self.route_ids.get(
                "worker-script" if name == "worker-ws" else "navigation"
            )
            if expected_parent is None or parent_id != expected_parent:
                reject("native_parent_unknown")
            self.records.add(name, identifier(request_id), "deny", parent_id)
            self.host.application_denied(name, request_id)
        except Exception:
            self.failure = "native_denial_unknown"
            reject(self.failure)

    def action(self, page) -> None:
        if not self.installed:
            reject("policy_not_installed")
        page.evaluate("() => composite.xhr()")
        page.evaluate("() => composite.fetch()")
        page.evaluate("() => composite.workerWS()")
        self.host.attest_worker_attempt(page)  # real ready AND attempt AND native denial required
        page.evaluate("() => composite.pageWS()")
        page.locator("#download").click(timeout=self.timeout(), no_wait_after=True)
        page.evaluate("() => composite.popup()")
        page.evaluate("() => composite.register().catch(() => null)")
        self.host.verify_native_matrix()  # exceptions/empty logs do not prove denial
        page.goto(
            "https://navigation-r3.test:8443/redirect-start",
            timeout=self.timeout(),
            wait_until="load",
        )
        if self.failure is not None:
            reject(self.failure)
        self.action_finished = True


def _execute_driver(host: HostPort, fetch) -> dict:
    """Internal hook wiring; injecting a test fetch never grants actual runtime authority."""
    try:
        host.verify_runtime()
        host.arm_parent_deadline(15000)
        hooks = PolicyHooks(host)
        fetch(
            "https://navigation-r3.test:8443/navigation",
            headless=True,
            proxy="http://198.51.100.20:18080",
            retries=1,
            timeout=hooks.timeout(),
            page_setup=lambda page: host.run_callback(lambda: hooks.setup(page)),
            page_action=lambda page: host.run_callback(lambda: hooks.action(page)),
            google_search=False,
            disable_resources=False,
            network_idle=False,
            executable_path="/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
            user_data_dir="/tmp/r3-composite-profile",  # noqa: S108 - proposed exclusive tmpfs
            additional_args={"ignore_https_errors": True},
            extra_flags=[
                "--ignore-certificate-errors",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
            ],
        )
        hooks.timeout()
        if hooks.failure is not None or not hooks.installed or not hooks.action_finished:
            reject(hooks.failure or "driver_incomplete")
        records = hooks.records.snapshot()
        actual = {record["route"] for record in records["application_records"]}
        if actual != set(MATRIX) - {"sw-update", "sw-fetch"}:
            reject("incomplete_application_matrix")
        join_network_receipts(records, host.network_receipts(records), host.execution_id())
        return {"status": "WIRING_RETURNED_NOT_R3_PASS", **records}
    except Exception:
        raise Rejected("driver_or_mapping_failed") from None
    finally:
        try:
            host.close_and_reap_owned()
        except Exception:
            raise Rejected("cleanup_unknown") from None


def synthetic_graph() -> bytes:
    execution = "SYNTHETIC-composite-001"
    collector = Collector(
        {
            "candidate_sha": "0" * 40,
            "input_sha": "0" * 64,
            "image_sha": "0" * 64,
            "payload_sha": "0" * 64,
            "manifest_sha": "0" * 64,
            "driver": "DynamicFetcher.fetch",
            "policy": POLICY,
            "r1e": "R1E-PR66",
            "r2c": "R2C-A4-PR68",
            "source": "synthetic_host",
        },
        execution,
    )
    for index, (route, (surface, actor, action, parent)) in enumerate(MATRIX.items(), 1):
        trigger_id, decision_id = "t-" + route, "d-" + route
        request_id = None if parent else "r-" + route
        parent_route = parent or ("redirect-start" if route == "redirect-end" else "navigation")
        if route == "worker-ws":
            parent_route = "worker-script"
        collector.append(
            "triggers",
            {
                "id": trigger_id,
                "execution_id": execution,
                "clock": "app",
                "seq": index * 3,
                "route": route,
                "surface": surface,
                "actor": actor,
                "parent_id": None if route == "navigation" else "t-" + parent_route,
                "request_id": request_id,
                "result": "PREVENTED_BY_DENIED_PARENT" if parent else "TRIGGERED",
            },
        )
        collector.append(
            "decisions",
            {
                "id": decision_id,
                "execution_id": execution,
                "clock": "app",
                "seq": index * 3 + 1,
                "trigger_id": trigger_id,
                "request_id": request_id,
                "action": action,
                "reason": "denied_parent"
                if parent
                else ("policy_allow" if action == "allow" else "default_deny"),
                "checks": {
                    "network": "PASS",
                    "site": "PASS",
                    "scope": "PASS",
                    "budget": "PASS",
                    "capability": "PASS" if action == "allow" else "DENY",
                },
                "used": {"requests": 1 if action == "allow" else 0, "pages": 0, "bytes": 0},
            },
        )
        sources = (
            {"app": "continued", "proxy": "forwarded", "fixture": "received"}
            if action == "allow"
            else {
                "app": "parent_prevented" if parent else "application_denied",
                "host-network": "parent_prevented" if parent else "policy_prevented_no_egress",
            }
        )
        for source, result in sources.items():
            collector.append(
                "observations",
                {
                    "id": "o-" + source + "-" + route,
                    "execution_id": execution,
                    "clock": source,
                    "seq": index * 3 + 2,
                    "trigger_id": trigger_id,
                    "decision_id": decision_id,
                    "request_id": request_id,
                    "source": source,
                    "result": result,
                    "actor": actor,
                    "transport_id": source + "-" + route
                    if source in {"proxy", "fixture"}
                    else None,
                },
            )
    return collector.finish(
        {
            "outcome": "completed",
            "cleanup": "owned_removed",
            "network_audit": "complete",
            "duration_ms": 1000,
        }
    )


def wiring_plan() -> dict:
    return {
        "status": "NO_GO",
        "driver": "DynamicFetcher.fetch",
        "page_setup": "install policy before navigation; host-owned trigger and decision mapping",
        "page_action": list(MATRIX),
        "budget_limits": dict(LIMITS),
        "missing": [
            "exact host permit",
            "host runtime binding and native-denial ports",
            "trusted CONNECT-to-request mapping receipts",
            "host deadline and owned-reap implementation",
        ],
    }


if __name__ == "__main__":
    raise SystemExit("NO_GO_real_execution_not_authorized")
