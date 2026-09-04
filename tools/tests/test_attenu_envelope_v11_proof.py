"""Static contract checks for the independent envelope-v1.1 proof."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "proofs" / "attenu-envelope-v1.1-independent"
VERIFIER = PROOF / "verify_envelope_vectors.py"
RUNNER = PROOF / "run_pinned_proof.py"
REPORT = PROOF / "report.json"
README = PROOF / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "attenu-envelope-proof.yml"

PIN = "6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64"
PYTHON_UPSTREAM = "f34a351c12ddc08e9c8bd3beca9da4695a46376f"
TYPESCRIPT_UPSTREAM = "51eebfc957c47aeba3738e5f1f67e8d3d55da50f"
TYPESCRIPT_SOURCE = (
    "attenu-io/attenu-guard-ts@"
    f"{TYPESCRIPT_UPSTREAM}:"
    "test/fixtures/vectors/envelopes/envelope_vectors_v1.json"
)


class TestAttenuEnvelopeV11Proof(unittest.TestCase):
    def test_all_durable_artifacts_exist(self) -> None:
        for path in (VERIFIER, RUNNER, REPORT, README, WORKFLOW):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_report_is_the_bounded_18_of_18_result(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["subject"]["sha256"], PIN)
        self.assertEqual(report["subject"]["commit"], PYTHON_UPSTREAM)
        self.assertEqual(report["subject"]["revision"], "envelope_vectors_v1.1")
        self.assertEqual(report["summary"], {
            "accept_cases": 5,
            "agree": 18,
            "cases": 18,
            "disagree": 0,
            "failure_vocabulary_covered": 7,
            "overall": "AGREE",
            "reject_cases": 13,
        })
        self.assertEqual(len(report["cases"]), 18)
        self.assertTrue(all(row["status"] == "AGREE" for row in report["cases"]))
        copies = report["subject"]["source_copies"]
        self.assertEqual([copy["sha256"] for copy in copies], [PIN, PIN, PIN])
        self.assertEqual(copies[2]["source"], TYPESCRIPT_SOURCE)
        self.assertIn(
            "byte identity of Python repository, PyPI wheel, and TypeScript "
            "repository vector copies",
            report["claim_boundary"]["proved"],
        )

    def test_verifier_is_independent_of_the_upstream_runtime(self) -> None:
        verifier = VERIFIER.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertNotRegex(verifier, r"(?:from|import)\s+attenu_guard")
        self.assertNotRegex(runner, r"(?:from|import)\s+attenu_guard")
        self.assertIn("Ed25519PublicKey", verifier)
        self.assertIn("entry_hash", verifier)
        self.assertIn("envelope_duplicate_subject", verifier)
        self.assertIn("failure_position_rule", verifier)
        self.assertIn(TYPESCRIPT_UPSTREAM, runner)
        self.assertIn("npm tarball is deliberately not treated", runner)

    def test_readme_keeps_the_claim_ceiling_and_source_boundary_explicit(self) -> None:
        text = README.read_text(encoding="utf-8")
        for phrase in (
            "18/18 AGREE",
            "global capture completeness",
            "Intended coverage is absent",
            "envelope array is outside the bundle anchor",
            "npm package is **not** used as a raw-vector source",
            "not certification",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_workflow_pins_inputs_and_has_no_credentials(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(PYTHON_UPSTREAM, text)
        self.assertIn(TYPESCRIPT_UPSTREAM, text)
        self.assertIn("attenu-io/attenu-guard-ts", text)
        self.assertIn(
            "test/fixtures/vectors/envelopes/envelope_vectors_v1.json",
            text,
        )
        self.assertIn("attenu-guard==0.13.0", text)
        self.assertNotIn("npm pack", text)
        self.assertNotIn("actions/setup-node", text)
        self.assertIn("cryptography==46.0.4", text)
        self.assertGreaterEqual(text.count("persist-credentials: false"), 3)
        uses = re.findall(r"uses:\s*[^@\s]+@([^\s#]+)", text)
        self.assertTrue(uses)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in uses), uses)
        self.assertRegex(text, r"permissions:\s*\n\s*contents:\s*read")
        self.assertNotIn("pull_request_target", text)


if __name__ == "__main__":
    unittest.main()
