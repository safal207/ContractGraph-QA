import copy
import json
import unittest
from pathlib import Path

from adapter_contract import (
    AdapterContractError,
    ContractBoundAdapter,
    enforce_search_bounds,
    validate_manifest,
    validate_model_coverage,
)
from auto_path_to_finding import search_paths
from generate_paths import SPEC, parse_transitions
from synthetic_adapter import SyntheticBuggyAdapter


HERE = Path(__file__).resolve().parent


class AdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((HERE / "adapter_manifest.synthetic.json").read_text(encoding="utf-8"))
        cls.rules = json.loads((HERE / "forbidden_state_rules.example.json").read_text(encoding="utf-8"))
        cls.guards = json.loads((HERE / "transition_guards.example.json").read_text(encoding="utf-8"))
        cls.transitions = parse_transitions(SPEC.read_text(encoding="utf-8"))

    def test_valid_manifest_and_model_coverage(self):
        validated = validate_manifest(copy.deepcopy(self.manifest))
        validate_model_coverage(validated, self.transitions)
        self.assertEqual(validated["adapter_id"], "synthetic-budget-v1")

    def test_production_scope_is_rejected(self):
        broken = copy.deepcopy(self.manifest)
        broken["scope"]["production"] = True
        with self.assertRaises(AdapterContractError):
            validate_manifest(broken)

    def test_literal_secret_container_is_rejected(self):
        broken = copy.deepcopy(self.manifest)
        broken["api_key"] = "must-never-live-in-manifest"
        with self.assertRaises(AdapterContractError):
            validate_manifest(broken)

    def test_missing_model_event_is_rejected_before_execution(self):
        broken = copy.deepcopy(self.manifest)
        broken["capabilities"]["supported_events"].remove("concurrent_action")
        with self.assertRaises(AdapterContractError):
            validate_model_coverage(validate_manifest(broken), self.transitions)

    def test_search_bounds_cannot_exceed_manifest(self):
        with self.assertRaises(AdapterContractError):
            enforce_search_bounds(self.manifest, max_depth=7, max_paths=250)
        with self.assertRaises(AdapterContractError):
            enforce_search_bounds(self.manifest, max_depth=6, max_paths=251)

    def test_snapshot_contract_is_enforced(self):
        class MissingStateAdapter(SyntheticBuggyAdapter):
            def snapshot(self):
                snap = super().snapshot()
                snap["values"].pop("budget_limit")
                return snap

        with self.assertRaises(AdapterContractError):
            ContractBoundAdapter(MissingStateAdapter(), self.manifest)

    def test_observation_action_must_match_event(self):
        class WrongActionAdapter(SyntheticBuggyAdapter):
            def apply(self, event):
                observation = super().apply(event)
                observation["request"]["action"] = "different_event"
                return observation

        wrapped = ContractBoundAdapter(WrongActionAdapter(), self.manifest)
        with self.assertRaises(AdapterContractError):
            wrapped.apply("fund")

    def test_contract_bound_search_preserves_minimal_finding_and_scope(self):
        result = search_paths(
            SyntheticBuggyAdapter,
            self.rules,
            guards_document=self.guards,
            adapter_manifest=self.manifest,
            max_depth=6,
            max_paths=250,
        )
        self.assertEqual(result["overall"], "violated")
        self.assertTrue(result["adapter_contract_enabled"])
        self.assertEqual(result["adapter_id"], "synthetic-budget-v1")
        self.assertEqual(
            [step["event"] for step in result["minimal_path"]],
            ["fund", "set_policy", "concurrent_action"],
        )
        self.assertEqual(result["records"][0]["scope"]["target"], "synthetic-budget-state-machine")


if __name__ == "__main__":
    unittest.main()
