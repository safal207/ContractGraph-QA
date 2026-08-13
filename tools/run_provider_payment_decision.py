#!/usr/bin/env python3
"""Run the provider → Unified Agent Payment Decision bridge from local JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.provider_adapter import load_provider_adapter, load_provider_observations
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--authority-status", required=True)
    parser.add_argument("--authority-evidence-ref", required=True)
    parser.add_argument("--decision-id")
    args = parser.parse_args()

    result = evaluate_provider_payment_decision(
        load_provider_adapter(args.adapter),
        load_provider_observations(args.observations),
        {
            "status": args.authority_status,
            "evidenceRef": args.authority_evidence_ref,
        },
        decision_id=args.decision_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
