from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from contractgraph_qa.tsse_adapters import (
    ToolCaptureError,
    adapt_tool_capture_file,
    canonical_result_hash,
    validate_tool_capture,
    validate_tool_profile,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "scenarios" / "tsse-tools"
SOROBAN_CAPTURE = FIXTURE_ROOT / "soroban-capture.json"
SOROBAN_PROFILE = FIXTURE_ROOT / "soroban-profile.json"
RECEIPT_RELATIVE = Path("artifacts") / "cargo-soroban-transition-receipt.json"
SNAPSHOT_RELATIVE = Path("artifacts") / "soroban-state-after-repay.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_artifact_digest(
    capture: dict[str, Any], artifact_id: str, digest: str
) -> None:
    artifacts = capture["toolArtifacts"]
    for artifact in artifacts:
        if artifact["id"] == artifact_id:
            artifact["digest"] = digest
            return
    raise AssertionError(f"fixture artifact {artifact_id!r} is missing")


def _copy_fixtures(temporary: str) -> Path:
    destination = Path(temporary) / "tsse-tools"
    shutil.copytree(FIXTURE_ROOT, destination)
    return destination


def _rewrite_receipt(
    root: Path, mutate: Callable[[dict[str, Any]], None]
) -> None:
    receipt_path = root / RECEIPT_RELATIVE
    receipt = _load(receipt_path)
    mutate(receipt)
    _write(receipt_path, receipt)

    capture_path = root / "soroban-capture.json"
    capture = _load(capture_path)
    _set_artifact_digest(capture, "cargo-soroban-receipt", _digest(receipt_path))
    _write(capture_path, capture)


