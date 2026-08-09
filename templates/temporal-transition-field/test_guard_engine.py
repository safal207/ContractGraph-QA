import copy
import json
import unittest
from pathlib import Path

from guard_engine import evaluate_transition_guards


HERE = Path(__file__).resolve().parent


class GuardEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guards = json.loads(
            (HERE / "transition_guards.example.json").read_text(encoding="utf-8")
        )

    def test_ready_concurrency_is_allowed_when_budget_remains(self):
        state = {
            "state_id": "Q2_READY",
            "values": {"consumed_budget": 0, "budget_limit": 40, "transaction_count": 0},
        }
        result = evaluate_transition_guards(
            state,
            ("Q2_READY", "concurrent_action", "Q7_RACE"),
            self.guards,
        )
        self.assertEqual(result["status"], "allowed")
        self.assertIn("G-09", result["guard_ids"])

    def test_duplicate_retry_is_blocked_without_prior_transaction(self):
        state = {
            "state_id": "Q2_READY",
            "values": {"consumed_budget": 0, "budget_limit": 40, "transaction_count": 0},
        }
        result = evaluate_transition_guards(
            state,
            ("Q2_READY", "duplicate_retry", "Q6_REPLAY_CHECK"),
            self.guards,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("G-07", result["guard_ids"])

    def test_action_is_blocked_when_limit_is_full(self):
        state = {
            "state_id": "Q3_COMMITTED",
            "values": {"consumed_budget": 40, "budget_limit": 40, "transaction_count": 2},
        }
        result = evaluate_transition_guards(
            state,
            ("Q3_COMMITTED", "action_valid", "Q3_COMMITTED"),
            self.guards,
        )
        self.assertEqual(result["status"], "blocked")

    def test_missing_guard_operand_is_inconclusive(self):
        state = {
            "state_id": "Q3_COMMITTED",
            "values": {"consumed_budget": 20, "transaction_count": 1},
        }
        result = evaluate_transition_guards(
            state,
            ("Q3_COMMITTED", "action_valid", "Q3_COMMITTED"),
            self.guards,
        )
        self.assertEqual(result["status"], "inconclusive")

    def test_undeclared_guard_defaults_to_allowed(self):
        state = {"state_id": "Q2_READY", "values": {}}
        result = evaluate_transition_guards(
            state,
            ("Q2_READY", "action_invalid", "Q5_REJECTED"),
            self.guards,
        )
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["reason"], "no_guard_declared")


if __name__ == "__main__":
    unittest.main()
