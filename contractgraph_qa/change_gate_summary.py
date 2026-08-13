"""Deterministic human-readable summary for causal security change-gate results."""

from __future__ import annotations

from typing import Any


def _text_list(values: object) -> str:
    if not isinstance(values, list):
        return "—"
    items = [str(value) for value in values if isinstance(value, str) and value]
    return ", ".join(items) if items else "—"


def _introduced_path(delta: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    paths = delta.get("introducedForbiddenPaths")
    if not isinstance(paths, dict) or not paths:
        return "—", None
    target = sorted(str(key) for key in paths)[0]
    path = paths.get(target)
    return target, path if isinstance(path, dict) else None


def _definition_drift_target(delta: dict[str, Any]) -> str:
    changes = delta.get("forbiddenDefinitionChanges")
    if not isinstance(changes, dict):
        return "—"
    removed = changes.get("removedFormerlyForbiddenCapabilities")
    reclassified = changes.get("forbiddenToAllowedCapabilities")
    candidates: list[str] = []
    if isinstance(removed, list):
        candidates.extend(str(value) for value in removed if isinstance(value, str))
    if isinstance(reclassified, list):
        candidates.extend(str(value) for value in reclassified if isinstance(value, str))
    return ", ".join(sorted(set(candidates))) if candidates else "—"


def _path_transition_ids(path: dict[str, Any] | None) -> str:
    if not path:
        return "—"
    transitions = path.get("transitions")
    if not isinstance(transitions, list):
        return "—"
    ids = [
        item.get("id")
        for item in transitions
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return " → ".join(ids) if ids else "—"


def render_change_gate_summary(result: dict[str, Any]) -> str:
    """Render a concise deterministic Markdown summary from machine gate output."""

    status = result.get("status", "blocked")
    base_sha = result.get("baseCommitSha", "unknown")
    head_sha = result.get("headCommitSha", "unknown")
    models = result.get("models")
    if not isinstance(models, list):
        models = []

    lines = [
        "# Causal Security Change Gate",
        "",
        f"**Status:** `{status}`",
        "",
        f"- Base commit: `{base_sha}`",
        f"- Head commit: `{head_sha}`",
        "",
        "| Model | Status | Gate reasons | Target | Invariant | Boundary | Exact introduced path |",
        "|---|---|---|---|---|---|---|",
    ]

    for model in models:
        if not isinstance(model, dict):
            continue
        delta = model.get("delta")
        delta_dict = delta if isinstance(delta, dict) else {}
        target, path = _introduced_path(delta_dict)
        if target == "—":
            target = _definition_drift_target(delta_dict)

        invariant = _text_list(path.get("invariantIds") if path else None)
        boundary = _text_list(path.get("crossedBoundaries") if path else None)
        if boundary == "—":
            removed_boundaries = delta_dict.get("removedDeclaredControlBoundaries")
            boundary = _text_list(removed_boundaries)

        lines.append(
            "| {model_id} | {status} | {reasons} | {target} | {invariant} | {boundary} | {path_ids} |".format(
                model_id=model.get("id", "—"),
                status=model.get("status", "blocked"),
                reasons=_text_list(model.get("gateReasons")),
                target=target,
                invariant=invariant,
                boundary=boundary,
                path_ids=_path_transition_ids(path),
            )
        )

    if not models:
        error = result.get("error")
        if isinstance(error, str) and error:
            lines.extend(["", f"**Gate error:** `{error}`"])

    lines.extend(
        [
            "",
            "> `pass` and `review` are bounded change-review results, not a production safety certification.",
        ]
    )
    return "\n".join(lines) + "\n"
