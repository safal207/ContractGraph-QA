from __future__ import annotations

import json
import unittest

from contractgraph_qa.integrations.langgraph_recovery_safety import (
    CheckStatus,
    LANGGRAPH_ISSUE_NUMBER,
    LANGGRAPH_ISSUE_REPOSITORY,
    OBSERVATION_SCHEMA,
    RECOVERY_SAFETY_PROPERTY_COMMIT,
    canonical_digest,
    evaluate_recovery_safety,
    logical_action_set_digest,
    semantic_action_identity,
)


def action(step: str) -> dict[str, object]:
    return {
        "kind": "fixture_external_effect",
        "workflow_instance": "langgraph-8039:t1",
        "logical_action": step,
    }


def record(step: str) -> dict[str, object]:
    payload = action(step)
    return {
        "step": step,
        "action": payload,
        "action_id": semantic_action_identity(payload),
    }


def observation(
    scenario: str,
    receiver: str,
    observable_state: dict[str, object],
    attempts: list[dict[str, object]],
    admissions: list[dict[str, object]],
    *,
    langgraph_version: str = "1.2.4",
    sqlite_version: str = "3.1.0",
    logical_actions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    received = {"thread_id": "t1", "input": {"sent": 0}}
    declared_actions = logical_actions or [action(step) for step in ("step1", "step2", "step3")]
    return {
        "schema": OBSERVATION_SCHEMA,
        "source": {
            "repository": LANGGRAPH_ISSUE_REPOSITORY,
            "issue": LANGGRAPH_ISSUE_NUMBER,
            "langgraph_version": langgraph_version,
            "sqlite_checkpointer_version": sqlite_version,
        },
        "scenario": scenario,
        "receiver": receiver,
        "received": received,
        "received_digest": canonical_digest(received),
        "logical_actions": declared_actions,
        "logical_action_set_digest": logical_action_set_digest(declared_actions),
        "crash_boundary": "checkpoint.put:channel_values.sent=2:entry",
        "observable_state": observable_state,
        "recovered_state_digest": canonical_digest(observable_state),
        "attempts": attempts,
        "admissions": admissions,
    }


class LangGraphRecoverySafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        step1 = record("step1")
        step2 = record("step2")
        step3 = record("step3")
        self.duplicate = observation(
            "writes-delay",
            "append",
            {"graph_state": {"sent": 3}, "admission_counts": {"step2": 2}},
            [step1, step2, step2, step3],
            [step1, step2, step2, step3],
        )
        self.exact_once = observation(
            "put-delay",
            "append",
            {"graph_state": {"sent": 3}, "admission_counts": {"step2": 1}},
            [step1, step2, step3],
            [step1, step2, step3],
        )
        self.dedup_control = observation(
            "writes-delay-dedup",
            "dedup",
            {"graph_state": {"sent": 3}, "admission_counts": {"step2": 1}},
            [step1, step2, step2, step3],
            [step1, step2, step3],
        )

    def test_semantic_identity_is_canonical_and_position_independent(self) -> None:
        first = semantic_action_identity(
            {"payee": "vendor-a", "amount": 25, "invoice": "inv-7"}
        )
        reordered = semantic_action_identity(
            {"invoice": "inv-7", "amount": 25, "payee": "vendor-a"}
        )
        changed = semantic_action_identity(
            {"invoice": "inv-8", "amount": 25, "payee": "vendor-a"}
        )
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

    def test_forced_interleavings_emit_rs1_rs2_rs3_counterexample(self) -> None:
        report = evaluate_recovery_safety([self.duplicate, self.exact_once])
        statuses = {check.property_id: check.status for check in report.checks}
        self.assertEqual(statuses["RS1"], CheckStatus.FAIL)
        self.assertEqual(statuses["RS2"], CheckStatus.FAIL)
        self.assertEqual(statuses["RS3"], CheckStatus.FAIL)
        self.assertFalse(report.conformant)

    def test_receiver_dedup_closes_rs3_control_not_runtime_reexecution(self) -> None:
        report = evaluate_recovery_safety(
            [self.duplicate, self.exact_once, self.dedup_control]
        )
        self.assertIsNotNone(report.receiver_control)
        assert report.receiver_control is not None
        self.assertEqual(report.receiver_control.status, CheckStatus.PASS)
        self.assertIn("re-executed", report.receiver_control.rationale)
        self.assertFalse(report.conformant)

    def test_single_observation_does_not_overclaim_rs1_or_rs2(self) -> None:
        report = evaluate_recovery_safety([self.exact_once])
        statuses = {check.property_id: check.status for check in report.checks}
        self.assertEqual(statuses["RS1"], CheckStatus.NOT_ESTABLISHED)
        self.assertEqual(statuses["RS2"], CheckStatus.NOT_ESTABLISHED)
        self.assertEqual(statuses["RS3"], CheckStatus.PASS)

    def test_changed_action_set_is_not_a_comparable_crash_pair(self) -> None:
        changed_actions = [action("step1"), action("step2"), action("step4")]
        changed_step4 = record("step4")
        changed = observation(
            "put-delay-different-action-set",
            "append",
            {"graph_state": {"sent": 3}, "admission_counts": {"step2": 1}},
            [record("step1"), record("step2"), changed_step4],
            [record("step1"), record("step2"), changed_step4],
            logical_actions=changed_actions,
        )
        report = evaluate_recovery_safety([self.duplicate, changed])
        statuses = {check.property_id: check.status for check in report.checks}
        self.assertEqual(statuses["RS1"], CheckStatus.NOT_ESTABLISHED)
        self.assertEqual(statuses["RS2"], CheckStatus.NOT_ESTABLISHED)

    def test_report_uses_observed_runtime_profile_and_property_pin(self) -> None:
        payload = evaluate_recovery_safety(
            [self.duplicate, self.exact_once, self.dedup_control]
        ).to_dict()
        rendered = json.dumps(payload, sort_keys=True)
        self.assertIn("cgqa.langgraph.recovery-safety-report/v0.1", rendered)
        self.assertEqual(payload["subject"]["langgraph_version"], "1.2.4")
        self.assertEqual(payload["subject"]["sqlite_checkpointer_version"], "3.1.0")
        self.assertEqual(
            payload["subject"]["property_commit"],
            RECOVERY_SAFETY_PROPERTY_COMMIT,
        )

    def test_mixed_runtime_profiles_are_explicit_not_silently_collapsed(self) -> None:
        newer = observation(
            "newer-runtime",
            "append",
            {"graph_state": {"sent": 3}, "admission_counts": {"step2": 1}},
            [record("step1"), record("step2"), record("step3")],
            [record("step1"), record("step2"), record("step3")],
            langgraph_version="1.2.11",
            sqlite_version="3.1.1",
        )
        subject = evaluate_recovery_safety([self.exact_once, newer]).subject
        self.assertIsNone(subject["langgraph_version"])
        self.assertEqual(len(subject["observed_profiles"]), 2)

    def test_tampered_action_identity_fails_closed(self) -> None:
        broken = dict(self.duplicate)
        broken_admissions = [dict(item) for item in self.duplicate["admissions"]]
        broken_admissions[1]["action_id"] = "sha256:" + "0" * 64
        broken["admissions"] = broken_admissions
        with self.assertRaisesRegex(ValueError, "does not bind"):
            evaluate_recovery_safety([broken, self.exact_once])

    def test_tampered_observable_state_digest_fails_closed(self) -> None:
        broken = dict(self.duplicate)
        broken["recovered_state_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "recovered_state_digest mismatch"):
            evaluate_recovery_safety([broken, self.exact_once])

    def test_admission_cannot_exceed_attempt_count(self) -> None:
        broken = dict(self.exact_once)
        broken["admissions"] = [*self.exact_once["admissions"], record("step2")]
        with self.assertRaisesRegex(ValueError, "more often than attempted"):
            evaluate_recovery_safety([broken, self.duplicate])


if __name__ == "__main__":
    unittest.main()
