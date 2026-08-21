"""Deterministic provenance wrapper for verified engagement evidence bundles."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any
import zipfile

from contractgraph_qa import __version__
from contractgraph_qa.engagement import EngagementError, verify_engagement_bundle
from contractgraph_qa.finding import canonical_json, manifest_sha256
from contractgraph_qa.measurement_provenance import (
    MeasurementProvenanceError,
    MeasurementSpec,
    run_measurement_provenance_gate,
    verify_measurement_provenance_result,
)

BUNDLE_SCHEMA = "cgqa.engagement-provenance-bundle.v1"
SOURCE_SCHEMA = "cgqa.engagement-measurement-source.v1"
MEASUREMENT_ID = "engagement-invariant-check-results"
COVERAGE_SCOPE = "engagement_declared_invariant_checks"
BUNDLE_FILES = (
    "base-engagement.zip",
    "measurement-input.json",
    "measurement-source.json",
    "measurement-provenance.json",
    "bundle.json",
)
BUNDLE_KEYS = {
    "schema",
    "bundleVersion",
    "tool",
    "engagementId",
    "manifestSha256",
    "baseBundleSha256",
    "measurementId",
    "artifacts",
}
TOOL_KEYS = {"name", "version"}
ARTIFACT_KEYS = {"sha256", "bytes"}
MAX_ENTRY_BYTES = 32 * 1024 * 1024


class EngagementProvenanceError(ValueError):
    """Expected engagement provenance construction or verification failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngagementProvenanceError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_ids(values: list[object], label: str) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        _require(
            isinstance(value, str) and bool(value.strip()),
            f"{label} must contain non-empty strings",
        )
        items.append(value.strip())
    _require(len(items) == len(set(items)), f"{label} must not contain duplicates")
    return tuple(sorted(items))


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def _read_base_artifacts(bundle: Path) -> tuple[bytes, bytes]:
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            return archive.read("manifest.json"), archive.read("engagement-result.json")
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise EngagementProvenanceError(
            f"cannot read verified base engagement artifacts: {exc}"
        ) from exc


