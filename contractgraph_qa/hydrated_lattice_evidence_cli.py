"""Build and verify deterministic Hydrated Contract Lattice evidence packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.hydrated_lattice_evidence import (
    HydratedLatticeEvidencePackError,
    build_hydrated_lattice_evidence_pack,
    verify_hydrated_lattice_evidence_pack,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cgqa-hydrated-evidence",
        description="Build or independently replay-verify a deterministic Hydrated Contract Lattice evidence ZIP.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a deterministic evidence ZIP")
    build.add_argument("--static-result", type=Path, required=True, help="Hydrated-lattice static result JSON")
    build.add_argument("--trace", type=Path, required=True, help="Normalized ExecutionTrace JSON")
    build.add_argument("--bindings", type=Path, required=True, help="Hydration bindings JSON")
    build.add_argument("--output", type=Path, required=True, help="Output ZIP path")

    verify = sub.add_parser("verify", help="Verify deterministic bytes and exact local replay")
    verify.add_argument("--pack", type=Path, required=True, help="Evidence ZIP path")
    verify.add_argument(
        "--expected-sha256",
        help="Optional separately obtained complete-pack SHA-256 external integrity anchor",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_hydrated_lattice_evidence_pack(
                args.static_result.resolve(),
                args.trace.resolve(),
                args.bindings.resolve(),
                args.output.resolve(),
            )
        else:
            result = verify_hydrated_lattice_evidence_pack(
                args.pack.resolve(), expected_pack_sha256=args.expected_sha256
            )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK
    except (HydratedLatticeEvidencePackError, ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"cgqa-hydrated-evidence: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-hydrated-evidence: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-hydrated-evidence: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
