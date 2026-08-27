"""Fail-closed records for source-bound external smart-contract investigations.

The record is deliberately chain-neutral.  It can preserve a useful finding before
ContractGraph-QA or a target-native regression is runnable, while keeping reported,
archived, and verified evidence states distinct.  Validation never turns a journal
entry into a security verdict.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

from contractgraph_qa.causal_temporal_utils import canonical_sha256

SCHEMA = "cgqa/external-investigation/v0.1"
RESULT_SCHEMA = "cgqa/external-investigation-result/v0.1"

CAPABILITY_IDS = (
    "exact_subject_artifact_gate",
    "preregistered_verification_plan",
    "orientation_center",
    "native_mapping_adapter_review",
    "safety_invariants",
    "liveness_reachability",
    "financial_conservation",
    "authorization_capabilities",
    "replay_idempotency",
    "temporal_lifecycle",
    "crash_recovery",
    "causal_ancestral_validity",
    "transition_geometry",
    "negative_control",
    "stateful_property_search",
    "independent_witness",
    "trace_integrity",
    "evidence_type_readiness",
    "counterexample_minimization",
    "root_cause_collapse",
    "deterministic_replay",
    "metamorphic_round_trip_verification",
    "native_regression",
    "durable_evidence_reopen_integrity",
    "verification_debt",
    "active_verification_planning",
    "meaning_trajectory",
    "dormant_patterns_watchpoints",
    "temporal_external_replication",
    "forward_remediation",
)

CAPABILITY_STATUSES = {
    "RUN",
    "NOT_APPLICABLE",
    "BLOCKED",
    "SKIPPED_WITH_REASON",
    "NOT_RUN",
}
AUTHORIZATION_STATUSES = {"CONFIRMED", "UNCONFIRMED", "NOT_REQUIRED"}
AUTHORIZATION_BASES = {
    "ASSIGNED_PUBLIC_ISSUE",
    "WRITTEN_SCOPE",
    "OWNED_TARGET",
    "PUBLIC_SAFE_HARBOR",
    "SOURCE_REVIEW_ONLY",
}
INVARIANT_FAMILIES = {
    "SAFETY",
    "LIVENESS",
    "CONSERVATION",
    "AUTHORIZATION",
    "REPLAY",
    "TEMPORAL",
    "CRASH_RECOVERY",
    "ECONOMIC_FAIRNESS",
    "OTHER",
}
EVIDENCE_KINDS = {
    "SOURCE",
    "ISSUE_UPDATE",
    "INDEPENDENT_HARNESS",
    "RESOURCE_MEASUREMENT",
    "IMPACT_MEASUREMENT",
    "NATIVE_REGRESSION",
    "CI",
    "CGQA_BUNDLE",
}
EVIDENCE_STATES = {
    "DIRECTLY_OBSERVED",
    "REPORTED_NOT_ARCHIVED",
    "ARCHIVED_UNVERIFIED",
    "VERIFIED",
}
EXECUTION_STATUSES = {"NOT_RUN", "BLOCKED", "RUN_FAIL", "RUN_PASS"}
FINDING_STATUSES = {
    "COUNTEREXAMPLE_FOUND",
    "NO_COUNTEREXAMPLE_WITHIN_BOUND",
    "INCONCLUSIVE",
    "NOT_RUN",
}
REMEDIATION_STATUSES = {
    "NOT_STARTED",
    "PROPOSED",
    "BLOCKED",
    "IMPLEMENTED_UNVERIFIED",
    "VERIFIED_WITHIN_BOUND",
}
BLOCKER_STATUSES = {"OPEN", "RESOLVED"}
DEBT_STATUSES = {"OPEN", "BLOCKED", "DONE_PASS", "DONE_FAIL", "NOT_APPLICABLE"}
IMPACT_CLASSES = {"QUALITATIVE", "MODELED", "MEASURED"}

TOP_LEVEL_KEYS = {
    "schema",
    "investigationId",
    "recordedAt",
    "subject",
    "authorization",
    "property",
    "evidence",
    "execution",
    "finding",
    "blockers",
    "capabilityMatrix",
    "verificationDebt",
    "impact",
    "nonClaims",
}
SUBJECT_KEYS = {
    "repository",
    "commitSha",
    "issueUrl",
    "paths",
    "ecosystem",
    "language",
    "framework",
    "network",
}
AUTHORIZATION_KEYS = {"status", "basis", "referenceUrl", "scope"}
PROPERTY_KEYS = {"id", "statement", "invariantFamily", "protectedOutcome"}
EVIDENCE_KEYS = {"id", "kind", "state", "reference", "claim", "sha256"}
EXECUTION_KEYS = {"nativeRegression", "contractGraphQa"}
NATIVE_EXECUTION_KEYS = {"status", "reference", "evidenceSha256"}
CGQA_EXECUTION_KEYS = {"status", "headSha", "reference", "evidenceSha256"}
FINDING_KEYS = {
    "status",
    "claim",
    "rootCause",
    "evidenceIds",
    "searchBound",
    "remediationStatus",
}
BLOCKER_KEYS = {"id", "status", "owner", "question", "reference"}
CAPABILITY_KEYS = {"id", "status", "evidenceBoundary"}
DEBT_KEYS = {"id", "capabilityId", "required", "status", "nextEvidence"}
IMPACT_KEYS = {"classification", "protectedOutcome", "statement", "evidenceIds", "assumptions"}

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ExternalInvestigationError(ValueError):
    """Raised when an external investigation record is malformed or overclaims."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExternalInvestigationError(message)


