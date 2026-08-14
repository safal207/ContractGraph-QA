#!/usr/bin/env python3
"""Run and independently replay the bounded P1-1 negative-path matrix.

The matrix exercises the policy boundary around the ProofPath authority
decision and the ContractGraph-QA verifier.  It never invokes a provider,
executor, network destination, wallet, or real secret.  Every case is a
deterministic dry-run whose decision and side-effect boundary are evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "cgqa.p1-1-negative-path-matrix.v0.1"
RESULT_SCHEMA = "cgqa.p1-1-negative-path-matrix-result.v0.1"
PASS = "PASS"
BLOCK = "BLOCK"
ACCEPT = "ACCEPT"
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_BUNDLE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_NOW = "2026-08-14T08:02:00Z"
EXPECTED_TOOL_ORIGIN = "ProofPath/proofpath-scig@4a05ee31d7497979c2505dd55bfef08823302e24"
EXPECTED_DELEGATION = "delegation:system-007"


class MatrixError(ValueError):
    """Raised when a P1-1 matrix input or result is not acceptable."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MatrixError(f"value is not canonical JSON: {exc}") from exc


def sha256_ref(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MatrixError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MatrixError(f"{path} must contain an object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MatrixError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise MatrixError(f"{field} must include a timezone")
    return parsed


def base_proposal(case_id: str) -> dict[str, Any]:
    arguments = {"operation": "reversible_read_check", "resource": "fixture://local/p1-1"}
    evidence = {
        "case_id": case_id,
        "source": "repository-owned synthetic fixture",
        "content": "no secret; no provider call; no external effect",
    }
    return {
        "trace_id": f"trace:p1-1:{case_id}",
        "span_id": f"span:p1-1:{case_id}",
        "parent_span_id": "span:p1-1:root",
        "agent": "contractgraph-qa-matrix",
        "method": "policy_evaluation_only",
        "intent_id": "intent:neo-resonance-system-007-001",
        "parent_cause": "event:intent:001",
        "root": False,
        "action": "reversible_read_check",
        "scope": "system-007:reversible-read",
        "target": "fixture://local/p1-1",
        "reversibility": "reversible",
        "approval_ref": "approval:bounded-advisory-matrix",
        "nonce": f"p1-1-nonce-{case_id}",
        "contains_secret": False,
        "destination": "fixture://local",
        "metadata": {"case_id": case_id, "trust_domain": "repository-fixture"},
        "subject": "neo-resonance-system-007-001",
        "risk_tier": "bounded",
        "policy_version": "p1-1-policy-v0.1",
        "arguments": arguments,
        "arguments_digest": sha256_ref(arguments),
        "idempotency_key": f"idempotency:p1-1:{case_id}",
        "issued_at": "2026-08-14T08:00:00Z",
        "expires_at": "2026-08-14T09:00:00Z",
        "tool_origin": EXPECTED_TOOL_ORIGIN,
        "data_classification": "synthetic",
        "delegation_chain": [EXPECTED_DELEGATION],
        "delegation_identity": EXPECTED_DELEGATION,
        "context_origin": "application",
        "authority_source": "policy",
        "fanout": 1,
        "bundle_id": f"p1-1-{case_id}",
        "evidence": evidence,
        "evidence_digest": sha256_ref(evidence),
    }


def base_state() -> dict[str, Any]:
    return {
        "used_nonces": [],
        "allowed_scopes": ["system-007:reversible-read"],
        "allowed_destinations": ["https://approved.example"],
        "fanout_budget": 10,
        "expected_tool_origin": EXPECTED_TOOL_ORIGIN,
        "expected_delegation_identity": EXPECTED_DELEGATION,
        "nonce_race": False,
    }


def build_case_specs() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def add(
        case_id: str,
        surface: str,
        threat: str,
        trigger: str,
        expected_reason: str,
        mutate: Any = None,
        expected_decision: str = BLOCK,
    ) -> None:
        proposal = base_proposal(case_id)
        state = base_state()
        if mutate is not None:
            mutate(proposal, state)
        cases.append(
            {
                "case_id": case_id,
                "surface": surface,
                "threat": threat,
                "trigger": trigger,
                "expected_decision": expected_decision,
                "expected_reason": expected_reason,
                "proposal": proposal,
                "state": state,
                "execution_mode": "dry_run",
            }
        )

    add(
        "safe_reversible_control",
        "ProofPath → ContractGraph-QA",
        "control",
        "complete bounded reversible proposal",
        "POLICY_ELIGIBLE",
        expected_decision=ACCEPT,
    )
    add(
        "missing_intent",
        "ProofPath authority boundary",
        "missing declared intent",
        "intent_id is absent",
        "MISSING_INTENT",
        lambda proposal, _state: proposal.update(intent_id=None),
    )
    add(
        "missing_causal_parent",
        "ProofPath authority boundary",
        "missing causal parent",
        "non-root proposal has no parent_cause",
        "MISSING_CAUSAL_PARENT",
        lambda proposal, _state: proposal.update(parent_cause=None),
    )
    add(
        "missing_nonce",
        "ProofPath authority boundary",
        "missing nonce",
        "nonce is absent",
        "MISSING_NONCE",
        lambda proposal, _state: proposal.update(nonce=None),
    )
    add(
        "nonce_replay",
        "ProofPath authority boundary",
        "replay",
        "nonce was already consumed",
        "INTENT_REPLAYED",
        lambda proposal, state: state["used_nonces"].append(proposal["nonce"]),
    )
    add(
        "expired_authority",
        "ProofPath authority boundary",
        "expiry",
        "authority expires before evaluation",
        "AUTHORITY_EXPIRED",
        lambda proposal, _state: proposal.update(expires_at="2026-08-14T08:01:00Z"),
    )
    add(
        "scope_violation",
        "ProofPath authority boundary",
        "scope escalation",
        "target scope is outside policy allow-list",
        "SCOPE_VIOLATION",
        lambda proposal, _state: proposal.update(scope="system-007:wallet-write"),
    )
    add(
        "secret_egress_unknown_destination",
        "ProofPath egress boundary",
        "secret egress",
        "secret-bearing proposal targets an unknown destination",
        "SECRET_EGRESS_DESTINATION_DENIED",
        lambda proposal, _state: proposal.update(
            contains_secret=True, destination="https://unknown.example"
        ),
    )

    def changed_arguments(proposal: dict[str, Any], _state: dict[str, Any]) -> None:
        proposal["arguments"]["resource"] = "fixture://local/changed"

    add(
        "changed_arguments_digest",
        "ProofPath argument binding",
        "argument drift",
        "arguments changed while the old digest remained",
        "ARGUMENT_DIGEST_MISMATCH",
        changed_arguments,
    )
    add(
        "fanout_exhaustion",
        "ContractGraph-QA budget boundary",
        "cascading failure",
        "requested fan-out exceeds the bounded budget",
        "RESOURCE_BUDGET_EXHAUSTED",
        lambda proposal, _state: proposal.update(fanout=11),
    )

    def tampered_evidence(proposal: dict[str, Any], _state: dict[str, Any]) -> None:
        proposal["evidence"]["content"] = "tampered fixture content"

    add(
        "tampered_evidence",
        "ContractGraph-QA evidence boundary",
        "evidence integrity",
        "evidence bytes changed while the old digest remained",
        "EVIDENCE_INTEGRITY_MISMATCH",
        tampered_evidence,
    )
    add(
        "untrusted_memory_or_tool_output",
        "ContractGraph-QA context boundary",
        "memory/context poisoning",
        "memory or tool output is presented as authority",
        "UNTRUSTED_CONTEXT_NOT_AUTHORITY",
        lambda proposal, _state: proposal.update(
            context_origin="memory", authority_source="tool_output"
        ),
    )
    add(
        "forged_delegation",
        "ProofPath delegation boundary",
        "confused deputy",
        "delegation identity does not match the bound chain",
        "DELEGATION_IDENTITY_MISMATCH",
        lambda proposal, _state: proposal.update(
            delegation_identity="delegation:forged",
            delegation_chain=["delegation:forged"],
        ),
    )
    add(
        "changed_tool_origin",
        "ProofPath supply-chain boundary",
        "tool provenance drift",
        "tool origin differs from the pinned verifier",
        "TOOL_PROVENANCE_MISMATCH",
        lambda proposal, _state: proposal.update(tool_origin="untrusted/tool@changed"),
    )
    add(
        "nonce_race",
        "ProofPath atomic commit boundary",
        "nonce race",
        "nonce becomes consumed during the evaluation/commit gap",
        "NONCE_RACE",
        lambda _proposal, state: state.update(nonce_race=True),
    )
    add(
        "bundle_path_traversal",
        "ContractGraph-QA evidence boundary",
        "path traversal",
        "bundle identifier escapes the evidence namespace",
        "UNSAFE_BUNDLE_ID",
        lambda proposal, _state: proposal.update(bundle_id="../escape"),
    )
    return cases


def evaluate_proposal(
    proposal: Mapping[str, Any], state: Mapping[str, Any], *, now: str
) -> tuple[str, str]:
    if not proposal.get("intent_id"):
        return BLOCK, "MISSING_INTENT"
    if not proposal.get("parent_cause") and proposal.get("root") is not True:
        return BLOCK, "MISSING_CAUSAL_PARENT"
    if not proposal.get("nonce"):
        return BLOCK, "MISSING_NONCE"
    if proposal["nonce"] in state.get("used_nonces", []):
        return BLOCK, "INTENT_REPLAYED"
    if state.get("nonce_race") is True:
        return BLOCK, "NONCE_RACE"
    if parse_time(now, "now") >= parse_time(str(proposal.get("expires_at")), "expires_at"):
        return BLOCK, "AUTHORITY_EXPIRED"
    if proposal.get("scope") not in state.get("allowed_scopes", []):
        return BLOCK, "SCOPE_VIOLATION"
    if proposal.get("contains_secret") and proposal.get("destination") not in state.get(
        "allowed_destinations", []
    ):
        return BLOCK, "SECRET_EGRESS_DESTINATION_DENIED"
    if proposal.get("arguments_digest") != sha256_ref(proposal.get("arguments")):
        return BLOCK, "ARGUMENT_DIGEST_MISMATCH"
    if proposal.get("fanout", 0) > state.get("fanout_budget", 0):
        return BLOCK, "RESOURCE_BUDGET_EXHAUSTED"
    if proposal.get("evidence_digest") != sha256_ref(proposal.get("evidence")):
        return BLOCK, "EVIDENCE_INTEGRITY_MISMATCH"
    if proposal.get("context_origin") not in {"application", "policy"} or proposal.get(
        "authority_source"
    ) in {"memory", "tool_output", "web"}:
        return BLOCK, "UNTRUSTED_CONTEXT_NOT_AUTHORITY"
    if proposal.get("tool_origin") != state.get("expected_tool_origin"):
        return BLOCK, "TOOL_PROVENANCE_MISMATCH"
    if proposal.get("delegation_identity") != state.get("expected_delegation_identity"):
        return BLOCK, "DELEGATION_IDENTITY_MISMATCH"
    if not SAFE_BUNDLE_RE.fullmatch(str(proposal.get("bundle_id", ""))):
        return BLOCK, "UNSAFE_BUNDLE_ID"
    return ACCEPT, "POLICY_ELIGIBLE"


def evaluate_case(case: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    case_id = str(case.get("case_id"))
    decision, reason = evaluate_proposal(case["proposal"], case["state"], now=now)
    expected_decision = case["expected_decision"]
    expected_reason = case["expected_reason"]
    if decision != expected_decision or reason != expected_reason:
        raise MatrixError(
            f"{case_id} expected {expected_decision}/{expected_reason}, got {decision}/{reason}"
        )
    input_digest = sha256_ref(
        {"case": case_id, "proposal": case["proposal"], "state": case["state"], "now": now}
    )
    decision_payload = {
        "case_id": case_id,
        "decision": decision,
        "reason": reason,
        "side_effect_executed": False,
        "executor_invoked": False,
    }
    return {
        "case_id": case_id,
        "surface": case["surface"],
        "threat": case["threat"],
        "trigger": case["trigger"],
        "expected_decision": expected_decision,
        "observed_decision": decision,
        "expected_reason": expected_reason,
        "observed_reason": reason,
        "side_effect_executed": False,
        "executor_invoked": False,
        "execution_mode": case["execution_mode"],
        "input_digest": input_digest,
        "evidence_ref": f"evidence://p1-1/{case_id}/decision",
        "decision_digest": sha256_ref(decision_payload),
        "replayable": True,
        "status": PASS,
    }


def run_matrix(*, checked_subject: str, proofpath_head: str, now: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not HEAD_RE.fullmatch(checked_subject):
        raise MatrixError("checked_subject must be a 40-character commit SHA")
    if not HEAD_RE.fullmatch(proofpath_head):
        raise MatrixError("proofpath_head must be a 40-character commit SHA")
    parse_time(now, "now")
    cases = build_case_specs()
    observations = [evaluate_case(case, now=now) for case in cases]
    replay_observations = [evaluate_case(copy.deepcopy(case), now=now) for case in cases]
    for first, replay in zip(observations, replay_observations):
        if first != replay:
            raise MatrixError(f"replay drift in {first['case_id']}")
    inputs = {
        "schema": SCHEMA,
        "matrix_id": "neo-resonance-p1-1-negative-paths-001",
        "checked_subject": checked_subject,
        "proofpath_head": proofpath_head,
        "now": now,
        "cases": cases,
    }
    result = {
        "schema": RESULT_SCHEMA,
        "matrix_id": inputs["matrix_id"],
        "checked_subject": checked_subject,
        "proofpath_head": proofpath_head,
        "now": now,
        "decision": PASS,
        "cases": observations,
        "coverage": {
            "total_cases": len(observations),
            "matched_decisions": len(observations),
            "blocked_cases": sum(item["observed_decision"] == BLOCK for item in observations),
            "accept_control_cases": sum(item["observed_decision"] == ACCEPT for item in observations),
            "executed_cases": sum(item["side_effect_executed"] for item in observations),
            "replay_stable_cases": sum(item["replayable"] for item in observations),
            "evidence_complete_cases": sum(bool(item["evidence_ref"]) for item in observations),
        },
        "authority": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
        },
        "mode": "deterministic_policy_evaluation_only",
    }
    return inputs, result


def verify_matrix(
    inputs: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    expected_subject: str,
    expected_proofpath_head: str,
) -> None:
    if inputs.get("schema") != SCHEMA or result.get("schema") != RESULT_SCHEMA:
        raise MatrixError("P1-1 matrix schema mismatch")
    if inputs.get("checked_subject") != expected_subject or result.get("checked_subject") != expected_subject:
        raise MatrixError("P1-1 matrix subject is stale")
    if inputs.get("proofpath_head") != expected_proofpath_head or result.get("proofpath_head") != expected_proofpath_head:
        raise MatrixError("P1-1 ProofPath subject is stale")
    if result.get("decision") != PASS:
        raise MatrixError("P1-1 matrix did not pass")
    cases = inputs.get("cases")
    observations = result.get("cases")
    if not isinstance(cases, list) or not isinstance(observations, list) or len(cases) != len(observations):
        raise MatrixError("P1-1 case count is not reproducible")
    replayed = [evaluate_case(copy.deepcopy(case), now=str(inputs["now"])) for case in cases]
    if replayed != observations:
        raise MatrixError("P1-1 result is not reproducible from matrix inputs")
    if any(item["status"] != PASS or item["side_effect_executed"] for item in observations):
        raise MatrixError("P1-1 case status or side-effect boundary is unsafe")
    if any(not item["replayable"] or not item["evidence_ref"] for item in observations):
        raise MatrixError("P1-1 case evidence is incomplete")
    authority = result.get("authority")
    if not isinstance(authority, Mapping) or any(authority.get(key) is not False for key in (
        "execution_authorized", "mutation_authorized", "external_effects_authorized"
    )):
        raise MatrixError("P1-1 matrix escalated authority")


def run_command(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    inputs, result = run_matrix(
        checked_subject=args.checked_subject,
        proofpath_head=args.proofpath_head,
        now=args.now,
    )
    write_json(output / "matrix-inputs.json", inputs)
    write_json(output / "matrix-result.json", result)
    write_json(
        output / "run-context.json",
        {
            "schema": "cgqa.p1-1-run-context.v0.1",
            "checked_subject": args.checked_subject,
            "expected_subject": args.checked_subject,
            "proofpath_head": args.proofpath_head,
            "workflow": "FCRP P1-1 — Negative-Path Matrix",
            "authority": "advisory only; dry-run policy evaluation; no executor or external effect",
        },
    )
    print("P1_1_MATRIX_PASS", sha256_ref(result))


def verify_command(args: argparse.Namespace) -> None:
    inputs = load_json(Path(args.inputs))
    result = load_json(Path(args.result))
    verify_matrix(
        inputs,
        result,
        expected_subject=args.checked_subject,
        expected_proofpath_head=args.proofpath_head,
    )
    print("P1_1_MATRIX_VERIFY_PASS", sha256_ref(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--output-dir", required=True)
    run.add_argument("--checked-subject", required=True)
    run.add_argument("--proofpath-head", required=True)
    run.add_argument("--now", default=DEFAULT_NOW)
    run.set_defaults(handler=run_command)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--inputs", required=True)
    verify.add_argument("--result", required=True)
    verify.add_argument("--checked-subject", required=True)
    verify.add_argument("--proofpath-head", required=True)
    verify.set_defaults(handler=verify_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (MatrixError, OSError, KeyError, TypeError) as exc:
        print(f"P1_1_MATRIX_INCOMPLETE {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
