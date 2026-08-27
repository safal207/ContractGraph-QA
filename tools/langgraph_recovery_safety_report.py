#!/usr/bin/env python3
"""Evaluate one or more LangGraph recovery-safety observation JSON files."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contractgraph_qa.integrations.langgraph_recovery_safety import (
    evaluate_recovery_safety,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _load_observations(paths: list[Path]) -> list[Mapping[str, Any]]:
    observations: list[Mapping[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            if not all(isinstance(item, Mapping) for item in payload):
                raise ValueError(f"{path} contains a non-object observation")
            observations.extend(payload)
        elif isinstance(payload, Mapping):
            observations.append(payload)
        else:
            raise ValueError(f"{path} must contain an observation or observation list")
    return observations


def main() -> int:
    args = _parse_args()
    payload = evaluate_recovery_safety(_load_observations(args.observations)).to_dict()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
