#!/usr/bin/env python3
"""Replay official v1.2 discrimination rows against exact registry artifacts.

The fixture and all four packages are hash-pinned and frozen in memory before
execution. The probes receive exact case objects parsed from the pinned v1.2
fixture; they do not construct substitute bundles.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
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
FIXTURE = PROOF_DIR / "bundle_vectors_v1.json"
PYTHON_PROBE = PROOF_DIR / "reference_python_probe.py"
TYPESCRIPT_PROBE = PROOF_DIR / "reference_ts_probe.cjs"

FIXTURE_IDENTITY = {
    "filename": "bundle_vectors_v1.json",
    "contract": "bundle_vectors_v1",
    "revision": "bundle_vectors_v1.2",
    "sha256": "54311d68c8342c01ce233f4b1aea251125a4f3323fd9776c01843d3b2f5700ea",
    "bytes": 146_765,
    "git_blob_sha1": "88aee3fd8b346810423266a51783ee10c80a6b1f",
}
WHEEL_FIXTURE_MEMBER = "attenu_guard/vectors/bundles/bundle_vectors_v1.json"

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
        "filename": "attenu_guard-0.12.1-py3-none-any.whl",
        "package": "attenu-guard",
        "version": "0.12.1",
        "sha256": "bccba92a439b1c7bed9314589488b279d6236055d21d32278434b368f3f9c36f",
        "bytes": 321_186,
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
        "filename": "attenu-guard-0.7.1.tgz",
        "package": "attenu-guard",
        "version": "0.7.1",
        "sha256": "0edc239d686ad1a709813f6382549745d3d48d1f5a5354a5d90fb1d4521ea5be",
        "bytes": 214_567,
        "format": "npm-tarball",
    },
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
EXPECTED_AFTER_DETAILS = {
    "reject_increased_ttl_literal": (
        "monotonicity: vectors:n1 not ⊆ parent vectors:n0 "
        "(ttl 7200 > parent 3600)"
    ),
    "reject_loosened_ceiling_literal": (
        "monotonicity: vectors:n1 not ⊆ parent vectors:n0 "
        "(ceiling max_rows<=250000 looser than parent max_rows<=100000)"
    ),
    "reject_null_ttl_literal": (
        "monotonicity: vectors:n1 not ⊆ parent vectors:n0 "
        "(ttl unbounded, parent 3600)"
    ),
    "reject_omitted_ceiling_literal": (
        "monotonicity: vectors:n1 not ⊆ parent vectors:n0 "
        "(ceiling max_rows unbounded, parent holds max_rows<=100000)"
    ),
}
CASE_CANONICALIZATION = "sorted-key compact JSON UTF-8"


class DuplicateMember(ValueError):
    """Raised when the pinned JSON contains duplicate object members."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateMember(f"duplicate JSON member: {key!r}")
        value[key] = item
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_bytes(payload)


