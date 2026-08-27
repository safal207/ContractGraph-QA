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

from contractgraph_qa.evm_hydrated_cli import main  # noqa: E402

HAS_FORGE = shutil.which("forge") is not None


class EvmHydratedCliTest(unittest.TestCase):
    @unittest.skipUnless(HAS_FORGE, "forge is required for Solidity extraction")
    def test_raw_receipt_runs_full_hydrated_pipeline(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "--target",
                    "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
                    "--profile",
                    str(ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"),
                    "--receipt",
                    str(ROOT / "scenarios" / "evm-receipt-double-settlement.json"),
                    "--receipt-profile",
                    str(ROOT / "scenarios" / "evm-receipt-double-settlement-profile.json"),
                    "--bindings",
                    str(ROOT / "scenarios" / "hydration-bindings-evm-receipt-race.json"),
                    "--root",
                    str(ROOT),
                ]
            )
        self.assertNotEqual(code, 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["receiptAdapter"]["status"], "pass")
        hydrated = result["hydratedAssessment"]
        self.assertEqual(hydrated["staticLifecycle"]["status"], "fail")
        self.assertEqual(hydrated["runtimeVerification"]["economicCardinality"]["status"], "fail")
        self.assertEqual(hydrated["runtimeVerification"]["successorConsistency"]["status"], "fail")
        self.assertEqual(hydrated["staticRuntimeConformance"]["status"], "pass")
        self.assertEqual(hydrated["bindingVerification"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
