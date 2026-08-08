#!/usr/bin/env python3
"""Build a deterministic artifact-level CycloneDX SBOM for a CGQA wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise RuntimeError(f"expected one wheel METADATA entry, found {len(names)}")
        metadata = BytesParser().parsebytes(archive.read(names[0]))
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise RuntimeError("wheel METADATA is missing Name or Version")
    return name, version


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    args = parser.parse_args()

    wheel = args.wheel.resolve()
    name, version = _wheel_metadata(wheel)
    wheel_sha256 = _sha256(wheel)
    purl_name = name.lower().replace("_", "-")
    purl = f"pkg:pypi/{purl_name}@{version}"
    timestamp = datetime.fromtimestamp(args.source_date_epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/safal207/ContractGraph-QA/{args.source_commit}/{wheel_sha256}",
    )

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "bom-ref": purl,
                "name": name,
                "version": version,
                "hashes": [{"alg": "SHA-256", "content": wheel_sha256}],
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "purl": purl,
                "properties": [
                    {"name": "cgqa:source-repository", "value": "https://github.com/safal207/ContractGraph-QA"},
                    {"name": "cgqa:source-commit", "value": args.source_commit},
                    {"name": "cgqa:runtime-dependencies", "value": "none declared"},
                ],
            },
        },
        "components": [],
        "dependencies": [{"ref": purl, "dependsOn": []}],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bom, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"ok": True, "output": str(args.output), "wheelSha256": wheel_sha256, "version": version}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
