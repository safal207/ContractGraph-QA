"""Deterministic replay of a prior forbidden capability path against a proposed fix."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.reachability import (
    CapabilityTransition,
    ImpactPath,
    ReachabilityModel,
    find_shortest_impact_path,
    impact_path_to_dict,
    reachability_model_sha256,
    run_reachability_model,
)


def _transition_semantics(edge: CapabilityTransition) -> dict[str, object]:
    return {
        "id": edge.id,
        "source": edge.source,
        "target": edge.target,
        "requiresViolations": list(edge.requires_violations),
        "invariantId": edge.invariant_id,
        "boundary": edge.boundary,
        "impact": edge.impact,
    }


def replay_impact_path(
    prior_path: ImpactPath,
    fixed_model: ReachabilityModel,
) -> dict[str, Any]:
    """Replay the exact prior transition sequence against ``fixed_model``.

    The replay is intentionally stricter than a fresh shortest-path search. Each
    prior transition id must still resolve to the same source/target edge and its
    current assumption guards must be satisfied by the fixed model. The result
    also performs a fresh search to detect alternate paths to the same forbidden
    target, preventing a blocked historical path from being mistaken for a
    complete fix when another route remains reachable.
    """

    capability_by_id = {item.id: item for item in fixed_model.capabilities}
    transition_by_id = {item.id: item for item in fixed_model.transitions}
    violations = set(fixed_model.violated_assumptions)

    current = prior_path.initial_capability
    steps: list[dict[str, object]] = []
    blocked_at: dict[str, object] | None = None

    if current not in capability_by_id:
        blocked_at = {
            "step": 0,
            "reason": "initial_capability_missing",
            "capabilityId": current,
        }
    else:
        for index, prior_edge in enumerate(prior_path.transitions, start=1):
            fixed_edge = transition_by_id.get(prior_edge.id)
            if fixed_edge is None:
                blocked_at = {
                    "step": index,
                    "reason": "transition_missing",
                    "transitionId": prior_edge.id,
                }
                break

            if fixed_edge.source != prior_edge.source or fixed_edge.target != prior_edge.target:
                blocked_at = {
                    "step": index,
                    "reason": "transition_rewired",
                    "transitionId": prior_edge.id,
                    "priorSource": prior_edge.source,
                    "priorTarget": prior_edge.target,
                    "fixedSource": fixed_edge.source,
                    "fixedTarget": fixed_edge.target,
                }
                break

            if fixed_edge.source != current:
                blocked_at = {
                    "step": index,
                    "reason": "path_not_contiguous_in_fixed_model",
                    "transitionId": prior_edge.id,
                    "expectedSource": current,
                    "actualSource": fixed_edge.source,
                }
                break

            missing_violations = sorted(set(fixed_edge.requires_violations) - violations)
            if missing_violations:
                blocked_at = {
                    "step": index,
                    "reason": "assumption_guard_restored",
                    "transitionId": prior_edge.id,
                    "missingViolatedAssumptions": missing_violations,
                }
                break

            steps.append(
                {
                    "step": index,
                    "transition": _transition_semantics(fixed_edge),
                    "status": "traversed",
                }
            )
            current = fixed_edge.target

    target = prior_path.target_capability
    target_capability = capability_by_id.get(target)
    exact_path_reaches_target = blocked_at is None and current == target
    exact_path_reaches_forbidden = bool(
        exact_path_reaches_target
        and target_capability is not None
        and target_capability.forbidden
    )

    alternate_path = None
    if target_capability is not None and target_capability.forbidden:
        alternate = find_shortest_impact_path(
            initial_capabilities=fixed_model.initial_capabilities,
            target_capabilities=(target,),
            capabilities=fixed_model.capabilities,
            transitions=fixed_model.transitions,
            violated_assumptions=fixed_model.violated_assumptions,
            assumptions=fixed_model.assumptions,
            max_depth=fixed_model.max_depth,
        )
        if alternate is not None:
            alternate_path = impact_path_to_dict(alternate)

    if exact_path_reaches_forbidden:
        status = "failing_path_persists"
    elif alternate_path is not None:
        status = "path_eliminated_but_risk_remains"
    else:
        status = "fix_verified"

    return {
        "status": status,
        "fixedModelSha256": reachability_model_sha256(fixed_model),
        "priorPath": impact_path_to_dict(prior_path),
        "exactReplay": {
            "reachedTargetCapability": exact_path_reaches_target,
            "reachedForbiddenCapability": exact_path_reaches_forbidden,
            "blockedAt": blocked_at,
            "steps": steps,
        },
        "alternateReachability": {
            "targetCapability": target,
            "stillForbidden": bool(target_capability is not None and target_capability.forbidden),
            "reachable": alternate_path is not None,
            "path": alternate_path,
        },
    }


def replay_prior_model_path(
    prior_model: ReachabilityModel,
    fixed_model: ReachabilityModel,
) -> dict[str, Any]:
    """Select the prior model's deterministic failing path and replay it after a fix."""

    prior_result = run_reachability_model(prior_model)
    if prior_result["status"] != "reachable":
        raise ValueError("prior model does not contain a reachable target path to replay")

    prior_path = find_shortest_impact_path(
        initial_capabilities=prior_model.initial_capabilities,
        target_capabilities=prior_model.target_capabilities,
        capabilities=prior_model.capabilities,
        transitions=prior_model.transitions,
        violated_assumptions=prior_model.violated_assumptions,
        assumptions=prior_model.assumptions,
        max_depth=prior_model.max_depth,
    )
    if prior_path is None:  # defensive consistency boundary
        raise ValueError("prior reachable result has no deterministic impact path")

    result = replay_impact_path(prior_path, fixed_model)
    result["priorModelSha256"] = reachability_model_sha256(prior_model)
    return result
