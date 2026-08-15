import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("detector", HERE / "detect_forbidden_state.py")
detector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(detector)


class ForbiddenStateDetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((HERE / "evidence_record.example.json").read_text(encoding="utf-8"))
        cls.rules = json.loads((HERE / "forbidden_state_rules.example.json").read_text(encoding="utf-8"))

    def test_clean_transition_is_not_a_finding(self):
        result = detector.detect(copy.deepcopy(self.evidence), self.rules)
        self.assertEqual(result["overall"], "not_found_within_observed_transition")
        self.assertFalse(result["forbidden_state_reached"])
        self.assertIsNone(result["finding"])

    def test_limit_crossing_creates_deterministic_finding(self):
        broken = copy.deepcopy(self.evidence)
        broken["post_state"]["values"]["consumed_budget"] = 80
        first = detector.detect(broken, self.rules)
        second = detector.detect(broken, self.rules)
        self.assertEqual(first["overall"], "violated")
        self.assertTrue(first["forbidden_state_reached"])
        self.assertIn("FS-01", first["finding"]["failed_rules"])
        self.assertEqual(first["finding"]["finding_id"], second["finding"]["finding_id"])

    def test_rejected_balance_mutation_is_detected(self):
        broken = copy.deepcopy(self.evidence)
        broken["decision"]["outcome"] = "rejected"
        broken["pre_state"]["values"]["resource_balance"] = 100
        broken["post_state"]["values"]["resource_balance"] = 70
        result = detector.detect(broken, self.rules)
        self.assertEqual(result["overall"], "violated")
        self.assertIn("FS-02", result["finding"]["failed_rules"])

    def test_missing_required_operand_fails_closed(self):
        incomplete = copy.deepcopy(self.evidence)
        del incomplete["post_state"]["values"]["budget_limit"]
        result = detector.detect(incomplete, self.rules)
        self.assertEqual(result["overall"], "inconclusive")
        self.assertFalse(result["forbidden_state_reached"])

    def test_commit_without_audit_is_detected(self):
        broken = copy.deepcopy(self.evidence)
        broken["evidence"]["audit_refs"] = []
        result = detector.detect(broken, self.rules)
        self.assertEqual(result["overall"], "violated")
        self.assertIn("FS-04", result["finding"]["failed_rules"])

    def test_blank_audit_reference_is_treated_as_empty(self):
        broken = copy.deepcopy(self.evidence)
        broken["evidence"]["audit_refs"] = ["   "]
        result = detector.detect(broken, self.rules)
        self.assertEqual(result["overall"], "violated")
        self.assertIn("FS-04", result["finding"]["failed_rules"])

    def test_empty_rules_document_fails_closed(self):
        result = detector.detect(copy.deepcopy(self.evidence), {"rules": []})
        self.assertEqual(result["overall"], "inconclusive")
        self.assertFalse(result["forbidden_state_reached"])
        self.assertIsNone(result["finding"])
        self.assertEqual(result["evaluations"][0]["reason"], "invalid_rule_document")

    def test_malformed_rule_fails_closed(self):
        malformed = {
            "rules": [
                {
                    "id": "BROKEN",
                    "when": [],
                    "assert": {"op": "eq", "left": {"path": "post_state.values.x"}},
                }
            ]
        }
        result = detector.detect(copy.deepcopy(self.evidence), malformed)
        self.assertEqual(result["overall"], "inconclusive")
        self.assertFalse(result["forbidden_state_reached"])
        self.assertIsNone(result["finding"])

    def test_duplicate_rule_is_not_applied_to_concurrent_aggregate(self):
        concurrent = copy.deepcopy(self.evidence)
        concurrent["request"]["action"] = "concurrent_action"
        concurrent["mutation"]["financial_mutation_count"] = 2
        result = detector.detect(concurrent, self.rules)
        fs03 = next(item for item in result["evaluations"] if item["id"] == "FS-03")
        self.assertEqual(fs03["status"], "not_applicable")

    def test_generated_verdict_does_not_change_observation_fingerprint(self):
        first_record = copy.deepcopy(self.evidence)
        second_record = copy.deepcopy(self.evidence)
        second_record["verdict"] = {
            "state": "fail",
            "forbidden_state_reached": True,
            "finding_id": "generated-later",
            "summary": "Generated annotation must not alter the observed-transition fingerprint.",
        }
        first = detector.detect(first_record, self.rules)
        second = detector.detect(second_record, self.rules)
        self.assertEqual(first["evidence_fingerprint"], second["evidence_fingerprint"])


if __name__ == "__main__":
    unittest.main()
