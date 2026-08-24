"""CLI for causal-temporal Phase 3 proof-integrity capabilities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.proof_integrity import (
    build_durable_manifest,
    evaluate_evidence_readiness,
    evaluate_metamorphic,
    evaluate_root_cause,
    evaluate_subject_freeze,
    evaluate_trace_integrity,
    evaluate_verification_plan,
    verify_durable_manifest,
)


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m contractgraph_qa.proof_integrity_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "plan", "trace", "readiness", "root-cause", "metamorphic"):
        child = sub.add_parser(command)
        child.add_argument("--input", type=Path, required=True)
    build = sub.add_parser("durable-build")
    build.add_argument("--root", type=Path, required=True)
    build.add_argument("--path", action="append", required=True, dest="paths")
    verify = sub.add_parser("durable-verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "freeze":
            result = evaluate_subject_freeze(_load(args.input.resolve()))
        elif args.command == "plan":
            result = evaluate_verification_plan(_load(args.input.resolve()))
        elif args.command == "trace":
            result = evaluate_trace_integrity(_load(args.input.resolve()))
        elif args.command == "readiness":
            result = evaluate_evidence_readiness(_load(args.input.resolve()))
        elif args.command == "root-cause":
            result = evaluate_root_cause(_load(args.input.resolve()))
        elif args.command == "metamorphic":
            result = evaluate_metamorphic(_load(args.input.resolve()))
        elif args.command == "durable-build":
            result = build_durable_manifest(args.root.resolve(), args.paths)
        else:
            result = verify_durable_manifest(
                args.root.resolve(),
                _load(args.manifest.resolve()),
            )
        _emit(result)
        if "status" not in result:
            return 0
        return 0 if result["status"] == "pass" else 2
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa proof-integrity: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
