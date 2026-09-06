"""Deterministic Slither JSON normalization into unverified replay seeds."""

from __future__ import annotations

import copy
from typing import Any

from contractgraph_qa.tsse_adapters.common import (
    RESULT_SCHEMA,
    ToolCaptureError,
    _relative_path,
    canonical_bytes,
    canonical_result_hash,
    canonical_sha256,
    executable_basename,
    parse_json_bytes,
    primary_artifact,
    profile_material,
)


SLITHER_OUTPUT_KEYS = {"success", "error", "results"}
SLITHER_RESULTS_KEYS = {"detectors"}
SLITHER_DETECTOR_REQUIRED_KEYS = {
    "check",
    "impact",
    "confidence",
    "description",
    "elements",
}
STATIC_SEED_KEYS = {
    "id",
    "detector",
    "impact",
    "confidence",
    "description",
    "sourceLocations",
    "evidenceRef",
    "verificationStatus",
    "recommendedDynamicTools",
}
SOURCE_LOCATION_KEYS = {"path", "lines"}
RECOMMENDED_DYNAMIC_TOOLS = ("foundry", "echidna", "medusa")
SLITHER_EXECUTABLES = frozenset({"slither", "slither.exe"})


def _requests_json(argv: list[str]) -> bool:
    for index, argument in enumerate(argv):
        if argument == "--json" and index + 1 < len(argv):
            return True
        if argument.startswith("--json=") and argument != "--json=":
            return True
    return False


def _external_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolCaptureError(f"{field} must be a non-empty string")
    return value.strip()


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolCaptureError(f"{field} must be an object")
    return value


def _exact_object(value: object, field: str, keys: set[str]) -> dict[str, Any]:
    item = _object(value, field)
    missing = sorted(keys - set(item))
    unknown = sorted(set(item) - keys)
    if missing:
        raise ToolCaptureError(f"{field} missing required fields: {', '.join(missing)}")
    if unknown:
        raise ToolCaptureError(f"{field} contains unknown fields: {', '.join(unknown)}")
    return item


def _results_object(value: object) -> dict[str, Any]:
    # Slither may add result sections (for example printers or compilations)
    # independently of detectors.  Parse only the detector section we consume;
    # the pinned profile and raw artifact digest retain the rest verbatim.
    return _object(value, "slither.results")


def _locations(elements: object, field: str) -> list[dict[str, Any]]:
    if not isinstance(elements, list) or not elements:
        raise ToolCaptureError(f"{field} must be a non-empty array")
    deduplicated: dict[bytes, dict[str, Any]] = {}
    for index, raw_element in enumerate(elements):
        element_field = f"{field}[{index}]"
        element = _object(raw_element, element_field)
        if "source_mapping" not in element:
            raise ToolCaptureError(f"{element_field}.source_mapping is required")
        mapping = _object(element["source_mapping"], f"{element_field}.source_mapping")
        if "filename_relative" not in mapping or "lines" not in mapping:
            raise ToolCaptureError(
                f"{element_field}.source_mapping requires filename_relative and lines"
            )
        path = _relative_path(
            mapping["filename_relative"],
            f"{element_field}.source_mapping.filename_relative",
        )
        raw_lines = mapping["lines"]
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ToolCaptureError(f"{element_field}.source_mapping.lines must be non-empty")
        lines: list[int] = []
        for line_index, raw_line in enumerate(raw_lines):
            if isinstance(raw_line, bool) or not isinstance(raw_line, int) or raw_line <= 0:
                raise ToolCaptureError(
                    f"{element_field}.source_mapping.lines[{line_index}] must be a positive integer"
                )
            lines.append(raw_line)
        location = {"path": path, "lines": sorted(set(lines))}
        deduplicated[canonical_bytes(location)] = location
    return sorted(
        deduplicated.values(),
        key=lambda item: (item["path"], item["lines"]),
    )


