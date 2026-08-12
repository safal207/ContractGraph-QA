"""Command-line interface for the ContractGraph-QA product runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import __version__
from contractgraph_qa.demo import run_demo
from contractgraph_qa.engagement import (
    EngagementError,
    verify_engagement_bundle,
    write_engagement_bundle,
)
from contractgraph_qa.engagement_run import (
    EngagementRunError,
    load_engagement_run_config,
    run_engagement_pipeline,
)
from contractgraph_qa.payment_recovery import (
    PaymentRecoveryError,
    evaluate_payment_recovery_file,
)
from contractgraph_qa.product import (
    ProductError,
    doctor,
    fingerprint_manifest,
    load_product_config,
    run_pipeline,
    validate_manifest_result,
    verify_evidence_bundle,
)
from contractgraph_qa.provider_adapter import (
    ProviderAdapterError,
    load_provider_adapter,
    reconcile_provider_files,
    validate_provider_adapter,
)
from contractgraph_qa.scaffold import ScaffoldError, init_engagement

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

    demo = subparsers.add_parser(
        "demo",
        help="Generate and verify a repository-owned demo evidence bundle without Forge",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("cgqa-demo"),
        help="Fresh destination directory; defaults to ./cgqa-demo",
    )

    init = subparsers.add_parser(
        "init-engagement",
        help="Create a fail-closed client engagement scaffold",
    )
    init.add_argument("name", help="Safe engagement identifier")
    init.add_argument(
        "--directory",
        type=Path,
        help="Destination directory; defaults to ./engagements/<name>",
    )

    run = subparsers.add_parser("run", help="Run capture → export → report → evidence-bundle pipeline")
    run.add_argument("--config", type=Path, required=True, help="Product TOML config")
    run.add_argument("--clean", action="store_true", help="Remove generated outputs before running")

    engagement_run = subparsers.add_parser(
        "engagement-run",
        help="Run direct multi-invariant Foundry capture → engagement evidence pipeline",
    )
    engagement_run.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Engagement-run TOML config",
    )

    engagement = subparsers.add_parser(
        "engagement",
        help="Build a multi-invariant engagement report, findings, and evidence bundle",
    )
    engagement.add_argument("--manifest", type=Path, required=True)
    engagement.add_argument("--result", type=Path, required=True, help="Multi-check engagement result JSON")
    engagement.add_argument("--output-dir", type=Path, required=True)
    engagement.add_argument("--bundle", type=Path, required=True)

    validate = subparsers.add_parser("validate", help="Validate a manifest and optional explorer result")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--result", type=Path)

    fingerprint = subparsers.add_parser("fingerprint", help="Print canonical manifest SHA-256")
    fingerprint.add_argument("--manifest", type=Path, required=True)

    verify = subparsers.add_parser("verify-bundle", help="Verify single-finding evidence ZIP integrity and semantic chain")
    verify.add_argument("bundle", type=Path)

    verify_engagement = subparsers.add_parser(
        "verify-engagement-bundle",
        help="Verify a multi-invariant engagement ZIP and its full semantic chain",
    )
    verify_engagement.add_argument("bundle", type=Path)

    payment_recovery = subparsers.add_parser(
        "payment-recovery-evaluate",
        help="Evaluate a vendor-neutral agent-payment recovery trace",
    )
    payment_recovery.add_argument(
        "--scenario",
        type=Path,
        required=True,
        help="Agent Payment Recovery Benchmark v0.1 scenario JSON",
    )

    provider_adapter_validate = subparsers.add_parser(
        "provider-adapter-validate",
        help="Validate a Provider Adapter Contract v0.1 profile",
    )
    provider_adapter_validate.add_argument(
        "--adapter",
        type=Path,
        required=True,
        help="Provider Adapter Contract v0.1 JSON",
    )

    provider_adapter_reconcile = subparsers.add_parser(
        "provider-adapter-reconcile",
        help="Normalize provider evidence into a fail-closed reconciliation decision",
    )
    provider_adapter_reconcile.add_argument(
        "--adapter",
        type=Path,
        required=True,
        help="Provider Adapter Contract v0.1 JSON",
    )
    provider_adapter_reconcile.add_argument(
        "--observations",
        type=Path,
        required=True,
        help="Captured provider observation JSON",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Check runtime dependencies")
    doctor_parser.add_argument("--require-forge", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            _emit(run_demo(args.output_dir))
            return EXIT_OK
        if args.command == "init-engagement":
            _emit(init_engagement(args.name, args.directory))
            return EXIT_OK
        if args.command == "run":
            config = load_product_config(args.config)
            _emit(run_pipeline(config, clean=args.clean))
            return EXIT_OK
        if args.command == "engagement-run":
            config = load_engagement_run_config(args.config)
            _emit(run_engagement_pipeline(config))
            return EXIT_OK
        if args.command == "engagement":
            _emit(
                write_engagement_bundle(
                    args.manifest.resolve(),
                    args.result.resolve(),
                    args.output_dir.resolve(),
                    args.bundle.resolve(),
                )
            )
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
        if args.command == "verify-engagement-bundle":
            _emit(verify_engagement_bundle(args.bundle))
            return EXIT_OK
        if args.command == "payment-recovery-evaluate":
            result = evaluate_payment_recovery_file(args.scenario.resolve())
            _emit(result)
            return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
        if args.command == "provider-adapter-validate":
            adapter = load_provider_adapter(args.adapter.resolve())
            _emit(validate_provider_adapter(adapter))
            return EXIT_OK
        if args.command == "provider-adapter-reconcile":
            result = reconcile_provider_files(
                args.adapter.resolve(),
                args.observations.resolve(),
            )
            _emit(result)
            return EXIT_OK if result["status"] == "final" else EXIT_VALIDATION
        if args.command == "doctor":
            _emit(doctor(require_forge=args.require_forge))
            return EXIT_OK
        parser.error("unknown command")
    except (
        ValueError,
        ProductError,
        EngagementError,
        EngagementRunError,
        ScaffoldError,
        PaymentRecoveryError,
        ProviderAdapterError,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        validation_commands = {
            "validate",
            "fingerprint",
            "verify-bundle",
            "verify-engagement-bundle",
            "payment-recovery-evaluate",
            "provider-adapter-validate",
            "provider-adapter-reconcile",
        }
        return EXIT_VALIDATION if args.command in validation_commands else EXIT_RUNTIME
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
