from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.runtime_conformance_matrix import (
    AXES,
    load_runtime_conformance_matrix,
    summarize_runtime_conformance_matrix,
    validate_runtime_conformance_matrix,
)


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "benchmarks" / "agent-runtime-conformance-matrix-v0.1" / "matrix.json"


class AgentRuntimeConformanceMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = load_runtime_conformance_matrix(MATRIX_PATH)

    def test_matrix_has_frozen_axes_and_five_source_pinned_runtimes(self) -> None:
        self.assertEqual(tuple(self.matrix["axes"]), AXES)
        self.assertEqual(len(self.matrix["runtimes"]), 5)
        self.assertEqual(
            [runtime["id"] for runtime in self.matrix["runtimes"]],
            [
                "crewai",
                "langgraph",
                "autogen",
                "microsoft-agent-framework",
                "openai-agents-sdk",
            ],
        )

    def test_matrix_projection_scores_match_source_benchmark_results(self) -> None:
        for runtime in self.matrix["runtimes"]:
            result_path = ROOT / runtime["benchmarkResult"]
            self.assertTrue(result_path.is_file(), runtime["benchmarkResult"])
            result = json.loads(result_path.read_text(encoding="utf-8"))

            self.assertEqual(result["source"]["repository"], runtime["source"]["repository"])
            self.assertEqual(result["source"]["commit"], runtime["source"]["commit"])
            self.assertEqual(result["spec"], self.matrix["projectionSpec"])

            passed = len(result["expectedPassedChecks"])
            failed = len(result["expectedFailedChecks"])
            self.assertEqual(passed + failed, 8)
            self.assertEqual(runtime["projection"]["passed"], passed)
            self.assertEqual(runtime["projection"]["total"], 8)
            self.assertEqual(runtime["projection"]["status"], "pass" if failed == 0 else "fail")

            self.assertEqual(
                runtime["replay"],
                "pass" if "replay_stability" in result["expectedPassedChecks"] else "fail",
            )
            self.assertEqual(
                runtime["explicitAbsence"],
                "pass"
                if "explicit_absence_enables_transition" in result["expectedPassedChecks"]
                else "fail",
            )
            self.assertEqual(
                runtime["deadlineBinding"],
                "pass"
                if "deadline_bound_to_evidence" in result["expectedPassedChecks"]
                else "fail",
            )

    def test_summary_keeps_projection_and_storage_claims_separate(self) -> None:
        summary = summarize_runtime_conformance_matrix(self.matrix)
        self.assertEqual(
            summary,
            {
                "runtimeCount": 5,
                "projectionPassCount": 4,
                "projectionFailCount": 1,
                "persistencePassCount": 4,
                "appendOnlyPassCount": 0,
                "appendOnlyAdapterRequiredCount": 3,
                "appendOnlyFailCount": 1,
                "appendOnlyNotMeasuredCount": 1,
                "destructiveMutationRuntimeCount": 1,
            },
        )

    def test_openai_session_mutation_surface_is_not_hidden_by_8_of_8_projection(self) -> None:
        openai = next(
            runtime for runtime in self.matrix["runtimes"] if runtime["id"] == "openai-agents-sdk"
        )
        self.assertEqual(openai["projection"], {"status": "pass", "passed": 8, "total": 8})
        self.assertEqual(openai["appendOnly"], "fail")
        self.assertEqual(openai["destructiveMutations"]["status"], "present")
        self.assertEqual(openai["destructiveMutations"]["operations"], ["pop_item", "clear_session"])

    def test_projection_score_status_mismatch_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.matrix)
        invalid["runtimes"][0]["projection"] = {"status": "pass", "passed": 6, "total": 8}
        with self.assertRaisesRegex(ValueError, "projection status and score disagree"):
            validate_runtime_conformance_matrix(invalid)

    def test_destructive_mutations_cannot_coexist_with_append_only_pass(self) -> None:
        invalid = copy.deepcopy(self.matrix)
        openai = next(
            runtime for runtime in invalid["runtimes"] if runtime["id"] == "openai-agents-sdk"
        )
        openai["appendOnly"] = "pass"
        with self.assertRaisesRegex(ValueError, "cannot be append-only"):
            validate_runtime_conformance_matrix(invalid)


if __name__ == "__main__":
    unittest.main()
