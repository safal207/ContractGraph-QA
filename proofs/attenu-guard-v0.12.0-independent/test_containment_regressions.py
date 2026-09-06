#!/usr/bin/env python3
"""Supplementary regression checks for containment gaps not isolated by v1.1.

These tests are deliberately separate from the released-corpus conformance
score. They derive local mutations from ``valid_bundle_v2``, rebuild the hash
chain and signed anchor, and check the exact defect boundary described for the
0.12.0 fix: scopes can be a literal subset while TTL or ceilings still widen.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import unittest
from pathlib import Path
from typing import Any, Callable

import independent_bundle_verifier as verifier


PROOF_DIR = Path(__file__).resolve().parent
FIXTURE = PROOF_DIR / "bundle_vectors_v1.json"


def _valid_case() -> tuple[dict[str, Any], dict[str, Any]]:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = next(item for item in document["cases"] if item["name"] == "valid_bundle_v2")
    return copy.deepcopy(case["bundle"]), copy.deepcopy(case["signer"])


def _entries(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = next(entry for entry in bundle["entries"] if entry["event"] == "root")
    spawn = next(entry for entry in bundle["entries"] if entry["event"] == "spawn")
    return root, spawn


def _rehash_and_resign(bundle: dict[str, Any], signer: dict[str, Any]) -> None:
    previous = verifier.GENESIS
    for position, entry in enumerate(bundle["entries"]):
        entry["seq"] = position
        entry["prev_hash"] = previous
        payload = {key: value for key, value in entry.items() if key != "hash"}
        entry["hash"] = hashlib.sha256(
            previous.encode("ascii") + verifier.jcs_bytes(payload)
        ).hexdigest()
        previous = entry["hash"]

    anchor = bundle["anchor"]
    anchor["seq"] = bundle["entries"][-1]["seq"]
    anchor["head"] = previous
    anchor["v"] = bundle["v"]
    anchor["chain_id"] = bundle["chain_id"]
    anchor_body = {
        key: value for key, value in anchor.items()
        if key not in {"kid", "sig", "verified"}
    }
    anchor["sig"] = hmac.new(
        bytes.fromhex(signer["secret_hex"]),
        verifier.jcs_bytes(anchor_body),
        hashlib.sha256,
    ).hexdigest()


def _literal_subset_case(
    mutate: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle, signer = _valid_case()
    root, spawn = _entries(bundle)
    root["authority"]["scopes"] = ["crm.read", "mail.send"]
    if mutate is not None:
        mutate(root, spawn)
    _rehash_and_resign(bundle, signer)
    return bundle, signer


class ContainmentRegressionTests(unittest.TestCase):
    def assert_monotonicity_reject(
        self,
        mutate: Callable[[dict[str, Any], dict[str, Any]], None],
    ) -> None:
        bundle, signer = _literal_subset_case(mutate)
        keys = [failure.score_key() for failure in verifier.verify_bundle(bundle, signer)]
        self.assertIn(
            {"reason": "monotonicity", "seq": 1, "node": "vectors:n1"},
            keys,
        )

    def test_literal_subset_base_accepts(self) -> None:
        bundle, signer = _literal_subset_case()
        self.assertEqual(verifier.verify_bundle(bundle, signer), [])

    def test_literal_subset_with_increased_ttl_rejects(self) -> None:
        self.assert_monotonicity_reject(
            lambda _root, spawn: spawn["granted"].__setitem__("ttl", 7200)
        )

    def test_literal_subset_with_loosened_ceiling_rejects(self) -> None:
        def mutate(_root: dict[str, Any], spawn: dict[str, Any]) -> None:
            spawn["granted"]["constraints"][0]["max"] = 250_000

        self.assert_monotonicity_reject(mutate)

    def test_literal_subset_with_missing_ttl_rejects(self) -> None:
        self.assert_monotonicity_reject(
            lambda _root, spawn: spawn["granted"].pop("ttl")
        )

    def test_literal_subset_with_missing_ceiling_rejects(self) -> None:
        self.assert_monotonicity_reject(
            lambda _root, spawn: spawn["granted"].__setitem__("constraints", [])
        )

    def test_invalid_shared_constraint_shape_or_type_rejects(self) -> None:
        def add_child_member(_root: dict[str, Any], spawn: dict[str, Any]) -> None:
            spawn["granted"]["constraints"][0]["unknown"] = True

        def add_parent_member(root: dict[str, Any], _spawn: dict[str, Any]) -> None:
            root["authority"]["constraints"][0]["unknown"] = True

        def set_child_boolean(_root: dict[str, Any], spawn: dict[str, Any]) -> None:
            spawn["granted"]["constraints"][0]["max"] = True

        def set_parent_boolean(root: dict[str, Any], _spawn: dict[str, Any]) -> None:
            root["authority"]["constraints"][0]["max"] = True

        for name, mutate in (
            ("child extra member", add_child_member),
            ("parent extra member", add_parent_member),
            ("child Boolean max", set_child_boolean),
            ("parent Boolean max", set_parent_boolean),
        ):
            with self.subTest(name=name):
                self.assert_monotonicity_reject(mutate)


if __name__ == "__main__":
    unittest.main()
