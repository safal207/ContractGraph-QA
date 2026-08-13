from __future__ import annotations

import unittest

from contractgraph_qa.provider_decision_evidence import (
    ProviderDecisionEvidenceError,
    canonical_json_bytes,
    verify_provider_decision_evidence,
)


class CanonicalJsonTypeTest(unittest.TestCase):
    def test_monetary_action_boolean_false_is_distinct_from_numeric_zero(self) -> None:
        self.assertNotEqual(
            canonical_json_bytes({"monetaryActionAllowed": False}),
            canonical_json_bytes({"monetaryActionAllowed": 0}),
        )

    def test_expected_pack_digest_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ProviderDecisionEvidenceError):
            verify_provider_decision_evidence(
                {"schema": "example"},
                expected_pack_sha256="0" * 64,
            )


if __name__ == "__main__":
    unittest.main()
