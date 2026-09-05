from __future__ import annotations

import contextlib
import io
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from contractgraph_qa import action_guard_cli, graph_layers_cli, tsse_adapter_cli, tsse_cli
from contractgraph_qa.evidence_io import write_text_atomic


ROOT = Path(__file__).resolve().parents[2]


class EvidenceOutputTest(unittest.TestCase):
    def test_existing_output_requires_explicit_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            write_text_atomic(output, '{"version": 1}\n')
            with self.assertRaises(FileExistsError):
                write_text_atomic(output, '{"version": 2}\n')
            self.assertEqual(output.read_bytes(), b'{"version": 1}\n')
            write_text_atomic(output, '{"version": 2}\n', force=True)
            self.assertEqual(output.read_bytes(), b'{"version": 2}\n')
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])

    def test_concurrent_publication_preserves_one_complete_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            barrier = threading.Barrier(2, timeout=10)
            real_link = os.link

            def publish_together(source: Path, destination: Path) -> None:
                barrier.wait()
                real_link(source, destination)

            def publish(text: str) -> tuple[bool, str]:
                try:
                    write_text_atomic(output, text)
                    return True, text
                except FileExistsError:
                    return False, text

            with mock.patch(
                "contractgraph_qa.evidence_io.os.link", side_effect=publish_together
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(publish, ('{"run": 1}\n', '{"run": 2}\n')))
            winners = [text for accepted, text in results if accepted]
            self.assertEqual(len(winners), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), winners[0])
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])

    def test_unsupported_atomic_creation_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            with mock.patch(
                "contractgraph_qa.evidence_io.os.link",
                side_effect=OSError("hard links unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "hard links unavailable"):
                    write_text_atomic(output, "{}\n")
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])

    def test_each_cli_preserves_output_created_after_preflight(self) -> None:
        scenarios = ROOT / "scenarios"
        cases = [
            (
                action_guard_cli.main,
                ["--input", str(scenarios / "action-guard/soroban-five-preflight.json")],
                action_guard_cli.EXIT_VALIDATION,
            ),
            (
                tsse_cli.main,
                ["--model", str(scenarios / "tsse-payment-lifecycle.json")],
                tsse_cli.EXIT_VALIDATION,
            ),
            (
                tsse_adapter_cli.main,
                [
                    "--capture", str(scenarios / "tsse-tools/foundry-capture.json"),
                    "--profile", str(scenarios / "tsse-tools/foundry-profile.json"),
                ],
                tsse_adapter_cli.EXIT_VALIDATION,
            ),
            (
                graph_layers_cli.main,
                ["--input", str(scenarios / "action-guard/soroban-five-operational-graph.json")],
                2,
            ),
        ]
        for entrypoint, arguments, expected in cases:
            with self.subTest(cli=entrypoint.__module__):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "result.json"
                    real_link = os.link

                    def publish_after_other_writer(source: Path, destination: Path) -> None:
                        destination.write_bytes(b'{"retained": true}\n')
                        real_link(source, destination)

                    stdout, stderr = io.StringIO(), io.StringIO()
                    with mock.patch(
                        "contractgraph_qa.evidence_io.os.link",
                        side_effect=publish_after_other_writer,
                    ):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            try:
                                code = entrypoint([*arguments, "--output", str(output)])
                            except SystemExit as exc:
                                code = exc.code
                    self.assertEqual(code, expected)
                    self.assertEqual(output.read_bytes(), b'{"retained": true}\n')
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertTrue(stderr.getvalue())
                    self.assertEqual(list(output.parent.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
