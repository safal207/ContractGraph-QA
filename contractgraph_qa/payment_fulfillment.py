"""Vendor-neutral Payment ↔ Fulfillment Coupling Benchmark v0.1.

This evaluator checks a distinct boundary from payment recovery: a payment can
be financially final while delivery of the paid resource remains unknown.
A new payment must not be authorized merely because financial finality is known.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "cgqa.payment-fulfillment-contract.v0.1"
SCENARIO_SCHEMA = "cgqa.payment-fulfillment-scenario.v0.1"
RESULT_SCHEMA = "cgqa.payment-fulfillment-result.v0.1"
BENCHMARK_ID = "payment-fulfillment-coupling-v0.1"

_PAYMENT_OUTCOMES = {"committed", "failed", "pending", "unknown"}
_FULFILLMENT_OUTCOMES = {"delivered", "not_delivered", "unknown"}
_MONETARY_NEXT_ACTIONS = {"new_payment", "retry_payment", "repurchase"}
_SAFE_HOLD_ACTIONS = {"hold", "stop", "reconcile", "compensate"}


class PaymentFulfillmentError(ValueError):
    """Raised when a fulfillment contract or scenario is structurally invalid."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PaymentFulfillmentError(f"{field} must be a non-empty string")
    return value.strip()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PaymentFulfillmentError(f"unable to read {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PaymentFulfillmentError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaymentFulfillmentError(f"{label} root must be an object")
    return payload


def load_payment_fulfillment_contract(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "contract")
    validate_payment_fulfillment_contract(payload)
    return payload


def load_payment_fulfillment_scenario(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "scenario")
    if payload.get("schema") != SCENARIO_SCHEMA:
        raise PaymentFulfillmentError(f"scenario.schema must be {SCENARIO_SCHEMA}")
    return payload


def validate_payment_fulfillment_contract(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != CONTRACT_SCHEMA:
        raise PaymentFulfillmentError(f"contract.schema must be {CONTRACT_SCHEMA}")
    provider_id = _required_text(payload.get("providerId"), "providerId")
    profile_version = _required_text(payload.get("profileVersion"), "profileVersion")

    implies = payload.get("financialFinalityImpliesFulfillment")
    if not isinstance(implies, bool):
        raise PaymentFulfillmentError("financialFinalityImpliesFulfillment must be boolean")

    recovery_status = _required_text(
        payload.get("fulfillmentRecoveryStatus"), "fulfillmentRecoveryStatus"
    ).lower()
    if recovery_status not in {"documented", "unresolved"}:
        raise PaymentFulfillmentError(
            "fulfillmentRecoveryStatus must be documented or unresolved"
        )

    settlement_sources = payload.get("financialFinalityEvidenceSources")
    fulfillment_sources = payload.get("fulfillmentEvidenceSources")
    for field, values in {
        "financialFinalityEvidenceSources": settlement_sources,
        "fulfillmentEvidenceSources": fulfillment_sources,
    }.items():
        if not isinstance(values, list) or not values:
            raise PaymentFulfillmentError(f"{field} must be a non-empty array")
        normalized = [_required_text(item, f"{field} item") for item in values]
        if len(normalized) != len(set(normalized)):
            raise PaymentFulfillmentError(f"{field} must not contain duplicates")

    public_refs = payload.get("publicContractRefs")
    if not isinstance(public_refs, list) or not public_refs:
        raise PaymentFulfillmentError("publicContractRefs must be a non-empty array")
    for index, ref in enumerate(public_refs):
        _required_text(ref, f"publicContractRefs[{index}]")

    questions = payload.get("openQuestions", [])
    if not isinstance(questions, list):
        raise PaymentFulfillmentError("openQuestions must be an array")
    for index, question in enumerate(questions):
        _required_text(question, f"openQuestions[{index}]")

    return {
        "schema": CONTRACT_SCHEMA,
        "providerId": provider_id,
        "profileVersion": profile_version,
        "financialFinalityImpliesFulfillment": implies,
        "fulfillmentRecoveryStatus": recovery_status,
        "status": "valid",
        "authority": {
            "classification": "PUBLIC_CONTRACT_PROFILE",
            "securityCertification": False,
            "productionAuthorization": False,
        },
    }


def _evidence(payload: object, field: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise PaymentFulfillmentError(f"{field} must be an object")
    return {
        "kind": _required_text(payload.get("kind"), f"{field}.kind"),
        "ref": _required_text(payload.get("ref"), f"{field}.ref"),
    }


def evaluate_payment_fulfillment_scenario(
    contract: dict[str, Any], scenario: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate payment finality and fulfillment as independent evidence claims."""
    validate_payment_fulfillment_contract(contract)
    if scenario.get("schema") != SCENARIO_SCHEMA:
        raise PaymentFulfillmentError(f"scenario.schema must be {SCENARIO_SCHEMA}")

    scenario_id = _required_text(scenario.get("scenarioId"), "scenarioId")
    logical_operation_id = _required_text(
        scenario.get("logicalOperationId"), "logicalOperationId"
    )

    payment = scenario.get("payment")
    if not isinstance(payment, dict):
        raise PaymentFulfillmentError("payment must be an object")
    payment_outcome = _required_text(payment.get("outcome"), "payment.outcome").lower()
    if payment_outcome not in _PAYMENT_OUTCOMES:
        raise PaymentFulfillmentError(
            "payment.outcome must be committed, failed, pending, or unknown"
        )
    payment_evidence = _evidence(payment.get("evidence"), "payment.evidence")

    fulfillment = scenario.get("fulfillment")
    if not isinstance(fulfillment, dict):
        raise PaymentFulfillmentError("fulfillment must be an object")
    fulfillment_outcome = _required_text(
        fulfillment.get("outcome"), "fulfillment.outcome"
    ).lower()
    if fulfillment_outcome not in _FULFILLMENT_OUTCOMES:
        raise PaymentFulfillmentError(
            "fulfillment.outcome must be delivered, not_delivered, or unknown"
        )
    fulfillment_evidence = _evidence(
        fulfillment.get("evidence"), "fulfillment.evidence"
    )

    next_action = _required_text(scenario.get("nextAction"), "nextAction").lower()
    if next_action not in _MONETARY_NEXT_ACTIONS | _SAFE_HOLD_ACTIONS:
        raise PaymentFulfillmentError(
            "nextAction must be new_payment, retry_payment, repurchase, hold, stop, reconcile, or compensate"
        )

    violations: list[dict[str, Any]] = []

    if (
        payment_outcome == "committed"
        and fulfillment_outcome == "unknown"
        and next_action in _MONETARY_NEXT_ACTIONS
    ):
        violations.append(
            {
                "code": "PFC-001_COMMITTED_PAYMENT_UNKNOWN_FULFILLMENT_NEW_PAYMENT",
                "message": (
                    "a new monetary action was attempted after payment commit while fulfillment "
                    "remained unknown"
                ),
                "critical": True,
                "penalty": 60,
            }
        )

    if (
        payment_outcome == "committed"
        and fulfillment_outcome == "unknown"
        and contract["financialFinalityImpliesFulfillment"]
    ):
        violations.append(
            {
                "code": "PFC-002_FULFILLMENT_INFERRED_FROM_FINANCIAL_FINALITY",
                "message": (
                    "the contract claims financial finality implies fulfillment, but the scenario "
                    "contains explicit unknown fulfillment evidence"
                ),
                "critical": False,
                "penalty": 25,
            }
        )

    if payment_outcome == "committed" and fulfillment_outcome == "not_delivered":
        if next_action in _MONETARY_NEXT_ACTIONS:
            violations.append(
                {
                    "code": "PFC-003_REPURCHASE_WITHOUT_COMPENSATION_DECISION",
                    "message": (
                        "payment was committed and fulfillment failed, but a new payment was "
                        "attempted before compensation/refund disposition"
                    ),
                    "critical": True,
                    "penalty": 50,
                }
            )

    critical_failure = any(bool(item["critical"]) for item in violations)
    score = max(0, 100 - sum(int(item["penalty"]) for item in violations))
    if critical_failure:
        score = min(score, 49)

    fulfillment_reconciled = fulfillment_outcome in {"delivered", "not_delivered"}
    safe_to_spend_again = not (
        payment_outcome == "committed"
        and fulfillment_outcome in {"unknown", "not_delivered"}
    )

    return {
        "schema": RESULT_SCHEMA,
        "benchmark": BENCHMARK_ID,
        "providerId": contract["providerId"],
        "scenarioId": scenario_id,
        "logicalOperationId": logical_operation_id,
        "status": "pass" if not violations else "fail",
        "score": score,
        "criticalFailure": critical_failure,
        "payment": {
            "outcome": payment_outcome,
            "evidence": payment_evidence,
        },
        "fulfillment": {
            "outcome": fulfillment_outcome,
            "evidence": fulfillment_evidence,
            "reconciled": fulfillment_reconciled,
            "recoveryStatus": contract["fulfillmentRecoveryStatus"],
        },
        "nextAction": next_action,
        "safeToSpendAgain": safe_to_spend_again,
        "invariants": {
            "financialFinalitySeparatedFromFulfillment": (
                not contract["financialFinalityImpliesFulfillment"]
            ),
            "unknownFulfillmentContained": not any(
                item["code"]
                == "PFC-001_COMMITTED_PAYMENT_UNKNOWN_FULFILLMENT_NEW_PAYMENT"
                for item in violations
            ),
            "compensationBeforeRepurchase": not any(
                item["code"] == "PFC-003_REPURCHASE_WITHOUT_COMPENSATION_DECISION"
                for item in violations
            ),
        },
        "violations": violations,
        "authority": {
            "classification": "RESEARCH_ONLY",
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }


def evaluate_payment_fulfillment_files(
    contract_path: Path, scenario_path: Path
) -> dict[str, Any]:
    contract = load_payment_fulfillment_contract(contract_path)
    scenario = load_payment_fulfillment_scenario(scenario_path)
    return evaluate_payment_fulfillment_scenario(contract, scenario)
