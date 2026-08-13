#!/usr/bin/env python3
"""Bind an exact causal-security gate result into a client proof pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.client_proof import attach_change_gate_evidence


def _load_object(path: Path, label: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind the exact machine change-gate JSON into a client proof pack"
    )
    parser.add_argument("--proof", type=Path, required=True, help="Client proof JSON")
    parser.add_argument(
        "--gate-result",
        type=Path,
        required=True,
        help="Causal security gate JSON artifact",
    )
    parser.add_argument("--output", type=Path, required=True, help="Bound proof JSON")
    args = parser.parse_args()

    proof = _load_object(args.proof.resolve(), "client proof")
    gate_result = _load_object(args.gate_result.resolve(), "change-gate result")
    bound = attach_change_gate_evidence(proof, gate_result)

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(bound, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
