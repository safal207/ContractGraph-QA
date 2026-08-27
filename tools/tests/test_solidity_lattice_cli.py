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

from contractgraph_qa.cli import EXIT_VALIDATION, main as cli_main  # noqa: E402

HAS_FORGE = shutil.which("forge") is not None


class SolidityLatticeCliTest(unittest.TestCase):
    @unittest.skipUnless(HAS_FORGE, "forge is required for compiler-AST integration")
    def test_vulnerable_target_returns_failure_evidence(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(
                [
                    "solidity-lattice-check",
                    "--target",
                    "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
                    "--profile",
                    str(ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"),
                    "--root",
                    str(ROOT),
                ]
            )
        self.assertEqual(code, EXIT_VALIDATION)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["lifecycleVerification"]["invariantId"], "CGQ-LIVE-001")
        self.assertEqual(result["latticeTemplate"]["schemaVersion"], "contract-lattice-template-v0.1")


if __name__ == "__main__":
    unittest.main()
