from __future__ import annotations

import unittest

from contractgraph_qa.container_hard_stop import (
    EVIDENCE_BOUNDARY,
    PARENT_SYSTEM_011_HEAD,
    PARENT_SYSTEM_011_RECEIPT_DIGEST,
    ContainerHardStopError,
    finalize_case_receipt,
)


class ContainerHardStopTests(unittest.TestCase):
    def observation(self, state="STALE", rebuild="ALLOW_REBUILD"):
        return {
            "observerMode": "read-only",
            "projectionState": state,
            "rebuildDecision": rebuild,
            "executionDecision": "HOLD",
            "tempCandidateAuthority": False,
            "authorityTransfer": "NONE",
            "executionAuthorized": False,
            "mutationAuthorized": False,
            "externalEffectsPerformed": False,
        }

    def finalize(self, **overrides):
        kwargs = dict(
            case="after_authority_commit",
            observation=self.observation(),
            subject_container_id="subject-aaa",
            observer_container_id="observer-bbb",
            kill_exit_code=137,
            image_identity={"image": "test", "imageId": "sha256:image", "repoDigests": []},
        )
        kwargs.update(overrides)
        return finalize_case_receipt(**kwargs)

    def assertRejected(self, **kwargs):
        with self.assertRaises(ContainerHardStopError):
            self.finalize(**kwargs)

    def test_positive_receipt_preserves_hold(self):
        receipt = self.finalize()
        self.assertTrue(receipt["containerHardStopObserved"])
        self.assertEqual(receipt["executionDecision"], "HOLD")
        self.assertFalse(receipt["physicalPowerLossProven"])

    def test_parent_head_drift_rejected(self):
        self.assertRejected(parent_head=PARENT_SYSTEM_011_HEAD[:-1] + "0")

    def test_parent_receipt_drift_rejected(self):
        self.assertRejected(parent_receipt_digest=PARENT_SYSTEM_011_RECEIPT_DIGEST + "x")

    def test_missing_container_hard_stop_rejected(self):
        self.assertRejected(container_hard_stop_observed=False)

    def test_non_sigkill_exit_rejected(self):
        self.assertRejected(kill_exit_code=0)

    def test_observer_must_be_distinct_container(self):
        self.assertRejected(observer_container_id="subject-aaa")

    def test_vm_hard_stop_claim_rejected(self):
        self.assertRejected(vm_hard_stop_observed=True)

    def test_physical_power_loss_claim_rejected(self):
        self.assertRejected(physical_power_loss_proven=True)

    def test_evidence_boundary_cannot_be_promoted(self):
        self.assertRejected(evidence_boundary=EVIDENCE_BOUNDARY + "_PHYSICAL")

    def test_observer_must_be_read_only(self):
        obs = self.observation()
        obs["observerMode"] = "read-write"
        self.assertRejected(observation=obs)

    def test_execution_escalation_rejected(self):
        obs = self.observation()
        obs["executionDecision"] = "ALLOW_FORK"
        self.assertRejected(observation=obs)

    def test_temp_candidate_cannot_become_authority(self):
        obs = self.observation()
        obs["tempCandidateAuthority"] = True
        self.assertRejected(observation=obs)

    def test_after_projection_commit_requires_healthy_no_rebuild(self):
        receipt = self.finalize(
            case="after_projection_commit",
            observation=self.observation("HEALTHY", "NO_REBUILD"),
        )
        self.assertEqual(receipt["projectionState"], "HEALTHY")
        self.assertEqual(receipt["executionDecision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
