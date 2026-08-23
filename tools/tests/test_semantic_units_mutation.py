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

from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict, run_mutation_acquisition  # noqa: E402
from contractgraph_qa.semantic_units_mutation import (  # noqa: E402
    generate_semantic_units_mutation_plan,
    load_semantic_units_config,
    semantic_units_config_from_dict,
)

SCENARIO = ROOT / "scenarios" / "decimal-scaler-semantic-units.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class SemanticUnitsMutationTest(unittest.TestCase):
    def test_config_rejects_unsupported_fault_class(self) -> None:
        document = _document()
        document["requiredFaultClasses"] = ["units_decimals", "replay_version"]
        with self.assertRaisesRegex(ValueError, "supports only units_decimals"):
            semantic_units_config_from_dict(document)

    def test_config_rejects_expected_decimal_as_alternative(self) -> None:
        document = _document()
        bindings = document["unitBindings"]
        assert isinstance(bindings, list)
        first = bindings[0]
        assert isinstance(first, dict)
        first["alternateDecimals"] = [6, 18]
        with self.assertRaisesRegex(ValueError, "must not contain expectedDecimals"):
            semantic_units_config_from_dict(document)

    def test_source_hash_mismatch_fails_before_ast_execution(self) -> None:
        document = _document()
        document["sourceSha256"] = "0" * 64
        config = semantic_units_config_from_dict(document)
        with self.assertRaisesRegex(ValueError, "sourceSha256 does not match"):
            generate_semantic_units_mutation_plan(config, ROOT)

    @unittest.skipUnless(shutil.which("forge"), "Forge is required for compiler-AST semantic mutation tests")
    def test_compiler_ast_confirms_two_reviewed_unit_bindings(self) -> None:
        result = generate_semantic_units_mutation_plan(load_semantic_units_config(SCENARIO), ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "generated_reviewed_semantic_mutations")
        self.assertEqual(result["generatedMutationCount"], 2)
        self.assertEqual(result["representedFaultClasses"], ["units_decimals"])
        self.assertEqual(result["ambiguousCandidates"], [])
        ast_sha = result["astSha256"]
        self.assertIsInstance(ast_sha, str)
        self.assertEqual(len(ast_sha), 64)
        plan = result["mutationPlan"]
        self.assertIsInstance(plan, dict)
        assert isinstance(plan, dict)
        parsed = mutation_plan_from_dict(plan)
        self.assertEqual(
            [item.mutation_id for item in parsed.mutations],
            ["unit-asset_decimals-6-to-18", "unit-price_decimals-8-to-18"],
        )
        self.assertTrue(all(item.fault_class == "units_decimals" for item in parsed.mutations))

    @unittest.skipUnless(shutil.which("forge"), "Forge is required for compiler-AST semantic mutation tests")
    def test_reviewed_decimal_mismatch_is_inconclusive_not_guessed(self) -> None:
        document = copy.deepcopy(_document())
        bindings = document["unitBindings"]
        assert isinstance(bindings, list)
        first = bindings[0]
        assert isinstance(first, dict)
        first["expectedDecimals"] = 7
        first["alternateDecimals"] = [18]
        result = generate_semantic_units_mutation_plan(semantic_units_config_from_dict(document), ROOT)
        self.assertEqual(result["status"], "inconclusive")
        unresolved = result["ambiguousCandidates"]
        assert isinstance(unresolved, list)
        self.assertTrue(any(isinstance(item, dict) and item.get("symbol") == "ASSET_DECIMALS" for item in unresolved))
        plan = result["mutationPlan"]
        self.assertIsInstance(plan, dict)
        assert isinstance(plan, dict)
        self.assertEqual(len(plan["mutations"]), 1)

    @unittest.skipUnless(shutil.which("forge"), "Forge is required for semantic mutation execution integration")
    def test_ast_generated_decimal_mutants_compile_and_are_detected(self) -> None:
        generation = generate_semantic_units_mutation_plan(load_semantic_units_config(SCENARIO), ROOT)
        self.assertEqual(generation["status"], "pass")
        plan = generation["mutationPlan"]
        assert isinstance(plan, dict)
        execution = run_mutation_acquisition(mutation_plan_from_dict(plan), ROOT)
        self.assertEqual(execution["status"], "pass")
        mutations = execution["mutations"]
        assert isinstance(mutations, list)
        self.assertEqual(len(mutations), 2)
        self.assertTrue(all(isinstance(item, dict) and item["classification"] == "detected" for item in mutations))
        spec = execution["specAssurance"]
        assert isinstance(spec, dict)
        self.assertEqual(spec["status"], "pass")
        self.assertEqual(spec["mutationScore"], 1.0)


if __name__ == "__main__":
    unittest.main()
