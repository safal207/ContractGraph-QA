#!/usr/bin/env python3
"""Reproduce and byte-compare the published-package before/after report."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


PROOF_DIR = Path(__file__).resolve().parent
DRIVER = PROOF_DIR / "replay_reference_releases.py"
PYTHON_PROBE = PROOF_DIR / "reference_python_probe.py"
TYPESCRIPT_PROBE = PROOF_DIR / "reference_ts_probe.cjs"
COMMITTED_REPORT = PROOF_DIR / "reference_release_report.json"

PINNED = {
    DRIVER: "70ada39fbed2381715a461f60968c3187a3ba636a835561b07a935124b296cba",
    PYTHON_PROBE: "1aca252783d02e996ca7fd1889f42a86a02d97120bfe06f7badbd522347debd0",
    TYPESCRIPT_PROBE: "b990a83a381e6ff00e95274286e30d7196cd051ed6b4e3bb00ce67525c9e72ea",
    COMMITTED_REPORT: "0b2e45dd5c01378cbbb83ca87b875a1d4005b4df7aab2967150be1b3475a9f39",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-before-wheel", type=Path, required=True)
    parser.add_argument("--python-after-wheel", type=Path, required=True)
    parser.add_argument("--typescript-before-tarball", type=Path, required=True)
    parser.add_argument("--typescript-after-tarball", type=Path, required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()

    for path, expected in PINNED.items():
        if not path.is_file():
            return fail(f"missing load-bearing artifact: {path}")
        actual = sha256(path)
        if actual != expected:
            return fail(f"{path.name} SHA-256 {actual}, expected {expected}")

    with tempfile.TemporaryDirectory(prefix="attenu-reference-provenance-") as temporary:
        generated = Path(temporary) / "reference_release_report.json"
        command = [
            sys.executable,
            str(DRIVER),
            "--python-before-wheel",
            str(args.python_before_wheel),
            "--python-after-wheel",
            str(args.python_after_wheel),
            "--typescript-before-tarball",
            str(args.typescript_before_tarball),
            "--typescript-after-tarball",
            str(args.typescript_after_tarball),
            "--node",
            args.node,
            "--report",
            str(generated),
        ]
        completed = subprocess.run(
            command,
            cwd=PROOF_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout, file=sys.stderr, end="")
            print(completed.stderr, file=sys.stderr, end="")
            return fail(f"reference replay exited {completed.returncode}")
        if generated.read_bytes() != COMMITTED_REPORT.read_bytes():
            return fail("committed reference report differs from exact-artifact replay")

    print("PASS: published-package before/after replay provenance verified")
    print("observations=24/24")
    print("defect_transitions=8/8")
    print(f"driver_sha256={sha256(DRIVER)}")
    print(f"python_probe_sha256={sha256(PYTHON_PROBE)}")
    print(f"typescript_probe_sha256={sha256(TYPESCRIPT_PROBE)}")
    print(f"report_sha256={sha256(COMMITTED_REPORT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
