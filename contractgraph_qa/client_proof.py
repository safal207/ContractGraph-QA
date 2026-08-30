"""Deterministic client proof-pack assembly for repository-owned demos."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from contractgraph_qa.change_gate_measurement import (
    COVERAGE_SCOPE,
    validate_change_gate_measurement_source,
)
from contractgraph_qa.measurement_provenance import verify_measurement_provenance_result
from contractgraph_qa.path_replay import replay_prior_model_path
from contractgraph_qa.postimpact import PostImpactModel, run_post_impact_model
from contractgraph_qa.reachability import ReachabilityModel, run_reachability_model


PROOF_SCHEMA = "cgqa.client-proof.v2"
CAUSAL_PROOF_SCHEMA = "cgqa.client-causal-proof.v1"
CHANGE_GATE_EVIDENCE_SCHEMA = "cgqa.client-change-gate-evidence.v1"
MEASUREMENT_PROVENANCE_EVIDENCE_SCHEMA = "cgqa.client-measurement-provenance-evidence.v1"


def _coverage(result: dict[str, Any]) -> dict[str, int]:
    counts = {
        "violated": 0,
        "not_found_within_bound": 0,
        "inconclusive": 0,
    }
    checks = result.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("engagement result must contain checks")
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("engagement result checks must be objects")
        status = check.get("status")
        if status not in counts:
            raise ValueError(f"unsupported engagement check status: {status}")
        counts[status] += 1
    return counts


def _violated_check(result: dict[str, Any]) -> dict[str, Any]:
    violated = [
        check
        for check in result["checks"]
        if isinstance(check, dict) and check.get("status") == "violated"
    ]
    if len(violated) != 1:
        raise ValueError("repository proof fixture must contain exactly one violated check")
    return violated[0]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _require_commit_sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError(f"{label} must be a 40-character git commit SHA")
    return value.lower()


def validate_change_gate_result_for_client_proof(
    gate_result: dict[str, Any],
) -> None:
    """Validate only the identity envelope needed to bind a gate result verbatim."""

    if not isinstance(gate_result, dict):
        raise ValueError("change-gate result must be a JSON object")
    if gate_result.get("schemaVersion") != 1:
        raise ValueError("change-gate result schemaVersion must be 1")
    if gate_result.get("status") not in {"pass", "review", "blocked"}:
        raise ValueError("change-gate result status must be pass, review, or blocked")
    _require_commit_sha(gate_result.get("baseCommitSha"), "baseCommitSha")
    _require_commit_sha(gate_result.get("headCommitSha"), "headCommitSha")
    models = gate_result.get("models")
    if not isinstance(models, list):
        raise ValueError("change-gate result models must be an array")


def change_gate_result_sha256(gate_result: dict[str, Any]) -> str:
    """Return the canonical content digest for one machine change-gate result."""

    validate_change_gate_result_for_client_proof(gate_result)
    return hashlib.sha256(_canonical_json_bytes(gate_result)).hexdigest()


def build_change_gate_evidence(gate_result: dict[str, Any]) -> dict[str, Any]:
    """Bind an exact machine gate result into client evidence without reinterpretation."""

    validate_change_gate_result_for_client_proof(gate_result)
    return {
        "schema": CHANGE_GATE_EVIDENCE_SCHEMA,
        "gateResultSha256": change_gate_result_sha256(gate_result),
        "gateResult": copy.deepcopy(gate_result),
    }


def verify_change_gate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Verify a client-proof gate binding and return the exact bound gate result."""

    if not isinstance(evidence, dict):
        raise ValueError("change-gate evidence must be an object")
    if set(evidence) != {"schema", "gateResultSha256", "gateResult"}:
        raise ValueError(
            "change-gate evidence must contain exactly schema, gateResultSha256, and gateResult"
        )
    if evidence.get("schema") != CHANGE_GATE_EVIDENCE_SCHEMA:
        raise ValueError("unsupported change-gate evidence schema")

    gate_result = evidence.get("gateResult")
    if not isinstance(gate_result, dict):
        raise ValueError("change-gate evidence gateResult must be an object")
    expected = change_gate_result_sha256(gate_result)
    actual = evidence.get("gateResultSha256")
    if actual != expected:
        raise ValueError("change-gate evidence digest mismatch")
    return copy.deepcopy(gate_result)


