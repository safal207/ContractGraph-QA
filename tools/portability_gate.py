#!/usr/bin/env python3
"""Cross-platform installed-wheel smoke gate for ContractGraph-QA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(f"expected exactly one METADATA entry, found {len(metadata_names)}")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
    version = metadata.get("Version")
    if not version:
        raise RuntimeError("wheel METADATA has no Version")
    return version


def _assert_lf_only(path: Path) -> None:
    data = path.read_bytes()
    if b"\r\n" in data:
        raise RuntimeError(f"non-canonical CRLF bytes found in {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel-dir", type=Path, required=True)
    args = parser.parse_args()

    wheels = sorted(args.wheel_dir.resolve().glob("contractgraph_qa-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one ContractGraph-QA wheel, found {len(wheels)}")
    wheel = wheels[0]
    version = _wheel_version(wheel)

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheel)],
        check=True,
    )

    with tempfile.TemporaryDirectory(prefix="cgqa-portability-") as tmp:
        work = Path(tmp)
        version_result = _run([sys.executable, "-m", "contractgraph_qa.cli", "--version"], work)
        expected_version = f"cgqa {version}"
        if version_result.stdout.strip() != expected_version:
            raise RuntimeError(
                f"installed-wheel version mismatch: expected {expected_version!r}, got {version_result.stdout.strip()!r}"
            )

        demo_a = work / "demo-a"
        demo_b = work / "demo-b"
        for demo in (demo_a, demo_b):
            _run(
                [sys.executable, "-m", "contractgraph_qa.cli", "demo", "--output-dir", str(demo)],
                work,
            )
            _run(
                [
                    sys.executable,
                    "-m",
                    "contractgraph_qa.cli",
                    "verify-bundle",
                    str(demo / "CGQA-005.evidence.zip"),
                ],
                work,
            )
            for relative in (
                Path("inputs/manifest.json"),
                Path("inputs/result.json"),
                Path("CGQA-005.finding.json"),
                Path("CGQA-005.md"),
            ):
                _assert_lf_only(demo / relative)

        deterministic_files = (
            "CGQA-005.finding.json",
            "CGQA-005.md",
            "CGQA-005.evidence.zip",
        )
        for name in deterministic_files:
            if (demo_a / name).read_bytes() != (demo_b / name).read_bytes():
                raise RuntimeError(f"non-deterministic installed-wheel demo artifact: {name}")

        summary = {
            "ok": True,
            "version": version,
            "platform": sys.platform,
            "canonicalLf": True,
            "deterministicArtifacts": list(deterministic_files),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
