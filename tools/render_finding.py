#!/usr/bin/env python3
"""Render a deterministic client-facing Markdown finding from ContractGraph-QA JSON evidence."""

from __future__ import annotations

import argparse
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
        fingerprint = evidence["manifestSha256"]
        _require(
            len(fingerprint) == 64 and all(char in "0123456789abcdef" for char in fingerprint),
            "evidence.manifestSha256 must be a lowercase SHA-256 hex digest",
        )

    if "exploredCandidates" in evidence:
        explored = evidence["exploredCandidates"]
        _require(
            isinstance(explored, int) and not isinstance(explored, bool) and explored >= 0,
            "evidence.exploredCandidates must be a non-negative integer",
        )
    if "notes" in evidence:
        _require_non_empty_string(evidence["notes"], "evidence.notes")


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Finding JSON file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write rendered Markdown")
    group.add_argument("--check", type=Path, help="Compare rendering with an existing Markdown file")
    args = parser.parse_args()

    rendered = render_markdown(load_finding(args.input))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        return 0

    expected = args.check.read_text(encoding="utf-8")
    if expected != rendered:
        raise SystemExit(f"rendered report differs from {args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
