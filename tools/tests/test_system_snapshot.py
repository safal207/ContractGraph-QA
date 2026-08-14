from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from contractgraph_qa.fcrp_v02 import evaluate_fcrp_v02_case
from contractgraph_qa.system_snapshot import SystemSnapshotError, validate_system_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "governance" / "neo-rezonans-system-snapshot.v0.1.json"
CASE_PATH = ROOT / "benchmarks" / "fcrp-v0.2" / "FCRP-SYSTEM-001-neo-rezonans.json"
REPO_REF = re.compile(r"^(?P<repo>[^@]+)@(?P<sha>[0-9a-f]{40})$")


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


class NeoRezonansSystemSnapshotTest(unittest.TestCase):
    def test_canonical_snapshot_passes_and_is_non_authorizing(self) -> None:
        snapshot = load_snapshot()
        result = validate_system_snapshot(snapshot)

        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["snapshotId"], "NEO-REZONANS-SYSTEM-001")
        self.assertEqual(result["layerCount"], 8)
        self.assertEqual(result["repositoryCount"], 7)
        self.assertEqual(result["edgeCount"], 8)
        self.assertEqual(result["authorityTransferEdges"], 1)
        self.assertEqual(result["feedbackEdges"], 1)
        self.assertEqual(result["hostRepository"], "safal207/ContractGraph-QA")
        self.assertEqual(
            result["hostBaseCommit"],
            "505041cae23d0527f7d567e1a6bd6d1952dc4960",
        )
        self.assertTrue(result["snapshotDigest"].startswith("sha256:"))
        self.assertFalse(snapshot["authorityBoundary"]["snapshotGrantsMutationAuthority"])
        self.assertFalse(snapshot["authorityBoundary"]["evidenceMayGrantAuthority"])

    def test_fcrp_system_case_passes_without_mutation_authority(self) -> None:
        case = load_case()
        result = evaluate_fcrp_v02_case(case)

        self.assertEqual(result["caseId"], "FCRP-SYSTEM-001")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["primaryTimeDomain"], "REPOSITORY_HISTORY")
        self.assertTrue(result["causalAdvanceRequired"])
        self.assertEqual(result["simulationStatus"], "PASS")
        self.assertFalse(result["mutationAuthorized"])
        self.assertEqual(result["upwardVerification"], "NOT_REQUIRED")
        self.assertTrue(result["causalPropagationStopped"])
        self.assertTrue(result["stopConditionsSatisfied"])
        self.assertEqual(result["decision"], case["expectedProtocolDecision"])

    def test_case_repository_evidence_matches_snapshot_repository_identities(self) -> None:
        snapshot = load_snapshot()
        case = load_case()

        snapshot_refs = {
            (layer["repository"], layer["canonicalCommit"])
            for layer in snapshot["layers"]
        }
        case_refs: set[tuple[str, str]] = set()
        for evidence in case["evidence"]:
            match = REPO_REF.fullmatch(evidence["ref"])
            if match:
                case_refs.add((match.group("repo"), match.group("sha")))

        self.assertEqual(case_refs, snapshot_refs)

    def test_branch_only_layer_cannot_be_default_system_dependency(self) -> None:
        snapshot = load_snapshot()
        snapshot["layers"][0]["status"] = "PROPOSED"

        with self.assertRaisesRegex(SystemSnapshotError, "must be CANONICAL"):
            validate_system_snapshot(snapshot)

    def test_one_repository_cannot_be_two_versions_in_one_snapshot(self) -> None:
        snapshot = load_snapshot()
        snapshot["layers"][5]["repository"] = snapshot["layers"][1]["repository"]

        with self.assertRaisesRegex(SystemSnapshotError, "cannot be bound to multiple commits"):
            validate_system_snapshot(snapshot)

    def test_non_authority_edge_must_forbid_execution_authority(self) -> None:
        snapshot = load_snapshot()
        edge = snapshot["edges"][0]
        edge["forbiddenInferences"].remove("execution_authority")

        with self.assertRaisesRegex(SystemSnapshotError, "explicitly forbid execution_authority"):
            validate_system_snapshot(snapshot)

    def test_non_authority_edge_cannot_carry_authorization_reference(self) -> None:
        snapshot = load_snapshot()
        snapshot["edges"][0]["allowedFacts"].append("authorization_ref")

        with self.assertRaisesRegex(SystemSnapshotError, "may not transfer authorization_ref"):
            validate_system_snapshot(snapshot)

    def test_authority_edge_must_transfer_explicit_reference(self) -> None:
        snapshot = load_snapshot()
        edge = next(item for item in snapshot["edges"] if item["authorityMode"] == "EXPLICIT_CONTRACT_ONLY")
        edge["allowedFacts"].remove("authorization_ref")

        with self.assertRaisesRegex(SystemSnapshotError, "authorization_ref explicitly"):
            validate_system_snapshot(snapshot)

    def test_explicit_authority_cannot_move_to_the_wrong_system_roles(self) -> None:
        snapshot = load_snapshot()
        original = next(item for item in snapshot["edges"] if item["authorityMode"] == "EXPLICIT_CONTRACT_ONLY")
        original["authorityMode"] = "NONE"
        original["allowedFacts"].remove("authorization_ref")
        original["forbiddenInferences"].append("execution_authority")

        wrong = snapshot["edges"][0]
        wrong["authorityMode"] = "EXPLICIT_CONTRACT_ONLY"
        wrong["allowedFacts"].append("authorization_ref")
        wrong["forbiddenInferences"].append("evidence_as_authority")

        with self.assertRaisesRegex(SystemSnapshotError, "explicit authority may flow only"):
            validate_system_snapshot(snapshot)

    def test_feedback_flag_cannot_move_to_another_edge(self) -> None:
        snapshot = load_snapshot()
        feedback = next(item for item in snapshot["edges"] if item["feedback"])
        feedback["feedback"] = False
        snapshot["edges"][0]["feedback"] = True

        with self.assertRaisesRegex(SystemSnapshotError, "feedback may close only"):
            validate_system_snapshot(snapshot)

    def test_host_capability_base_cannot_drift_inside_self_hosted_snapshot(self) -> None:
        snapshot = load_snapshot()
        snapshot["layers"][2]["canonicalCommit"] = "0" * 40

        with self.assertRaisesRegex(SystemSnapshotError, "exact pre-acceptance host base"):
            validate_system_snapshot(snapshot)

    def test_host_acceptance_mode_prevents_self_referential_commit_contract(self) -> None:
        snapshot = load_snapshot()
        snapshot["snapshotPolicy"]["hostAcceptanceMode"] = "PIN_FUTURE_MERGE_SHA"

        with self.assertRaisesRegex(SystemSnapshotError, "BASE_PLUS_GOVERNANCE_SNAPSHOT"):
            validate_system_snapshot(snapshot)

    def test_snapshot_itself_never_grants_mutation_authority(self) -> None:
        snapshot = load_snapshot()
        snapshot["authorityBoundary"]["snapshotGrantsMutationAuthority"] = True

        with self.assertRaisesRegex(SystemSnapshotError, "may not itself grant mutation authority"):
            validate_system_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
