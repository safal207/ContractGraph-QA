from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.agent_trajectory import (
    evaluate_agent_trajectory_file,
    evaluate_agent_trajectory_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "benchmarks" / "proof-carrying-agent-trajectories-v0.1" / "cases"
EXPECTED_CASE_NAMES = {
    "fail_handoff_after_unknown_redispatch.json",
    "fail_lost_ack_crash_resume_redispatch.json",
    "fail_stale_observer_retry.json",
    "pass_handoff_after_unknown_reconcile.json",
    "pass_lost_ack_crash_resume_reconcile.json",
    "pass_stale_observer_reconcile.json",
}


def _scenario(events: list[dict[str, object]], scenario_id: str) -> dict[str, object]:
    return {
        "schema": "cgqa.proof-carrying-agent-trajectory-scenario.v0.1",
        "benchmark": "proof-carrying-agent-trajectories-v0.1",
        "scenarioId": scenario_id,
        "trajectoryId": "traj-test",
        "policy": {
            "name": "test-policy",
            "requirePredecessorProof": True,
            "requireTerminalEvidence": True,
        },
        "events": events,
    }


def _event(seq: int, event_type: str, segment: str = "segment-1", **extra: object) -> dict[str, object]:
    event: dict[str, object] = {
        "seq": seq,
        "type": event_type,
        "trajectoryId": "traj-test",
        "segmentId": segment,
        "logicalOperationId": "op-test",
    }
    event.update(extra)
    return event


class AgentTrajectoryBenchmarkTest(unittest.TestCase):
    def test_seed_matrix_has_exact_six_cases_and_expected_results(self) -> None:
        names = {path.name for path in CASES.glob("*.json")}
        self.assertEqual(names, EXPECTED_CASE_NAMES)

        for path in sorted(CASES.glob("*.json")):
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                result = evaluate_agent_trajectory_file(path)
                expected_codes = sorted(payload.get("expectedViolationCodes", []))
                observed_codes = sorted(item["code"] for item in result["violations"])
                self.assertEqual(result["status"], payload["expectedStatus"])
                self.assertEqual(observed_codes, expected_codes)

    def test_terminal_evidence_must_match_reconciliation_evidence(self) -> None:
        payload = _scenario(
            [
                _event(1, "authorize"),
                _event(2, "dispatch", agentId="agent-a", executionId="exec-1"),
                _event(
                    3,
                    "reconcile",
                    executionId="exec-1",
                    outcome="committed",
                    evidenceKind="provider_receipt",
                    evidenceRef="receipt:A",
                ),
                _event(
                    4,
                    "terminal",
                    outcome="committed",
                    evidenceKind="provider_receipt",
                    evidenceRef="receipt:B",
                ),
            ],
            "terminal-evidence-mismatch",
        )
        result = evaluate_agent_trajectory_scenario(payload)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("PCT-004_TERMINAL_WITHOUT_EXTERNAL_PROOF", codes)

    def test_stale_reconciliation_cannot_resolve_latest_execution(self) -> None:
        payload = _scenario(
            [
                _event(1, "authorize"),
                _event(2, "dispatch", agentId="agent-a", executionId="exec-1"),
                _event(3, "ambiguous", executionId="exec-1"),
                _event(
                    4,
                    "reconcile",
                    executionId="exec-1",
                    outcome="no_effect",
                    evidenceKind="provider_status",
                    evidenceRef="status:exec-1:no-effect",
                    retryAuthorized=True,
                ),
                _event(
                    5,
                    "retry",
                    agentId="agent-a",
                    executionId="exec-2",
                    retryOfExecutionId="exec-1",
                ),
                _event(
                    6,
                    "reconcile",
                    executionId="exec-1",
                    outcome="committed",
                    evidenceKind="provider_receipt",
                    evidenceRef="receipt:stale",
                ),
                _event(
                    7,
                    "terminal",
                    outcome="committed",
                    evidenceKind="provider_receipt",
                    evidenceRef="receipt:stale",
                ),
            ],
            "stale-reconciliation",
        )
        result = evaluate_agent_trajectory_scenario(payload)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("PCT-002_TRAJECTORY_IDENTITY_DRIFT", codes)
        self.assertIn("PCT-004_TERMINAL_WITHOUT_EXTERNAL_PROOF", codes)

    def test_handoff_must_reference_latest_execution(self) -> None:
        payload = _scenario(
            [
                _event(1, "authorize"),
                _event(2, "dispatch", agentId="agent-a", executionId="exec-1"),
                _event(3, "ambiguous", executionId="exec-1"),
                _event(
                    4,
                    "reconcile",
                    executionId="exec-1",
                    outcome="no_effect",
                    evidenceKind="provider_status",
                    evidenceRef="status:exec-1:no-effect",
                    retryAuthorized=True,
                ),
                _event(
                    5,
                    "retry",
                    agentId="agent-a",
                    executionId="exec-2",
                    retryOfExecutionId="exec-1",
                ),
                _event(
                    6,
                    "handoff",
                    segment="segment-2",
                    fromAgentId="agent-a",
                    toAgentId="agent-b",
                    predecessorExecutionId="exec-1",
                    predecessorSegmentId="segment-1",
                    predecessorProofRef="trace:event:5",
                ),
            ],
            "historical-handoff",
        )
        result = evaluate_agent_trajectory_scenario(payload)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("PCT-002_TRAJECTORY_IDENTITY_DRIFT", codes)

    def test_reconcile_must_use_active_segment_after_resume(self) -> None:
        payload = _scenario(
            [
                _event(1, "authorize"),
                _event(2, "dispatch", agentId="agent-a", executionId="exec-1"),
                _event(3, "ambiguous", executionId="exec-1"),
                _event(
                    4,
                    "resume",
                    segment="segment-2",
                    agentId="agent-a",
                    predecessorExecutionId="exec-1",
                    predecessorSegmentId="segment-1",
                    predecessorProofRef="trace:event:3",
                ),
                _event(
                    5,
                    "reconcile",
                    segment="segment-1",
                    executionId="exec-1",
                    outcome="committed",
                    evidenceKind="provider_receipt",
                    evidenceRef="receipt:wrong-segment",
                ),
            ],
            "reconcile-segment-drift",
        )
        result = evaluate_agent_trajectory_scenario(payload)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("PCT-002_TRAJECTORY_IDENTITY_DRIFT", codes)


if __name__ == "__main__":
    unittest.main()
