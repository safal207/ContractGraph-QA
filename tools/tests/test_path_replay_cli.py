from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main


class ReachabilityReplayCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.prior = cls.root / "scenarios/adversarial-adapter-fixture.json"
        cls.fixed = cls.root / "scenarios/adversarial-adapter-fixture-fixed.json"

    def _run(self, fixed: Path) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "reachability-replay",
                    "--prior-model",
                    str(self.prior),
                    "--fixed-model",
                    str(fixed),
                ]
            )
        return code, json.loads(stdout.getvalue())

    def test_fix_verified_returns_zero(self) -> None:
        code, payload = self._run(self.fixed)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["status"], "fix_verified")
        self.assertFalse(payload["alternateReachability"]["reachable"])
        self.assertEqual(
            payload["exactReplay"]["blockedAt"]["reason"],
            "assumption_guard_restored",
        )

    def test_persistent_path_returns_validation_exit(self) -> None:
        code, payload = self._run(self.prior)
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["status"], "failing_path_persists")
        self.assertTrue(payload["exactReplay"]["reachedForbiddenCapability"])


if __name__ == "__main__":
    unittest.main()
