from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.liminalqa_interop import (
    LiminalQaInteropError,
    LIMINAL_CANDIDATE_PROFILE,
    LIMINAL_CANDIDATE_SCHEMA,
    LIMINAL_CANDIDATE_SCHEMA_SHA256,
    build_liminalqa_evidence_export,
    canonical_json_bytes,
    import_liminalqa_candidates,
    sha256_hex,
    validate_liminalqa_candidate_export,
    validate_liminalqa_evidence_export,
)
from contractgraph_qa.liminalqa_interop_cli import export_main, import_candidates_main
from contractgraph_qa.finding import load_json_object

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "a10862f40e2d4d59c122a61119fbb3c9c1ff6cab"


class LiminalQaInteropTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "manifests" / "examples" / "engagement-fixture.json"
        self.result_path = ROOT / "results" / "examples" / "CGQA-E-001.engagement-result.json"
        self.manifest = load_json_object(self.manifest_path, "manifest")
        self.result = load_json_object(self.result_path, "result")

    def evidence(self) -> dict[str, object]:
        return build_liminalqa_evidence_export(
            self.manifest,
            self.result,
            repository="https://github.com/safal207/ContractGraph-QA",
            commit_sha=COMMIT,
            adapter_version="1.3.0",
            trace_id="trace-CGQA-E-001",
            operation_id="bounded-search-CGQA-E-001",
            attempt_id="attempt-001",
            valid_at="2026-09-03T10:00:00Z",
            observed_at="2026-09-03T10:01:00Z",
            recorded_at="2026-09-03T10:02:00Z",
            causal_parents=["manifest-engagement-fixture"],
        )

    def candidates(self) -> dict[str, object]:
        evidence = self.evidence()
        return {
            "schema": "org.liminalqa.cgqa-candidates.v0.1",
            "profile": "org.liminalqa.non-authoritative-candidate-seeds.v0.1",
            "exportId": "liminal-candidates-example-001",
            "producer": {"name": "liminalqa", "version": "0.1.0"},
            "sourceEvidence": {
                "schema": evidence["schema"],
                "exportId": evidence["exportId"],
                "sha256": sha256_hex(canonical_json_bytes(evidence)),
            },
            "subject": evidence["subject"],
            "identity": evidence["identity"],
            "derivedAt": "2026-09-03T10:03:00Z",
            "authority": {
                "classification": "non_authoritative_seed",
                "mayAuthorizeAction": False,
                "requiresCgqaVerification": True,
            },
            "candidates": [
                {
                    "candidateId": "candidate-terminal-state-bound",
                    "invariantId": "terminal-state-bound",
                    "sourceStatus": "violated",
                    "kind": "replay_regression",
                    "priority": "medium",
                    "reason": "Replay the observed shortest failing path.",
                    "requiredChecks": [
                        "exact_subject",
                        "independent_cgqa_replay",
                        "failing_path_integrity",
                    ],
                },
                {
                    "candidateId": "candidate-budget-sensitive-branch",
                    "invariantId": "budget-sensitive-branch",
                    "sourceStatus": "inconclusive",
                    "kind": "verification_debt",
                    "priority": "low",
                    "reason": "Increase or refine the declared search bound.",
                    "requiredChecks": [
                        "exact_subject",
                        "reviewed_bound_change",
                        "independent_cgqa_replay",
                    ],
                },
            ],
            "causalParents": [evidence["exportId"]],
            "limitations": [
                "Candidates are hypotheses and have not been independently verified by ContractGraph-QA."
            ],
            "verificationDebt": [
                {
                    "invariantId": "budget-sensitive-branch",
                    "reason": "The source evidence was inconclusive.",
                }
            ],
        }

    def test_export_is_deterministic_and_preserves_all_bounded_statuses(self) -> None:
        first = self.evidence()
        second = self.evidence()
        self.assertEqual(first, second)
        self.assertEqual(
            [check["status"] for check in first["checks"]],
            ["violated", "not_found_within_bound", "inconclusive"],
        )
        self.assertEqual(first["assessment"]["continuityVerdict"], "not_computed")
        self.assertIs(first["authority"]["mayAuthorizeAction"], False)
        self.assertEqual(first["subject"]["commitSha"], COMMIT)

    def test_export_rejects_temporal_inversion(self) -> None:
        with self.assertRaisesRegex(LiminalQaInteropError, "validAt <= observedAt <= recordedAt"):
            build_liminalqa_evidence_export(
                self.manifest,
                self.result,
                repository="repo",
                commit_sha=COMMIT,
                adapter_version="1.3.0",
                trace_id="trace-1",
                operation_id="operation-1",
                attempt_id="attempt-1",
                valid_at="2026-09-03T10:02:00Z",
                observed_at="2026-09-03T10:01:00Z",
                recorded_at="2026-09-03T10:03:00Z",
            )

    def test_evidence_validator_rejects_status_count_tampering(self) -> None:
        tampered = copy.deepcopy(self.evidence())
        tampered["assessment"]["counts"]["violated"] = 0
        with self.assertRaisesRegex(LiminalQaInteropError, "counts does not match"):
            validate_liminalqa_evidence_export(tampered)

    def test_evidence_validator_rejects_duplicate_debt_and_unknown_severity(self) -> None:
        duplicate_debt = copy.deepcopy(self.evidence())
        duplicate_debt["verificationDebt"].append(copy.deepcopy(duplicate_debt["verificationDebt"][0]))
        with self.assertRaisesRegex(LiminalQaInteropError, "duplicate invariants"):
            validate_liminalqa_evidence_export(duplicate_debt)

        unknown_severity = copy.deepcopy(self.evidence())
        unknown_severity["checks"][0]["severity"] = "urgent"
        with self.assertRaisesRegex(LiminalQaInteropError, "severity is unsupported"):
            validate_liminalqa_evidence_export(unknown_severity)

    def test_candidate_import_stays_non_authoritative(self) -> None:
        candidates = self.candidates()
        validate_liminalqa_candidate_export(candidates)
        source = canonical_json_bytes(candidates) + b"\n"
        receipt = import_liminalqa_candidates(candidates, source_bytes=source)
        self.assertEqual(receipt["acceptedAs"], "non_authoritative_seed")
        self.assertIs(receipt["mayAuthorizeAction"], False)
        self.assertIs(receipt["requiresFreshCgqaVerification"], True)
        self.assertEqual(receipt["candidateCount"], 2)
        self.assertEqual(receipt["source"]["sha256"], sha256_hex(source))

    def test_candidate_import_rejects_authorization_escalation(self) -> None:
        tampered = copy.deepcopy(self.candidates())
        tampered["authority"]["mayAuthorizeAction"] = True
        with self.assertRaisesRegex(LiminalQaInteropError, "mayAuthorizeAction must be false"):
            import_liminalqa_candidates(tampered)

    def test_candidate_import_rejects_ambiguous_provenance_and_weak_checks(self) -> None:
        candidates = self.candidates()
        with self.assertRaisesRegex(LiminalQaInteropError, "does not encode"):
            import_liminalqa_candidates(candidates, source_bytes=b'{"different":true}\n')

        weak = copy.deepcopy(candidates)
        weak["candidates"][0]["requiredChecks"].remove("independent_cgqa_replay")
        with self.assertRaisesRegex(LiminalQaInteropError, "mandatory fresh-verification"):
            import_liminalqa_candidates(weak)

        duplicate_invariant = copy.deepcopy(candidates)
        duplicate_invariant["candidates"][1]["invariantId"] = duplicate_invariant["candidates"][0]["invariantId"]
        with self.assertRaisesRegex(LiminalQaInteropError, "duplicate candidate invariant"):
            import_liminalqa_candidates(duplicate_invariant)

    def test_liminalqa_golden_vector_and_exact_schema_pin(self) -> None:
        fixture_path = ROOT / "tools" / "tests" / "fixtures" / "liminalqa-cgqa-candidates-v0.1.json"
        raw = fixture_path.read_bytes()
        fixture = json.loads(raw)
        validate_liminalqa_candidate_export(fixture)
        receipt = import_liminalqa_candidates(fixture, source_bytes=raw)
        self.assertEqual(receipt["candidateCount"], 2)
        self.assertIs(receipt["mayAuthorizeAction"], False)

        pin_path = (
            ROOT
            / "contractgraph_qa"
            / "schemas"
            / "liminalqa-cgqa-candidates-v0.1.external-contract.json"
        )
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
        self.assertEqual(pin["producerSchema"], LIMINAL_CANDIDATE_SCHEMA)
        self.assertEqual(pin["producerProfile"], LIMINAL_CANDIDATE_PROFILE)
        self.assertEqual(pin["schemaSha256"], LIMINAL_CANDIDATE_SCHEMA_SHA256)
        self.assertEqual(pin["producerCommit"], "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3")

    def test_cli_round_trip_writes_file_first_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "cgqa-evidence.json"
            receipt_path = root / "cgqa-seed-receipt.json"
            code = export_main(
                [
                    "--manifest", str(self.manifest_path),
                    "--result", str(self.result_path),
                    "--repository", "https://github.com/safal207/ContractGraph-QA",
                    "--commit-sha", COMMIT,
                    "--adapter-version", "1.3.0",
                    "--trace-id", "trace-CGQA-E-001",
                    "--operation-id", "bounded-search-CGQA-E-001",
                    "--attempt-id", "attempt-001",
                    "--valid-at", "2026-09-03T10:00:00Z",
                    "--observed-at", "2026-09-03T10:01:00Z",
                    "--recorded-at", "2026-09-03T10:02:00Z",
                    "--out", str(evidence_path),
                ]
            )
            self.assertEqual(code, 0)
            validate_liminalqa_evidence_export(json.loads(evidence_path.read_text(encoding="utf-8")))

            candidate_path = root / "liminal-candidates.json"
            candidate_path.write_bytes(canonical_json_bytes(self.candidates()) + b"\n")
            code = import_candidates_main(
                ["--input", str(candidate_path), "--out", str(receipt_path)]
            )
            self.assertEqual(code, 0)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["acceptedAs"], "non_authoritative_seed")


if __name__ == "__main__":
    unittest.main()
