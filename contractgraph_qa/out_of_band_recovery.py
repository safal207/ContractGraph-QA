from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SYSTEM_CASE = "FCRP-SYSTEM-011"
SCHEMA = "cgqa.out-of-band-recovery-receipt.v0.1"
SUITE_SCHEMA = "cgqa.out-of-band-recovery-suite-receipt.v0.1"
PARENT_SYSTEM_010_HEAD = "09e681d320472ed2706a39b878e32b9309c5c981"
PARENT_SYSTEM_010_RECEIPT_DIGEST = "sha256:165316534e67d10f4ecc255787d840583b49f08ffd6aa3cfc40bb54f3cc597f1"
EVIDENCE_BOUNDARY = "OUT_OF_BAND_PROCESS_TERMINATION_NOT_PHYSICAL_POWER_LOSS"
VERDICT = "OUT_OF_BAND_RECOVERY_OBSERVED_POWER_BOUNDARY_HELD"

CASES = (
    "after_authority_commit",
    "after_temp_fsync",
    "after_projection_commit",
)

EXPECTED = {
    "after_authority_commit": ("STALE", "ALLOW_REBUILD", "HOLD"),
    "after_temp_fsync": ("STALE", "ALLOW_REBUILD", "HOLD"),
    "after_projection_commit": ("HEALTHY", "NO_REBUILD", "HOLD"),
}


