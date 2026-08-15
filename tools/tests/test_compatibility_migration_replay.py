from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "compatibility_migration_replay.py"
SPEC = importlib.util.spec_from_file_location("compatibility_migration_replay", MODULE_PATH)
assert SPEC and SPEC.loader
compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compat)

MATRIX = Path(__file__).resolve().parents[2] / "benchmarks/global-p1-8/compatibility-migration.v0.1.json"


class CompatibilityMigrationReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.source = deepcopy(self.matrix["source_payload"])

    def case(self, case_id: str) -> dict:
        return next(item for item in self.matrix["cases"] if item["id"] == case_id)

    def test_current_exact_contract_is_accepted(self) -> None:
        result = compat.evaluate_case(self.case("current-exact"), self.source)
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertEqual(result["reason_code"], "EXACT_CURRENT_REVISION")
        self.assertEqual(result["recovery_status"], "NOT_REQUIRED")

    def test_proofpath_new_revision_is_rejected(self) -> None:
        result = compat.evaluate_case(self.case("proofpath-v0-2-candidate"), self.source)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "UNSUPPORTED_SCHEMA_REVISION")
        self.assertEqual(result["recovery_status"], "ORIGINAL_PRESERVED")

    def test_liminaldb_new_protocol_is_rejected(self) -> None:
        result = compat.evaluate_case(self.case("liminaldb-1-1-candidate"), self.source)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "UNSUPPORTED_SCHEMA_REVISION")

    def test_rinse_new_receipt_is_rejected(self) -> None:
        result = compat.evaluate_case(self.case("rinse-v0-2-candidate"), self.source)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "UNSUPPORTED_SCHEMA_REVISION")

    def test_route_reorder_is_rejected(self) -> None:
        result = compat.evaluate_case(self.case("route-reorder-candidate"), self.source)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "ROUTE_ORDER_DRIFT")

    def test_authority_escalation_is_rejected(self) -> None:
        result = compat.evaluate_case(self.case("authority-escalation-candidate"), self.source)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "AUTHORITY_ESCALATION")

    def test_recovery_is_digest_stable(self) -> None:
        result = compat.evaluate_case(self.case("proofpath-v0-2-candidate"), self.source)
        self.assertEqual(result["source_payload_digest"], result["recovered_payload_digest"])
        self.assertFalse(result["write_performed"])

    def test_receipt_tamper_is_rejected(self) -> None:
        receipt = {
            "schema": compat.RECEIPT_SCHEMA,
            "authority": {
                "source_mutation_authorized": False,
                "execution_authorized": False,
                "external_effects_authorized": False,
            },
        }
        receipt["receipt_digest"] = "sha256:" + compat.sha256_object(receipt)
        compat.verify_receipt(receipt)
        receipt["policy"] = "ATTACKER_POLICY"
        with self.assertRaisesRegex(compat.CompatibilityReplayError, "digest mismatch"):
            compat.verify_receipt(receipt)

    def test_duplicate_subject_component_is_rejected(self) -> None:
        records = [
            {"component": "rinse", "repository": "one", "revision": "a", "path": "p", "git_blob": "b", "sha256": "c"},
            {"component": "rinse", "repository": "two", "revision": "d", "path": "q", "git_blob": "e", "sha256": "f"},
        ]
        with self.assertRaisesRegex(compat.CompatibilityReplayError, "duplicate component"):
            compat.build_subject_fingerprint(records)


if __name__ == "__main__":
    unittest.main()
