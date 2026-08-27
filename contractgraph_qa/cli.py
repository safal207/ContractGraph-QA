"""Unified ContractGraph-QA CLI dispatcher."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import (
    active_verification_cli,
    causal_temporal_cli,
    legacy_cli,
    ltp_continuity_bridge_cli,
    proof_integrity_cli,
    project_quickstart_cli,
)
from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision_file,
)
from contractgraph_qa.ancestral_validity import load_ancestral_trace, run_ancestral_validity
from contractgraph_qa.contract_lattice import load_contract_lattice, run_contract_lattice
from contractgraph_qa.economic_cardinality import (
    load_economic_cardinality_model,
    run_economic_cardinality_model,
)
from contractgraph_qa.execution_trace import load_execution_trace, run_execution_trace
from contractgraph_qa.lifecycle_liveness import (
    load_lifecycle_liveness_model,
    run_lifecycle_liveness_model,
)
from contractgraph_qa.orientation_center import evaluate_orientation_center, load_orientation_center
from contractgraph_qa.payment_evidence_pack import (
    PaymentEvidencePackError,
    build_payment_evidence_pack,
    verify_payment_evidence_pack,
)
from contractgraph_qa.runtime_conformance_profile import (
    evaluate_runtime_conformance_profile,
    load_runtime_conformance_profile,
)
from contractgraph_qa.solidity_lattice import check_target, load_profile
from contractgraph_qa.successor_consistency import (
    load_successor_consistency_model,
    run_successor_consistency_model,
)
from contractgraph_qa.transition_geometry import (
    load_transition_geometry_model,
    run_transition_geometry_model,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_RUNTIME = legacy_cli.EXIT_RUNTIME
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL

PHASE2_COMMANDS = {"witness", "debt", "watch", "replicate", "remediate"}
PROOF_COMMANDS = {
    "subject-freeze": "freeze",
    "verification-plan": "plan",
    "trace-integrity": "trace",
    "evidence-readiness": "readiness",
    "root-cause": "root-cause",
    "metamorphic": "metamorphic",
    "durable-build": "durable-build",
    "durable-verify": "durable-verify",
}
ACTIVE_COMMANDS = {
    "plan-verification": "plan",
    "record-verification-cost": "record-cost",
}


def _emit(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _normalize_subcli_exit(code: int) -> int:
    if code in {EXIT_OK, 130}:
        return code
    if code == 2:
        return EXIT_VALIDATION
    return code


def _print_unified_help() -> None:
    print(legacy_cli._build_parser().format_help().rstrip())
    print(
        """

Universal onboarding:
  quickstart                 Detect a local smart-contract project and create a safe starter report

Smart-contract continuity:
  continuity-export         Export reviewed CGQA evidence to the normative LTP v0.1 input contract

Causal-temporal vNext:
  geometry                   Compare operation-order and loop path dependence
  ancestry                   Evaluate local versus inherited causal validity
  orient                     Aggregate causal-context readiness
  witness                    Verify independent event/object coverage
  debt                       Evaluate unresolved verification work
  watch                      Evaluate dormant causal watchpoints
  replicate                  Evaluate temporal/external replication and drift
  remediate                  Validate forward remediation without history rewrite
  subject-freeze             Re-check exact subject identity before/after evidence collection
  verification-plan          Verify a preregistered plan and append-only amendments
  trace-integrity            Detect duplicate, missing, reordered, or foreign trace evidence
  evidence-readiness         Classify evidence type and structural readiness
  root-cause                 Collapse downstream symptoms under graph-relative causal roots
  metamorphic                Verify round-trip/metamorphic preservation
  durable-build              Build a durable evidence manifest
  durable-verify             Re-open and verify durable evidence bytes
  plan-verification          Select verification work under capacity/budget without marking it verified
  record-verification-cost   Bind observed cost to exact work

