from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.active_verification import evaluate_active_verification  # noqa: E402
from contractgraph_qa.ancestral_validity import run_ancestral_validity  # noqa: E402
from contractgraph_qa.causal_temporal_utils import canonical_sha256  # noqa: E402
from contractgraph_qa.causal_watchpoints import evaluate_causal_watchpoints  # noqa: E402
from contractgraph_qa.forward_remediation import evaluate_forward_remediation  # noqa: E402
from contractgraph_qa.independent_witness import evaluate_independent_witness  # noqa: E402
from contractgraph_qa.orientation_center import evaluate_orientation_center  # noqa: E402
from contractgraph_qa.proof_integrity import (  # noqa: E402
    build_durable_manifest,
    evaluate_evidence_readiness,
    evaluate_metamorphic,
    evaluate_root_cause,
    evaluate_subject_freeze,
    evaluate_trace_integrity,
    evaluate_verification_plan,
    verify_durable_manifest,
)
from contractgraph_qa.replication_drift import evaluate_replication_drift  # noqa: E402
from contractgraph_qa.transition_geometry import run_transition_geometry_model  # noqa: E402
from contractgraph_qa.verification_debt import evaluate_verification_debt  # noqa: E402


class CausalTemporalVNextIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = {
            "repo": "example/repo",
            "commit": "vnext-final",
            "objectId": "escrow-1",
        }
        self.subject_hash = canonical_sha256(self.subject)

    def _endpoint(self) -> dict[str, object]:
        return {
            "subjectHash": self.subject_hash,
            "state": {"status": "settled", "generation": 2},
            "effects": {"payout": 100, "refund": 0},
            "history": {"generation": 2, "branch": "main"},
        }

    def _geometry(self) -> dict[str, object]:
        endpoint = self._endpoint()
        return run_transition_geometry_model(
            {
                "schema": "cgqa/transition-geometry/v0.1",
                "subject": self.subject,
                "requirements": {"requireEndpointSubjectBinding": True},
                "operators": {"a": "settle", "b": "finalize"},
                "origin": json.loads(json.dumps(endpoint)),
                "aThenB": json.loads(json.dumps(endpoint)),
                "bThenA": json.loads(json.dumps(endpoint)),
                "loop": {
                    "operators": ["settle", "finalize", "observe"],
                    "returned": json.loads(json.dumps(endpoint)),
                },
            }
        )

    def _ancestry(self) -> dict[str, object]:
        return run_ancestral_validity(
            {
                "schema": "cgqa/ancestral-validity/v0.1",
                "subject": self.subject,
                "targetEventId": "target",
                "events": [
                    {
                        "id": "root",
                        "kind": "ROOT",
                        "actor": "system",
                        "occurredAt": 1,
                        "scope": "escrow-1",
                        "localValid": True,
                    },
                    {
                        "id": "approval",
                        "kind": "APPROVAL",
                        "actor": "reviewer",
                        "occurredAt": 2,
                        "scope": "escrow-1",
                        "parentId": "root",
                        "localValid": True,
                    },
                    {
                        "id": "target",
                        "kind": "ACTION",
                        "actor": "agent",
                        "occurredAt": 3,
                        "scope": "escrow-1",
                        "parentId": "approval",
                        "localValid": True,
                    },
                ],
            }
        )

    def _witness(self) -> dict[str, object]:
        return evaluate_independent_witness(
            {
                "schema": "cgqa/independent-witness/v0.1",
                "subject": self.subject,
                "coverageLevel": "SUBJECT_OBJECT_COVERAGE",
                "observed": {
                    "sourceId": "ledger",
                    "failureDomain": "database",
                    "subjectHash": self.subject_hash,
                    "events": [
                        {"eventId": "e1", "objectId": "escrow-1"},
                        {"eventId": "e2", "objectId": "escrow-1"},
                    ],
                },
                "external": {
                    "sourceId": "gateway-log",
                    "failureDomain": "gateway",
                    "subjectHash": self.subject_hash,
                    "events": [
                        {"eventId": "e1", "objectId": "escrow-1"},
                        {"eventId": "e2", "objectId": "escrow-1"},
                    ],
                },
            }
        )

    def _orientation(
        self,
        geometry: dict[str, object],
        ancestry: dict[str, object],
        debt_receipts: list[dict[str, object]],
    ) -> dict[str, object]:
        return evaluate_orientation_center(
            {
                "schema": "cgqa/orientation-center/v0.1",
                "subject": self.subject,
                "state": {"status": "settled", "generation": 2},
                "ancestry": {"status": "VALID_WITHIN_TRACE"},
                "ancestryResults": [ancestry],
                "geometryResults": [geometry],
                "authorityNow": {"status": "VALID"},
                "supportingEvidence": [
                    {"id": "native-regression", "status": "PASS"},
                    {"id": "durable-reopen", "status": "PASS"},
                ],
                "counterevidence": [],
                "verificationDebt": debt_receipts,
                "independentWitnesses": [{"id": "external-witness", "status": "PASS"}],
                "watchpoints": [{"id": "late-retry", "status": "WATCHING"}],
                "requirements": {
                    "requireSupportingEvidence": True,
                    "requireIndependentWitness": True,
                    "requireAncestry": True,
                    "requireAuthority": True,
                    "requireGeometry": True,
                    "requireAncestryReceipt": True,
                },
            }
        )

    def test_vnext_full_route_preserves_hold_until_required_work_is_verified(self) -> None:
        freeze = evaluate_subject_freeze(
            {
                "schema": "cgqa/subject-freeze/v0.1",
                "subjectBefore": self.subject,
                "subjectAfter": dict(self.subject),
            }
        )
        self.assertEqual(freeze["classification"], "UNCHANGED")

        geometry = self._geometry()
        self.assertEqual(geometry["status"], "pass")
        self.assertEqual(geometry["pair"]["classification"], "CLOSED")
        self.assertEqual(geometry["loop"]["classification"], "FLAT_LOOP")

        ancestry = self._ancestry()
        self.assertEqual(ancestry["status"], "pass")
        self.assertEqual(ancestry["effectiveValidity"], "valid_within_trace")
        self.assertIsNone(ancestry["firstInvalidity"])

        witness = self._witness()
        self.assertEqual(witness["status"], "pass")
        self.assertTrue(witness["independent"])

        watchpoints = evaluate_causal_watchpoints(
            {
                "schema": "cgqa/causal-watchpoints/v0.1",
                "subject": self.subject,
                "currentStep": 5,
                "evidence": [],
                "watchpoints": [
                    {
                        "id": "late-retry",
                        "status": "DORMANT",
                        "startStep": 2,
                        "endStep": 10,
                        "generation": 2,
                        "subjectHash": self.subject_hash,
                        "conditions": [{"field": "retry.count", "equals": 2}],
                    }
                ],
            }
        )
        self.assertEqual(watchpoints["watchpoints"][0]["status"], "WATCHING")

        plan = {
            "subjectHash": self.subject_hash,
            "invariants": ["conservation", "once-only"],
            "forbiddenStates": ["double-effect"],
            "capabilities": ["geometry", "ancestry", "witness", "replication"],
            "negativeControls": ["remove-terminal-guard"],
            "bounds": {"maxDepth": 8, "seed": 7},
        }
        verification_plan = evaluate_verification_plan(
            {
                "schema": "cgqa/verification-plan/v0.1",
                "plan": plan,
                "amendments": [],
                "result": {
                    "planHash": canonical_sha256(plan),
                    "subjectHash": self.subject_hash,
                    "executedCapabilities": ["geometry", "ancestry", "witness", "replication"],
                    "bounds": dict(plan["bounds"]),
                },
            }
        )
        self.assertEqual(verification_plan["status"], "pass")

        trace = evaluate_trace_integrity(
            {
                "schema": "cgqa/trace-integrity/v0.1",
                "subject": self.subject,
                "completeExpected": True,
                "events": [
                    {"eventId": "e0", "sequence": 0, "subjectHash": self.subject_hash},
                    {
                        "eventId": "e1",
                        "sequence": 1,
                        "subjectHash": self.subject_hash,
                        "predecessorId": "e0",
                    },
                    {
                        "eventId": "e2",
                        "sequence": 2,
                        "subjectHash": self.subject_hash,
                        "predecessorId": "e1",
                    },
                ],
            }
        )
        self.assertEqual(trace["status"], "pass")

        readiness = evaluate_evidence_readiness(
            {
                "schema": "cgqa/evidence-readiness/v0.1",
                "subject": self.subject,
                "evidence": [
                    {
                        "id": "w1",
                        "class": "WITNESSED",
                        "subjectHash": self.subject_hash,
                        "sourceType": "DIRECT_OBSERVATION",
                        "replayable": True,
                        "fresh": True,
                        "independent": True,
                    },
                    {
                        "id": "counter-reviewed",
                        "class": "COUNTEREVIDENCE",
                        "subjectHash": self.subject_hash,
                        "sourceType": "DIRECT_OBSERVATION",
                        "replayable": True,
                        "fresh": True,
                        "independent": True,
                    },
                ],
                "requirements": {
                    "requireFresh": True,
                    "requireReplayable": True,
                    "expectedCounterevidenceIds": ["counter-reviewed"],
                },
            }
        )
        self.assertEqual(readiness["readiness"], "READY")
        self.assertIsNone(readiness["truthProbability"])

        root_cause = evaluate_root_cause(
            {
                "schema": "cgqa/root-cause-collapse/v0.1",
                "findings": [
                    {"id": "root", "invariant": "replay"},
                    {"id": "symptom", "invariant": "accounting"},
                ],
                "edges": [{"from": "root", "to": "symptom", "relation": "CAUSES"}],
            }
        )
        self.assertEqual(root_cause["independentRootCount"], 1)

        endpoint = self._endpoint()
        metamorphic = evaluate_metamorphic(
            {
                "schema": "cgqa/metamorphic-roundtrip/v0.1",
                "subject": self.subject,
                "cases": [
                    {
                        "id": "persist-reopen",
                        "before": endpoint,
                        "after": json.loads(json.dumps(endpoint)),
                        "preserve": {"state": True, "effects": True, "history": True},
                    }
                ],
            }
        )
        self.assertEqual(metamorphic["status"], "pass")

        drift = evaluate_replication_drift(
            {
                "schema": "cgqa/replication-drift/v0.1",
                "mode": "TEMPORAL_EXTERNAL",
                "currentGeneration": 2,
                "refitOnReplication": False,
                "performanceThresholds": {"errorRate": 0.01},
                "target": {
                    "subject": {**self.subject, "generation": 1},
                    "generation": 1,
                    "sourceId": "source-a",
                    "evidenceHash": "old-evidence",
                    "structureSignature": "graph-a",
                    "performance": {"errorRate": 0.01},
                },
                "replication": {
                    "subject": {**self.subject, "generation": 2},
                    "generation": 2,
                    "sourceId": "source-b",
                    "evidenceHash": "new-evidence",
                    "structureSignature": "graph-a",
                    "performance": {"errorRate": 0.04},
                },
            }
        )
        self.assertEqual(drift["freshness"], "FRESH")
        self.assertEqual(drift["driftKind"], "PERFORMANCE_DRIFT")
        self.assertEqual(drift["status"], "hold")
        self.assertFalse(drift["remediationAuthorized"])

        remediation = evaluate_forward_remediation(
            {
                "schema": "cgqa/forward-remediation/v0.1",
                "subject": self.subject,
                "current": {"generation": 2, "stateHash": "current-state"},
                "proposal": {
                    "id": "rem-1",
                    "action": "SAFE_ROLLBACK",
                    "subjectHash": self.subject_hash,
                    "baseGeneration": 2,
                    "evidenceGeneration": 2,
                    "resultGeneration": 3,
                    "sourceGeneration": 1,
                    "automatic": False,
                    "assessmentId": "review-1",
                    "evidenceRefs": ["drift-1"],
                },
            }
        )
        self.assertEqual(remediation["status"], "pass")
        self.assertTrue(remediation["historyPreserved"])
        self.assertFalse(remediation["executionAuthorized"])

        planner = evaluate_active_verification(
            {
                "schema": "cgqa/active-verification/v0.1",
                "subject": self.subject,
                "completedWorkIds": [],
                "policy": {
                    "capacityUnits": 1,
                    "budget": 10,
                    "requireInformationGain": False,
                    "weights": {
                        "risk": 10,
                        "priority": 2,
                        "age": 1,
                        "informationGain": 1,
                        "cost": 1,
                    },
                },
                "work": [
                    {
                        "id": "drift-review",
                        "subjectHash": self.subject_hash,
                        "capability": "Temporal / External Replication",
                        "required": True,
                        "riskWeight": 5,
                        "priority": 5,
                        "age": 1,
                        "capacityUnits": 1,
                        "cost": {"estimated": 2},
                        "expectedInformationGain": 3,
                        "prerequisites": [],
                    }
                ],
            }
        )
        self.assertEqual(planner["selectedWorkIds"], ["drift-review"])
        self.assertFalse(planner["selectionIsVerification"])

        unresolved_debt = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": planner["verificationDebtReceipts"],
            }
        )
        self.assertEqual(unresolved_debt["status"], "hold")

        mid_orientation = self._orientation(
            geometry,
            ancestry,
            unresolved_debt["debtReceipts"],
        )
        self.assertEqual(mid_orientation["readiness"], "INDETERMINATE")

        resolved_debt = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": [
                    {
                        "id": "drift-review",
                        "capability": "Temporal / External Replication",
                        "required": True,
                        "status": "COMPLETED_PASS",
                        "subjectHash": self.subject_hash,
                    }
                ],
            }
        )
        self.assertEqual(resolved_debt["status"], "pass")

        final_orientation = self._orientation(
            geometry,
            ancestry,
            resolved_debt["debtReceipts"],
        )
        self.assertEqual(final_orientation["readiness"], "BALANCED")
        self.assertEqual(final_orientation["status"], "pass")
        self.assertFalse(final_orientation["securityVerdictAuthorized"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orientation.json").write_text(
                json.dumps(final_orientation, sort_keys=True), encoding="utf-8"
            )
            (root / "planner.json").write_text(
                json.dumps(planner, sort_keys=True), encoding="utf-8"
            )
            manifest = build_durable_manifest(root, ["orientation.json", "planner.json"])
            durable = verify_durable_manifest(root, manifest)
            self.assertEqual(durable["status"], "pass")


if __name__ == "__main__":
    unittest.main()
