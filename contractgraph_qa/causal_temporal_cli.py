"""Executable CLI for causal-temporal Phase 2 verification capabilities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.causal_watchpoints import evaluate_causal_watchpoints, load_causal_watchpoints
from contractgraph_qa.forward_remediation import evaluate_forward_remediation, load_forward_remediation
from contractgraph_qa.independent_witness import evaluate_independent_witness, load_independent_witness
from contractgraph_qa.replication_drift import evaluate_replication_drift, load_replication_drift
from contractgraph_qa.verification_debt import evaluate_verification_debt, load_verification_debt


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m contractgraph_qa.causal_temporal_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("witness", "Independent Witness v0.1 JSON"),
        ("debt", "Verification Debt v0.1 JSON"),
        ("watch", "Causal Watchpoints v0.1 JSON"),
        ("replicate", "Replication Drift v0.1 JSON"),
        ("remediate", "Forward Remediation v0.1 JSON"),
    ):
        child = sub.add_parser(command)
        child.add_argument("--input", type=Path, required=True, help=help_text)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = args.input.resolve()
        if args.command == "witness":
            result = evaluate_independent_witness(load_independent_witness(path))
        elif args.command == "debt":
            result = evaluate_verification_debt(load_verification_debt(path))
        elif args.command == "watch":
            result = evaluate_causal_watchpoints(load_causal_watchpoints(path))
        elif args.command == "replicate":
            result = evaluate_replication_drift(load_replication_drift(path))
        else:
            result = evaluate_forward_remediation(load_forward_remediation(path))
        _emit(result)
        return 0 if result["status"] == "pass" else 2
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa causal-temporal: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
