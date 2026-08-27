from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.repair_search import (  # noqa: E402
    load_repair_search_model,
    repair_search_model_from_dict,
    repair_search_model_sha256,
    run_repair_search_model,
)

SCENARIO = ROOT / "scenarios" / "milepact-minimal-repair-search.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class RepairSearchTest(unittest.TestCase):
    def test_milepact_selects_two_change_minimal_verified_repair(self) -> None:
        result = run_repair_search_model(load_repair_search_model(SCENARIO))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "minimal_verified_repair")
        self.assertEqual(result["minimumRepairCount"], 2)
        self.assertEqual(result["verifiedCandidateSetCount"], 2)
        selected = result["selectedRepair"]
        assert isinstance(selected, dict)
        self.assertEqual(selected["candidateSetId"], "cutoff-plus-resolve")
        self.assertEqual(
            selected["repairIds"],
            ["explicit-dispute-cutoff", "resolve-disputed-state"],
        )
        minimal = result["minimalVerifiedCandidates"]
        assert isinstance(minimal, list)
        self.assertEqual([item["candidateSetId"] for item in minimal], ["cutoff-plus-resolve"])

    def test_single_repairs_are_not_misreported_as_full_repair(self) -> None:
        result = run_repair_search_model(load_repair_search_model(SCENARIO))
        evaluations = {
            item["candidateSetId"]: item
            for item in result["candidateEvaluations"]
            if isinstance(item, dict)
        }
        self.assertEqual(evaluations["cutoff-only"]["classification"], "partial_repair")
        self.assertEqual(evaluations["resolve-only"]["classification"], "partial_repair")
        self.assertEqual(evaluations["ui-only"]["classification"], "no_effect")

    def test_guard_regression_disqualifies_otherwise_complete_candidate(self) -> None:
        document = _document()
        candidate_sets = document["candidateSets"]
        assert isinstance(candidate_sets, list)
        for candidate in candidate_sets:
            if isinstance(candidate, dict) and candidate.get("candidateSetId") == "cutoff-plus-resolve":
                assessment = candidate["assessment"]
                assert isinstance(assessment, dict)
                results = assessment["invariantResults"]
                assert isinstance(results, list)
                for item in results:
                    if isinstance(item, dict) and item.get("invariantId") == "CGQ-SAFE-001":
                        item["status"] = "fail"
        result = run_repair_search_model(repair_search_model_from_dict(document))
        self.assertEqual(result["minimumRepairCount"], 3)
        selected = result["selectedRepair"]
        assert isinstance(selected, dict)
        self.assertEqual(selected["candidateSetId"], "all-three")
        evaluations = {
            item["candidateSetId"]: item
            for item in result["candidateEvaluations"]
            if isinstance(item, dict)
        }
        self.assertEqual(evaluations["cutoff-plus-resolve"]["classification"], "regression")

    def test_inconclusive_smaller_candidate_does_not_beat_verified_larger_candidate(self) -> None:
        document = _document()
        candidate_sets = document["candidateSets"]
        assert isinstance(candidate_sets, list)
        for candidate in candidate_sets:
            if isinstance(candidate, dict) and candidate.get("candidateSetId") == "cutoff-only":
                assessment = candidate["assessment"]
                assert isinstance(assessment, dict)
                results = assessment["invariantResults"]
                assert isinstance(results, list)
                for item in results:
                    if isinstance(item, dict) and item.get("invariantId") == "CGQ-LIVE-001":
                        item["status"] = "inconclusive"
        result = run_repair_search_model(repair_search_model_from_dict(document))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["minimumRepairCount"], 2)

    def test_unknown_repair_reference_is_rejected(self) -> None:
        document = _document()
        candidate_sets = document["candidateSets"]
        assert isinstance(candidate_sets, list)
        candidate = candidate_sets[0]
        assert isinstance(candidate, dict)
        candidate["repairIds"] = ["does-not-exist"]
        with self.assertRaisesRegex(ValueError, "unknown repairs"):
            repair_search_model_from_dict(document)

    def test_duplicate_candidate_composition_is_rejected(self) -> None:
        document = _document()
        candidate_sets = document["candidateSets"]
        assert isinstance(candidate_sets, list)
        duplicate = copy.deepcopy(candidate_sets[0])
        assert isinstance(duplicate, dict)
        duplicate["candidateSetId"] = "duplicate-cutoff"
        candidate_sets.append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate candidate repair composition"):
            repair_search_model_from_dict(document)

    def test_invalid_baseline_blocks_minimality_claim(self) -> None:
        document = _document()
        baseline = document["baseline"]
        assert isinstance(baseline, dict)
        results = baseline["invariantResults"]
        assert isinstance(results, list)
        for item in results:
            if isinstance(item, dict) and item.get("invariantId") == "CGQ-RACE-001":
                item["status"] = "pass"
        result = run_repair_search_model(repair_search_model_from_dict(document))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["classification"], "inconclusive")
        self.assertIsNone(result["selectedRepair"])

    def test_model_hash_is_deterministic(self) -> None:
        first = repair_search_model_from_dict(copy.deepcopy(_document()))
        second = repair_search_model_from_dict(copy.deepcopy(_document()))
        self.assertEqual(repair_search_model_sha256(first), repair_search_model_sha256(second))


if __name__ == "__main__":
    unittest.main()
