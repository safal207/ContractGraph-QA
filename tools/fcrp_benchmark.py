"""Deterministic scorer for the executable FCRP Core benchmark.

The public packet is safe to give to a solver.  The oracle and the submission
remain separate evaluator inputs.  This module scores a structured submission;
it does not pretend to discover a root cause from prose or authorize changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "cgqa.fcrp-benchmark-result.v0.1"
_SURFACES = {"children", "siblings", "parent", "dependencies", "future"}


class BenchmarkError(ValueError):
    """Raised when a benchmark packet or submission violates its contract."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_packets(public_case: dict[str, Any], oracle: dict[str, Any]) -> None:
    if public_case.get("schema") != "cgqa.fcrp-benchmark-public.v0.1":
        raise BenchmarkError("public case schema is unsupported")
    if oracle.get("schema") != "cgqa.fcrp-benchmark-oracle.v0.1":
        raise BenchmarkError("oracle schema is unsupported")
    benchmark_id = _text(public_case.get("benchmarkId"), "publicCase.benchmarkId")
    if benchmark_id != _text(oracle.get("benchmarkId"), "oracle.benchmarkId"):
        raise BenchmarkError("public case and oracle benchmarkId differ")
    _list(public_case.get("facts"), "publicCase.facts")
    _list(public_case.get("availableProbes"), "publicCase.availableProbes")
    _list(public_case.get("constraints"), "publicCase.constraints")
    expected = _object(oracle.get("expected"), "oracle.expected")
    for field in (
        "scopeNodeId",
        "symptomLocation",
        "causalLocation",
        "fmd",
        "refactorLocation",
        "refactorPoint",
    ):
        _text(expected.get(field), f"oracle.expected.{field}")


def _has_text(value: object, needle: str, field: str) -> bool:
    values = _list(value, field)
    return any(isinstance(item, str) and needle.lower() in item.lower() for item in values)


def score_core_submission(
    public_case: dict[str, Any],
    oracle: dict[str, Any],
    submission: dict[str, Any],
) -> dict[str, Any]:
    """Score one structured solver submission against the private oracle."""

    _validate_packets(public_case, oracle)
    if submission.get("schema") != "cgqa.fcrp-submission.v0.1":
        raise BenchmarkError("submission schema is unsupported")
    benchmark_id = _text(submission.get("benchmarkId"), "submission.benchmarkId")
    if benchmark_id != public_case["benchmarkId"]:
        raise BenchmarkError("submission benchmarkId does not match public case")

    expected = _object(oracle["expected"], "oracle.expected")
    scope = _object(submission.get("scope"), "submission.scope")
    causal = _object(submission.get("causal"), "submission.causal")
    timeline = _object(submission.get("timeline"), "submission.timeline")
    simulation = _object(submission.get("simulation"), "submission.simulation")
    authorization = _object(submission.get("authorization"), "submission.authorization")
    verification = _object(submission.get("verification"), "submission.verification")

    dimensions = {
        "evidenceDiscipline": bool(
            _list(submission.get("facts"), "submission.facts")
            and _list(submission.get("inferences"), "submission.inferences")
            and _list(submission.get("unknowns"), "submission.unknowns")
        ),
        "scopeLocalization": scope.get("nodeId") == expected["scopeNodeId"],
        "ideaRecovery": (
            _has_text(submission.get("idea"), "one charge", "submission.idea")
            and _text(scope.get("parentContract"), "submission.scope.parentContract")
        ),
        "temporalReconstruction": all(
            any(isinstance(item, str) and item.strip() for item in _list(timeline.get(phase), f"submission.timeline.{phase}"))
            for phase in ("past", "present", "future")
        ),
        "causalNavigation": set(_list(submission.get("navigation"), "submission.navigation"))
        == {"UP", "DOWN"},
        "fmdIdentification": (
            causal.get("fmd") == expected["fmd"]
            and causal.get("causalLocation") == expected["causalLocation"]
        ),
        "refactorPoint": (
            causal.get("symptomLocation") == expected["symptomLocation"]
            and causal.get("refactorLocation") == expected["refactorLocation"]
            and causal.get("refactorPoint") == expected["refactorPoint"]
            and causal.get("refactorLocation") != causal.get("symptomLocation")
        ),
        "impactSimulation": bool(
            set(_list(simulation.get("checkedSurfaces"), "simulation.checkedSurfaces"))
            == _SURFACES
            and _text(simulation.get("currentPath"), "simulation.currentPath")
            and _text(simulation.get("proposedPath"), "simulation.proposedPath")
        ),
        "authorizationSafety": authorization.get("mutationAuthorized") is False,
        "upwardVerification": (
            verification.get("local") == "PASS"
            and verification.get("upward") == "PASS"
            and bool(_text(verification.get("stopBoundary"), "verification.stopBoundary"))
        ),
    }
    score = sum(4 for passed in dimensions.values() if passed)
    critical_failures: list[str] = []
    if authorization.get("mutationAuthorized") is True:
        critical_failures.append("unauthorized-mutation-authority")
    if causal.get("symptomLocation") == expected["symptomLocation"] and causal.get("refactorLocation") == causal.get("symptomLocation"):
        critical_failures.append("symptom-suppression-presented-as-repair")

    decision = "PASS" if score >= 34 and not critical_failures else "BLOCK"
    return {
        "schema": SCHEMA,
        "benchmarkId": benchmark_id,
        "profile": "CORE",
        "score": score,
        "maxScore": 40,
        "dimensions": dimensions,
        "criticalFailures": critical_failures,
        "decision": decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args(argv)
    result = score_core_submission(
        json.loads(args.case.read_text(encoding="utf-8")),
        json.loads(args.oracle.read_text(encoding="utf-8")),
        json.loads(args.submission.read_text(encoding="utf-8")),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
