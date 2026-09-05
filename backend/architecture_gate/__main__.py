from __future__ import annotations

import argparse
import json
from pathlib import Path

from architecture_gate.gate import ArchitectureError, check_architecture, generate_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="FlowTracer architecture gate")
    parser.add_argument("command", choices=("check", "generate-baseline"))
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root containing ARCHITECTURE.toml",
    )
    parser.add_argument("--output", type=Path, help="Baseline output path")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.command == "generate-baseline":
            output = args.output or repo_root / "backend" / "architecture-baseline.json"
            snapshot = generate_baseline(repo_root, output.resolve())
            print(
                json.dumps(
                    {
                        "status": "generated",
                        "source_commit": snapshot["source_commit"],
                        "findings": len(snapshot["findings"]),
                        "output": str(output),
                    },
                    sort_keys=True,
                )
            )
            return 0
        report = check_architecture(repo_root)
    except ArchitectureError as exc:
        print(json.dumps({"status": "failed", "errors": exc.errors}, sort_keys=True))
        return 1
    print(json.dumps(report.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
