#!/usr/bin/env python3
"""Export deterministic ContractGraph-QA finding JSON from an adapter manifest and explorer result."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.finding import (  # noqa: E402
    canonical_json,
    export_finding,
    load_json_object,
    manifest_sha256,
    validate_manifest,
    validate_result,
)

__all__ = [
    "canonical_json",
    "export_finding",
    "load_json_object",
    "manifest_sha256",
    "validate_manifest",
    "validate_result",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Adapter manifest JSON")
    parser.add_argument("result", type=Path, help="Explorer result JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write exported finding JSON")
    group.add_argument("--check", type=Path, help="Compare with an existing finding JSON")
    args = parser.parse_args()

    manifest = load_json_object(args.manifest, "manifest")
    result = load_json_object(args.result, "result")
    exported = canonical_json(export_finding(manifest, result))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(exported, encoding="utf-8")
        return 0

    expected = args.check.read_text(encoding="utf-8")
    if expected != exported:
        raise SystemExit(f"exported finding differs from {args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
