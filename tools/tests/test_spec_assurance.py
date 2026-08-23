from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.spec_assurance import (  # noqa: E402
    load_spec_assurance_model,
    run_spec_assurance_model,
    spec_assurance_model_from_dict,
    spec_assurance_model_sha256,
)

SCENARIO = ROOT / "scenarios" / "spec-assurance-race-property.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class SpecAssuranceTest(unittest.TestCase):
    def test_reviewed_race_property_detects_full_declared_fault_model(self) -> None:
        result = run_spec_assurance_model(load_spec_assurance_model(SCENARIO))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "assured_over_reviewed_fault_model")
        self.assertEqual(result["mutationScore"], 1.0)
        self.assertEqual(result["survivedMutationIds"], [])
        self.assertEqual(result["unrepresentedRequiredFaultClasses"], [])

    def test_surviving_required_mutation_fails_specification(self) -> None:
        document = _document()
        mutations = document["mutations"]
        assert isinstance(mutations, list)
        mutation = mutations[0]
        assert isinstance(mutation, dict)
        mutation["result"] = "survived"
        result = run_spec_assurance_model(spec_assurance_model_from_dict(document))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["classification"], "weak_specification")
        self.assertEqual(result["requiredSurvivedMutationIds"], ["M-RACE-OVERLAP-001"])

    def test_missing_activation_witness_blocks_pass_as_vacuity_not_excluded(self) -> None:
        document = _document()
        activation = document["activationWitness"]
        assert isinstance(activation, dict)
        activation["observed"] = False
        result = run_spec_assurance_model(spec_assurance_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["classification"], "inconclusive")

    def test_inconclusive_required_mutation_blocks_pass(self) -> None:
        document = _document()
        mutations = document["mutations"]
        assert isinstance(mutations, list)
        mutation = mutations[1]
        assert isinstance(mutation, dict)
        mutation["result"] = "inconclusive"
        result = run_spec_assurance_model(spec_assurance_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["requiredInconclusiveMutationIds"], ["M-RACE-OUTCOME-001"])

    def test_unrepresented_required_fault_class_blocks_pass(self) -> None:
        document = _document()
        required = document["requiredFaultClasses"]
        assert isinstance(required, list)
        required.append("authority-bypass")
        result = run_spec_assurance_model(spec_assurance_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["unrepresentedRequiredFaultClasses"], ["authority-bypass"])

    def test_nonpassing_baseline_blocks_assurance_claim(self) -> None:
        document = _document()
        baseline = document["baseline"]
        assert isinstance(baseline, dict)
        baseline["status"] = "inconclusive"
        result = run_spec_assurance_model(spec_assurance_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")

    def test_duplicate_mutation_id_is_rejected(self) -> None:
        document = _document()
        mutations = document["mutations"]
        assert isinstance(mutations, list)
        duplicate = copy.deepcopy(mutations[0])
        mutations.append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate mutationId"):
            spec_assurance_model_from_dict(document)

    def test_model_hash_is_deterministic(self) -> None:
        first = spec_assurance_model_from_dict(copy.deepcopy(_document()))
        second = spec_assurance_model_from_dict(copy.deepcopy(_document()))
        self.assertEqual(spec_assurance_model_sha256(first), spec_assurance_model_sha256(second))


if __name__ == "__main__":
    unittest.main()
