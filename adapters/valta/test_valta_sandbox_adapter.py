import json
import os
import unittest
from pathlib import Path

from valta_sandbox_adapter import ValtaAdapterNotReady, ValtaSandboxAdapter


HERE = Path(__file__).resolve().parent


class ValtaSandboxAdapterTests(unittest.TestCase):
    def test_manifest_contains_no_literal_api_key(self):
        text = (HERE / "adapter_manifest.valta.sandbox.json").read_text(encoding="utf-8")
        self.assertNotIn("sk_valta_", text)
        self.assertIn("VALTA_TEST_API_KEY", text)

    def test_endpoint_map_keeps_live_execution_disabled(self):
        config = json.loads((HERE / "endpoint_map.valta.sandbox.json").read_text(encoding="utf-8"))
        self.assertFalse(config["execution_gate"]["live_execution_enabled"])
        self.assertFalse(config["execution_gate"]["spend_payload_confirmed"])

    def test_known_setup_request_shapes_are_deterministic(self):
        adapter = ValtaSandboxAdapter()
        fund = adapter.plan_fund(amount=100, idempotency_key="test-1")
        self.assertEqual(fund["method"], "POST")
        self.assertTrue(fund["url"].endswith("/sandbox/deposit"))
        self.assertEqual(fund["json"]["agent"], "wallet-guardian")
        self.assertEqual(fund["json"]["idempotencyKey"], "test-1")

        policy = adapter.plan_policy(daily_limit=60, max_per_transaction=40)
        self.assertTrue(policy["url"].endswith("/policies"))
        self.assertEqual(policy["json"]["dailyLimit"], 60)
        self.assertEqual(policy["json"]["maxPerTransaction"], 40)

    def test_request_plan_never_contains_real_api_key(self):
        os.environ["VALTA_TEST_API_KEY"] = "sentinel-do-not-render"
        try:
            plan = ValtaSandboxAdapter().plan_audit()
            rendered = json.dumps(plan)
            self.assertNotIn("sentinel-do-not-render", rendered)
            self.assertIn("<from VALTA_TEST_API_KEY>", rendered)
        finally:
            os.environ.pop("VALTA_TEST_API_KEY", None)

    def test_spend_is_fail_closed_until_body_is_confirmed(self):
        adapter = ValtaSandboxAdapter()
        with self.assertRaises(ValtaAdapterNotReady):
            adapter.plan_spend(event="action_valid", amount=20)

    def test_live_mode_is_refused_by_execution_gate(self):
        with self.assertRaises(ValtaAdapterNotReady):
            ValtaSandboxAdapter(live=True)

    def test_old_transfer_is_marked_environment_constraint(self):
        config = json.loads((HERE / "endpoint_map.valta.sandbox.json").read_text(encoding="utf-8"))
        transfer = config["environment_constraints"]["unsupported_transfer_endpoint"]
        self.assertEqual(transfer["expected_test_key_behavior"], 403)
        self.assertFalse(transfer["finding_eligible"])


if __name__ == "__main__":
    unittest.main()
