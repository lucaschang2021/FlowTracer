from __future__ import annotations

import json
import socket

from proxy.egress_proxy import FIXTURE_IP, _validated_target


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def forbidden_system_dns(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("proxy attempted system DNS")

    socket.getaddrinfo = forbidden_system_dns  # type: ignore[assignment]
    try:
        require(
            _validated_target("fixture-r2.test", 8443) == (FIXTURE_IP, "validated", (FIXTURE_IP,)),
            "declared fixture was not validated",
        )
        expected = {
            "rebind-r2.test": "dns_rebinding",
            "mixed-r2.test": "mixed_answer",
            "loopback-r2.test": "loopback",
            "private-r2.test": "private",
            "linklocal-r2.test": "link_local",
            "metadata-r2.test": "metadata",
            "multicast-r2.test": "multicast",
            "reserved-r2.test": "reserved",
            "unspecified-r2.test": "unspecified",
            "undeclared-r2.test": "not_declared_fixture",
        }
        actual = {host: _validated_target(host, 8443)[1] for host in expected}
        require(actual == expected, "policy denial matrix mismatch")
        require(
            _validated_target("fixture-r2.test", 22)[1] == "dangerous_port",
            "dangerous port was not denied",
        )
        require(
            _validated_target(FIXTURE_IP, 8443)[1] == "direct_ip",
            "direct IP was not denied",
        )
        require(
            _validated_target("unknown-r2.test", 8443)[1] == "undeclared_host",
            "undeclared host was not denied",
        )
    finally:
        socket.getaddrinfo = original_getaddrinfo
    print(json.dumps({"cases": 14, "result": "PASS", "system_dns_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
