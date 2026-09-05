from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.tsse_adapters import (  # noqa: E402
    ENVIRONMENT_HASH_DOMAIN,
    STATE_HASH_DOMAIN,
    ToolCaptureError,
    adapt_tool_capture,
    adapt_tool_capture_file,
    canonical_result_hash,
    canonical_sha256,
    load_tool_capture,
    load_tool_profile,
    validate_tool_capture,
)


FIXTURE_ROOT = ROOT / "scenarios" / "tsse-tools"
FOUNDRY_CAPTURE = FIXTURE_ROOT / "foundry-capture.json"
FOUNDRY_PROFILE = FIXTURE_ROOT / "foundry-profile.json"
SLITHER_CAPTURE = FIXTURE_ROOT / "slither-capture.json"
SLITHER_PROFILE = FIXTURE_ROOT / "slither-profile.json"

ECHIDNA_DIGEST = "62c62a9198d3ba205cc316f9c5a269dba3f27a2a60c289e25ccdf0fb7dc98340"
MEDUSA_DIGEST = "872c67a61999a6b408271d9c3fa4019be2c5e8717bce094afe2a99d5c8c303b0"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _adapt(
    capture: dict[str, object],
    profile: dict[str, object],
    *,
    capture_root: Path = FIXTURE_ROOT,
    profile_root: Path = FIXTURE_ROOT,
) -> dict[str, object]:
    return adapt_tool_capture(capture, capture_root, profile, profile_root)


def _dynamic_case(tool: str) -> tuple[dict[str, object], dict[str, object]]:
    capture = copy.deepcopy(_load(FOUNDRY_CAPTURE))
    profile = copy.deepcopy(_load(FOUNDRY_PROFILE))
    if tool == "echidna":
        version = "echidna-fixture-v0.1"
        artifact_id = "echidna-campaign"
        artifact_kind = "echidna-campaign-json"
        artifact_path = "artifacts/echidna-campaign.json"
        digest = ECHIDNA_DIGEST
        argv = ["echidna", ".", "--format", "json"]
    elif tool == "medusa":
        version = "medusa-fixture-v0.1"
        artifact_id = "medusa-counterexample"
        artifact_kind = "medusa-counterexample"
        artifact_path = "artifacts/medusa-counterexample.json"
        digest = MEDUSA_DIGEST
        argv = ["medusa", "fuzz", "--target-contracts", "PaymentCoordinator"]
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(tool)

    scope = f"Repository-owned synthetic {tool} fixture; no production security claim."
    capture["captureId"] = f"{tool}-payment-lifecycle-v0.1"
    capture["tool"] = tool
    capture["toolVersion"] = version
    capture["run"]["argv"] = argv
    capture["toolArtifacts"] = [
        {
            "id": artifact_id,
            "kind": artifact_kind,
            "path": artifact_path,
            "digest": digest,
        }
    ]
    for observation in capture["observations"][1:]:
        observation["incoming"]["evidenceRefs"] = [artifact_id]
    capture["scope"] = scope

    profile["profileId"] = f"{tool}-payment-policy-v0.1"
    profile["tool"] = tool
    profile["acceptedToolVersions"] = [version]
    profile["observationHash"] = canonical_sha256(capture["observations"])
    profile["scope"] = scope
    return capture, profile


