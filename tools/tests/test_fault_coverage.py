from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.fault_coverage import (  # noqa: E402
    build_fault_coverage_matrix,
    render_fault_coverage_markdown,
)
from contractgraph_qa.fault_mutation_generator import (  # noqa: E402
    generate_fault_mutation_plan,
    generator_config_from_dict,
)
from contractgraph_qa.mutation_acquisition import (  # noqa: E402
    mutation_plan_from_dict,
    mutation_plan_sha256,
    run_mutation_acquisition,
)

SCENARIO = ROOT / "scenarios" / "escrow-auto-fault-generator.json"


def _generation() -> dict[str, object]:
    document = json.loads(SCENARIO.read_text(encoding="utf-8"))
    document["requiredFaultClasses"] = ["authorization", "time_boundary"]
    document["maxMutationsPerFaultClass"] = 1
    bindings = document["testBindings"]
    assert isinstance(bindings, list)
    document["testBindings"] = [
        item
        for item in bindings
        if isinstance(item, dict) and item.get("faultClass") in {"authorization", "time_boundary"}
    ]
    result = generate_fault_mutation_plan(generator_config_from_dict(document), ROOT)
    assert result["status"] == "pass"
    return result


def _synthetic_execution(generation: dict[str, object], outcomes: dict[str, str] | None = None) -> dict[str, object]:
    plan_raw = generation["mutationPlan"]
    assert isinstance(plan_raw, dict)
    plan = mutation_plan_from_dict(plan_raw)
    outcomes = outcomes or {}
    mutations = []
    for item in plan.mutations:
        result = outcomes.get(item.mutation_id, "detected")
        mutations.append(
            {
                "mutationId": item.mutation_id,
                "faultClass": item.fault_class,
                "specAssuranceResult": result,
                "evidenceSha256": hashlib.sha256(f"{item.mutation_id}:{result}".encode()).hexdigest(),
            }
        )
    results = {item["specAssuranceResult"] for item in mutations}
    if "survived" in results:
        spec_status = "fail"
    elif "inconclusive" in results:
        spec_status = "inconclusive"
    else:
        spec_status = "pass"
    return {
        "schemaVersion": "solidity-mutation-result-v0.1",
        "status": "pass" if "inconclusive" not in results else "inconclusive",
        "acquisitionId": plan.acquisition_id,
        "planSha256": mutation_plan_sha256(plan),
        "sourcePath": plan.source_path,
        "sourceSha256": plan.source_sha256,
        "mutations": mutations,
        "specAssurance": {"status": spec_status},
    }


class FaultCoverageMatrixTest(unittest.TestCase):
    def test_all_reviewed_mutations_detected_is_pass(self) -> None:
        generation = _generation()
        matrix = build_fault_coverage_matrix(generation, _synthetic_execution(generation))
        self.assertEqual(matrix["status"], "pass")
        self.assertEqual(matrix["classification"], "all_reviewed_mutations_detected")
        self.assertEqual(matrix["blindSpotFaultClasses"], [])
        self.assertEqual(matrix["inconclusiveFaultClasses"], [])
        self.assertEqual(matrix["totals"]["reviewedKillRate"], 1.0)
        rows = {item["faultClass"]: item for item in matrix["matrix"]}
        self.assertEqual(rows["authorization"]["status"], "covered_over_reviewed_mutations")
        self.assertEqual(rows["time_boundary"]["killRate"], 1.0)

    def test_surviving_mutation_is_explicit_blind_spot(self) -> None:
        generation = _generation()
        plan = generation["mutationPlan"]
        assert isinstance(plan, dict)
        target = plan["mutations"][0]["mutationId"]
        execution = _synthetic_execution(generation, {target: "survived"})
        matrix = build_fault_coverage_matrix(generation, execution)
        self.assertEqual(matrix["status"], "fail")
        self.assertEqual(matrix["classification"], "blind_spots_present")
        self.assertEqual(len(matrix["blindSpotFaultClasses"]), 1)
        blind = [item for item in matrix["matrix"] if item["status"] == "blind_spot"]
        self.assertEqual(blind[0]["survivedCount"], 1)
        self.assertEqual(blind[0]["killRate"], 0.0)

    def test_inconclusive_execution_suppresses_kill_rate(self) -> None:
        generation = _generation()
        plan = generation["mutationPlan"]
        assert isinstance(plan, dict)
        target = plan["mutations"][0]["mutationId"]
        execution = _synthetic_execution(generation, {target: "inconclusive"})
        matrix = build_fault_coverage_matrix(generation, execution)
        self.assertEqual(matrix["status"], "inconclusive")
        row = next(item for item in matrix["matrix"] if item["inconclusiveCount"] == 1)
        self.assertIsNone(row["killRate"])
        self.assertIsNone(matrix["totals"]["reviewedKillRate"])
        markdown = render_fault_coverage_markdown(matrix)
        self.assertIn("| — |", markdown)

    def test_execution_from_different_plan_is_rejected(self) -> None:
        generation = _generation()
        execution = _synthetic_execution(generation)
        execution["planSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "mutation-plan SHA-256 differ"):
            build_fault_coverage_matrix(generation, execution)

    def test_matrix_is_deterministic(self) -> None:
        generation = _generation()
        execution = _synthetic_execution(generation)
        first = build_fault_coverage_matrix(copy.deepcopy(generation), copy.deepcopy(execution))
        second = build_fault_coverage_matrix(copy.deepcopy(generation), copy.deepcopy(execution))
        self.assertEqual(first, second)
        self.assertEqual(len(first["matrixSha256"]), 64)

    @unittest.skipUnless(shutil.which("forge"), "Forge is required for fault coverage integration")
    def test_generated_foundry_evidence_projects_to_green_matrix(self) -> None:
        generation = _generation()
        plan_raw = generation["mutationPlan"]
        assert isinstance(plan_raw, dict)
        execution = run_mutation_acquisition(mutation_plan_from_dict(plan_raw), ROOT)
        matrix = build_fault_coverage_matrix(generation, execution)
        self.assertEqual(matrix["status"], "pass")
        self.assertEqual(matrix["coveredFaultClasses"], ["authorization", "time_boundary"])
        self.assertEqual(matrix["totals"]["generatedMutationCount"], 2)
        self.assertEqual(matrix["totals"]["detectedCount"], 2)


if __name__ == "__main__":
    unittest.main()
