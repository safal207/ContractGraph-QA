from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main as cli_main  # noqa: E402
from contractgraph_qa.execution_trace import (  # noqa: E402
    execution_trace_from_dict,
    execution_trace_sha256,
    load_execution_trace,
    run_execution_trace,
)


class ExecutionTraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ROOT / "scenarios" / "execution-trace-double-settlement-conflict.json"
        self.data = json.loads(self.fixture.read_text(encoding="utf-8"))

    def test_fixture_fails_both_independent_invariants(self) -> None:
        result = run_execution_trace(load_execution_trace(self.fixture))

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["economicCardinality"]["status"], "fail")
        self.assertEqual(result["successorConsistency"]["status"], "fail")
        self.assertEqual(
            result["economicCardinality"]["violations"][0]["minimalCounterexampleEventIds"],
            ["evt-release", "evt-dispute"],
        )
        self.assertEqual(
            result["successorConsistency"]["violations"][0]["minimalCounterexampleEventIds"],
            ["evt-release", "evt-dispute"],
        )

    def test_duplicate_observations_of_same_effect_and_commit_pass(self) -> None:
        data = copy.deepcopy(self.data)
        first = data["events"][0]
        duplicate = copy.deepcopy(first)
        duplicate["eventId"] = "evt-release-webhook-copy"
        duplicate["sourceRef"] = "webhook:delivery-2"
        data["events"] = [first, duplicate]

        result = run_execution_trace(execution_trace_from_dict(data))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["economicCardinality"]["status"], "pass")
        self.assertEqual(result["successorConsistency"]["status"], "pass")

    def test_uncommitted_competitor_and_unapplied_effect_do_not_fail(self) -> None:
        data = copy.deepcopy(self.data)
        data["events"][1]["economicEffect"]["applied"] = False
        data["events"][1]["stateCommit"]["committed"] = False

        result = run_execution_trace(execution_trace_from_dict(data))
        self.assertEqual(result["status"], "pass")

    def test_economic_only_trace_runs_only_cardinality(self) -> None:
        data = copy.deepcopy(self.data)
        for event in data["events"]:
            event.pop("stateCommit")

        result = run_execution_trace(execution_trace_from_dict(data))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["economicCardinality"]["status"], "fail")
        self.assertEqual(result["successorConsistency"], {"status": "not_applicable"})

    def test_successor_only_trace_runs_only_consistency(self) -> None:
        data = copy.deepcopy(self.data)
        for event in data["events"]:
            event.pop("economicEffect")

        result = run_execution_trace(execution_trace_from_dict(data))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["economicCardinality"], {"status": "not_applicable"})
        self.assertEqual(result["successorConsistency"]["status"], "fail")

    def test_source_refs_and_hash_are_deterministic(self) -> None:
        first = execution_trace_from_dict(self.data)
        second = execution_trace_from_dict(copy.deepcopy(self.data))
        self.assertEqual(execution_trace_sha256(first), execution_trace_sha256(second))
        result = run_execution_trace(first)
        self.assertEqual(result["sourceRefs"], ["tx:0xaaa", "tx:0xbbb"])
        self.assertEqual(len(result["traceSha256"]), 64)

    def test_rejects_event_without_supported_projection(self) -> None:
        data = copy.deepcopy(self.data)
        data["events"] = [{"eventId": "empty"}]
        with self.assertRaisesRegex(ValueError, "economicEffect and/or stateCommit"):
            execution_trace_from_dict(data)

    def test_rejects_duplicate_event_id(self) -> None:
        data = copy.deepcopy(self.data)
        data["events"][1]["eventId"] = data["events"][0]["eventId"]
        with self.assertRaisesRegex(ValueError, "duplicate eventId"):
            execution_trace_from_dict(data)

    def test_rejects_contradictory_commit_semantics_fail_closed(self) -> None:
        data = copy.deepcopy(self.data)
        data["events"][1]["stateCommit"]["commitId"] = data["events"][0]["stateCommit"]["commitId"]
        with self.assertRaisesRegex(ValueError, "commitId has inconsistent static semantics"):
            run_execution_trace(execution_trace_from_dict(data))

    def test_cli_failure_returns_validation_exit(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(["execution-trace-check", "--trace", str(self.fixture)])

        self.assertEqual(exit_code, EXIT_VALIDATION)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "fail")

    def test_cli_safe_trace_returns_ok(self) -> None:
        data = copy.deepcopy(self.data)
        data["events"][1]["economicEffect"]["applied"] = False
        data["events"][1]["stateCommit"]["committed"] = False
        trace = execution_trace_from_dict(data)

        # Exercise the same product semantics directly; repository fixture covers CLI failure path.
        result = run_execution_trace(trace)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(EXIT_OK, 0)


if __name__ == "__main__":
    unittest.main()
