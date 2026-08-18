"""Compatibility CLI dispatcher with agent-payment and ASTRA product commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision_file,
)
from contractgraph_qa.astra_transition import AstraTransitionError, analyze_transition_path
from contractgraph_qa.payment_evidence_pack import (
    PaymentEvidencePackError,
    build_payment_evidence_pack,
    verify_payment_evidence_pack,
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


def _astra_transition_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa astra-transition",
        description=(
            "Score a bounded transition path with ASTRA Transition Pressure, "
            "failure-gradient, and verifier-reflection semantics."
        ),
    )
    parser.add_argument("--input", type=Path, required=True, help="ASTRA transition JSON")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.resolve().read_text(encoding="utf-8"))
        _emit(analyze_transition_path(payload))
        return EXIT_OK
    except (AstraTransitionError, FileNotFoundError, json.JSONDecodeError) as exc:
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
    if effective and effective[0] == "agent-payment-evidence-pack":
        return _evidence_pack_main(effective[1:])
    if effective and effective[0] == "verify-agent-payment-evidence-pack":
        return _verify_evidence_pack_main(effective[1:])
    if effective and effective[0] == "astra-transition":
        return _astra_transition_main(effective[1:])
    return legacy_cli.main(effective)


if __name__ == "__main__":
    raise SystemExit(main())
