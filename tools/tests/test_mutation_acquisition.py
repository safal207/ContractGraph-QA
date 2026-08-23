from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.mutation_acquisition import (  # noqa: E402
    apply_exact_mutation,
    load_mutation_plan,
    mutation_plan_from_dict,
    mutation_plan_sha256,
    run_mutation_acquisition,
)

PLAN = ROOT / "scenarios" / "escrow-foundry-mutation-plan.json"


def _document() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class MutationAcquisitionTest(unittest.TestCase):
    def test_plan_hash_is_deterministic(self) -> None:
        first = mutation_plan_from_dict(copy.deepcopy(_document()))
        second = mutation_plan_from_dict(copy.deepcopy(_document()))
        self.assertEqual(mutation_plan_sha256(first), mutation_plan_sha256(second))

    def test_exact_mutation_is_source_bound_and_reports_span(self) -> None:
        plan = load_mutation_plan(PLAN)
        source = (ROOT / plan.source_path).read_text(encoding="utf-8")
        mutated, span = apply_exact_mutation(source, plan.mutations[0])
        self.assertNotEqual(source, mutated)
        self.assertIn("if (msg.sender == buyer) revert Unauthorized();", mutated)
        self.assertGreater(span["startLine"], 1)
        self.assertGreater(span["endOffset"], span["startOffset"])

    def test_non_unique_match_is_rejected(self) -> None:
        plan = load_mutation_plan(PLAN)
        mutation = plan.mutations[0]
        with self.assertRaisesRegex(ValueError, "must occur exactly once"):
            apply_exact_mutation(mutation.match + "\n" + mutation.match, mutation)

    def test_parent_traversal_is_rejected(self) -> None:
        document = _document()
        document["sourcePath"] = "../Escrow.sol"
        with self.assertRaisesRegex(ValueError, "must not traverse"):
            mutation_plan_from_dict(document)

    def test_duplicate_mutation_ids_are_rejected(self) -> None:
        document = _document()
        mutations = document["mutations"]
        assert isinstance(mutations, list)
        duplicate = copy.deepcopy(mutations[0])
        mutations.append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate mutationId"):
            mutation_plan_from_dict(document)

    def test_source_sha_mismatch_fails_before_execution(self) -> None:
        document = _document()
        document["sourceSha256"] = "0" * 64
        plan = mutation_plan_from_dict(document)
        with self.assertRaisesRegex(ValueError, "sourceSha256 does not match"):
            run_mutation_acquisition(plan, ROOT)

    @unittest.skipUnless(shutil.which("forge"), "forge is required for mutation integration test")
    def test_repository_mutant_is_compilable_and_detected_by_foundry(self) -> None:
        document = _document()
        mutations = document["mutations"]
        assert isinstance(mutations, list)
        document["mutations"] = [mutations[0]]
        document["requiredFaultClasses"] = ["authorization-inversion"]
        plan = mutation_plan_from_dict(document)
        with tempfile.TemporaryDirectory(prefix="cgqa-mutation-output-") as temp_name:
            output = Path(temp_name) / "evidence"
            result = run_mutation_acquisition(plan, ROOT, output_dir=output)
            self.assertEqual(result["status"], "pass")
            mutation_results = result["mutations"]
            assert isinstance(mutation_results, list)
            self.assertEqual(len(mutation_results), 1)
            self.assertEqual(mutation_results[0]["classification"], "detected")
            self.assertEqual(mutation_results[0]["specAssuranceResult"], "detected")
            spec = result["specAssurance"]
            assert isinstance(spec, dict)
            self.assertEqual(spec["status"], "pass")
            self.assertEqual(spec["classification"], "assured_over_reviewed_fault_model")
            self.assertTrue((output / "mutation-result.json").is_file())
            self.assertTrue(
                (output / "mutants" / "release-auth-inversion" / "src" / "examples" / "Escrow.sol").is_file()
            )


if __name__ == "__main__":
    unittest.main()
