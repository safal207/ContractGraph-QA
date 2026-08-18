"""Deterministic evidence binding for ASTRA analyses.

The pack binds source inputs and independently recomputed ASTRA outputs without
turning ASTRA prioritization into a security claim. Deterministic ContractGraph-QA
explorers and normal invariant/replay evidence remain authoritative.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Callable

from contractgraph_qa.astra_transition import AstraTransitionError, analyze_transition_path
from contractgraph_qa.astra_state_planes import AstraStatePlaneError, analyze_state_planes
from contractgraph_qa.astra_causal_locality import AstraCausalLocalityError, analyze_causal_locality
from contractgraph_qa.astra_queue import AstraQueueError, compare_queue_ordering

PACK_SCHEMA = "cgqa.astra-evidence-pack.v0.1"
MANIFEST_SCHEMA = "cgqa.astra-evidence-pack-manifest.v0.1"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_ANALYZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "transition": analyze_transition_path,
    "state_planes": analyze_state_planes,
    "causal_locality": analyze_causal_locality,
    "queue": compare_queue_ordering,
}
_AUTHORITY = {
    "classification": "RESEARCH_ONLY",
    "securityCertification": False,
    "productionAuthorization": False,
    "financialAuthorization": False,
    "baselineAuthoritative": True,
}


class AstraEvidenceError(ValueError):
    """Raised when ASTRA evidence input or pack verification fails."""


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _load_source(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AstraEvidenceError(f"unable to read ASTRA evidence input: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AstraEvidenceError(f"invalid ASTRA evidence JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AstraEvidenceError("ASTRA evidence input root must be an object")
    analyses = payload.get("analyses")
    if not isinstance(analyses, dict) or not analyses:
        raise AstraEvidenceError("analyses must be a non-empty object")
    unknown = sorted(set(analyses) - set(_ANALYZERS))
    if unknown:
        raise AstraEvidenceError(f"unknown ASTRA analysis kind(s): {', '.join(unknown)}")
    return payload


def _recompute(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("analyses")
    if not isinstance(raw, dict):
        raise AstraEvidenceError("analyses must be an object")
    results: dict[str, Any] = {}
    for kind in sorted(raw):
        analysis_input = raw[kind]
        if not isinstance(analysis_input, dict):
            raise AstraEvidenceError(f"analyses.{kind} must be an object")
        try:
            results[kind] = _ANALYZERS[kind](analysis_input)
        except (AstraTransitionError, AstraStatePlaneError, AstraCausalLocalityError, AstraQueueError) as exc:
            raise AstraEvidenceError(f"analyses.{kind}: {exc}") from exc
    return {
        "schema_version": "astra-evidence-results-v0.1",
        "baseline_preserved": True,
        "results": results,
        "authority": dict(_AUTHORITY),
    }


def _summary(result: dict[str, Any]) -> bytes:
    kinds = sorted(result["results"])
    lines = [
        "# ASTRA Evidence Pack v0.1",
        "",
        "This pack binds ASTRA source inputs to independently recomputable outputs.",
        "ASTRA is a prioritization/interpretation overlay; deterministic CGQA exploration, replay, and invariant evidence remain authoritative.",
        "",
        "## Bound analyses",
        "",
    ]
    for kind in kinds:
        verdict = result["results"][kind].get("verdict", "n/a")
        lines.append(f"- `{kind}`: `{verdict}`")
    lines.extend([
        "",
        "## Authority boundary",
        "",
        "This artifact does not certify security, authorize production actions, or grant financial authority.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def build_astra_evidence_pack(input_path: Path, output_path: Path) -> dict[str, Any]:
    payload = _load_source(input_path)
    recomputed = _recompute(payload)
    artifacts = {
        "input.json": _canonical_json(payload),
        "results.json": _canonical_json(recomputed),
        "summary.md": _summary(recomputed),
    }
    content_names = ["input.json", "results.json", "summary.md"]
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "packSchema": PACK_SCHEMA,
        "analyses": sorted(recomputed["results"]),
        "entries": [
            {"path": name, "sha256": _sha256(artifacts[name]), "bytes": len(artifacts[name])}
            for name in content_names
        ],
        "authority": dict(_AUTHORITY),
    }
    manifest_bytes = _canonical_json(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in content_names:
            archive.writestr(_zip_entry(name), artifacts[name])
        archive.writestr(_zip_entry("manifest.json"), manifest_bytes)
    return {
        "schema": PACK_SCHEMA,
        "output": str(output_path),
        "sha256": _sha256(output_path.read_bytes()),
        "analyses": sorted(recomputed["results"]),
        "entries": [*content_names, "manifest.json"],
    }


def verify_astra_evidence_pack(pack_path: Path) -> dict[str, Any]:
    names_expected = ["input.json", "results.json", "summary.md", "manifest.json"]
    try:
        with zipfile.ZipFile(pack_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != names_expected:
                raise AstraEvidenceError("ASTRA pack entries are not canonical")
            for info in infos:
                if info.date_time != _FIXED_ZIP_TIME or info.compress_type != zipfile.ZIP_STORED:
                    raise AstraEvidenceError(f"non-canonical ZIP metadata: {info.filename}")
                if info.create_system != 3 or info.external_attr != 0o100644 << 16:
                    raise AstraEvidenceError(f"non-canonical ZIP file mode: {info.filename}")
            blobs = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise AstraEvidenceError(f"unable to read ASTRA evidence pack: {exc}") from exc

    try:
        source = json.loads(blobs["input.json"])
        packed_results = json.loads(blobs["results.json"])
        manifest = json.loads(blobs["manifest.json"])
    except json.JSONDecodeError as exc:
        raise AstraEvidenceError(f"ASTRA pack JSON is invalid: {exc}") from exc

    if not isinstance(source, dict) or not isinstance(packed_results, dict) or not isinstance(manifest, dict):
        raise AstraEvidenceError("ASTRA pack JSON roots must be objects")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("packSchema") != PACK_SCHEMA:
        raise AstraEvidenceError("ASTRA manifest schema mismatch")
    if manifest.get("authority") != _AUTHORITY:
        raise AstraEvidenceError("ASTRA authority boundary mismatch")
    if blobs["input.json"] != _canonical_json(source) or blobs["results.json"] != _canonical_json(packed_results) or blobs["manifest.json"] != _canonical_json(manifest):
        raise AstraEvidenceError("ASTRA JSON entry is not canonical")

    declared = manifest.get("entries")
    if not isinstance(declared, list) or [item.get("path") if isinstance(item, dict) else None for item in declared] != names_expected[:3]:
        raise AstraEvidenceError("ASTRA manifest entries are not canonical")
    for item in declared:
        name = item["path"]
        if item.get("sha256") != _sha256(blobs[name]) or item.get("bytes") != len(blobs[name]):
            raise AstraEvidenceError(f"ASTRA content hash/size mismatch: {name}")

    recomputed = _recompute(source)
    if _canonical_json(recomputed) != blobs["results.json"]:
        raise AstraEvidenceError("results.json does not match independent ASTRA recomputation")
    if _summary(recomputed) != blobs["summary.md"]:
        raise AstraEvidenceError("summary.md does not match recomputed ASTRA results")
    if manifest.get("analyses") != sorted(recomputed["results"]):
        raise AstraEvidenceError("ASTRA manifest analysis list mismatch")

    return {
        "schema": PACK_SCHEMA,
        "status": "verified",
        "sha256": _sha256(pack_path.read_bytes()),
        "analyses": sorted(recomputed["results"]),
        "baseline_preserved": True,
    }
