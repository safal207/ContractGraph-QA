import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_PROOF = ROOT / "proofs" / "attenu-guard-v0.12.0-independent"
PROOF = ROOT / "proofs" / "attenu-guard-v0.12.1-independent"
FIXTURE = PROOF / "bundle_vectors_v1.json"
REPORT = PROOF / "report.json"
REFERENCE_REPORT = PROOF / "reference_release_report.json"
DRIVER = PROOF / "replay_reference_releases.py"
EXPECTED_FIXTURE_SHA256 = (
    "54311d68c8342c01ce233f4b1aea251125a4f3323fd9776c01843d3b2f5700ea"
)
EXPECTED_FIXTURE_GIT_BLOB_SHA1 = "88aee3fd8b346810423266a51783ee10c80a6b1f"
APPENDED_CASES = [
    "valid_bundle_v2_literal",
    "reject_increased_ttl_literal",
    "reject_loosened_ceiling_literal",
    "reject_null_ttl_literal",
    "reject_omitted_ceiling_literal",
]
DEFECT_CASES = APPENDED_CASES[1:]
REPLAY_CASES = APPENDED_CASES + ["reject_widened_scope"]
REPOSITORY_SUBJECT = {
    "repository": "safal207/ContractGraph-QA",
    "pull_request": 152,
    "branch": "proof/attenu-guard-v0.12.1-independent",
    "receipt_url": (
        "https://github.com/safal207/ContractGraph-QA/pull/152"
        "#issuecomment-5528155565"
    ),
    "binding": "external receipt binds the exact base, head, and tree",
}


def _entry(case, event):
    return next(item for item in case["bundle"]["entries"] if item.get("event") == event)