def attach_change_gate_evidence(
    proof_pack: dict[str, Any],
    gate_result: dict[str, Any],
) -> dict[str, Any]:
    """Attach the exact gate result to a client proof pack as content-addressed evidence."""

    if not isinstance(proof_pack, dict):
        raise ValueError("client proof pack must be a JSON object")
    evidence = build_change_gate_evidence(gate_result)
    existing = proof_pack.get("changeGateEvidence")
    if existing is not None and existing != evidence:
        raise ValueError("client proof pack already contains different change-gate evidence")

    bound = copy.deepcopy(proof_pack)
    bound["changeGateEvidence"] = evidence
    return bound


def measurement_provenance_result_sha256(result: dict[str, Any]) -> str:
    """Return the canonical digest after independently recomputing the provenance verdict."""

    verify_measurement_provenance_result(result)
    return hashlib.sha256(_canonical_json_bytes(result)).hexdigest()


def _validate_provenance_result_against_source(
    result: dict[str, Any], source: dict[str, Any]
) -> None:
    verify_measurement_provenance_result(result)
    measurements = result.get("measurements")
    if not isinstance(measurements, list) or len(measurements) != 1:
        raise ValueError("change-gate provenance must contain exactly one measurement")
    measurement = measurements[0]
    if not isinstance(measurement, dict):
        raise ValueError("change-gate provenance measurement must be an object")
    if measurement.get("id") != source.get("measurementId"):
        raise ValueError("measurement-provenance source measurement id mismatch")
    if measurement.get("coverageScope") != COVERAGE_SCOPE:
        raise ValueError("measurement-provenance coverage scope mismatch")
    if measurement.get("observedUnits") != len(source["observedModelIds"]):
        raise ValueError("measurement-provenance observed count does not match source ids")
    if measurement.get("eligibleUnits") != len(source["eligibleModelIds"]):
        raise ValueError("measurement-provenance eligible count does not match source ids")


