"""Source binding for measurement provenance over causal change-gate results."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from contractgraph_qa.measurement_provenance import (
    MeasurementProvenanceError,
    MeasurementSpec,
    build_change_gate_model_coverage_input,
    run_measurement_provenance_gate,
)


CHANGE_GATE_MEASUREMENT_SOURCE_SCHEMA = "cgqa.change-gate-measurement-source.v1"
MEASUREMENT_ID = "causal-security-change-gate-model-results"
COVERAGE_SCOPE = "change_gate_base_head_configured_model_results"


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, label: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise MeasurementProvenanceError(f"{label} must be a 64-character SHA-256 hex digest")
    return value.lower()


def change_gate_result_content_sha256(gate_result: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json_bytes(gate_result))


def _canonical_ids(values: Iterable[str], label: str) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise MeasurementProvenanceError(f"{label} must contain non-empty strings")
        items.append(value.strip())
    if len(items) != len(set(items)):
        raise MeasurementProvenanceError(f"{label} must not contain duplicates")
    return tuple(sorted(items))


def _observed_model_ids(gate_result: dict[str, Any]) -> tuple[str, ...]:
    models = gate_result.get("models")
    if not isinstance(models, list):
        raise MeasurementProvenanceError("change-gate result models must be an array")
    values: list[str] = []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            raise MeasurementProvenanceError(f"change-gate result models[{index}] must be an object")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise MeasurementProvenanceError(
                f"change-gate result models[{index}].id must be a non-empty string"
            )
        values.append(model_id.strip())
    return _canonical_ids(values, "observed change-gate model ids")


def build_change_gate_measurement_source(
    gate_result: dict[str, Any],
    *,
    base_model_ids: Iterable[str],
    head_model_ids: Iterable[str],
    base_config_bytes: bytes | None,
    head_config_bytes: bytes,
) -> dict[str, Any]:
    """Bind the coverage denominator/numerator to exact gate and config artifacts."""

    base_ids = _canonical_ids(base_model_ids, "base_model_ids")
    head_ids = _canonical_ids(head_model_ids, "head_model_ids")
    eligible_ids = tuple(sorted(set(base_ids) | set(head_ids)))
    if not eligible_ids:
        raise MeasurementProvenanceError("configured change-gate model population must be non-empty")
    observed_ids = _observed_model_ids(gate_result)
    unexpected = sorted(set(observed_ids) - set(eligible_ids))
    if unexpected:
        raise MeasurementProvenanceError(
            "change-gate result contains model ids outside the base/head config population: "
            + ", ".join(unexpected)
        )
    if not isinstance(head_config_bytes, bytes) or not head_config_bytes:
        raise MeasurementProvenanceError("head config bytes must be non-empty")
    if base_config_bytes is not None and not isinstance(base_config_bytes, bytes):
        raise MeasurementProvenanceError("base config bytes must be bytes or null")

    return {
        "schema": CHANGE_GATE_MEASUREMENT_SOURCE_SCHEMA,
        "measurementId": MEASUREMENT_ID,
        "gateResultSha256": change_gate_result_content_sha256(gate_result),
        "baseConfigSha256": (
            _sha256_bytes(base_config_bytes) if base_config_bytes is not None else None
        ),
        "headConfigSha256": _sha256_bytes(head_config_bytes),
        "eligibleModelIds": list(eligible_ids),
        "observedModelIds": list(observed_ids),
    }


def validate_change_gate_measurement_source(
    source: dict[str, Any],
    *,
    gate_result: dict[str, Any] | None = None,
) -> None:
    """Validate a source receipt and optionally bind it to the exact gate result."""

    if not isinstance(source, dict):
        raise MeasurementProvenanceError("change-gate measurement source must be an object")
    expected = {
        "schema",
        "measurementId",
        "gateResultSha256",
        "baseConfigSha256",
        "headConfigSha256",
        "eligibleModelIds",
        "observedModelIds",
    }
    if set(source) != expected:
        raise MeasurementProvenanceError("change-gate measurement source has invalid shape")
    if source.get("schema") != CHANGE_GATE_MEASUREMENT_SOURCE_SCHEMA:
        raise MeasurementProvenanceError("unsupported change-gate measurement source schema")
    if source.get("measurementId") != MEASUREMENT_ID:
        raise MeasurementProvenanceError("unexpected change-gate measurement id")
    _require_sha256(source.get("gateResultSha256"), "gateResultSha256")
    _require_sha256(source.get("baseConfigSha256"), "baseConfigSha256", allow_none=True)
    _require_sha256(source.get("headConfigSha256"), "headConfigSha256")

    eligible_raw = source.get("eligibleModelIds")
    observed_raw = source.get("observedModelIds")
    if not isinstance(eligible_raw, list) or not eligible_raw:
        raise MeasurementProvenanceError("eligibleModelIds must be a non-empty array")
    if not isinstance(observed_raw, list):
        raise MeasurementProvenanceError("observedModelIds must be an array")
    eligible = _canonical_ids(eligible_raw, "eligibleModelIds")
    observed = _canonical_ids(observed_raw, "observedModelIds")
    if list(eligible) != eligible_raw or list(observed) != observed_raw:
        raise MeasurementProvenanceError("source model ids must be canonically sorted")
    if not set(observed).issubset(set(eligible)):
        raise MeasurementProvenanceError("observedModelIds must be a subset of eligibleModelIds")

    if gate_result is not None:
        expected_gate_sha = change_gate_result_content_sha256(gate_result)
        if source["gateResultSha256"] != expected_gate_sha:
            raise MeasurementProvenanceError("measurement source gate-result digest mismatch")
        if list(_observed_model_ids(gate_result)) != observed_raw:
            raise MeasurementProvenanceError("measurement source observed model ids mismatch")


def build_change_gate_measurement_artifacts(
    gate_result: dict[str, Any],
    *,
    base_model_ids: Iterable[str],
    head_model_ids: Iterable[str],
    base_config_bytes: bytes | None,
    head_config_bytes: bytes,
    required_schema_epoch: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the gate input and its exact source-binding receipt together."""

    payload = build_change_gate_model_coverage_input(
        gate_result,
        base_model_ids=base_model_ids,
        head_model_ids=head_model_ids,
        required_schema_epoch=required_schema_epoch,
    )
    source = build_change_gate_measurement_source(
        gate_result,
        base_model_ids=base_model_ids,
        head_model_ids=head_model_ids,
        base_config_bytes=base_config_bytes,
        head_config_bytes=head_config_bytes,
    )
    return payload, source


def provenance_result_from_change_gate_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Recompute the one-measurement integration result without filesystem input."""

    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "measurements"}:
        raise MeasurementProvenanceError("change-gate measurement input has invalid shape")
    measurements = payload.get("measurements")
    if payload.get("schemaVersion") != 1 or not isinstance(measurements, list) or len(measurements) != 1:
        raise MeasurementProvenanceError(
            "change-gate measurement input must contain exactly one schema-v1 measurement"
        )
    item = measurements[0]
    if not isinstance(item, dict):
        raise MeasurementProvenanceError("change-gate measurement must be an object")
    try:
        spec = MeasurementSpec(
            id=item["id"],
            schema_epoch=item["schemaEpoch"],
            required_schema_epoch=item["requiredSchemaEpoch"],
            coverage_scope=item["coverageScope"],
            observed_units=item["observedUnits"],
            eligible_units=item["eligibleUnits"],
            required_coverage=float(item["requiredCoverage"]),
            measurement_available=item["measurementAvailable"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementProvenanceError(f"invalid change-gate measurement input: {exc}") from exc
    return run_measurement_provenance_gate((spec,))
