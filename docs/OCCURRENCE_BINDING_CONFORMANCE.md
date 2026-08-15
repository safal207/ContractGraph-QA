# Exact Occurrence Binding Conformance

Status: reference contract; provider- and framework-neutral.

## Problem

A semantic authorization decision can have more than one concrete occurrence because of retries, re-issuance, cancellation/recreation, authority transfer, or concurrent execution paths.

Binding execution only to `decision_ref` is therefore insufficient when more than one occurrence shares that semantic identity.

## Invariant

> A side-effecting execution may consume an authorization only when the semantic decision resolves to exactly one concrete occurrence.

The conformance rule is:

```text
one semantic match + no collision
    -> may resolve without cites_event_id

multiple semantic matches + no cites_event_id
    -> OCCURRENCE_AMBIGUOUS (fail closed)

multiple semantic matches + exact cites_event_id
    -> resolve only that occurrence

cites_event_id that does not belong to decision_ref
    -> OCCURRENCE_NOT_FOUND (fail closed)
```

Compact identity rule:

```text
semantic decision identity != authorization occurrence identity != consumption fact
```

## Resolution and consumption

`resolve_occurrence()` and `attempt_consume()` are intentionally separate operations.

A synchronous runtime may execute both inside one atomic call or transaction. That does not require collapsing their causal identities:

```text
DecisionOccurrence(event_id): ALLOW
        -> RESOLVED_ALLOW
        -> CONSUMED
        -> execution
```

A caller may simply not observe an intermediate wall-clock gap.

## Falsification cases

`tools/tests/test_occurrence_binding.py` proves the following boundaries:

1. a unique semantic decision resolves without an explicit event id;
2. a real collision without `cites_event_id` returns `OCCURRENCE_AMBIGUOUS`;
3. the same collision resolves when the exact event id is supplied;
4. an unknown event id never falls back to a semantic match;
5. an event id cannot cross-bind to another decision;
6. `RESOLVED_ALLOW` and `CONSUMED` remain distinct facts;
7. one occurrence cannot be consumed twice;
8. ambiguous and denied resolutions cannot be consumed.

## Provenance boundary

This contract was added after an external review in the CrewAI GuardrailProvider discussion independently checked a runnable reference implementation with collision and explicit-event-id cases. That review is evidence that the boundary shape is useful and executable; it is **not** evidence of CrewAI adoption or production deployment.

The ContractGraph-QA implementation is intentionally small and framework-neutral so the same falsification suite can be reused by provider adapters, agent runtimes, and authorization ledgers.
