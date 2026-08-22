"""Compatibility CLI dispatcher with agent-payment product commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision_file,
)
from contractgraph_qa.economic_cardinality import (
    load_economic_cardinality_model,
    run_economic_cardinality_model,
)
from contractgraph_qa.lifecycle_liveness import (
    load_lifecycle_liveness_model,
    run_lifecycle_liveness_model,
)
from contractgraph_qa.payment_evidence_pack import (
    PaymentEvidencePackError,
    build_payment_evidence_pack,
    verify_payment_evidence_pack,
)
from contractgraph_qa.solidity_lifecycle_extractor import (
    check_lifecycle_from_ast,
    load_ast_file,
    load_forge_ast,
    load_lifecycle_profile,
)
from contractgraph_qa.successor_consistency import (
    load_successor_consistency_model,
    run_successor_consistency_model,
)
from contractgraph_qa import legacy_cli

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_RUNTIME = legacy_cli.EXIT_RUNTIME
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _emit(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _decision_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa agent-payment-decision",
        description="Derive one fail-closed next action from normalized agent-payment state.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Unified Agent Payment Decision Input v0.1 JSON",
    )
    args = parser.parse_args(argv)
    try:
        _emit(evaluate_agent_payment_decision_file(args.input.resolve()))
        return EXIT_OK
    except (AgentPaymentDecisionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _lifecycle_liveness_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa lifecycle-liveness",
        description=(
            "Verify that every reachable state holding locked economic value "
            "retains a path to a declared safe economic terminal."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Lifecycle liveness model JSON",
    )
    args = parser.parse_args(argv)
    try:
        model = load_lifecycle_liveness_model(args.model.resolve())
        result = run_lifecycle_liveness_model(model)
        _emit(result)
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _solidity_lifecycle_check_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa solidity-lifecycle-check",
        description=(
            "Extract lifecycle transitions from Solidity compiler AST evidence and "
            "run deterministic economic liveness verification."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--ast",
        type=Path,
        help="Pre-captured Solidity compiler AST JSON",
    )
    source.add_argument(
        "--target",
        help="Foundry contract target passed to `forge inspect <target> ast`",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Reviewed Solidity lifecycle extraction profile JSON",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Optional Foundry project root when --target is used",
    )
    args = parser.parse_args(argv)
    try:
        profile = load_lifecycle_profile(args.profile.resolve())
        if args.ast is not None:
            ast = load_ast_file(args.ast.resolve())
        else:
            ast = load_forge_ast(args.target, args.root)
        result = check_lifecycle_from_ast(ast, profile)
        _emit(result)
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _economic_cardinality_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa economic-cardinality",
        description=(
            "Verify that each logical action/effect slot produces at most one "
            "distinct confirmed economic occurrence."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Economic effect cardinality model JSON",
    )
    args = parser.parse_args(argv)
    try:
        model = load_economic_cardinality_model(args.model.resolve())
        result = run_economic_cardinality_model(model)
        _emit(result)
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _successor_consistency_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa successor-consistency",
        description=(
            "Verify that one conflict-domain parent state version produces at most "
            "one distinct committed child commit."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Successor consistency model JSON",
    )
    args = parser.parse_args(argv)
    try:
        model = load_successor_consistency_model(args.model.resolve())
        result = run_successor_consistency_model(model)
        _emit(result)
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _evidence_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa agent-payment-evidence-pack",
        description="Build a deterministic customer-facing evidence ZIP from agent-payment state.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Unified Agent Payment Decision Input v0.1 JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination evidence ZIP",
    )
    args = parser.parse_args(argv)
    try:
        _emit(build_payment_evidence_pack(args.input.resolve(), args.output.resolve()))
        return EXIT_OK
    except (PaymentEvidencePackError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _verify_evidence_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa verify-agent-payment-evidence-pack",
        description="Verify hashes and recompute the decision in an Agent Payment Evidence Pack.",
    )
    parser.add_argument("bundle", type=Path, help="Evidence ZIP to verify")
    args = parser.parse_args(argv)
    try:
        _emit(verify_payment_evidence_pack(args.bundle.resolve()))
        return EXIT_OK
    except (PaymentEvidencePackError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    if effective and effective[0] == "agent-payment-decision":
        return _decision_main(effective[1:])
    if effective and effective[0] == "lifecycle-liveness":
        return _lifecycle_liveness_main(effective[1:])
    if effective and effective[0] == "solidity-lifecycle-check":
        return _solidity_lifecycle_check_main(effective[1:])
    if effective and effective[0] == "economic-cardinality":
        return _economic_cardinality_main(effective[1:])
    if effective and effective[0] == "successor-consistency":
        return _successor_consistency_main(effective[1:])
    if effective and effective[0] == "agent-payment-evidence-pack":
        return _evidence_pack_main(effective[1:])
    if effective and effective[0] == "verify-agent-payment-evidence-pack":
        return _verify_evidence_pack_main(effective[1:])
    return legacy_cli.main(effective)


if __name__ == "__main__":
    raise SystemExit(main())
