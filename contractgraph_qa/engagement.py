"""Multi-invariant engagement aggregation, reporting, and evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from contractgraph_qa import __version__
from contractgraph_qa.finding import (
    STEP_KEYS,
    canonical_json,
    export_finding,
    load_json_object,
    manifest_sha256,
    validate_manifest,
)

STATUSES = {"violated", "not_found_within_bound", "inconclusive"}
ENGAGEMENT_RESULT_KEYS = {
    "schemaVersion",
    "engagementId",
    "adapterId",
    "scopeId",
    "manifestSha256",
    "searchRunId",
    "replay",
    "checks",
}
CHECK_KEYS = {
    "invariantId",
    "status",
    "findingId",
    "exploredCandidates",
    "notes",
    "path",
}
BUNDLE_KEYS = {
    "bundleVersion",
    "tool",
    "engagementId",
    "manifestSha256",
    "searchRunId",
    "findingIds",
    "artifacts",
}
TOOL_KEYS = {"name", "version"}
ARTIFACT_KEYS = {"sha256", "bytes"}
SAFE_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_BUNDLE_ENTRY_BYTES = 16 * 1024 * 1024
BASE_BUNDLE_FILES = (
    "manifest.json",
    "engagement-result.json",
    "engagement.json",
    "engagement.md",
)


class EngagementError(ValueError):
    """Expected engagement validation or verification failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngagementError(message)


