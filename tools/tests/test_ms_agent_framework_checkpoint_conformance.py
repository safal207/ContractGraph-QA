from __future__ import annotations

import copy
import unittest

from contractgraph_qa.integrations.ms_agent_framework_checkpoint import (
    MS_AGENT_FRAMEWORK_CHECKPOINT_SOURCE,
    MS_AGENT_FRAMEWORK_SOURCE_COMMIT,
    MS_AGENT_FRAMEWORK_SOURCE_REPOSITORY,
    checkpoint_json_round_trip,
    project_ms_agent_framework_checkpoint_boundary,
    restore_witnesses_from_workflow_checkpoint,
    workflow_checkpoint_state,
)
from contractgraph_qa.witness_projection_conformance import (
    ABSENCE_AFTER_DEADLINE,
    RESPONSE,
    SENT,
    run_witness_projection_conformance,
)


class MicrosoftAgentFrameworkCheckpointConformanceTest(unittest.TestCase):
    def test_source_is_pinned(self) -> None:
        self.assertEqual(MS_AGENT_FRAMEWORK_SOURCE_REPOSITORY, "microsoft/agent-framework")
        self.assertEqual(
            MS_AGENT_FRAMEWORK_SOURCE_COMMIT,
            "d9d3fb6252f7ae9e7f8104edce7266f0782a813c",
        )
        self.assertEqual(
            MS_AGENT_FRAMEWORK_CHECKPOINT_SOURCE,
            "python/packages/core/agent_framework/_workflows/_checkpoint.py",
        )

    def test_checkpoint_state_preserves_exact_witness_order(self) -> None:
        witnesses = [
            copy.deepcopy(SENT),
            copy.deepcopy(ABSENCE_AFTER_DEADLINE),
            copy.deepcopy(RESPONSE),
        ]
        checkpoint = workflow_checkpoint_state(witnesses)
        restored = restore_witnesses_from_workflow_checkpoint(checkpoint)
        self.assertEqual(restored, witnesses)

    def test_json_round_trip_preserves_decision_evidence(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
        checkpoint = workflow_checkpoint_state(
            witnesses,
            checkpoint_id="cp-2",
            previous_checkpoint_id="cp-1",
        )
        restored_checkpoint = checkpoint_json_round_trip(checkpoint)
        restored = restore_witnesses_from_workflow_checkpoint(restored_checkpoint)

        self.assertEqual([item["kind"] for item in restored], ["sent", "absence"])
        self.assertEqual(restored[0]["at"], SENT["at"])
        self.assertEqual(restored[0]["deadline"], SENT["deadline"])
        self.assertEqual(restored[1]["checked_at"], ABSENCE_AFTER_DEADLINE["checked_at"])
        self.assertEqual(tuple(restored[1]["window"]), ABSENCE_AFTER_DEADLINE["window"])
        self.assertEqual(restored[1]["deadline"], ABSENCE_AFTER_DEADLINE["deadline"])
        self.assertEqual(restored[1]["result"], ABSENCE_AFTER_DEADLINE["result"])
        self.assertEqual(restored_checkpoint["previous_checkpoint_id"], "cp-1")

    def test_checkpoint_metadata_time_is_not_projection_input(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
        early = workflow_checkpoint_state(
            witnesses, timestamp="2026-01-01T00:00:00+00:00"
        )
        late = workflow_checkpoint_state(
            witnesses, timestamp="2099-01-01T00:00:00+00:00"
        )
        early_outcome = project_ms_agent_framework_checkpoint_boundary(
            restore_witnesses_from_workflow_checkpoint(early), now=3000
        )
        late_outcome = project_ms_agent_framework_checkpoint_boundary(
            restore_witnesses_from_workflow_checkpoint(late), now=10**12
        )
        self.assertEqual(early_outcome, late_outcome)

    def test_framework_checkpoint_hosted_boundary_is_v01_conformant(self) -> None:
        report = run_witness_projection_conformance(
            project_ms_agent_framework_checkpoint_boundary
        )
        self.assertTrue(report.conformant)
        self.assertEqual(len(report.checks), 8)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_projection_does_not_back_mutate_checkpoint_state(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
        checkpoint = workflow_checkpoint_state(witnesses)
        before = copy.deepcopy(checkpoint)
        project_ms_agent_framework_checkpoint_boundary(
            restore_witnesses_from_workflow_checkpoint(checkpoint), now=3000
        )
        self.assertEqual(checkpoint, before)


if __name__ == "__main__":
    unittest.main()
