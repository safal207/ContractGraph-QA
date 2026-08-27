from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.causal_repair import (  # noqa: E402
    causal_repair_model_from_dict,
    causal_repair_model_sha256,
    load_causal_repair_model,
    run_causal_repair_model,
)

SCENARIO = ROOT / "scenarios" / "milepact-causal-repair-dispute-cutoff.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class CausalRepairTest(unittest.TestCase):
    def test_milepact_cutoff_repairs_race_but_reports_remaining_dead_end(self) -> None:
        result = run_causal_repair_model(load_causal_repair_model(SCENARIO))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "partial_repair")
        self.assertEqual(result["repairedTargetInvariantIds"], ["CGQ-RACE-001"])
        self.assertEqual(result["preExistingFailureInvariantIds"], ["CGQ-LIVE-001"])
        self.assertEqual(result["regressedGuardInvariantIds"], [])

    def test_fully_clean_candidate_is_verified_repair(self) -> None:
        document = _document()
        candidate = document["candidate"]
        assert isinstance(candidate, dict)
        results = candidate["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-LIVE-001":
                item["status"] = "pass"
        result = run_causal_repair_model(causal_repair_model_from_dict(document))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "verified_repair")
        self.assertEqual(result["preExistingFailureInvariantIds"], [])

    def test_target_that_still_fails_is_no_effect(self) -> None:
        document = _document()
        candidate = document["candidate"]
        assert isinstance(candidate, dict)
        results = candidate["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-RACE-001":
                item["status"] = "fail"
        result = run_causal_repair_model(causal_repair_model_from_dict(document))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["classification"], "no_effect")
        self.assertEqual(result["unresolvedTargetInvariantIds"], ["CGQ-RACE-001"])

    def test_guard_regression_overrides_target_repair(self) -> None:
        document = _document()
        candidate = document["candidate"]
        assert isinstance(candidate, dict)
        results = candidate["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-SAFE-001":
                item["status"] = "fail"
        result = run_causal_repair_model(causal_repair_model_from_dict(document))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["classification"], "regression")
        self.assertEqual(result["regressedGuardInvariantIds"], ["CGQ-SAFE-001"])

    def test_weakened_guard_evidence_is_inconclusive(self) -> None:
        document = _document()
        candidate = document["candidate"]
        assert isinstance(candidate, dict)
        results = candidate["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-CONS-001":
                item["status"] = "inconclusive"
        result = run_causal_repair_model(causal_repair_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["classification"], "inconclusive")
        self.assertEqual(result["weakenedGuardEvidenceInvariantIds"], ["CGQ-CONS-001"])

    def test_target_must_be_a_proven_baseline_failure(self) -> None:
        document = _document()
        baseline = document["baseline"]
        assert isinstance(baseline, dict)
        results = baseline["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-RACE-001":
                item["status"] = "pass"
        result = run_causal_repair_model(causal_repair_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["classification"], "inconclusive")

    def test_target_and_guard_sets_must_be_disjoint(self) -> None:
        document = _document()
        document["guardInvariantIds"] = ["CGQ-RACE-001"]
        with self.assertRaisesRegex(ValueError, "must be disjoint"):
            causal_repair_model_from_dict(document)

    def test_model_hash_is_deterministic(self) -> None:
        document = _document()
        first = causal_repair_model_from_dict(copy.deepcopy(document))
        second = causal_repair_model_from_dict(copy.deepcopy(document))
        self.assertEqual(causal_repair_model_sha256(first), causal_repair_model_sha256(second))


if __name__ == "__main__":
    unittest.main()
