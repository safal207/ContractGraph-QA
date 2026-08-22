from __future__ import annotations

import unittest

from contractgraph_qa.witness_projection import project_witnesses
from contractgraph_qa.witness_projection_conformance import (
    SPEC_ID,
    run_witness_projection_conformance,
)


def clock_reading_projection(witnesses, now):
    state = "pending"
    for witness in witnesses:
        if witness["kind"] == "sent":
            state = "awaiting_response"
            if now >= witness["deadline"]:
                state = "expired"
        elif witness["kind"] == "response":
            state = "accepted"
    return state


def deadline_ignoring_projection(witnesses, now):
    del now
    state = "pending"
    for witness in witnesses:
        if witness["kind"] == "sent":
            state = "awaiting_response"
        elif witness["kind"] == "absence":
            state = "expired"
        elif witness["kind"] == "response":
            state = "accepted"
    return state


def mutating_projection(witnesses, now):
    state = project_witnesses(witnesses, now)
    if witnesses:
        witnesses[0]["mutated_by_projection"] = True
    return state


class WitnessProjectionConformanceApiTest(unittest.TestCase):
    def test_reference_projection_conforms(self) -> None:
        report = run_witness_projection_conformance(project_witnesses)
        self.assertEqual(report.spec, SPEC_ID)
        self.assertTrue(report.conformant)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_report_is_machine_serializable(self) -> None:
        payload = run_witness_projection_conformance(project_witnesses).to_dict()
        self.assertEqual(payload["spec"], SPEC_ID)
        self.assertTrue(payload["conformant"])
        self.assertEqual(len(payload["checks"]), 8)
        self.assertTrue(all("name" in check for check in payload["checks"]))
        self.assertTrue(all("passed" in check for check in payload["checks"]))
        self.assertTrue(all("detail" in check for check in payload["checks"]))

    def test_known_bad_clock_reader_is_rejected(self) -> None:
        report = run_witness_projection_conformance(clock_reading_projection)
        self.assertFalse(report.conformant)
        checks = {check.name: check for check in report.checks}
        self.assertFalse(checks["deterministic_across_evaluator_time"].passed)
        self.assertFalse(checks["replay_stability"].passed)

    def test_deadline_ignoring_projection_is_rejected(self) -> None:
        report = run_witness_projection_conformance(deadline_ignoring_projection)
        self.assertFalse(report.conformant)
        checks = {check.name: check for check in report.checks}
        self.assertFalse(checks["deadline_bound_to_evidence"].passed)
        self.assertFalse(checks["missing_deadline_fails_closed"].passed)

    def test_projection_that_mutates_evidence_is_rejected(self) -> None:
        report = run_witness_projection_conformance(mutating_projection)
        self.assertFalse(report.conformant)
        checks = {check.name: check for check in report.checks}
        self.assertFalse(checks["projection_does_not_mutate_evidence"].passed)


if __name__ == "__main__":
    unittest.main()
