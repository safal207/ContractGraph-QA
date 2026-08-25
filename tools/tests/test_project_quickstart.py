from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa import cli  # noqa: E402
from contractgraph_qa.project_quickstart import (  # noqa: E402
    ProjectQuickstartError,
    inspect_project,
    write_quickstart,
)


SOLIDITY_SOURCE = """
// tx.origin in a comment must not be reported.
pragma solidity ^0.8.24;

contract Vault {
    string private constant NOTE = "delegatecall in a string is not code";

    function deadline() external view returns (uint256) {
        return block.timestamp;
    }

    function raw(address target, bytes calldata data) external returns (bool) {
        (bool ok,) = target.call(data);
        return ok;
    }
}

interface IVault {
    function deadline() external view returns (uint256);
}
"""


class ProjectQuickstartTest(unittest.TestCase):
    def _foundry_project(self, root: Path) -> None:
        (root / "foundry.toml").write_text("[profile.default]\nsrc = 'src'\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "Vault.sol").write_text(SOLIDITY_SOURCE, encoding="utf-8")
        (root / "lib").mkdir()
        (root / "lib" / "Excluded.sol").write_text(
            "contract Excluded { function x() external { selfdestruct(payable(msg.sender)); } }",
            encoding="utf-8",
        )
        (root / "node_modules").mkdir()
        (root / "node_modules" / "Ignored.sol").write_text(
            "contract Ignored {}",
            encoding="utf-8",
        )

    def test_foundry_inventory_and_review_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry_project(root)
            with mock.patch(
                "contractgraph_qa.project_quickstart._tool_path",
                side_effect=lambda _root, name: "/usr/bin/forge" if name == "forge" else None,
            ):
                result = inspect_project(root)

            self.assertEqual(result["primary"]["framework"], "foundry")
            self.assertEqual(result["languages"], ["solidity"])
            self.assertEqual(
                {(row["kind"], row["name"]) for row in result["declarations"]},
                {("contract", "Vault"), ("interface", "IVault")},
            )
            self.assertEqual([row["path"] for row in result["sourceFiles"]], ["src/Vault.sol"])
            signal_ids = {row["id"] for row in result["reviewSignals"]}
            self.assertIn("TIMESTAMP_DEPENDENCE", signal_ids)
            self.assertIn("LOW_LEVEL_CALL", signal_ids)
            self.assertNotIn("TX_ORIGIN", signal_ids)
            self.assertNotIn("DELEGATECALL", signal_ids)
            self.assertNotIn("SELFDESTRUCT", signal_ids)
            self.assertEqual(result["readiness"], "READY_FOR_NATIVE_AND_CGQA_REVIEW")
            self.assertFalse(result["securityVerdictAuthorized"])

    def test_hardhat_detection_from_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contracts").mkdir()
            (root / "contracts" / "Token.sol").write_text(
                "pragma solidity ^0.8.20; contract Token {}",
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                json.dumps({"devDependencies": {"hardhat": "3.0.0"}}),
                encoding="utf-8",
            )
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "hardhat")
            self.assertEqual(result["nativePlan"]["requiredTool"], "local hardhat")
            self.assertEqual(result["nativeResult"]["status"], "not_requested")

    def test_soroban_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                '[package]\nname="demo"\n[dependencies]\nsoroban-sdk="22"\n',
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "lib.rs").write_text(
                "#[contract]\npub struct PaymentContract;\n",
                encoding="utf-8",
            )
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "soroban")
            self.assertEqual(result["primary"]["ecosystem"], "stellar")
            self.assertEqual(result["declarations"][0]["name"], "PaymentContract")

    def test_native_execution_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry_project(root)
            with mock.patch(
                "contractgraph_qa.project_quickstart._native_plan",
                return_value={
                    "framework": "foundry",
                    "requiredTool": "forge",
                    "available": True,
                    "command": ["forge", "test"],
                    "executionPolicy": "NOT_RUN_BY_DEFAULT",
                },
            ), mock.patch(
                "contractgraph_qa.project_quickstart._run_native"
            ) as run_native:
                result = inspect_project(root, run_native=False)
                run_native.assert_not_called()
                self.assertEqual(result["nativeResult"]["status"], "not_requested")

    def test_native_failure_is_visible_not_silently_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry_project(root)
            with mock.patch(
                "contractgraph_qa.project_quickstart._native_plan",
                return_value={
                    "framework": "foundry",
                    "requiredTool": "forge",
                    "available": True,
                    "command": ["forge", "test"],
                    "executionPolicy": "NOT_RUN_BY_DEFAULT",
                },
            ), mock.patch(
                "contractgraph_qa.project_quickstart._run_native",
                return_value={
                    "requested": True,
                    "status": "fail",
                    "returnCode": 1,
                    "durationSeconds": 0.2,
                    "stdout": "",
                    "stderr": "failing test",
                },
            ):
                result = inspect_project(root, run_native=True)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["readiness"], "NATIVE_TESTS_FAILED")

    def test_output_nested_under_source_does_not_hide_source_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry_project(root)
            output = root / "src" / ".review-output"
            result = write_quickstart(root, output_directory=output)
            self.assertEqual(result["sourceFiles"], 1)
            payload = json.loads((output / "quickstart.json").read_text(encoding="utf-8"))
            self.assertEqual([row["path"] for row in payload["sourceFiles"]], ["src/Vault.sol"])

    def test_write_quickstart_is_deterministic_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry_project(root)
            output = root / "analysis"
            first = write_quickstart(root, output_directory=output)
            payload = json.loads((output / "quickstart.json").read_text(encoding="utf-8"))
            self.assertEqual(first["projectFingerprint"], payload["subject"]["projectFingerprint"])
            self.assertTrue(first["ok"])
            self.assertTrue((output / "REPORT.md").is_file())
            with self.assertRaises(ProjectQuickstartError):
                write_quickstart(root, output_directory=output)
            second = write_quickstart(root, output_directory=output, force=True)
            self.assertEqual(first["projectFingerprint"], second["projectFingerprint"])

    def test_no_contract_sources_is_bounded_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = inspect_project(root)
            self.assertEqual(result["status"], "hold")
            self.assertEqual(result["readiness"], "BLOCKED_NO_CONTRACT_SOURCES")
            written = write_quickstart(root)
            self.assertFalse(written["ok"])
            self.assertEqual(written["status"], "hold")


