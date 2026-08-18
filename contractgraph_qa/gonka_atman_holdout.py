"""Prospective held-out benchmark harness for GONKA-ATMAN.

This module deliberately does not manufacture a held-out result from already-known
Gonka findings. A benchmark case is registered before its hidden target cause is
revealed, with a frozen policy id and fixed baseline check order. After evidence
collection, the oracle may be revealed and the two strategies compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .gonka_atman import GonkaAtmanError, select_next_best_evidence


BASELINE_ORDER = (
    "TRACE_REQUEST_IDENTITY",
    "WAIT_NEXT_PROTOCOL_DIFF",
    "RECONCILE_EXECUTION_NONCES",
    "RECONCILE_SETTLEMENT_REFS",
    "COMPARE_RUNTIME_FINGERPRINT",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seal_holdout_case(case: dict[str, Any]) -> dict[str, Any]:
    """Seal public benchmark inputs before the hidden oracle is revealed."""
    required = [
        "case_id",
        "logical_operation_id",
        "source_revision",
        "runtime_generation",
        "evidence_generation",
        "hypotheses",
        "policy_id",
    ]
    for field in required:
        if field not in case:
            raise GonkaAtmanError(f"missing field: {field}")
    if "target_cause" in case or "oracle" in case:
        raise GonkaAtmanError("sealed case must not contain target/oracle data")

    public = dict(case)
    public.setdefault("observed_evidence", [])
    commitment = sha256(_canonical(public)).hexdigest()
    return {
        "schema_version": "gonka-atman-holdout-seal-v0.1",
        "case": public,
        "case_commitment_sha256": commitment,
        "baseline_order": list(BASELINE_ORDER),
        "target_revealed": False,
    }


def _first_matching_baseline_index(target_check: str) -> int:
    try:
        return BASELINE_ORDER.index(target_check) + 1
    except ValueError as exc:
        raise GonkaAtmanError(f"oracle target check not in frozen baseline order: {target_check}") from exc


def evaluate_revealed_holdout(sealed: dict[str, Any], oracle: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one prospectively sealed case after oracle reveal.

    The oracle names the minimum evidence check that actually resolves the hidden
    cause. This benchmark measures evidence-check selection cost only; it is not a
    vulnerability or security-severity benchmark.
    """
    if sealed.get("schema_version") != "gonka-atman-holdout-seal-v0.1":
        raise GonkaAtmanError("unsupported sealed benchmark schema")
    case = sealed.get("case")
    if not isinstance(case, dict):
        raise GonkaAtmanError("sealed case missing case object")
    if sha256(_canonical(case)).hexdigest() != sealed.get("case_commitment_sha256"):
        raise GonkaAtmanError("sealed case commitment mismatch")

    target_check = oracle.get("resolving_check_id")
    target_cause = oracle.get("target_cause")
    if not isinstance(target_check, str) or not target_check:
        raise GonkaAtmanError("oracle resolving_check_id required")
    if not isinstance(target_cause, str) or not target_cause:
        raise GonkaAtmanError("oracle target_cause required")

    # ATMAN is evaluated from exactly the pre-reveal case state.
    decision = select_next_best_evidence(case)
    selected = decision.get("next_best_evidence")
    atman_first = selected.get("check_id") if isinstance(selected, dict) else None

    baseline_checks = _first_matching_baseline_index(target_check)
    atman_checks = 1 if atman_first == target_check else None

    if atman_checks is None:
        verdict = "NOT_RESOLVED_ON_FIRST_ATMAN_CHECK"
        savings = None
    else:
        savings = baseline_checks - atman_checks
        verdict = "ATMAN_EARLIER" if savings > 0 else "SAME_COST"

    return {
        "schema_version": "gonka-atman-holdout-result-v0.1",
        "case_id": case.get("case_id"),
        "policy_id": case.get("policy_id"),
        "case_commitment_sha256": sealed.get("case_commitment_sha256"),
        "oracle": {
            "target_cause": target_cause,
            "resolving_check_id": target_check,
        },
        "atman_first_check": atman_first,
        "baseline_checks_to_resolution": baseline_checks,
        "atman_checks_to_resolution": atman_checks,
        "evidence_checks_saved": savings,
        "verdict": verdict,
        "limitations": [
            "prospective benchmark only",
            "measures first-check evidence selection cost",
            "does not establish vulnerability severity or causal truth",
        ],
    }
