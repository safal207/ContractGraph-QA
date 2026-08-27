from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.hydrated_lattice_cli import main  # noqa: E402

HAS_FORGE = shutil.which("forge") is not None


class HydratedLatticeCliTest(unittest.TestCase):
    @unittest.skipUnless(HAS_FORGE, "forge is required for hydrated CLI integration")
    def test_one_command_surfaces_static_and_runtime_failures(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "--target",
                    "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
                    "--profile",
                    str(ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"),
                    "--trace",
                    str(ROOT / "scenarios" / "execution-trace-double-settlement-conflict.json"),
                    "--bindings",
                    str(ROOT / "scenarios" / "hydration-bindings-escrow-race.json"),
                    "--root",
                    str(ROOT),
                ]
            )
        self.assertNotEqual(code, 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["staticLifecycle"]["status"], "fail")
        self.assertEqual(result["runtimeVerification"]["economicCardinality"]["status"], "fail")
        self.assertEqual(result["runtimeVerification"]["successorConsistency"]["status"], "fail")
        self.assertEqual(result["staticRuntimeConformance"]["status"], "pass")
        self.assertEqual(result["bindingVerification"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
