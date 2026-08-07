import unittest

from tools.validate_fork_scope import ForkScope, validate_scope


class ValidateForkScopeTests(unittest.TestCase):
    def valid_scope(self, **overrides):
        values = {
            "scope_id": "client-scope-001",
            "authorization_reference": "signed-sow-2026-08-07",
            "chain_id": 1,
            "block_number": 20_000_000,
            "target": "0x1234567890abcdef1234567890abcdef12345678",
            "confirmed": "YES",
        }
        values.update(overrides)
        return ForkScope(**values)

    def test_valid_scope_is_normalized(self):
        result = validate_scope(self.valid_scope(target="0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"))
        self.assertEqual(result["target"], "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd")
        self.assertNotIn("confirmed", result)

    def test_confirmation_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            validate_scope(self.valid_scope(confirmed="NO"))

    def test_authorization_reference_is_required(self):
        with self.assertRaisesRegex(ValueError, "authorization reference"):
            validate_scope(self.valid_scope(authorization_reference=""))

    def test_zero_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "zero address"):
            validate_scope(self.valid_scope(target="0x" + "0" * 40))

    def test_bad_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "20-byte"):
            validate_scope(self.valid_scope(target="0x1234"))

    def test_chain_and_block_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "chain id"):
            validate_scope(self.valid_scope(chain_id=0))
        with self.assertRaisesRegex(ValueError, "block number"):
            validate_scope(self.valid_scope(block_number=0))


if __name__ == "__main__":
    unittest.main()
