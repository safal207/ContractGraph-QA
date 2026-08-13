"""Deterministic bundle v3 for post-impact containment/recovery evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
import zipfile

from contractgraph_qa import __version__
from contractgraph_qa.control_report import render_control_report
from contractgraph_qa.finding import canonical_json
from contractgraph_qa.postimpact import (
    PostImpactModel,
    post_impact_model_from_dict,
    post_impact_model_sha256,
    post_impact_model_to_dict,
    run_post_impact_model,
)
from contractgraph_qa.product import ProductError, verify_evidence_bundle
from contractgraph_qa.reachability import reachability_model_from_dict, run_reachability_model

BASE_V2_FILES = (
    "manifest.json",
    "result.json",
    "reachability-model.json",
    "reachability.json",
    "finding.json",
    "report.md",
    "bundle.json",
)
CONTROL_BUNDLE_FILES = (
    "manifest.json",
    "result.json",
    "reachability-model.json",
    "reachability.json",
    "post-impact-model.json",
    "post-impact.json",
    "finding.json",
    "report.md",
    "control-report.md",
    "base-bundle.json",
    "bundle.json",
)
CONTROL_BUNDLE_KEYS = {
    "bundleVersion",
    "tool",
    "findingId",
    "manifestSha256",
    "reachabilityModelSha256",
    "postImpactModelSha256",
    "baseBundleSha256",
    "artifacts",
}
TOOL_KEYS = {"name", "version"}
ARTIFACT_KEYS = {"sha256", "bytes"}
MAX_ENTRY_BYTES = 16 * 1024 * 1024


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def _write_zip(path: Path, names: tuple[str, ...], payloads: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(_zip_entry(name), payloads[name])


def _read_exact_zip(path: Path, expected: tuple[str, ...]) -> dict[str, bytes]:
    source = path.expanduser().resolve()
    _require(source.is_file(), f"bundle not found: {source}")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            _require(names == expected, "bundle entries are missing, reordered, or unexpected")
            for info in infos:
                _require(info.file_size <= MAX_ENTRY_BYTES, f"bundle entry exceeds size limit: {info.filename}")
            return {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise ProductError(f"invalid bundle: {exc}") from exc


def _load_json(payload: bytes, field: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductError(f"invalid JSON in {field}: {exc}") from exc
    _require(isinstance(value, dict), f"{field} must be an object")
    return value


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _canonical_post_impact(
    model: PostImpactModel,
    reachability_model_data: dict[str, Any],
    reachability_result: dict[str, Any],
) -> tuple[bytes, bytes, bytes, dict[str, object]]:
    reachability_model = reachability_model_from_dict(reachability_model_data)
    expected_reachability = run_reachability_model(reachability_model)
    _require(
        canonical_json(expected_reachability).encode("utf-8")
        == canonical_json(reachability_result).encode("utf-8"),
        "embedded reachability result does not match its model",
    )
    post_result = run_post_impact_model(model, reachability_model, expected_reachability)
    model_bytes = canonical_json(post_impact_model_to_dict(model)).encode("utf-8")
    result_bytes = canonical_json(post_result).encode("utf-8")
    report_bytes = render_control_report(post_result).encode("utf-8")
    return model_bytes, result_bytes, report_bytes, post_result


def create_control_evidence_bundle(
    base_bundle: Path,
    post_impact_model: PostImpactModel,
    output: Path,
) -> dict[str, Any]:
    """Upgrade an independently verified reachability bundle v2 into control bundle v3."""

    base_path = base_bundle.expanduser().resolve()
    base_verification = verify_evidence_bundle(base_path)
    _require(
        base_verification.get("bundleVersion") == 2,
        "control bundle requires a reachability-aware bundle v2",
    )
    base_payloads = _read_exact_zip(base_path, BASE_V2_FILES)
    reachability_model_data = _load_json(base_payloads["reachability-model.json"], "reachability-model.json")
    reachability_result = _load_json(base_payloads["reachability.json"], "reachability.json")
    model_bytes, result_bytes, report_bytes, post_result = _canonical_post_impact(
        post_impact_model,
        reachability_model_data,
        reachability_result,
    )

    payloads: dict[str, bytes] = {
        "manifest.json": base_payloads["manifest.json"],
        "result.json": base_payloads["result.json"],
        "reachability-model.json": base_payloads["reachability-model.json"],
        "reachability.json": base_payloads["reachability.json"],
        "post-impact-model.json": model_bytes,
        "post-impact.json": result_bytes,
        "finding.json": base_payloads["finding.json"],
        "report.md": base_payloads["report.md"],
        "control-report.md": report_bytes,
        "base-bundle.json": base_payloads["bundle.json"],
    }
    for name, payload in payloads.items():
        _require(len(payload) <= MAX_ENTRY_BYTES, f"artifact too large for control bundle: {name}")

    reachability_model_hash = str(reachability_result["modelSha256"])
    control_manifest: dict[str, Any] = {
        "bundleVersion": 3,
        "tool": {"name": "contractgraph-qa", "version": __version__},
        "findingId": base_verification["findingId"],
        "manifestSha256": base_verification["manifestSha256"],
        "reachabilityModelSha256": reachability_model_hash,
        "postImpactModelSha256": post_result["postImpactModelSha256"],
        "baseBundleSha256": _sha256(base_path.read_bytes()),
        "artifacts": {
            name: {"sha256": _sha256(payload), "bytes": len(payload)}
            for name, payload in payloads.items()
        },
    }
    payloads["bundle.json"] = canonical_json(control_manifest).encode("utf-8")
    output_path = output.expanduser().resolve()
    _write_zip(output_path, CONTROL_BUNDLE_FILES, payloads)
    return {
        "ok": True,
        "bundleVersion": 3,
        "findingId": base_verification["findingId"],
        "manifestSha256": base_verification["manifestSha256"],
        "reachabilityModelSha256": reachability_model_hash,
        "postImpactModelSha256": post_result["postImpactModelSha256"],
        "postImpactStatus": post_result["status"],
        "controlReport": "control-report.md",
        "bundle": str(output_path),
        "bundleSha256": _sha256(output_path.read_bytes()),
    }


def verify_control_evidence_bundle(path: Path) -> dict[str, Any]:
    """Independently reconstruct v2 evidence, then re-run post-impact control semantics."""

    source = path.expanduser().resolve()
    payloads = _read_exact_zip(source, CONTROL_BUNDLE_FILES)
    control_manifest = _load_json(payloads["bundle.json"], "bundle.json")
    _reject_extra_keys(control_manifest, CONTROL_BUNDLE_KEYS, "bundle")
    _require(control_manifest.get("bundleVersion") == 3, "unsupported control bundleVersion")

    tool = control_manifest.get("tool")
    _require(isinstance(tool, dict), "bundle.tool must be an object")
    _reject_extra_keys(tool, TOOL_KEYS, "bundle.tool")
    _require(tool.get("name") == "contractgraph-qa", "bundle.tool.name mismatch")
    _require(
        isinstance(tool.get("version"), str) and bool(tool["version"].strip()),
        "bundle.tool.version missing",
    )

    artifacts = control_manifest.get("artifacts")
    _require(isinstance(artifacts, dict), "bundle.artifacts must be an object")
    expected_artifacts = set(CONTROL_BUNDLE_FILES) - {"bundle.json"}
    _require(set(artifacts) == expected_artifacts, "control bundle artifact set mismatch")
    for name in tuple(item for item in CONTROL_BUNDLE_FILES if item != "bundle.json"):
        record = artifacts.get(name)
        _require(isinstance(record, dict), f"artifact record missing: {name}")
        _reject_extra_keys(record, ARTIFACT_KEYS, f"bundle.artifacts.{name}")
        _require(record.get("sha256") == _sha256(payloads[name]), f"bundle hash mismatch: {name}")
        _require(record.get("bytes") == len(payloads[name]), f"bundle size mismatch: {name}")

    base_payloads = {
        "manifest.json": payloads["manifest.json"],
        "result.json": payloads["result.json"],
        "reachability-model.json": payloads["reachability-model.json"],
        "reachability.json": payloads["reachability.json"],
        "finding.json": payloads["finding.json"],
        "report.md": payloads["report.md"],
        "bundle.json": payloads["base-bundle.json"],
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        reconstructed = Path(temp_dir) / "base.evidence.zip"
        _write_zip(reconstructed, BASE_V2_FILES, base_payloads)
        _require(
            _sha256(reconstructed.read_bytes()) == control_manifest.get("baseBundleSha256"),
            "base bundle SHA-256 mismatch",
        )
        base_verification = verify_evidence_bundle(reconstructed)

    reachability_model_data = _load_json(payloads["reachability-model.json"], "reachability-model.json")
    reachability_result = _load_json(payloads["reachability.json"], "reachability.json")
    post_model_data = _load_json(payloads["post-impact-model.json"], "post-impact-model.json")
    try:
        post_model = post_impact_model_from_dict(post_model_data)
        expected_model_bytes, expected_result_bytes, expected_report_bytes, expected_post_result = (
            _canonical_post_impact(post_model, reachability_model_data, reachability_result)
        )
    except ValueError as exc:
        raise ProductError(f"invalid post-impact evidence: {exc}") from exc

    _require(expected_model_bytes == payloads["post-impact-model.json"], "post-impact-model.json is not canonical")
    _require(expected_result_bytes == payloads["post-impact.json"], "post-impact.json does not match post-impact-model.json")
    _require(
        expected_report_bytes == payloads["control-report.md"],
        "control-report.md does not match post-impact.json",
    )
    _require(
        control_manifest.get("postImpactModelSha256") == post_impact_model_sha256(post_model),
        "bundle postImpactModelSha256 mismatch",
    )
    _require(
        control_manifest.get("reachabilityModelSha256") == reachability_result.get("modelSha256"),
        "bundle reachabilityModelSha256 mismatch",
    )
    _require(control_manifest.get("findingId") == base_verification["findingId"], "bundle findingId mismatch")
    _require(
        control_manifest.get("manifestSha256") == base_verification["manifestSha256"],
        "bundle manifestSha256 mismatch",
    )

    return {
        "ok": True,
        "bundleVersion": 3,
        "bundle": str(source),
        "bundleSha256": _sha256(source.read_bytes()),
        "findingId": base_verification["findingId"],
        "manifestSha256": base_verification["manifestSha256"],
        "reachabilityModelSha256": reachability_result["modelSha256"],
        "postImpactModelSha256": expected_post_result["postImpactModelSha256"],
        "postImpactStatus": expected_post_result["status"],
        "boundTargetCapability": expected_post_result["boundTargetCapability"],
        "controlReport": "control-report.md",
    }