class UnifiedCliTest(unittest.TestCase):
    def test_unified_help_lists_new_front_door_and_vnext(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["--help"])
        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("quickstart", output)
        self.assertIn("subject-freeze", output)
        self.assertIn("plan-verification", output)

    def test_quickstart_routes_through_main_cgqa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "A.sol").write_text("contract A {}", encoding="utf-8")
            output = root / "out-report"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(
                    [
                        "quickstart",
                        "--target",
                        str(root),
                        "--output-dir",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["framework"], "standalone-solidity")
            self.assertTrue((output / "quickstart.json").is_file())

    def test_quickstart_hold_returns_public_validation_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "report"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(
                    [
                        "quickstart",
                        "--target",
                        str(root),
                        "--output-dir",
                        str(output),
                    ]
                )
            self.assertEqual(code, cli.EXIT_VALIDATION)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "hold")
            self.assertFalse(result["ok"])

    def test_phase2_exit_code_is_normalized(self) -> None:
        with mock.patch.object(cli.causal_temporal_cli, "main", return_value=2) as subcli:
            code = cli.main(["witness", "--input", "evidence.json"])
        self.assertEqual(code, cli.EXIT_VALIDATION)
        subcli.assert_called_once_with(["witness", "--input", "evidence.json"])

    def test_proof_alias_is_routed(self) -> None:
        with mock.patch.object(cli.proof_integrity_cli, "main", return_value=0) as subcli:
            code = cli.main(["subject-freeze", "--input", "freeze.json"])
        self.assertEqual(code, 0)
        subcli.assert_called_once_with(["freeze", "--input", "freeze.json"])

    def test_active_planner_alias_is_routed(self) -> None:
        with mock.patch.object(cli.active_verification_cli, "main", return_value=0) as subcli:
            code = cli.main(["plan-verification", "--input", "campaign.json"])
        self.assertEqual(code, 0)
        subcli.assert_called_once_with(["plan", "--input", "campaign.json"])


if __name__ == "__main__":
    unittest.main()
