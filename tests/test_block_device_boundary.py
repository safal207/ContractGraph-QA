from __future__ import annotations

import copy
import unittest

from contractgraph_qa.block_device_boundary import (
    EVIDENCE_BOUNDARY,
    PARENT_SYSTEM_009_HEAD,
    PARENT_SYSTEM_009_RECEIPT_DIGEST,
    SYSTEM_CASE,
    BlockDeviceBoundaryError,
    finalize_capability_receipt,
)


def observation(**overrides):
    base = {
        "schema": "cgqa.block-device-capability-observation.v0.1",
        "systemCase": SYSTEM_CASE,
        "commands": {},
        "sudoNoninteractive": True,
        "loopControlPresent": True,
        "loopDeviceAttachable": True,
        "filesystemMountable": True,
        "blockBackedWriteFsyncObserved": True,
        "abruptRunnerPowerCutObserved": False,
        "physicalPowerLossProven": False,
        "loopError": None,
        "mountError": None,
    }
    base.update(overrides)
    return base


class BlockDeviceBoundaryTests(unittest.TestCase):
    def test_full_block_capability_still_holds_power_boundary(self) -> None:
        receipt = finalize_capability_receipt(observation())
        self.assertEqual(receipt["capability"], "BLOCK_BACKED_FSYNC_AVAILABLE")
        self.assertEqual(receipt["abruptPowerCapability"], "UNAVAILABLE")
        self.assertFalse(receipt["physicalPowerLossProven"])
        self.assertEqual(receipt["executionDecision"], "HOLD")
        self.assertEqual(receipt["authorityTransfer"], "NONE")

    def test_unavailable_block_device_is_valid_observation_not_failure(self) -> None:
        receipt = finalize_capability_receipt(
            observation(
                sudoNoninteractive=False,
                loopControlPresent=False,
                loopDeviceAttachable=False,
                filesystemMountable=False,
                blockBackedWriteFsyncObserved=False,
            )
        )
        self.assertEqual(receipt["capability"], "BLOCK_DEVICE_UNAVAILABLE")
        self.assertEqual(receipt["executionDecision"], "HOLD")

    def test_parent_head_drift_rejected(self) -> None:
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(
                observation(),
                parent_head=PARENT_SYSTEM_009_HEAD[:-1] + "0",
            )

    def test_parent_receipt_drift_rejected(self) -> None:
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(
                observation(),
                parent_receipt_digest=PARENT_SYSTEM_009_RECEIPT_DIGEST[:-1] + "0",
            )

    def test_physical_power_claim_rejected(self) -> None:
        bad = observation(physicalPowerLossProven=True)
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(bad)

    def test_in_band_runner_power_claim_rejected(self) -> None:
        bad = observation(abruptRunnerPowerCutObserved=True)
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(bad)

    def test_mount_without_loop_is_inconsistent(self) -> None:
        bad = observation(loopDeviceAttachable=False)
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(bad)

    def test_fsync_without_mount_is_inconsistent(self) -> None:
        bad = observation(filesystemMountable=False)
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(bad)

    def test_evidence_boundary_cannot_be_promoted(self) -> None:
        with self.assertRaises(BlockDeviceBoundaryError):
            finalize_capability_receipt(
                observation(), evidence_boundary="PHYSICAL_POWER_LOSS_PROVEN"
            )


if __name__ == "__main__":
    unittest.main()
