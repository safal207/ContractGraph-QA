from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp_v02 import FCRPV02Error, evaluate_fcrp_v02_case


CASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "fcrp-v0.2"
    / "FCRP-V02-PORT-001-liminalosai-authority.json"
)


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


class FCRPV02ContractTest(unittest.TestCase):
    def test_v02_portability_case_passes_without_granting_mutation_authority(self) -> None:
        case = load_case()
        result = evaluate_fcrp_v02_case(case)

        self.assertEqual(result["schema"], "cgqa.fcrp-result.v0.2")
        self.assertEqual(result["caseId"], "FCRP-V02-PORT-001")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["firstMeaningfulDivergence"], "N1")
        self.assertEqual(result["causePoint"], "N1")
        self.assertEqual(result["refactorPoint"], "N3")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["primaryTimeDomain"], "CAUSAL_SEQUENCE")
        self.assertEqual(result["simulationStatus"], "PASS")
        self.assertFalse(result["mutationAuthorized"])
        self.assertTrue(result["causalPropagationStopped"])
        self.assertTrue(result["stopConditionsSatisfied"])
        self.assertEqual(
            result["evidenceStrengths"]["E-LIMINAL-SELF009"],
            "RECOMPUTABLE",
        )
        self.assertEqual(result["decision"], case["expectedProtocolDecision"])

    def test_evidence_cannot_grant_authority(self) -> None:
        case = load_case()
        case["evidence"][0]["mayGrantAuthority"] = True

        with self.assertRaisesRegex(FCRPV02Error, "may not itself grant authority"):
            evaluate_fcrp_v02_case(case)

    def test_authorization_boundary_cannot_promote_evidence_to_authority(self) -> None:
        case = load_case()
        case["authorization"]["evidenceMayGrantAuthority"] = True

        with self.assertRaisesRegex(FCRPV02Error, "must be false"):
            evaluate_fcrp_v02_case(case)

    def test_mutation_authority_requires_separate_authorization_reference(self) -> None:
        case = load_case()
        case["authorization"]["mutationAuthorized"] = True
        case["authorization"]["authorizationRef"] = None

        with self.assertRaisesRegex(FCRPV02Error, "authorizationRef"):
            evaluate_fcrp_v02_case(case)

    def test_causal_advance_requires_evidence_when_time_model_requires_it(self) -> None:
        case = load_case()
        case["timeModel"]["causalAdvanceRequired"] = True
        case["timeModel"]["causalAdvanceEvidenceRefs"] = []

        with self.assertRaisesRegex(FCRPV02Error, "causalAdvanceEvidenceRefs"):
            evaluate_fcrp_v02_case(case)

    def test_upward_not_required_needs_explicit_causal_propagation_stop(self) -> None:
        case = load_case()
        case["verification"]["upward"] = "NOT_REQUIRED"
        case["verification"]["stopConditions"]["causalPropagationStopped"] = False

        with self.assertRaisesRegex(FCRPV02Error, "all four stop conditions"):
            evaluate_fcrp_v02_case(case)

    def test_simulation_failure_blocks_even_when_local_and_upward_pass(self) -> None:
        case = load_case()
        case["simulation"]["status"] = "FAIL"
        case["simulation"]["evidenceRefs"] = ["E-LIMINAL-SELF009"]

        result = evaluate_fcrp_v02_case(case)
        self.assertEqual(result["decision"], "BLOCK")

    def test_v01_module_remains_independent(self) -> None:
        from contractgraph_qa.fcrp import FCRP_SCHEMA

        self.assertEqual(FCRP_SCHEMA, "cgqa.fcrp-case.v0.1")
        self.assertNotEqual(load_case()["schema"], FCRP_SCHEMA)


if __name__ == "__main__":
    unittest.main()
