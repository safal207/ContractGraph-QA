from __future__ import annotations

import copy
import unittest

from contractgraph_qa.integrations.openai_agents_sqlite_session import (
    OPENAI_AGENTS_NATIVE_MUTATORS,
    OPENAI_AGENTS_SESSION_SOURCE,
    OPENAI_AGENTS_SOURCE_COMMIT,
    OPENAI_AGENTS_SOURCE_REPOSITORY,
    OPENAI_AGENTS_SQLITE_SESSION_SOURCE,
    encode_witness_as_session_item,
    project_openai_agents_session_boundary,
    restore_witnesses_from_session_items,
    sqlite_session_round_trip,
)
from contractgraph_qa.witness_projection_conformance import (
    ABSENCE_AFTER_DEADLINE,
    RESPONSE,
    SENT,
    run_witness_projection_conformance,
)


class OpenAIAgentsSessionConformanceTest(unittest.TestCase):
    def test_source_is_pinned(self) -> None:
        self.assertEqual(OPENAI_AGENTS_SOURCE_REPOSITORY, "openai/openai-agents-python")
        self.assertEqual(
            OPENAI_AGENTS_SOURCE_COMMIT,
            "7f7a44f8dc0650296bd5ab6c745c9bcbaa6ac3b7",
        )
        self.assertEqual(OPENAI_AGENTS_SESSION_SOURCE, "src/agents/memory/session.py")
        self.assertEqual(
            OPENAI_AGENTS_SQLITE_SESSION_SOURCE,
            "src/agents/memory/sqlite_session.py",
        )

    def test_sqlite_session_shape_preserves_order_and_evidence(self) -> None:
        witnesses = [
            copy.deepcopy(SENT),
            copy.deepcopy(ABSENCE_AFTER_DEADLINE),
            copy.deepcopy(RESPONSE),
        ]
        items = [encode_witness_as_session_item(witness) for witness in witnesses]
        restored_items = sqlite_session_round_trip(items)
        restored = restore_witnesses_from_session_items(restored_items)

        self.assertEqual([item["kind"] for item in restored], ["sent", "absence", "response"])
        self.assertEqual(restored[1]["checked_at"], ABSENCE_AFTER_DEADLINE["checked_at"])
        self.assertEqual(list(restored[1]["window"]), list(ABSENCE_AFTER_DEADLINE["window"]))
        self.assertEqual(restored[1]["deadline"], ABSENCE_AFTER_DEADLINE["deadline"])
        self.assertEqual(restored[1]["result"], "no_response")

    def test_hosted_session_boundary_is_v01_conformant(self) -> None:
        report = run_witness_projection_conformance(
            project_openai_agents_session_boundary
        )
        self.assertTrue(report.conformant)
        self.assertEqual(len(report.checks), 8)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_ambient_time_does_not_change_replay(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
        early = project_openai_agents_session_boundary(witnesses, now=3000)
        late = project_openai_agents_session_boundary(witnesses, now=10**12)
        self.assertEqual(early, late)

    def test_native_session_contract_is_not_append_only(self) -> None:
        self.assertEqual(OPENAI_AGENTS_NATIVE_MUTATORS, ("pop_item", "clear_session"))

    def test_projection_does_not_mutate_source_witnesses(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
        before = copy.deepcopy(witnesses)
        project_openai_agents_session_boundary(witnesses, now=3000)
        self.assertEqual(witnesses, before)


if __name__ == "__main__":
    unittest.main()
