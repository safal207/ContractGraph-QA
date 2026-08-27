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

from contractgraph_qa.fault_coverage import build_fault_coverage_matrix  # noqa: E402
from contractgraph_qa.fault_mutation_generator import (  # noqa: E402
    _function_by_line,
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

    def test_function_map_resets_when_brace_is_on_the_next_line(self) -> None:
        source = """contract C {
    function fund()
        external
        payable
    {
        if (msg.sender != owner) revert Auth();
    }

    function refund()
        external
    {
        if (msg.sender != owner) revert Auth();
        depositedAmount = 0;
    }

    function foo() {}
}
"""
        names = _function_by_line(source)
        lines = source.splitlines()
        by_line = {index + 1: names[index] for index in range(len(lines))}
        self.assertEqual(by_line[6], "fund")
        self.assertEqual(by_line[12], "refund")
        self.assertEqual(by_line[13], "refund")
        self.assertEqual(by_line[16], "foo")
        self.assertEqual(by_line[17], "<contract>")

    def test_next_line_braces_bind_mutations_to_the_owning_function(self) -> None:
        import hashlib
        import tempfile

        source = """contract C {
    address owner;
    uint256 depositedAmount;
    function fund()
        external
        payable
    {
        if (msg.sender != owner) revert Auth();
        depositedAmount = msg.value;
    }

    function refund()
        external
    {
        if (msg.sender != owner) revert Auth();
        depositedAmount = 0;
    }
}
"""
        source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = Path("src") / "C.sol"
            (root / rel).parent.mkdir(parents=True)
            (root / rel).write_text(source, encoding="utf-8")
            config = generator_config_from_dict(
                {
                    "schemaVersion": "fault-mutation-generator-v0.1",
                    "generationId": "brace-style",
                    "sourcePath": rel.as_posix(),
                    "sourceSha256": source_sha,
                    "propertyInvariantId": "INV-1",
                    "propertyDescription": "auth",
                    "activationWitness": {
                        "observed": True,
                        "evidenceSha256": "a" * 64,
                        "description": "reviewed",
                    },
                    "requiredFaultClasses": ["authorization"],
                    "foundry": {"profile": "default", "timeoutSeconds": 30},
                    "testBindings": [
                        {
                            "faultClass": "authorization",
                            "function": "refund",
                            "matchPath": "test/C.t.sol",
                            "matchTest": "testRefundAuth",
                        }
                    ],
                    "maxMutationsPerFaultClass": 10,
                }
            )
            result = generate_fault_mutation_plan(config, root)
        discovered = result["discoveredCandidates"]
        assert isinstance(discovered, list)
        refund_hits = [
            item
            for item in discovered
            if isinstance(item, dict) and item.get("function") == "refund"
        ]
        fund_hits = [
            item
            for item in discovered
            if isinstance(item, dict) and item.get("function") == "fund"
        ]
        self.assertEqual(len(refund_hits), 1)
        self.assertEqual(len(fund_hits), 1)
        self.assertEqual(result["generatedMutationCount"], 1)
        plan = result["mutationPlan"]
        assert isinstance(plan, dict)
        self.assertEqual(plan["mutations"][0]["matchTest"], "testRefundAuth")
        self.assertIn("refund()", plan["mutations"][0]["description"])

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
        coverage = build_fault_coverage_matrix(generated, acquisition)
        self.assertEqual(coverage["status"], "pass")
        self.assertEqual(coverage["coveredFaultClasses"], ["authorization", "time_boundary"])
        self.assertEqual(coverage["totals"]["reviewedKillRate"], 1.0)


if __name__ == "__main__":
    unittest.main()