def _static_seeds(
    detectors: object,
    evidence_ref: str,
    subject_paths: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(detectors, list):
        raise ToolCaptureError("slither.results.detectors must be an array")
    deduplicated: dict[bytes, dict[str, Any]] = {}
    for index, raw_detector in enumerate(detectors):
        field = f"slither.results.detectors[{index}]"
        detector = _object(raw_detector, field)
        missing = sorted(SLITHER_DETECTOR_REQUIRED_KEYS - set(detector))
        if missing:
            raise ToolCaptureError(f"{field} missing required fields: {', '.join(missing)}")
        source_locations = _locations(detector["elements"], f"{field}.elements")
        unknown_sources = sorted(
            {item["path"] for item in source_locations} - subject_paths
        )
        if unknown_sources:
            raise ToolCaptureError(
                f"{field} references source paths outside the verified subject manifest: "
                + ", ".join(unknown_sources)
            )
        core = {
            "detector": _external_text(detector["check"], f"{field}.check"),
            "impact": _external_text(detector["impact"], f"{field}.impact"),
            "confidence": _external_text(detector["confidence"], f"{field}.confidence"),
            "description": _external_text(detector["description"], f"{field}.description"),
            "sourceLocations": source_locations,
            "evidenceRef": evidence_ref,
            "verificationStatus": "unverified",
            "recommendedDynamicTools": list(RECOMMENDED_DYNAMIC_TOOLS),
        }
        identity = {
            key: core[key]
            for key in (
                "detector",
                "impact",
                "confidence",
                "description",
                "sourceLocations",
                "evidenceRef",
            )
        }
        key = canonical_bytes(identity)
        candidate = {
            "id": "slither-seed-" + canonical_sha256(identity)[:24],
            **core,
        }
        previous = deduplicated.get(key)
        if previous is None or candidate["description"] < previous["description"]:
            deduplicated[key] = candidate
    return sorted(deduplicated.values(), key=canonical_bytes)


def adapt_slither_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Parse official Slither JSON into static seeds without emitting TSSE."""

    if capture["tool"] != "slither":
        raise ToolCaptureError(
            f"Slither adapter cannot process tool {capture['tool']!r}"
        )
    if executable_basename(capture) not in SLITHER_EXECUTABLES:
        raise ToolCaptureError("Slither argv[0] must be slither or slither.exe")
    if not _requests_json(capture["run"]["argv"]):
        raise ToolCaptureError("Slither argv must record a --json output destination")
    artifact, raw = primary_artifact(capture, verified)
    output = _exact_object(
        parse_json_bytes(raw, f"Slither artifact {artifact['path']}"),
        "slither",
        SLITHER_OUTPUT_KEYS,
    )
    success = output["success"]
    if not isinstance(success, bool):
        raise ToolCaptureError("slither.success must be a boolean")
    error = output["error"]
    if error is not None:
        error = _external_text(error, "slither.error")

    seeds: list[dict[str, Any]] = []
    if success:
        if error is not None:
            raise ToolCaptureError("successful Slither output must have error: null")
        results = _results_object(output["results"])
        subject_paths = {
            item["path"] for item in verified["profileSubjectArtifacts"]
        }
        seeds = _static_seeds(
            results.get("detectors", []),
            artifact["id"],
            subject_paths,
        )
    else:
        results = output["results"]
        if results is not None:
            parsed_results = _results_object(results)
            detectors = parsed_results.get("detectors", [])
            if not isinstance(detectors, list):
                raise ToolCaptureError("slither.results.detectors must be an array")

    profile_hash = canonical_sha256(profile_material(profile))
    run_complete = capture["run"]["termination"] == "completed"
    normalization_status = "complete" if success and run_complete else "inconclusive"
    native_evidence = {
        "status": "static-only" if success else "inconclusive",
        "parser": "slither-json/v0.1",
        "artifactId": artifact["id"],
        "artifactDigest": artifact["digest"],
        "outputHash": canonical_sha256(output),
    }
    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "captureId": capture["captureId"],
        "tool": "slither",
        "toolVersion": capture["toolVersion"],
        "status": "inconclusive",
        "normalizationStatus": normalization_status,
        "scanVerdict": "NOT_ASSESSED",
        "captureHash": canonical_sha256(capture),
        "subjectBundleHash": verified["subjectBundleHash"],
        "profileId": profile["profileId"],
        "profileHash": profile_hash,
        "normalizationHash": canonical_sha256(
            {
                "profileHash": profile_hash,
                "run": capture["run"],
                "nativeEvidence": native_evidence,
                "slitherSuccess": success,
                "toolError": error,
                "staticSeeds": seeds,
            }
        ),
        "subject": {
            "repository": profile["subject"]["repository"],
            "revision": profile["subject"]["revision"],
            "artifacts": verified["subjectArtifacts"],
        },
        "profileArtifactVerification": {
            "status": "verified",
            "subjectBundleHash": verified["subjectBundleHash"],
            "artifacts": verified["profileSubjectArtifacts"],
        },
        "captureSubjectArtifacts": verified["captureSubjectArtifacts"],
        "run": copy.deepcopy(capture["run"]),
        "toolArtifacts": verified["toolArtifacts"],
        "nativeEvidence": native_evidence,
        "slitherSuccess": success,
        "toolError": error,
        "staticSeeds": seeds,
        "claimBoundary": (
            "Slither detector records were parsed from one digest-verified artifact into unverified "
            "static replay seeds. No runtime state, causal transition, TSSE model, TSSE PASS, dynamic "
            "reproduction, source-inventory completeness, or system-security conclusion is emitted."
        ),
        "verificationDebt": [
            "Every static seed requires independent dynamic reproduction and state observation.",
            "Slither binary authenticity, build/compiler equivalence, and source inventory remain unverified.",
            "An empty detector list is not evidence that the reviewed subject is vulnerability-free.",
        ],
    }
    result["resultHash"] = canonical_result_hash(result)
    return result


adapt_capture = adapt_slither_capture

__all__ = [
    "RECOMMENDED_DYNAMIC_TOOLS",
    "SLITHER_DETECTOR_REQUIRED_KEYS",
    "SLITHER_OUTPUT_KEYS",
    "SLITHER_RESULTS_KEYS",
    "SLITHER_EXECUTABLES",
    "SOURCE_LOCATION_KEYS",
    "STATIC_SEED_KEYS",
    "adapt_capture",
    "adapt_slither_capture",
]
