#!/usr/bin/env python3
"""Derive source-bound measurement provenance from real change-gate coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.change_gate import load_change_gate_config
from contractgraph_qa.change_gate_measurement import build_change_gate_measurement_artifacts
from contractgraph_qa.measurement_provenance import MeasurementProvenanceError


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeasurementProvenanceError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MeasurementProvenanceError(f"{label} must contain a JSON object")
    return data


def _config_data(
    path: Path, *, allow_missing: bool
) -> tuple[tuple[str, ...], bytes | None]:
    source = path.resolve()
    if allow_missing and not source.exists():
        return (), None
    config = load_change_gate_config(source)
    return tuple(item.id for item in config.models), source.read_bytes()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build source-bound measurement provenance from change-gate model coverage"
    )
    parser.add_argument("--gate-result", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--head-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        gate_result = _load_object(args.gate_result.resolve(), "change-gate result")
        base_ids, base_bytes = _config_data(args.base_config, allow_missing=True)
        head_ids, head_bytes = _config_data(args.head_config, allow_missing=False)
        assert head_bytes is not None
        payload, source = build_change_gate_measurement_artifacts(
            gate_result,
            base_model_ids=base_ids,
            head_model_ids=head_ids,
            base_config_bytes=base_bytes,
            head_config_bytes=head_bytes,
            required_schema_epoch=1,
        )
    except (MeasurementProvenanceError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 10

    _write_json(args.output, payload)
    _write_json(args.source_output, source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
