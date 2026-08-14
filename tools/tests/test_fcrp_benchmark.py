from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.fcrp_benchmark import score_core_submission


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = json.loads((ROOT / "benchmarks/fcrp-v0.3/cases/FCRP-CORE-001-public.json").read_text())
ORACLE = json.loads((ROOT / "benchmarks/fcrp-v0.3/oracles/FCRP-CORE-001.json").read_text())
COUNTERFACTUAL = json.loads(
    (ROOT / "benchmarks/fcrp-v0.3/oracles/FCRP-CORE-001-counterfactual.json").read_text()
)


def reference_submission() -> dict:
    return {
        "schema": "cgqa.fcrp-submission.v0.1",
        "benchmarkId": "FCRP-CORE-001",
        "facts": ["timeout", "retry", "two charges"],
        "inferences": ["retry key construction is upstream of duplicate settlement"],
        "unknowns": ["provider behavior after stable key repair"],
        "scope": {
            "nodeId": "payment-execution-retry-provider-boundary",
            "parentContract": "order-level charge and receipt invariant",
        },
        "idea": ["one charge per logical order"],
        "timeline": {
            "past": ["retry design chose attempt-level identity"],
            "present": ["two provider operations and two charges are observed"],
            "future": ["stable key is simulated before authorizing the repair"],
        },
        "navigation": ["UP", "DOWN"],
        "causal": {
            "symptomLocation": "D1",
            "fmd": "B1",
            "causalLocation": "B1",
            "refactorLocation": "C1",
            "refactorPoint": "stable-order-scoped-idempotency-key-before-provider-call",
        },
        "simulation": {
            "checkedSurfaces": ["children", "siblings", "parent", "dependencies", "future"],
            "currentPath": "different retry keys → two provider operations → two charges",
            "proposedPath": "stable order key → one provider operation → one charge and receipt",
        },
        "authorization": {"mutationAuthorized": False},
        "verification": {
            "local": "PASS",
            "upward": "PASS",
            "stopBoundary": "one provider operation → one charge → one receipt → order invariant",
        },
    }


class FCRPBenchmarkTest(unittest.TestCase):
    def test_reference_submission_passes(self) -> None:
        result = score_core_submission(PUBLIC, ORACLE, reference_submission())
        self.assertEqual(result["score"], 40)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["criticalFailures"], [])

    def test_symptom_suppression_is_critical_failure(self) -> None:
        submission = reference_submission()
        submission["causal"]["refactorLocation"] = "D1"
        submission["causal"]["refactorPoint"] = "suppress-duplicate-email"

        result = score_core_submission(PUBLIC, ORACLE, submission)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("symptom-suppression-presented-as-repair", result["criticalFailures"])

    def test_counterfactual_oracle_moves_the_causal_location(self) -> None:
        self.assertNotEqual(ORACLE["expected"]["causalLocation"], COUNTERFACTUAL["expected"]["causalLocation"])
        self.assertNotEqual(ORACLE["expected"]["refactorLocation"], COUNTERFACTUAL["expected"]["refactorLocation"])


if __name__ == "__main__":
    unittest.main()
