import importlib.util
import io
import unittest
from pathlib import Path
from urllib import parse

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("bounded_runner", HERE / "bounded_runner_template.py")
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class BoundedRunnerTests(unittest.TestCase):
    def test_path_prefix_confusion_is_rejected(self):
        with self.assertRaises(RuntimeError):
            runner.guard("/action-evil")
        runner.guard("/action")
        runner.guard("/action/child")

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(RuntimeError):
            runner.guard("/../action")

    def test_cross_origin_redirect_target_is_rejected(self):
        parts = parse.urlsplit("https://attacker.invalid/api/action")
        with self.assertRaisesRegex(RuntimeError, "origin"):
            runner._relative_scoped_segments(parts)

    def test_response_read_is_bounded(self):
        oversized = io.BytesIO(b"x" * (runner.MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "response_exceeds"):
            runner._bounded_read(oversized)

    def test_invalid_json_is_explicit_error(self):
        data, parse_error = runner._decode_json(b"{not-json")
        self.assertIsNone(data)
        self.assertEqual(parse_error["kind"], "invalid_json")

    def test_failed_preflight_blocks_mutations_but_collects_tail(self):
        original_call = runner.call
        calls = []

        def fake_call(method, path, payload=None, execute=False, start_barrier=None):
            calls.append((method, path))
            if path == "/audit" and len(calls) == 1:
                return {"complete": False, "transport_error": "URLError"}
            return {"complete": True, "status": 200, "data": {}}

        runner.call = fake_call
        try:
            result = runner.run_boundary_race(
                execute=True,
                boundary_limit=100,
                remaining_budget=40,
                action_amount=30,
            )
        finally:
            runner.call = original_call

        self.assertFalse(result["complete"])
        self.assertEqual(result["race"], [])
        self.assertEqual(result["precondition"]["reason"], "unreadable_or_failed_audit_preflight")
        self.assertNotIn(("POST", "/action"), calls)
        self.assertIn(("GET", "/transactions"), calls)

    def test_unproven_boundary_blocks_mutations(self):
        original_call = runner.call
        calls = []

        def fake_call(method, path, payload=None, execute=False, start_barrier=None):
            calls.append((method, path))
            return {"complete": True, "status": 200, "data": {}}

        runner.call = fake_call
        try:
            result = runner.run_boundary_race(
                execute=True,
                boundary_limit=100,
                remaining_budget=80,
                action_amount=30,
            )
        finally:
            runner.call = original_call

        self.assertFalse(result["complete"])
        self.assertEqual(result["race"], [])
        self.assertEqual(result["precondition"]["status"], "blocked")
        self.assertNotIn(("POST", "/action"), calls)

    def test_dry_run_remains_network_free(self):
        result = runner.run_boundary_race(execute=False)
        self.assertTrue(all(item["dry_run"] for item in result["race"]))
        self.assertEqual(result["precondition"]["status"], "not_evaluated_dry_run")


if __name__ == "__main__":
    unittest.main()
