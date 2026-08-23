from __future__ import annotations

import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.fault_mutation_generator import (  # noqa: E402
    generate_fault_mutation_plan,
    generator_config_from_dict,
    load_generator_config,
)
from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict, run_mutation_acquisition  # noqa: E402

SCENARIO = ROOT / "scenarios" / "escrow-auto-fault-generator.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class FaultMutationGeneratorTest(unittest.TestCase):
    def test_repository_escrow_generates_all_supported_required_classes(self) -> None:
        result = generate_fault_mutation_plan(load_generator_config(SCENARIO), ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "generated_complete_review_set")
        self.assertEqual(result["generatedMutationCount"], 14)
        self.assertEqual(
            result["representedFaultClasses"],
            ["accounting", "authorization", "state_transition", "time_boundary"],
        )
        self.assertEqual(result["unsupportedRequiredFaultClasses"], [])
        plan = result["mutationPlan"]
        self.assertIsInstance(plan, dict)
        assert isinstance(plan, dict)
        self.assertEqual(len(plan["mutations"]), 14)
        mutation_plan_from_dict(plan)

    def test_replay_and_units_are_explicitly_unsupported(self) -> None:
        document = _document()
        document["requiredFaultClasses"] = ["authorization", "replay_version", "units_decimals"]
        result = generate_fault_mutation_plan(generator_config_from_dict(document), ROOT)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["classification"], "incomplete_generation")
        self.assertEqual(result["unsupportedRequiredFaultClasses"], ["replay_version", "units_decimals"])
        plan = result["mutationPlan"]
        assert isinstance(plan, dict)
        self.assertEqual(plan["requiredFaultClasses"], ["authorization", "replay_version", "units_decimals"])

    def test_missing_test_binding_is_fail_closed(self) -> None:
        document = _document()
        bindings = document["testBindings"]
        assert isinstance(bindings, list)
        document["testBindings"] = [
            item
            for item in bindings
            if not (isinstance(item, dict) and item.get("faultClass") == "time_boundary")
        ]
        result = generate_fault_mutation_plan(generator_config_from_dict(document), ROOT)
        self.assertEqual(result["status"], "inconclusive")
        self.assertIn("time_boundary", result["unboundFaultClasses"])
        self.assertIn("time_boundary", result["missingCandidateFaultClasses"])

    def test_source_hash_mismatch_is_rejected(self) -> None:
        document = _document()
        document["sourceSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "sourceSha256 does not match"):
            generate_fault_mutation_plan(generator_config_from_dict(document), ROOT)

    def test_generation_is_deterministic(self) -> None:
        first = generate_fault_mutation_plan(generator_config_from_dict(copy.deepcopy(_document())), ROOT)
        second = generate_fault_mutation_plan(generator_config_from_dict(copy.deepcopy(_document())), ROOT)
        self.assertEqual(first, second)

    @unittest.skipUnless(shutil.which("forge"), "Forge is required for mutation execution integration")
    def test_generated_authorization_and_time_mutants_are_killed_by_foundry(self) -> None:
        document = _document()
        document["requiredFaultClasses"] = ["authorization", "time_boundary"]
        document["maxMutationsPerFaultClass"] = 1
        bindings = document["testBindings"]
        assert isinstance(bindings, list)
        document["testBindings"] = [
            item
            for item in bindings
            if isinstance(item, dict) and item.get("faultClass") in {"authorization", "time_boundary"}
        ]
        generated = generate_fault_mutation_plan(generator_config_from_dict(document), ROOT)
        self.assertEqual(generated["status"], "pass")
        plan = generated["mutationPlan"]
        assert isinstance(plan, dict)
        self.assertEqual(len(plan["mutations"]), 2)
        acquisition = run_mutation_acquisition(mutation_plan_from_dict(plan), ROOT)
        results = acquisition["mutations"]
        assert isinstance(results, list)
        self.assertTrue(results)
        self.assertTrue(all(item["classification"] == "detected" for item in results if isinstance(item, dict)))
        spec = acquisition["specAssurance"]
        assert isinstance(spec, dict)
        self.assertEqual(spec["status"], "pass")


if __name__ == "__main__":
    unittest.main()
