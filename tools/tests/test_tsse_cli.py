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

from contractgraph_qa.tsse_cli import main  # noqa: E402
from contractgraph_qa.cli import main as unified_main  # noqa: E402
from tools.tests.test_tsse import valid_tsse_model  # noqa: E402


class TSSECliTest(unittest.TestCase):
    def _write_model(self, directory: Path, model: dict[str, object]) -> Path:
        path = directory / "tsse-model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        return path

    def test_cli_emits_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = self._write_model(Path(tmp), valid_tsse_model())
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--model", str(model_path)])

        self.assertEqual(code, 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["modelId"], "uniswap-v4-tsse-001")
        self.assertRegex(result["modelHash"], r"^[0-9a-f]{64}$")

    def test_output_file_matches_stdout_without_suppressing_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            model_path = self._write_model(directory, valid_tsse_model())
            output_path = directory / "tsse-result.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    ["--model", str(model_path), "--output", str(output_path)]
                )
            stdout_result = json.loads(stdout.getvalue())
            file_result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(file_result, stdout_result)

    def test_hold_returns_one_and_still_emits_machine_readable_result(self) -> None:
        model = valid_tsse_model()
        model["nodes"][1]["time"]["timestamp"] = 999  # type: ignore[index]
        with tempfile.TemporaryDirectory() as tmp:
            model_path = self._write_model(Path(tmp), model)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--model", str(model_path)])

        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "hold")

    def test_validation_error_returns_two(self) -> None:
        model = valid_tsse_model()
        model["unexpected"] = True
        with tempfile.TemporaryDirectory() as tmp:
            model_path = self._write_model(Path(tmp), model)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["--model", str(model_path)])

        self.assertEqual(code, 2)
        self.assertTrue(stderr.getvalue().strip())

    def test_output_cannot_overwrite_input_model(self) -> None:
        model = valid_tsse_model()
        with tempfile.TemporaryDirectory() as tmp:
            model_path = self._write_model(Path(tmp), model)
            original = model_path.read_bytes()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(
                    ["--model", str(model_path), "--output", str(model_path)]
                )

            self.assertEqual(code, 2)
            self.assertEqual(model_path.read_bytes(), original)
            self.assertIn("must not overwrite", stderr.getvalue())

    def test_existing_output_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            model_path = self._write_model(directory, valid_tsse_model())
            output_path = directory / "existing-result.json"
            output_path.write_text("preserve-me", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                refused = main(
                    ["--model", str(model_path), "--output", str(output_path)]
                )

            self.assertEqual(refused, 2)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "preserve-me")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                replaced = main(
                    [
                        "--model",
                        str(model_path),
                        "--output",
                        str(output_path),
                        "--force",
                    ]
                )

            self.assertEqual(replaced, 0)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                json.loads(stdout.getvalue()),
            )

    def test_failed_atomic_replace_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            model_path = self._write_model(directory, valid_tsse_model())
            output_path = directory / "existing-result.json"
            output_path.write_text("preserve-me", encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch(
                "contractgraph_qa.tsse_cli.os.replace",
                side_effect=OSError("simulated replace failure"),
            ):
                with contextlib.redirect_stderr(stderr):
                    code = main(
                        [
                            "--model",
                            str(model_path),
                            "--output",
                            str(output_path),
                            "--force",
                        ]
                    )

            self.assertEqual(code, 2)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "preserve-me")
            self.assertEqual(list(directory.glob(f".{output_path.name}.*.tmp")), [])

    def test_unified_cli_normalizes_hold_to_public_validation_exit(self) -> None:
        model = valid_tsse_model()
        model["nodes"][1]["time"]["timestamp"] = 999  # type: ignore[index]
        with tempfile.TemporaryDirectory() as tmp:
            model_path = self._write_model(Path(tmp), model)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = unified_main(["tsse", "--model", str(model_path)])

        self.assertEqual(code, 10)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "hold")


if __name__ == "__main__":
    unittest.main()
