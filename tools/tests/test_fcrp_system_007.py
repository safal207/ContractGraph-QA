from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.run_fcrp_system_007 import (
    System007Error,
    assert_reflection_boundary,
    compare_declared_heads,
    validate_intent,
)


ROOT = Path(__file__).resolve().parents[2]
INTENT_PATH = ROOT / "benchmarks/system-native/FCRP-SYSTEM-007-intent.json"


class FcrpSystem007UnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intent = json.loads(INTENT_PATH.read_text(encoding="utf-8"))

    def test_intent_fixture_is_canonical_and_non_authorizing(self) -> None:
        identity = validate_intent(self.intent)
        self.assertEqual(identity["logical_operation_id"], "neo-resonance-system-007-001")
        self.assertEqual(identity["argument_digest"], self.intent["argument_digest"])

    def test_missing_intent_is_rejected(self) -> None:
        with self.assertRaises(System007Error):
            validate_intent({})

    def test_replayed_nonce_is_rejected(self) -> None:
        with self.assertRaisesRegex(System007Error, "nonce"):
            validate_intent(self.intent, used_nonces={self.intent["nonce"]})

    def test_changed_argument_under_old_digest_is_rejected(self) -> None:
        changed = copy.deepcopy(self.intent)
        changed["arguments"]["expected_decision"] = "ALLOW"
        with self.assertRaisesRegex(System007Error, "argument_digest"):
            validate_intent(changed)

    def test_stale_dependency_head_is_rejected(self) -> None:
        observed = {"proofpath": "a" * 40}
        expected = {"proofpath": "b" * 40}
        with self.assertRaisesRegex(System007Error, "stale dependency head"):
            compare_declared_heads(observed, expected)

    def test_reflection_execution_escalation_is_rejected(self) -> None:
        loop = {
            "source_mutated": False,
            "write_back_performed": False,
            "graph": {
                "verdict": "ACCEPT_WITH_LIMITS",
                "authority": {
                    "classification": "REFLECTION_ONLY",
                    "truth_authorized": False,
                    "execution_authorized": False,
                    "mutation_authorized": False,
                },
                "candidate_handoffs": [{"execution_allowed": False}],
            },
        }
        assert_reflection_boundary(loop)
        escalated = copy.deepcopy(loop)
        escalated["graph"]["candidate_handoffs"][0]["execution_allowed"] = True
        with self.assertRaisesRegex(System007Error, "executable"):
            assert_reflection_boundary(escalated)


if __name__ == "__main__":
    unittest.main()
