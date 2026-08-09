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


if __name__ == "__main__":
    unittest.main()
