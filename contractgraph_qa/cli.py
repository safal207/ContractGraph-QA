"""Compatibility CLI dispatcher with agent-payment and ASTRA product commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.agent_payment_decision import AgentPaymentDecisionError, evaluate_agent_payment_decision_file
from contractgraph_qa.astra_causal_locality import AstraCausalLocalityError, analyze_causal_locality
from contractgraph_qa.astra_evidence import AstraEvidenceError, build_astra_evidence_pack, verify_astra_evidence_pack
from contractgraph_qa.astra_queue import AstraQueueError, compare_queue_ordering
from contractgraph_qa.astra_state_planes import AstraStatePlaneError, analyze_state_planes
from contractgraph_qa.astra_transition import AstraTransitionError, analyze_transition_path
from contractgraph_qa.payment_evidence_pack import PaymentEvidencePackError, build_payment_evidence_pack, verify_payment_evidence_pack
from contractgraph_qa import legacy_cli

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_RUNTIME = legacy_cli.EXIT_RUNTIME
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _emit(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _json_input(command: str, description: str, argv: list[str], analyzer, error_type) -> int:
    parser = argparse.ArgumentParser(prog=command, description=description)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.resolve().read_text(encoding="utf-8"))
        _emit(analyzer(payload))
        return EXIT_OK
    except (error_type, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except Exception as exc:  # pragma: no cover
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _decision_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cgqa agent-payment-decision")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _emit(evaluate_agent_payment_decision_file(args.input.resolve()))
        return EXIT_OK
    except (AgentPaymentDecisionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION


def _evidence_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cgqa agent-payment-evidence-pack")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _emit(build_payment_evidence_pack(args.input.resolve(), args.output.resolve()))
        return EXIT_OK
    except (PaymentEvidencePackError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION


def _verify_evidence_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cgqa verify-agent-payment-evidence-pack")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        _emit(verify_payment_evidence_pack(args.bundle.resolve()))
        return EXIT_OK
    except (PaymentEvidencePackError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION


def _astra_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cgqa astra-evidence-pack")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _emit(build_astra_evidence_pack(args.input.resolve(), args.output.resolve()))
        return EXIT_OK
    except (AstraEvidenceError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION


def _verify_astra_pack_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cgqa verify-astra-evidence-pack")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        _emit(verify_astra_evidence_pack(args.bundle.resolve()))
        return EXIT_OK
    except (AstraEvidenceError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION


def main(argv: list[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    if effective and effective[0] == "agent-payment-decision": return _decision_main(effective[1:])
    if effective and effective[0] == "agent-payment-evidence-pack": return _evidence_pack_main(effective[1:])
    if effective and effective[0] == "verify-agent-payment-evidence-pack": return _verify_evidence_pack_main(effective[1:])
    if effective and effective[0] == "astra-transition": return _json_input("cgqa astra-transition", "ASTRA transition pressure", effective[1:], analyze_transition_path, AstraTransitionError)
    if effective and effective[0] == "astra-state-planes": return _json_input("cgqa astra-state-planes", "ASTRA state planes", effective[1:], analyze_state_planes, AstraStatePlaneError)
    if effective and effective[0] == "astra-causal-locality": return _json_input("cgqa astra-causal-locality", "ASTRA causal locality", effective[1:], analyze_causal_locality, AstraCausalLocalityError)
    if effective and effective[0] == "astra-queue": return _json_input("cgqa astra-queue", "ASTRA queue comparison", effective[1:], compare_queue_ordering, AstraQueueError)
    if effective and effective[0] == "astra-evidence-pack": return _astra_pack_main(effective[1:])
    if effective and effective[0] == "verify-astra-evidence-pack": return _verify_astra_pack_main(effective[1:])
    return legacy_cli.main(effective)


if __name__ == "__main__":
    raise SystemExit(main())
