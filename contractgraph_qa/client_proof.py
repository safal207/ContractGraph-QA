"""Deterministic client proof-pack assembly for repository-owned demos."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.path_replay import replay_prior_model_path
from contractgraph_qa.postimpact import PostImpactModel, run_post_impact_model
from contractgraph_qa.reachability import ReachabilityModel, run_reachability_model


PROOF_SCHEMA = "cgqa.client-proof.v2"
CAUSAL_PROOF_SCHEMA = "cgqa.client-causal-proof.v1"


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

    return {
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
            "priceUsd": 200,
            "maxPrioritizedInvariants": 5,
            "retestPasses": 1,
        },
    }
