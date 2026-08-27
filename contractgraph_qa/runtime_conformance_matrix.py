from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "agent-runtime-conformance-matrix/v0.1"
PROJECTION_SPEC = "witness-projection-conformance/v0.1"
AXES = (
    "projection",
    "replay",
    "explicitAbsence",
    "deadlineBinding",
    "persistence",
    "appendOnly",
    "destructiveMutations",
)
CAPABILITY_STATUSES = {"pass", "fail", "adapter_required", "not_measured"}
MUTATION_STATUSES = {"present", "absent", "not_measured"}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def load_runtime_conformance_matrix(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    validate_runtime_conformance_matrix(document)
    return document


def validate_runtime_conformance_matrix(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise ValueError("runtime conformance matrix must be a JSON object")
    if document.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {SCHEMA_VERSION}")
    if document.get("projectionSpec") != PROJECTION_SPEC:
        raise ValueError(f"projectionSpec must be {PROJECTION_SPEC}")
    if tuple(document.get("axes", ())) != AXES:
        raise ValueError("axes must match the v0.1 axis contract exactly")

    vocabulary = document.get("statusVocabulary")
    if not isinstance(vocabulary, dict):
        raise ValueError("statusVocabulary must be an object")
    if set(vocabulary.get("capability", ())) != CAPABILITY_STATUSES:
        raise ValueError("capability status vocabulary is invalid")
    if set(vocabulary.get("mutationSurface", ())) != MUTATION_STATUSES:
        raise ValueError("mutation-surface status vocabulary is invalid")

    runtimes = document.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        raise ValueError("runtimes must be a non-empty array")

    seen_ids: set[str] = set()
    for index, runtime in enumerate(runtimes):
        _validate_runtime(runtime, index=index, seen_ids=seen_ids)


def summarize_runtime_conformance_matrix(document: dict[str, Any]) -> dict[str, int]:
    validate_runtime_conformance_matrix(document)
    runtimes = document["runtimes"]
    return {
        "runtimeCount": len(runtimes),
        "projectionPassCount": sum(item["projection"]["status"] == "pass" for item in runtimes),
        "projectionFailCount": sum(item["projection"]["status"] == "fail" for item in runtimes),
        "persistencePassCount": sum(item["persistence"] == "pass" for item in runtimes),
        "appendOnlyPassCount": sum(item["appendOnly"] == "pass" for item in runtimes),
        "appendOnlyAdapterRequiredCount": sum(
            item["appendOnly"] == "adapter_required" for item in runtimes
        ),
        "appendOnlyFailCount": sum(item["appendOnly"] == "fail" for item in runtimes),
        "appendOnlyNotMeasuredCount": sum(
            item["appendOnly"] == "not_measured" for item in runtimes
        ),
        "destructiveMutationRuntimeCount": sum(
            item["destructiveMutations"]["status"] == "present" for item in runtimes
        ),
    }


def _validate_runtime(runtime: Any, *, index: int, seen_ids: set[str]) -> None:
    field = f"runtimes[{index}]"
    if not isinstance(runtime, dict):
        raise ValueError(f"{field} must be an object")

    runtime_id = _non_empty_text(runtime.get("id"), f"{field}.id")
    if runtime_id in seen_ids:
        raise ValueError(f"duplicate runtime id: {runtime_id}")
    seen_ids.add(runtime_id)

    _non_empty_text(runtime.get("name"), f"{field}.name")
    _non_empty_text(runtime.get("boundaryType"), f"{field}.boundaryType")
    benchmark_result = _non_empty_text(runtime.get("benchmarkResult"), f"{field}.benchmarkResult")
    if not benchmark_result.startswith("benchmarks/") or not benchmark_result.endswith("/result.json"):
        raise ValueError(f"{field}.benchmarkResult must point to a benchmark result.json")
    _non_empty_text(runtime.get("claimBoundary"), f"{field}.claimBoundary")

    source = runtime.get("source")
    if not isinstance(source, dict):
        raise ValueError(f"{field}.source must be an object")
    _non_empty_text(source.get("repository"), f"{field}.source.repository")
    commit = _non_empty_text(source.get("commit"), f"{field}.source.commit")
    if not _HEX40.fullmatch(commit):
        raise ValueError(f"{field}.source.commit must be a pinned 40-character lowercase SHA")

    projection = runtime.get("projection")
    if not isinstance(projection, dict):
        raise ValueError(f"{field}.projection must be an object")
    projection_status = projection.get("status")
    if projection_status not in {"pass", "fail"}:
        raise ValueError(f"{field}.projection.status must be pass or fail")
    passed = projection.get("passed")
    total = projection.get("total")
    if isinstance(passed, bool) or not isinstance(passed, int):
        raise ValueError(f"{field}.projection.passed must be an integer")
    if isinstance(total, bool) or not isinstance(total, int) or total != 8:
        raise ValueError(f"{field}.projection.total must be 8")
    if passed < 0 or passed > total:
        raise ValueError(f"{field}.projection.passed is outside the score range")
    if (projection_status == "pass") != (passed == total):
        raise ValueError(f"{field}.projection status and score disagree")

    for axis in ("replay", "explicitAbsence", "deadlineBinding", "persistence", "appendOnly"):
        if runtime.get(axis) not in CAPABILITY_STATUSES:
            raise ValueError(f"{field}.{axis} has an invalid capability status")

    mutations = runtime.get("destructiveMutations")
    if not isinstance(mutations, dict):
        raise ValueError(f"{field}.destructiveMutations must be an object")
    mutation_status = mutations.get("status")
    if mutation_status not in MUTATION_STATUSES:
        raise ValueError(f"{field}.destructiveMutations.status is invalid")
    operations = mutations.get("operations")
    if not isinstance(operations, list) or any(
        not isinstance(operation, str) or not operation.strip() for operation in operations
    ):
        raise ValueError(f"{field}.destructiveMutations.operations must be a string array")
    if len(set(operations)) != len(operations):
        raise ValueError(f"{field}.destructiveMutations.operations contains duplicates")
    if mutation_status == "present" and not operations:
        raise ValueError(f"{field} marks destructive mutations present without operations")
    if mutation_status != "present" and operations:
        raise ValueError(f"{field} lists destructive operations without status=present")
    if mutation_status == "present" and runtime.get("appendOnly") == "pass":
        raise ValueError(f"{field} cannot be append-only while destructive mutations are present")
    if runtime.get("appendOnly") == "fail" and mutation_status != "present":
        raise ValueError(f"{field} appendOnly=fail requires an observed destructive mutation surface")


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()