def _load_fixture() -> tuple[dict[str, Any], bytes, str]:
    raw = FIXTURE.read_bytes()
    if len(raw) != FIXTURE_IDENTITY["bytes"]:
        raise ValueError(
            f"fixture byte count {len(raw)}, expected {FIXTURE_IDENTITY['bytes']}"
        )
    digest = sha256_bytes(raw)
    if digest != FIXTURE_IDENTITY["sha256"]:
        raise ValueError(
            f"fixture SHA-256 {digest}, expected {FIXTURE_IDENTITY['sha256']}"
        )
    document = json.loads(raw, object_pairs_hook=_strict_object)
    if not isinstance(document, dict):
        raise ValueError("fixture is not a JSON object")
    if document.get("version") != FIXTURE_IDENTITY["contract"]:
        raise ValueError("fixture contract mismatch")
    if document.get("revision") != FIXTURE_IDENTITY["revision"]:
        raise ValueError("fixture revision mismatch")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 17:
        raise ValueError("fixture must contain exactly 17 cases")
    by_name = {case.get("name"): case for case in cases if isinstance(case, dict)}
    if len(by_name) != len(cases):
        raise ValueError("fixture has duplicate or malformed case names")
    if any(name not in by_name for name in CASE_ORDER):
        raise ValueError("fixture is missing a replay case")
    selected = [by_name[name] for name in CASE_ORDER]
    probe_document = {
        "version": document["version"],
        "revision": document["revision"],
        "fixture_sha256": digest,
        "cases": selected,
    }
    rendered = json.dumps(
        probe_document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return document, raw, rendered


def _verified_artifact(
    path: Path,
    identity: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    """Read, verify, and freeze one artifact for all later extraction."""
    if not path.is_file():
        raise ValueError(f"missing artifact: {path}")
    payload = path.read_bytes()
    size = len(payload)
    digest = sha256_bytes(payload)
    if size != identity["bytes"]:
        raise ValueError(
            f"{path.name}: byte count {size}, expected {identity['bytes']}"
        )
    if digest != identity["sha256"]:
        raise ValueError(
            f"{path.name}: SHA-256 {digest}, expected {identity['sha256']}"
        )
    return (
        {
            "filename": identity["filename"],
            "package": identity["package"],
            "version": identity["version"],
            "format": identity["format"],
            "bytes": size,
            "sha256": digest,
            "execution_source": "same verified in-memory bytes",
        },
        payload,
    )


def _safe_target(root: Path, member_name: str) -> Path:
    target = (root / member_name).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"archive path escapes extraction root: {member_name!r}") from exc
    return target


def _extract_wheel(payload: bytes, destination: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            _safe_target(destination, member.filename)
            mode = member.external_attr >> 16
            if (mode & 0o170000) == 0o120000:
                raise ValueError(f"wheel contains a symbolic link: {member.filename!r}")
        archive.extractall(destination)


def _extract_npm_tarball(payload: bytes, destination: Path) -> Path:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
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
        raise ValueError("npm tarball has no package/package.json")
    return package_root


def _verify_wheel_fixture(payload: bytes, fixture_raw: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        packaged = archive.read(WHEEL_FIXTURE_MEMBER)
        record_names = [name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
        if len(record_names) != 1:
            raise ValueError("0.12.1 wheel must contain exactly one RECORD")
        record_text = archive.read(record_names[0]).decode("utf-8")
    if packaged != fixture_raw:
        raise ValueError("0.12.1 wheel fixture differs from the vendored fixture")
    record_row = next(
        (row for row in csv.reader(io.StringIO(record_text)) if row[0] == WHEEL_FIXTURE_MEMBER),
        None,
    )
    expected_record_digest = base64.urlsafe_b64encode(
        hashlib.sha256(fixture_raw).digest()
    ).rstrip(b"=").decode("ascii")
    expected_row = [
        WHEEL_FIXTURE_MEMBER,
        f"sha256={expected_record_digest}",
        str(len(fixture_raw)),
    ]
    if record_row != expected_row:
        raise ValueError(f"wheel RECORD fixture row differs: {record_row!r}")
    return {
        "member": WHEEL_FIXTURE_MEMBER,
        "bytes": len(packaged),
        "sha256": sha256_bytes(packaged),
        "record_digest": record_row[1],
        "record_size": int(record_row[2]),
        "matches_vendored_fixture": True,
    }


def _run_json(
    command: list[str],
    *,
    input_text: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROOF_DIR,
        env=env,
        input=input_text,
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


def _python_probe(extracted: Path, version: str, input_text: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(extracted)
    environment["PYTHONNOUSERSITE"] = "1"
    return _run_json(
        [sys.executable, str(PYTHON_PROBE), version],
        input_text=input_text,
        env=environment,
    )


def _typescript_probe(
    package_root: Path,
    version: str,
    node: str,
    input_text: str,
) -> dict[str, Any]:
    return _run_json(
        [node, str(TYPESCRIPT_PROBE), str(package_root), version],
        input_text=input_text,
    )


def _expected_decision(stage: str, name: str) -> str:
    if name == "valid_bundle_v2_literal":
        return "accept"
    if name == "reject_widened_scope":
        return "reject"
    if name in DEFECT_CASES:
        return "accept" if stage == "before" else "reject"
    raise ValueError(f"unknown case: {name}")


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _transition_counts(
    before_cases: list[dict[str, Any]],
    after_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive aggregate transition evidence from validated case observations."""
    if [case.get("name") for case in before_cases] != CASE_ORDER:
        raise ValueError("before transition case order mismatch")
    if [case.get("name") for case in after_cases] != CASE_ORDER:
        raise ValueError("after transition case order mismatch")
    before = {case["name"]: case for case in before_cases}
    after = {case["name"]: case for case in after_cases}
    controls = set(CASE_ORDER) - DEFECT_CASES
    defect_cases_flipped = sum(
        before[name].get("decision") == "accept"
        and after[name].get("decision") == "reject"
        for name in DEFECT_CASES
    )
    controls_stable = sum(
        before[name].get("decision") == after[name].get("decision")
        for name in controls
    )
    return {
        "defect_cases_flipped": defect_cases_flipped,
        "controls_stable": controls_stable,
        "passed": (
            defect_cases_flipped == len(DEFECT_CASES)
            and controls_stable == len(controls)
        ),
    }


def _validate_probe(
    probe: dict[str, Any],
    *,
    implementation: str,
    version: str,
    stage: str,
    expected_case_hashes: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    if probe.get("implementation") != implementation:
        raise ValueError(f"implementation identity mismatch: {probe!r}")
    if probe.get("package") != "attenu-guard" or probe.get("version") != version:
        raise ValueError(f"package identity mismatch: {probe!r}")
    expected_fixture = {
        "contract": FIXTURE_IDENTITY["contract"],
        "revision": FIXTURE_IDENTITY["revision"],
        "sha256": FIXTURE_IDENTITY["sha256"],
    }
    if probe.get("fixture") != expected_fixture:
        raise ValueError(f"fixture identity mismatch: {probe!r}")
    if probe.get("case_canonicalization") != CASE_CANONICALIZATION:
        raise ValueError(f"case canonicalization mismatch: {probe!r}")
    runtime = probe.get("runtime")
    if not isinstance(runtime, dict) or not runtime or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in runtime.items()
    ):
        raise ValueError(f"runtime identity missing or malformed: {probe!r}")

    cases = probe.get("cases")
    if not isinstance(cases, list) or [case.get("name") for case in cases] != CASE_ORDER:
        raise ValueError(f"case list/order mismatch for {implementation} {version}")

    validated: list[dict[str, Any]] = []
    for case in cases:
        name = case["name"]
        expected = _expected_decision(stage, name)
        checks = case.get("checks")
        if not isinstance(checks, dict):
            raise ValueError(f"{implementation} {version} {name}: missing checks")
        if checks.get("integrity") is not True or checks.get("anchor") != "verified":
            raise ValueError(
                f"{implementation} {version} {name}: integrity/anchor control failed"
            )
        if checks.get("containment") is not True:
            raise ValueError(f"{implementation} {version} {name}: containment also failed")
        for digest_key in ("case_sha256", "bundle_sha256"):
            digest = case.get(digest_key)
            if not _is_sha256(digest):
                raise ValueError(
                    f"{implementation} {version} {name}: invalid {digest_key}"
                )
            if digest != expected_case_hashes[name][digest_key]:
                raise ValueError(
                    f"{implementation} {version} {name}: {digest_key} mismatch"
                )

        expected_positions = [] if expected == "accept" else [
            {"reason": "monotonicity", "seq": 1, "node": "vectors:n1"}
        ]
        matched = (
            case.get("decision") == expected
            and checks.get("monotonicity") is (expected == "accept")
            and case.get("failure_positions") == expected_positions
        )
        if not matched:
            raise ValueError(
                f"{implementation} {version} {name}: expected {expected}, observed {case!r}"
            )
        failures = case.get("failure_details")
        if expected == "accept" and failures != []:
            raise ValueError(f"{implementation} {version} {name}: accepted with failures")
        if stage == "after" and name in DEFECT_CASES:
            if not isinstance(failures, list) or len(failures) != 1:
                raise ValueError(f"{implementation} {version} {name}: failure count differs")
            if failures[0].get("detail") != EXPECTED_AFTER_DETAILS[name]:
                raise ValueError(
                    f"{implementation} {version} {name}: dimension detail differs"
                )
        validated.append({**case, "expected_decision": expected, "matched": True})
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

    fixture_document, fixture_raw, probe_input = _load_fixture()
    by_name = {case["name"]: case for case in fixture_document["cases"]}
    expected_case_hashes = {
        name: {
            "case_sha256": _canonical_sha256(by_name[name]),
            "bundle_sha256": _canonical_sha256(by_name[name]["bundle"]),
        }
        for name in CASE_ORDER
    }

    supplied = {
        "python_before": args.python_before_wheel,
        "python_after": args.python_after_wheel,
        "typescript_before": args.typescript_before_tarball,
        "typescript_after": args.typescript_after_tarball,
    }
    frozen_artifacts = {
        name: _verified_artifact(path, ARTIFACTS[name])
        for name, path in supplied.items()
    }
    artifact_report = {name: frozen[0] for name, frozen in frozen_artifacts.items()}
    artifact_payloads = {name: frozen[1] for name, frozen in frozen_artifacts.items()}
    wheel_fixture = _verify_wheel_fixture(
        artifact_payloads["python_after"], fixture_raw
    )

    with tempfile.TemporaryDirectory(prefix="attenu-v12-reference-replay-") as temporary:
        root = Path(temporary)
        py_before_root = root / "python-before"
        py_after_root = root / "python-after"
        ts_before_root = root / "typescript-before"
        ts_after_root = root / "typescript-after"
        for destination in (py_before_root, py_after_root, ts_before_root, ts_after_root):
            destination.mkdir()

        _extract_wheel(artifact_payloads["python_before"], py_before_root)
        _extract_wheel(artifact_payloads["python_after"], py_after_root)
        ts_before_package = _extract_npm_tarball(
            artifact_payloads["typescript_before"], ts_before_root
        )
        ts_after_package = _extract_npm_tarball(
            artifact_payloads["typescript_after"], ts_after_root
        )

        raw_results = {
            "python_before": _python_probe(py_before_root, "0.11.0", probe_input),
            "python_after": _python_probe(py_after_root, "0.12.1", probe_input),
            "typescript_before": _typescript_probe(
                ts_before_package, "0.6.0", args.node, probe_input
            ),
            "typescript_after": _typescript_probe(
                ts_after_package, "0.7.1", args.node, probe_input
            ),
        }

    identities = {
        "python_before": ("python", "0.11.0", "before"),
        "python_after": ("python", "0.12.1", "after"),
        "typescript_before": ("typescript", "0.6.0", "before"),
        "typescript_after": ("typescript", "0.7.1", "after"),
    }
    validated_results = {
        name: {
            **raw_results[name],
            "cases": _validate_probe(
                raw_results[name],
                implementation=identity[0],
                version=identity[1],
                stage=identity[2],
                expected_case_hashes=expected_case_hashes,
            ),
        }
        for name, identity in identities.items()
    }

    runtime_identities = {
        "python": validated_results["python_before"]["runtime"],
        "typescript": validated_results["typescript_before"]["runtime"],
    }
    if validated_results["python_after"]["runtime"] != runtime_identities["python"]:
        raise ValueError("Python before/after probes used different runtime identities")
    if validated_results["typescript_after"]["runtime"] != runtime_identities["typescript"]:
        raise ValueError("TypeScript before/after probes used different runtime identities")

    observations = sum(len(result["cases"]) for result in validated_results.values())
    transition_counts = {
        "python": _transition_counts(
            validated_results["python_before"]["cases"],
            validated_results["python_after"]["cases"],
        ),
        "typescript": _transition_counts(
            validated_results["typescript_before"]["cases"],
            validated_results["typescript_after"]["cases"],
        ),
    }
    defect_transitions = sum(
        result["defect_cases_flipped"] for result in transition_counts.values()
    )
    stable_control_transitions = sum(
        result["controls_stable"] for result in transition_counts.values()
    )
    transitions_passed = all(
        result["passed"] is True for result in transition_counts.values()
    )
    report = {
        "claim": (
            "the exact official v1.2 literal-subset rows accepted by the vulnerable "
            "Python and TypeScript releases are positioned monotonicity rejects in "
            "the fixed 0.12.1 and 0.7.1 registry artifacts"
        ),
        "claim_boundary": (
            "six exact official case objects and four registry artifacts only; no "
            "package-to-source build attestation or production security claim"
        ),
        "fixture": {
            **FIXTURE_IDENTITY,
            "execution_source": "same verified raw bytes parsed once before probes",
            "python_after_wheel_binding": wheel_fixture,
        },
        "artifacts": artifact_report,
        "case_inputs": {
            "canonicalization": CASE_CANONICALIZATION,
            "selected_order": CASE_ORDER,
            "per_case": expected_case_hashes,
        },
        "runtime_identities": runtime_identities,
        "probes": {
            "python": {"path": PYTHON_PROBE.name, "sha256": sha256(PYTHON_PROBE)},
            "typescript": {
                "path": TYPESCRIPT_PROBE.name,
                "sha256": sha256(TYPESCRIPT_PROBE),
            },
        },
        "results": validated_results,
        "transitions": {
            "python": {
                "before": "0.11.0",
                "after": "0.12.1",
                **transition_counts["python"],
            },
            "typescript": {
                "before": "0.6.0",
                "after": "0.7.1",
                **transition_counts["typescript"],
            },
        },
        "summary": {
            "passed": transitions_passed,
            "observations_matched": observations,
            "observations_total": observations,
            "defect_transitions_proved": defect_transitions,
            "stable_control_transitions": stable_control_transitions,
        },
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
