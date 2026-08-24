"""CLI for deterministic active-verification planning and cost observations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.active_verification import (
    evaluate_active_verification,
    evaluate_cost_observation,
    load_active_verification,
)


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m contractgraph_qa.active_verification_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--input", type=Path, required=True)
    cost = sub.add_parser("record-cost")
    cost.add_argument("--input", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = json.loads(args.input.resolve().read_text(encoding="utf-8"))
        if args.command == "plan":
            result = evaluate_active_verification(payload)
        else:
            result = evaluate_cost_observation(payload)
        _emit(result)
        return 0 if result["status"] == "pass" else 2
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa active-verification: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