class TSSESorobanAdapterTest(unittest.TestCase):
    def test_fixture_builds_a_bounded_native_bound_graph(self) -> None:
        capture = validate_tool_capture(_load(SOROBAN_CAPTURE))
        profile = validate_tool_profile(_load(SOROBAN_PROFILE))
        self.assertEqual(capture["tool"], "cargo-soroban")
        self.assertEqual(profile["tool"], "cargo-soroban")

        result = adapt_tool_capture_file(SOROBAN_CAPTURE, SOROBAN_PROFILE)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["normalizationStatus"], "complete")
        self.assertEqual(result["scanVerdict"], "NOT_ASSESSED")
        self.assertEqual(result["nativeEvidence"]["status"], "bound")
        self.assertEqual(result["nativeEvidence"]["framework"], "soroban")
        self.assertEqual(result["nativeEvidence"]["steps"], 1)
        self.assertEqual(
            result["nativeEvidence"]["subjectBundleHash"],
            result["subjectBundleHash"],
        )
        self.assertEqual(
            result["nativeEvidence"]["execution"],
            {"matched": 1, "passed": 1, "failed": 0, "ignored": 0},
        )
        self.assertEqual(set(result["nativeBindings"]), {"repay-loan"})
        self.assertEqual(result["tsseResult"]["status"], "pass")
        self.assertIn("did not execute Cargo", result["claimBoundary"])
        self.assertEqual(result["resultHash"], canonical_result_hash(result))

        receipt = _load(FIXTURE_ROOT / RECEIPT_RELATIVE)
        target = result["tsseModel"]["nodes"][1]
        self.assertEqual(
            target["state"]["stateHash"], receipt["steps"][0]["state"]["stateHash"]
        )
        self.assertEqual(
            target["environment"]["externalStateHash"],
            receipt["steps"][0]["environmentHash"],
        )

    def test_soroban_tool_is_present_in_all_public_tool_schemas(self) -> None:
        for filename in (
            "tsse-tool-capture.schema.json",
            "tsse-tool-profile.schema.json",
            "tsse-tool-adapter-result.schema.json",
        ):
            with self.subTest(schema=filename):
                schema = _load(ROOT / "graph" / "schema" / filename)
                self.assertIn(
                    "cargo-soroban", schema["properties"]["tool"]["enum"]
                )

        capture_schema = _load(
            ROOT / "graph" / "schema" / "tsse-tool-capture.schema.json"
        )
        branches = capture_schema["allOf"]
        soroban_branch = next(
            branch
            for branch in branches
            if branch.get("if", {}).get("properties", {}).get("tool", {}).get("const")
            == "cargo-soroban"
        )
        contains = soroban_branch["then"]["properties"]["toolArtifacts"]["contains"]
        self.assertEqual(
            contains["properties"]["kind"]["const"],
            "cargo-soroban-transition-receipt",
        )
        artifact_policy = soroban_branch["then"]["properties"]["toolArtifacts"]
        self.assertEqual(artifact_policy["minItems"], 2)
        self.assertEqual(
            set(artifact_policy["items"]["properties"]["kind"]["enum"]),
            {"cargo-soroban-transition-receipt", "soroban-state-snapshot"},
        )

        result_schema = _load(
            ROOT / "graph" / "schema" / "tsse-tool-adapter-result.schema.json"
        )
        self.assertIn(
            "cargo-soroban",
            result_schema["allOf"][0]["else"]["properties"]["tool"]["enum"],
        )

    def test_every_receipt_coordinate_is_integrity_bound(self) -> None:
        mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            (
                "time",
                lambda receipt: receipt["steps"][0]["time"].__setitem__(
                    "ledgerSequence", 1002
                ),
            ),
            (
                "space",
                lambda receipt: receipt["steps"][0]["space"].__setitem__(
                    "network", "standalone:other"
                ),
            ),
            (
                "state",
                lambda receipt: receipt["steps"][0]["state"].__setitem__(
                    "phase", "PAID"
                ),
            ),
            (
                "environment",
                lambda receipt: receipt["steps"][0].__setitem__(
                    "environmentHash", "0" * 64
                ),
            ),
            (
                "actor",
                lambda receipt: receipt["steps"][0]["actor"].__setitem__(
                    "identity", "attacker"
                ),
            ),
            (
                "authority",
                lambda receipt: receipt["steps"][0]["authority"].__setitem__(
                    "status", "revoked"
                ),
            ),
            (
                "value",
                lambda receipt: receipt["steps"][0]["value"].__setitem__(
                    "moved", 41
                ),
            ),
        )
        for dimension, mutate in mutations:
            with self.subTest(dimension=dimension), tempfile.TemporaryDirectory() as temporary:
                root = _copy_fixtures(temporary)
                _rewrite_receipt(root, mutate)

                with self.assertRaisesRegex(
                    ToolCaptureError, "does not match the reviewed observation"
                ):
                    adapt_tool_capture_file(
                        root / "soroban-capture.json", root / "soroban-profile.json"
                    )

    def test_receipt_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _copy_fixtures(temporary)
            _rewrite_receipt(root, lambda receipt: receipt.__setitem__("proof", True))

            with self.assertRaisesRegex(ToolCaptureError, "unknown fields"):
                adapt_tool_capture_file(
                    root / "soroban-capture.json", root / "soroban-profile.json"
                )

    def test_receipt_subject_bundle_hash_must_match_verified_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _copy_fixtures(temporary)
            _rewrite_receipt(
                root,
                lambda receipt: receipt.__setitem__("subjectBundleHash", "0" * 64),
            )

            with self.assertRaisesRegex(ToolCaptureError, "subjectBundleHash does not match"):
                adapt_tool_capture_file(
                    root / "soroban-capture.json", root / "soroban-profile.json"
                )

    def test_receipt_execution_requires_one_matching_passing_test(self) -> None:
        invalid_counts = (
            {"matched": 0, "passed": 0, "failed": 0, "ignored": 0},
            {"matched": 1, "passed": 0, "failed": 1, "ignored": 0},
            {"matched": 1, "passed": 1, "failed": 0, "ignored": 1},
        )
        for execution in invalid_counts:
            with self.subTest(execution=execution), tempfile.TemporaryDirectory() as temporary:
                root = _copy_fixtures(temporary)
                _rewrite_receipt(
                    root,
                    lambda receipt, counts=execution: receipt.__setitem__(
                        "execution", counts
                    ),
                )

                with self.assertRaisesRegex(
                    ToolCaptureError, "exactly one matched and passed test"
                ):
                    adapt_tool_capture_file(
                        root / "soroban-capture.json", root / "soroban-profile.json"
                    )

    def test_snapshot_bytes_and_receipt_digest_are_cross_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _copy_fixtures(temporary)
            snapshot_path = root / SNAPSHOT_RELATIVE
            snapshot = _load(snapshot_path)
            snapshot["state"]["outstanding"] = 59
            _write(snapshot_path, snapshot)

            capture_path = root / "soroban-capture.json"
            capture = _load(capture_path)
            _set_artifact_digest(
                capture, "soroban-state-after-repay", _digest(snapshot_path)
            )
            _write(capture_path, capture)

            with self.assertRaisesRegex(ToolCaptureError, "snapshotDigest does not match"):
                adapt_tool_capture_file(
                    capture_path, root / "soroban-profile.json"
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = _copy_fixtures(temporary)
            _rewrite_receipt(
                root,
                lambda receipt: receipt["steps"][0].__setitem__(
                    "snapshotDigest", "0" * 64
                ),
            )

            with self.assertRaisesRegex(ToolCaptureError, "snapshotDigest does not match"):
                adapt_tool_capture_file(
                    root / "soroban-capture.json", root / "soroban-profile.json"
                )

    def test_command_requires_locked_package_and_exact_test_selection(self) -> None:
        def without_package(argv: list[str]) -> None:
            package_index = argv.index("-p")
            del argv[package_index : package_index + 2]

        mutations: tuple[
            tuple[str, Callable[[list[str]], None], str], ...
        ] = (
            ("locked", lambda argv: argv.remove("--locked"), "--locked exactly once"),
            ("package", without_package, "select exactly one package"),
            ("exact", lambda argv: argv.remove("--exact"), "--exact exactly once"),
        )
        for label, mutate, message in mutations:
            with self.subTest(selector=label), tempfile.TemporaryDirectory() as temporary:
                root = _copy_fixtures(temporary)
                capture_path = root / "soroban-capture.json"
                capture = _load(capture_path)
                mutate(capture["run"]["argv"])
                _write(capture_path, capture)

                with self.assertRaisesRegex(ToolCaptureError, message):
                    adapt_tool_capture_file(
                        capture_path, root / "soroban-profile.json"
                    )

    def test_unknown_tool_fails_closed(self) -> None:
        capture = copy.deepcopy(_load(SOROBAN_CAPTURE))
        capture["tool"] = "cargo-soroban-unreviewed"

        with self.assertRaisesRegex(ToolCaptureError, "unsupported value"):
            validate_tool_capture(capture)

    def test_repeated_reopen_has_a_stable_result_hash(self) -> None:
        first = adapt_tool_capture_file(SOROBAN_CAPTURE, SOROBAN_PROFILE)
        second = adapt_tool_capture_file(SOROBAN_CAPTURE, SOROBAN_PROFILE)

        self.assertEqual(first["captureHash"], second["captureHash"])
        self.assertEqual(first["normalizationHash"], second["normalizationHash"])
        self.assertEqual(first["resultHash"], second["resultHash"])
        self.assertEqual(first["resultHash"], canonical_result_hash(first))


if __name__ == "__main__":
    unittest.main()
