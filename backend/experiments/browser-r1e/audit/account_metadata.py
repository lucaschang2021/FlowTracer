from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path


def summarize(lines: Iterable[str]) -> dict[str, object]:
    records = []
    for raw in lines:
        fields = raw.rstrip("\n").split(":")
        if fields and fields[0] == "flowtracer":
            records.append(fields)
    record = records[0] if len(records) == 1 else []
    summary: dict[str, object] = {
        "account_name": "flowtracer",
        "record_count": len(records),
        "field_count": len(record),
        "password_locked": bool(record and record[1].startswith("!")),
        "sp_lstchg": record[2] if len(record) > 2 else None,
    }
    if summary != {
        "account_name": "flowtracer",
        "field_count": 9,
        "password_locked": True,
        "record_count": 1,
        "sp_lstchg": "0",
    }:
        raise RuntimeError("flowtracer account metadata structure mismatch")
    return summary


def self_check() -> dict[str, object]:
    valid = "flowtracer:!:0:0:99999:7:::\n"
    if summarize(valid.splitlines(keepends=True))["sp_lstchg"] != "0":
        raise RuntimeError("valid deterministic account rejected")
    invalid = (
        "flowtracer:x:0:0:99999:7:::\n",
        "flowtracer:!:1:0:99999:7:::\n",
        "flowtracer:!:0:0:99999:7::\n",
        valid + valid,
    )
    for sample in invalid:
        try:
            summarize(sample.splitlines(keepends=True))
        except RuntimeError:
            continue
        raise RuntimeError("invalid account metadata accepted")
    return {"negative_cases": len(invalid), "status": "PASS"}


def main() -> None:
    if sys.argv[1:] == ["--self-check"]:
        print(json.dumps(self_check(), sort_keys=True))
        return
    if sys.argv[1:]:
        raise SystemExit("unexpected arguments")
    print(
        json.dumps(
            summarize(Path("/etc/shadow").read_text(encoding="utf-8").splitlines()),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
