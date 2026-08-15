from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

SYSTEM_CASE = "FCRP-SYSTEM-012"
SCHEMA = "cgqa.container-hard-stop-receipt.v0.1"
SUITE_SCHEMA = "cgqa.container-hard-stop-suite-receipt.v0.1"
PARENT_SYSTEM_011_HEAD = "b3eb2443d870d52a152fed8bbd25bfe9a522886c"
PARENT_SYSTEM_011_RECEIPT_DIGEST = "sha256:eeaca7299b3a47ef24fe3c378cb501a6f9861c08e48946b79fa5ee7cf9f9ef7f"
EVIDENCE_BOUNDARY = "CONTAINER_HARD_STOP_NOT_VM_OR_PHYSICAL_POWER_LOSS"
VERDICT = "CONTAINER_HARD_STOP_RECOVERY_OBSERVED_STRONGER_BOUNDARIES_HELD"
UNAVAILABLE_VERDICT = "CONTAINER_HARD_STOP_UNAVAILABLE_BOUNDARY_HELD"
DEFAULT_IMAGE = "python:3.12-slim"

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


class ContainerHardStopError(ValueError):
    """Raised when a container hard-stop claim exceeds observed evidence."""


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


def create_baseline(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(root / "authority.db")
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
    marker = root / "container.ready.json"
    with marker.open("w", encoding="utf-8") as fh:
        json.dump({"phase": phase, "containerPid": os.getpid()}, fh, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(root)


def run_subject(root: Path, case: str) -> int:
    if case not in CASES:
        raise ContainerHardStopError(f"unknown case: {case}")
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
    while True:
        time.sleep(1.0)


def _docker_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        proc = subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _wait_for_marker(root: Path, timeout: float = 20.0) -> dict[str, Any]:
    marker = root / "container.ready.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            return json.loads(marker.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise ContainerHardStopError("subject container did not reach requested fault phase")


def _image_identity(image: str) -> dict[str, Any]:
    image_id = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
    digests_raw = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"], text=True
    ).strip()
    try:
        digests = json.loads(digests_raw)
    except json.JSONDecodeError:
        digests = []
    return {"image": image, "imageId": image_id, "repoDigests": digests}


def finalize_case_receipt(
    *,
    case: str,
    observation: dict[str, Any],
    subject_container_id: str,
    observer_container_id: str,
    kill_exit_code: int,
    image_identity: dict[str, Any],
    parent_head: str = PARENT_SYSTEM_011_HEAD,
    parent_receipt_digest: str = PARENT_SYSTEM_011_RECEIPT_DIGEST,
    container_hard_stop_observed: bool = True,
    vm_hard_stop_observed: bool = False,
    physical_power_loss_proven: bool = False,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
) -> dict[str, Any]:
    if case not in EXPECTED:
        raise ContainerHardStopError(f"unknown case: {case}")
    if parent_head != PARENT_SYSTEM_011_HEAD:
        raise ContainerHardStopError("parent SYSTEM-011 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_SYSTEM_011_RECEIPT_DIGEST:
        raise ContainerHardStopError("parent SYSTEM-011 receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise ContainerHardStopError("SYSTEM-012 may not promote its evidence boundary")
    if not container_hard_stop_observed:
        raise ContainerHardStopError("receipt requires an observed external container hard-stop")
    if kill_exit_code != 137:
        raise ContainerHardStopError("container hard-stop must be backed by SIGKILL exit code 137")
    if not subject_container_id or not observer_container_id or subject_container_id == observer_container_id:
        raise ContainerHardStopError("cold observer must run in a distinct container")
    if vm_hard_stop_observed:
        raise ContainerHardStopError("container evidence cannot claim VM hard-stop")
    if physical_power_loss_proven:
        raise ContainerHardStopError("container hard-stop is not physical power-loss proof")
    if observation.get("observerMode") != "read-only":
        raise ContainerHardStopError("cold container observer must remain read-only")
    expected_state, expected_rebuild, expected_execution = EXPECTED[case]
    if observation.get("projectionState") != expected_state:
        raise ContainerHardStopError("projection state does not match fault phase")
    if observation.get("rebuildDecision") != expected_rebuild:
        raise ContainerHardStopError("rebuild decision exceeds observed evidence")
    if observation.get("executionDecision") != expected_execution:
        raise ContainerHardStopError("execution continuation must remain HOLD")
    if observation.get("tempCandidateAuthority") is not False:
        raise ContainerHardStopError("temp candidate must never become authority")
    if observation.get("authorityTransfer") != "NONE":
        raise ContainerHardStopError("verification must transfer no authority")
    for field in ("executionAuthorized", "mutationAuthorized", "externalEffectsPerformed"):
        if observation.get(field) is not False:
            raise ContainerHardStopError(f"{field} must remain false")
    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "faultCase": case,
        "parent": {
            "systemCase": "FCRP-SYSTEM-011",
            "head": parent_head,
            "outOfBandReceiptDigest": parent_receipt_digest,
        },
        "subjectContainerId": subject_container_id,
        "observerContainerId": observer_container_id,
        "containerHardStopObserved": True,
        "containerKillExitCode": kill_exit_code,
        "observerMountMode": "read-only",
        "projectionState": expected_state,
        "rebuildDecision": expected_rebuild,
        "executionDecision": expected_execution,
        "tempCandidateAuthority": False,
        "vmHardStopObserved": False,
        "physicalPowerLossProven": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "imageIdentity": image_identity,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256(unsigned)
    return receipt


def run_case(case: str, repo_root: Path, image: str = DEFAULT_IMAGE) -> dict[str, Any]:
    if not _docker_available():
        raise ContainerHardStopError("docker runtime unavailable")
    subprocess.run(["docker", "pull", image], check=True, stdout=subprocess.DEVNULL)
    image_identity = _image_identity(image)
    with tempfile.TemporaryDirectory(prefix=f"system-012-{case}-") as tmp:
        root = Path(tmp).resolve()
        create_baseline(root)
        token = hashlib.sha256(f"{case}-{time.time_ns()}".encode()).hexdigest()[:12]
        subject_name = f"cgqa-s012-subject-{token}"
        observer_name = f"cgqa-s012-observer-{token}"
        repo = repo_root.resolve()
        subject_cmd = [
            "docker", "run", "-d", "--name", subject_name,
            "-v", f"{repo}:/repo:ro", "-v", f"{root}:/state:rw",
            "-w", "/repo", "-e", "PYTHONPATH=/repo", image,
            "python", "-m", "contractgraph_qa.container_hard_stop", "subject",
            "--root", "/state", "--case", case,
        ]
        subject_container_id = subprocess.check_output(subject_cmd, text=True).strip()
        observer_container_id = ""
        try:
            _wait_for_marker(root)
            subprocess.run(["docker", "kill", "--signal=KILL", subject_name], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["docker", "wait", subject_name], check=True, stdout=subprocess.DEVNULL)
            kill_exit_code = int(
                subprocess.check_output(["docker", "inspect", subject_name, "--format", "{{.State.ExitCode}}"], text=True).strip()
            )
            observer_cmd = [
                "docker", "run", "--name", observer_name,
                "-v", f"{repo}:/repo:ro", "-v", f"{root}:/state:ro",
                "-w", "/repo", "-e", "PYTHONPATH=/repo", image,
                "python", "-m", "contractgraph_qa.container_hard_stop", "observe", "--root", "/state",
            ]
            proc = subprocess.run(observer_cmd, check=True, capture_output=True, text=True)
            observer_container_id = subprocess.check_output(
                ["docker", "inspect", observer_name, "--format", "{{.Id}}"], text=True
            ).strip()
            observation = json.loads(proc.stdout)
            return finalize_case_receipt(
                case=case,
                observation=observation,
                subject_container_id=subject_container_id,
                observer_container_id=observer_container_id,
                kill_exit_code=kill_exit_code,
                image_identity=image_identity,
            )
        finally:
            subprocess.run(["docker", "rm", "-f", subject_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", "-f", observer_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_matrix(output_dir: Path, repo_root: Path, image: str = DEFAULT_IMAGE) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not _docker_available():
        body = {
            "schema": SUITE_SCHEMA,
            "systemCase": SYSTEM_CASE,
            "parentHead": PARENT_SYSTEM_011_HEAD,
            "parentOutOfBandReceiptDigest": PARENT_SYSTEM_011_RECEIPT_DIGEST,
            "containerRuntimeAvailable": False,
            "strongestExercisedCapability": "EXTERNAL_PROCESS_KILL_ONLY",
            "containerHardStopObserved": False,
            "vmHardStopObserved": False,
            "physicalPowerLossProven": False,
            "executionDecision": "HOLD",
            "authorityTransfer": "NONE",
            "executionAuthorized": False,
            "mutationAuthorized": False,
            "externalEffectsPerformed": False,
            "verdict": UNAVAILABLE_VERDICT,
            "evidenceBoundary": EVIDENCE_BOUNDARY,
            "caseCount": 0,
            "caseReceiptDigests": [],
        }
        body["receiptDigest"] = _sha256(body)
        (output_dir / "container-hard-stop-suite-receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
        return body

    receipts = []
    for case in CASES:
        receipt = run_case(case, repo_root, image=image)
        receipts.append(receipt)
        (output_dir / f"{case}.receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    body = {
        "schema": SUITE_SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parentHead": PARENT_SYSTEM_011_HEAD,
        "parentOutOfBandReceiptDigest": PARENT_SYSTEM_011_RECEIPT_DIGEST,
        "containerRuntimeAvailable": True,
        "strongestExercisedCapability": "CONTAINER_HARD_STOP_OBSERVED",
        "containerHardStopObserved": True,
        "vmHardStopObserved": False,
        "physicalPowerLossProven": False,
        "allExecutionHeld": all(r["executionDecision"] == "HOLD" for r in receipts),
        "allDistinctColdContainers": all(r["subjectContainerId"] != r["observerContainerId"] for r in receipts),
        "allSigkillExit137": all(r["containerKillExitCode"] == 137 for r in receipts),
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "verdict": VERDICT,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "caseCount": len(receipts),
        "caseReceiptDigests": [r["receiptDigest"] for r in receipts],
        "imageIdentity": receipts[0]["imageIdentity"],
    }
    body["receiptDigest"] = _sha256(body)
    (output_dir / "container-hard-stop-suite-receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_subject = sub.add_parser("subject")
    p_subject.add_argument("--root", type=Path, required=True)
    p_subject.add_argument("--case", choices=CASES, required=True)
    p_observe = sub.add_parser("observe")
    p_observe.add_argument("--root", type=Path, required=True)
    p_matrix = sub.add_parser("matrix")
    p_matrix.add_argument("--output", type=Path, required=True)
    p_matrix.add_argument("--repo-root", type=Path, default=Path.cwd())
    p_matrix.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()
    if args.command == "subject":
        return run_subject(args.root, args.case)
    if args.command == "observe":
        print(json.dumps(observe_storage(args.root), sort_keys=True))
        return 0
    suite = run_matrix(args.output, args.repo_root, image=args.image)
    print("SYSTEM_012_CAPABILITY", suite["strongestExercisedCapability"])
    print("SYSTEM_012_CONTAINER_HARD_STOP", str(suite["containerHardStopObserved"]).upper())
    print("SYSTEM_012_VM_HARD_STOP", str(suite["vmHardStopObserved"]).upper())
    print("SYSTEM_012_POWER_LOSS_PROVEN", str(suite["physicalPowerLossProven"]).upper())
    print("SYSTEM_012_VERDICT", suite["verdict"])
    print("SYSTEM_012_RECEIPT", suite["receiptDigest"])
    print("EVIDENCE_BOUNDARY", suite["evidenceBoundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
