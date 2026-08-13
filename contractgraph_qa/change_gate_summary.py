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


def _fix_replay_rows(models: list[object]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("id", "—"))
        replays = model.get("fixReplays")
        if not isinstance(replays, list):
            continue
        for replay in replays:
            if isinstance(replay, dict):
                rows.append((model_id, replay))
    return rows


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

    fix_rows = _fix_replay_rows(models)
    if fix_rows:
        lines.extend(
            [
                "",
                "## Exact historical fix replay",
                "",
                "| Model | Historical target | Replay status | Historical path | Blocked at | Alternate path reachable |",
                "|---|---|---|---|---|---|",
            ]
        )
        for model_id, item in fix_rows:
            replay = item.get("replay")
            replay_dict = replay if isinstance(replay, dict) else {}
            prior_path = replay_dict.get("priorPath")
            prior_path_dict = prior_path if isinstance(prior_path, dict) else None
            exact = replay_dict.get("exactReplay")
            exact_dict = exact if isinstance(exact, dict) else {}
            blocked_at = exact_dict.get("blockedAt")
            blocked_dict = blocked_at if isinstance(blocked_at, dict) else {}
            alternate = replay_dict.get("alternateReachability")
            alternate_dict = alternate if isinstance(alternate, dict) else {}
            alternate_reachable = alternate_dict.get("reachable")
            alternate_text = (
                "yes" if alternate_reachable is True else "no" if alternate_reachable is False else "—"
            )
            lines.append(
                "| {model_id} | {target} | {status} | {path_ids} | {blocked} | {alternate} |".format(
                    model_id=model_id,
                    target=item.get("targetCapability", "—"),
                    status=item.get("status", "—"),
                    path_ids=_path_transition_ids(prior_path_dict),
                    blocked=blocked_dict.get("reason", "—"),
                    alternate=alternate_text,
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
