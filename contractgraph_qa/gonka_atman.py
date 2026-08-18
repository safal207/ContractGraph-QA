"""Experimental ATMAN helpers for the Gonka verification profile.

This module does not alter the existing Gonka PASS/FAIL semantics. It classifies
verifier-side uncertainty and selects the next evidence check that most cleanly
discriminates between competing hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class GonkaAtmanError(ValueError):
    """Raised when GONKA-ATMAN input is malformed."""


_ALLOWED_HYPOTHESES = {
    "IDENTITY_PROPAGATION_FAILURE",
    "ACCOUNTING_LOOKUP_FAILURE",
    "PROTOCOL_TIME_DELAY",
    "STALE_RUNTIME_GENERATION",
    "DUPLICATE_EXECUTION",
    "SETTLEMENT_RECONCILIATION_FAILURE",
}


@dataclass(frozen=True)
class EvidenceCheck:
    check_id: str
    description: str
    discriminates: frozenset[str]
    information_gain: float


_CHECKS = (
    EvidenceCheck(
        "COMPARE_RUNTIME_FINGERPRINT",
        "Compare executed runtime/image fingerprint with the source/evidence generation.",
        frozenset({"STALE_RUNTIME_GENERATION"}),
        0.98,
    ),
    EvidenceCheck(
        "TRACE_REQUEST_IDENTITY",
        "Trace logical operation -> transport request IDs -> detached execution context.",
        frozenset({"IDENTITY_PROPAGATION_FAILURE", "ACCOUNTING_LOOKUP_FAILURE"}),
        0.86,
    ),
    EvidenceCheck(
        "WAIT_NEXT_PROTOCOL_DIFF",
        "Advance to the next eligible protocol diff and re-read terminal/accounting state.",
        frozenset({"PROTOCOL_TIME_DELAY", "SETTLEMENT_RECONCILIATION_FAILURE"}),
        0.91,
    ),
    EvidenceCheck(
        "RECONCILE_EXECUTION_NONCES",
        "Bind every execution nonce to one logical operation, winner, cost, and accounting mutation.",
        frozenset({"DUPLICATE_EXECUTION", "ACCOUNTING_LOOKUP_FAILURE"}),
        0.94,
    ),
    EvidenceCheck(
        "RECONCILE_SETTLEMENT_REFS",
        "Compare accounting mutations and settlement references for unexplained or duplicated effects.",
        frozenset({"SETTLEMENT_RECONCILIATION_FAILURE", "DUPLICATE_EXECUTION"}),
        0.93,
    ),
)


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GonkaAtmanError(f"{name} must be a non-empty string")
    return value.strip()


def _generation_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    source = _text("source_revision", payload.get("source_revision"))
    runtime = _text("runtime_generation", payload.get("runtime_generation"))
    evidence = _text("evidence_generation", payload.get("evidence_generation"))

    expected_runtime = payload.get("expected_runtime_generation")
    if expected_runtime is not None:
        expected_runtime = _text("expected_runtime_generation", expected_runtime)

    if expected_runtime is not None and runtime != expected_runtime:
        verdict = "VERIFIER_GENERATION_MISMATCH"
    elif runtime != evidence:
        verdict = "VERIFIER_GENERATION_MISMATCH"
    else:
        verdict = "PASS"

    return {
        "source_revision": source,
        "runtime_generation": runtime,
        "evidence_generation": evidence,
        "expected_runtime_generation": expected_runtime,
        "verdict": verdict,
    }


def select_next_best_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Select the next evidence check for an inconclusive Gonka candidate.

    The selector is deliberately bounded and transparent. It does not infer a
    target defect. Generation mismatch takes precedence because a stale runtime
    invalidates downstream causal interpretation.
    """

    if not isinstance(payload, dict):
        raise GonkaAtmanError("input must be an object")

    case_id = _text("case_id", payload.get("case_id"))
    logical_operation_id = _text("logical_operation_id", payload.get("logical_operation_id"))
    generation = _generation_verdict(payload)

    raw_hypotheses = payload.get("hypotheses")
    if not isinstance(raw_hypotheses, list) or not raw_hypotheses:
        raise GonkaAtmanError("hypotheses must be a non-empty array")

    hypotheses: list[str] = []
    for index, raw in enumerate(raw_hypotheses):
        item = _text(f"hypotheses[{index}]", raw)
        if item not in _ALLOWED_HYPOTHESES:
            raise GonkaAtmanError(f"unsupported hypothesis: {item}")
        if item not in hypotheses:
            hypotheses.append(item)

    observed = payload.get("observed_evidence", [])
    if not isinstance(observed, list):
        raise GonkaAtmanError("observed_evidence must be an array")
    observed_ids = {_text(f"observed_evidence[{i}]", item) for i, item in enumerate(observed)}

    if generation["verdict"] != "PASS":
        selected = next(check for check in _CHECKS if check.check_id == "COMPARE_RUNTIME_FINGERPRINT")
        reason = "generation coherence must be restored before target-side interpretation"
    else:
        candidates: list[tuple[float, int, str, EvidenceCheck]] = []
        hypothesis_set = set(hypotheses)
        for check in _CHECKS:
            if check.check_id in observed_ids:
                continue
            coverage = len(hypothesis_set & set(check.discriminates))
            if coverage == 0:
                continue
            score = check.information_gain * (coverage / len(hypothesis_set))
            candidates.append((score, coverage, check.check_id, check))

        if not candidates:
            return {
                "schema_version": "gonka-atman-next-evidence-v0.1",
                "case_id": case_id,
                "logical_operation_id": logical_operation_id,
                "generation": generation,
                "hypotheses": hypotheses,
                "action": "HOLD",
                "next_best_evidence": None,
                "reason": "no remaining bounded evidence check discriminates the current hypotheses",
                "target_claim_allowed": False,
            }

        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
        selected = candidates[0][3]
        reason = "highest bounded information gain across the current competing hypotheses"

    return {
        "schema_version": "gonka-atman-next-evidence-v0.1",
        "case_id": case_id,
        "logical_operation_id": logical_operation_id,
        "generation": generation,
        "hypotheses": hypotheses,
        "action": "COLLECT_MORE_EVIDENCE",
        "next_best_evidence": {
            "check_id": selected.check_id,
            "description": selected.description,
            "discriminates": sorted(set(hypotheses) & set(selected.discriminates)),
            "information_gain": selected.information_gain,
        },
        "reason": reason,
        "target_claim_allowed": False,
    }
