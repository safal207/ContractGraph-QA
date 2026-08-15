import json
import unittest
from pathlib import Path

from auto_path_to_finding import search_paths
from synthetic_adapter import SyntheticBuggyAdapter, SyntheticSafeAdapter


HERE = Path(__file__).resolve().parent


class AutomaticPathToFindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads(
            (HERE / "forbidden_state_rules.example.json").read_text(encoding="utf-8")
        )
        cls.guards = json.loads(
            (HERE / "transition_guards.example.json").read_text(encoding="utf-8")
        )

    def test_buggy_adapter_finds_shortest_guarded_concurrency_path(self):
        result = search_paths(
            SyntheticBuggyAdapter,
            self.rules,
            guards_document=self.guards,
            max_depth=6,
            max_paths=250,
        )
        self.assertEqual(result["overall"], "violated")
        self.assertTrue(result["finding"]["forbidden_state_reached"])
        self.assertIn("FS-01", result["finding"]["failed_rules"])
        self.assertEqual(
            [step["event"] for step in result["minimal_path"]],
            ["fund", "set_policy", "concurrent_action"],
        )
        self.assertEqual(result["violating_step"], 3)
        self.assertTrue(result["guards_enabled"])

    def test_safe_adapter_has_no_finding_within_guarded_bound(self):
        result = search_paths(
            SyntheticSafeAdapter,
            self.rules,
            guards_document=self.guards,
            max_depth=6,
            max_paths=250,
        )
        self.assertEqual(result["overall"], "not_found_within_bound")
        self.assertFalse(result["finding"])
        self.assertIsNone(result["minimal_path"])
        self.assertGreater(result["paths_pruned_by_guard"], 0)
        self.assertGreater(result["guard_stats"]["blocked"], 0)

    def test_finding_id_is_deterministic_for_same_guarded_search(self):
        first = search_paths(
            SyntheticBuggyAdapter,
            self.rules,
            guards_document=self.guards,
            max_depth=6,
            max_paths=250,
        )
        second = search_paths(
            SyntheticBuggyAdapter,
            self.rules,
            guards_document=self.guards,
            max_depth=6,
            max_paths=250,
        )
        self.assertEqual(first["finding"]["finding_id"], second["finding"]["finding_id"])

    def test_search_is_bounded_by_max_paths(self):
        result = search_paths(
            SyntheticSafeAdapter,
            self.rules,
            guards_document=self.guards,
            max_depth=6,
            max_paths=2,
        )
        self.assertLessEqual(result["paths_explored"], 2)
        self.assertEqual(result["max_paths"], 2)

    def test_guards_can_be_disabled_for_v04_compatibility(self):
        result = search_paths(SyntheticBuggyAdapter, self.rules, max_depth=6, max_paths=250)
        self.assertEqual(result["overall"], "violated")
        self.assertFalse(result["guards_enabled"])

    def test_invalid_bounds_fail_fast(self):
        with self.assertRaises(ValueError):
            search_paths(SyntheticSafeAdapter, self.rules, max_depth=0)
        with self.assertRaises(ValueError):
            search_paths(SyntheticSafeAdapter, self.rules, max_paths=0)


if __name__ == "__main__":
    unittest.main()
