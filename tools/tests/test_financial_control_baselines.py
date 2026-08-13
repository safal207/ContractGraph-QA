from __future__ import annotations

import unittest
from pathlib import Path

from contractgraph_qa.change_gate import load_change_gate_config
from contractgraph_qa.reachability import load_reachability_model, run_reachability_model


class FinancialControlBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Resolve repository paths and the safe/failure control pairs once."""
        cls.root = Path(__file__).resolve().parents[2]
        cls.cases = {
            "escrow-approval": (
                "escrow-approval-bypass",
                "approval-threshold-enforced",
                "release-without-required-approval",
                "bypass-approval-threshold",
                "escrow-release-requires-approval",
                "approval-threshold",
            ),
            "authority-freshness": (
                "stale-authority",
                "authority-state-fresh",
                "spend-under-stale-authority",
                "use-stale-authority-snapshot",
                "payment-authority-must-be-current",
                "authority-freshness",
            ),
            "authority-revocation": (
                "revoked-authority",
                "revocation-propagated",
                "spend-after-revocation",
                "ignore-revocation",
                "revoked-authority-cannot-spend",
                "authority-revocation",
            ),
            "idempotency-continuity": (
                "idempotency-replay",
                "idempotency-identity-stable",
                "create-second-payment-attempt",
                "change-idempotency-identity",
                "retry-must-preserve-idempotency",
                "idempotency-continuity",
            ),
            "settlement-deduplication": (
                "duplicate-settlement",
                "settlement-single-application",
                "apply-duplicate-settlement",
                "reapply-settlement-effect",
                "settlement-applied-once",
                "settlement-deduplication",
            ),
        }

    def test_safe_baselines_keep_forbidden_security_objects_but_block_the_path(self) -> None:
        """Keep security identity stable while proving the safe path is blocked."""
        for baseline_name, (
            failure_name,
            assumption_id,
            target,
            transition_id,
            invariant,
            boundary,
        ) in self.cases.items():
            with self.subTest(baseline=baseline_name):
                baseline = load_reachability_model(
                    self.root
                    / "scenarios"
                    / "financial-control-baselines"
                    / f"{baseline_name}.json"
                )
                failure = load_reachability_model(
                    self.root / "scenarios" / f"{failure_name}.json"
                )

                # The reviewed baseline preserves the same security identity as the
                # corresponding failure example. Only the declared violation state changes.
                self.assertEqual(baseline.assumptions, failure.assumptions)
                self.assertEqual(baseline.capabilities, failure.capabilities)
                self.assertEqual(baseline.transitions, failure.transitions)
                self.assertEqual(baseline.initial_capabilities, failure.initial_capabilities)
                self.assertEqual(baseline.target_capabilities, failure.target_capabilities)
                self.assertEqual(baseline.max_depth, failure.max_depth)
                self.assertEqual(baseline.violated_assumptions, ())
                self.assertEqual(failure.violated_assumptions, (assumption_id,))

                capability_by_id = {item.id: item for item in baseline.capabilities}
                self.assertTrue(capability_by_id[target].forbidden)
                self.assertEqual(baseline.transitions[0].id, transition_id)
                self.assertEqual(baseline.transitions[0].invariant_id, invariant)
                self.assertEqual(baseline.transitions[0].boundary, boundary)

                baseline_result = run_reachability_model(baseline)
                failure_result = run_reachability_model(failure)
                self.assertEqual(baseline_result["status"], "not_found_within_bound")
                self.assertIsNone(baseline_result["path"])
                self.assertEqual(failure_result["status"], "reachable")
                self.assertEqual(failure_result["path"]["targetCapability"], target)

    def test_financial_control_profile_is_strict_and_points_to_all_baselines(self) -> None:
        """Bind every profile model ID to its exact reviewed baseline path."""
        config = load_change_gate_config(self.root / "financial-control-gate.toml")
        self.assertEqual(config.schema_version, 1)
        self.assertEqual(len(config.models), 5)
        model_ids = [model.id for model in config.models]
        self.assertEqual(
            model_ids,
            [
                "authority-freshness-control",
                "authority-revocation-control",
                "escrow-approval-control",
                "idempotency-continuity-control",
                "settlement-deduplication-control",
            ],
        )
        expected_paths = {
            "authority-freshness-control": "scenarios/financial-control-baselines/authority-freshness.json",
            "authority-revocation-control": "scenarios/financial-control-baselines/authority-revocation.json",
            "escrow-approval-control": "scenarios/financial-control-baselines/escrow-approval.json",
            "idempotency-continuity-control": "scenarios/financial-control-baselines/idempotency-continuity.json",
            "settlement-deduplication-control": "scenarios/financial-control-baselines/settlement-deduplication.json",
        }
        for model in config.models:
            self.assertEqual(model.path, expected_paths[model.id])
            self.assertTrue((self.root / model.path).is_file(), model.path)


if __name__ == "__main__":
    unittest.main()
