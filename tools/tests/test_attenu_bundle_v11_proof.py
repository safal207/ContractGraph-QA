import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OLD_PROOF = ROOT / "proofs" / "attenu-guard-v0.11.0-independent"
PROOF = ROOT / "proofs" / "attenu-guard-v0.12.0-independent"
FIXTURE = PROOF / "bundle_vectors_v1.json"
REPORT = PROOF / "report.json"
EXPECTED_FIXTURE_SHA256 = (
    "b21c5a44a79d422d52857f03e2f3327d559c409e98c482b4664e1ab726327403"
)
NEW_CASES = {
    "reject_widened_scope",
    "reject_uncontained_allow",
    "reject_increased_ttl",
    "reject_loosened_ceiling",
}


def _entry(case, event):
    return next(item for item in case["bundle"]["entries"] if item.get("event") == event)


class AttenuBundleV11ProofTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_pinned_fixture_identity_and_revision(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                         EXPECTED_FIXTURE_SHA256)
        self.assertEqual(self.fixture["version"], "bundle_vectors_v1")
        self.assertEqual(self.fixture["revision"], "bundle_vectors_v1.1")
        self.assertEqual(len(self.fixture["cases"]), 12)

    def test_provenance_check_executes_successfully(self):
        completed = subprocess.run(
            [sys.executable, str(PROOF / "check_report_provenance.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("cases=12/12", completed.stdout)

    def test_first_eight_cases_are_unchanged(self):
        old_fixture = json.loads(
            (OLD_PROOF / "bundle_vectors_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.fixture["cases"][:8], old_fixture["cases"])

    def test_new_cases_have_exactly_the_declared_failure(self):
        reports = {case["name"]: case for case in self.report["cases"]}
        self.assertEqual(set(reports) & NEW_CASES, NEW_CASES)
        for name in sorted(NEW_CASES):
            with self.subTest(case=name):
                case = reports[name]
                observed = [
                    {key: row[key] for key in ("node", "reason", "seq")}
                    for row in case["failure_details"]
                ]
                self.assertTrue(case["passed"])
                self.assertEqual(observed, case["required_failures"])

    def test_ttl_and_ceiling_rows_preserve_the_literal_scope_confound(self):
        cases = {case["name"]: case for case in self.fixture["cases"]}
        for name in ("reject_increased_ttl", "reject_loosened_ceiling"):
            with self.subTest(case=name):
                root = _entry(cases[name], "root")["authority"]
                child = _entry(cases[name], "spawn")["granted"]
                # The 0.11.0 verifier gated its full narrowing check on this
                # literal, non-wildcard-aware difference. It is non-empty for
                # both v1.1 rows, so these rows do not discriminate that bug.
                self.assertEqual(set(child["scopes"]) - set(root["scopes"]), {"crm.read"})


if __name__ == "__main__":
    unittest.main()