def _load_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngagementProvenanceError(f"invalid JSON in {label}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def build_engagement_measurement_artifacts(
    manifest: dict[str, Any],
    result: dict[str, Any],
    *,
    manifest_bytes: bytes,
    result_bytes: bytes,
    required_schema_epoch: int = 1,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build measurement input, source receipt, and provenance verdict.

    The denominator comes from invariant ids declared by the manifest. The
    numerator comes independently from invariant ids actually emitted by the
    engagement result. The source receipt binds those populations to the exact
    bytes that entered the client evidence bundle.
    """

    _require(
        isinstance(manifest_bytes, bytes) and bool(manifest_bytes),
        "manifest bytes must be non-empty",
    )
    _require(
        isinstance(result_bytes, bytes) and bool(result_bytes),
        "result bytes must be non-empty",
    )

    raw_invariants = manifest.get("invariants")
    raw_checks = result.get("checks")
    _require(
        isinstance(raw_invariants, list) and bool(raw_invariants),
        "manifest invariants must be non-empty",
    )
    _require(isinstance(raw_checks, list), "engagement result checks must be an array")

    declared_values: list[object] = []
    for index, item in enumerate(raw_invariants):
        _require(
            isinstance(item, dict),
            f"manifest invariants[{index}] must be an object",
        )
        declared_values.append(item.get("id"))
    observed_values: list[object] = []
    for index, item in enumerate(raw_checks):
        _require(
            isinstance(item, dict),
            f"engagement result checks[{index}] must be an object",
        )
        observed_values.append(item.get("invariantId"))

    declared_ids = _canonical_ids(declared_values, "declared invariant ids")
    observed_ids = _canonical_ids(observed_values, "observed invariant ids")
    unexpected = sorted(set(observed_ids) - set(declared_ids))
    _require(
        not unexpected,
        "engagement result contains invariant ids outside the manifest population: "
        + ", ".join(unexpected),
    )

    schema_epoch = result.get("schemaVersion")
    _require(
        isinstance(schema_epoch, int)
        and not isinstance(schema_epoch, bool)
        and schema_epoch >= 1,
        "engagement result schemaVersion must be an integer >= 1",
    )
    _require(
        isinstance(required_schema_epoch, int)
        and not isinstance(required_schema_epoch, bool)
        and required_schema_epoch >= 1,
        "required_schema_epoch must be an integer >= 1",
    )

    fingerprint = manifest_sha256(manifest)
    _require(
        result.get("manifestSha256") == fingerprint,
        "engagement result manifestSha256 does not match manifest",
    )
    engagement_id = result.get("engagementId")
    _require(
        isinstance(engagement_id, str) and bool(engagement_id.strip()),
        "engagementId must be non-empty",
    )

    measurement_input = {
        "schemaVersion": 1,
        "measurements": [
            {
                "id": MEASUREMENT_ID,
                "schemaEpoch": schema_epoch,
                "requiredSchemaEpoch": required_schema_epoch,
                "coverageScope": COVERAGE_SCOPE,
                "observedUnits": len(observed_ids),
                "eligibleUnits": len(declared_ids),
                "requiredCoverage": 1.0,
                "measurementAvailable": True,
            }
        ],
    }
    provenance = run_measurement_provenance_gate(
        (
            MeasurementSpec(
                id=MEASUREMENT_ID,
                schema_epoch=schema_epoch,
                required_schema_epoch=required_schema_epoch,
                coverage_scope=COVERAGE_SCOPE,
                observed_units=len(observed_ids),
                eligible_units=len(declared_ids),
                required_coverage=1.0,
                measurement_available=True,
            ),
        )
    )
    source = {
        "schema": SOURCE_SCHEMA,
        "measurementId": MEASUREMENT_ID,
        "engagementId": engagement_id.strip(),
        "manifestSha256": fingerprint,
        "manifestArtifactSha256": _sha256(manifest_bytes),
        "engagementResultArtifactSha256": _sha256(result_bytes),
        "declaredInvariantIds": list(declared_ids),
        "observedInvariantIds": list(observed_ids),
    }
    return measurement_input, source, provenance


def _bundle_manifest(
    base_verification: dict[str, Any],
    payloads: dict[str, bytes],
) -> dict[str, Any]:
    artifact_names = tuple(name for name in BUNDLE_FILES if name != "bundle.json")
    _require(
        set(payloads) == set(artifact_names),
        "provenance bundle manifest received an unexpected artifact population",
    )
    return {
        "schema": BUNDLE_SCHEMA,
        "bundleVersion": 1,
        "tool": {"name": "contractgraph-qa", "version": __version__},
        "engagementId": base_verification["engagementId"],
        "manifestSha256": base_verification["manifestSha256"],
        "baseBundleSha256": _sha256(payloads["base-engagement.zip"]),
        "measurementId": MEASUREMENT_ID,
        "artifacts": {
            name: {
                "sha256": _sha256(payloads[name]),
                "bytes": len(payloads[name]),
            }
            for name in artifact_names
        },
    }


def create_engagement_provenance_bundle(
    base_bundle: Path,
    output: Path,
) -> dict[str, Any]:
    """Wrap a verified engagement bundle with source-bound measurement provenance."""

    base = base_bundle.expanduser().resolve()
    base_verification = verify_engagement_bundle(base)
    manifest_bytes, result_bytes = _read_base_artifacts(base)
    manifest = _load_object(manifest_bytes, "manifest.json")
    result = _load_object(result_bytes, "engagement-result.json")
    measurement_input, source, provenance = build_engagement_measurement_artifacts(
        manifest,
        result,
        manifest_bytes=manifest_bytes,
        result_bytes=result_bytes,
    )
    _require(
        provenance.get("status") == "pass",
        "blocked measurement provenance cannot become client evidence",
    )

    payloads = {
        "base-engagement.zip": base.read_bytes(),
        "measurement-input.json": canonical_json(measurement_input).encode("utf-8"),
        "measurement-source.json": canonical_json(source).encode("utf-8"),
        "measurement-provenance.json": canonical_json(provenance).encode("utf-8"),
    }
    for name, payload in payloads.items():
        _require(
            len(payload) <= MAX_ENTRY_BYTES,
            f"provenance bundle artifact too large: {name}",
        )
    bundle_manifest = _bundle_manifest(base_verification, payloads)
    bundle_bytes = canonical_json(bundle_manifest).encode("utf-8")

    target = output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as archive:
        for name in BUNDLE_FILES:
            payload = bundle_bytes if name == "bundle.json" else payloads[name]
            archive.writestr(_zip_entry(name), payload)

    verified = verify_engagement_provenance_bundle(target)
    return {
        "ok": True,
        "engagementId": verified["engagementId"],
        "manifestSha256": verified["manifestSha256"],
        "coverage": verified["coverage"],
        "findingIds": verified["findingIds"],
        "measurementProvenanceStatus": verified["measurementProvenanceStatus"],
        "baseBundleSha256": verified["baseBundleSha256"],
        "bundle": str(target),
        "bundleSha256": verified["bundleSha256"],
    }


def verify_engagement_provenance_bundle(path: Path) -> dict[str, Any]:
    """Independently reconstruct the base engagement and its measurement boundary."""

    source_path = path.expanduser().resolve()
    _require(
        source_path.is_file(),
        f"engagement provenance bundle not found: {source_path}",
    )
    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            _require(
                names == BUNDLE_FILES,
                "provenance bundle entries are missing, reordered, or unexpected",
            )
            for info in infos:
                _require(
                    info.file_size <= MAX_ENTRY_BYTES,
                    f"provenance bundle entry exceeds size limit: {info.filename}",
                )
            payloads = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise EngagementProvenanceError(
            f"invalid engagement provenance bundle: {exc}"
        ) from exc

    bundle_manifest = _load_object(payloads["bundle.json"], "bundle.json")
    _require(
        set(bundle_manifest) == BUNDLE_KEYS,
        "provenance bundle manifest has invalid shape",
    )
    _require(
        bundle_manifest.get("schema") == BUNDLE_SCHEMA,
        "unsupported provenance bundle schema",
    )
    _require(
        bundle_manifest.get("bundleVersion") == 1,
        "unsupported provenance bundleVersion",
    )
    tool = bundle_manifest.get("tool")
    _require(
        isinstance(tool, dict) and set(tool) == TOOL_KEYS,
        "provenance bundle tool has invalid shape",
    )
    _require(tool.get("name") == "contractgraph-qa", "provenance bundle tool name mismatch")
    _require(
        isinstance(tool.get("version"), str) and bool(tool["version"].strip()),
        "provenance bundle tool version missing",
    )
    _require(
        bundle_manifest.get("measurementId") == MEASUREMENT_ID,
        "provenance bundle measurement id mismatch",
    )

    artifacts = bundle_manifest.get("artifacts")
    _require(isinstance(artifacts, dict), "provenance bundle artifacts must be an object")
    expected_artifact_names = tuple(
        name for name in BUNDLE_FILES if name != "bundle.json"
    )
    _require(
        set(artifacts) == set(expected_artifact_names),
        "provenance bundle artifact set mismatch",
    )
    for name in expected_artifact_names:
        record = artifacts.get(name)
        _require(
            isinstance(record, dict) and set(record) == ARTIFACT_KEYS,
            f"invalid artifact record: {name}",
        )
        _require(
            record.get("sha256") == _sha256(payloads[name]),
            f"provenance bundle hash mismatch: {name}",
        )
        _require(
            record.get("bytes") == len(payloads[name]),
            f"provenance bundle size mismatch: {name}",
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir) / "base-engagement.zip"
        base_path.write_bytes(payloads["base-engagement.zip"])
        try:
            base_verification = verify_engagement_bundle(base_path)
        except EngagementError as exc:
            raise EngagementProvenanceError(
                f"embedded engagement bundle failed verification: {exc}"
            ) from exc
        manifest_bytes, result_bytes = _read_base_artifacts(base_path)

    manifest = _load_object(manifest_bytes, "manifest.json")
    result = _load_object(result_bytes, "engagement-result.json")
    expected_input, expected_source, expected_provenance = (
        build_engagement_measurement_artifacts(
            manifest,
            result,
            manifest_bytes=manifest_bytes,
            result_bytes=result_bytes,
        )
    )
    try:
        supplied_provenance = _load_object(
            payloads["measurement-provenance.json"],
            "measurement-provenance.json",
        )
        verify_measurement_provenance_result(supplied_provenance)
    except MeasurementProvenanceError as exc:
        raise EngagementProvenanceError(
            f"invalid measurement provenance verdict: {exc}"
        ) from exc

    _require(
        payloads["measurement-input.json"]
        == canonical_json(expected_input).encode("utf-8"),
        "measurement-input.json does not match the embedded engagement population",
    )
    _require(
        payloads["measurement-source.json"]
        == canonical_json(expected_source).encode("utf-8"),
        "measurement-source.json does not match the embedded engagement sources",
    )
    _require(
        payloads["measurement-provenance.json"]
        == canonical_json(expected_provenance).encode("utf-8"),
        "measurement-provenance.json does not match the recomputed measurement boundary",
    )
    _require(
        expected_provenance.get("status") == "pass",
        "embedded measurement provenance is blocked",
    )

    expected_payloads = {
        name: payloads[name]
        for name in expected_artifact_names
    }
    expected_manifest = _bundle_manifest(base_verification, expected_payloads)
    _require(
        payloads["bundle.json"] == canonical_json(expected_manifest).encode("utf-8"),
        "bundle.json does not match provenance artifacts",
    )
    _require(
        bundle_manifest.get("engagementId") == base_verification["engagementId"],
        "provenance bundle engagementId mismatch",
    )
    _require(
        bundle_manifest.get("manifestSha256") == base_verification["manifestSha256"],
        "provenance bundle manifestSha256 mismatch",
    )
    _require(
        bundle_manifest.get("baseBundleSha256")
        == _sha256(payloads["base-engagement.zip"]),
        "provenance bundle baseBundleSha256 mismatch",
    )

    return {
        "ok": True,
        "bundle": str(source_path),
        "bundleSha256": _sha256(source_path.read_bytes()),
        "engagementId": base_verification["engagementId"],
        "manifestSha256": base_verification["manifestSha256"],
        "coverage": base_verification["coverage"],
        "findingIds": base_verification["findingIds"],
        "baseBundleSha256": _sha256(payloads["base-engagement.zip"]),
        "measurementProvenanceStatus": expected_provenance["status"],
        "coverageScope": COVERAGE_SCOPE,
    }
