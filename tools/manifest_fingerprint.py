#!/usr/bin/env python3
"""Print the canonical SHA-256 fingerprint for a ContractGraph-QA adapter manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from export_finding import load_json_object, manifest_sha256, validate_manifest


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
