from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.proofpath_scig_adapter import (
    PROOFPATH_SCIG_CANONICAL_COMMIT,
    ProofPathScigBridgeError,
    build_proofpath_scig_from_provider_evidence,
    finalize_native_proofpath_receipt,
)
from contractgraph_qa.provider_decision_evidence import (
    build_provider_decision_evidence,
    canonical_evidence_pack_sha256,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision


ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"
CASE = ROOT / "benchmarks" / "system-native" / "CGQA-PROOFPATH-001.json"


class ProofPathScigAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = json.loads(CASE.read_text(encoding="utf-8"))
        cls.adapter = json.loads(
            (ADAPTERS / "crossmint-public-contract.v0.1.json").read_text(encoding="utf-8")
        )
        cls.observations = json.loads(
            (ADAPTERS / "crossmint-observations-get-success.json").read_text(encoding="utf-8")
        )
        cls.authority = copy.deepcopy(cls.case["source"]["authority"])

    def decision(self) -> dict:
        return evaluate_provider_payment_decision(
            copy.deepcopy(self.adapter),
            copy.deepcopy(self.observations),
            copy.deepcopy(self.authority),
            decision_id=self.case["source"]["decisionId"],
        )

    def pack(self) -> dict:
        return build_provider_decision_evidence(
            copy.deepcopy(self.adapter),
            copy.deepcopy(self.observations),
            copy.deepcopy(self.authority),
            self.decision(),
        )

    def scig(self) -> dict:
        return build_proofpath_scig_from_provider_evidence(
            self.pack(),
            observed_at=self.case["bridge"]["observedAt"],
        )

    @staticmethod
    def valid_native_stdout(scig: dict) -> str:
        lines = [f"SCIG {scig['incident_id']}"]
        for invariant in scig["invariants"]:
            lines.append(f"{invariant['id']:<18} {invariant['result'].upper()}")
        lines.extend(
            [
                "CONTAINMENT        PASSED",
                "RECOVERY           PASSED",
                "VERIFICATION       PASSED",
                "RESULT             VALID",
            ]
        )
        return "\n".join(lines) + "\n"

    def test_native_projection_preserves_logical_operation_and_evidence_digest(self) -> None:
        pack = self.pack()
        scig = build_proofpath_scig_from_provider_evidence(
            pack,
            observed_at=self.case["bridge"]["observedAt"],
        )

        self.assertEqual(scig["schema_version"], "0.1")
        self.assertEqual(scig["logical_operation_id"], self.case["logicalOperationId"])
        self.assertEqual(
            scig["bridge_contract"]["source_evidence_pack_sha256"],
            canonical_evidence_pack_sha256(pack),
        )
        self.assertEqual(
            scig["bridge_contract"]["consumer_capability_commit"],
            self.case["proofpath"]["canonicalCapabilityCommit"],
        )
        self.assertEqual(scig["bridge_contract"]["authority_transfer"], "NONE")
        self.assertIsNone(scig["bridge_contract"]["authorization_ref"])
        self.assertFalse(scig["bridge_contract"]["execution_authorized"])
        self.assertFalse(scig["bridge_contract"]["mutation_authorized"])
        self.assertFalse(scig["bridge_contract"]["external_effects_performed"])
        self.assertTrue(all(item["result"] == "held" for item in scig["invariants"]))
        self.assertEqual(scig["post_state"]["decision"], "STOP")
        self.assertFalse(scig["post_state"]["monetary_action_allowed"])

    def test_projection_is_deterministic(self) -> None:
        self.assertEqual(self.scig(), self.scig())

    def test_tampered_native_cgqa_pack_fails_before_projection(self) -> None:
        pack = self.pack()
        pack["payloads"]["providerDecision"]["decision"]["decision"] = "ALLOW"
        with self.assertRaisesRegex(ProofPathScigBridgeError, "failed native replay"):
            build_proofpath_scig_from_provider_evidence(
                pack,
                observed_at=self.case["bridge"]["observedAt"],
            )

    def test_claim_boundary_cannot_invent_production_authorization(self) -> None:
        pack = self.pack()
        # claimBoundary is intentionally outside the embedded payload digests; the
        # cross-repository adapter must validate it explicitly rather than assuming
        # successful pack replay makes these claims trustworthy.
        pack["claimBoundary"]["productionAuthorization"] = True
        with self.assertRaisesRegex(ProofPathScigBridgeError, "productionAuthorization"):
            build_proofpath_scig_from_provider_evidence(
                pack,
                observed_at=self.case["bridge"]["observedAt"],
            )

    def test_claim_boundary_cannot_claim_network_calls(self) -> None:
        pack = self.pack()
        pack["claimBoundary"]["networkCallsPerformed"] = True
        with self.assertRaisesRegex(ProofPathScigBridgeError, "networkCallsPerformed"):
            build_proofpath_scig_from_provider_evidence(
                pack,
                observed_at=self.case["bridge"]["observedAt"],
            )

    def test_native_receipt_binds_exact_canonical_scig_capability_commit(self) -> None:
        scig = self.scig()
        receipt = finalize_native_proofpath_receipt(scig, self.valid_native_stdout(scig))

        self.assertEqual(receipt["logicalOperationId"], self.case["logicalOperationId"])
        self.assertEqual(receipt["proofpath"]["result"], "VALID")
        self.assertEqual(
            receipt["proofpath"]["capabilityCommit"],
            PROOFPATH_SCIG_CANONICAL_COMMIT,
        )
        self.assertEqual(receipt["authorityTransfer"], "NONE")
        self.assertFalse(receipt["executionAuthorized"])
        self.assertFalse(receipt["mutationAuthorized"])
        self.assertFalse(receipt["externalEffectsPerformed"])
        self.assertTrue(receipt["receiptDigest"].startswith("sha256:"))

    def test_wrong_proofpath_capability_commit_fails_closed(self) -> None:
        scig = self.scig()
        with self.assertRaisesRegex(ProofPathScigBridgeError, "canonical proofpath.scig"):
            finalize_native_proofpath_receipt(
                scig,
                self.valid_native_stdout(scig),
                proofpath_capability_commit="0" * 40,
            )

    def test_invalid_native_verifier_result_is_rejected(self) -> None:
        scig = self.scig()
        output = self.valid_native_stdout(scig).replace("RESULT             VALID", "RESULT             INVALID")
        with self.assertRaisesRegex(ProofPathScigBridgeError, "RESULT VALID"):
            finalize_native_proofpath_receipt(scig, output)

    def test_authority_cannot_reappear_in_proofpath_projection(self) -> None:
        scig = self.scig()
        scig["bridge_contract"]["authority_transfer"] = "EXPLICIT"
        with self.assertRaisesRegex(ProofPathScigBridgeError, "transfer no authority"):
            finalize_native_proofpath_receipt(scig, self.valid_native_stdout(scig))


if __name__ == "__main__":
    unittest.main()
