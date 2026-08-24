"""Deterministic verification-work planning under finite capacity and budget."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_bool,
    require_int,
    require_list,
    require_object,
    require_subject,
    require_text,
)

SCHEMA = "cgqa/active-verification/v0.1"


class ActiveVerificationError(CausalTemporalError):
    """Raised when active-verification campaign input is malformed."""


def _number(value: object, name: str, *, minimum: float = 0.0) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ActiveVerificationError(f"{name} must be numeric")
    number = float(value)
    if number < minimum:
        raise ActiveVerificationError(f"{name} must be >= {minimum}")
    return number


def _cost(value: object, name: str) -> dict[str, Any]:
    cost = require_object(value, name)
    _number(cost.get("estimated"), f"{name}.estimated")
    if "declared" in cost and cost["declared"] is not None:
        _number(cost["declared"], f"{name}.declared")
    if "observed" in cost and cost["observed"] is not None:
        _number(cost["observed"], f"{name}.observed")
        require_text(cost.get("observedReceiptHash"), f"{name}.observedReceiptHash")
    return cost


def validate_active_verification(data: object) -> dict[str, Any]:
    campaign = require_object(data, "campaign")
    if campaign.get("schema") != SCHEMA:
        raise ActiveVerificationError(f"schema must equal {SCHEMA!r}")
    _, subject_hash = require_subject(campaign)
    policy = require_object(campaign.get("policy"), "policy")
    capacity = require_int(policy.get("capacityUnits"), "policy.capacityUnits")
    if capacity < 0:
        raise ActiveVerificationError("policy.capacityUnits must be >= 0")
    _number(policy.get("budget"), "policy.budget")
    require_bool(policy.get("requireInformationGain", False), "policy.requireInformationGain")
    weights = require_object(policy.get("weights"), "policy.weights")
    for key in ("risk", "priority", "age", "informationGain", "cost"):
        _number(weights.get(key), f"policy.weights.{key}")
    if float(weights["age"]) <= 0:
        raise ActiveVerificationError("policy.weights.age must be > 0 for anti-starvation")

    completed_ids = set()
    for index, raw in enumerate(require_list(campaign.get("completedWorkIds", []), "completedWorkIds")):
        completed_ids.add(require_text(raw, f"completedWorkIds[{index}]"))

    work = require_list(campaign.get("work"), "work")
    seen: set[str] = set()
    for index, raw in enumerate(work):
        item = require_object(raw, f"work[{index}]")
        work_id = require_text(item.get("id"), f"work[{index}].id")
        if work_id in seen:
            raise ActiveVerificationError(f"duplicate work id: {work_id}")
        seen.add(work_id)
        if item.get("subjectHash") != subject_hash:
            raise ActiveVerificationError(f"work[{index}].subjectHash does not match exact subject")
        require_text(item.get("capability"), f"work[{index}].capability")
        require_bool(item.get("required", True), f"work[{index}].required")
        _number(item.get("riskWeight"), f"work[{index}].riskWeight")
        _number(item.get("priority"), f"work[{index}].priority")
        age = require_int(item.get("age"), f"work[{index}].age")
        units = require_int(item.get("capacityUnits"), f"work[{index}].capacityUnits")
        if age < 0 or units < 0:
            raise ActiveVerificationError(f"work[{index}] age/capacityUnits must be >= 0")
        _cost(item.get("cost"), f"work[{index}].cost")
        if "expectedInformationGain" in item and item["expectedInformationGain"] is not None:
            _number(item["expectedInformationGain"], f"work[{index}].expectedInformationGain")
        prerequisites = require_list(item.get("prerequisites", []), f"work[{index}].prerequisites")
        for pindex, raw_prerequisite in enumerate(prerequisites):
            require_text(raw_prerequisite, f"work[{index}].prerequisites[{pindex}]")
    return campaign


def load_active_verification(path: Path) -> dict[str, Any]:
    return validate_active_verification(json.loads(path.read_text(encoding="utf-8")))


def _planning_cost(item: dict[str, Any]) -> tuple[float, str]:
    cost = item["cost"]
    if cost.get("observed") is not None:
        return float(cost["observed"]), "OBSERVED_COST"
    return float(cost["estimated"]), "ESTIMATED_COST"


def evaluate_active_verification(data: dict[str, Any]) -> dict[str, object]:
    campaign = validate_active_verification(data)
    subject_hash = canonical_sha256(campaign["subject"])
    policy = campaign["policy"]
    weights = policy["weights"]
    completed = set(campaign.get("completedWorkIds", []))
    capacity_total = int(policy["capacityUnits"])
    budget_total = float(policy["budget"])
    capacity_remaining = capacity_total
    budget_remaining = budget_total
    require_eig = bool(policy.get("requireInformationGain", False))

    rows: list[dict[str, object]] = []
    candidates: list[tuple[float, str, dict[str, Any], float, str]] = []
    for item in sorted(campaign["work"], key=lambda row: row["id"]):
        prerequisites = list(item.get("prerequisites", []))
        missing_prerequisites = sorted(set(prerequisites) - completed)
        planning_cost, cost_basis = _planning_cost(item)
        eig = item.get("expectedInformationGain")
        base = {
            "id": item["id"],
            "capability": item["capability"],
            "required": item.get("required", True),
            "subjectHash": subject_hash,
            "planningCost": planning_cost,
            "costBasis": cost_basis,
            "declaredCost": item["cost"].get("declared"),
            "estimatedCost": item["cost"]["estimated"],
            "observedCost": item["cost"].get("observed"),
            "capacityUnits": item["capacityUnits"],
            "expectedInformationGain": eig,
            "verified": False,
        }
        if missing_prerequisites:
            rows.append(
                {
                    **base,
                    "disposition": "BLOCKED_PREREQUISITE",
                    "missingPrerequisites": missing_prerequisites,
                    "score": None,
                }
            )
            continue
        if require_eig and eig is None:
            rows.append(
                {
                    **base,
                    "disposition": "UNMODELED_INFORMATION_VALUE",
                    "missingPrerequisites": [],
                    "score": None,
                }
            )
            continue
        if int(item["capacityUnits"]) > capacity_total or planning_cost > budget_total:
            rows.append(
                {
                    **base,
                    "disposition": "DEFERRED_OVERSIZED",
                    "missingPrerequisites": [],
                    "score": None,
                }
            )
            continue
        eig_value = float(eig or 0.0)
        score = (
            float(item["riskWeight"]) * float(weights["risk"])
            + float(item["priority"]) * float(weights["priority"])
            + float(item["age"]) * float(weights["age"])
            + eig_value * float(weights["informationGain"])
            - planning_cost * float(weights["cost"])
        )
        candidates.append((score, str(item["id"]), item, planning_cost, cost_basis))

    candidates.sort(key=lambda row: (-row[0], row[1]))
    for score, _, item, planning_cost, cost_basis in candidates:
        base = {
            "id": item["id"],
            "capability": item["capability"],
            "required": item.get("required", True),
            "subjectHash": subject_hash,
            "planningCost": planning_cost,
            "costBasis": cost_basis,
            "declaredCost": item["cost"].get("declared"),
            "estimatedCost": item["cost"]["estimated"],
            "observedCost": item["cost"].get("observed"),
            "capacityUnits": item["capacityUnits"],
            "expectedInformationGain": item.get("expectedInformationGain"),
            "verified": False,
            "missingPrerequisites": [],
            "score": score,
        }
        units = int(item["capacityUnits"])
        if units > capacity_remaining:
            disposition = "DEFERRED_CAPACITY"
        elif planning_cost > budget_remaining:
            disposition = "DEFERRED_BUDGET"
        else:
            disposition = "SELECTED"
            capacity_remaining -= units
            budget_remaining -= planning_cost
        rows.append({**base, "disposition": disposition})

    rows.sort(key=lambda row: row["id"])
    selected = [row["id"] for row in rows if row["disposition"] == "SELECTED"]
    debt_receipts: list[dict[str, object]] = []
    debt_status_map = {
        "SELECTED": "ADMITTED",
        "DEFERRED_CAPACITY": "DEFERRED_CAPACITY",
        "DEFERRED_BUDGET": "DEFERRED_BUDGET",
        "DEFERRED_OVERSIZED": "DEFERRED_OVERSIZED",
        "BLOCKED_PREREQUISITE": "BLOCKED",
        "UNMODELED_INFORMATION_VALUE": "BLOCKED",
    }
    for row in rows:
        if row["required"]:
            debt_receipts.append(
                {
                    "id": row["id"],
                    "capability": row["capability"],
                    "required": True,
                    "status": debt_status_map[str(row["disposition"])],
                    "subjectHash": subject_hash,
                }
            )

    return {
        "schema": "cgqa/active-verification-result/v0.1",
        "status": "pass",
        "subjectHash": subject_hash,
        "campaignHash": canonical_sha256(campaign),
        "policyHash": canonical_sha256(policy),
        "selectedWorkIds": selected,
        "capacity": {
            "total": capacity_total,
            "remaining": capacity_remaining,
        },
        "budget": {
            "total": budget_total,
            "remaining": budget_remaining,
        },
        "work": rows,
        "verificationDebtReceipts": debt_receipts,
        "selectionIsVerification": False,
        "informationGainIsTruth": False,
        "claimBoundary": (
            "Selected != Verified; ExpectedInformationGain != Truth; Deferred != Invalid. "
            "Scheduling never authorizes a semantic PASS or execution."
        ),
    }


def evaluate_cost_observation(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/verification-cost-observation/v0.1":
        raise ActiveVerificationError(
            "schema must equal 'cgqa/verification-cost-observation/v0.1'"
        )
    _, subject_hash = require_subject(model)
    work = require_object(model.get("work"), "work")
    work_id = require_text(work.get("id"), "work.id")
    if work.get("subjectHash") != subject_hash:
        raise ActiveVerificationError("work.subjectHash does not match exact subject")
    work_hash = require_text(work.get("workHash"), "work.workHash")
    observation = require_object(model.get("observation"), "observation")
    source_id = require_text(observation.get("sourceId"), "observation.sourceId")
    receipt_hash = require_text(observation.get("receiptHash"), "observation.receiptHash")
    measured = _number(observation.get("measuredCost"), "observation.measuredCost")
    return {
        "schema": "cgqa/verification-cost-observation-result/v0.1",
        "status": "pass",
        "subjectHash": subject_hash,
        "workId": work_id,
        "workHash": work_hash,
        "observedCost": measured,
        "sourceId": source_id,
        "receiptHash": receipt_hash,
        "costIsQuality": False,
        "claimBoundary": "Observed cost is accounting evidence for one exact work item; Cost != Verification Quality and Cost != Truth.",
    }
