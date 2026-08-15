import json
import unittest

from build_evidence_graph import build_dot, build_markdown, record_digest


class EvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "run_id": "r1",
            "scenario_id": "T11",
            "pre_state": {"state_id": "READY", "values": {"spent": 20}},
            "request": {"action": "race", "logical_operation_id": "op1"},
            "decision": {"outcome": "accepted"},
            "mutation": {"committed": True},
            "post_state": {"state_id": "SPENT", "values": {"spent": 50}},
            "evidence": {"audit_refs": ["a1"]},
            "invariants": [
                {
                    "id": "INV-01",
                    "rule": "spent <= limit",
                    "verdict": "pass",
                    "observed": "50 <= 60",
                }
            ],
            "verdict": {"state": "pass", "forbidden_state_reached": False},
        }

    def test_digest_is_deterministic(self):
        round_tripped = json.loads(json.dumps(self.record))
        self.assertEqual(record_digest(self.record), record_digest(round_tripped))

    def test_dot_has_full_chain(self):
        dot = build_dot(self.record)
        self.assertIn("pre_state -> request;", dot)
        self.assertIn("post_state -> evidence;", dot)
        self.assertIn("invariant_1 -> verdict;", dot)

    def test_markdown_contains_verdict_and_digest(self):
        md = build_markdown(self.record)
        self.assertIn("Verdict: **pass**", md)
        self.assertIn(record_digest(self.record), md)


if __name__ == "__main__":
    unittest.main()
