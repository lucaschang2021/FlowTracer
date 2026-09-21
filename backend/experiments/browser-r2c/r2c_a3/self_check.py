from __future__ import annotations

import json

from proxy.egress_proxy import FIXTURE_IP, _validated_target


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    target, reason, passes = _validated_target("fixture-r2c.test", 8443)
    require(target == FIXTURE_IP and reason == "validated", "fixture allow failed")
    require(len(passes) == 2, "fixture did not use two resolution passes")
    require(
        all(set(value) == {"A", "AAAA"} for value in passes),
        "resolution pass omitted A or AAAA",
    )
    expected = {
        "rebind-r2c.test": "dns_rebinding",
        "mixed-r2c.test": "mixed_answer",
        "loopback-r2c.test": "loopback",
        "private-r2c.test": "private",
        "linklocal-r2c.test": "link_local",
        "metadata-r2c.test": "metadata",
        "multicast-r2c.test": "multicast",
        "reserved-r2c.test": "reserved",
        "unspecified-r2c.test": "unspecified",
        "undeclared-r2c.test": "not_declared_fixture",
    }
    actual = {host: _validated_target(host, 8443)[1] for host in expected}
    require(actual == expected, f"deny policy mismatch: {actual}")
    require(
        _validated_target("fixture-r2c.test", 22)[1] == "dangerous_port",
        "dangerous port was not denied",
    )
    require(
        _validated_target(FIXTURE_IP, 8443)[1] == "direct_ip",
        "direct IP was not denied",
    )
    require(
        _validated_target("unknown-r2c.test", 8443)[1] == "undeclared_host",
        "unknown host was not denied",
    )
    print(
        json.dumps(
            {
                "a_aaaa_each_pass": True,
                "deny_cases": len(expected) + 3,
                "resolution_passes": 2,
                "result": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
