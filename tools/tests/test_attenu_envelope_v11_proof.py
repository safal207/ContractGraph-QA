"""Static and local negative controls for the independent envelope-v1.1 scorer."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = (
    _ROOT
    / "proofs"
    / "attenu-guard-v0.13.0-envelope-independent"
    / "independent_envelope_verifier.py"
)


def _load_module():
    name = "_cgqa_test_independent_envelope_v11"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def _tiny_ledger() -> list[dict]:
    entries: list[dict] = []
    previous = MOD.BASE.GENESIS
    for seq, event, node in (
        (0, "root", "vectors:n0"),
        (1, "spawn", "vectors:n1"),
        (2, "allow", "vectors:n0"),
    ):
        entry = {
            "v": 2,
            "c14n": "JCS",
            "seq": seq,
            "ts": seq,
            "event": event,
            "prev_hash": previous,
            "chain_id": "vectors",
            "node": node,
        }
        if event == "allow":
            entry["call_id"] = "1" * 32
        payload = dict(entry)
        entry["hash"] = hashlib.sha256(
            previous.encode("ascii") + MOD.BASE.jcs_bytes(payload)
        ).hexdigest()
        previous = entry["hash"]
        entries.append(entry)
    return entries


def _signed_bundle(
    *,
    result: str = "matched",
) -> tuple[dict, list[dict], Ed25519PrivateKey]:
    entries = _tiny_ledger()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        Encoding.Raw,
        PublicFormat.Raw,
    )

    envelope = {
        "v": 1,
        "typ": MOD.ENVELOPE_TYP,
        "subject": {
            "chain_id": "vectors",
            "node": "vectors:n1",
            "seq": 1,
            "entry_hash": MOD._recomputed_hashes(entries)[1],
            "event": "spawn",
        },
        "observed": {
            "result": result,
            "at": "2026-09-01T11:00:00Z",
            "method": "sidecar:test",
        },
        "witness": {"kid": "test-witness", "alg": MOD.ENVELOPE_ALG},
    }
    envelope["sig"] = private_key.sign(
        MOD.BASE.jcs_bytes(envelope)
    ).hex()

    bundle = {
        "v": 2,
        "c14n": "JCS",
        "chain_id": "vectors",
        "entries": entries,
        "envelopes": [envelope],
    }
    witness_keys = [
        {
            "kid": "test-witness",
            "alg": MOD.ENVELOPE_ALG,
            "public_key_hex": public_key.hex(),
        }
    ]
    return bundle, witness_keys, private_key


class TestIndependentEnvelopeV11(unittest.TestCase):
    def test_exact_subject_and_closed_vocabularies_are_pinned(self):
        self.assertEqual(MOD.VECTOR_CONTRACT, "envelope_vectors_v1")
        self.assertEqual(MOD.VECTOR_REVISION, "envelope_vectors_v1.1")
        self.assertEqual(
            MOD.UPSTREAM_COMMIT,
            "8042a0ce33a9f8a7bf54a1917d5e8a0ac0344084",
        )
        self.assertEqual(
            MOD.PINNED_VECTOR_SHA256,
            "6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64",
        )
        self.assertEqual(len(MOD.PINNED_CASES), 18)
        self.assertEqual(
            MOD.ENVELOPE_FAILURES,
            {
                "envelope_unknown_version",
                "envelope_unknown_member",
                "envelope_subject_mismatch",
                "envelope_duplicate_subject",
                "envelope_non_canonical",
                "envelope_unknown_witness",
                "envelope_bad_signature",
            },
        )

    def test_source_does_not_import_or_execute_upstream_verifier(self):
        source = _MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import attenu_guard", source)
        self.assertNotIn("from attenu_guard", source)
        self.assertNotIn("subprocess", source)
        self.assertIn("independent_bundle_verifier.py", source)

    def test_valid_envelope_is_witness_signed(self):
        bundle, witness_keys, _ = _signed_bundle()
        score = MOD._score_envelopes(bundle, witness_keys)

        self.assertEqual(score.failures, ())
        self.assertEqual(score.states["1"], MOD.WITNESS_SIGNED)
        self.assertEqual(score.results["1"], "matched")
        self.assertEqual(score.states["0"], MOD.PROCESS_ASSERTED)
        self.assertEqual(score.states["2"], MOD.PROCESS_ASSERTED)

    def test_bad_signature_fails_closed_at_covered_entry(self):
        bundle, witness_keys, _ = _signed_bundle()
        bundle["envelopes"][0]["sig"] = "00" * 64

        score = MOD._score_envelopes(bundle, witness_keys)

        self.assertEqual(
            [(failure.reason, failure.seq, failure.node) for failure in score.failures],
            [("envelope_bad_signature", 1, "vectors:n1")],
        )
        self.assertEqual(score.states["1"], MOD.PROCESS_ASSERTED)

    def test_duplicate_subject_cannot_overwrite_first_witness(self):
        bundle, witness_keys, private_key = _signed_bundle()
        second = copy.deepcopy(bundle["envelopes"][0])
        second["observed"]["result"] = "not_matched"
        second["sig"] = private_key.sign(
            MOD.BASE.jcs_bytes(
                {key: value for key, value in second.items() if key != "sig"}
            )
        ).hex()
        bundle["envelopes"].append(second)

        score = MOD._score_envelopes(bundle, witness_keys)

        self.assertIn(
            ("envelope_duplicate_subject", 1, "vectors:n1"),
            [(failure.reason, failure.seq, failure.node) for failure in score.failures],
        )
        self.assertEqual(score.states["1"], MOD.PROCESS_ASSERTED)
        self.assertEqual(score.results["1"], "matched")

    def test_unknown_algorithm_is_not_misreported_as_bad_signature(self):
        bundle, witness_keys, private_key = _signed_bundle()
        envelope = bundle["envelopes"][0]
        envelope["witness"]["alg"] = "none"
        envelope["sig"] = private_key.sign(
            MOD.BASE.jcs_bytes(
                {key: value for key, value in envelope.items() if key != "sig"}
            )
        ).hex()

        score = MOD._score_envelopes(bundle, witness_keys)

        self.assertEqual(
            [failure.reason for failure in score.failures],
            ["envelope_unknown_witness"],
        )

    def test_locator_mismatch_is_positioned_by_seq_found_entry(self):
        bundle, witness_keys, private_key = _signed_bundle()
        envelope = bundle["envelopes"][0]
        envelope["subject"]["node"] = "vectors:n0"
        envelope["sig"] = private_key.sign(
            MOD.BASE.jcs_bytes(
                {key: value for key, value in envelope.items() if key != "sig"}
            )
        ).hex()

        score = MOD._score_envelopes(bundle, witness_keys)

        failure = score.failures[0]
        self.assertEqual(failure.reason, "envelope_subject_mismatch")
        self.assertEqual(failure.seq, 1)
        self.assertEqual(failure.node, "vectors:n1")


if __name__ == "__main__":
    unittest.main()
