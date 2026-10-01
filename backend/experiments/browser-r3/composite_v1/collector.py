"""Copy-safe SYNTHETIC collector; cannot sign runtime authority."""

from contract import canonical, reject, strict_json


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
