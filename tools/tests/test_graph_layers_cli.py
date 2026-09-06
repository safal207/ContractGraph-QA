from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.graph_layers_cli import main
from tools.tests.test_graph_layers import document, edge


class GraphLayersCliTests(unittest.TestCase):
    def _write_graph(self, directory: Path, *, observed: bool = True) -> Path:
        path = directory / "graph.json"
        graph = document(fact=[edge("e1", "a", "b", "observed")] if observed else [])
        path.write_text(json.dumps(graph), encoding="utf-8")
        return path

    def _assert_invalid(self, args: list[str], message: str) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                main(args)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(message, stderr.getvalue())

    def test_computed_diff_keeps_exit_zero_and_output_matches_stdout(self) -> None:
        for observed, expected in ((True, "aligned"), (False, "drift_detected")):
            with self.subTest(status=expected), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                source = self._write_graph(directory, observed=observed)
                output = directory / "results" / "diff.json"
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = main(["--input", str(source), "--output", str(output)])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout.getvalue())["status"], expected)
                self.assertEqual(output.read_text(encoding="utf-8"), stdout.getvalue())

    def test_duplicate_fields_fail_before_output_is_written(self) -> None:
        duplicates = (
            ('"graphId": "test-graph"', '"graphId": "test-graph", "graphId": "test-graph"'),
            ('"from": "a"', '"from": "a", "from": "a"'),
        )
        for original_field, duplicated_field in duplicates:
            with self.subTest(field=original_field), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                source = self._write_graph(directory)
                text = source.read_text(encoding="utf-8")
                self.assertIn(original_field, text)
                source.write_text(text.replace(original_field, duplicated_field, 1), encoding="utf-8")
                output = directory / "diff.json"
                self._assert_invalid(
                    ["--input", str(source), "--output", str(output)],
                    "duplicate JSON object key",
                )
                self.assertFalse(output.exists())

    def test_non_json_constants_are_rejected_by_loader(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as tmp:
                source = self._write_graph(Path(tmp))
                text = source.read_text(encoding="utf-8")
                source.write_text(
                    text.replace('"graphId": "test-graph"', f'"graphId": {constant}', 1),
                    encoding="utf-8",
                )
                self._assert_invalid(["--input", str(source)], "non-JSON numeric constant")

    def test_input_graph_cannot_be_overwritten_even_with_force(self) -> None:
        for force in (False, True):
            with self.subTest(force=force), tempfile.TemporaryDirectory() as tmp:
                source = self._write_graph(Path(tmp))
                original = source.read_bytes()
                args = ["--input", str(source), "--output", str(source)]
                if force:
                    args.append("--force")
                self._assert_invalid(args, "must not overwrite the input graph")
                self.assertEqual(source.read_bytes(), original)

    def test_resolved_input_alias_is_rejected_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self._write_graph(directory)
            original = source.read_bytes()
            (directory / "nested").mkdir()
            alias = directory / "nested" / ".." / source.name
            self._assert_invalid(
                ["--input", str(source), "--output", str(alias), "--force"],
                "must not overwrite the input graph",
            )
            self.assertEqual(source.read_bytes(), original)

    def test_hardlink_input_alias_is_rejected_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self._write_graph(directory)
            original = source.read_bytes()
            alias = directory / "alias.json"
            try:
                os.link(source, alias)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            self._assert_invalid(
                ["--input", str(source), "--output", str(alias), "--force"],
                "must not overwrite the input graph",
            )
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(alias.read_bytes(), original)

    def test_existing_output_is_preserved_until_force_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = self._write_graph(directory)
            output = directory / "diff.json"
            output.write_text("previous evidence", encoding="utf-8")
            args = ["--input", str(source), "--output", str(output)]
            self._assert_invalid(args, "already exists")
            self.assertEqual(output.read_text(encoding="utf-8"), "previous evidence")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([*args, "--force"])
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
