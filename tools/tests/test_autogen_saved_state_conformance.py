from __future__ import annotations

import json
import unittest

from contractgraph_qa.integrations.autogen_saved_state import (
    AUTOGEN_SOURCE_COMMIT,
    AUTOGEN_SOURCE_REPOSITORY,
    load_witness_state,
    project_saved_autogen_state,
    save_witness_state,
)
from contractgraph_qa.witness_projection_conformance import (
    ABSENCE_AFTER_DEADLINE,
    RESPONSE,
    SENT,
    run_witness_projection_conformance,
)


class AutoGenSavedStateConformanceTest(unittest.TestCase):
    def test_source_is_pinned(self) -> None:
        self.assertEqual(AUTOGEN_SOURCE_REPOSITORY, "microsoft/autogen")
        self.assertEqual(
            AUTOGEN_SOURCE_COMMIT,
            "027ecf0a379bcc1d09956d46d12d44a3ad9cee14",
        )

    def test_state_payload_is_json_serializable(self) -> None:
        state = save_witness_state([SENT, ABSENCE_AFTER_DEADLINE])
        encoded = json.dumps(state, sort_keys=True)
        self.assertEqual(json.loads(encoded), state)

    def test_save_load_preserves_witness_semantics_and_order(self) -> None:
        state = save_witness_state([SENT, ABSENCE_AFTER_DEADLINE, RESPONSE])
        restored = load_witness_state(state)
        self.assertEqual([w["kind"] for w in restored], ["sent", "absence", "response"])
        self.assertEqual(restored[1]["deadline"], ABSENCE_AFTER_DEADLINE["deadline"])
        self.assertEqual(restored[1]["checked_at"], ABSENCE_AFTER_DEADLINE["checked_at"])
        self.assertEqual(restored[1]["result"], "no_response")

    def test_ambient_clock_is_not_persisted(self) -> None:
        state = save_witness_state([SENT, ABSENCE_AFTER_DEADLINE])
        self.assertNotIn("now", state)
        self.assertNotIn("evaluated_at", state)
        self.assertNotIn("state", state)

    def test_hosted_adapter_is_v01_conformant(self) -> None:
        report = run_witness_projection_conformance(project_saved_autogen_state)
        self.assertTrue(report.conformant)
        self.assertEqual(len(report.checks), 8)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_replay_after_save_load_uses_evidence_only(self) -> None:
        witnesses = [SENT, ABSENCE_AFTER_DEADLINE]
        self.assertEqual(project_saved_autogen_state(witnesses, now=3_000), "expired")
        self.assertEqual(project_saved_autogen_state(witnesses, now=10**12), "expired")
        self.assertEqual(
            project_saved_autogen_state([*witnesses, RESPONSE], now=10**12),
            "accepted",
        )


if __name__ == "__main__":
    unittest.main()