Run `cgqa <command> --help` for command-specific arguments.
""".rstrip()
    )


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


def _contract_lattice_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa contract-lattice-check",
        description=(
            "Verify a Contract Lattice across state, version, value, authority, evidence, "
            "and explicit time-witness coordinates."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Contract Lattice v0.1 JSON",
    )
    args = parser.parse_args(argv)
    try:
        model = load_contract_lattice(args.model.resolve())
        result = run_contract_lattice(model)
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


def _solidity_lattice_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa solidity-lattice-check",
        description=(
            "Compile Solidity to compiler AST, extract a lifecycle graph, verify economic "
            "liveness, and emit a Contract Lattice template without inventing runtime facts."
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Foundry target in <source.sol>:<Contract> form",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Reviewed Solidity lattice profile JSON",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Optional Foundry project root",
    )
    args = parser.parse_args(argv)
    try:
        profile = load_profile(args.profile.resolve())
        root = None if args.root is None else args.root.resolve()
        result = check_target(args.target, profile, root)
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


def _execution_trace_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa execution-trace-check",
        description=(
            "Project one normalized execution evidence stream into independent "
            "economic-cardinality and successor-consistency checks."
        ),
    )
    parser.add_argument(
        "--trace",
        type=Path,
        required=True,
        help="Normalized execution trace v0.1 JSON",
    )
    args = parser.parse_args(argv)
    try:
        result = run_execution_trace(load_execution_trace(args.trace.resolve()))
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


def _runtime_conformance_profile_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa runtime-conformance-profile",
        description=(
            "Validate one portable Agent Runtime Conformance Profile v0.1 and "
            "emit separate profile-validity and projection-conformance claims."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Agent Runtime Conformance Profile v0.1 JSON",
    )
    args = parser.parse_args(argv)
    try:
        profile = load_runtime_conformance_profile(args.input.resolve())
        _emit(evaluate_runtime_conformance_profile(profile))
        return EXIT_OK
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


def _geometry_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa geometry",
        description="Compare operation order and closed-loop path dependence over observed endpoints.",
    )
    parser.add_argument("--model", type=Path, required=True, help="Transition Geometry v0.1 JSON")
    args = parser.parse_args(argv)
    try:
        result = run_transition_geometry_model(load_transition_geometry_model(args.model.resolve()))
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


def _ancestry_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa ancestry",
        description="Evaluate local versus effective validity across one normalized causal ancestry trace.",
    )
    parser.add_argument("--trace", type=Path, required=True, help="Ancestral Validity v0.1 JSON")
    args = parser.parse_args(argv)
    try:
        result = run_ancestral_validity(load_ancestral_trace(args.trace.resolve()))
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


def _orient_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa orient",
        description="Evaluate whether a declared causal context is BALANCED, INDETERMINATE, or UNSTABLE.",
    )
    parser.add_argument("--bundle", type=Path, required=True, help="Orientation Center v0.1 JSON")
    args = parser.parse_args(argv)
    try:
        result = evaluate_orientation_center(load_orientation_center(args.bundle.resolve()))
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


def main(argv: list[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    if not effective or effective[0] in {"-h", "--help"}:
        _print_unified_help()
        return EXIT_OK
    if effective[0] == "quickstart":
        return project_quickstart_cli.main(effective[1:])
    if effective[0] == "continuity-export":
        return ltp_continuity_bridge_cli.main(effective[1:])
    if effective[0] in PHASE2_COMMANDS:
        return _normalize_subcli_exit(causal_temporal_cli.main(effective))
    if effective[0] in PROOF_COMMANDS:
        mapped = [PROOF_COMMANDS[effective[0]], *effective[1:]]
        return _normalize_subcli_exit(proof_integrity_cli.main(mapped))
    if effective[0] in ACTIVE_COMMANDS:
        mapped = [ACTIVE_COMMANDS[effective[0]], *effective[1:]]
        return _normalize_subcli_exit(active_verification_cli.main(mapped))
    if effective[0] == "agent-payment-decision":
        return _decision_main(effective[1:])
    if effective[0] == "lifecycle-liveness":
        return _lifecycle_liveness_main(effective[1:])
    if effective[0] == "contract-lattice-check":
        return _contract_lattice_main(effective[1:])
    if effective[0] == "solidity-lattice-check":
        return _solidity_lattice_main(effective[1:])
    if effective[0] == "economic-cardinality":
        return _economic_cardinality_main(effective[1:])
    if effective[0] == "successor-consistency":
        return _successor_consistency_main(effective[1:])
    if effective[0] == "execution-trace-check":
        return _execution_trace_main(effective[1:])
    if effective[0] == "runtime-conformance-profile":
        return _runtime_conformance_profile_main(effective[1:])
    if effective[0] == "agent-payment-evidence-pack":
        return _evidence_pack_main(effective[1:])
    if effective[0] == "verify-agent-payment-evidence-pack":
        return _verify_evidence_pack_main(effective[1:])
    if effective[0] == "geometry":
        return _geometry_main(effective[1:])
    if effective[0] == "ancestry":
        return _ancestry_main(effective[1:])
    if effective[0] == "orient":
        return _orient_main(effective[1:])
    return legacy_cli.main(effective)


if __name__ == "__main__":
    raise SystemExit(main())
