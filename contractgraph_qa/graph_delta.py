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
    capability_classification = {
        item.id: {"forbidden": item.forbidden, "description": item.description}
        for item in sorted(model.capabilities, key=lambda item: item.id)
    }
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
        "capabilityClassification": capability_classification,
        "declaredForbiddenCapabilities": sorted(
            capability_id
            for capability_id, value in capability_classification.items()
            if value["forbidden"] is True
        ),
        "reachableForbiddenCapabilities": sorted(paths),
        "declaredControlBoundaries": declared_boundaries,
        "reachableForbiddenBoundaries": reachable_boundaries,
        "paths": {key: paths[key] for key in sorted(paths)},
    }


def _forbidden_definition_changes(
    base: dict[str, object],
    head: dict[str, object],
) -> dict[str, list[str]]:
    """Detect attempts to erase a historical forbidden target by definition."""

    base_classification = base["capabilityClassification"]
    head_classification = head["capabilityClassification"]
    assert isinstance(base_classification, dict)
    assert isinstance(head_classification, dict)

    base_forbidden = set(base["declaredForbiddenCapabilities"])
    head_ids = set(head_classification)

    removed = sorted(base_forbidden - head_ids)
    reclassified_allowed = sorted(
        capability_id
        for capability_id in base_forbidden & head_ids
        if head_classification[capability_id]["forbidden"] is not True
    )
    newly_declared_forbidden = sorted(
        set(head["declaredForbiddenCapabilities"])
        - set(base["declaredForbiddenCapabilities"])
    )
    return {
        "removedFormerlyForbiddenCapabilities": removed,
        "forbiddenToAllowedCapabilities": reclassified_allowed,
        "newlyDeclaredForbiddenCapabilities": newly_declared_forbidden,
    }


def compare_reachability_models(
    base_model: ReachabilityModel,
    head_model: ReachabilityModel,
) -> dict[str, Any]:
    """Compare old/new models and surface change-introduced causal risk.

    A PR is not allowed to manufacture a risk reduction merely by deleting a
    historical forbidden capability or relabeling it as allowed. Definition
    drift therefore uses the existing ``risk_increase_detected`` gate status,
    with ``gateReasons`` identifying the specific fail-closed condition.
    """

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
    definition_changes = _forbidden_definition_changes(base, head)
    forbidden_definition_changed = bool(
        definition_changes["removedFormerlyForbiddenCapabilities"]
        or definition_changes["forbiddenToAllowedCapabilities"]
    )

    gate_reasons: list[str] = []
    if newly_reachable:
        gate_reasons.append("new_forbidden_reachability")
    if forbidden_definition_changed:
        gate_reasons.append("forbidden_definition_changed")

    if gate_reasons:
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
        "gateReasons": gate_reasons,
        "baseModelSha256": base["modelSha256"],
        "headModelSha256": head["modelSha256"],
        "newlyReachableForbiddenCapabilities": newly_reachable,
        "noLongerReachableForbiddenCapabilities": no_longer_reachable,
        "removedDeclaredControlBoundaries": removed_boundaries,
        "addedDeclaredControlBoundaries": added_boundaries,
        "removedReachableForbiddenBoundaries": removed_reachable_boundaries,
        "forbiddenDefinitionChanges": definition_changes,
        "introducedForbiddenPaths": introduced_paths,
        "base": base,
        "head": head,
    }
