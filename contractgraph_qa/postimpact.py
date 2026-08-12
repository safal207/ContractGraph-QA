from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from contractgraph_qa.reachability import ReachabilityModel, reachability_model_sha256

POST_IMPACT_MODEL_KEYS = {"containments", "recoveries", "verifications"}
CONTAINMENT_KEYS = {"id", "capabilityId", "description", "outcome", "evidence"}
RECOVERY_KEYS = {
    "id",
    "containmentId",
    "description",
    "outcome",
    "restoredCapabilityId",
    "evidence",
}
RECOVERY_REQUIRED_KEYS = RECOVERY_KEYS - {"restoredCapabilityId"}
VERIFICATION_KEYS = {
    "id",
    "subjectType",
    "subjectId",
    "description",
    "outcome",
    "evidence",
}

CONTAINMENT_OUTCOMES = {"contained", "escaped"}
RECOVERY_OUTCOMES = {"recovered", "failed", "not_attempted"}
VERIFICATION_SUBJECT_TYPES = {"containment", "recovery"}
VERIFICATION_OUTCOMES = {"verified", "failed", "inconclusive"}


@dataclass(frozen=True, slots=True)
class ContainmentNode:
    """A control that attempts to stop propagation after a forbidden capability is reached."""

    id: str
    capability_id: str
    description: str
    outcome: str
    evidence: str


@dataclass(frozen=True, slots=True)
class RecoveryNode:
    """A compensation or restoration action linked to a containment attempt."""

    id: str
    containment_id: str
    description: str
    outcome: str
    restored_capability_id: str | None
    evidence: str


@dataclass(frozen=True, slots=True)
class VerificationNode:
    """A verification statement over a containment or recovery node."""

    id: str
    subject_type: str
    subject_id: str
    description: str
    outcome: str
    evidence: str


