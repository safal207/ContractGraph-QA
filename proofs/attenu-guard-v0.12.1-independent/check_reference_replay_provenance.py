#!/usr/bin/env python3
"""Verify and optionally replay the exact official-v1.2 package report."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PROOF_DIR = Path(__file__).resolve().parent
DRIVER = PROOF_DIR / "replay_reference_releases.py"
PYTHON_PROBE = PROOF_DIR / "reference_python_probe.py"
TYPESCRIPT_PROBE = PROOF_DIR / "reference_ts_probe.cjs"
FIXTURE = PROOF_DIR / "bundle_vectors_v1.json"
COMMITTED_REPORT = PROOF_DIR / "reference_release_report.json"

PINNED = {
    DRIVER: "181e09f34076805c2a43b8ea7cd5527faf4289c6a7b93fd6aa2d5c56db869a5c",
    PYTHON_PROBE: "cd051b7c6b08c6ea7479e2455ee500d1ce72247ad6c01c6faf3c0da255ebbf44",
    TYPESCRIPT_PROBE: "2802a02230fd353cb4d7ecd2fc276b3f6207cff66af77191b436908ab1838107",
    FIXTURE: "54311d68c8342c01ce233f4b1aea251125a4f3323fd9776c01843d3b2f5700ea",
    COMMITTED_REPORT: "0d794ba2624723631a6a58219a401d27df9c2e7b5e11248f91904443b3f67ad7",
}
CASE_ORDER = [
    "valid_bundle_v2_literal",
    "reject_increased_ttl_literal",
    "reject_loosened_ceiling_literal",
    "reject_null_ttl_literal",
    "reject_omitted_ceiling_literal",
    "reject_widened_scope",
]
DEFECT_CASES = {
    "reject_increased_ttl_literal",
    "reject_loosened_ceiling_literal",
    "reject_null_ttl_literal",
    "reject_omitted_ceiling_literal",
}
RESULT_IDENTITIES = {
    "python_before": ("python", "0.11.0", "before", "python"),
    "python_after": ("python", "0.12.1", "after", "python"),
    "typescript_before": ("typescript", "0.6.0", "before", "typescript"),
    "typescript_after": ("typescript", "0.7.1", "after", "typescript"),
}
ARTIFACT_IDENTITIES = {
    "python_before": (
        "attenu_guard-0.11.0-py3-none-any.whl",
        "0.11.0",
        312_444,
        "cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0",
    ),
    "python_after": (
        "attenu_guard-0.12.1-py3-none-any.whl",
        "0.12.1",
        321_186,
        "bccba92a439b1c7bed9314589488b279d6236055d21d32278434b368f3f9c36f",
    ),
    "typescript_before": (
        "attenu-guard-0.6.0.tgz",
        "0.6.0",
        222_495,
        "9099da7270cda6e662a76ddf6ca08bd568bd8232970078cd1e47e76dd2377a13",
    ),
    "typescript_after": (
        "attenu-guard-0.7.1.tgz",
        "0.7.1",
        214_567,
        "0edc239d686ad1a709813f6382549745d3d48d1f5a5354a5d90fb1d4521ea5be",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def _expected_decision(stage: str, name: str) -> str:
    if name == "valid_bundle_v2_literal":
        return "accept"
    if name == "reject_widened_scope":
        return "reject"
    if name in DEFECT_CASES:
        return "accept" if stage == "before" else "reject"
    raise ValueError(f"unknown case: {name}")


def _validate_committed_report() -> None:
    report = json.loads(COMMITTED_REPORT.read_text(encoding="utf-8"))
    if report.get("summary") != {
        "defect_transitions_proved": 8,
        "observations_matched": 24,
        "observations_total": 24,
        "passed": True,
        "stable_control_transitions": 4,
    }:
        raise ValueError("reference report summary mismatch")

    fixture = report.get("fixture")
    expected_fixture = {
        "filename": "bundle_vectors_v1.json",
        "contract": "bundle_vectors_v1",
        "revision": "bundle_vectors_v1.2",
        "sha256": PINNED[FIXTURE],
        "bytes": 146_765,
        "git_blob_sha1": "88aee3fd8b346810423266a51783ee10c80a6b1f",
        "execution_source": "same verified raw bytes parsed once before probes",
    }
    if not isinstance(fixture, dict):
        raise ValueError("reference report fixture section is missing")
    observed_fixture = {
        key: fixture.get(key)
        for key in expected_fixture
    }
    if observed_fixture != expected_fixture:
        raise ValueError("reference report fixture identity mismatch")
    wheel_binding = fixture.get("python_after_wheel_binding")
    if (
        not isinstance(wheel_binding, dict)
        or wheel_binding.get("sha256") != PINNED[FIXTURE]
        or wheel_binding.get("bytes") != 146_765
        or wheel_binding.get("record_size") != 146_765
        or wheel_binding.get("matches_vendored_fixture") is not True
    ):
        raise ValueError("Python 0.12.1 wheel fixture binding mismatch")

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_IDENTITIES):
        raise ValueError("reference report artifact set mismatch")
    for name, (filename, version, size, digest) in ARTIFACT_IDENTITIES.items():
        artifact = artifacts[name]
        if {
            "filename": artifact.get("filename"),
            "version": artifact.get("version"),
            "bytes": artifact.get("bytes"),
            "sha256": artifact.get("sha256"),
            "package": artifact.get("package"),
            "execution_source": artifact.get("execution_source"),
        } != {
            "filename": filename,
            "version": version,
            "bytes": size,
            "sha256": digest,
            "package": "attenu-guard",
            "execution_source": "same verified in-memory bytes",
        }:
            raise ValueError(f"{name}: artifact identity mismatch")

    case_inputs = report.get("case_inputs")
    if not isinstance(case_inputs, dict):
        raise ValueError("reference report case input identity is missing")
    if case_inputs.get("canonicalization") != "sorted-key compact JSON UTF-8":
        raise ValueError("reference report case canonicalization mismatch")
    if case_inputs.get("selected_order") != CASE_ORDER:
        raise ValueError("reference report selected case order mismatch")
    per_case = case_inputs.get("per_case")
    if not isinstance(per_case, dict) or set(per_case) != set(CASE_ORDER):
        raise ValueError("reference report per-case identities mismatch")

    runtimes = report.get("runtime_identities")
    if not isinstance(runtimes, dict) or set(runtimes) != {"python", "typescript"}:
        raise ValueError("reference report runtime identity mismatch")
    results = report.get("results")
    if not isinstance(results, dict) or set(results) != set(RESULT_IDENTITIES):
        raise ValueError("reference report result set mismatch")
    for name, (implementation, version, stage, runtime_key) in RESULT_IDENTITIES.items():
        result = results[name]
        if (
            result.get("implementation") != implementation
            or result.get("package") != "attenu-guard"
            or result.get("version") != version
            or result.get("runtime") != runtimes[runtime_key]
        ):
            raise ValueError(f"{name}: package or runtime identity mismatch")
        cases = result.get("cases")
        if not isinstance(cases, list) or [case.get("name") for case in cases] != CASE_ORDER:
            raise ValueError(f"{name}: case set/order mismatch")
        for case in cases:
            expected = _expected_decision(stage, case["name"])
            if case.get("expected_decision") != expected or case.get("matched") is not True:
                raise ValueError(f"{name}/{case['name']}: observation did not match")
            identity = per_case[case["name"]]
            if (
                case.get("case_sha256") != identity.get("case_sha256")
                or case.get("bundle_sha256") != identity.get("bundle_sha256")
            ):
                raise ValueError(f"{name}/{case['name']}: case identity mismatch")

    expected_probes = {
        "python": {"path": PYTHON_PROBE.name, "sha256": sha256(PYTHON_PROBE)},
        "typescript": {
            "path": TYPESCRIPT_PROBE.name,
            "sha256": sha256(TYPESCRIPT_PROBE),
        },
    }
    if report.get("probes") != expected_probes:
        raise ValueError("reference report probe identity mismatch")
    expected_transitions = {
        "python": {
            "before": "0.11.0",
            "after": "0.12.1",
            "defect_cases_flipped": 4,
            "controls_stable": 2,
            "passed": True,
        },
        "typescript": {
            "before": "0.6.0",
            "after": "0.7.1",
            "defect_cases_flipped": 4,
            "controls_stable": 2,
            "passed": True,
        },
    }
    if report.get("transitions") != expected_transitions:
        raise ValueError("reference report transition summary mismatch")


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
        print("PASS: static official-v1.2 package replay evidence verified")
        print("observations=24/24")
        print("defect_transitions=8/8")
        print("stable_control_transitions=4/4")
        return 0

    artifact_args = {
        "--python-before-wheel": args.python_before_wheel,
        "--python-after-wheel": args.python_after_wheel,
        "--typescript-before-tarball": args.typescript_before_tarball,
        "--typescript-after-tarball": args.typescript_after_tarball,
    }
    missing = [name for name, path in artifact_args.items() if path is None]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="attenu-v12-reference-provenance-") as temporary:
        generated = Path(temporary) / "reference_release_report.json"
        command = [sys.executable, str(DRIVER)]
        for name, path in artifact_args.items():
            command.extend((name, str(path.resolve())))
        command.extend(("--node", args.node, "--report", str(generated)))
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

    print("PASS: official-v1.2 package replay provenance verified")
    print("observations=24/24")
    print("defect_transitions=8/8")
    print("stable_control_transitions=4/4")
    print(f"driver_sha256={sha256(DRIVER)}")
    print(f"python_probe_sha256={sha256(PYTHON_PROBE)}")
    print(f"typescript_probe_sha256={sha256(TYPESCRIPT_PROBE)}")
    print(f"report_sha256={sha256(COMMITTED_REPORT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
