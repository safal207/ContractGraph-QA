from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contractgraph_qa.interop_conformance as conformance
from contractgraph_qa.interop_conformance import (
    CLAIM_BOUNDARY,
    DEFAULT_SUITE_PATH,
    INVALID_BLOCKED,
    SUITE_SHA256,
    UNSAFE_ACCEPTED,
    VALID_NON_AUTHORIZING,
    InteropConformanceError,
    load_interop_conformance_suite,
    run_interop_conformance_suite,
)
from contractgraph_qa.liminalqa_interop_cli import conformance_main

ROOT = Path(__file__).resolve().parents[2]
SUITE_ROOT = DEFAULT_SUITE_PATH.parent


class InteropConformanceTest(unittest.TestCase):
    def test_default_suite_is_exactly_pinned_and_covers_both_directions(self) -> None:
        suite = load_interop_conformance_suite()

        self.assertEqual(hashlib.sha256(DEFAULT_SUITE_PATH.read_bytes()).hexdigest(), SUITE_SHA256)
        self.assertEqual(suite["claimBoundary"], CLAIM_BOUNDARY)
        self.assertEqual(len(suite["contracts"]), 2)
        self.assertEqual(len(suite["cases"]), 14)
        self.assertEqual(len({case["id"] for case in suite["cases"]}), 14)
        for contract in suite["contracts"]:
            outcomes = {
                case["expectedSemantics"]
                for case in suite["cases"]
                if case["contract"] == contract["id"]
            }
            self.assertEqual(outcomes, {VALID_NON_AUTHORIZING, INVALID_BLOCKED})

    def test_vendored_assets_match_canonical_bytes_and_declared_digests(self) -> None:
        suite = load_interop_conformance_suite()
        contracts = {contract["id"]: contract for contract in suite["contracts"]}

        for contract in contracts.values():
            schema = SUITE_ROOT / contract["schemaPath"]
            fixture = SUITE_ROOT / contract["fixturePath"]
            self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(), contract["schemaSha256"])
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), contract["fixtureSha256"])

        self.assertEqual(
            (SUITE_ROOT / contracts["cgqa-evidence"]["schemaPath"]).read_bytes(),
            (ROOT / "contractgraph_qa/schemas/cgqa-liminalqa-evidence-v0.1.schema.json").read_bytes(),
        )
        self.assertEqual(
            (SUITE_ROOT / contracts["liminal-candidates"]["fixturePath"]).read_bytes(),
            (ROOT / "tools/tests/fixtures/liminalqa-cgqa-candidates-v0.1.json").read_bytes(),
        )

    def test_reference_runner_passes_every_vector_without_side_effect_authority(self) -> None:
        report = run_interop_conformance_suite()

        self.assertEqual(report, run_interop_conformance_suite())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["counts"], {"total": 14, "passed": 14, "failed": 0})
        self.assertEqual(report["implementation"]["language"], "python")
        self.assertEqual(len(report["contractPins"]), 2)
        self.assertIs(report["authority"]["mayAuthorizeAction"], False)
        self.assertTrue(all(result["sideEffectExecuted"] is False for result in report["results"]))

        golden = [result for result in report["results"] if result["category"] == "golden"]
        blocked = [result for result in report["results"] if result["category"] != "golden"]
        cases = {case["id"]: case for case in load_interop_conformance_suite()["cases"]}
        self.assertTrue(
            all(result["inputSha256"] == cases[result["id"]]["expectedInputSha256"] for result in report["results"])
        )
        self.assertEqual({result["observedSemantics"] for result in golden}, {VALID_NON_AUTHORIZING})
        self.assertEqual({result["observedSemantics"] for result in blocked}, {INVALID_BLOCKED})
        self.assertEqual(
            {result["category"] for result in blocked},
            {
                "authority_escalation",
                "semantic_mismatch",
                "temporal_inversion",
                "unknown_field",
                "ambiguous_json",
                "verification_weakening",
                "unsafe_identifier",
            },
        )

    def test_runner_reports_adapter_semantic_drift_as_failure(self) -> None:
        original_observe = conformance._observe
        calls = 0

        def drifting_observe(artifact_schema: str, raw: bytes) -> tuple[str, str]:
            nonlocal calls
            calls += 1
            observed = original_observe(artifact_schema, raw)
            if calls == 1:
                return INVALID_BLOCKED, "simulated adapter drift"
            return observed

        with patch.object(conformance, "_observe", side_effect=drifting_observe):
            report = run_interop_conformance_suite()

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["counts"], {"total": 14, "passed": 13, "failed": 1})
        self.assertEqual(report["results"][0]["diagnostic"], "simulated adapter drift")
        self.assertNotEqual(report["reportId"], run_interop_conformance_suite()["reportId"])

    def test_authorizing_acceptance_is_observed_as_unsafe_not_blocked(self) -> None:
        raw = (SUITE_ROOT / "fixtures/cgqa-liminalqa-evidence-v0.1.json").read_bytes()
        accepted = json.loads(raw)
        accepted["authority"]["mayAuthorizeAction"] = True

        with patch.object(conformance, "validate_liminalqa_evidence_export", return_value=accepted):
            observed, diagnostic = conformance._observe(
                "org.contractgraph-qa.liminalqa-evidence.v0.1",
                raw,
            )

        self.assertEqual(observed, UNSAFE_ACCEPTED)
        self.assertIn("action authority", diagnostic)

    def test_runner_rejects_tampered_asset_and_rewritten_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "liminalqa-v0.1"
            shutil.copytree(SUITE_ROOT, copied)
            fixture = copied / "fixtures/cgqa-liminalqa-evidence-v0.1.json"
            fixture.write_bytes(fixture.read_bytes() + b" ")
            with self.assertRaisesRegex(InteropConformanceError, "fixture digest mismatch"):
                run_interop_conformance_suite(copied / "suite.json")

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "liminalqa-v0.1"
            shutil.copytree(SUITE_ROOT, copied)
            manifest = copied / "suite.json"
            manifest.write_bytes(manifest.read_bytes() + b" ")
            with self.assertRaisesRegex(InteropConformanceError, "suite digest"):
                run_interop_conformance_suite(manifest)

    def test_runner_rejects_byte_different_mutation_before_adapter_invocation(self) -> None:
        with (
            patch.object(conformance, "_apply_operation", return_value=b"{}\n"),
            patch.object(conformance, "_observe") as observe,
            self.assertRaisesRegex(InteropConformanceError, "mutation digest"),
        ):
            run_interop_conformance_suite()

        observe.assert_not_called()

    def test_cli_emits_one_machine_readable_non_authorizing_report(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = conformance_main([])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["status"], "PASS")
        self.assertIs(report["authority"]["mayAuthorizeAction"], False)


if __name__ == "__main__":
    unittest.main()
