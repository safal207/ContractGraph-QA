#!/usr/bin/env python3
"""Verify the CGQA release SBOM against the built wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from email.parser import BytesParser
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        entries = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(entries) != 1:
            raise RuntimeError(f"expected one METADATA entry, found {len(entries)}")
        metadata = BytesParser().parsebytes(archive.read(entries[0]))
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise RuntimeError("wheel METADATA is missing Name or Version")
    return name, version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    wheel = args.wheel.resolve()
    sbom = json.loads(args.sbom.read_text(encoding="utf-8"))
    name, version = _metadata(wheel)
    digest = _sha256(wheel)

    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.5":
        raise RuntimeError("unsupported SBOM format/version")
    component = sbom.get("metadata", {}).get("component", {})
    if component.get("name") != name or component.get("version") != version:
        raise RuntimeError("SBOM package identity does not match wheel METADATA")
    hashes = component.get("hashes", [])
    if {"alg": "SHA-256", "content": digest} not in hashes:
        raise RuntimeError("SBOM wheel SHA-256 does not match built wheel")
    properties = {item.get("name"): item.get("value") for item in component.get("properties", [])}
    if properties.get("cgqa:source-commit") != args.source_commit:
        raise RuntimeError("SBOM source commit does not match workflow commit")
    if properties.get("cgqa:runtime-dependencies") != "none declared":
        raise RuntimeError("unexpected runtime dependency declaration")

    print(json.dumps({"ok": True, "version": version, "wheelSha256": digest, "sourceCommit": args.source_commit}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
