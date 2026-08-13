from __future__ import annotations

import unittest

from contractgraph_qa.provider_decision_evidence import canonical_json_bytes


class CanonicalJsonTypeTest(unittest.TestCase):
    def test_boolean_false_is_distinct_from_numeric_zero(self) -> None:
        self.assertNotEqual(
            canonical_json_bytes({"value": False}),
            canonical_json_bytes({"value": 0}),
        )


if __name__ == "__main__":
    unittest.main()
