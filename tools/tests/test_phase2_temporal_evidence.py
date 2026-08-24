from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.causal_temporal_cli import main as phase2_cli_main  # noqa: E402
from contractgraph_qa.causal_temporal_utils import canonical_sha256  # noqa: E402
from contractgraph_qa.causal_watchpoints import evaluate_causal_watchpoints  # noqa: E402
from contractgraph_qa.forward_remediation import evaluate_forward_remediation  # noqa: E402
from contractgraph_qa.independent_witness import evaluate_independent_witness  # noqa: E402
from contractgraph_qa.orientation_center import evaluate_orientation_center  # noqa: E402
from contractgraph_qa.replication_drift import evaluate_replication_drift  # noqa: E402
from contractgraph_qa.verification_debt import evaluate_verification_debt  # noqa: E402


class Phase2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = {"repo": "example/repo", "objectId": "escrow-1"}
        self.subject_hash = canonical_sha256(self.subject)

    def _witness(self, *, external_ids: list[str] | None = None) -> dict[str, object]:
        external_ids = external_ids or ["e1", "e2"]
        return {
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
                    {"eventId": event_id, "objectId": "escrow-1"}
                    for event_id in external_ids
                ],
            },
        }

    def test_witness_exact_coverage_passes(self) -> None:
        result = evaluate_independent_witness(self._witness())
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["independent"])

    def test_equal_counts_do_not_hide_event_id_gap(self) -> None:
        model = self._witness(external_ids=["e1", "e3"])
        result = evaluate_independent_witness(model)
        self.assertEqual(result["status"], "fail")
        self.assertIn("EVENT_ID_COVERAGE_MISMATCH", result["reasons"])

    def test_self_attested_witness_fails_independence(self) -> None:
        model = self._witness()
        model["external"]["failureDomain"] = "database"
        result = evaluate_independent_witness(model)
        self.assertIn("WITNESS_NOT_INDEPENDENT", result["reasons"])

    def test_object_identity_mismatch_fails(self) -> None:
        model = self._witness()
        model["external"]["events"][1]["objectId"] = "other-object"
        result = evaluate_independent_witness(model)
        self.assertIn("SUBJECT_OBJECT_MISMATCH", result["reasons"])

    def test_completed_is_not_pass_for_required_debt(self) -> None:
        result = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": [
                    {
                        "id": "restart-replay",
                        "capability": "Crash / Recovery",
                        "required": True,
                        "status": "COMPLETED",
                        "subjectHash": self.subject_hash,
                    }
                ],
            }
        )
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["orientationImpact"], "INDETERMINATE")

    def test_completed_pass_resolves_required_debt(self) -> None:
        result = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": [
                    {
                        "id": "restart-replay",
                        "capability": "Crash / Recovery",
                        "required": True,
                        "status": "COMPLETED_PASS",
                        "subjectHash": self.subject_hash,
                    }
                ],
            }
        )
        self.assertEqual(result["status"], "pass")

    def _watch_model(self) -> dict[str, object]:
        return {
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
                    "generation": 1,
                    "subjectHash": self.subject_hash,
                    "conditions": [{"field": "retry.count", "equals": 2}],
                }
            ],
        }

    def test_time_alone_does_not_activate_watchpoint(self) -> None:
        result = evaluate_causal_watchpoints(self._watch_model())
        self.assertEqual(result["watchpoints"][0]["status"], "WATCHING")

    def test_matching_condition_activates_watchpoint(self) -> None:
        model = self._watch_model()
        model["evidence"] = [
            {
                "id": "obs-1",
                "step": 5,
                "subjectHash": self.subject_hash,
                "facts": {"retry": {"count": 2}},
            }
        ]
        result = evaluate_causal_watchpoints(model)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["watchpoints"][0]["status"], "ACTIVATED")

    def test_foreign_subject_evidence_cannot_activate(self) -> None:
        model = self._watch_model()
        model["evidence"] = [
            {
                "id": "foreign",
                "step": 5,
                "subjectHash": "f" * 64,
                "facts": {"retry": {"count": 2}},
            }
        ]
        result = evaluate_causal_watchpoints(model)
        self.assertEqual(result["watchpoints"][0]["status"], "WATCHING")
        self.assertEqual(result["foreignEvidenceIds"], ["foreign"])

    def _replication(self) -> dict[str, object]:
        return {
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

    def test_fresh_performance_drift_is_hold_not_model_falsehood(self) -> None:
        result = evaluate_replication_drift(self._replication())
        self.assertEqual(result["freshness"], "FRESH")
        self.assertEqual(result["driftKind"], "PERFORMANCE_DRIFT")
        self.assertEqual(result["status"], "hold")
        self.assertFalse(result["remediationAuthorized"])

    def test_reused_evidence_is_not_fresh(self) -> None:
        model = self._replication()
        model["replication"]["evidenceHash"] = "old-evidence"
        result = evaluate_replication_drift(model)
        self.assertEqual(result["status"], "fail")
        self.assertIn("EVIDENCE_REUSED", result["freshnessFailures"])

    def test_external_mode_requires_distinct_source(self) -> None:
        model = self._replication()
        model["replication"]["sourceId"] = "source-a"
        result = evaluate_replication_drift(model)
        self.assertIn("EXTERNAL_SOURCE_NOT_DISTINCT", result["freshnessFailures"])

    def _remediation(self) -> dict[str, object]:
        return {
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

    def test_safe_rollback_moves_forward(self) -> None:
        result = evaluate_forward_remediation(self._remediation())
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["historyPreserved"])
        self.assertFalse(result["executionAuthorized"])

    def test_history_rewrite_is_rejected(self) -> None:
        model = self._remediation()
        model["proposal"]["resultGeneration"] = 1
        result = evaluate_forward_remediation(model)
        self.assertIn("HISTORY_REWRITE_OR_NON_FORWARD_RESULT", result["reasons"])

    def test_automatic_rollback_is_rejected(self) -> None:
        model = self._remediation()
        model["proposal"]["automatic"] = True
        result = evaluate_forward_remediation(model)
        self.assertIn("AUTOMATIC_REMEDIATION_NOT_AUTHORIZED", result["reasons"])

    def test_cross_capability_drift_debt_orientation_remediation(self) -> None:
        witness = evaluate_independent_witness(self._witness())
        self.assertEqual(witness["status"], "pass")
        drift = evaluate_replication_drift(self._replication())
        self.assertEqual(drift["status"], "hold")
        debt = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": [
                    {
                        "id": "drift-review",
                        "capability": "Temporal / External Replication",
                        "required": True,
                        "status": "ADMITTED",
                        "subjectHash": self.subject_hash,
                    }
                ],
            }
        )
        orientation = evaluate_orientation_center(
            {
                "schema": "cgqa/orientation-center/v0.1",
                "subject": self.subject,
                "state": {"generation": 2},
                "ancestry": {
                    "status": "PASS",
                    "effectiveValidity": "valid_within_trace",
                    "subjectHash": self.subject_hash,
                },
                "geometryResults": [],
                "authorityNow": {"status": "VALID"},
                "supportingEvidence": [
                    {"id": "historical-pass", "status": "PASS", "subjectHash": self.subject_hash}
                ],
                "counterevidence": [],
                "verificationDebt": debt["debtReceipts"],
                "independentWitnesses": [
                    {"id": "external-witness", "status": "PASS", "subjectHash": self.subject_hash}
                ],
                "watchpoints": [],
                "requirements": {
                    "requireSupportingEvidence": True,
                    "requireIndependentWitness": True,
                    "requireAncestry": True,
                    "requireAuthority": True,
                    "requireGeometry": False,
                    "requireChildSubjectBinding": True,
                },
            }
        )
        self.assertEqual(orientation["readiness"], "INDETERMINATE")
        remediation = evaluate_forward_remediation(self._remediation())
        self.assertEqual(remediation["status"], "pass")
        self.assertFalse(remediation["executionAuthorized"])

    def test_phase2_cli_is_deterministic_and_nonzero_on_hold(self) -> None:
        model = self._replication()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replication.json"
            path.write_text(json.dumps(model), encoding="utf-8")
            outputs: list[str] = []
            codes: list[int] = []
            for _ in range(2):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    codes.append(phase2_cli_main(["replicate", "--input", str(path)]))
                outputs.append(stdout.getvalue())
            self.assertEqual(codes, [2, 2])
            self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