def _load_driver():
    spec = importlib.util.spec_from_file_location("attenu_v12_reference_replay", DRIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load replay driver: {DRIVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel_bytes(marker):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture/value.txt", marker)
    return payload.getvalue()


def _npm_tarball_bytes(marker):
    payload = io.BytesIO()
    files = {
        "package/package.json": b'{"name":"fixture","version":"1.0.0"}\n',
        "package/value.txt": marker.encode("utf-8"),
    }
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o644
            member.mtime = 0
            archive.addfile(member, io.BytesIO(content))
    return payload.getvalue()


class AttenuBundleV12ProofTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = _load_driver()
        cls.fixture_raw = FIXTURE.read_bytes()
        cls.fixture = json.loads(cls.fixture_raw)
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.reference_report = json.loads(REFERENCE_REPORT.read_text(encoding="utf-8"))

    def test_pinned_fixture_identity_revision_and_git_blob(self):
        self.assertEqual(hashlib.sha256(self.fixture_raw).hexdigest(), EXPECTED_FIXTURE_SHA256)
        git_blob = b"blob " + str(len(self.fixture_raw)).encode("ascii") + b"\0" + self.fixture_raw
        self.assertEqual(hashlib.sha1(git_blob).hexdigest(), EXPECTED_FIXTURE_GIT_BLOB_SHA1)
        self.assertEqual(len(self.fixture_raw), 146_765)
        self.assertEqual(self.fixture["version"], "bundle_vectors_v1")
        self.assertEqual(self.fixture["revision"], "bundle_vectors_v1.2")
        self.assertEqual(len(self.fixture["cases"]), 17)

    def test_report_provenance_executes_successfully(self):
        completed = subprocess.run(
            [sys.executable, str(PROOF / "check_report_provenance.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("cases=17/17", completed.stdout)

    def test_repository_receipt_and_temporal_boundary_are_explicit(self):
        self.assertEqual(self.report["repository_subject"], REPOSITORY_SUBJECT)
        self.assertEqual(self.reference_report["repository_subject"], REPOSITORY_SUBJECT)
        readme = (PROOF / "README.md").read_text(encoding="utf-8")
        self.assertIn(REPOSITORY_SUBJECT["receipt_url"], readme)
        self.assertIn(
            "| Temporal Lifecycle | NOT_RUN |",
            readme,
        )
        self.assertNotIn("| Temporal Lifecycle | RUN |", readme)

    def test_reference_replay_static_provenance_executes_successfully(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(PROOF / "check_reference_replay_provenance.py"),
                "--static-only",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("observations=24/24", completed.stdout)
        self.assertIn("defect_transitions=8/8", completed.stdout)

    def test_first_twelve_cases_are_structurally_unchanged(self):
        previous = json.loads(
            (PREVIOUS_PROOF / "bundle_vectors_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.fixture["cases"][:12], previous["cases"])

    def test_appended_rows_have_the_declared_order_and_results(self):
        appended = self.fixture["cases"][12:]
        self.assertEqual([case["name"] for case in appended], APPENDED_CASES)
        reports = {case["name"]: case for case in self.report["cases"]}
        self.assertTrue(reports["valid_bundle_v2_literal"]["passed"])
        self.assertEqual(reports["valid_bundle_v2_literal"]["failure_details"], [])
        for name in DEFECT_CASES:
            with self.subTest(case=name):
                case = reports[name]
                observed = [
                    {key: row[key] for key in ("node", "reason", "seq")}
                    for row in case["failure_details"]
                ]
                self.assertTrue(case["passed"])
                self.assertEqual(observed, case["required_failures"])
                self.assertEqual(
                    observed,
                    [{"node": "vectors:n1", "reason": "monotonicity", "seq": 1}],
                )

    def test_literal_subset_rows_isolate_one_authority_dimension(self):
        cases = {case["name"]: case for case in self.fixture["cases"]}
        base = cases["valid_bundle_v2_literal"]
        root_authority = _entry(base, "root")["authority"]
        base_grant = _entry(base, "spawn")["granted"]
        self.assertEqual(root_authority["scopes"], ["crm.read", "mail.send"])
        self.assertEqual(base_grant["scopes"], ["crm.read"])
        self.assertNotIn("*", "".join(root_authority["scopes"]))
        self.assertEqual(set(base_grant["scopes"]) - set(root_authority["scopes"]), set())

        expected_grants = {}
        increased_ttl = copy.deepcopy(base_grant)
        increased_ttl["ttl"] = 7200
        expected_grants["reject_increased_ttl_literal"] = increased_ttl
        loosened_ceiling = copy.deepcopy(base_grant)
        loosened_ceiling["constraints"][0]["max"] = 250_000
        expected_grants["reject_loosened_ceiling_literal"] = loosened_ceiling
        null_ttl = copy.deepcopy(base_grant)
        null_ttl["ttl"] = None
        expected_grants["reject_null_ttl_literal"] = null_ttl
        omitted_ceiling = copy.deepcopy(base_grant)
        omitted_ceiling["constraints"] = []
        expected_grants["reject_omitted_ceiling_literal"] = omitted_ceiling

        for name, expected_grant in expected_grants.items():
            with self.subTest(case=name):
                case = cases[name]
                self.assertEqual(_entry(case, "root")["authority"], root_authority)
                self.assertEqual(_entry(case, "spawn")["granted"], expected_grant)

    def test_exact_official_rows_discriminate_old_and_new_packages(self):
        report = self.reference_report
        self.assertEqual(
            report["summary"],
            {
                "defect_transitions_proved": 8,
                "observations_matched": 24,
                "observations_total": 24,
                "passed": True,
                "stable_control_transitions": 4,
            },
        )
        self.assertEqual(report["case_inputs"]["selected_order"], REPLAY_CASES)
        for implementation in ("python", "typescript"):
            before = {
                case["name"]: case
                for case in report["results"][f"{implementation}_before"]["cases"]
            }
            after = {
                case["name"]: case
                for case in report["results"][f"{implementation}_after"]["cases"]
            }
            self.assertEqual(before["valid_bundle_v2_literal"]["decision"], "accept")
            self.assertEqual(after["valid_bundle_v2_literal"]["decision"], "accept")
            self.assertEqual(before["reject_widened_scope"]["decision"], "reject")
            self.assertEqual(after["reject_widened_scope"]["decision"], "reject")
            for name in DEFECT_CASES:
                with self.subTest(implementation=implementation, case=name):
                    self.assertEqual(before[name]["decision"], "accept")
                    self.assertEqual(after[name]["decision"], "reject")
                    self.assertEqual(before[name]["case_sha256"], after[name]["case_sha256"])
                    self.assertEqual(
                        before[name]["bundle_sha256"], after[name]["bundle_sha256"]
                    )

    def test_transition_counts_are_derived_from_observations(self):
        report = self.reference_report
        python_before = report["results"]["python_before"]["cases"]
        python_after = report["results"]["python_after"]["cases"]
        self.assertEqual(
            self.driver._transition_counts(python_before, python_after),
            {"defect_cases_flipped": 4, "controls_stable": 2, "passed": True},
        )

        changed_after = copy.deepcopy(python_after)
        changed_after[1]["decision"] = "accept"
        self.assertEqual(
            self.driver._transition_counts(python_before, changed_after),
            {"defect_cases_flipped": 3, "controls_stable": 2, "passed": False},
        )

    def test_verified_wheel_snapshot_survives_path_swap(self):
        trusted = _wheel_bytes("trusted")
        swapped = _wheel_bytes("swapped")
        identity = {
            "filename": "fixture.whl",
            "package": "fixture",
            "version": "1.0.0",
            "sha256": hashlib.sha256(trusted).hexdigest(),
            "bytes": len(trusted),
            "format": "wheel",
        }
        with tempfile.TemporaryDirectory(prefix="attenu-v12-wheel-snapshot-") as temporary:
            root = Path(temporary)
            supplied = root / "fixture.whl"
            destination = root / "extracted"
            destination.mkdir()
            supplied.write_bytes(trusted)
            report, frozen = self.driver._verified_artifact(supplied, identity)
            supplied.write_bytes(swapped)
            self.driver._extract_wheel(frozen, destination)
            self.assertEqual(
                (destination / "fixture" / "value.txt").read_text(encoding="utf-8"),
                "trusted",
            )
            self.assertEqual(report["execution_source"], "same verified in-memory bytes")
            self.assertNotEqual(report["sha256"], hashlib.sha256(swapped).hexdigest())

    def test_verified_npm_snapshot_survives_path_swap(self):
        trusted = _npm_tarball_bytes("trusted")
        swapped = _npm_tarball_bytes("swapped")
        identity = {
            "filename": "fixture.tgz",
            "package": "fixture",
            "version": "1.0.0",
            "sha256": hashlib.sha256(trusted).hexdigest(),
            "bytes": len(trusted),
            "format": "npm-tarball",
        }
        with tempfile.TemporaryDirectory(prefix="attenu-v12-npm-snapshot-") as temporary:
            root = Path(temporary)
            supplied = root / "fixture.tgz"
            destination = root / "extracted"
            destination.mkdir()
            supplied.write_bytes(trusted)
            report, frozen = self.driver._verified_artifact(supplied, identity)
            supplied.write_bytes(swapped)
            package_root = self.driver._extract_npm_tarball(frozen, destination)
            self.assertEqual(
                (package_root / "value.txt").read_text(encoding="utf-8"),
                "trusted",
            )
            self.assertEqual(report["execution_source"], "same verified in-memory bytes")
            self.assertNotEqual(report["sha256"], hashlib.sha256(swapped).hexdigest())

    def test_tampered_fixture_and_archive_escape_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="attenu-v12-negative-") as temporary:
            root = Path(temporary)
            tampered = root / "bundle_vectors_v1.json"
            tampered.write_bytes(self.fixture_raw + b"\n")
            with mock.patch.object(self.driver, "FIXTURE", tampered):
                with self.assertRaisesRegex(ValueError, "fixture byte count"):
                    self.driver._load_fixture()
            with self.assertRaisesRegex(ValueError, "archive path escapes"):
                self.driver._safe_target(root, "../escape")


if __name__ == "__main__":
    unittest.main()
