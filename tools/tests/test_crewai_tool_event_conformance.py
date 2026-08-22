from __future__ import annotations

import unittest

from contractgraph_qa.integrations.crewai_tool_events import (
    CREWAI_NATIVE_TOOL_EVENT_TYPES,
    CREWAI_SOURCE_COMMIT,
    CREWAI_SOURCE_REPOSITORY,
    canonical_witness_to_crewai_event,
    project_pinned_crewai_tool_boundary,
)
from contractgraph_qa.witness_projection_conformance import (
    ABSENCE_AFTER_DEADLINE,
    SENT,
    run_witness_projection_conformance,
)


class CrewAIToolEventConformanceTest(unittest.TestCase):
    def test_source_is_pinned(self) -> None:
        self.assertEqual(CREWAI_SOURCE_REPOSITORY, "crewAIInc/crewAI")
        self.assertEqual(
            CREWAI_SOURCE_COMMIT,
            "f4731f5025f861c78e3af0487cc80bf5e7c64782",
        )

    def test_current_native_vocabulary_is_explicit(self) -> None:
        self.assertEqual(
            CREWAI_NATIVE_TOOL_EVENT_TYPES,
            {
                "tool_usage_started",
                "tool_usage_finished",
                "tool_usage_error",
                "tool_failure_detected",
                "tool_validate_input_error",
                "tool_selection_error",
                "tool_execution_error",
            },
        )

    def test_absence_has_no_native_tool_event_at_pinned_boundary(self) -> None:
        self.assertIsNone(canonical_witness_to_crewai_event(ABSENCE_AFTER_DEADLINE))

    def test_started_witness_maps_to_native_started_event(self) -> None:
        event = canonical_witness_to_crewai_event(SENT)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["type"], "tool_usage_started")

    def test_current_crewai_tool_event_boundary_is_not_v01_conformant(self) -> None:
        report = run_witness_projection_conformance(project_pinned_crewai_tool_boundary)
        self.assertFalse(report.conformant)

        failed = {check.name for check in report.checks if not check.passed}
        self.assertEqual(
            failed,
            {
                "explicit_absence_enables_transition",
                "deadline_bound_to_evidence",
            },
        )

    def test_current_boundary_still_passes_the_other_replay_properties(self) -> None:
        report = run_witness_projection_conformance(project_pinned_crewai_tool_boundary)
        passed = {check.name for check in report.checks if check.passed}
        self.assertEqual(
            passed,
            {
                "deterministic_across_evaluator_time",
                "replay_stability",
                "prefix_stability",
                "non_monotone_state_over_monotone_evidence",
                "missing_deadline_fails_closed",
                "projection_does_not_mutate_evidence",
            },
        )


if __name__ == "__main__":
    unittest.main()
