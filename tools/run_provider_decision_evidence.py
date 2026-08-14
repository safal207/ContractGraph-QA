#!/usr/bin/env python3
"""Build or verify a deterministic provider-grounded payment decision evidence pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.provider_adapter import load_provider_adapter, load_provider_observations
from contractgraph_qa.provider_decision_evidence import (
    build_provider_decision_evidence,
    canonical_evidence_pack_sha256,
    verify_provider_decision_evidence,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision


def _load_object(path: Path, label: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(args: argparse.Namespace) -> int:
    adapter = load_provider_adapter(args.adapter)
    observations = load_provider_observations(args.observations)
    authority = {
        "status": args.authority_status,
        "evidenceRef": args.authority_evidence_ref,
    }
    decision = evaluate_provider_payment_decision(
        adapter,
        observations,
        authority,
        decision_id=args.decision_id,
    )
    pack = build_provider_decision_evidence(adapter, observations, authority, decision)
    _write(args.output, pack)
    print(f"evidencePackSha256={canonical_evidence_pack_sha256(pack)}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    pack = _load_object(args.evidence, "evidence")
    decision = verify_provider_decision_evidence(
        pack,
        expected_pack_sha256=args.expected_pack_sha256,
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build evidence from local reviewed inputs")
    build.add_argument("--adapter", required=True, type=Path)
    build.add_argument("--observations", required=True, type=Path)
    build.add_argument("--authority-status", required=True)
    build.add_argument("--authority-evidence-ref", required=True)
    build.add_argument("--decision-id")
    build.add_argument("--output", required=True, type=Path)
    build.set_defaults(func=_build)

    verify = subparsers.add_parser("verify", help="verify hashes and replay embedded evidence")
    verify.add_argument("--evidence", required=True, type=Path)
    verify.add_argument(
        "--expected-pack-sha256",
        help="trusted externally stored canonical SHA-256 for the complete evidence pack",
    )
    verify.set_defaults(func=_verify)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
