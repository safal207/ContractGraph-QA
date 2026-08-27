#!/usr/bin/env python3
"""Run the deterministic measurement-provenance gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.measurement_provenance import (
    MeasurementProvenanceError,
    load_measurement_provenance_input,
    run_measurement_provenance_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run measurement-provenance gate")
    parser.add_argument("--input", type=Path, required=True, help="Measurement provenance JSON input")
    args = parser.parse_args()

    try:
        measurements = load_measurement_provenance_input(args.input)
        result = run_measurement_provenance_gate(measurements)
    except (MeasurementProvenanceError, OSError, ValueError) as exc:
        print(json.dumps({"schemaVersion": 1, "status": "blocked", "error": str(exc)}, sort_keys=True))
        return 10

    print(json.dumps(result, indent=2, sort_keys=True))
    return 10 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
