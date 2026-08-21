"""Deterministic measurement-provenance gate.

The gate constrains downstream decisions to the schema epoch and coverage scope
actually represented by a measurement. It intentionally keeps "unmeasured"
separate from a negative observation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MeasurementProvenanceError(ValueError):
    """Raised when measurement-provenance input is invalid or ambiguous."""


@dataclass(frozen=True)
class MeasurementSpec:
    id: str
    schema_epoch: int
    required_schema_epoch: int
    coverage_scope: str
    observed_units: int | None
    eligible_units: int | None
    required_coverage: float
    measurement_available: bool


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MeasurementProvenanceError(f"{label} must be a non-empty string")
    return value.strip()


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MeasurementProvenanceError(f"{label} must be an integer >= {minimum}")
    return value


def _require_fraction(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementProvenanceError(f"{label} must be a number between 0 and 1")
    fraction = float(value)
    if not 0.0 <= fraction <= 1.0:
        raise MeasurementProvenanceError(f"{label} must be between 0 and 1")
    return fraction


def _parse_measurement(data: object, label: str) -> MeasurementSpec:
    if not isinstance(data, dict):
        raise MeasurementProvenanceError(f"{label} must be an object")

    expected = {
        "id",
        "schemaEpoch",
        "requiredSchemaEpoch",
        "coverageScope",
        "observedUnits",
        "eligibleUnits",
        "requiredCoverage",
        "measurementAvailable",
    }
    if set(data) != expected:
        raise MeasurementProvenanceError(
            f"{label} must contain exactly {', '.join(sorted(expected))}"
        )

    measurement_available = data["measurementAvailable"]
    if not isinstance(measurement_available, bool):
        raise MeasurementProvenanceError(f"{label}.measurementAvailable must be boolean")

    observed_raw = data["observedUnits"]
    eligible_raw = data["eligibleUnits"]
    if measurement_available:
        observed_units = _require_int(observed_raw, f"{label}.observedUnits")
        eligible_units = _require_int(eligible_raw, f"{label}.eligibleUnits", minimum=1)
        if observed_units > eligible_units:
            raise MeasurementProvenanceError(
                f"{label}.observedUnits cannot exceed eligibleUnits"
            )
    else:
        if observed_raw is not None or eligible_raw is not None:
            raise MeasurementProvenanceError(
                f"{label} must use null observedUnits/eligibleUnits when measurementAvailable is false"
            )
        observed_units = None
        eligible_units = None

    return MeasurementSpec(
        id=_require_text(data["id"], f"{label}.id"),
        schema_epoch=_require_int(data["schemaEpoch"], f"{label}.schemaEpoch", minimum=1),
        required_schema_epoch=_require_int(
            data["requiredSchemaEpoch"], f"{label}.requiredSchemaEpoch", minimum=1
        ),
        coverage_scope=_require_text(data["coverageScope"], f"{label}.coverageScope"),
        observed_units=observed_units,
        eligible_units=eligible_units,
        required_coverage=_require_fraction(data["requiredCoverage"], f"{label}.requiredCoverage"),
        measurement_available=measurement_available,
    )


def load_measurement_provenance_input(path: Path) -> tuple[MeasurementSpec, ...]:
    source = path.expanduser().resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeasurementProvenanceError(f"cannot read measurement input {source}: {exc}") from exc

    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "measurements"}:
        raise MeasurementProvenanceError(
            "measurement input must contain exactly schemaVersion and measurements"
        )
    if payload["schemaVersion"] != 1:
        raise MeasurementProvenanceError("measurement input schemaVersion must be 1")

    raw_measurements = payload["measurements"]
    if not isinstance(raw_measurements, list) or not raw_measurements:
        raise MeasurementProvenanceError("measurements must be a non-empty array")

    measurements = tuple(
        _parse_measurement(item, f"measurements[{index}]")
        for index, item in enumerate(raw_measurements)
    )
    ids = [item.id for item in measurements]
    if len(ids) != len(set(ids)):
        raise MeasurementProvenanceError("measurement ids must be unique")
    return tuple(sorted(measurements, key=lambda item: item.id))


def evaluate_measurement(measurement: MeasurementSpec) -> dict[str, Any]:
    """Evaluate one measurement against its declared epoch and coverage requirement."""

    reasons: list[str] = []
    coverage_fraction: float | None = None

    if not measurement.measurement_available:
        reasons.append("UNMEASURED")
    else:
        assert measurement.observed_units is not None
        assert measurement.eligible_units is not None
        coverage_fraction = measurement.observed_units / measurement.eligible_units
        if measurement.schema_epoch != measurement.required_schema_epoch:
            reasons.append("EPOCH_MISMATCH")
        if coverage_fraction + 1e-12 < measurement.required_coverage:
            reasons.append("PARTIAL_COVERAGE")

    return {
        "id": measurement.id,
        "status": "blocked" if reasons else "pass",
        "blocking": bool(reasons),
        "gateReasons": reasons,
        "schemaEpoch": measurement.schema_epoch,
        "requiredSchemaEpoch": measurement.required_schema_epoch,
        "coverageScope": measurement.coverage_scope,
        "observedUnits": measurement.observed_units,
        "eligibleUnits": measurement.eligible_units,
        "coverageFraction": coverage_fraction,
        "requiredCoverage": measurement.required_coverage,
        "measurementAvailable": measurement.measurement_available,
    }


def run_measurement_provenance_gate(measurements: tuple[MeasurementSpec, ...]) -> dict[str, Any]:
    results = [evaluate_measurement(item) for item in measurements]
    blocking_measurements = [item["id"] for item in results if item["blocking"] is True]
    return {
        "schemaVersion": 1,
        "status": "blocked" if blocking_measurements else "pass",
        "blockingMeasurements": blocking_measurements,
        "measurements": results,
    }