class OutOfBandRecoveryError(ValueError):
    """Raised when an out-of-band recovery claim exceeds observed evidence."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _fsync_dir(path: Path) -> None:
    if hasattr(os, "O_DIRECTORY"):
        fd = os.open(str(path), os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write_projection(path: Path, generation: int, *, rename: bool = True) -> Path:
    payload = {
        "schema": "projection.v1",
        "generation": generation,
        "projects": ["alpha", "beta"],
        "pins": ["thread-1"],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        fh.flush()
        os.fsync(fh.fileno())
    if rename:
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    return tmp


def _create_baseline(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    db = root / "authority.db"
    con = sqlite3.connect(db)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        con.execute("CREATE TABLE threads(id TEXT PRIMARY KEY, project TEXT NOT NULL)")
        con.execute("INSERT INTO meta(key, value) VALUES('generation', 1)")
        con.execute("INSERT INTO threads(id, project) VALUES('thread-1', 'alpha')")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        con.close()
    _write_projection(root / "projection.json", 1)


def _read_authority(path: Path) -> dict[str, Any]:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            check = con.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                return {"integrity": "CORRUPT", "generation": None, "error": str(check)}
            row = con.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
            if not row or not isinstance(row[0], int):
                return {"integrity": "CORRUPT", "generation": None, "error": "missing generation"}
            return {"integrity": "VALID", "generation": row[0], "error": None}
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return {"integrity": "CORRUPT", "generation": None, "error": type(exc).__name__}


def _read_projection(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"integrity": "MISSING", "generation": None, "error": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"integrity": "CORRUPT", "generation": None, "error": type(exc).__name__}
    generation = payload.get("generation")
    if not isinstance(generation, int):
        return {"integrity": "CORRUPT", "generation": None, "error": "missing generation"}
    return {"integrity": "VALID", "generation": generation, "error": None}


def observe_storage(root: Path) -> dict[str, Any]:
    authority = _read_authority(root / "authority.db")
    projection = _read_projection(root / "projection.json")
    temp = _read_projection(root / "projection.json.tmp")

    if authority["integrity"] != "VALID":
        state = "UNPROVABLE"
    elif projection["integrity"] == "MISSING":
        state = "MISSING"
    elif projection["integrity"] == "CORRUPT":
        state = "CORRUPT"
    elif projection["generation"] > authority["generation"]:
        state = "UNPROVABLE"
    elif projection["generation"] < authority["generation"]:
        state = "STALE"
    else:
        state = "HEALTHY"

    if authority["integrity"] == "VALID" and state in {"MISSING", "STALE", "CORRUPT"}:
        rebuild = "ALLOW_REBUILD"
    elif state == "HEALTHY":
        rebuild = "NO_REBUILD"
    else:
        rebuild = "HOLD"

    return {
        "observerPid": os.getpid(),
        "observerMode": "read-only",
        "authority": authority,
        "projection": projection,
        "tempCandidate": temp,
        "projectionState": state,
        "rebuildDecision": rebuild,
        "executionDecision": "HOLD",
        "tempCandidateAuthority": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
    }


def _write_phase_marker(root: Path, phase: str) -> None:
    marker = root / "subject.ready.json"
    with marker.open("w", encoding="utf-8") as fh:
        json.dump({"phase": phase, "subjectPid": os.getpid()}, fh, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(root)


def run_subject(root: Path, case: str) -> int:
    if case not in CASES:
        raise OutOfBandRecoveryError(f"unknown case: {case}")

    con = sqlite3.connect(root / "authority.db")
    try:
        con.execute("PRAGMA synchronous=FULL")
        con.execute("UPDATE meta SET value=2 WHERE key='generation'")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        con.close()

    if case == "after_authority_commit":
        _write_phase_marker(root, case)
    else:
        tmp = _write_projection(root / "projection.json", 2, rename=False)
        if case == "after_temp_fsync":
            _write_phase_marker(root, case)
        else:
            os.replace(tmp, root / "projection.json")
            _fsync_dir(root)
            _write_phase_marker(root, case)

    # The subject never terminates itself. The supervisor must kill it externally.
    while True:
        time.sleep(1.0)


def _wait_for_marker(root: Path, timeout: float = 10.0) -> dict[str, Any]:
    marker = root / "subject.ready.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            return json.loads(marker.read_text(encoding="utf-8"))
        time.sleep(0.02)
    raise OutOfBandRecoveryError("subject did not reach requested fault phase")


def _run_cold_observer(root: Path) -> dict[str, Any]:
    output = root / "cold-observation.json"
    cmd = [
        sys.executable,
        "-m",
        "contractgraph_qa.out_of_band_recovery",
        "observe",
        "--root",
        str(root),
        "--output",
        str(output),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return json.loads(output.read_text(encoding="utf-8"))


def probe_outer_capabilities() -> dict[str, Any]:
    docker_cli = shutil.which("docker")
    docker_daemon = False
    if docker_cli:
        try:
            proc = subprocess.run(
                [docker_cli, "info", "--format", "{{.ServerVersion}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
            )
            docker_daemon = proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            docker_daemon = False

    qemu_binary = shutil.which("qemu-system-x86_64") is not None
    kvm_path = Path("/dev/kvm")
    kvm_accessible = kvm_path.exists() and os.access(kvm_path, os.R_OK | os.W_OK)
    unshare_binary = shutil.which("unshare") is not None

    return {
        "dockerCliAvailable": docker_cli is not None,
        "dockerDaemonAvailable": docker_daemon,
        "qemuSystemAvailable": qemu_binary,
        "kvmDeviceAccessible": kvm_accessible,
        "unshareBinaryAvailable": unshare_binary,
        "vmHardStopExercised": False,
        "containerHardStopExercised": False,
    }


def finalize_case_receipt(
    *,
    case: str,
    observation: dict[str, Any],
    supervisor_pid: int,
    subject_pid: int,
    parent_head: str = PARENT_SYSTEM_010_HEAD,
    parent_receipt_digest: str = PARENT_SYSTEM_010_RECEIPT_DIGEST,
    external_termination_observed: bool = True,
    self_termination_observed: bool = False,
    physical_power_loss_proven: bool = False,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
) -> dict[str, Any]:
    if case not in EXPECTED:
        raise OutOfBandRecoveryError(f"unknown case: {case}")
    if parent_head != PARENT_SYSTEM_010_HEAD:
        raise OutOfBandRecoveryError("parent SYSTEM-010 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_SYSTEM_010_RECEIPT_DIGEST:
        raise OutOfBandRecoveryError("parent SYSTEM-010 receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise OutOfBandRecoveryError("SYSTEM-011 may not promote its evidence boundary")
    if physical_power_loss_proven:
        raise OutOfBandRecoveryError("external process kill is not physical power loss proof")
    if not external_termination_observed:
        raise OutOfBandRecoveryError("out-of-band receipt requires observed external termination")
    if self_termination_observed:
        raise OutOfBandRecoveryError("subject self-termination cannot satisfy out-of-band evidence")
    if supervisor_pid == subject_pid:
        raise OutOfBandRecoveryError("supervisor must be outside the subject process")
    observer_pid = observation.get("observerPid")
    if not isinstance(observer_pid, int) or observer_pid in {supervisor_pid, subject_pid}:
        raise OutOfBandRecoveryError("cold observer must be a distinct process")
    if observation.get("observerMode") != "read-only":
        raise OutOfBandRecoveryError("cold observer must remain read-only")

    expected_state, expected_rebuild, expected_execution = EXPECTED[case]
    if observation.get("projectionState") != expected_state:
        raise OutOfBandRecoveryError("projection state does not match fault phase")
    if observation.get("rebuildDecision") != expected_rebuild:
        raise OutOfBandRecoveryError("rebuild decision exceeds observed evidence")
    if observation.get("executionDecision") != expected_execution:
        raise OutOfBandRecoveryError("execution continuation must remain HOLD")
    if observation.get("tempCandidateAuthority") is not False:
        raise OutOfBandRecoveryError("temp candidate must never become authority")
    if observation.get("authorityTransfer") != "NONE":
        raise OutOfBandRecoveryError("verification must transfer no authority")
    for field in ("executionAuthorized", "mutationAuthorized", "externalEffectsPerformed"):
        if observation.get(field) is not False:
            raise OutOfBandRecoveryError(f"{field} must remain false")

    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "faultCase": case,
        "parent": {
            "systemCase": "FCRP-SYSTEM-010",
            "head": parent_head,
            "blockDeviceReceiptDigest": parent_receipt_digest,
        },
        "subjectBoundary": "SEPARATE_PROCESS",
        "terminationInitiator": "SUPERVISOR",
        "externalTerminationObserved": True,
        "selfTerminationObserved": False,
        "coldRestartObserver": True,
        "observerMode": "read-only",
        "supervisorPid": supervisor_pid,
        "subjectPid": subject_pid,
        "observerPid": observer_pid,
        "projectionState": expected_state,
        "rebuildDecision": expected_rebuild,
        "executionDecision": expected_execution,
        "authorityIntegrity": observation["authority"]["integrity"],
        "authorityGeneration": observation["authority"]["generation"],
        "projectionIntegrity": observation["projection"]["integrity"],
        "projectionGeneration": observation["projection"]["generation"],
        "tempCandidateGeneration": observation["tempCandidate"]["generation"],
        "tempCandidateAuthority": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "physicalPowerLossProven": False,
        "vmHardStopObserved": False,
        "evidenceBoundary": evidence_boundary,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256(unsigned)
    return receipt


def run_fault_case(case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"system-011-{case}-") as tmp:
        root = Path(tmp)
        _create_baseline(root)
        supervisor_pid = os.getpid()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "contractgraph_qa.out_of_band_recovery",
                "subject",
                "--root",
                str(root),
                "--case",
                case,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            marker = _wait_for_marker(root)
            if marker.get("subjectPid") != proc.pid or marker.get("phase") != case:
                raise OutOfBandRecoveryError("subject phase marker identity mismatch")
            subject_pid = proc.pid
            proc.kill()  # External SIGKILL-equivalent from the supervisor process.
            proc.wait(timeout=5)
            observation = _run_cold_observer(root)
            receipt = finalize_case_receipt(
                case=case,
                observation=observation,
                supervisor_pid=supervisor_pid,
                subject_pid=subject_pid,
            )
            return observation, receipt
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)


def run_matrix(output_dir: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    for case in CASES:
        observation, receipt = run_fault_case(case)
        row = {
            "case": case,
            "projectionState": observation["projectionState"],
            "rebuildDecision": observation["rebuildDecision"],
            "executionDecision": observation["executionDecision"],
            "externalTerminationObserved": receipt["externalTerminationObserved"],
            "coldRestartObserver": receipt["coldRestartObserver"],
            "physicalPowerLossProven": receipt["physicalPowerLossProven"],
            "receiptDigest": receipt["receiptDigest"],
            "evidenceBoundary": receipt["evidenceBoundary"],
        }
        rows.append(row)
        if output_dir is not None:
            (output_dir / f"{case}.receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

    capabilities = probe_outer_capabilities()
    unsigned_suite = {
        "schema": SUITE_SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parentSystemCase": "FCRP-SYSTEM-010",
        "parentHead": PARENT_SYSTEM_010_HEAD,
        "parentBlockDeviceReceiptDigest": PARENT_SYSTEM_010_RECEIPT_DIGEST,
        "caseCount": len(rows),
        "allExternalTerminationObserved": all(row["externalTerminationObserved"] for row in rows),
        "allColdRestartObservers": all(row["coldRestartObserver"] for row in rows),
        "allExecutionHeld": all(row["executionDecision"] == "HOLD" for row in rows),
        "strongestExercisedCapability": "EXTERNAL_PROCESS_KILL_OBSERVED",
        "physicalPowerLossProven": False,
        "vmHardStopObserved": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "verdict": VERDICT,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "outerCapabilities": capabilities,
        "caseReceiptDigests": [row["receiptDigest"] for row in rows],
    }
    suite = dict(unsigned_suite)
    suite["receiptDigest"] = _sha256(unsigned_suite)

    if output_dir is not None:
        (output_dir / "matrix.json").write_text(
            json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output_dir / "outer-capabilities.json").write_text(
            json.dumps(capabilities, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output_dir / "out-of-band-suite-receipt.json").write_text(
            json.dumps(suite, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return rows, suite


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_subject = sub.add_parser("subject")
    p_subject.add_argument("--root", type=Path, required=True)
    p_subject.add_argument("--case", choices=CASES, required=True)

    p_observe = sub.add_parser("observe")
    p_observe.add_argument("--root", type=Path, required=True)
    p_observe.add_argument("--output", type=Path, required=True)

    p_matrix = sub.add_parser("matrix")
    p_matrix.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "subject":
        return run_subject(args.root, args.case)
    if args.command == "observe":
        observation = observe_storage(args.root)
        args.output.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0

    rows, suite = run_matrix(args.output)
    for row in rows:
        print(
            row["case"],
            row["projectionState"],
            row["rebuildDecision"],
            row["executionDecision"],
            "external=" + str(row["externalTerminationObserved"]),
        )
    print(f"PASS out-of-band matrix {len(rows)}/{len(CASES)}")
    print("SYSTEM_011_CAPABILITY", suite["strongestExercisedCapability"])
    print("SYSTEM_011_POWER_BOUNDARY", "UNAVAILABLE")
    print("SYSTEM_011_VERDICT", suite["verdict"])
    print("SYSTEM_011_RECEIPT", suite["receiptDigest"])
    print("EVIDENCE_BOUNDARY", suite["evidenceBoundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