class TSSEToolAdapterTest(unittest.TestCase):
    def test_foundry_fixture_builds_native_bound_ready_tsse_model(self) -> None:
        result = adapt_tool_capture_file(FOUNDRY_CAPTURE, FOUNDRY_PROFILE)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["normalizationStatus"], "complete")
        self.assertEqual(result["scanVerdict"], "NOT_ASSESSED")
        self.assertEqual(result["tsseResult"]["status"], "pass")
        self.assertEqual(result["tsseResult"]["counts"]["transitions"], 2)
        self.assertTrue(all(result["tsseModel"]["requirements"].values()))
        self.assertEqual(result["nativeEvidence"]["status"], "bound")
        self.assertEqual(
            set(result["nativeBindings"]),
            {"authorize-payment", "settle-payment"},
        )
        self.assertTrue(result["tsseModel"]["exactSubject"]["commit"].startswith("sha256:"))
        self.assertEqual(result["resultHash"], canonical_result_hash(result))

        created = result["tsseModel"]["nodes"][0]
        expected_state = canonical_sha256(
            {
                "domain": STATE_HASH_DOMAIN,
                "phase": created["state"]["phase"],
                "values": created["state"]["values"],
            }
        )
        expected_environment = canonical_sha256(
            {
                "domain": ENVIRONMENT_HASH_DOMAIN,
                "environment": _load(FOUNDRY_CAPTURE)["observations"][0]["environment"],
            }
        )
        self.assertEqual(created["state"]["stateHash"], expected_state)
        self.assertEqual(
            created["environment"]["externalStateHash"],
            expected_environment,
        )

    def test_slither_fixture_produces_only_unverified_static_seed(self) -> None:
        result = adapt_tool_capture_file(SLITHER_CAPTURE, SLITHER_PROFILE)

        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["normalizationStatus"], "complete")
        self.assertEqual(result["scanVerdict"], "NOT_ASSESSED")
        self.assertNotIn("tsseModel", result)
        self.assertNotIn("tsseResult", result)
        self.assertEqual(len(result["staticSeeds"]), 1)
        seed = result["staticSeeds"][0]
        self.assertEqual(seed["detector"], "reentrancy-eth")
        self.assertEqual(seed["verificationStatus"], "unverified")
        self.assertEqual(seed["recommendedDynamicTools"], ["foundry", "echidna", "medusa"])

    def test_real_echidna_and_medusa_artifacts_bind_native_sequences(self) -> None:
        for tool in ("echidna", "medusa"):
            with self.subTest(tool=tool):
                capture, profile = _dynamic_case(tool)
                result = _adapt(capture, profile)
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["tool"], tool)
                self.assertEqual(result["nativeEvidence"]["status"], "bound")
                self.assertEqual(len(result["nativeBindings"]), 2)
                self.assertEqual(result["tsseResult"]["status"], "pass")

    def test_echidna_nullable_arguments_are_supported_but_items_are_strings(self) -> None:
        for arguments, should_pass in ((None, True), ([100], False)):
            with self.subTest(arguments=arguments):
                with tempfile.TemporaryDirectory() as temporary:
                    copy_root = Path(temporary) / "capture"
                    shutil.copytree(FIXTURE_ROOT, copy_root)
                    artifact = copy_root / "artifacts" / "echidna-campaign.json"
                    campaign = _load(artifact)
                    campaign["tests"][0]["transactions"][0]["arguments"] = arguments
                    artifact.write_text(json.dumps(campaign), encoding="utf-8")
                    capture, profile = _dynamic_case("echidna")
                    capture["toolArtifacts"][0]["digest"] = hashlib.sha256(
                        artifact.read_bytes()
                    ).hexdigest()

                    if should_pass:
                        result = _adapt(
                            capture,
                            profile,
                            capture_root=copy_root,
                            profile_root=copy_root,
                        )
                        self.assertEqual(result["status"], "ready")
                    else:
                        with self.assertRaisesRegex(ToolCaptureError, "must be a non-empty string"):
                            _adapt(
                                capture,
                                profile,
                                capture_root=copy_root,
                                profile_root=copy_root,
                            )

    def test_relabeling_foundry_bytes_as_echidna_is_rejected(self) -> None:
        capture = copy.deepcopy(_load(FOUNDRY_CAPTURE))
        profile = copy.deepcopy(_load(FOUNDRY_PROFILE))
        scope = "Synthetic relabel attack fixture."
        capture["tool"] = "echidna"
        capture["toolVersion"] = "echidna-fixture-v0.1"
        capture["run"]["argv"] = ["echidna", ".", "--format", "json"]
        capture["toolArtifacts"][0]["kind"] = "echidna-campaign-json"
        capture["scope"] = scope
        profile["tool"] = "echidna"
        profile["acceptedToolVersions"] = ["echidna-fixture-v0.1"]
        profile["scope"] = scope

        with self.assertRaises(ToolCaptureError):
            _adapt(capture, profile)

    def test_native_action_sequence_mismatch_is_rejected(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        capture["observations"][1]["incoming"]["action"] = "withdraw"
        profile["observationHash"] = canonical_sha256(capture["observations"])

        with self.assertRaisesRegex(ToolCaptureError, "do not exactly match"):
            _adapt(capture, profile)

    def test_forbidden_phase_replay_returns_hold(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        capture["observations"][1]["state"]["phase"] = "SETTLED"
        capture["observations"][2]["state"]["phase"] = "AUTHORIZED"
        profile["observationHash"] = canonical_sha256(capture["observations"])

        result = _adapt(capture, profile)

        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["tsseResult"]["status"], "hold")
        codes = {item["code"] for item in result["tsseResult"]["violations"]}
        self.assertIn("FORBIDDEN_PHASE_TRANSITION", codes)

    def test_unknown_nested_tsse_status_never_becomes_ready(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)

        with mock.patch(
            "contractgraph_qa.tsse_adapters.common.run_tsse_model",
            return_value={"status": "inconclusive"},
        ):
            with self.assertRaisesRegex(ToolCaptureError, "unsupported status"):
                _adapt(capture, profile)

    def test_nonterminal_dynamic_run_is_rejected(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        capture["run"]["termination"] = "timed-out"
        capture["run"]["exitCode"] = None

        with self.assertRaisesRegex(ToolCaptureError, "completed run"):
            _adapt(capture, profile)

    def test_unaccepted_exit_code_and_version_are_rejected(self) -> None:
        for field, value, message in (
            ("exitCode", 1, "not accepted"),
            ("toolVersion", "forge-unreviewed", "not accepted"),
        ):
            with self.subTest(field=field):
                capture = _load(FOUNDRY_CAPTURE)
                profile = _load(FOUNDRY_PROFILE)
                if field == "exitCode":
                    capture["run"][field] = value
                else:
                    capture[field] = value
                with self.assertRaisesRegex(ToolCaptureError, message):
                    _adapt(capture, profile)

    def test_capture_cannot_replace_external_profile_policy(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        capture["forbiddenTransitions"][0]["fromPhase"] = "NEVER"

        with self.assertRaisesRegex(ToolCaptureError, "does not exactly match"):
            _adapt(capture, profile)

    def test_capture_cannot_replace_reviewed_observation_coordinates(self) -> None:
        for dimension, mutate in (
            (
                "state",
                lambda capture: capture["observations"][1]["state"]["values"].__setitem__(
                    "amount", 999999999
                ),
            ),
            (
                "actor",
                lambda capture: capture["observations"][1]["actor"].__setitem__(
                    "identity", "invented-actor"
                ),
            ),
            (
                "environment",
                lambda capture: capture["observations"][1]["environment"].__setitem__(
                    "oracleState", "invented-oracle"
                ),
            ),
        ):
            with self.subTest(dimension=dimension):
                capture = _load(FOUNDRY_CAPTURE)
                profile = _load(FOUNDRY_PROFILE)
                mutate(capture)
                with self.assertRaisesRegex(ToolCaptureError, "observationHash"):
                    _adapt(capture, profile)

    def test_max_sequence_bound_covers_every_transition(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        capture["run"]["bounds"]["maxSequenceLength"] = 1

        with self.assertRaisesRegex(ToolCaptureError, "exceeds"):
            validate_tool_capture(capture)

    def test_completed_dynamic_run_requires_concrete_positive_bounds(self) -> None:
        for bound in ("testLimit", "maxSequenceLength", "timeLimitSeconds", "workers"):
            with self.subTest(bound=bound):
                capture = _load(FOUNDRY_CAPTURE)
                capture["run"]["bounds"][bound] = None
                with self.assertRaisesRegex(ToolCaptureError, f"positive {bound}"):
                    validate_tool_capture(capture)

    def test_recorded_command_must_match_native_adapter(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        capture["run"]["argv"][1] = "script"

        with self.assertRaisesRegex(ToolCaptureError, "forge test"):
            _adapt(capture, profile)

    def test_dynamic_native_contract_must_match_observed_space(self) -> None:
        capture, profile = _dynamic_case("echidna")
        capture["observations"][1]["space"]["contract"] = "OtherContract"
        profile["observationHash"] = canonical_sha256(capture["observations"])

        with self.assertRaisesRegex(ToolCaptureError, "observation space"):
            _adapt(capture, profile)

    def test_artifact_digest_is_recomputed_from_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            source = copy_root / "artifacts" / "PaymentCoordinator.sol"
            source.write_bytes(source.read_bytes() + b"\n// tampered\n")

            with self.assertRaisesRegex(ToolCaptureError, "digest mismatch"):
                adapt_tool_capture_file(
                    copy_root / "foundry-capture.json",
                    copy_root / "foundry-profile.json",
                )

    def test_capture_and_profile_subject_artifacts_are_verified_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            capture_root = Path(temporary) / "capture"
            profile_root = Path(temporary) / "profile"
            shutil.copytree(FIXTURE_ROOT, capture_root)
            shutil.copytree(FIXTURE_ROOT, profile_root)

            result = adapt_tool_capture_file(
                capture_root / "foundry-capture.json",
                profile_root / "foundry-profile.json",
            )
            self.assertEqual(result["status"], "ready")

            profile_source = profile_root / "artifacts" / "PaymentCoordinator.sol"
            profile_source.write_bytes(profile_source.read_bytes() + b"\n// profile tamper\n")
            with self.assertRaisesRegex(ToolCaptureError, "profile subject.*digest mismatch"):
                adapt_tool_capture_file(
                    capture_root / "foundry-capture.json",
                    profile_root / "foundry-profile.json",
                )

    def test_relative_paths_cannot_escape_capture_directory(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        capture["subject"]["artifacts"][0]["path"] = "../PaymentCoordinator.sol"

        with self.assertRaisesRegex(ToolCaptureError, "parent"):
            validate_tool_capture(capture)

    def test_every_dynamic_artifact_must_be_bound_to_a_transition(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        capture["toolArtifacts"].append(
            {
                "id": "orphan",
                "kind": "state-snapshot",
                "path": "artifacts/slither-result.json",
                "digest": "653077439a6a0855595ce73c1cd8b2e4167bb76cbd8fbef1b35c146b241d8307",
            }
        )

        with self.assertRaisesRegex(ToolCaptureError, "not referenced"):
            validate_tool_capture(capture)

    def test_duplicate_capture_and_profile_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "capture.json"
            profile = root / "profile.json"
            duplicate = (
                '{"schema":"cgqa/tsse-tool-capture/v0.1",'
                '"schema":"cgqa/tsse-tool-capture/v0.1"}'
            )
            capture.write_text(duplicate, encoding="utf-8")
            profile.write_text(
                '{"schema":"cgqa/tsse-tool-profile/v0.1",'
                '"schema":"cgqa/tsse-tool-profile/v0.1"}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ToolCaptureError, "duplicate JSON object key"):
                load_tool_capture(capture)
            with self.assertRaisesRegex(ToolCaptureError, "duplicate JSON object key"):
                load_tool_profile(profile)

    def test_semantic_hashes_ignore_json_object_key_order(self) -> None:
        capture = _load(FOUNDRY_CAPTURE)
        profile = _load(FOUNDRY_PROFILE)
        reordered = dict(reversed(list(copy.deepcopy(capture).items())))
        values = reordered["observations"][0]["state"]["values"]
        reordered["observations"][0]["state"]["values"] = dict(
            reversed(list(values.items()))
        )

        first = _adapt(capture, profile)
        second = _adapt(reordered, profile)

        self.assertEqual(first["captureHash"], second["captureHash"])
        self.assertEqual(first["normalizationHash"], second["normalizationHash"])
        self.assertEqual(first["resultHash"], second["resultHash"])

    def test_slither_failure_remains_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            artifact = copy_root / "artifacts" / "slither-result.json"
            artifact.write_text(
                json.dumps({"success": False, "error": "compile failed", "results": None}),
                encoding="utf-8",
            )
            capture_path = copy_root / "slither-capture.json"
            capture = _load(capture_path)
            capture["toolArtifacts"][0]["digest"] = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
            capture_path.write_text(json.dumps(capture), encoding="utf-8")

            result = adapt_tool_capture_file(
                capture_path,
                copy_root / "slither-profile.json",
            )

        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["normalizationStatus"], "inconclusive")
        self.assertEqual(result["staticSeeds"], [])

    def test_slither_allows_optional_detector_section_and_other_result_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            artifact = copy_root / "artifacts" / "slither-result.json"
            artifact.write_text(
                json.dumps(
                    {
                        "success": True,
                        "error": None,
                        "results": {"printers": [], "compilations": []},
                    }
                ),
                encoding="utf-8",
            )
            capture_path = copy_root / "slither-capture.json"
            capture = _load(capture_path)
            capture["toolArtifacts"][0]["digest"] = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
            capture_path.write_text(json.dumps(capture), encoding="utf-8")

            result = adapt_tool_capture_file(
                capture_path,
                copy_root / "slither-profile.json",
            )

        self.assertEqual(result["normalizationStatus"], "complete")
        self.assertEqual(result["staticSeeds"], [])

    def test_slither_locations_must_belong_to_verified_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            artifact = copy_root / "artifacts" / "slither-result.json"
            output = _load(artifact)
            output["results"]["detectors"][0]["elements"][0]["source_mapping"][
                "filename_relative"
            ] = "artifacts/Other.sol"
            artifact.write_text(json.dumps(output), encoding="utf-8")
            capture_path = copy_root / "slither-capture.json"
            capture = _load(capture_path)
            capture["toolArtifacts"][0]["digest"] = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
            capture_path.write_text(json.dumps(capture), encoding="utf-8")

            with self.assertRaisesRegex(ToolCaptureError, "outside the verified subject"):
                adapt_tool_capture_file(
                    capture_path,
                    copy_root / "slither-profile.json",
                )

    def test_slither_seed_identity_retains_distinct_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary) / "capture"
            shutil.copytree(FIXTURE_ROOT, copy_root)
            artifact = copy_root / "artifacts" / "slither-result.json"
            output = _load(artifact)
            second = copy.deepcopy(output["results"]["detectors"][0])
            second["description"] = "A distinct path at the same source location."
            output["results"]["detectors"].append(second)
            artifact.write_text(json.dumps(output), encoding="utf-8")
            capture_path = copy_root / "slither-capture.json"
            capture = _load(capture_path)
            capture["toolArtifacts"][0]["digest"] = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
            capture_path.write_text(json.dumps(capture), encoding="utf-8")

            result = adapt_tool_capture_file(
                capture_path,
                copy_root / "slither-profile.json",
            )

        self.assertEqual(len(result["staticSeeds"]), 2)


if __name__ == "__main__":
    unittest.main()
