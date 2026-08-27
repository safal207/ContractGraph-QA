"""Deterministic evidence pack for Hydrated Contract Lattice assessments.

The pack preserves static possibility evidence, normalized runtime actuality,
reviewed hydration bindings, and the deterministic composed assessment as
separate payloads. Verification replays the assessment from the embedded inputs.

A verifier-supplied complete-pack digest can bind the bytes to an external
integrity anchor. Without that separately obtained digest, verification proves
local consistency only; it does not prove source identity, capture completeness,
authority truth, security certification, or production authorization.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Mapping
import zipfile

from contractgraph_qa.execution_trace import execution_trace_from_dict, execution_trace_to_dict
from contractgraph_qa.hydrated_lattice import (
    hydration_bindings_from_dict,
    hydration_bindings_to_dict,
    run_hydrated_lattice,
)

PACK_SCHEMA = "cgqa.hydrated-lattice-evidence-pack.v0.1"
MANIFEST_SCHEMA = "cgqa.hydrated-lattice-evidence-pack-manifest.v0.1"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_FIXED_ZIP_CREATE_VERSION = 20
_FIXED_ZIP_EXTRACT_VERSION = 20
_CONTENT_NAMES = [
    "static-result.json",
    "execution-trace.json",
    "hydration-bindings.json",
    "assessment.json",
    "client-summary.md",
]
_PACK_NAMES = [*_CONTENT_NAMES, "manifest.json"]
_AUTHORITY = {
    "classification": "RESEARCH_ONLY",
    "securityCertification": False,
    "productionAuthorization": False,
    "financialAuthorization": False,
    "sourceAuthenticityProven": False,
}
_EXTERNAL_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class HydratedLatticeEvidencePackError(ValueError):
    """Raised when a hydrated-lattice evidence pack cannot be built or verified."""


def canonical_json_bytes(payload: object) -> bytes:
    """Encode type-sensitive deterministic JSON bytes used by the pack contract."""
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HydratedLatticeEvidencePackError(f"payload is not canonical-JSON encodable: {exc}") from exc
    return (text + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HydratedLatticeEvidencePackError(f"unable to read {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HydratedLatticeEvidencePackError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HydratedLatticeEvidencePackError(f"{label} root must be an object")
    return payload


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_version = _FIXED_ZIP_CREATE_VERSION
    info.extract_version = _FIXED_ZIP_EXTRACT_VERSION
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _status(value: object, label: str) -> str:
    if value not in {"pass", "fail", "inconclusive"}:
        raise HydratedLatticeEvidencePackError(f"{label} has invalid status")
    return str(value)


def _client_summary(assessment: Mapping[str, object]) -> bytes:
    overall = _status(assessment.get("status"), "assessment")
    static = assessment.get("staticLifecycle")
    runtime = assessment.get("runtimeVerification")
    conformance = assessment.get("staticRuntimeConformance")
    bindings = assessment.get("bindingVerification")
    if not all(isinstance(item, dict) for item in (static, runtime, conformance, bindings)):
        raise HydratedLatticeEvidencePackError("assessment is missing verification sections")

    economic = runtime.get("economicCardinality")
    successor = runtime.get("successorConsistency")
    economic_status = economic.get("status") if isinstance(economic, dict) else "missing"
    successor_status = successor.get("status") if isinstance(successor, dict) else "missing"
    missing_authority = bindings.get("missingAuthorityCommitIds", [])
    missing_time = bindings.get("missingTimeWitnessCommitIds", [])
    missing_evidence = bindings.get("missingEvidenceCommitIds", [])

    lines = [
        "# Hydrated Contract Lattice Evidence Pack v0.1",
        "",
        "## Executive verdict",
        "",
        f"**Overall assessment: `{overall.upper()}`.**",
        "",
        "## Independent proof legs",
        "",
        "| Proof leg | Status |",
        "|---|---|",
        f"| Static lifecycle | `{static.get('status', 'missing')}` |",
        f"| Runtime economic cardinality | `{economic_status}` |",
        f"| Runtime successor consistency | `{successor_status}` |",
        f"| Static/runtime transition conformance | `{conformance.get('status', 'missing')}` |",
        f"| Authority/time/evidence bindings | `{bindings.get('status', 'missing')}` |",
        "",
        "## Missing proof coordinates",
        "",
        f"- authority commit IDs: `{', '.join(map(str, missing_authority)) if missing_authority else 'none'}`",
        f"- time-witness commit IDs: `{', '.join(map(str, missing_time)) if missing_time else 'none'}`",
        f"- evidence commit IDs: `{', '.join(map(str, missing_evidence)) if missing_evidence else 'none'}`",
        "",
        "## Interpretation",
        "",
        "Static possibility and runtime actuality are separate proof legs. A legal static transition can still participate in an unsafe observed composition, and missing required proof material remains INCONCLUSIVE rather than being promoted to PASS.",
        "",
        "## Scope boundary",
        "",
        "This deterministic pack proves local replay consistency over the embedded reviewed static result, normalized execution trace, and hydration bindings. A separately supplied complete-pack SHA-256 can bind these exact bytes to an external integrity reference, but a digest alone does not prove who produced the evidence. The pack does not prove raw EVM/provider capture completeness, semantic-normalization authority, concrete balances, truth of external authority/time sources, security certification, or production/financial authorization.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _normalize_inputs(
    static_result: dict[str, Any],
    execution_trace: dict[str, Any],
    hydration_bindings: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, object], dict[str, object], dict[str, object]]:
    trace = execution_trace_from_dict(execution_trace)
    bindings = hydration_bindings_from_dict(hydration_bindings)
    assessment = run_hydrated_lattice(static_result, trace, bindings)
    return (
        static_result,
        execution_trace_to_dict(trace),
        hydration_bindings_to_dict(bindings),
        assessment,
    )


def build_hydrated_lattice_evidence_pack(
    static_result_path: Path,
    execution_trace_path: Path,
    hydration_bindings_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Build a deterministic ZIP from exact hydrated-lattice proof inputs."""
    static_result = _load_json_object(static_result_path, "static result")
    execution_trace = _load_json_object(execution_trace_path, "execution trace")
    hydration_bindings = _load_json_object(hydration_bindings_path, "hydration bindings")

    try:
        static_result, trace_document, bindings_document, assessment = _normalize_inputs(
            static_result, execution_trace, hydration_bindings
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HydratedLatticeEvidencePackError(f"unable to evaluate hydrated lattice: {exc}") from exc

    artifacts = {
        "static-result.json": canonical_json_bytes(static_result),
        "execution-trace.json": canonical_json_bytes(trace_document),
        "hydration-bindings.json": canonical_json_bytes(bindings_document),
        "assessment.json": canonical_json_bytes(assessment),
        "client-summary.md": _client_summary(assessment),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "packSchema": PACK_SCHEMA,
        "assessmentSchema": assessment.get("schemaVersion"),
        "status": assessment.get("status"),
        "entries": [
            {"path": name, "sha256": _sha256(artifacts[name]), "bytes": len(artifacts[name])}
            for name in _CONTENT_NAMES
        ],
        "authority": dict(_AUTHORITY),
        "verificationBoundary": "LOCAL_REPLAY_CONSISTENCY_WITH_OPTIONAL_EXTERNAL_BYTE_DIGEST",
    }
    manifest_bytes = canonical_json_bytes(manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in _CONTENT_NAMES:
            archive.writestr(_zip_entry(name), artifacts[name])
        archive.writestr(_zip_entry("manifest.json"), manifest_bytes)

    pack_bytes = output_path.read_bytes()
    return {
        "schema": PACK_SCHEMA,
        "output": str(output_path),
        "sha256": _sha256(pack_bytes),
        "status": assessment["status"],
        "entries": list(_PACK_NAMES),
        "externalIntegrityBound": False,
    }


def _read_pack(pack_path: Path) -> tuple[bytes, dict[str, bytes]]:
    try:
        pack_bytes = pack_path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(pack_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != _PACK_NAMES:
                raise HydratedLatticeEvidencePackError(
                    "pack entries must be exactly " + ", ".join(_PACK_NAMES) + " in canonical order"
                )
            if archive.comment != b"":
                raise HydratedLatticeEvidencePackError("non-canonical ZIP archive comment")
            for info in infos:
                if info.date_time != _FIXED_ZIP_TIME:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP timestamp: {info.filename}")
                if info.compress_type != zipfile.ZIP_STORED:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP compression: {info.filename}")
                if info.create_version != _FIXED_ZIP_CREATE_VERSION:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP create version: {info.filename}")
                if info.extract_version != _FIXED_ZIP_EXTRACT_VERSION:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP extract version: {info.filename}")
                if info.create_system != 3 or info.external_attr != 0o100644 << 16:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP file mode: {info.filename}")
                if info.extra != b"":
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP extra field: {info.filename}")
                if info.comment != b"":
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP entry comment: {info.filename}")
                if info.flag_bits != 0:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP flag bits: {info.filename}")
                if info.internal_attr != 0:
                    raise HydratedLatticeEvidencePackError(f"non-canonical ZIP internal attributes: {info.filename}")
            return pack_bytes, {name: archive.read(name) for name in names}
    except HydratedLatticeEvidencePackError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise HydratedLatticeEvidencePackError(f"unable to read evidence pack: {exc}") from exc


def _decode_json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HydratedLatticeEvidencePackError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HydratedLatticeEvidencePackError(f"{label} root must be an object")
    if canonical_json_bytes(payload) != data:
        raise HydratedLatticeEvidencePackError(f"{label} is not canonical JSON")
    return payload


def _validate_external_digest(pack_bytes: bytes, expected_pack_sha256: str | None) -> bool:
    if expected_pack_sha256 is None:
        return False
    if not isinstance(expected_pack_sha256, str) or not _EXTERNAL_DIGEST_RE.fullmatch(expected_pack_sha256):
        raise HydratedLatticeEvidencePackError("expected pack digest must be exactly 64 hexadecimal characters")
    actual = _sha256(pack_bytes)
    if actual != expected_pack_sha256.lower():
        raise HydratedLatticeEvidencePackError(
            f"external pack digest mismatch: expected {expected_pack_sha256.lower()}, observed {actual}"
        )
    return True


def verify_hydrated_lattice_evidence_pack(
    pack_path: Path,
    *,
    expected_pack_sha256: str | None = None,
) -> dict[str, object]:
    """Verify deterministic bytes, entry hashes and exact local semantic replay."""
    pack_bytes, blobs = _read_pack(pack_path)
    externally_bound = _validate_external_digest(pack_bytes, expected_pack_sha256)

    manifest = _decode_json_object(blobs["manifest.json"], "manifest.json")
    static_result = _decode_json_object(blobs["static-result.json"], "static-result.json")
    execution_trace = _decode_json_object(blobs["execution-trace.json"], "execution-trace.json")
    hydration_bindings = _decode_json_object(blobs["hydration-bindings.json"], "hydration-bindings.json")
    packed_assessment = _decode_json_object(blobs["assessment.json"], "assessment.json")

    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise HydratedLatticeEvidencePackError("manifest schema mismatch")
    if manifest.get("packSchema") != PACK_SCHEMA:
        raise HydratedLatticeEvidencePackError("manifest packSchema mismatch")
    if canonical_json_bytes(manifest.get("authority")) != canonical_json_bytes(_AUTHORITY):
        raise HydratedLatticeEvidencePackError("manifest authority boundary mismatch")
    if manifest.get("verificationBoundary") != "LOCAL_REPLAY_CONSISTENCY_WITH_OPTIONAL_EXTERNAL_BYTE_DIGEST":
        raise HydratedLatticeEvidencePackError("manifest verification boundary mismatch")

    declared = manifest.get("entries")
    if not isinstance(declared, list) or len(declared) != len(_CONTENT_NAMES):
        raise HydratedLatticeEvidencePackError("manifest must hash exactly five content entries")
    declared_names = [item.get("path") if isinstance(item, dict) else None for item in declared]
    if declared_names != _CONTENT_NAMES:
        raise HydratedLatticeEvidencePackError("manifest content entries are not canonical")
    for item in declared:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            raise HydratedLatticeEvidencePackError("manifest entry shape mismatch")
        name = str(item["path"])
        data = blobs[name]
        if item.get("sha256") != _sha256(data) or item.get("bytes") != len(data):
            raise HydratedLatticeEvidencePackError(f"content hash/size mismatch: {name}")

    try:
        _, normalized_trace, normalized_bindings, replayed = _normalize_inputs(
            static_result, execution_trace, hydration_bindings
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HydratedLatticeEvidencePackError(f"embedded proof inputs are invalid: {exc}") from exc

    if canonical_json_bytes(normalized_trace) != blobs["execution-trace.json"]:
        raise HydratedLatticeEvidencePackError("execution-trace.json is not the normalized trace representation")
    if canonical_json_bytes(normalized_bindings) != blobs["hydration-bindings.json"]:
        raise HydratedLatticeEvidencePackError("hydration-bindings.json is not the normalized bindings representation")
    if canonical_json_bytes(replayed) != blobs["assessment.json"]:
        raise HydratedLatticeEvidencePackError("assessment.json does not match exact hydrated-lattice replay")
    if _client_summary(replayed) != blobs["client-summary.md"]:
        raise HydratedLatticeEvidencePackError("client-summary.md does not match the replayed assessment")
    if manifest.get("assessmentSchema") != replayed.get("schemaVersion"):
        raise HydratedLatticeEvidencePackError("manifest assessmentSchema mismatch")
    if manifest.get("status") != replayed.get("status"):
        raise HydratedLatticeEvidencePackError("manifest status mismatch")

    return {
        "schema": PACK_SCHEMA,
        "status": "verified",
        "assessmentStatus": replayed["status"],
        "sha256": _sha256(pack_bytes),
        "externalIntegrityBound": externally_bound,
        "verificationBoundary": (
            "externally_bound_exact_bytes_plus_local_replay"
            if externally_bound
            else "local_replay_consistency_only"
        ),
    }
