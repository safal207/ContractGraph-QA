from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contractgraph_qa import cli
from contractgraph_qa import project_quickstart_cli
from contractgraph_qa.project_quickstart_hardened import (
    ProjectQuickstartError,
    _read_bytes,
    _run_command,
    _safe_environment,
    inspect_project,
    write_quickstart,
)


class QuickstartHardeningTest(unittest.TestCase):
    def _foundry(self, root: Path) -> None:
        (root / "foundry.toml").write_text(
            '[profile.default]\nsrc = "src"\nsolc_version = "0.8.24"\n',
            encoding="utf-8",
        )
        (root / "src").mkdir(parents=True)
        (root / "src" / "Vault.sol").write_text(
            "pragma solidity ^0.8.24; contract Vault { uint256 public value; }\n",
            encoding="utf-8",
        )

    def test_configuration_change_changes_exact_project_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            first = inspect_project(root)
            (root / "foundry.toml").write_text(
                '[profile.default]\nsrc = "src"\nsolc_version = "0.8.25"\n',
                encoding="utf-8",
            )
            second = inspect_project(root)
            self.assertEqual(
                first["subject"]["sourceFingerprint"],
                second["subject"]["sourceFingerprint"],
            )
            self.assertNotEqual(
                first["subject"]["configurationFingerprint"],
                second["subject"]["configurationFingerprint"],
            )
            self.assertNotEqual(
                first["subject"]["projectFingerprint"],
                second["subject"]["projectFingerprint"],
            )

    def test_run_native_without_detected_runner_is_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            with mock.patch(
                "contractgraph_qa.project_quickstart_hardened._tool_path",
                return_value=None,
            ):
                result = inspect_project(root, run_native=True)
            self.assertEqual(result["status"], "hold")
            self.assertEqual(result["readiness"], "BLOCKED_NATIVE_TOOL_MISSING")
            self.assertEqual(result["nativeResult"]["status"], "not_available")

    def test_native_source_mutation_stales_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)

            def mutate(*_args, **_kwargs):
                (root / "src" / "Vault.sol").write_text(
                    "pragma solidity ^0.8.24; contract Vault { uint256 public changed; }\n",
                    encoding="utf-8",
                )
                return {
                    "requested": True,
                    "status": "pass",
                    "returnCode": 0,
                    "durationSeconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                    "environmentPolicy": "SANITIZED",
                    "inheritedEnvironmentNames": ["PATH"],
                    "strippedSensitiveEnvironmentNames": [],
                }

            with mock.patch(
                "contractgraph_qa.project_quickstart_hardened._native_plan",
                return_value={
                    "framework": "foundry",
                    "projectRoot": ".",
                    "requiredTool": "forge",
                    "available": True,
                    "command": ["forge", "test"],
                    "executionPolicy": "NOT_RUN_BY_DEFAULT",
                },
            ), mock.patch(
                "contractgraph_qa.project_quickstart_hardened._run_command",
                side_effect=mutate,
            ):
                result = inspect_project(root, run_native=True)
            self.assertEqual(result["status"], "hold")
            self.assertEqual(result["readiness"], "STALE_SUBJECT_AFTER_NATIVE_TESTS")
            self.assertTrue(result["postNativeSubject"]["changed"])
            self.assertTrue(result["postNativeSubject"]["fingerprintChanged"])

    def test_native_environment_is_secret_safe_by_default(self) -> None:
        values = {
            "PATH": "/bin",
            "HOME": "/home/test",
            "PRIVATE_KEY": "do-not-pass",
            "RPC_URL": "https://secret.example",
            "SERVICE_TOKEN": "token",
        }
        with mock.patch.dict(os.environ, values, clear=True):
            safe, inherited, stripped = _safe_environment(inherit_environment=False)
            self.assertEqual(safe["PATH"], "/bin")
            self.assertNotIn("PRIVATE_KEY", safe)
            self.assertNotIn("RPC_URL", safe)
            self.assertNotIn("SERVICE_TOKEN", safe)
            self.assertIn("PRIVATE_KEY", stripped)
            full, full_names, _ = _safe_environment(inherit_environment=True)
            self.assertEqual(full["PRIVATE_KEY"], "do-not-pass")
            self.assertIn("PRIVATE_KEY", full_names)
            self.assertIn("PATH", inherited)

    def test_failed_force_refresh_preserves_previous_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            output = root / ".cgqa" / "quickstart"
            write_quickstart(root, output_directory=output)
            original = (output / "quickstart.json").read_bytes()
            (output / "sentinel.txt").write_text("preserve", encoding="utf-8")
            with mock.patch(
                "contractgraph_qa.project_quickstart_hardened.inspect_project",
                side_effect=ProjectQuickstartError("synthetic failure"),
            ):
                with self.assertRaises(ProjectQuickstartError):
                    write_quickstart(root, output_directory=output, force=True)
            self.assertEqual((output / "quickstart.json").read_bytes(), original)
            self.assertEqual((output / "sentinel.txt").read_text(encoding="utf-8"), "preserve")

    def test_nested_foundry_workspace_is_primary_and_its_lib_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "packages" / "payments"
            (nested / "src").mkdir(parents=True)
            (nested / "lib").mkdir()
            (nested / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
            (nested / "src" / "Vault.sol").write_text("contract Vault {}\n", encoding="utf-8")
            (nested / "lib" / "Dependency.sol").write_text(
                "contract Dependency {}\n",
                encoding="utf-8",
            )
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "foundry")
            self.assertEqual(result["primary"]["projectRoot"], "packages/payments")
            self.assertEqual(
                [row["path"] for row in result["sourceFiles"]],
                ["packages/payments/src/Vault.sol"],
            )

    def test_cargo_description_does_not_fake_soroban_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "lib.rs").write_text("pub struct Plain;\n", encoding="utf-8")
            (root / "Cargo.toml").write_text(
                '[package]\nname="plain"\nversion="0.1.0"\ndescription="mentions soroban-sdk only"\n',
                encoding="utf-8",
            )
            result = inspect_project(root)
            frameworks = {row["framework"] for row in result["detections"]}
            self.assertNotIn("soroban", frameworks)

    def test_near_contract_attributes_are_reported_as_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "lib.rs").write_text(
                "#[near_bindgen]\npub struct Legacy;\n"
                "#[near(contract_state)]\npub struct Modern;\n",
                encoding="utf-8",
            )
            (root / "Cargo.toml").write_text(
                '[package]\nname="near-contract"\nversion="0.1.0"\n'
                '[dependencies]\nnear-sdk="5"\n',
                encoding="utf-8",
            )

            result = inspect_project(root)

            self.assertEqual(result["primary"]["framework"], "near")
            self.assertEqual(
                {
                    (row["kind"], row["name"])
                    for row in result["declarations"]
                },
                {("near contract", "Legacy"), ("near contract", "Modern")},
            )

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_untracked_build_output_does_not_stale_native_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            subprocess.run(
                ["git", "init", "-q", "-b", "main"],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=CGQA Test",
                    "-c",
                    "user.email=cgqa@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "fixture",
                ],
                cwd=root,
                check=True,
            )

            def create_build_output(*_args, **_kwargs):
                (root / "out").mkdir()
                (root / "out" / "Vault.json").write_text("{}\n", encoding="utf-8")
                return {
                    "requested": True,
                    "status": "pass",
                    "returnCode": 0,
                    "durationSeconds": 0.01,
                    "stdout": "",
                    "stderr": "",
                    "environmentPolicy": "SANITIZED_ISOLATED_HOME",
                    "inheritedEnvironmentNames": ["PATH"],
                    "strippedSensitiveEnvironmentNames": [],
                }

            with mock.patch(
                "contractgraph_qa.project_quickstart_hardened._native_plan",
                return_value={
                    "framework": "foundry",
                    "projectRoot": ".",
                    "requiredTool": "forge",
                    "available": True,
                    "command": ["forge", "test"],
                    "executionPolicy": "NOT_RUN_BY_DEFAULT",
                },
            ), mock.patch(
                "contractgraph_qa.project_quickstart_hardened._run_command",
                side_effect=create_build_output,
            ):
                result = inspect_project(root, run_native=True)

            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["postNativeSubject"]["changed"])
            self.assertTrue((root / "out" / "Vault.json").is_file())

    def test_windows_timeout_kills_process_tree_with_bounded_drain(self) -> None:
        process = mock.Mock()
        process.pid = 4242
        process.returncode = None
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(
                cmd=["npm", "test"],
                timeout=1,
                output=b"partial-out",
                stderr=b"partial-err",
            ),
            (b"-tail", b"-tail"),
        ]

        with mock.patch(
            "contractgraph_qa.project_quickstart_hardened.os.name",
            "nt",
        ), mock.patch(
            "contractgraph_qa.project_quickstart_hardened.tempfile.mkdtemp",
            return_value="C:\\cgqa-home",
        ), mock.patch(
            "contractgraph_qa.project_quickstart_hardened.subprocess.Popen",
            return_value=process,
        ) as popen, mock.patch(
            "contractgraph_qa.project_quickstart_hardened.subprocess.run",
        ) as run, mock.patch(
            "contractgraph_qa.project_quickstart_hardened.shutil.rmtree",
        ) as rmtree:
            result = _run_command(
                Path("."),
                {"command": ["npm", "test"]},
                1,
                inherit_environment=False,
            )

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["stdout"], "partial-out-tail")
        self.assertEqual(result["stderr"], "partial-err-tail")
        popen.assert_called_once()
        run.assert_called_once_with(
            ["taskkill", "/PID", "4242", "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        process.communicate.assert_has_calls(
            [mock.call(timeout=1), mock.call(timeout=10)]
        )
        rmtree.assert_called_once_with("C:\\cgqa-home", ignore_errors=True)

    def test_fuel_sway_project_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "Forc.toml").write_text(
                '[project]\nauthors = ["CGQA"]\nentry = "main.sw"\nlicense = "Apache-2.0"\nname = "vault"\n',
                encoding="utf-8",
            )
            (root / "src" / "main.sw").write_text("contract;\n", encoding="utf-8")
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "fuel")
            self.assertEqual(result["primary"]["ecosystem"], "fuel")

    def test_unreadable_source_makes_inventory_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            bad = root / "src" / "Bad.sol"
            bad.write_text("contract Bad {}\n", encoding="utf-8")

            def read(path: Path) -> bytes:
                if path.name == "Bad.sol":
                    raise OSError("synthetic unreadable source")
                return _read_bytes(path)

            with mock.patch(
                "contractgraph_qa.project_quickstart_hardened._read_bytes",
                side_effect=read,
            ):
                result = inspect_project(root)
            self.assertEqual(result["status"], "hold")
            self.assertEqual(result["readiness"], "INCOMPLETE_PROJECT_INVENTORY")
            self.assertIn(
                "src/Bad.sol",
                {row["path"] for row in result["skippedOversizedOrUnreadable"]},
            )

    def test_explicit_root_project_beats_nested_project_of_another_framework(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contracts").mkdir()
            (root / "contracts" / "Root.sol").write_text("contract Root {}\n", encoding="utf-8")
            (root / "hardhat.config.js").write_text("module.exports = {};\n", encoding="utf-8")
            nested = root / "packages" / "nested"
            (nested / "src").mkdir(parents=True)
            (nested / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
            (nested / "src" / "Nested.sol").write_text("contract Nested {}\n", encoding="utf-8")
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "hardhat")
            self.assertEqual(result["primary"]["projectRoot"], ".")

    def test_renamed_cargo_dependency_is_detected_by_package_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "lib.rs").write_text(
                "#[contract]\npub struct AliasContract;\n",
                encoding="utf-8",
            )
            (root / "Cargo.toml").write_text(
                '[package]\nname="alias-contract"\nversion="0.1.0"\n'
                '[dependencies]\nstellar = { package = "soroban-sdk", version = "22" }\n',
                encoding="utf-8",
            )
            result = inspect_project(root)
            self.assertEqual(result["primary"]["framework"], "soroban")

    def test_native_harness_change_updates_configuration_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._foundry(root)
            (root / "test").mkdir()
            harness = root / "test" / "integration.js"
            harness.write_text("module.exports = 1;\n", encoding="utf-8")
            first = inspect_project(root)
            harness.write_text("module.exports = 2;\n", encoding="utf-8")
            second = inspect_project(root)
            self.assertEqual(
                first["subject"]["sourceFingerprint"],
                second["subject"]["sourceFingerprint"],
            )
            self.assertNotEqual(
                first["subject"]["configurationFingerprint"],
                second["subject"]["configurationFingerprint"],
            )

    def test_quickstart_parser_error_uses_public_validation_exit(self) -> None:
        self.assertEqual(project_quickstart_cli.main(["--unknown"]), cli.EXIT_VALIDATION)

    def test_phase2_parser_error_is_normalized_by_main_cli(self) -> None:
        self.assertEqual(cli.main(["witness"]), cli.EXIT_VALIDATION)


if __name__ == "__main__":
    unittest.main()
