from __future__ import annotations

import copy
import unittest

from contractgraph_qa.integrations.langgraph_checkpoint_state import (
    LANGGRAPH_CHECKPOINT_SOURCE,
    LANGGRAPH_SOURCE_COMMIT,
    LANGGRAPH_SOURCE_REPOSITORY,
    LANGGRAPH_STATEGRAPH_SOURCE,
    append_witnesses,
    checkpoint_witness_state,
    project_langgraph_hosted_boundary,
    restore_witnesses_from_checkpoint,
)
from contractgraph_qa.witness_projection_conformance import (
    ABSENCE_AFTER_DEADLINE,
    RESPONSE,
    SENT,
    run_witness_projection_conformance,
)


class LangGraphCheckpointStateConformanceTest(unittest.TestCase):
    def test_source_is_pinned(self) -> None:
        self.assertEqual(LANGGRAPH_SOURCE_REPOSITORY, "langchain-ai/langgraph")
        self.assertEqual(
            LANGGRAPH_SOURCE_COMMIT,
            "f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f",
        )
        self.assertEqual(
            LANGGRAPH_STATEGRAPH_SOURCE,
            "libs/langgraph/langgraph/graph/state.py",
        )
        self.assertEqual(
            LANGGRAPH_CHECKPOINT_SOURCE,
            "libs/checkpoint/langgraph/checkpoint/base/__init__.py",
        )

    def test_append_reducer_preserves_old_evidence(self) -> None:
        original = [copy.deepcopy(SENT)]
        before = copy.deepcopy(original)
        extended = append_witnesses(original, ABSENCE_AFTER_DEADLINE)
        self.assertEqual(original, before)
        self.assertEqual(extended, [SENT, ABSENCE_AFTER_DEADLINE])

    def test_checkpoint_round_trip_preserves_exact_witness_sequence(self) -> None:
        witnesses = [SENT, ABSENCE_AFTER_DEADLINE, RESPONSE]
        checkpoint = checkpoint_witness_state(witnesses)
        restored = restore_witnesses_from_checkpoint(checkpoint)
        self.assertEqual(restored, witnesses)
        self.assertIsNot(restored, witnesses)

    def test_hosted_adapter_is_v01_conformant(self) -> None:
        report = run_witness_projection_conformance(project_langgraph_hosted_boundary)
        self.assertTrue(report.conformant)
        self.assertEqual(len(report.checks), 8)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_hosted_adapter_result_is_machine_serializable(self) -> None:
        payload = run_witness_projection_conformance(
            project_langgraph_hosted_boundary
        ).to_dict()
        self.assertTrue(payload["conformant"])
        self.assertEqual(payload["spec"], "witness-projection-conformance/v0.1")


if __name__ == "__main__":
    unittest.main()
