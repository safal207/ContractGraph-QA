from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.ltp_continuity_bridge import (  # noqa: E402
    LTP_SCHEMA_CONTRACT,
    build_ltp_continuity_export,
    canonical_json_bytes,
)

BENCHMARK = ROOT / "benchmarks" / "smart-contract-continuity-bridge-v0.1"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class LtpContinuityBridgeBenchmarkTest(unittest.TestCase):
    def test_committed_pass_artifacts_rebuild_byte_identically(self) -> None:
        observations = _load(BENCHMARK / "observations-pass.json")
        self.assertIsInstance(observations, dict)
        ltp_input, bridge_report = build_ltp_continuity_export(
            intents=[
                _load(BENCHMARK / "intent-attempt-1.json"),
                _load(BENCHMARK / "intent-attempt-2.json"),
            ],
            captures=[
                _load(BENCHMARK / "rpc-capture-attempt-1.json"),
                _load(BENCHMARK / "rpc-capture-attempt-2.json"),
            ],
            receipt_traces=[_load(BENCHMARK / "receipt-trace-attempt-2.json")],
            observations=observations["observations"],
            as_of="2026-08-27T10:10:00Z",
        )

        self.assertEqual(
            canonical_json_bytes(ltp_input),
            (BENCHMARK / "generated-pass-continuity-input.json").read_bytes(),
        )
        self.assertEqual(
            canonical_json_bytes(bridge_report),
            (BENCHMARK / "generated-pass-bridge-report.json").read_bytes(),
        )

    def test_ltp_reports_match_the_expected_fixture_matrix(self) -> None:
        matrix = _load(BENCHMARK / "cases" / "fixture-matrix.json")
        self.assertEqual(
            matrix["schemaVersion"],
            "cgqa-smart-contract-continuity-fixture-matrix-v0.1",
        )
        for case in matrix["cases"]:
            with self.subTest(case=case["caseId"]):
                report_path = (
                    BENCHMARK
                    / "reports"
                    / f"{Path(case['file']).stem}.report.json"
                )
                if case["expectedExit"] == 1:
                    self.assertFalse(report_path.exists())
                    continue
                report = _load(report_path)
                self.assertEqual(report["overall_status"], case["expectedStatus"])
                self.assertEqual(
                    sorted({finding["code"] for finding in report["findings"]}),
                    sorted(case["expectedFindingCodes"]),
                )

    def test_normative_ltp_contract_is_external_and_hash_pinned(self) -> None:
        contract = _load(
            ROOT
            / "contractgraph_qa"
            / "schemas"
            / "ltp_continuity_external_contract_v0_1.json"
        )
        self.assertFalse(contract["vendored"])
        self.assertEqual(contract["commitSha"], LTP_SCHEMA_CONTRACT["commitSha"])
        self.assertEqual(contract["treeSha"], LTP_SCHEMA_CONTRACT["treeSha"])
        self.assertEqual(contract["schemas"], LTP_SCHEMA_CONTRACT["schemas"])

    def test_ltp_deterministic_replay_report_bytes_match(self) -> None:
        self.assertEqual(
            (BENCHMARK / "generated-pass-continuity-report.json").read_bytes(),
            (BENCHMARK / "generated-pass-continuity-report-replay.json").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
