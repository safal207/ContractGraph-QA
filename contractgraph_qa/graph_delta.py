"""Deterministic reachability graph delta for change / PR risk review."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.reachability import (
    ReachabilityModel,
    find_shortest_impact_path,
    impact_path_to_dict,
    reachability_model_sha256,
)


def _forbidden_paths(model: ReachabilityModel) -> dict[str, dict[str, object]]:
    """Return every forbidden capability reachable within the model bound."""

    paths: dict[str, dict[str, object]] = {}
    forbidden = sorted(item.id for item in model.capabilities if item.forbidden)
    for capability_id in forbidden:
        path = find_shortest_impact_path(
            initial_capabilities=model.initial_capabilities,
            target_capabilities=(capability_id,),
            capabilities=model.capabilities,
            transitions=model.transitions,
            violated_assumptions=model.violated_assumptions,
            assumptions=model.assumptions,
            max_depth=model.max_depth,
        )
        if path is not None:
            paths[capability_id] = impact_path_to_dict(path)
    return paths


def reachability_snapshot(model: ReachabilityModel) -> dict[str, object]:
    """Build a stable snapshot suitable for deterministic before/after comparison."""

    paths = _forbidden_paths(model)
    declared_boundaries = sorted(
        {edge.boundary for edge in model.transitions if edge.boundary is not None}
    )
    reachable_boundaries = sorted(
        {
            boundary
            for path in paths.values()
            for boundary in path["crossedBoundaries"]
            if isinstance(boundary, str)
        }
    )
    return {
        "modelSha256": reachability_model_sha256(model),
        "maxDepth": model.max_depth,
        "reachableForbiddenCapabilities": sorted(paths),
        "declaredControlBoundaries": declared_boundaries,
        "reachableForbiddenBoundaries": reachable_boundaries,
        "paths": {key: paths[key] for key in sorted(paths)},
    }


def compare_reachability_models(
    base_model: ReachabilityModel,
    head_model: ReachabilityModel,
) -> dict[str, Any]:
    """Compare old/new models and surface change-introduced causal risk."""

    base = reachability_snapshot(base_model)
    head = reachability_snapshot(head_model)

    base_forbidden = set(base["reachableForbiddenCapabilities"])
    head_forbidden = set(head["reachableForbiddenCapabilities"])
    base_boundaries = set(base["declaredControlBoundaries"])
    head_boundaries = set(head["declaredControlBoundaries"])
    base_reachable_boundaries = set(base["reachableForbiddenBoundaries"])
    head_reachable_boundaries = set(head["reachableForbiddenBoundaries"])

    newly_reachable = sorted(head_forbidden - base_forbidden)
    no_longer_reachable = sorted(base_forbidden - head_forbidden)
    removed_boundaries = sorted(base_boundaries - head_boundaries)
    added_boundaries = sorted(head_boundaries - base_boundaries)
    removed_reachable_boundaries = sorted(
        base_reachable_boundaries - head_reachable_boundaries
    )

    if newly_reachable:
        status = "risk_increase_detected"
    elif removed_boundaries:
        status = "control_boundary_change"
    elif no_longer_reachable:
        status = "risk_reduced"
    else:
        status = "no_material_delta"

    head_paths = head["paths"]
    introduced_paths = {
        capability_id: head_paths[capability_id]
        for capability_id in newly_reachable
    }

    return {
        "status": status,
        "baseModelSha256": base["modelSha256"],
        "headModelSha256": head["modelSha256"],
        "newlyReachableForbiddenCapabilities": newly_reachable,
        "noLongerReachableForbiddenCapabilities": no_longer_reachable,
        "removedDeclaredControlBoundaries": removed_boundaries,
        "addedDeclaredControlBoundaries": added_boundaries,
        "removedReachableForbiddenBoundaries": removed_reachable_boundaries,
        "introducedForbiddenPaths": introduced_paths,
        "base": base,
        "head": head,
    }
