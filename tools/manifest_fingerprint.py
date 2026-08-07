#!/usr/bin/env python3
"""Print the canonical SHA-256 fingerprint for a ContractGraph-QA adapter manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.finding import load_json_object, manifest_sha256, validate_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Adapter manifest JSON")
    args = parser.parse_args()

    manifest = load_json_object(args.manifest, "manifest")
    validate_manifest(manifest)
    print(manifest_sha256(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
