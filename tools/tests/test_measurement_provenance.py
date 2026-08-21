from __future__ import annotations

import copy
import unittest

from contractgraph_qa.measurement_provenance import (
    MeasurementProvenanceError,
    MeasurementSpec,
    build_change_gate_model_coverage_input,
    evaluate_measurement,
    run_measurement_provenance_gate,
    verify_measurement_provenance_result,
)


class MeasurementProvenanceGateTests(unittest.TestCase):
    def test_passes_when_epoch_and_required_coverage_match(self) -> None:
        result = evaluate_measurement(
            MeasurementSpec(
                id="route-coverage",
                schema_epoch=2,
                required_schema_epoch=2,
                coverage_scope="tool_call_route",
                observed_units=100,
                eligible_units=100,
                required_coverage=1.0,
                measurement_available=True,
            )
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["gateReasons"], [])
        self.assertEqual(result["coverageFraction"], 1.0)

    def test_blocks_epoch_mismatch(self) -> None:
        result = evaluate_measurement(
            MeasurementSpec(
                id="epoch-probe",
                schema_epoch=1,
                required_schema_epoch=2,
                coverage_scope="scanner_records",
                observed_units=25,
                eligible_units=25,
                required_coverage=1.0,
                measurement_available=True,
            )
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("EPOCH_MISMATCH", result["gateReasons"])

    def test_blocks_partial_coverage_against_declared_requirement(self) -> None:
        result = evaluate_measurement(
            MeasurementSpec(
                id="partial-route-coverage",
                schema_epoch=3,
                required_schema_epoch=3,
                coverage_scope="tool_call_route",
                observed_units=334,
                eligible_units=1000,
                required_coverage=0.95,
                measurement_available=True,
            )
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["gateReasons"], ["PARTIAL_COVERAGE"])
        self.assertAlmostEqual(result["coverageFraction"], 0.334)

    def test_unmeasured_stays_unknown_instead_of_false(self) -> None:
        result = evaluate_measurement(
            MeasurementSpec(
                id="missing-instrument",
                schema_epoch=4,
                required_schema_epoch=4,
                coverage_scope="source_observation",
                observed_units=None,
                eligible_units=None,
                required_coverage=1.0,
                measurement_available=False,
            )
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["gateReasons"], ["UNMEASURED"])
        self.assertIsNone(result["observedUnits"])
        self.assertIsNone(result["eligibleUnits"])
        self.assertIsNone(result["coverageFraction"])

    def test_change_gate_coverage_denominator_comes_from_base_head_configs(self) -> None:
        gate_result = {
            "schemaVersion": 1,
            "models": [{"id": "adapter"}],
        }
        payload = build_change_gate_model_coverage_input(
            gate_result,
            base_model_ids=("adapter",),
            head_model_ids=("adapter", "new-model"),
        )
        measurement = payload["measurements"][0]
        self.assertEqual(measurement["observedUnits"], 1)
        self.assertEqual(measurement["eligibleUnits"], 2)
        result = evaluate_measurement(
            MeasurementSpec(
                id=measurement["id"],
                schema_epoch=measurement["schemaEpoch"],
                required_schema_epoch=measurement["requiredSchemaEpoch"],
                coverage_scope=measurement["coverageScope"],
                observed_units=measurement["observedUnits"],
                eligible_units=measurement["eligibleUnits"],
                required_coverage=measurement["requiredCoverage"],
                measurement_available=measurement["measurementAvailable"],
            )
        )
        self.assertEqual(result["gateReasons"], ["PARTIAL_COVERAGE"])

    def test_change_gate_coverage_rejects_unconfigured_result_ids(self) -> None:
        with self.assertRaisesRegex(MeasurementProvenanceError, "outside the base/head"):
            build_change_gate_model_coverage_input(
                {"schemaVersion": 1, "models": [{"id": "ghost"}]},
                base_model_ids=("adapter",),
                head_model_ids=("adapter",),
            )

    def test_result_verifier_recomputes_status_and_rejects_tampering(self) -> None:
        result = run_measurement_provenance_gate(
            (
                MeasurementSpec(
                    id="complete",
                    schema_epoch=1,
                    required_schema_epoch=1,
                    coverage_scope="change_gate_base_head_configured_model_results",
                    observed_units=2,
                    eligible_units=2,
                    required_coverage=1.0,
                    measurement_available=True,
                ),
            )
        )
        verify_measurement_provenance_result(result)
        tampered = copy.deepcopy(result)
        tampered["measurements"][0]["status"] = "blocked"
        with self.assertRaisesRegex(
            MeasurementProvenanceError, "recomputed provenance verdict"
        ):
            verify_measurement_provenance_result(tampered)


if __name__ == "__main__":
    unittest.main()
