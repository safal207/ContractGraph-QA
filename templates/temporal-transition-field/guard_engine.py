#!/usr/bin/env python3
"""Guard evaluation for Temporal Transition Field v0.5.

Guards are pure, fail-closed predicates over the current pre-state and declared
transition. They reuse the constrained comparison semantics from the v0.3
detector and never execute arbitrary expressions.
"""
from __future__ import annotations

from typing import Any

from detect_forbidden_state import evaluate_clause


def _matches_transition(binding: dict[str, Any], transition: tuple[str, str, str]) -> bool:
    src, event, dst = transition
    return (
        binding.get("from") == src
        and binding.get("event") == event
        and binding.get("to") == dst
    )


def evaluate_transition_guards(
    pre_state: dict[str, Any],
    transition: tuple[str, str, str],
    guards_document: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return allowed, blocked, or inconclusive for one declared transition."""
    if not guards_document:
        return {
            "status": "allowed",
            "reason": "guards_disabled",
            "guard_ids": [],
            "evaluations": [],
        }

    relevant = [
        guard
        for guard in guards_document.get("guards", [])
        if _matches_transition(guard.get("transition", {}), transition)
    ]
    if not relevant:
        return {
            "status": "allowed",
            "reason": "no_guard_declared",
            "guard_ids": [],
            "evaluations": [],
        }

    envelope = {
        "pre_state": pre_state,
        "transition": {
            "from": transition[0],
            "event": transition[1],
            "to": transition[2],
        },
    }
    guard_evaluations: list[dict[str, Any]] = []

    for guard in relevant:
        clauses = [evaluate_clause(envelope, clause) for clause in guard.get("all", [])]
        if any(item["status"] == "inconclusive" for item in clauses):
            status = "inconclusive"
        elif any(item["status"] == "fail" for item in clauses):
            status = "blocked"
        else:
            status = "allowed"
        guard_evaluations.append(
            {
                "id": guard.get("id"),
                "status": status,
                "clauses": clauses,
            }
        )

    if any(item["status"] == "inconclusive" for item in guard_evaluations):
        overall = "inconclusive"
        reason = "guard_operand_missing_or_not_comparable"
    elif any(item["status"] == "blocked" for item in guard_evaluations):
        overall = "blocked"
        reason = "guard_predicate_false"
    else:
        overall = "allowed"
        reason = "all_guards_passed"

    return {
        "status": overall,
        "reason": reason,
        "guard_ids": [item["id"] for item in guard_evaluations],
        "evaluations": guard_evaluations,
    }
