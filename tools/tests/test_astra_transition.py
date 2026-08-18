import unittest

from contractgraph_qa.astra_transition import (
    AstraTransitionError,
    analyze_transition_path,
    transition_pressure,
)


class AstraTransitionTests(unittest.TestCase):
    def test_transition_pressure_is_multiplicative(self):
        score = transition_pressure(
            {
                "stimulus": 1.0,
                "state_complexity": 0.5,
                "future_pressure": 1.0,
                "witness_gap": 0.5,
                "divergence": 1.0,
            }
        )
        self.assertEqual(score, 25.0)

    def test_failure_gradient_detects_acceleration_and_crystallization(self):
        result = analyze_transition_path(
            {
                "material_acceleration": 5.0,
                "transitions": [
                    {
                        "id": "request",
                        "stimulus": 0.7,
                        "state_complexity": 0.7,
                        "future_pressure": 0.7,
                        "witness_gap": 0.7,
                        "divergence": 0.7,
                    },
                    {
                        "id": "ambiguous-timeout",
                        "stimulus": 0.9,
                        "state_complexity": 0.9,
                        "future_pressure": 0.9,
                        "witness_gap": 0.9,
                        "divergence": 0.9,
                    },
                    {
                        "id": "duplicate-settlement",
                        "stimulus": 1.0,
                        "state_complexity": 1.0,
                        "future_pressure": 1.0,
                        "witness_gap": 1.0,
                        "divergence": 1.0,
                    },
                ],
            }
        )
        gradient = result["failure_gradient"]
        self.assertEqual(gradient["first_material_acceleration"], "ambiguous-timeout")
        self.assertEqual(gradient["crystallization_transition"], "duplicate-settlement")
        self.assertEqual(result["verdict"], "TARGET_CANDIDATE")
        self.assertTrue(result["baseline_preserved"])

    def test_verifier_reflection_blocks_target_claim(self):
        result = analyze_transition_path(
            {
                "transitions": [
                    {
                        "id": "protocol-wait",
                        "stimulus": 1.0,
                        "state_complexity": 1.0,
                        "future_pressure": 1.0,
                        "witness_gap": 1.0,
                        "divergence": 1.0,
                    }
                ],
                "verifier_reflection": {"wrong_clock_model": True},
            }
        )
        self.assertEqual(result["verdict"], "VERIFIER_FAIL")
        self.assertEqual(
            result["verifier_reflection"]["unresolved"], ["wrong_clock_model"]
        )

    def test_no_crystallization_is_not_promoted_to_failure(self):
        result = analyze_transition_path(
            {
                "transitions": [
                    {
                        "id": "bounded-clean",
                        "stimulus": 0.5,
                        "state_complexity": 0.5,
                        "future_pressure": 0.5,
                        "witness_gap": 0.5,
                        "divergence": 0.5,
                    }
                ]
            }
        )
        self.assertEqual(result["verdict"], "NO_CRYSTALLIZED_FAILURE")

    def test_invalid_component_fails_closed(self):
        with self.assertRaises(AstraTransitionError):
            transition_pressure(
                {
                    "stimulus": 1.2,
                    "state_complexity": 0.5,
                    "future_pressure": 0.5,
                    "witness_gap": 0.5,
                    "divergence": 0.5,
                }
            )


if __name__ == "__main__":
    unittest.main()
