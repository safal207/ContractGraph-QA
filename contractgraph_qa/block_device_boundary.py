"""Block-device capability and abrupt-power evidence boundary for FCRP-SYSTEM-010.

SYSTEM-010 probes what the current host can safely exercise (loop device attach,
filesystem mount, real block-backed write/fsync) without promoting those
observations to physical power-loss proof.

A hosted job cannot prove the durability semantics of its own abrupt power cut:
terminating the runner destroys the observation channel itself and still does
not control storage-controller/device-cache/torn-sector behavior.  Therefore
this contract keeps the physical-power boundary explicit and fail-closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .recovery_integrity_adapter import canonical_bytes

SYSTEM_CASE = "FCRP-SYSTEM-010"
SCHEMA = "cgqa.block-device-boundary-receipt.v0.1"
PARENT_SYSTEM_009_HEAD = "106ff65f2e8725a41aeb3a80f2f88c7da64b414e"
PARENT_SYSTEM_009_RECEIPT_DIGEST = (
    "sha256:65be6aff67020ebb073fc023ee9e53ca32177d9baa6b0a2de73ab93cd4a93e2e"
)
EVIDENCE_BOUNDARY = "BLOCK_DEVICE_CAPABILITY_NOT_PHYSICAL_POWER_LOSS"
VERDICT = "BLOCK_DEVICE_CAPABILITY_OBSERVED_POWER_BOUNDARY_HELD"


class BlockDeviceBoundaryError(ValueError):
    """Raised when a SYSTEM-010 claim exceeds observed capability evidence."""


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _run(argv: list[str]) -> tuple[bool, str]:
    try:
        cp = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    return cp.returncode == 0, cp.stdout.strip()[-1000:]


def probe_capabilities() -> dict[str, Any]:
    commands = {
        name: shutil.which(name) is not None
        for name in ("sudo", "losetup", "mkfs.ext4", "mount", "umount")
    }
    sudo_noninteractive = False
    if commands["sudo"]:
        sudo_noninteractive, _ = _run(["sudo", "-n", "true"])

    loop_control_present = Path("/dev/loop-control").exists()
    loop_attach = False
    fs_mount = False
    block_write_fsync = False
    loop_error: str | None = None
    mount_error: str | None = None

    with tempfile.TemporaryDirectory(prefix="system-010-") as tmp:
        root = Path(tmp)
        image = root / "block.img"
        with image.open("wb") as fh:
            fh.seek(32 * 1024 * 1024 - 1)
            fh.write(b"\0")
            fh.flush()
            os.fsync(fh.fileno())

        loopdev: str | None = None
        if (
            sudo_noninteractive
            and loop_control_present
            and commands["losetup"]
        ):
            ok, output = _run(["sudo", "losetup", "--find", "--show", str(image)])
            if ok and output:
                loopdev = output.splitlines()[-1].strip()
                loop_attach = loopdev.startswith("/dev/loop")
            else:
                loop_error = output or "loop attach failed"

        try:
            if (
                loopdev
                and commands["mkfs.ext4"]
                and commands["mount"]
                and commands["umount"]
            ):
                ok, output = _run(["sudo", "mkfs.ext4", "-F", "-q", loopdev])
                if not ok:
                    mount_error = output or "mkfs.ext4 failed"
                else:
                    mountpoint = root / "mnt"
                    mountpoint.mkdir()
                    ok, output = _run(["sudo", "mount", loopdev, str(mountpoint)])
                    if not ok:
                        mount_error = output or "mount failed"
                    else:
                        fs_mount = True
                        marker = mountpoint / "marker.bin"
                        try:
                            ok, output = _run(
                                [
                                    "sudo",
                                    "sh",
                                    "-c",
                                    f"printf system-010 > '{marker}' && sync -f '{marker}'",
                                ]
                            )
                            block_write_fsync = ok
                            if not ok:
                                mount_error = output or "block-backed write/fsync failed"
                        finally:
                            _run(["sudo", "umount", str(mountpoint)])
        finally:
            if loopdev:
                _run(["sudo", "losetup", "-d", loopdev])

    return {
        "schema": "cgqa.block-device-capability-observation.v0.1",
        "systemCase": SYSTEM_CASE,
        "commands": commands,
        "sudoNoninteractive": sudo_noninteractive,
        "loopControlPresent": loop_control_present,
        "loopDeviceAttachable": loop_attach,
        "filesystemMountable": fs_mount,
        "blockBackedWriteFsyncObserved": block_write_fsync,
        "abruptRunnerPowerCutObserved": False,
        "physicalPowerLossProven": False,
        "loopError": loop_error,
        "mountError": mount_error,
    }


def finalize_capability_receipt(
    observation: dict[str, Any],
    *,
    parent_head: str = PARENT_SYSTEM_009_HEAD,
    parent_receipt_digest: str = PARENT_SYSTEM_009_RECEIPT_DIGEST,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
) -> dict[str, Any]:
    if parent_head != PARENT_SYSTEM_009_HEAD:
        raise BlockDeviceBoundaryError("parent SYSTEM-009 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_SYSTEM_009_RECEIPT_DIGEST:
        raise BlockDeviceBoundaryError("parent SYSTEM-009 receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise BlockDeviceBoundaryError("SYSTEM-010 may not claim physical power-loss proof")
    if observation.get("systemCase") != SYSTEM_CASE:
        raise BlockDeviceBoundaryError("observation systemCase mismatch")

    for field in (
        "sudoNoninteractive",
        "loopControlPresent",
        "loopDeviceAttachable",
        "filesystemMountable",
        "blockBackedWriteFsyncObserved",
        "abruptRunnerPowerCutObserved",
        "physicalPowerLossProven",
    ):
        if not isinstance(observation.get(field), bool):
            raise BlockDeviceBoundaryError(f"{field} must be boolean")

    if observation["abruptRunnerPowerCutObserved"]:
        raise BlockDeviceBoundaryError(
            "hosted in-band probe cannot claim observation of its own abrupt runner power cut"
        )
    if observation["physicalPowerLossProven"]:
        raise BlockDeviceBoundaryError("physical power-loss proof is outside SYSTEM-010 evidence")
    if observation["filesystemMountable"] and not observation["loopDeviceAttachable"]:
        raise BlockDeviceBoundaryError("filesystem mount capability requires loop-device attachment")
    if observation["blockBackedWriteFsyncObserved"] and not observation["filesystemMountable"]:
        raise BlockDeviceBoundaryError("block-backed fsync observation requires mounted filesystem")

    capability = (
        "BLOCK_BACKED_FSYNC_AVAILABLE"
        if observation["blockBackedWriteFsyncObserved"]
        else "LOOP_FS_AVAILABLE"
        if observation["filesystemMountable"]
        else "LOOP_DEVICE_AVAILABLE"
        if observation["loopDeviceAttachable"]
        else "BLOCK_DEVICE_UNAVAILABLE"
    )

    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parent": {
            "systemCase": "FCRP-SYSTEM-009",
            "head": parent_head,
            "storageFaultReceiptDigest": parent_receipt_digest,
        },
        "observationSha256": _sha256(observation),
        "capability": capability,
        "abruptPowerCapability": "UNAVAILABLE",
        "physicalPowerLossProven": False,
        "executionDecision": "HOLD",
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "verdict": VERDICT,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256(unsigned)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    observation = probe_capabilities()
    receipt = finalize_capability_receipt(observation)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "capability-observation.json").write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "block-device-boundary-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("SYSTEM_010_CAPABILITY", receipt["capability"])
    print("SYSTEM_010_POWER_BOUNDARY", receipt["abruptPowerCapability"])
    print("SYSTEM_010_VERDICT", receipt["verdict"])
    print("SYSTEM_010_RECEIPT", receipt["receiptDigest"])
    print("EVIDENCE_BOUNDARY", receipt["evidenceBoundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
