"""Command-line interface for the ContractGraph-QA product runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import __version__
from contractgraph_qa.product import (
    ProductError,
    doctor,
    fingerprint_manifest,
    load_product_config,
    run_pipeline,
    validate_manifest_result,
    verify_evidence_bundle,
)

EXIT_OK = 0
EXIT_VALIDATION = 10
EXIT_RUNTIME = 20
EXIT_INTERNAL = 70


def _emit(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cgqa",
        description="ContractGraph-QA: causal-temporal smart-contract QA evidence pipeline.",
    )
    parser.add_argument("--version", action="version", version=f"cgqa {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run capture → export → report → evidence-bundle pipeline")
    run.add_argument("--config", type=Path, required=True, help="Product TOML config")
    run.add_argument("--clean", action="store_true", help="Remove generated outputs before running")

    validate = subparsers.add_parser("validate", help="Validate a manifest and optional explorer result")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--result", type=Path)

    fingerprint = subparsers.add_parser("fingerprint", help="Print canonical manifest SHA-256")
    fingerprint.add_argument("--manifest", type=Path, required=True)

    verify = subparsers.add_parser("verify-bundle", help="Verify evidence ZIP integrity and semantic chain")
    verify.add_argument("bundle", type=Path)

    doctor_parser = subparsers.add_parser("doctor", help="Check runtime dependencies")
    doctor_parser.add_argument("--require-forge", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            config = load_product_config(args.config)
            _emit(run_pipeline(config, clean=args.clean))
            return EXIT_OK
        if args.command == "validate":
            _emit(validate_manifest_result(args.manifest.resolve(), args.result.resolve() if args.result else None))
            return EXIT_OK
        if args.command == "fingerprint":
            _emit({"manifestSha256": fingerprint_manifest(args.manifest.resolve())})
            return EXIT_OK
        if args.command == "verify-bundle":
            _emit(verify_evidence_bundle(args.bundle))
            return EXIT_OK
        if args.command == "doctor":
            _emit(doctor(require_forge=args.require_forge))
            return EXIT_OK
        parser.error("unknown command")
    except (ValueError, ProductError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION if args.command in {"validate", "fingerprint", "verify-bundle"} else EXIT_RUNTIME
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
