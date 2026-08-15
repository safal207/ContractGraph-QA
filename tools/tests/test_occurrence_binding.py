from __future__ import annotations

import unittest

from contractgraph_qa.occurrence_binding import (
    ALREADY_CONSUMED,
    CONSUMED,
    NOT_AUTHORIZED,
    OCCURRENCE_AMBIGUOUS,
    OCCURRENCE_NOT_FOUND,
    RESOLVED_ALLOW,
    RESOLVED_DENY,
    DecisionOccurrence,
    attempt_consume,
    resolve_occurrence,
)


class OccurrenceBindingConformanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.e1 = DecisionOccurrence(event_id="evt-1", decision_ref="decision-A", verdict="ALLOW")
        self.e2 = DecisionOccurrence(event_id="evt-2", decision_ref="decision-A", verdict="ALLOW")
        self.deny = DecisionOccurrence(event_id="evt-3", decision_ref="decision-B", verdict="DENY")

    def test_unique_semantic_decision_resolves_without_event_id(self) -> None:
        result = resolve_occurrence("decision-B", None, [self.e1, self.deny])
        self.assertEqual(result.status, RESOLVED_DENY)
        self.assertEqual(result.occurrence, self.deny)

    def test_collision_without_cites_event_id_fails_closed(self) -> None:
        result = resolve_occurrence("decision-A", None, [self.e1, self.e2])
        self.assertEqual(result.status, OCCURRENCE_AMBIGUOUS)
        self.assertIsNone(result.occurrence)

    def test_collision_resolves_when_exact_event_id_is_cited(self) -> None:
        result = resolve_occurrence("decision-A", "evt-2", [self.e1, self.e2])
        self.assertEqual(result.status, RESOLVED_ALLOW)
        self.assertEqual(result.occurrence, self.e2)

    def test_unknown_event_id_does_not_fall_back_to_semantic_match(self) -> None:
        result = resolve_occurrence("decision-A", "evt-missing", [self.e1, self.e2])
        self.assertEqual(result.status, OCCURRENCE_NOT_FOUND)
        self.assertIsNone(result.occurrence)

    def test_event_id_from_other_decision_does_not_cross_bind(self) -> None:
        result = resolve_occurrence("decision-A", "evt-3", [self.e1, self.deny])
        self.assertEqual(result.status, OCCURRENCE_NOT_FOUND)
        self.assertIsNone(result.occurrence)

    def test_resolved_allow_and_consumed_remain_distinct_facts(self) -> None:
        result = resolve_occurrence("decision-A", "evt-1", [self.e1, self.e2])
        consumed: set[str] = set()

        self.assertEqual(result.status, RESOLVED_ALLOW)
        self.assertEqual(attempt_consume(result, consumed), CONSUMED)
        self.assertEqual(consumed, {"evt-1"})

    def test_same_occurrence_cannot_be_consumed_twice(self) -> None:
        result = resolve_occurrence("decision-A", "evt-1", [self.e1, self.e2])
        consumed: set[str] = set()

        self.assertEqual(attempt_consume(result, consumed), CONSUMED)
        self.assertEqual(attempt_consume(result, consumed), ALREADY_CONSUMED)

    def test_ambiguous_or_denied_resolution_cannot_be_consumed(self) -> None:
        consumed: set[str] = set()
        ambiguous = resolve_occurrence("decision-A", None, [self.e1, self.e2])
        denied = resolve_occurrence("decision-B", "evt-3", [self.deny])

        self.assertEqual(attempt_consume(ambiguous, consumed), NOT_AUTHORIZED)
        self.assertEqual(attempt_consume(denied, consumed), NOT_AUTHORIZED)
        self.assertEqual(consumed, set())


if __name__ == "__main__":
    unittest.main()
