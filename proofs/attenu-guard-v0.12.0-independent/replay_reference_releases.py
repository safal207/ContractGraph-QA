#!/usr/bin/env python3
"""Replay the bundle-verifier regression against exact published artifacts.

This is a discriminating before/after proof:

* Python wheel 0.11.0 -> 0.12.0
* npm tarball 0.6.0 -> 0.7.0

The four defect cases use a literal scope subset, so the old scope-difference
gate does not run.  The packages are extracted without installation or
network access after their exact bytes are verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PROOF_DIR = Path(__file__).resolve().parent
PYTHON_PROBE = PROOF_DIR / "reference_python_probe.py"
TYPESCRIPT_PROBE = PROOF_DIR / "reference_ts_probe.cjs"

ARTIFACTS = {
    "python_before": {
        "filename": "attenu_guard-0.11.0-py3-none-any.whl",
        "package": "attenu-guard",
        "version": "0.11.0",
        "sha256": "cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0",
        "bytes": 312_444,
        "format": "wheel",
    },
    "python_after": {
        "filename": "attenu_guard-0.12.0-py3-none-any.whl",
        "package": "attenu-guard",
        "version": "0.12.0",
        "sha256": "0c17b0f14379ac2f85d091abcb30b5180bce0b6e19d97a88a080c985abec5dc7",
        "bytes": 317_617,
        "format": "wheel",
    },
    "typescript_before": {
        "filename": "attenu-guard-0.6.0.tgz",
        "package": "attenu-guard",
        "version": "0.6.0",
        "sha256": "9099da7270cda6e662a76ddf6ca08bd568bd8232970078cd1e47e76dd2377a13",
        "bytes": 222_495,
        "format": "npm-tarball",
    },
    "typescript_after": {
        "filename": "attenu-guard-0.7.0.tgz",
        "package": "attenu-guard",
        "version": "0.7.0",
        "sha256": "6461138a638a2ac991000f4fcf1c84f317aee1155eef6f53bbc5a932e8b30b12",
        "bytes": 214_352,
        "format": "npm-tarball",
    },
}

CASE_ORDER = [
    "literal_subset_base",
    "increased_ttl",
    "loosened_ceiling",
    "unbounded_ttl",
    "dropped_ceiling",
    "widened_scope_control",
]
DEFECT_CASES = {
    "increased_ttl",
    "loosened_ceiling",
    "unbounded_ttl",
    "dropped_ceiling",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_artifact(path: Path, identity: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing artifact: {path}")
    size = path.stat().st_size
    digest = sha256(path)
    if size != identity["bytes"]:
        raise ValueError(
            f"{path.name}: byte count {size}, expected {identity['bytes']}"
        )
    if digest != identity["sha256"]:
        raise ValueError(
            f"{path.name}: SHA-256 {digest}, expected {identity['sha256']}"
        )
    return {
        "filename": identity["filename"],
        "package": identity["package"],
        "version": identity["version"],
        "format": identity["format"],
        "bytes": size,
        "sha256": digest,
    }


def _safe_target(root: Path, member_name: str) -> Path:
    target = (root / member_name).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"archive path escapes extraction root: {member_name!r}") from exc
    return target


def _extract_wheel(path: Path, destination: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            _safe_target(destination, member.filename)
            mode = member.external_attr >> 16
            if (mode & 0o170000) == 0o120000:
                raise ValueError(f"wheel contains a symbolic link: {member.filename!r}")
        archive.extractall(destination)


def _extract_npm_tarball(path: Path, destination: Path) -> Path:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            target = _safe_target(destination, member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"npm tarball contains a non-file member: {member.name!r}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"cannot read npm tarball member: {member.name!r}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    package_root = destination / "package"
    if not (package_root / "package.json").is_file():
        raise ValueError(f"npm tarball has no package/package.json: {path}")
    return package_root


def _run_json(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROOF_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"probe exited {completed.returncode}: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"probe did not emit a JSON object: {' '.join(command)}")
    return value


def _python_probe(extracted: Path, version: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(extracted)
    environment["PYTHONNOUSERSITE"] = "1"
    return _run_json(
        [sys.executable, str(PYTHON_PROBE), version],
        env=environment,
    )


def _typescript_probe(package_root: Path, version: str, node: str) -> dict[str, Any]:
    return _run_json(
        [node, str(TYPESCRIPT_PROBE), str(package_root), version],
    )


def _expected_decision(stage: str, name: str) -> str:
    if name == "literal_subset_base":
        return "accept"
    if name == "widened_scope_control":
        return "reject"
    if name in DEFECT_CASES:
        return "accept" if stage == "before" else "reject"
    raise ValueError(f"unknown case: {name}")


def _validate_probe(
    probe: dict[str, Any],
    *,
    implementation: str,
    version: str,
    stage: str,
) -> list[dict[str, Any]]:
    if probe.get("implementation") != implementation:
        raise ValueError(f"implementation identity mismatch: {probe!r}")
    if probe.get("package") != "attenu-guard" or probe.get("version") != version:
        raise ValueError(f"package identity mismatch: {probe!r}")
    if probe.get("defect_cases") != sorted(DEFECT_CASES):
        raise ValueError(f"defect case declaration mismatch: {probe!r}")

    cases = probe.get("cases")
    if not isinstance(cases, list) or [case.get("name") for case in cases] != CASE_ORDER:
        raise ValueError(f"case list/order mismatch for {implementation} {version}")

    validated: list[dict[str, Any]] = []
    for case in cases:
        name = case["name"]
        expected = _expected_decision(stage, name)
        observed = case.get("decision")
        checks = case.get("checks")
        if not isinstance(checks, dict):
            raise ValueError(f"{implementation} {version} {name}: missing checks")
        if checks.get("integrity") is not True or checks.get("anchor") != "verified":
            raise ValueError(
                f"{implementation} {version} {name}: integrity/anchor control failed"
            )
        if checks.get("containment") is not True:
            raise ValueError(f"{implementation} {version} {name}: containment also failed")

        expected_monotonicity = expected == "accept"
        expected_positions = [] if expected == "accept" else [
            {"reason": "monotonicity", "seq": 1, "node": "t:n1"}
        ]
        matched = (
            observed == expected
            and checks.get("monotonicity") is expected_monotonicity
            and case.get("failure_positions") == expected_positions
        )
        if not matched:
            raise ValueError(
                f"{implementation} {version} {name}: expected {expected}, observed {case!r}"
            )
        validated.append({
            **case,
            "expected_decision": expected,
            "matched": True,
        })
    return validated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-before-wheel", type=Path, required=True)
    parser.add_argument("--python-after-wheel", type=Path, required=True)
    parser.add_argument("--typescript-before-tarball", type=Path, required=True)
    parser.add_argument("--typescript-after-tarball", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    supplied = {
        "python_before": args.python_before_wheel,
        "python_after": args.python_after_wheel,
        "typescript_before": args.typescript_before_tarball,
        "typescript_after": args.typescript_after_tarball,
    }
    artifact_report = {
        name: _verified_artifact(path, ARTIFACTS[name])
        for name, path in supplied.items()
    }

    with tempfile.TemporaryDirectory(prefix="attenu-reference-replay-") as temporary:
        root = Path(temporary)
        py_before_root = root / "python-before"
        py_after_root = root / "python-after"
        ts_before_root = root / "typescript-before"
        ts_after_root = root / "typescript-after"
        for destination in (py_before_root, py_after_root, ts_before_root, ts_after_root):
            destination.mkdir()

        _extract_wheel(supplied["python_before"], py_before_root)
        _extract_wheel(supplied["python_after"], py_after_root)
        ts_before_package = _extract_npm_tarball(
            supplied["typescript_before"], ts_before_root
        )
        ts_after_package = _extract_npm_tarball(
            supplied["typescript_after"], ts_after_root
        )

        raw_results = {
            "python_before": _python_probe(py_before_root, "0.11.0"),
            "python_after": _python_probe(py_after_root, "0.12.0"),
            "typescript_before": _typescript_probe(
                ts_before_package, "0.6.0", args.node
            ),
            "typescript_after": _typescript_probe(
                ts_after_package, "0.7.0", args.node
            ),
        }

    validated_results = {
        "python_before": {
            **raw_results["python_before"],
            "cases": _validate_probe(
                raw_results["python_before"],
                implementation="python",
                version="0.11.0",
                stage="before",
            ),
        },
        "python_after": {
            **raw_results["python_after"],
            "cases": _validate_probe(
                raw_results["python_after"],
                implementation="python",
                version="0.12.0",
                stage="after",
            ),
        },
        "typescript_before": {
            **raw_results["typescript_before"],
            "cases": _validate_probe(
                raw_results["typescript_before"],
                implementation="typescript",
                version="0.6.0",
                stage="before",
            ),
        },
        "typescript_after": {
            **raw_results["typescript_after"],
            "cases": _validate_probe(
                raw_results["typescript_after"],
                implementation="typescript",
                version="0.7.0",
                stage="after",
            ),
        },
    }

    observations = sum(len(result["cases"]) for result in validated_results.values())
    report = {
        "claim": (
            "exact published Python and TypeScript artifacts change all four literal-subset "
            "authority-widening cases from false accept before the fix to monotonicity reject "
            "after the fix, while both controls remain stable"
        ),
        "claim_boundary": (
            "published artifact runtime behavior only; no independent package-to-source "
            "build attestation; HS256 is a deterministic test signer"
        ),
        "artifacts": artifact_report,
        "probes": {
            "python": {
                "path": PYTHON_PROBE.name,
                "sha256": sha256(PYTHON_PROBE),
            },
            "typescript": {
                "path": TYPESCRIPT_PROBE.name,
                "sha256": sha256(TYPESCRIPT_PROBE),
            },
        },
        "results": validated_results,
        "transitions": {
            "python": {
                "before": "0.11.0",
                "after": "0.12.0",
                "defect_cases_flipped": 4,
                "controls_stable": 2,
                "passed": True,
            },
            "typescript": {
                "before": "0.6.0",
                "after": "0.7.0",
                "defect_cases_flipped": 4,
                "controls_stable": 2,
                "passed": True,
            },
        },
        "summary": {
            "passed": True,
            "observations_matched": observations,
            "observations_total": observations,
            "defect_transitions_proved": 8,
        },
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
