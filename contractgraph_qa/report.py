"""Deterministic client-facing Markdown rendering for ContractGraph-QA findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEVERITIES = {"critical", "high", "medium", "low", "info"}
REQUIRED_TOP_LEVEL = {
    "id",
    "title",
    "severity",
    "contract",
    "network",
    "summary",
    "invariant",
    "minimalFailingPath",
    "impact",
    "recommendation",
    "evidence",
}
REQUIRED_TEXT_FIELDS = ("id", "title", "contract", "network", "summary", "impact", "recommendation")
REQUIRED_STEP_TEXT_FIELDS = ("actor", "action", "preState", "postState", "effect")
OPTIONAL_PROVENANCE_FIELDS = (
    "adapterId",
    "scopeId",
    "authorizationReference",
    "target",
    "manifestSha256",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_non_empty_string(value: Any, field: str) -> None:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")


def _require_sha256(value: Any, field: str) -> None:
    _require_non_empty_string(value, field)
    _require(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value),
        f"{field} must be a lowercase SHA-256 hex digest",
    )


def _require_string_array(value: Any, field: str) -> list[str]:
    _require(isinstance(value, list), f"{field} must be an array")
    for index, item in enumerate(value):
        _require_non_empty_string(item, f"{field}[{index}]")
    _require(len(value) == len(set(value)), f"{field} must contain unique values")
    return value


def _validate_reachability_evidence(
    reachability: Any,
    finding: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    """Validate the optional causal reachability block before rendering it."""

    _require(isinstance(reachability, dict), "evidence.reachability must be an object")
    for field in (
        "artifact",
        "modelArtifact",
        "boundManifestSha256",
        "boundInvariantId",
        "status",
        "modelSha256",
    ):
        _require_non_empty_string(reachability.get(field), f"evidence.reachability.{field}")

    _require_sha256(
        reachability["boundManifestSha256"],
        "evidence.reachability.boundManifestSha256",
    )
    _require_sha256(reachability["modelSha256"], "evidence.reachability.modelSha256")
    _require(
        reachability["status"] == "reachable",
        "evidence.reachability.status must be reachable for a finding report",
    )
    _require(
        reachability["boundInvariantId"] == finding["invariant"]["id"],
        "evidence.reachability.boundInvariantId must match finding invariant",
    )
    if "manifestSha256" in evidence:
        _require(
            reachability["boundManifestSha256"] == evidence["manifestSha256"],
            "evidence.reachability.boundManifestSha256 must match finding provenance",
        )

    max_depth = reachability.get("maxDepth")
    _require(
        isinstance(max_depth, int) and not isinstance(max_depth, bool) and max_depth >= 0,
        "evidence.reachability.maxDepth must be a non-negative integer",
    )
    declared_violations = _require_string_array(
        reachability.get("violatedAssumptions"),
        "evidence.reachability.violatedAssumptions",
    )
    targets = _require_string_array(
        reachability.get("targetCapabilities"),
        "evidence.reachability.targetCapabilities",
    )

    path = reachability.get("path")
    _require(isinstance(path, dict), "evidence.reachability.path must be an object")
    for field in ("initialCapability", "targetCapability"):
        _require_non_empty_string(path.get(field), f"evidence.reachability.path.{field}")
    path_violations = _require_string_array(
        path.get("violatedAssumptions"),
        "evidence.reachability.path.violatedAssumptions",
    )
    invariant_ids = _require_string_array(
        path.get("invariantIds"),
        "evidence.reachability.path.invariantIds",
    )
    _require_string_array(
        path.get("crossedBoundaries"),
        "evidence.reachability.path.crossedBoundaries",
    )
    if path.get("impact") is not None:
        _require_non_empty_string(path["impact"], "evidence.reachability.path.impact")

    _require(
        sorted(path_violations) == sorted(declared_violations),
        "evidence.reachability path violations must match declared violations",
    )
    _require(
        path["targetCapability"] in targets,
        "evidence.reachability path target must be a declared target capability",
    )
    _require(
        reachability["boundInvariantId"] in invariant_ids,
        "evidence.reachability path must contain the bound finding invariant",
    )

    transitions = path.get("transitions")
    _require(isinstance(transitions, list), "evidence.reachability.path.transitions must be an array")
    current = path["initialCapability"]
    transition_ids: set[str] = set()
    for index, transition in enumerate(transitions):
        field = f"evidence.reachability.path.transitions[{index}]"
        _require(isinstance(transition, dict), f"{field} must be an object")
        for key in ("id", "source", "target"):
            _require_non_empty_string(transition.get(key), f"{field}.{key}")
        _require(transition["id"] not in transition_ids, f"{field}.id must be unique")
        transition_ids.add(transition["id"])
        _require(
            transition["source"] == current,
            "evidence.reachability capability transitions must form a contiguous path",
        )
        required = _require_string_array(
            transition.get("requiresViolations", []),
            f"{field}.requiresViolations",
        )
        _require(
            set(required).issubset(set(declared_violations)),
            f"{field}.requiresViolations must be declared as violated",
        )
        for key in ("invariantId", "boundary", "impact"):
            if transition.get(key) is not None:
                _require_non_empty_string(transition[key], f"{field}.{key}")
        current = transition["target"]
    _require(
        current == path["targetCapability"],
        "evidence.reachability capability path must terminate at targetCapability",
    )


def validate_finding(data: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL - data.keys())
    _require(not missing, f"missing required fields: {', '.join(missing)}")

    for field in REQUIRED_TEXT_FIELDS:
        _require_non_empty_string(data[field], field)

    severity = data["severity"]
    _require_non_empty_string(severity, "severity")
    _require(severity.lower() in SEVERITIES, "invalid severity")

    invariant = data["invariant"]
    _require(isinstance(invariant, dict), "invariant must be an object")
    _require_non_empty_string(invariant.get("id"), "invariant.id")
    _require_non_empty_string(invariant.get("expression"), "invariant.expression")

    path = data["minimalFailingPath"]
    _require(isinstance(path, list) and len(path) > 0, "minimalFailingPath must be non-empty")

    for index, step in enumerate(path, start=1):
        _require(isinstance(step, dict), f"path step {index} must be an object")
        _require("step" in step, f"path step {index} missing step")
        _require(
            isinstance(step["step"], int) and not isinstance(step["step"], bool),
            f"path step {index} step must be an integer",
        )
        _require(step["step"] == index, "path steps must be contiguous and 1-based")

        for key in REQUIRED_STEP_TEXT_FIELDS:
            _require(key in step, f"path step {index} missing {key}")
            _require_non_empty_string(step[key], f"path step {index}.{key}")

    evidence = data["evidence"]
    _require(isinstance(evidence, dict), "evidence must be an object")
    _require_non_empty_string(evidence.get("replay"), "evidence.replay")
    _require_non_empty_string(evidence.get("authorization"), "evidence.authorization")

    for field in OPTIONAL_PROVENANCE_FIELDS:
        if field in evidence:
            _require_non_empty_string(evidence[field], f"evidence.{field}")

    if "manifestSha256" in evidence:
        _require_sha256(evidence["manifestSha256"], "evidence.manifestSha256")

    if "exploredCandidates" in evidence:
        explored = evidence["exploredCandidates"]
        _require(
            isinstance(explored, int) and not isinstance(explored, bool) and explored >= 0,
            "evidence.exploredCandidates must be a non-negative integer",
        )
    if "notes" in evidence:
        _require_non_empty_string(evidence["notes"], "evidence.notes")
    if "reachability" in evidence:
        _validate_reachability_evidence(evidence["reachability"], data, evidence)


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none declared"


def _render_causal_security_path(lines: list[str], reachability: dict[str, Any]) -> None:
    path = reachability["path"]
    transitions = path["transitions"]
    capability_chain = [path["initialCapability"], *[item["target"] for item in transitions]]

    lines.extend(
        [
            "",
            "## Causal security path",
            "",
            "This bounded graph explains how the observed finding is connected to a reachable forbidden capability.",
            "",
            f"- **Reachability status:** `{reachability['status']}`",
            f"- **Bound invariant:** `{reachability['boundInvariantId']}`",
            f"- **Model SHA-256:** `{reachability['modelSha256']}`",
            f"- **Broken assumptions:** {_code_list(reachability['violatedAssumptions'])}",
            "- **Capability path:** " + " → ".join(f"`{item}`" for item in capability_chain),
            f"- **Crossed boundaries:** {_code_list(path['crossedBoundaries'])}",
        ]
    )
    if path.get("impact"):
        lines.append(f"- **Reachability impact:** {path['impact']}")

    lines.extend(
        [
            "",
            "| # | Capability transition | From | To | Invariant | Boundary | Requires broken assumptions |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for index, transition in enumerate(transitions, start=1):
        invariant = transition.get("invariantId") or "—"
        boundary = transition.get("boundary") or "—"
        requires = transition.get("requiresViolations") or []
        lines.append(
            "| {index} | `{transition_id}` | `{source}` | `{target}` | `{invariant}` | `{boundary}` | {requires} |".format(
                index=index,
                transition_id=_escape_table(transition["id"]),
                source=_escape_table(transition["source"]),
                target=_escape_table(transition["target"]),
                invariant=_escape_table(invariant),
                boundary=_escape_table(boundary),
                requires=_escape_table(_code_list(requires)),
            )
        )

    lines.extend(
        [
            "",
            "The path is evidence about the declared model and search bound; it is not an exhaustive claim that no other causal path exists.",
        ]
    )


def render_markdown(data: dict[str, Any]) -> str:
    validate_finding(data)

    severity = data["severity"].upper()
    invariant = data["invariant"]
    evidence = data["evidence"]

    lines = [
        f"# {data['id']} — {data['title']}",
        "",
        f"**Severity:** {severity}  ",
        f"**Contract:** `{data['contract']}`  ",
        f"**Network / environment:** `{data['network']}`",
        "",
        "## Executive summary",
        "",
        data["summary"].strip(),
        "",
        "## Violated invariant",
        "",
        f"**{invariant['id']}**",
        "",
        "```text",
        invariant["expression"],
        "```",
        "",
        "## Minimal failing path",
        "",
        "| Step | Actor | Action | Pre-state | Post-state | Effect |",
        "|---:|---|---|---|---|---|",
    ]

    for step in data["minimalFailingPath"]:
        lines.append(
            "| {step} | {actor} | `{action}` | `{pre}` | `{post}` | {effect} |".format(
                step=step["step"],
                actor=_escape_table(step["actor"]),
                action=_escape_table(step["action"]),
                pre=_escape_table(step["preState"]),
                post=_escape_table(step["postState"]),
                effect=_escape_table(step["effect"]),
            )
        )

    if "reachability" in evidence:
        _render_causal_security_path(lines, evidence["reachability"])

    lines.extend(
        [
            "",
            "## Impact",
            "",
            data["impact"].strip(),
            "",
            "## Evidence and replay",
            "",
            f"- **Authorization:** {evidence['authorization']}",
            f"- **Replay:** `{evidence['replay']}`",
        ]
    )

    provenance_labels = {
        "adapterId": "Adapter ID",
        "scopeId": "Scope ID",
        "authorizationReference": "Authorization reference",
        "target": "Target",
        "manifestSha256": "Manifest SHA-256",
    }
    for field in OPTIONAL_PROVENANCE_FIELDS:
        if field in evidence:
            lines.append(f"- **{provenance_labels[field]}:** `{evidence[field]}`")

    if "reachability" in evidence:
        reachability = evidence["reachability"]
        lines.extend(
            [
                f"- **Reachability artifact:** `{reachability['artifact']}`",
                f"- **Reachability model artifact:** `{reachability['modelArtifact']}`",
            ]
        )
    if "exploredCandidates" in evidence:
        lines.append(f"- **Explored candidates:** {evidence['exploredCandidates']}")
    if evidence.get("notes"):
        lines.append(f"- **Notes:** {evidence['notes']}")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            data["recommendation"].strip(),
            "",
            "## Retest checklist",
            "",
            "- [ ] Apply the proposed fix in the authorized target.",
            "- [ ] Replay the exact minimal failing path.",
            "- [ ] Confirm the violated invariant now holds after every accepted transition.",
            "- [ ] Keep the path as a regression test.",
            "",
            "## Scope note",
            "",
            "This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.",
            "",
        ]
    )

    return "\n".join(lines)


def load_finding(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _require(isinstance(data, dict), "finding input must be a JSON object")
    return data