def _non_blank(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _non_negative_int(value: Any, field: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{field} must be a non-negative integer",
    )
    return value


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _safe_artifact_id(value: Any, field: str) -> str:
    text = _non_blank(value, field)
    _require(bool(SAFE_ARTIFACT_ID.fullmatch(text)), f"{field} contains unsafe artifact characters")
    return text


def _validate_step(step: Any, index: int, field: str) -> None:
    _require(isinstance(step, dict), f"{field}[{index}] must be an object")
    _reject_extra_keys(step, STEP_KEYS, f"{field}[{index}]")
    for name in ("actionId", "preState", "postState", "effect"):
        _non_blank(step.get(name), f"{field}[{index}].{name}")
    if "parameter" in step:
        parameter = step["parameter"]
        _require(
            isinstance(parameter, (str, int)) and not isinstance(parameter, bool),
            f"{field}[{index}].parameter must be a string or integer",
        )


def validate_engagement_result(result: dict[str, Any]) -> None:
    _reject_extra_keys(result, ENGAGEMENT_RESULT_KEYS, "engagementResult")
    _require(result.get("schemaVersion") == 1, "engagementResult.schemaVersion must equal 1")
    _safe_artifact_id(result.get("engagementId"), "engagementResult.engagementId")
    for field in ("adapterId", "scopeId", "searchRunId", "replay"):
        _non_blank(result.get(field), f"engagementResult.{field}")
    fingerprint = _non_blank(result.get("manifestSha256"), "engagementResult.manifestSha256")
    _require(
        bool(SHA256_HEX.fullmatch(fingerprint)),
        "engagementResult.manifestSha256 must be lowercase SHA-256 hex",
    )

    checks = result.get("checks")
    _require(isinstance(checks, list) and checks, "engagementResult.checks must be non-empty")
    seen_invariants: set[str] = set()
    seen_findings: set[str] = set()
    for index, check in enumerate(checks):
        _require(isinstance(check, dict), f"engagementResult.checks[{index}] must be an object")
        _reject_extra_keys(check, CHECK_KEYS, f"engagementResult.checks[{index}]")
        invariant_id = _non_blank(
            check.get("invariantId"), f"engagementResult.checks[{index}].invariantId"
        )
        _require(
            invariant_id not in seen_invariants,
            f"duplicate engagement invariant check: {invariant_id}",
        )
        seen_invariants.add(invariant_id)

        status = _non_blank(check.get("status"), f"engagementResult.checks[{index}].status")
        _require(status in STATUSES, f"invalid engagement status for invariant {invariant_id}")
        _non_negative_int(
            check.get("exploredCandidates"),
            f"engagementResult.checks[{index}].exploredCandidates",
        )
        _non_blank(check.get("notes"), f"engagementResult.checks[{index}].notes")

        if status == "violated":
            finding_id = _safe_artifact_id(
                check.get("findingId"), f"engagementResult.checks[{index}].findingId"
            )
            _require(finding_id not in seen_findings, f"duplicate finding id: {finding_id}")
            seen_findings.add(finding_id)
            path = check.get("path")
            _require(
                isinstance(path, list) and path,
                f"violated invariant {invariant_id} requires a non-empty path",
            )
            for step_index, step in enumerate(path):
                _validate_step(step, step_index, f"engagementResult.checks[{index}].path")
        else:
            _require(
                "findingId" not in check,
                f"{status} invariant {invariant_id} must not declare findingId",
            )
            _require(
                "path" not in check,
                f"{status} invariant {invariant_id} must not declare a failing path",
            )


def _manifest_invariants(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in manifest["invariants"]}


def _single_result(result: dict[str, Any], check: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapterId": result["adapterId"],
        "scopeId": result["scopeId"],
        "manifestSha256": result["manifestSha256"],
        "findingId": check["findingId"],
        "invariantId": check["invariantId"],
        "replay": result["replay"],
        "exploredCandidates": check["exploredCandidates"],
        "notes": check["notes"],
        "path": check["path"],
    }


def build_engagement(
    manifest: dict[str, Any], result: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_manifest(manifest)
    validate_engagement_result(result)

    _require(
        result["adapterId"] == manifest["adapterId"],
        "engagement adapterId does not match manifest",
    )
    _require(
        result["scopeId"] == manifest["scope"]["scopeId"],
        "engagement scopeId does not match manifest",
    )
    expected_fingerprint = manifest_sha256(manifest)
    _require(
        result["manifestSha256"] == expected_fingerprint,
        "engagement manifestSha256 does not match manifest",
    )

    invariants = _manifest_invariants(manifest)
    checked_ids = {check["invariantId"] for check in result["checks"]}
    declared_ids = set(invariants)
    missing = sorted(declared_ids - checked_ids)
    unknown = sorted(checked_ids - declared_ids)
    _require(not missing, f"engagement omitted declared invariants: {', '.join(missing)}")
    _require(not unknown, f"engagement contains unknown invariants: {', '.join(unknown)}")

    findings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    counts = {status: 0 for status in STATUSES}
    for check in result["checks"]:
        invariant = invariants[check["invariantId"]]
        status = check["status"]
        counts[status] += 1
        row: dict[str, Any] = {
            "invariantId": check["invariantId"],
            "title": invariant["title"],
            "severity": invariant["severity"],
            "status": status,
            "exploredCandidates": check["exploredCandidates"],
            "notes": check["notes"],
        }
        if status == "violated":
            finding = export_finding(manifest, _single_result(result, check))
            findings.append(finding)
            row["findingId"] = finding["id"]
            row["pathLength"] = len(finding["minimalFailingPath"])
        checks.append(row)

    engagement = {
        "schemaVersion": 1,
        "engagementId": result["engagementId"],
        "contract": manifest["contract"],
        "network": manifest["network"],
        "adapterId": manifest["adapterId"],
        "scopeId": manifest["scope"]["scopeId"],
        "manifestSha256": expected_fingerprint,
        "searchRunId": result["searchRunId"],
        "replay": result["replay"],
        "scope": {
            "authorization": manifest["scope"]["authorization"],
            "authorizationReference": manifest["scope"]["authorizationReference"],
            "target": manifest["scope"]["target"],
        },
        "coverage": {
            "declaredInvariants": len(declared_ids),
            "checkedInvariants": len(checks),
            "violated": counts["violated"],
            "notFoundWithinBound": counts["not_found_within_bound"],
            "inconclusive": counts["inconclusive"],
        },
        "checks": checks,
    }
    return engagement, findings


def render_engagement_markdown(engagement: dict[str, Any]) -> str:
    coverage = engagement["coverage"]
    lines = [
        f"# {engagement['engagementId']} — ContractGraph-QA engagement",
        "",
        f"**Contract:** `{engagement['contract']}`  ",
        f"**Network / environment:** `{engagement['network']}`  ",
        f"**Adapter:** `{engagement['adapterId']}`  ",
        f"**Scope:** `{engagement['scopeId']}`  ",
        f"**Search run:** `{engagement['searchRunId']}`  ",
        f"**Manifest SHA-256:** `{engagement['manifestSha256']}`",
        "",
        "## Coverage summary",
        "",
        f"- Declared invariants: **{coverage['declaredInvariants']}**",
        f"- Checked invariants: **{coverage['checkedInvariants']}**",
        f"- Violated: **{coverage['violated']}**",
        f"- No violation found within bound: **{coverage['notFoundWithinBound']}**",
        f"- Inconclusive: **{coverage['inconclusive']}**",
        "",
        "## Invariant checks",
        "",
        "| Invariant | Severity | Status | Candidates | Finding | Notes |",
        "|---|---|---|---:|---|---|",
    ]
    for check in engagement["checks"]:
        finding = check.get("findingId", "—")
        notes = str(check["notes"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{check['invariantId']}` | {check['severity'].upper()} | `{check['status']}` | "
            f"{check['exploredCandidates']} | {finding} | {notes} |"
        )

    lines.extend(
        [
            "",
            "## Replay",
            "",
            f"`{engagement['replay']}`",
            "",
            "## Authorization",
            "",
            engagement["scope"]["authorization"],
            "",
            f"Reference: `{engagement['scope']['authorizationReference']}`  ",
            f"Target: `{engagement['scope']['target']}`",
            "",
            "## Interpretation boundary",
            "",
            "`not_found_within_bound` means only that no violation was found inside the declared bounded model. "
            "`inconclusive` means the run cannot support a clean conclusion. Neither status is a claim that the contract is secure.",
            "",
        ]
    )
    return "\n".join(lines)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def _finding_payloads(findings: list[dict[str, Any]]) -> dict[str, bytes]:
    from contractgraph_qa.report import render_markdown

    payloads: dict[str, bytes] = {}
    for finding in sorted(findings, key=lambda item: item["id"]):
        finding_id = _safe_artifact_id(finding["id"], "finding.id")
        payloads[f"findings/{finding_id}.finding.json"] = canonical_json(finding).encode("utf-8")
        payloads[f"findings/{finding_id}.md"] = render_markdown(finding).encode("utf-8")
    return payloads


def _bundle_manifest(
    engagement: dict[str, Any],
    payloads: dict[str, bytes],
    finding_ids: list[str],
    tool_version: str,
) -> dict[str, Any]:
    return {
        "bundleVersion": 2,
        "tool": {"name": "contractgraph-qa", "version": tool_version},
        "engagementId": engagement["engagementId"],
        "manifestSha256": engagement["manifestSha256"],
        "searchRunId": engagement["searchRunId"],
        "findingIds": sorted(finding_ids),
        "artifacts": {
            name: {"sha256": _sha256_bytes(payload), "bytes": len(payload)}
            for name, payload in payloads.items()
        },
    }


def write_engagement_bundle(
    manifest_path: Path,
    result_path: Path,
    output_dir: Path,
    bundle_path: Path,
) -> dict[str, Any]:
    manifest = load_json_object(manifest_path, "manifest")
    result = load_json_object(result_path, "engagementResult")
    engagement, findings = build_engagement(manifest, result)

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {
        "manifest.json": manifest_path.read_bytes(),
        "engagement-result.json": result_path.read_bytes(),
        "engagement.json": canonical_json(engagement).encode("utf-8"),
        "engagement.md": render_engagement_markdown(engagement).encode("utf-8"),
    }
    payloads.update(_finding_payloads(findings))
    for name, payload in payloads.items():
        _require(len(payload) <= MAX_BUNDLE_ENTRY_BYTES, f"engagement artifact too large: {name}")

    (output_dir / "engagement.json").write_bytes(payloads["engagement.json"])
    (output_dir / "engagement.md").write_bytes(payloads["engagement.md"])
    findings_dir = output_dir / "findings"
    findings_dir.mkdir(exist_ok=True)
    for name, payload in payloads.items():
        if name.startswith("findings/"):
            (output_dir / name).write_bytes(payload)

    finding_ids = [finding["id"] for finding in findings]
    bundle_manifest = _bundle_manifest(engagement, payloads, finding_ids, __version__)
    bundle_payload = canonical_json(bundle_manifest).encode("utf-8")
    ordered_names = list(BASE_BUNDLE_FILES) + sorted(
        name for name in payloads if name.startswith("findings/")
    )
    ordered_names.append("bundle.json")

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "w") as archive:
        for name in ordered_names:
            payload = bundle_payload if name == "bundle.json" else payloads[name]
            archive.writestr(_zip_entry(name), payload)

    verification = verify_engagement_bundle(bundle_path)
    return {
        "ok": True,
        "engagementId": engagement["engagementId"],
        "coverage": engagement["coverage"],
        "findingIds": sorted(finding_ids),
        "outputDir": str(output_dir),
        "bundle": str(bundle_path),
        "bundleSha256": verification["bundleSha256"],
    }


def _validate_archive_name(name: str) -> None:
    pure = PurePosixPath(name)
    _require(not pure.is_absolute(), f"absolute bundle entry is not allowed: {name}")
    _require(".." not in pure.parts, f"parent traversal bundle entry is not allowed: {name}")
    _require("\\" not in name, f"backslash bundle entry is not allowed: {name}")


def _bundle_tool_version(bundle_manifest: dict[str, Any]) -> str:
    _reject_extra_keys(bundle_manifest, BUNDLE_KEYS, "bundle")
    _require(bundle_manifest.get("bundleVersion") == 2, "unsupported engagement bundleVersion")
    tool = bundle_manifest.get("tool")
    _require(isinstance(tool, dict), "bundle.tool must be an object")
    _reject_extra_keys(tool, TOOL_KEYS, "bundle.tool")
    _require(_non_blank(tool.get("name"), "bundle.tool.name") == "contractgraph-qa", "bundle.tool.name mismatch")
    return _non_blank(tool.get("version"), "bundle.tool.version")


def verify_engagement_bundle(path: Path) -> dict[str, Any]:
    source = path.expanduser().resolve()
    _require(source.is_file(), f"engagement bundle not found: {source}")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _require(len(names) == len(set(names)), "engagement bundle contains duplicate entries")
            for info in infos:
                _validate_archive_name(info.filename)
                _require(
                    info.file_size <= MAX_BUNDLE_ENTRY_BYTES,
                    f"bundle entry exceeds size limit: {info.filename}",
                )
            _require("bundle.json" in names, "engagement bundle is missing bundle.json")
            payloads = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise EngagementError(f"invalid engagement bundle: {exc}") from exc

    try:
        bundle_manifest = json.loads(payloads["bundle.json"].decode("utf-8"))
        manifest = json.loads(payloads["manifest.json"].decode("utf-8"))
        result = json.loads(payloads["engagement-result.json"].decode("utf-8"))
        engagement_payload = json.loads(payloads["engagement.json"].decode("utf-8"))
        engagement_markdown = payloads["engagement.md"].decode("utf-8")
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngagementError(f"engagement bundle contains invalid required data: {exc}") from exc

    _require(isinstance(manifest, dict), "manifest.json must be an object")
    _require(isinstance(result, dict), "engagement-result.json must be an object")
    _require(isinstance(engagement_payload, dict), "engagement.json must be an object")
    _require(isinstance(bundle_manifest, dict), "bundle.json must be an object")
    tool_version = _bundle_tool_version(bundle_manifest)

    expected_engagement, expected_findings = build_engagement(manifest, result)
    expected_payloads: dict[str, bytes] = {
        "manifest.json": payloads["manifest.json"],
        "engagement-result.json": payloads["engagement-result.json"],
        "engagement.json": canonical_json(expected_engagement).encode("utf-8"),
        "engagement.md": render_engagement_markdown(expected_engagement).encode("utf-8"),
    }
    expected_payloads.update(_finding_payloads(expected_findings))
    expected_finding_ids = sorted(finding["id"] for finding in expected_findings)
    expected_bundle_manifest = _bundle_manifest(
        expected_engagement,
        expected_payloads,
        expected_finding_ids,
        tool_version,
    )
    expected_bundle_payload = canonical_json(expected_bundle_manifest).encode("utf-8")

    expected_names = list(BASE_BUNDLE_FILES) + sorted(
        name for name in expected_payloads if name.startswith("findings/")
    ) + ["bundle.json"]
    _require(names == expected_names, "engagement bundle entries are missing, reordered, or unexpected")
    for name, expected in expected_payloads.items():
        _require(
            payloads.get(name) == expected,
            f"engagement artifact does not match semantic chain: {name}",
        )
    _require(
        payloads["bundle.json"] == expected_bundle_payload,
        "bundle.json does not match engagement artifacts",
    )
    _require(engagement_payload == expected_engagement, "engagement.json semantic mismatch")
    _require(
        engagement_markdown == render_engagement_markdown(expected_engagement),
        "engagement.md semantic mismatch",
    )

    return {
        "ok": True,
        "bundle": str(source),
        "engagementId": expected_engagement["engagementId"],
        "findingIds": expected_finding_ids,
        "coverage": expected_engagement["coverage"],
        "manifestSha256": expected_engagement["manifestSha256"],
        "toolVersion": tool_version,
        "bundleSha256": _sha256_file(source),
    }