def _object(value: object, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{field} must be an object")
    return value


def _strict(value: object, allowed: set[str], field: str) -> dict[str, Any]:
    item = _object(value, field)
    missing = sorted(allowed - set(item))
    extras = sorted(set(item) - allowed)
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")
    return item


def _list(value: object, field: str) -> list[Any]:
    _require(isinstance(value, list), f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _nullable_text(value: object, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _enum(value: object, allowed: set[str], field: str) -> str:
    text = _text(value, field)
    _require(text in allowed, f"{field} has unsupported value: {text}")
    return text


def _safe_id(value: object, field: str) -> str:
    text = _text(value, field)
    _require(_SAFE_ID.fullmatch(text) is not None, f"{field} must be a safe identifier")
    return text


def _sha(value: object, field: str, length: int) -> str:
    text = _text(value, field)
    pattern = _HEX40 if length == 40 else _HEX64
    _require(pattern.fullmatch(text) is not None, f"{field} must be {length} lowercase hex characters")
    return text


def _nullable_sha(value: object, field: str, length: int) -> str | None:
    return None if value is None else _sha(value, field, length)


def _https_url(value: object, field: str) -> str:
    text = _text(value, field)
    _require(text.startswith("https://"), f"{field} must use https://")
    return text


def _nullable_reference(value: object, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _unique_texts(value: object, field: str, *, require_items: bool = False) -> list[str]:
    raw = _list(value, field)
    if require_items:
        _require(bool(raw), f"{field} must not be empty")
    items = [_text(item, f"{field}[{index}]") for index, item in enumerate(raw)]
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def _timestamp(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalInvestigationError(f"{field} must be an RFC3339 timestamp") from exc
    _require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return text


def _validate_subject(value: object) -> dict[str, Any]:
    subject = _strict(value, SUBJECT_KEYS, "subject")
    repository = _text(subject["repository"], "subject.repository")
    _require(_REPOSITORY.fullmatch(repository) is not None, "subject.repository must be owner/name")
    _sha(subject["commitSha"], "subject.commitSha", 40)
    _https_url(subject["issueUrl"], "subject.issueUrl")
    paths = _unique_texts(subject["paths"], "subject.paths", require_items=True)
    for index, path in enumerate(paths):
        parsed = PurePosixPath(path)
        _require(not parsed.is_absolute(), f"subject.paths[{index}] must be relative")
        _require(".." not in parsed.parts, f"subject.paths[{index}] must not traverse parents")
    for name in ("ecosystem", "language", "framework"):
        _text(subject[name], f"subject.{name}")
    _nullable_text(subject["network"], "subject.network")
    return subject


def _validate_authorization(value: object) -> dict[str, Any]:
    authorization = _strict(value, AUTHORIZATION_KEYS, "authorization")
    status = _enum(authorization["status"], AUTHORIZATION_STATUSES, "authorization.status")
    _enum(authorization["basis"], AUTHORIZATION_BASES, "authorization.basis")
    reference = authorization["referenceUrl"]
    if reference is not None:
        _https_url(reference, "authorization.referenceUrl")
    if status == "CONFIRMED":
        _require(reference is not None, "confirmed authorization requires referenceUrl")
    _text(authorization["scope"], "authorization.scope")
    return authorization


def _validate_property(value: object) -> dict[str, Any]:
    item = _strict(value, PROPERTY_KEYS, "property")
    _safe_id(item["id"], "property.id")
    _text(item["statement"], "property.statement")
    _enum(item["invariantFamily"], INVARIANT_FAMILIES, "property.invariantFamily")
    _text(item["protectedOutcome"], "property.protectedOutcome")
    return item


def _validate_evidence(
    value: object,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    raw = _list(value, "evidence")
    _require(bool(raw), "evidence must not be empty")
    items: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value_item in enumerate(raw):
        field = f"evidence[{index}]"
        item = _strict(value_item, EVIDENCE_KEYS, field)
        evidence_id = _safe_id(item["id"], f"{field}.id")
        _require(evidence_id not in ids, f"duplicate evidence id: {evidence_id}")
        ids.add(evidence_id)
        _enum(item["kind"], EVIDENCE_KINDS, f"{field}.kind")
        state = _enum(item["state"], EVIDENCE_STATES, f"{field}.state")
        _text(item["reference"], f"{field}.reference")
        _text(item["claim"], f"{field}.claim")
        digest = _nullable_sha(item["sha256"], f"{field}.sha256", 64)
        if state == "REPORTED_NOT_ARCHIVED":
            _require(digest is None, f"{field}.sha256 must be null when evidence is not archived")
        if state in {"ARCHIVED_UNVERIFIED", "VERIFIED"}:
            _require(digest is not None, f"{field}.sha256 is required for archived evidence")
        items.append(item)
    return items, {item["id"]: item for item in items}


def _validate_execution_item(
    value: object,
    *,
    field: str,
    keys: set[str],
    require_head: bool,
) -> dict[str, Any]:
    item = _strict(value, keys, field)
    status = _enum(item["status"], EXECUTION_STATUSES, f"{field}.status")
    reference = _nullable_reference(item["reference"], f"{field}.reference")
    digest = _nullable_sha(item["evidenceSha256"], f"{field}.evidenceSha256", 64)
    head = None
    if require_head:
        head = _nullable_sha(item["headSha"], f"{field}.headSha", 40)
    if status in {"RUN_PASS", "RUN_FAIL"}:
        _require(reference is not None, f"{field}.reference is required after execution")
        _require(digest is not None, f"{field}.evidenceSha256 is required after execution")
        if require_head:
            _require(head is not None, f"{field}.headSha is required after execution")
    else:
        _require(reference is None, f"{field}.reference must be null when execution did not run")
        _require(digest is None, f"{field}.evidenceSha256 must be null when execution did not run")
        if require_head:
            _require(head is None, f"{field}.headSha must be null when execution did not run")
    return item


def _validate_execution(value: object) -> dict[str, Any]:
    execution = _strict(value, EXECUTION_KEYS, "execution")
    _validate_execution_item(
        execution["nativeRegression"],
        field="execution.nativeRegression",
        keys=NATIVE_EXECUTION_KEYS,
        require_head=False,
    )
    _validate_execution_item(
        execution["contractGraphQa"],
        field="execution.contractGraphQa",
        keys=CGQA_EXECUTION_KEYS,
        require_head=True,
    )
    return execution


def _validate_finding(
    value: object,
    *,
    evidence_ids: set[str],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    finding = _strict(value, FINDING_KEYS, "finding")
    status = _enum(finding["status"], FINDING_STATUSES, "finding.status")
    _text(finding["claim"], "finding.claim")
    root_cause = _nullable_text(finding["rootCause"], "finding.rootCause")
    search_bound = _nullable_text(finding["searchBound"], "finding.searchBound")
    refs = _unique_texts(finding["evidenceIds"], "finding.evidenceIds")
    missing = sorted(set(refs) - evidence_ids)
    _require(not missing, "finding references unknown evidence ids: " + ", ".join(missing))
    remediation = _enum(
        finding["remediationStatus"],
        REMEDIATION_STATUSES,
        "finding.remediationStatus",
    )
    native_status = execution["nativeRegression"]["status"]
    cgqa_status = execution["contractGraphQa"]["status"]
    if status == "COUNTEREXAMPLE_FOUND":
        _require(bool(refs), "COUNTEREXAMPLE_FOUND requires evidenceIds")
        _require(root_cause is not None, "COUNTEREXAMPLE_FOUND requires rootCause")
    if status == "NO_COUNTEREXAMPLE_WITHIN_BOUND":
        _require(search_bound is not None, "NO_COUNTEREXAMPLE_WITHIN_BOUND requires searchBound")
        _require(
            native_status == "RUN_PASS" or cgqa_status == "RUN_PASS",
            "NO_COUNTEREXAMPLE_WITHIN_BOUND requires an executed passing search",
        )
    if status == "NOT_RUN":
        _require(not refs, "NOT_RUN finding must not cite outcome evidence")
        _require(root_cause is None, "NOT_RUN finding must not claim a root cause")
    if remediation == "VERIFIED_WITHIN_BOUND":
        _require(
            native_status == "RUN_PASS" and cgqa_status == "RUN_PASS",
            "VERIFIED_WITHIN_BOUND requires native and ContractGraph-QA RUN_PASS evidence",
        )
    return finding


def _validate_blockers(value: object) -> list[dict[str, Any]]:
    raw = _list(value, "blockers")
    items: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value_item in enumerate(raw):
        field = f"blockers[{index}]"
        item = _strict(value_item, BLOCKER_KEYS, field)
        blocker_id = _safe_id(item["id"], f"{field}.id")
        _require(blocker_id not in ids, f"duplicate blocker id: {blocker_id}")
        ids.add(blocker_id)
        status = _enum(item["status"], BLOCKER_STATUSES, f"{field}.status")
        _text(item["owner"], f"{field}.owner")
        _text(item["question"], f"{field}.question")
        reference = _nullable_reference(item["reference"], f"{field}.reference")
        if status == "RESOLVED":
            _require(reference is not None, f"{field}.reference is required when resolved")
        items.append(item)
    return items


def _validate_capabilities(value: object) -> list[dict[str, Any]]:
    raw = _list(value, "capabilityMatrix")
    items: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value_item in enumerate(raw):
        field = f"capabilityMatrix[{index}]"
        item = _strict(value_item, CAPABILITY_KEYS, field)
        capability_id = _safe_id(item["id"], f"{field}.id")
        _require(capability_id not in ids, f"duplicate capability id: {capability_id}")
        ids.add(capability_id)
        _enum(item["status"], CAPABILITY_STATUSES, f"{field}.status")
        _text(item["evidenceBoundary"], f"{field}.evidenceBoundary")
        items.append(item)
    expected = set(CAPABILITY_IDS)
    _require(
        ids == expected,
        "capabilityMatrix must classify the complete AGENTS.md capability set; "
        f"missing={sorted(expected - ids)}, extra={sorted(ids - expected)}",
    )
    return items


def _validate_debt(value: object) -> list[dict[str, Any]]:
    raw = _list(value, "verificationDebt")
    items: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, value_item in enumerate(raw):
        field = f"verificationDebt[{index}]"
        item = _strict(value_item, DEBT_KEYS, field)
        debt_id = _safe_id(item["id"], f"{field}.id")
        _require(debt_id not in ids, f"duplicate verification debt id: {debt_id}")
        ids.add(debt_id)
        capability_id = _safe_id(item["capabilityId"], f"{field}.capabilityId")
        _require(capability_id in CAPABILITY_IDS, f"{field}.capabilityId is unknown")
        _require(isinstance(item["required"], bool), f"{field}.required must be boolean")
        _enum(item["status"], DEBT_STATUSES, f"{field}.status")
        _text(item["nextEvidence"], f"{field}.nextEvidence")
        items.append(item)
    return items


def _validate_impact(
    value: object, evidence_by_id: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    impact = _strict(value, IMPACT_KEYS, "impact")
    classification = _enum(
        impact["classification"], IMPACT_CLASSES, "impact.classification"
    )
    _text(impact["protectedOutcome"], "impact.protectedOutcome")
    _text(impact["statement"], "impact.statement")
    refs = _unique_texts(impact["evidenceIds"], "impact.evidenceIds")
    missing = sorted(set(refs) - set(evidence_by_id))
    _require(not missing, "impact references unknown evidence ids: " + ", ".join(missing))
    assumptions = _unique_texts(impact["assumptions"], "impact.assumptions")
    if classification == "MEASURED":
        _require(bool(refs), "MEASURED impact requires evidenceIds")
        measured = [
            evidence_by_id[ref]
            for ref in refs
            if evidence_by_id[ref]["kind"] == "IMPACT_MEASUREMENT"
            and evidence_by_id[ref]["state"] == "VERIFIED"
        ]
        _require(
            bool(measured),
            "MEASURED impact requires VERIFIED IMPACT_MEASUREMENT evidence",
        )
    if classification == "MODELED":
        _require(bool(assumptions), "MODELED impact requires explicit assumptions")
    return impact


def validate_external_investigation(data: object) -> dict[str, Any]:
    """Validate a strict external-investigation record without upgrading its claims."""

    model = _strict(data, TOP_LEVEL_KEYS, "record")
    _require(model["schema"] == SCHEMA, f"schema must equal {SCHEMA}")
    _safe_id(model["investigationId"], "investigationId")
    _timestamp(model["recordedAt"], "recordedAt")
    _validate_subject(model["subject"])
    _validate_authorization(model["authorization"])
    _validate_property(model["property"])
    _, evidence_by_id = _validate_evidence(model["evidence"])
    execution = _validate_execution(model["execution"])
    _validate_finding(
        model["finding"], evidence_ids=set(evidence_by_id), execution=execution
    )
    blockers = _validate_blockers(model["blockers"])
    capabilities = _validate_capabilities(model["capabilityMatrix"])
    _validate_debt(model["verificationDebt"])
    _validate_impact(model["impact"], evidence_by_id)
    _unique_texts(model["nonClaims"], "nonClaims", require_items=True)

    open_blockers = [item for item in blockers if item["status"] == "OPEN"]
    remediation_status = model["finding"]["remediationStatus"]
    if remediation_status == "BLOCKED":
        _require(bool(open_blockers), "BLOCKED remediation requires an OPEN blocker")
    if remediation_status == "VERIFIED_WITHIN_BOUND":
        _require(not open_blockers, "verified remediation cannot retain an OPEN blocker")

    capability_by_id = {item["id"]: item for item in capabilities}
    native_execution_status = execution["nativeRegression"]["status"]
    expected_native_capability_status = {
        "NOT_RUN": "NOT_RUN",
        "BLOCKED": "BLOCKED",
        "RUN_FAIL": "RUN",
        "RUN_PASS": "RUN",
    }[native_execution_status]
    _require(
        capability_by_id["native_regression"]["status"]
        == expected_native_capability_status,
        "native_regression capability status must match native execution state",
    )
    return model


def load_external_investigation(path: Path) -> dict[str, Any]:
    return validate_external_investigation(json.loads(path.read_text(encoding="utf-8")))


def evaluate_external_investigation(model: dict[str, Any]) -> dict[str, object]:
    """Project workflow readiness while preserving finding and evidence boundaries."""

    validated = validate_external_investigation(model)
    blockers = validated["blockers"]
    debt = validated["verificationDebt"]
    open_blocker_ids = sorted(item["id"] for item in blockers if item["status"] == "OPEN")
    failed_debt_ids = sorted(
        item["id"]
        for item in debt
        if item["required"] and item["status"] == "DONE_FAIL"
    )
    unresolved_debt_ids = sorted(
        item["id"]
        for item in debt
        if item["required"] and item["status"] in {"OPEN", "BLOCKED"}
    )
    native_status = validated["execution"]["nativeRegression"]["status"]
    cgqa_status = validated["execution"]["contractGraphQa"]["status"]
    bounded_remediation_verified = (
        validated["finding"]["remediationStatus"] == "VERIFIED_WITHIN_BOUND"
        and native_status == "RUN_PASS"
        and cgqa_status == "RUN_PASS"
    )

    if validated["authorization"]["status"] == "UNCONFIRMED":
        workflow_status = "BLOCKED"
        reasons = ["AUTHORIZATION_UNCONFIRMED"]
    elif native_status == "RUN_FAIL" or cgqa_status == "RUN_FAIL":
        workflow_status = "UNSTABLE"
        reasons = ["NATIVE_OR_CGQA_EXECUTION_FAILED"]
    elif failed_debt_ids:
        workflow_status = "UNSTABLE"
        reasons = ["REQUIRED_VERIFICATION_FAILED"]
    elif open_blocker_ids:
        workflow_status = "BLOCKED"
        reasons = ["OPEN_AUTHORITY_OR_ARCHITECTURE_BLOCKER"]
    elif unresolved_debt_ids:
        workflow_status = "INDETERMINATE"
        reasons = ["REQUIRED_VERIFICATION_DEBT_UNRESOLVED"]
    elif not bounded_remediation_verified:
        workflow_status = "INDETERMINATE"
        reasons = ["EXECUTION_OR_REMEDIATION_INCOMPLETE"]
    else:
        workflow_status = "BALANCED"
        reasons = []

    capability_counts = Counter(item["status"] for item in validated["capabilityMatrix"])
    evidence_counts = Counter(item["state"] for item in validated["evidence"])
    next_transition_ids = open_blocker_ids or unresolved_debt_ids or failed_debt_ids

    return {
        "schema": RESULT_SCHEMA,
        "recordValidationStatus": "VALID",
        "investigationId": validated["investigationId"],
        "recordHash": canonical_sha256(validated),
        "subjectHash": canonical_sha256(validated["subject"]),
        "subjectCommitSha": validated["subject"]["commitSha"],
        "findingStatus": validated["finding"]["status"],
        "workflowStatus": workflow_status,
        "workflowReasonCodes": reasons,
        "nativeRegressionStatus": native_status,
        "contractGraphQaStatus": cgqa_status,
        "boundedRemediationVerified": bounded_remediation_verified,
        "capabilityStatusCounts": dict(sorted(capability_counts.items())),
        "evidenceStateCounts": dict(sorted(evidence_counts.items())),
        "openBlockerIds": open_blocker_ids,
        "failedRequiredDebtIds": failed_debt_ids,
        "unresolvedRequiredDebtIds": unresolved_debt_ids,
        "nextTransitionIds": next_transition_ids,
        "impactClassification": validated["impact"]["classification"],
        "securityVerdictAuthorized": False,
        "claimBoundary": (
            "A valid external-investigation record preserves a source-bound finding, "
            "evidence state, blockers, and verification debt. It is not a ContractGraph-QA "
            "execution result, remediation verification, audit opinion, or security certification."
        ),
    }
