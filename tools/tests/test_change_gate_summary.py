from __future__ import annotations

import unittest

from contractgraph_qa.change_gate_summary import render_change_gate_summary


class ChangeGateSummaryTests(unittest.TestCase):
    def test_blocked_summary_includes_exact_causal_path(self) -> None:
        result = {
            "status": "blocked",
            "baseCommitSha": "a" * 40,
            "headCommitSha": "b" * 40,
            "models": [
                {
                    "id": "escrow",
                    "status": "blocked",
                    "gateReasons": ["new_forbidden_reachability"],
                    "delta": {
                        "introducedForbiddenPaths": {
                            "release-without-approval": {
                                "invariantIds": ["approval-required"],
                                "crossedBoundaries": ["approval-boundary"],
                                "transitions": [
                                    {"id": "request-release"},
                                    {"id": "bypass-approval"},
                                ],
                            }
                        },
                        "removedDeclaredControlBoundaries": [],
                    },
                }
            ],
        }
        rendered = render_change_gate_summary(result)
        self.assertIn("**Status:** `blocked`", rendered)
        self.assertIn("release-without-approval", rendered)
        self.assertIn("approval-required", rendered)
        self.assertIn("approval-boundary", rendered)
        self.assertIn("request-release → bypass-approval", rendered)

    def test_definition_drift_summary_surfaces_historical_target(self) -> None:
        result = {
            "status": "blocked",
            "baseCommitSha": "a" * 40,
            "headCommitSha": "b" * 40,
            "models": [
                {
                    "id": "wallet",
                    "status": "blocked",
                    "gateReasons": ["forbidden_definition_changed"],
                    "delta": {
                        "introducedForbiddenPaths": {},
                        "forbiddenDefinitionChanges": {
                            "removedFormerlyForbiddenCapabilities": ["overspend"],
                            "forbiddenToAllowedCapabilities": [],
                        },
                        "removedDeclaredControlBoundaries": [],
                    },
                }
            ],
        }
        rendered = render_change_gate_summary(result)
        self.assertIn("forbidden_definition_changed", rendered)
        self.assertIn("overspend", rendered)

    def test_review_summary_surfaces_removed_boundary(self) -> None:
        result = {
            "status": "review",
            "baseCommitSha": "a" * 40,
            "headCommitSha": "b" * 40,
            "models": [
                {
                    "id": "settlement",
                    "status": "review",
                    "gateReasons": [],
                    "delta": {
                        "introducedForbiddenPaths": {},
                        "removedDeclaredControlBoundaries": ["settlement-idempotency"],
                    },
                }
            ],
        }
        rendered = render_change_gate_summary(result)
        self.assertIn("**Status:** `review`", rendered)
        self.assertIn("settlement-idempotency", rendered)

    def test_verified_fix_summary_uses_machine_replay_evidence(self) -> None:
        result = {
            "status": "pass",
            "baseCommitSha": "a" * 40,
            "headCommitSha": "b" * 40,
            "models": [
                {
                    "id": "escrow",
                    "status": "pass",
                    "gateReasons": [],
                    "delta": {
                        "introducedForbiddenPaths": {},
                        "removedDeclaredControlBoundaries": [],
                    },
                    "fixReplays": [
                        {
                            "targetCapability": "release-without-approval",
                            "status": "fix_verified",
                            "verified": True,
                            "replay": {
                                "priorPath": {
                                    "transitions": [
                                        {"id": "enter-approval-stage"},
                                        {"id": "bypass-approval"},
                                    ]
                                },
                                "exactReplay": {
                                    "blockedAt": {
                                        "reason": "assumption_guard_restored"
                                    }
                                },
                                "alternateReachability": {"reachable": False},
                            },
                        }
                    ],
                }
            ],
        }
        rendered = render_change_gate_summary(result)
        self.assertIn("## Exact historical fix replay", rendered)
        self.assertIn("release-without-approval", rendered)
        self.assertIn("fix_verified", rendered)
        self.assertIn("enter-approval-stage → bypass-approval", rendered)
        self.assertIn("assumption_guard_restored", rendered)
        self.assertIn("| no |", rendered)


if __name__ == "__main__":
    unittest.main()
