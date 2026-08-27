"""Forward-only remediation validation that preserves prior history."""

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

SCHEMA = "cgqa/forward-remediation/v0.1"
ACTIONS = {
    "HOLD",
    "COLLECT_MORE_EVIDENCE",
    "PARAMETER_REVISION",
    "STRUCTURAL_REVISION",
    "SAFE_ROLLBACK",
}


class ForwardRemediationError(CausalTemporalError):
    """Raised when remediation input is malformed."""


def validate_forward_remediation(data: object) -> dict[str, Any]:
    model = require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise ForwardRemediationError(f"schema must equal {SCHEMA!r}")
    _, subject_hash = require_subject(model)
    current = require_object(model.get("current"), "current")
    current_generation = require_int(current.get("generation"), "current.generation")
    if current_generation < 0:
        raise ForwardRemediationError("current.generation must be >= 0")
    require_text(current.get("stateHash"), "current.stateHash")
    proposal = require_object(model.get("proposal"), "proposal")
    require_text(proposal.get("id"), "proposal.id")
    action = require_text(proposal.get("action"), "proposal.action")
    if action not in ACTIONS:
        raise ForwardRemediationError(f"proposal.action must be one of {sorted(ACTIONS)}")
    for field in ("baseGeneration", "evidenceGeneration", "resultGeneration"):
        value = require_int(proposal.get(field), f"proposal.{field}")
        if value < 0:
            raise ForwardRemediationError(f"proposal.{field} must be >= 0")
    if proposal.get("subjectHash") != subject_hash:
        raise ForwardRemediationError("proposal.subjectHash does not match exact subject")
    automatic = proposal.get("automatic", False)
    require_bool(automatic, "proposal.automatic")
    evidence_refs = require_list(proposal.get("evidenceRefs"), "proposal.evidenceRefs")
    if not evidence_refs:
        raise ForwardRemediationError("proposal.evidenceRefs must not be empty")
    for index, ref in enumerate(evidence_refs):
        require_text(ref, f"proposal.evidenceRefs[{index}]")
    require_text(proposal.get("assessmentId"), "proposal.assessmentId")
    if action == "SAFE_ROLLBACK":
        source_generation = require_int(proposal.get("sourceGeneration"), "proposal.sourceGeneration")
        if source_generation < 0:
            raise ForwardRemediationError("proposal.sourceGeneration must be >= 0")
    return model


def load_forward_remediation(path: Path) -> dict[str, Any]:
    return validate_forward_remediation(json.loads(path.read_text(encoding="utf-8")))


def evaluate_forward_remediation(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_forward_remediation(model)
    subject_hash = canonical_sha256(validated["subject"])
    current = validated["current"]
    proposal = validated["proposal"]
    reasons: list[str] = []

    if proposal["baseGeneration"] != current["generation"]:
        reasons.append("STALE_BASE_GENERATION")
    if proposal["evidenceGeneration"] != current["generation"]:
        reasons.append("STALE_REMEDIATION_EVIDENCE")
    if proposal["resultGeneration"] <= current["generation"]:
        reasons.append("HISTORY_REWRITE_OR_NON_FORWARD_RESULT")
    if proposal["automatic"]:
        reasons.append("AUTOMATIC_REMEDIATION_NOT_AUTHORIZED")
    if proposal["action"] == "SAFE_ROLLBACK":
        source_generation = proposal["sourceGeneration"]
        if source_generation >= current["generation"]:
            reasons.append("ROLLBACK_SOURCE_NOT_HISTORICAL")
        if source_generation == proposal["resultGeneration"]:
            reasons.append("ROLLBACK_REUSES_OLD_GENERATION")

    return {
        "schema": "cgqa/forward-remediation-result/v0.1",
        "status": "pass" if not reasons else "fail",
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(validated),
        "proposalId": proposal["id"],
        "action": proposal["action"],
        "baseGeneration": proposal["baseGeneration"],
        "resultGeneration": proposal["resultGeneration"],
        "historyPreserved": not any(
            reason in {"HISTORY_REWRITE_OR_NON_FORWARD_RESULT", "ROLLBACK_REUSES_OLD_GENERATION"}
            for reason in reasons
        ),
        "reasons": reasons,
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "claimBoundary": (
            "ForwardRollback != HistoryRewrite. This result validates proposal structure only; "
            "it does not authorize execution, mutation, or automatic rollback."
        ),
    }
