from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_OK, main as cli_main  # noqa: E402


class Phase1OrientationIntegrationTest(unittest.TestCase):
    def test_cross_capability_fixture_is_balanced_via_public_cli(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(
                [
                    "orient",
                    "--bundle",
                    str(ROOT / "scenarios" / "orientation-cross-capability.json"),
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["readiness"], "BALANCED")
        self.assertFalse(payload["securityVerdictAuthorized"])
        self.assertEqual(
            {row["capability"] for row in payload["contributingCapabilities"]},
            {"Transition Geometry", "Ancestral Validity"},
        )


if __name__ == "__main__":
    unittest.main()
