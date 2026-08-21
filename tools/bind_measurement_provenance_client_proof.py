#!/usr/bin/env python3
"""Bind source-verified passing measurement provenance into a client proof pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.change_gate import load_change_gate_config
from contractgraph_qa.change_gate_measurement import (
    build_change_gate_measurement_artifacts,
    provenance_result_from_change_gate_input,
)
from contractgraph_qa.client_proof import (
    attach_measurement_provenance_evidence,
    verify_change_gate_evidence,
)
from contractgraph_qa.measurement_provenance import MeasurementProvenanceError


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def _config_data(
    path: Path, *, allow_missing: bool
) -> tuple[tuple[str, ...], bytes | None]:
    source = path.resolve()
    if allow_missing and not source.exists():
        return (), None
    config = load_change_gate_config(source)
    return tuple(item.id for item in config.models), source.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind source-verified passing measurement provenance into a client proof"
    )
    parser.add_argument("--proof", type=Path, required=True, help="Client proof JSON")
    parser.add_argument("--provenance-result", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--head-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Bound proof JSON")
    args = parser.parse_args()

    try:
        proof = _load_object(args.proof.resolve(), "client proof")
        result = _load_object(args.provenance_result.resolve(), "measurement-provenance result")
        source = _load_object(args.source.resolve(), "measurement source")

        change_evidence = proof.get("changeGateEvidence")
        if not isinstance(change_evidence, dict):
            raise ValueError("client proof must already contain changeGateEvidence")
        gate_result = verify_change_gate_evidence(change_evidence)

        base_ids, base_bytes = _config_data(args.base_config, allow_missing=True)
        head_ids, head_bytes = _config_data(args.head_config, allow_missing=False)
        assert head_bytes is not None
        expected_input, expected_source = build_change_gate_measurement_artifacts(
            gate_result,
            base_model_ids=base_ids,
            head_model_ids=head_ids,
            base_config_bytes=base_bytes,
            head_config_bytes=head_bytes,
            required_schema_epoch=1,
        )
        if source != expected_source:
            raise ValueError("measurement source does not match exact gate/config artifacts")
        expected_result = provenance_result_from_change_gate_input(expected_input)
        if result != expected_result:
            raise ValueError("measurement provenance result does not match rederived gate coverage")

        bound = attach_measurement_provenance_evidence(proof, result, source)
    except (MeasurementProvenanceError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 10

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(bound, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
