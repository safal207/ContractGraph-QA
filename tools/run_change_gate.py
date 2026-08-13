#!/usr/bin/env python3
"""Run the repository-owned causal security change gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.change_gate import ChangeGateError, run_change_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run causal-security reachability regression gate")
    parser.add_argument("--base-ref", required=True, help="Exact git base ref or commit")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("causal-security-gate.toml"),
        help="Repository-owned gate config",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository checkout root",
    )
    args = parser.parse_args()

    try:
        result = run_change_gate(
            args.config.resolve(),
            args.base_ref,
            repo_root=args.repo_root.resolve(),
        )
    except (ChangeGateError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 10

    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
