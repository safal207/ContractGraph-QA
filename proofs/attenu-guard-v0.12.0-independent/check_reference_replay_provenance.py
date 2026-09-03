#!/usr/bin/env python3
"""Reproduce and byte-compare the published-package before/after report."""
from __future__ import annotations

import argparse
import hashlib
import json
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
    DRIVER: "a97927a9ad9ba7856762a692d037f8ba7b4e0ce597eb450aad0f88c2c4ac4070",
    PYTHON_PROBE: "b2031baab8593ae1245da1a253d5703a7a6517ab68003ee9687d6269e000515e",
    TYPESCRIPT_PROBE: "b6cd21d7c6ee14c800111592ac7200e410b6f0dce2547355a18e714f49d22f41",
    COMMITTED_REPORT: "b0feea64ac84c454aa0f931926771d753fcf1ffc848e7a1a3ef5740cd534cdba",
}
CASE_ORDER = [
    "literal_subset_base",
    "increased_ttl",
    "loosened_ceiling",
    "unbounded_ttl",
    "dropped_ceiling",
    "widened_scope_control",
]
RESULT_IDENTITIES = {
    "python_before": ("python", "0.11.0", "python"),
    "python_after": ("python", "0.12.0", "python"),
    "typescript_before": ("typescript", "0.6.0", "typescript"),
    "typescript_after": ("typescript", "0.7.0", "typescript"),
}
EXPECTED_PROFILE = {
    "canonicalization": "sorted-key compact JSON UTF-8",
    "params_salt_hex": "00" * 16,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def _validate_committed_report() -> None:
    report = json.loads(COMMITTED_REPORT.read_text(encoding="utf-8"))
    if report.get("summary") != {
        "defect_transitions_proved": 8,
        "observations_matched": 24,
        "observations_total": 24,
        "passed": True,
    }:
        raise ValueError("reference report summary mismatch")

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "python_before",
        "python_after",
        "typescript_before",
        "typescript_after",
    }:
        raise ValueError("reference report artifact set mismatch")
    for name, artifact in artifacts.items():
        if artifact.get("execution_source") != "same verified in-memory bytes":
            raise ValueError(f"{name}: artifact execution source is not bound")

    bundle_inputs = report.get("bundle_inputs")
    if not isinstance(bundle_inputs, dict):
        raise ValueError("reference report has no bundle input identity")
    if {
        key: bundle_inputs.get(key)
        for key in ("canonicalization", "params_salt_hex")
    } != EXPECTED_PROFILE:
        raise ValueError("reference report bundle profile mismatch")
    per_case = bundle_inputs.get("per_case_sha256")
    if not isinstance(per_case, dict) or set(per_case) != set(CASE_ORDER):
        raise ValueError("reference report bundle digest set mismatch")

    runtimes = report.get("runtime_identities")
    if not isinstance(runtimes, dict) or set(runtimes) != {"python", "typescript"}:
        raise ValueError("reference report runtime identity mismatch")

    results = report.get("results")
    if not isinstance(results, dict) or set(results) != set(RESULT_IDENTITIES):
        raise ValueError("reference report result set mismatch")
    for name, (implementation, version, runtime_key) in RESULT_IDENTITIES.items():
        result = results[name]
        if (
            result.get("implementation") != implementation
            or result.get("package") != "attenu-guard"
            or result.get("version") != version
        ):
            raise ValueError(f"{name}: package identity mismatch")
        if result.get("runtime") != runtimes[runtime_key]:
            raise ValueError(f"{name}: runtime identity mismatch")
        if result.get("bundle_profile") != EXPECTED_PROFILE:
            raise ValueError(f"{name}: bundle profile mismatch")
        cases = result.get("cases")
        if (
            not isinstance(cases, list)
            or [case.get("name") for case in cases] != CASE_ORDER
        ):
            raise ValueError(f"{name}: case set/order mismatch")
        for case in cases:
            digest = case.get("bundle_sha256")
            if digest != per_case[case["name"]]:
                raise ValueError(f"{name}/{case['name']}: bundle identity mismatch")
            if case.get("matched") is not True:
                raise ValueError(f"{name}/{case['name']}: observation did not match")

    expected_probes = {
        "python": {
            "path": PYTHON_PROBE.name,
            "sha256": sha256(PYTHON_PROBE),
        },
        "typescript": {
            "path": TYPESCRIPT_PROBE.name,
            "sha256": sha256(TYPESCRIPT_PROBE),
        },
    }
    if report.get("probes") != expected_probes:
        raise ValueError("reference report probe identity mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--python-before-wheel", type=Path)
    parser.add_argument("--python-after-wheel", type=Path)
    parser.add_argument("--typescript-before-tarball", type=Path)
    parser.add_argument("--typescript-after-tarball", type=Path)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()

    for path, expected in PINNED.items():
        if not path.is_file():
            return fail(f"missing load-bearing artifact: {path}")
        actual = sha256(path)
        if actual != expected:
            return fail(f"{path.name} SHA-256 {actual}, expected {expected}")

    try:
        _validate_committed_report()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))

    if args.static_only:
        print("PASS: static published-package replay evidence verified")
        print("observations=24/24")
        print("defect_transitions=8/8")
        return 0

    artifact_args = {
        "--python-before-wheel": (
            args.python_before_wheel.resolve() if args.python_before_wheel else None
        ),
        "--python-after-wheel": (
            args.python_after_wheel.resolve() if args.python_after_wheel else None
        ),
        "--typescript-before-tarball": (
            args.typescript_before_tarball.resolve()
            if args.typescript_before_tarball
            else None
        ),
        "--typescript-after-tarball": (
            args.typescript_after_tarball.resolve()
            if args.typescript_after_tarball
            else None
        ),
    }
    missing = [name for name, path in artifact_args.items() if path is None]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="attenu-reference-provenance-") as temporary:
        generated = Path(temporary) / "reference_release_report.json"
        command = [
            sys.executable,
            str(DRIVER),
            "--python-before-wheel",
            str(artifact_args["--python-before-wheel"]),
            "--python-after-wheel",
            str(artifact_args["--python-after-wheel"]),
            "--typescript-before-tarball",
            str(artifact_args["--typescript-before-tarball"]),
            "--typescript-after-tarball",
            str(artifact_args["--typescript-after-tarball"]),
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
