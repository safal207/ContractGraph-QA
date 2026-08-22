from __future__ import annotations

import copy
import unittest

from contractgraph_qa.witness_projection import (
    WitnessProjectionError,
    project_witnesses,
)

T0, T1, T2, DEADLINE = 1000, 2000, 3000, 2500
SENT = {"kind": "sent", "at": T0, "deadline": DEADLINE}
ABSENCE = {
    "kind": "absence",
    "checked_at": T2,
    "window": (T0, T2),
    "deadline": DEADLINE,
    "result": "no_response",
}
RESPONSE = {"kind": "response", "at": T1}


def clock_reading_projection(witnesses, now):
    """Known-bad implementation used to guard the conformance guard itself."""
    state = "pending"
    for witness in witnesses:
        if witness["kind"] == "sent":
            state = "awaiting_response"
            if now >= witness["deadline"]:
                state = "expired"
        elif witness["kind"] == "response":
            state = "accepted"
    return state


class WitnessProjectionConformanceTest(unittest.TestCase):
    def test_same_witnesses_same_outcome_across_evaluators(self) -> None:
        witnesses = [SENT]
        self.assertEqual(
            project_witnesses(witnesses, now=T1),
            project_witnesses(witnesses, now=T2 + 10_000),
        )

    def test_clock_reading_projection_is_red(self) -> None:
        witnesses = [SENT]
        self.assertNotEqual(
            clock_reading_projection(witnesses, now=T1),
            clock_reading_projection(witnesses, now=T2 + 10_000),
        )

    def test_absence_witness_enables_transition(self) -> None:
        self.assertEqual(project_witnesses([SENT], now=T2), "awaiting_response")
        self.assertEqual(project_witnesses([SENT, ABSENCE], now=T2), "expired")

    def test_replay_is_stable(self) -> None:
        witnesses = [SENT, ABSENCE]
        first = project_witnesses(witnesses, now=T2)
        for later in (T2 + 1, T2 + 86_400, T2 + 10**9):
            self.assertEqual(project_witnesses(witnesses, now=later), first)

    def test_new_witness_does_not_rewrite_old_evidence(self) -> None:
        log = [SENT, ABSENCE]
        prefix_states = [
            project_witnesses(log[:i], now=T2) for i in range(len(log) + 1)
        ]
        extended = log + [RESPONSE]
        for i, expected in enumerate(prefix_states):
            self.assertEqual(project_witnesses(extended[:i], now=T2), expected)

    def test_non_monotone_state_over_monotone_witness_set(self) -> None:
        self.assertEqual(project_witnesses([SENT, ABSENCE], now=T2), "expired")
        self.assertEqual(
            project_witnesses([SENT, ABSENCE, RESPONSE], now=T2), "accepted"
        )

    def test_deadline_is_evidence_not_projection_config(self) -> None:
        absence_without_deadline = copy.deepcopy(ABSENCE)
        del absence_without_deadline["deadline"]
        with self.assertRaisesRegex(
            WitnessProjectionError,
            "ambient configuration is not evidence",
        ):
            project_witnesses([SENT, absence_without_deadline], now=T2)

    def test_projection_does_not_mutate_witness_log(self) -> None:
        witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE)]
        before = copy.deepcopy(witnesses)
        project_witnesses(witnesses, now=T2)
        self.assertEqual(witnesses, before)


if __name__ == "__main__":
    unittest.main()