def build_measurement_provenance_evidence(
    result: dict[str, Any],
    source: dict[str, Any],
    *,
    gate_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Content-address a recomputed result plus the exact source-binding receipt."""

    validate_change_gate_measurement_source(source, gate_result=gate_result)
    _validate_provenance_result_against_source(result, source)
    return {
        "schema": MEASUREMENT_PROVENANCE_EVIDENCE_SCHEMA,
        "source": copy.deepcopy(source),
        "provenanceResultSha256": measurement_provenance_result_sha256(result),
        "provenanceResult": copy.deepcopy(result),
    }


def verify_measurement_provenance_evidence(
    evidence: dict[str, Any],
    *,
    gate_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify source binding, result semantics, and the content digest."""

    if not isinstance(evidence, dict):
        raise ValueError("measurement-provenance evidence must be an object")
    if set(evidence) != {
        "schema",
        "source",
        "provenanceResultSha256",
        "provenanceResult",
    }:
        raise ValueError("measurement-provenance evidence has invalid shape")
    if evidence.get("schema") != MEASUREMENT_PROVENANCE_EVIDENCE_SCHEMA:
        raise ValueError("unsupported measurement-provenance evidence schema")

    source = evidence.get("source")
    result = evidence.get("provenanceResult")
    if not isinstance(source, dict) or not isinstance(result, dict):
        raise ValueError("measurement-provenance evidence source/result must be objects")
    validate_change_gate_measurement_source(source, gate_result=gate_result)
    _validate_provenance_result_against_source(result, source)
    expected = measurement_provenance_result_sha256(result)
    if evidence.get("provenanceResultSha256") != expected:
        raise ValueError("measurement-provenance evidence digest mismatch")
    return copy.deepcopy(result)


def attach_measurement_provenance_evidence(
    proof_pack: dict[str, Any],
    result: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Attach provenance only when it passes and matches the proof's exact gate result."""

    if not isinstance(proof_pack, dict):
        raise ValueError("client proof pack must be a JSON object")
    change_evidence = proof_pack.get("changeGateEvidence")
    if not isinstance(change_evidence, dict):
        raise ValueError(
            "measurement provenance requires changeGateEvidence in the client proof"
        )
    gate_result = verify_change_gate_evidence(change_evidence)
    evidence = build_measurement_provenance_evidence(
        result, source, gate_result=gate_result
    )
    verified = verify_measurement_provenance_evidence(
        evidence, gate_result=gate_result
    )
    if verified.get("status") != "pass":
        raise ValueError(
            "blocked measurement provenance cannot be bound into an authoritative client proof"
        )

    existing = proof_pack.get("measurementProvenanceEvidence")
    if existing is not None and existing != evidence:
        raise ValueError(
            "client proof pack already contains different measurement-provenance evidence"
        )
    bound = copy.deepcopy(proof_pack)
    bound["measurementProvenanceEvidence"] = evidence
    return bound


def build_causal_security_proof(
    prior_model: ReachabilityModel,
    post_impact_model: PostImpactModel,
    fixed_model: ReachabilityModel,
) -> dict[str, Any]:
    """Build the causal introduction → control → fix replay proof chain."""

    prior = run_reachability_model(prior_model)
    if prior["status"] != "reachable" or not isinstance(prior.get("path"), dict):
        raise ValueError("prior model must contain a reachable forbidden target path")

    path = prior["path"]
    target = path.get("targetCapability")
    forbidden = {
        capability.id: capability.forbidden for capability in prior_model.capabilities
    }
    if not isinstance(target, str) or not forbidden.get(target, False):
        raise ValueError("prior path target must be a forbidden capability")

    control = run_post_impact_model(post_impact_model, prior_model, prior)
    replay = replay_prior_model_path(prior_model, fixed_model)
    if replay["status"] != "fix_verified":
        raise ValueError("client proof fixture requires a verified fixed model")

    return {
        "schema": CAUSAL_PROOF_SCHEMA,
        "sourceType": "repository-owned-local-causal-fixture",
        "forbiddenCapability": target,
        "priorModelSha256": prior["modelSha256"],
        "causalPath": path,
        "control": {
            "status": control["status"],
            "postImpactModelSha256": control["postImpactModelSha256"],
            "boundReachabilityModelSha256": control[
                "boundReachabilityModelSha256"
            ],
            "boundTargetCapability": control["boundTargetCapability"],
            "controlGraph": control["controlGraph"],
        },
        "fixReplay": {
            "status": replay["status"],
            "fixedModelSha256": replay["fixedModelSha256"],
            "exactReplay": replay["exactReplay"],
            "alternateReachability": replay["alternateReachability"],
        },
        "claimBoundary": {
            "authorizedLocalModelOnly": True,
            "productionExploitabilityClaim": False,
            "exhaustiveSecurityClaim": False,
        },
    }


def build_client_proof_pack(
    engagement_result: dict[str, Any],
    prior_model: ReachabilityModel,
    post_impact_model: PostImpactModel,
    fixed_model: ReachabilityModel,
    *,
    change_gate_result: dict[str, Any] | None = None,
    measurement_provenance_result: dict[str, Any] | None = None,
    measurement_provenance_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete deterministic repository-owned client proof pack."""

    violated = _violated_check(engagement_result)
    path = violated.get("path")
    if not isinstance(path, list) or not path:
        raise ValueError("violated engagement check must contain a non-empty path")
    action_ids: list[str] = []
    for step in path:
        if not isinstance(step, dict) or not isinstance(step.get("actionId"), str):
            raise ValueError("violated path steps must contain actionId")
        action_ids.append(step["actionId"])

    for field in ("engagementId", "adapterId", "scopeId"):
        value = engagement_result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"engagement result {field} must be non-empty")

    proof = {
        "schemaVersion": 2,
        "schema": PROOF_SCHEMA,
        "sourceType": "repository-owned-local-demo",
        "engagementId": engagement_result["engagementId"],
        "adapterId": engagement_result["adapterId"],
        "scopeId": engagement_result["scopeId"],
        "expectedCoverage": _coverage(engagement_result),
        "violatedInvariantId": violated["invariantId"],
        "minimalPathActionIds": action_ids,
        "causalSecurityProof": build_causal_security_proof(
            prior_model,
            post_impact_model,
            fixed_model,
        ),
        "pilot": {
            "program": "recovery-design-partner-lab",
            "designPartnerCap": 5,
            "priceUsd": 750,
            "scopeBoundaries": 1,
            "deliveryTargetBusinessDays": 5,
            "asyncByDefault": True,
            "maxPrioritizedInvariants": 5,
            "retestPasses": 1,
        },
    }
    if change_gate_result is not None:
        proof = attach_change_gate_evidence(proof, change_gate_result)
    if (measurement_provenance_result is None) != (
        measurement_provenance_source is None
    ):
        raise ValueError(
            "measurement provenance result and source must be supplied together"
        )
    if measurement_provenance_result is not None:
        assert measurement_provenance_source is not None
        proof = attach_measurement_provenance_evidence(
            proof,
            measurement_provenance_result,
            measurement_provenance_source,
        )
    return proof
