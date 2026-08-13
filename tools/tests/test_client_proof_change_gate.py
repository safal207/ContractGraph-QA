from __future__ import annotations

import copy
import unittest

from contractgraph_qa.client_proof import (
    attach_change_gate_evidence,
    build_change_gate_evidence,
    change_gate_result_sha256,
    verify_change_gate_evidence,
)


GATE_RESULT = {
    "schemaVersion": 1,
    "status": "pass",
    "baseRef": "origin/main",
    "baseCommitSha": "a" * 40,
    "headCommitSha": "b" * 40,
    "configPath": "causal-security-gate.toml",
    "baselineConfigPresent": True,
    "blockingModels": [],
    "reviewModels": [],
    "verifiedFixModels": ["escrow"],
    "models": [
        {
            "id": "escrow",
            "path": "scenarios/escrow.json",
            "status": "pass",
            "blocking": False,
            "gateReasons": [],
            "delta": {
                "status": "risk_reduced",
                "gateReasons": [],
                "noLongerReachableForbiddenCapabilities": [
                    "release-without-approval"
                ],
                "introducedForbiddenPaths": {},
            },
            "fixReplays": [
                {
                    "targetCapability": "release-without-approval",
                    "status": "fix_verified",
                    "verified": True,
                    "replay": {
                        "status": "fix_verified",
                        "priorModelSha256": "1" * 64,
                        "fixedModelSha256": "2" * 64,
                        "priorPath": {
                            "initialCapability": "request-release",
                            "targetCapability": "release-without-approval",
                            "transitions": [{"id": "bypass-approval"}],
                        },
                        "exactReplay": {
                            "blockedAt": {
                                "step": 1,
                                "reason": "assumption_guard_restored",
                                "transitionId": "bypass-approval",
                            }
                        },
                        "alternateReachability": {
                            "targetCapability": "release-without-approval",
                            "reachable": False,
                            "path": None,
                        },
                    },
                }
            ],
        }
    ],
}


class ClientProofChangeGateTests(unittest.TestCase):
    def test_binding_preserves_exact_machine_result_verbatim(self) -> None:
        evidence = build_change_gate_evidence(GATE_RESULT)
        self.assertEqual(evidence["gateResult"], GATE_RESULT)
        self.assertEqual(
            evidence["gateResultSha256"],
            change_gate_result_sha256(GATE_RESULT),
        )
        self.assertEqual(verify_change_gate_evidence(evidence), GATE_RESULT)

    def test_digest_is_independent_of_dictionary_key_order(self) -> None:
        reordered = dict(reversed(list(GATE_RESULT.items())))
        self.assertEqual(
            change_gate_result_sha256(reordered),
            change_gate_result_sha256(GATE_RESULT),
        )

    def test_tampered_nested_replay_is_rejected(self) -> None:
        evidence = build_change_gate_evidence(GATE_RESULT)
        evidence["gateResult"]["models"][0]["fixReplays"][0]["replay"]["status"] = (
            "failing_path_persists"
        )
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify_change_gate_evidence(evidence)

    def test_attach_does_not_rederive_or_mutate_existing_causal_claims(self) -> None:
        proof = {
            "schemaVersion": 2,
            "causalSecurityProof": {
                "forbiddenCapability": "existing-proof-target",
                "sentinel": "must-remain-byte-semantically-identical",
            },
        }
        original = copy.deepcopy(proof)
        bound = attach_change_gate_evidence(proof, GATE_RESULT)
        self.assertEqual(proof, original)
        self.assertEqual(bound["causalSecurityProof"], original["causalSecurityProof"])
        self.assertEqual(bound["changeGateEvidence"]["gateResult"], GATE_RESULT)

    def test_conflicting_rebind_fails_closed(self) -> None:
        bound = attach_change_gate_evidence({"schemaVersion": 2}, GATE_RESULT)
        changed = copy.deepcopy(GATE_RESULT)
        changed["headCommitSha"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "already contains different"):
            attach_change_gate_evidence(bound, changed)

    def test_blocked_gate_result_is_still_valid_client_evidence(self) -> None:
        blocked = copy.deepcopy(GATE_RESULT)
        blocked["status"] = "blocked"
        blocked["blockingModels"] = ["escrow"]
        blocked["verifiedFixModels"] = []
        evidence = build_change_gate_evidence(blocked)
        self.assertEqual(verify_change_gate_evidence(evidence)["status"], "blocked")

    def test_incomplete_runner_error_is_not_bound_as_commit_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "schemaVersion"):
            build_change_gate_evidence({"status": "blocked", "error": "bad config"})


if __name__ == "__main__":
    unittest.main()
