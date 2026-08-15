import unittest

from contractgraph_qa.out_of_band_recovery import (
    EVIDENCE_BOUNDARY,
    OutOfBandRecoveryError,
    finalize_case_receipt,
)


class OutOfBandRecoveryTests(unittest.TestCase):
    def observation(self):
        return {
            "observerPid": 3003,
            "observerMode": "read-only",
            "authority": {"integrity": "VALID", "generation": 2, "error": None},
            "projection": {"integrity": "VALID", "generation": 1, "error": None},
            "tempCandidate": {"integrity": "MISSING", "generation": None, "error": None},
            "projectionState": "STALE",
            "rebuildDecision": "ALLOW_REBUILD",
            "executionDecision": "HOLD",
            "tempCandidateAuthority": False,
            "authorityTransfer": "NONE",
            "executionAuthorized": False,
            "mutationAuthorized": False,
            "externalEffectsPerformed": False,
        }

    def finalize(self, **kwargs):
        params = {
            "case": "after_authority_commit",
            "observation": self.observation(),
            "supervisor_pid": 1001,
            "subject_pid": 2002,
        }
        params.update(kwargs)
        return finalize_case_receipt(**params)

    def test_positive_receipt_requires_distinct_read_only_observer(self):
        receipt = self.finalize()
        self.assertTrue(receipt["externalTerminationObserved"])
        self.assertTrue(receipt["coldRestartObserver"])
        self.assertEqual(receipt["observerMode"], "read-only")
        self.assertEqual(receipt["executionDecision"], "HOLD")
        self.assertFalse(receipt["physicalPowerLossProven"])

    def test_subject_self_termination_cannot_satisfy_boundary(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(self_termination_observed=True)

    def test_external_termination_must_be_observed(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(external_termination_observed=False)

    def test_supervisor_must_be_outside_subject(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(supervisor_pid=2002)

    def test_cold_observer_must_be_distinct_from_subject(self):
        observation = self.observation()
        observation["observerPid"] = 2002
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(observation=observation)

    def test_cold_observer_must_be_distinct_from_supervisor(self):
        observation = self.observation()
        observation["observerPid"] = 1001
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(observation=observation)

    def test_observer_cannot_mutate_during_verification(self):
        observation = self.observation()
        observation["observerMode"] = "read-write"
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(observation=observation)

    def test_physical_power_loss_claim_is_rejected(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(physical_power_loss_proven=True)

    def test_parent_head_drift_is_rejected(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(parent_head="deadbeef")

    def test_parent_receipt_drift_is_rejected(self):
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(parent_receipt_digest="sha256:deadbeef")

    def test_evidence_boundary_cannot_be_promoted(self):
        self.assertNotEqual(EVIDENCE_BOUNDARY, "PHYSICAL_POWER_LOSS_PROVEN")
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(evidence_boundary="PHYSICAL_POWER_LOSS_PROVEN")

    def test_execution_authority_escalation_is_rejected(self):
        observation = self.observation()
        observation["executionDecision"] = "ALLOW_FORK"
        observation["executionAuthorized"] = True
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(observation=observation)

    def test_temp_candidate_never_becomes_authority(self):
        observation = self.observation()
        observation["tempCandidateAuthority"] = True
        with self.assertRaises(OutOfBandRecoveryError):
            self.finalize(observation=observation)


if __name__ == "__main__":
    unittest.main()
