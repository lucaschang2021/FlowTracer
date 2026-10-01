"""Pure deadline/terminal rules; no process creation or permission surrogate."""

from contract import object_fields, reject


def remaining_timeout_ms(start_ns: int, now_ns: int, limit_ms: int = 15000) -> int:
    if any(type(v) is not int for v in (start_ns, now_ns, limit_ms)):
        reject("invalid_clock")
    if start_ns < 0 or now_ns < start_ns or not 1 <= limit_ms <= 15000:
        reject("invalid_clock")
    remaining = limit_ms - (now_ns - start_ns) // 1000000 - 1000
    if remaining <= 0:
        reject("deadline")
    return min(5000, remaining)


def terminal(value: object) -> None:
    item = object_fields(value, {"outcome", "cleanup", "network_audit", "duration_ms"})
    if (item["outcome"], item["cleanup"], item["network_audit"]) != (
        "completed",
        "owned_removed",
        "complete",
    ):
        reject("invalid_terminal")
    if type(item["duration_ms"]) is not int or not 0 < item["duration_ms"] < 15000:
        reject("invalid_terminal")


def launch_real(*_args, **_kwargs) -> None:
    reject("NO_GO_host_permission_and_adapter_missing")


if __name__ == "__main__":
    raise SystemExit("NO_GO_real_execution_not_authorized")
