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

from contractgraph_qa.cli import EXIT_OK, main as cli_main  # noqa: E402
from contractgraph_qa.external_investigation import (  # noqa: E402
    AUTHORIZATION_BASES,
    AUTHORIZATION_STATUSES,
    CAPABILITY_IDS,
    CAPABILITY_STATUSES,
    DEBT_STATUSES,
    EVIDENCE_KINDS,
    EVIDENCE_STATES,
    EXECUTION_STATUSES,
    FINDING_STATUSES,
    IMPACT_CLASSES,
    INVARIANT_FAMILIES,
    REMEDIATION_STATUSES,
    SCHEMA,
    TOP_LEVEL_KEYS,
    ExternalInvestigationError,
    evaluate_external_investigation,
    load_external_investigation,
    validate_external_investigation,
)

SCENARIO = ROOT / "scenarios" / "external-investigation-stellar-dice-duel.json"
SCHEMA_PATH = ROOT / "graph" / "schema" / "external-investigation.schema.json"


def _document() -> dict[str, object]:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class ExternalInvestigationTest(unittest.TestCase):
    def test_stellar_record_preserves_blocked_workflow_and_not_run_execution(self) -> None:
        result = evaluate_external_investigation(load_external_investigation(SCENARIO))

        self.assertEqual(result["findingStatus"], "COUNTEREXAMPLE_FOUND")
        self.assertEqual(result["workflowStatus"], "BLOCKED")
        self.assertEqual(result["contractGraphQaStatus"], "NOT_RUN")
        self.assertEqual(result["nativeRegressionStatus"], "NOT_RUN")
        self.assertFalse(result["boundedRemediationVerified"])
        self.assertFalse(result["securityVerdictAuthorized"])
        self.assertEqual(result["openBlockerIds"], ["GAME-HUB-NEUTRAL-SETTLEMENT"])
        self.assertIn("DEBT-CGQA-RUN", result["unresolvedRequiredDebtIds"])
        self.assertEqual(sum(result["capabilityStatusCounts"].values()), len(CAPABILITY_IDS))
        self.assertEqual(result["evidenceStateCounts"]["REPORTED_NOT_ARCHIVED"], 3)

    def test_record_hash_is_deterministic(self) -> None:
        first = evaluate_external_investigation(copy.deepcopy(_document()))
        second = evaluate_external_investigation(copy.deepcopy(_document()))
        self.assertEqual(first["recordHash"], second["recordHash"])
        self.assertEqual(first["subjectHash"], second["subjectHash"])

    def test_complete_capability_matrix_is_required(self) -> None:
        record = _document()
        capabilities = record["capabilityMatrix"]
        assert isinstance(capabilities, list)
        capabilities.pop()
        with self.assertRaisesRegex(ExternalInvestigationError, "complete AGENTS.md"):
            validate_external_investigation(record)

    def test_duplicate_capability_is_rejected(self) -> None:
        record = _document()
        capabilities = record["capabilityMatrix"]
        assert isinstance(capabilities, list)
        capabilities.append(copy.deepcopy(capabilities[0]))
        with self.assertRaisesRegex(ExternalInvestigationError, "duplicate capability id"):
            validate_external_investigation(record)

    def test_verified_remediation_cannot_bypass_not_run_boundaries(self) -> None:
        record = _document()
        finding = record["finding"]
        assert isinstance(finding, dict)
        finding["remediationStatus"] = "VERIFIED_WITHIN_BOUND"
        with self.assertRaisesRegex(ExternalInvestigationError, "requires native and ContractGraph-QA"):
            validate_external_investigation(record)

    def test_bounded_no_finding_requires_real_execution(self) -> None:
        record = _document()
        finding = record["finding"]
        assert isinstance(finding, dict)
        finding["status"] = "NO_COUNTEREXAMPLE_WITHIN_BOUND"
        finding["rootCause"] = None
        with self.assertRaisesRegex(ExternalInvestigationError, "executed passing search"):
            validate_external_investigation(record)

    def test_archived_evidence_requires_digest(self) -> None:
        record = _document()
        evidence = record["evidence"]
        assert isinstance(evidence, list)
        item = evidence[1]
        assert isinstance(item, dict)
        item["state"] = "ARCHIVED_UNVERIFIED"
        with self.assertRaisesRegex(ExternalInvestigationError, "required for archived evidence"):
            validate_external_investigation(record)

    def test_reported_not_archived_evidence_rejects_digest(self) -> None:
        record = _document()
        evidence = record["evidence"]
        assert isinstance(evidence, list)
        item = evidence[1]
        assert isinstance(item, dict)
        item["sha256"] = "a" * 64
        with self.assertRaisesRegex(ExternalInvestigationError, "must be null"):
            validate_external_investigation(record)

    def test_unknown_finding_evidence_id_is_rejected(self) -> None:
        record = _document()
        finding = record["finding"]
        assert isinstance(finding, dict)
        evidence_ids = finding["evidenceIds"]
        assert isinstance(evidence_ids, list)
        evidence_ids.append("MISSING-001")
        with self.assertRaisesRegex(ExternalInvestigationError, "unknown evidence ids"):
            validate_external_investigation(record)

    def test_measured_impact_requires_evidence(self) -> None:
        record = _document()
        impact = record["impact"]
        assert isinstance(impact, dict)
        impact["classification"] = "MEASURED"
        impact["evidenceIds"] = []
        with self.assertRaisesRegex(ExternalInvestigationError, "MEASURED impact"):
            validate_external_investigation(record)

    def test_measured_impact_rejects_non_measurement_evidence(self) -> None:
        record = _document()
        impact = record["impact"]
        assert isinstance(impact, dict)
        impact["classification"] = "MEASURED"
        with self.assertRaisesRegex(ExternalInvestigationError, "VERIFIED IMPACT_MEASUREMENT"):
            validate_external_investigation(record)

    def test_blocked_remediation_requires_an_open_blocker(self) -> None:
        record = _document()
        record["blockers"] = []
        with self.assertRaisesRegex(ExternalInvestigationError, "requires an OPEN blocker"):
            validate_external_investigation(record)

    def test_native_capability_must_match_execution_state(self) -> None:
        record = _document()
        capabilities = record["capabilityMatrix"]
        assert isinstance(capabilities, list)
        native = next(
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("id") == "native_regression"
        )
        native["status"] = "RUN"
        with self.assertRaisesRegex(ExternalInvestigationError, "must match native execution"):
            validate_external_investigation(record)

    def test_incomplete_execution_cannot_become_balanced_when_debt_is_omitted(self) -> None:
        record = _document()
        finding = record["finding"]
        assert isinstance(finding, dict)
        finding["remediationStatus"] = "PROPOSED"
        record["blockers"] = []
        record["verificationDebt"] = []
        result = evaluate_external_investigation(record)
        self.assertEqual(result["workflowStatus"], "INDETERMINATE")
        self.assertEqual(
            result["workflowReasonCodes"],
            ["EXECUTION_OR_REMEDIATION_INCOMPLETE"],
        )

    def test_failed_native_execution_is_unstable(self) -> None:
        record = _document()
        finding = record["finding"]
        assert isinstance(finding, dict)
        finding["remediationStatus"] = "PROPOSED"
        record["blockers"] = []
        execution = record["execution"]
        assert isinstance(execution, dict)
        native_execution = execution["nativeRegression"]
        assert isinstance(native_execution, dict)
        native_execution.update(
            {
                "status": "RUN_FAIL",
                "reference": "artifacts/native-red.json",
                "evidenceSha256": "a" * 64,
            }
        )
        capabilities = record["capabilityMatrix"]
        assert isinstance(capabilities, list)
        native_capability = next(
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("id") == "native_regression"
        )
        native_capability["status"] = "RUN"
        result = evaluate_external_investigation(record)
        self.assertEqual(result["workflowStatus"], "UNSTABLE")
        self.assertEqual(result["workflowReasonCodes"], ["NATIVE_OR_CGQA_EXECUTION_FAILED"])

    def test_unconfirmed_authorization_blocks_otherwise_valid_record(self) -> None:
        record = _document()
        authorization = record["authorization"]
        assert isinstance(authorization, dict)
        authorization["status"] = "UNCONFIRMED"
        result = evaluate_external_investigation(record)
        self.assertEqual(result["workflowStatus"], "BLOCKED")
        self.assertEqual(result["workflowReasonCodes"], ["AUTHORIZATION_UNCONFIRMED"])

    def test_public_cli_returns_valid_record_even_when_workflow_is_blocked(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["external-investigation", "--record", str(SCENARIO)])
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["workflowStatus"], "BLOCKED")
        self.assertFalse(result["securityVerdictAuthorized"])

    def test_checked_in_schema_tracks_runtime_contract_enums(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema"]["const"], SCHEMA)
        self.assertEqual(set(schema["properties"]), TOP_LEVEL_KEYS)
        self.assertEqual(set(schema["required"]), TOP_LEVEL_KEYS)
        self.assertEqual(
            set(schema["$defs"]["capability"]["properties"]["id"]["enum"]),
            set(CAPABILITY_IDS),
        )
        self.assertEqual(
            set(schema["$defs"]["capability"]["properties"]["status"]["enum"]),
            CAPABILITY_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["authorization"]["properties"]["status"]["enum"]),
            AUTHORIZATION_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["authorization"]["properties"]["basis"]["enum"]),
            AUTHORIZATION_BASES,
        )
        self.assertEqual(
            set(schema["$defs"]["property"]["properties"]["invariantFamily"]["enum"]),
            INVARIANT_FAMILIES,
        )
        self.assertEqual(
            set(schema["$defs"]["evidence"]["properties"]["kind"]["enum"]),
            EVIDENCE_KINDS,
        )
        self.assertEqual(
            set(schema["$defs"]["evidence"]["properties"]["state"]["enum"]),
            EVIDENCE_STATES,
        )
        self.assertEqual(
            set(schema["$defs"]["nativeExecution"]["properties"]["status"]["enum"]),
            EXECUTION_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["finding"]["properties"]["status"]["enum"]),
            FINDING_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["finding"]["properties"]["remediationStatus"]["enum"]),
            REMEDIATION_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["debt"]["properties"]["status"]["enum"]),
            DEBT_STATUSES,
        )
        self.assertEqual(
            set(schema["$defs"]["impact"]["properties"]["classification"]["enum"]),
            IMPACT_CLASSES,
        )


if __name__ == "__main__":
    unittest.main()
