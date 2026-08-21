from __future__ import annotations

import unittest

from contractgraph_qa.measurement_provenance import MeasurementSpec, evaluate_measurement


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


if __name__ == "__main__":
    unittest.main()