@dataclass(frozen=True, slots=True)
class PostImpactModel:
    """Strict deterministic model for containment, recovery, and verification."""

    containments: tuple[ContainmentNode, ...]
    recoveries: tuple[RecoveryNode, ...]
    verifications: tuple[VerificationNode, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _non_empty(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(data: dict[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def post_impact_model_from_dict(data: dict[str, Any]) -> PostImpactModel:
    """Parse a strict post-impact model and reject dangling control references."""

    _require(isinstance(data, dict), "post-impact model must be a JSON object")
    _reject_extra_keys(data, POST_IMPACT_MODEL_KEYS, "post-impact model")
    _require_keys(data, POST_IMPACT_MODEL_KEYS, "post-impact model")

    containments_raw = data["containments"]
    _require(
        isinstance(containments_raw, list) and bool(containments_raw),
        "post-impact model.containments must be a non-empty array",
    )
    containments: list[ContainmentNode] = []
    for index, item in enumerate(containments_raw):
        field = f"post-impact model.containments[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, CONTAINMENT_KEYS, field)
        _require_keys(item, CONTAINMENT_KEYS, field)
        outcome = _non_empty(item["outcome"], f"{field}.outcome")
        _require(outcome in CONTAINMENT_OUTCOMES, f"{field}.outcome must be one of {sorted(CONTAINMENT_OUTCOMES)}")
        containments.append(
            ContainmentNode(
                id=_non_empty(item["id"], f"{field}.id"),
                capability_id=_non_empty(item["capabilityId"], f"{field}.capabilityId"),
                description=_non_empty(item["description"], f"{field}.description"),
                outcome=outcome,
                evidence=_non_empty(item["evidence"], f"{field}.evidence"),
            )
        )

    recoveries_raw = data["recoveries"]
    _require(isinstance(recoveries_raw, list), "post-impact model.recoveries must be an array")
    recoveries: list[RecoveryNode] = []
    for index, item in enumerate(recoveries_raw):
        field = f"post-impact model.recoveries[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, RECOVERY_KEYS, field)
        _require_keys(item, RECOVERY_REQUIRED_KEYS, field)
        outcome = _non_empty(item["outcome"], f"{field}.outcome")
        _require(outcome in RECOVERY_OUTCOMES, f"{field}.outcome must be one of {sorted(RECOVERY_OUTCOMES)}")
        restored = item.get("restoredCapabilityId")
        if restored is not None:
            restored = _non_empty(restored, f"{field}.restoredCapabilityId")
        if outcome == "recovered":
            _require(restored is not None, f"{field}.restoredCapabilityId is required when outcome is recovered")
        else:
            _require(restored is None, f"{field}.restoredCapabilityId is only valid when outcome is recovered")
        recoveries.append(
            RecoveryNode(
                id=_non_empty(item["id"], f"{field}.id"),
                containment_id=_non_empty(item["containmentId"], f"{field}.containmentId"),
                description=_non_empty(item["description"], f"{field}.description"),
                outcome=outcome,
                restored_capability_id=restored,
                evidence=_non_empty(item["evidence"], f"{field}.evidence"),
            )
        )

    verifications_raw = data["verifications"]
    _require(isinstance(verifications_raw, list), "post-impact model.verifications must be an array")
    verifications: list[VerificationNode] = []
    for index, item in enumerate(verifications_raw):
        field = f"post-impact model.verifications[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, VERIFICATION_KEYS, field)
        _require_keys(item, VERIFICATION_KEYS, field)
        subject_type = _non_empty(item["subjectType"], f"{field}.subjectType")
        _require(
            subject_type in VERIFICATION_SUBJECT_TYPES,
            f"{field}.subjectType must be one of {sorted(VERIFICATION_SUBJECT_TYPES)}",
        )
        outcome = _non_empty(item["outcome"], f"{field}.outcome")
        _require(
            outcome in VERIFICATION_OUTCOMES,
            f"{field}.outcome must be one of {sorted(VERIFICATION_OUTCOMES)}",
        )
        verifications.append(
            VerificationNode(
                id=_non_empty(item["id"], f"{field}.id"),
                subject_type=subject_type,
                subject_id=_non_empty(item["subjectId"], f"{field}.subjectId"),
                description=_non_empty(item["description"], f"{field}.description"),
                outcome=outcome,
                evidence=_non_empty(item["evidence"], f"{field}.evidence"),
            )
        )

    all_ids = [item.id for item in containments] + [item.id for item in recoveries] + [item.id for item in verifications]
    _require(len(all_ids) == len(set(all_ids)), "post-impact node ids must be globally unique")

    containment_ids = {item.id for item in containments}
    recovery_ids = {item.id for item in recoveries}
    for recovery in recoveries:
        _require(
            recovery.containment_id in containment_ids,
            f"recovery references unknown containment: {recovery.containment_id}",
        )
    for verification in verifications:
        known = containment_ids if verification.subject_type == "containment" else recovery_ids
        _require(
            verification.subject_id in known,
            f"verification references unknown {verification.subject_type}: {verification.subject_id}",
        )

    return PostImpactModel(
        containments=tuple(containments),
        recoveries=tuple(recoveries),
        verifications=tuple(verifications),
    )


def load_post_impact_model(path: Path) -> PostImpactModel:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return post_impact_model_from_dict(data)


def post_impact_model_to_dict(model: PostImpactModel) -> dict[str, object]:
    return {
        "containments": [
            {
                "id": item.id,
                "capabilityId": item.capability_id,
                "description": item.description,
                "outcome": item.outcome,
                "evidence": item.evidence,
            }
            for item in model.containments
        ],
        "recoveries": [
            {
                "id": item.id,
                "containmentId": item.containment_id,
                "description": item.description,
                "outcome": item.outcome,
                "restoredCapabilityId": item.restored_capability_id,
                "evidence": item.evidence,
            }
            for item in model.recoveries
        ],
        "verifications": [
            {
                "id": item.id,
                "subjectType": item.subject_type,
                "subjectId": item.subject_id,
                "description": item.description,
                "outcome": item.outcome,
                "evidence": item.evidence,
            }
            for item in model.verifications
        ],
    }


def post_impact_model_sha256(model: PostImpactModel) -> str:
    canonical = json.dumps(
        post_impact_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _aggregate_status(
    containments: tuple[ContainmentNode, ...],
    recoveries: tuple[RecoveryNode, ...],
    verifications: tuple[VerificationNode, ...],
) -> str:
    if any(item.outcome == "escaped" for item in containments):
        return "escaped"
    if any(item.outcome == "failed" for item in recoveries):
        return "recovery_failed"
    if not verifications:
        return "unverified"
    if any(item.outcome == "failed" for item in verifications):
        return "verification_failed"
    if any(item.outcome == "inconclusive" for item in verifications):
        return "inconclusive"
    return "contained_and_verified"


def run_post_impact_model(
    model: PostImpactModel,
    reachability_model: ReachabilityModel,
    reachability_result: dict[str, object],
) -> dict[str, object]:
    """Bind a post-impact control graph to the exact selected reachability target."""

    expected_reachability_hash = reachability_model_sha256(reachability_model)
    _require(
        reachability_result.get("modelSha256") == expected_reachability_hash,
        "post-impact input does not match the supplied reachability model",
    )
    _require(
        reachability_result.get("status") == "reachable",
        "post-impact analysis requires a reachable forbidden capability",
    )
    path = reachability_result.get("path")
    _require(isinstance(path, dict), "reachable result must contain a path")
    target = _non_empty(path.get("targetCapability"), "reachability path.targetCapability")

    capabilities = {item.id: item for item in reachability_model.capabilities}
    _require(target in capabilities, f"reachability target capability is unknown: {target}")
    _require(capabilities[target].forbidden, f"post-impact target capability must be forbidden: {target}")

    for containment in model.containments:
        _require(
            containment.capability_id in capabilities,
            f"containment references unknown capability: {containment.capability_id}",
        )
    for recovery in model.recoveries:
        if recovery.restored_capability_id is not None:
            _require(
                recovery.restored_capability_id in capabilities,
                f"recovery references unknown restored capability: {recovery.restored_capability_id}",
            )
            _require(
                not capabilities[recovery.restored_capability_id].forbidden,
                f"recovered capability must not be forbidden: {recovery.restored_capability_id}",
            )

    selected_containments = tuple(sorted(
        (item for item in model.containments if item.capability_id == target),
        key=lambda item: item.id,
    ))
    _require(selected_containments, f"post-impact model has no containment for target capability: {target}")
    containment_ids = {item.id for item in selected_containments}
    selected_recoveries = tuple(sorted(
        (item for item in model.recoveries if item.containment_id in containment_ids),
        key=lambda item: item.id,
    ))
    recovery_ids = {item.id for item in selected_recoveries}
    selected_verifications = tuple(sorted(
        (
            item
            for item in model.verifications
            if (item.subject_type == "containment" and item.subject_id in containment_ids)
            or (item.subject_type == "recovery" and item.subject_id in recovery_ids)
        ),
        key=lambda item: item.id,
    ))

    nodes: list[dict[str, object]] = [
        {
            "id": f"capability:{target}",
            "nodeType": "capability",
            "forbidden": True,
        }
    ]
    edges: list[dict[str, str]] = []

    for containment in selected_containments:
        node_id = f"containment:{containment.id}"
        nodes.append(
            {
                "id": node_id,
                "nodeType": "containment",
                "description": containment.description,
                "outcome": containment.outcome,
                "evidence": containment.evidence,
            }
        )
        edges.append(
            {
                "source": f"capability:{target}",
                "relation": "contained_by",
                "target": node_id,
            }
        )

    for recovery in selected_recoveries:
        node_id = f"recovery:{recovery.id}"
        nodes.append(
            {
                "id": node_id,
                "nodeType": "recovery",
                "description": recovery.description,
                "outcome": recovery.outcome,
                "restoredCapabilityId": recovery.restored_capability_id,
                "evidence": recovery.evidence,
            }
        )
        edges.append(
            {
                "source": f"containment:{recovery.containment_id}",
                "relation": "recovered_by",
                "target": node_id,
            }
        )
        if recovery.restored_capability_id is not None:
            restored = recovery.restored_capability_id
            restored_node = f"capability:{restored}"
            if not any(item["id"] == restored_node for item in nodes):
                nodes.append(
                    {
                        "id": restored_node,
                        "nodeType": "capability",
                        "forbidden": capabilities[restored].forbidden,
                    }
                )
            edges.append(
                {
                    "source": node_id,
                    "relation": "restores_to",
                    "target": restored_node,
                }
            )

    for verification in selected_verifications:
        node_id = f"verification:{verification.id}"
        nodes.append(
            {
                "id": node_id,
                "nodeType": "verification",
                "description": verification.description,
                "outcome": verification.outcome,
                "evidence": verification.evidence,
            }
        )
        edges.append(
            {
                "source": f"{verification.subject_type}:{verification.subject_id}",
                "relation": "verified_by",
                "target": node_id,
            }
        )

    nodes.sort(key=lambda item: str(item["id"]))
    edges.sort(key=lambda item: (item["source"], item["relation"], item["target"]))

    return {
        "status": _aggregate_status(selected_containments, selected_recoveries, selected_verifications),
        "postImpactModelSha256": post_impact_model_sha256(model),
        "boundReachabilityModelSha256": expected_reachability_hash,
        "boundTargetCapability": target,
        "controlGraph": {
            "nodes": nodes,
            "edges": edges,
        },
    }
