import unittest

from contractgraph_qa.astra_state_planes import (
    AstraStatePlaneError,
    analyze_state_planes,
)


class AstraStatePlaneTests(unittest.TestCase):
    def test_independent_witness_can_confirm_primary(self):
        result = analyze_state_planes(
            {
                "states": [
                    {
                        "id": "released",
                        "state_hash": "h1",
                        "future_signature": "terminal",
                        "primary": {
                            "fingerprint": "released:100",
                            "source_root": "contract-storage",
                        },
                        "mirrors": [
                            {
                                "id": "event",
                                "fingerprint": "released:100",
                                "source_root": "event-log",
                            }
                        ],
                        "witnesses": [
                            {
                                "id": "token-balance",
                                "fingerprint": "released:100",
                                "source_root": "erc20-balance",
                                "independent": True,
                            }
                        ],
                    }
                ]
            }
        )
        state = result["states"][0]
        self.assertEqual(state["witness_gap"], 0.0)
        self.assertFalse(state["state_plane_ambiguity"])
        self.assertEqual(result["verdict"], "CONSISTENT_WITH_INPUT")

    def test_missing_independent_witness_fails_closed(self):
        result = analyze_state_planes(
            {
                "states": [
                    {
                        "id": "pending",
                        "state_hash": "h1",
                        "future_signature": "can-settle",
                        "primary": {
                            "fingerprint": "pending",
                            "source_root": "contract-storage",
                        },
                        "mirrors": [],
                        "witnesses": [],
                    }
                ]
            }
        )
        state = result["states"][0]
        self.assertEqual(state["witness_gap"], 1.0)
        self.assertTrue(state["state_plane_ambiguity"])
        self.assertEqual(result["verdict"], "REVIEW_REQUIRED")

    def test_same_hash_different_future_is_suspect(self):
        result = analyze_state_planes(
            {
                "states": [
                    {
                        "id": "s1",
                        "state_hash": "same",
                        "future_signature": "retry-can-settle",
                        "primary": {
                            "fingerprint": "pending",
                            "source_root": "storage",
                        },
                        "witnesses": [
                            {
                                "id": "w1",
                                "fingerprint": "pending",
                                "source_root": "chain",
                                "independent": True,
                            }
                        ],
                    },
                    {
                        "id": "s2",
                        "state_hash": "same",
                        "future_signature": "retry-blocked",
                        "primary": {
                            "fingerprint": "pending",
                            "source_root": "storage",
                        },
                        "witnesses": [
                            {
                                "id": "w2",
                                "fingerprint": "pending",
                                "source_root": "chain",
                                "independent": True,
                            }
                        ],
                    },
                ]
            }
        )
        self.assertEqual(len(result["state_hash_suspicions"]), 1)
        suspicion = result["state_hash_suspicions"][0]
        self.assertEqual(suspicion["status"], "STATE_HASH_SUSPECT")
        self.assertIn("different_future_signature", suspicion["reasons"])
        self.assertEqual(result["verdict"], "REVIEW_REQUIRED")

    def test_independent_witness_divergence_is_visible(self):
        result = analyze_state_planes(
            {
                "states": [
                    {
                        "id": "settled",
                        "state_hash": "h2",
                        "future_signature": "terminal",
                        "primary": {
                            "fingerprint": "settled",
                            "source_root": "accounting-db",
                        },
                        "witnesses": [
                            {
                                "id": "chain-transfer",
                                "fingerprint": "not-settled",
                                "source_root": "chain",
                                "independent": True,
                            }
                        ],
                    }
                ]
            }
        )
        state = result["states"][0]
        self.assertEqual(state["witness_divergence"], 1.0)
        self.assertEqual(state["independent_witness_disagreements"], ["chain-transfer"])
        self.assertTrue(state["state_plane_ambiguity"])

    def test_duplicate_state_id_is_rejected(self):
        payload = {
            "states": [
                {
                    "id": "same",
                    "state_hash": "h1",
                    "future_signature": "a",
                    "primary": {"fingerprint": "a", "source_root": "p"},
                },
                {
                    "id": "same",
                    "state_hash": "h2",
                    "future_signature": "b",
                    "primary": {"fingerprint": "b", "source_root": "p"},
                },
            ]
        }
        with self.assertRaises(AstraStatePlaneError):
            analyze_state_planes(payload)


if __name__ == "__main__":
    unittest.main()
