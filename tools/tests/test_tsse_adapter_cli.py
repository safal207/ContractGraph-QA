from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main as unified_main  # noqa: E402
from contractgraph_qa.tsse_adapter_cli import (  # noqa: E402
    EXIT_HOLD,
    EXIT_VALIDATION as ADAPTER_EXIT_VALIDATION,
    main,
)


FIXTURE_ROOT = ROOT / "scenarios" / "tsse-tools"
FOUNDRY_CAPTURE = FIXTURE_ROOT / "foundry-capture.json"
FOUNDRY_PROFILE = FIXTURE_ROOT / "foundry-profile.json"
SLITHER_CAPTURE = FIXTURE_ROOT / "slither-capture.json"
SLITHER_PROFILE = FIXTURE_ROOT / "slither-profile.json"


class TSSEAdapterCLITest(unittest.TestCase):
    def test_foundry_ready_returns_zero_and_machine_json(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "--capture",
                    str(FOUNDRY_CAPTURE),
                    "--profile",
                    str(FOUNDRY_PROFILE),
                ]
            )

        self.assertEqual(code, EXIT_OK)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["scanVerdict"], "NOT_ASSESSED")

    def test_slither_static_seeds_return_hold_exit(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "--capture",
                    str(SLITHER_CAPTURE),
                    "--profile",
                    str(SLITHER_PROFILE),
                ]
            )

        self.assertEqual(code, EXIT_HOLD)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "inconclusive")

    def test_unified_cli_normalizes_inconclusive_to_public_validation_exit(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = unified_main(
                [
                    "tsse-adapt",
                    "--capture",
                    str(SLITHER_CAPTURE),
                    "--profile",
                    str(SLITHER_PROFILE),
                ]
            )

        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(json.loads(stdout.getvalue())["tool"], "slither")

    def test_model_and_result_outputs_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            model = Path(temporary) / "model.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--capture",
                        str(FOUNDRY_CAPTURE),
                        "--profile",
                        str(FOUNDRY_PROFILE),
                        "--output",
                        str(output),
                        "--model-out",
                        str(model),
                    ]
                )

            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "ready")
            self.assertEqual(
                json.loads(model.read_text(encoding="utf-8"))["schema"],
                "cgqa/tsse-transition-model/v0.1",
            )

    def test_slither_cannot_be_written_as_tsse_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            model = Path(temporary) / "model.json"
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "--capture",
                        str(SLITHER_CAPTURE),
                        "--profile",
                        str(SLITHER_PROFILE),
                        "--output",
                        str(output),
                        "--model-out",
                        str(model),
                    ]
                )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertFalse(output.exists())
            self.assertFalse(model.exists())
            self.assertIn("dynamic", stderr.getvalue())

    def test_model_output_requires_companion_adapter_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / "model.json"
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "--capture",
                        str(FOUNDRY_CAPTURE),
                        "--profile",
                        str(FOUNDRY_PROFILE),
                        "--model-out",
                        str(model),
                    ]
                )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertFalse(model.exists())
            self.assertIn("companion --output", stderr.getvalue())

    def test_output_cannot_replace_bound_artifact(self) -> None:
        artifact = FIXTURE_ROOT / "artifacts" / "foundry-replay.json"
        before = artifact.read_bytes()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(
                [
                    "--capture",
                    str(FOUNDRY_CAPTURE),
                    "--profile",
                    str(FOUNDRY_PROFILE),
                    "--output",
                    str(artifact),
                    "--force",
                ]
            )

        self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
        self.assertEqual(artifact.read_bytes(), before)
        self.assertIn("bound artifact", stderr.getvalue())

    def test_existing_output_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            output.write_text("old", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "--capture",
                        str(FOUNDRY_CAPTURE),
                        "--profile",
                        str(FOUNDRY_PROFILE),
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertEqual(output.read_text(encoding="utf-8"), "old")
            self.assertIn("--force", stderr.getvalue())

    def test_atomic_replace_failure_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            output.write_text("old", encoding="utf-8")
            with mock.patch(
                "contractgraph_qa.tsse_adapter_cli.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    code = main(
                        [
                            "--capture",
                            str(FOUNDRY_CAPTURE),
                            "--profile",
                            str(FOUNDRY_PROFILE),
                            "--output",
                            str(output),
                            "--force",
                        ]
                    )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertEqual(output.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])

    def test_model_write_failure_leaves_adapter_receipt_for_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            model = Path(temporary) / "model.json"
            stderr = io.StringIO()
            real_write_atomic = __import__(
                "contractgraph_qa.tsse_adapter_cli",
                fromlist=["_write_atomic"],
            )._write_atomic
            calls = 0

            def fail_second_write(path: Path, rendered: str) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("model replace failed")
                real_write_atomic(path, rendered)

            with mock.patch(
                "contractgraph_qa.tsse_adapter_cli._write_atomic",
                side_effect=fail_second_write,
            ):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    stderr
                ):
                    code = main(
                        [
                            "--capture",
                            str(FOUNDRY_CAPTURE),
                            "--profile",
                            str(FOUNDRY_PROFILE),
                            "--output",
                            str(output),
                            "--model-out",
                            str(model),
                        ]
                    )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "ready")
            self.assertFalse(model.exists())
            self.assertIn("model replace failed", stderr.getvalue())

    def test_capture_with_bad_digest_is_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            artifact = copy_root / "artifacts" / "foundry-replay.json"
            artifact.write_bytes(artifact.read_bytes() + b"tamper")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "--capture",
                        str(copy_root / "foundry-capture.json"),
                        "--profile",
                        str(copy_root / "foundry-profile.json"),
                    ]
                )

            self.assertEqual(code, ADAPTER_EXIT_VALIDATION)
            self.assertIn("digest mismatch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
