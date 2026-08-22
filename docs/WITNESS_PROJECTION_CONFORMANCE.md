# Witness Projection Conformance v0.1

This document freezes a small executable contract for replayable outcome derivation from append-only evidence.

## Compact contract

> Same witnesses, same outcome. New witnesses may change the outcome but must not rewrite old evidence. Time and absence affect state only after becoming explicit witnesses.

## Scope

The contract applies to reducers, authorization/audit layers, recovery logic, and other systems that derive externally meaningful state from recorded evidence.

It is intentionally small. It does not prescribe a vendor receipt format, persistence engine, or framework-specific hook API.

## Invariants

### 1. Monotone witnesses

Evidence grows by append:

```text
W' = W + [w]
```

A later observation may change the derived state, but it must not mutate earlier evidence to manufacture the new result.

### 2. Deterministic projection

For any two evaluators holding the same witness sequence:

```text
P(W) == P(W)
```

The result must not depend on the evaluator's wall clock, process-local mutable state, or drifting configuration.

### 3. No ambient clock dependency

A projection may accept `now` as a conformance probe, but a conformant implementation declines to use it.

This is intentionally stronger than hiding time behind an interface: the known-bad implementation in the executable suite can read the clock and is required to fail the determinism property.

### 4. Explicit absence

"Nothing happened" is not evidence until an observation records it.

A time-dependent transition therefore consumes a witness such as:

```json
{
  "kind": "absence",
  "checked_at": 3000,
  "window": [1000, 3000],
  "deadline": 2500,
  "result": "no_response"
}
```

Without that witness, the state remains unchanged even if wall-clock time has passed the deadline.

### 5. Deadline/config binding

The deadline used to derive an expiry must be carried by evidence consumed by the projection. Reading it from mutable projection configuration recreates the same nondeterminism under config drift.

The reference implementation therefore fails closed when an absence witness does not carry its deadline.

### 6. Prefix stability

Appending a new witness must not alter what any old prefix of the log projected to before the append.

This catches implementations that normalize, backfill, or rewrite earlier witnesses after later evidence arrives.

### 7. Non-monotone state over monotone evidence

The witness set can grow monotonically while the projected state changes non-monotonically.

Example:

```text
[sent, absence]           -> expired
[sent, absence, response] -> accepted
```

The state changed. The evidence did not shrink or get rewritten.

### 8. Replay stability

A frozen witness sequence must replay to the same result later.

If a read performed tomorrow derives a different state from the same bytes than a read today, the projection is not an audit/replay function.

### 9. Guard the guard

The suite includes a deliberately non-conformant clock-reading projection and asserts that it produces different outputs for the same witnesses under different `now` values.

A conformance test that never demonstrates detection of a violating implementation can pass vacuously.

## Executable reference

Reference projection:

```text
contractgraph_qa/witness_projection.py
```

Conformance tests:

```text
tools/tests/test_witness_projection_conformance.py
```

Run only this boundary:

```bash
python -m unittest tools.tests.test_witness_projection_conformance -v
```

Or run the repository Python gate:

```bash
python -m unittest discover -s tools/tests -p 'test_*.py' -v
```

## Framework integration boundary

For an agent middleware or authorization hook, any decision that can expire, back off, time out, or become stale must consume a recorded observation rather than call `now()` inside the replayable decision projection.

Live checks may read the clock. Their result must then be appended as evidence. The projection consumes that evidence.

```text
ambient world / clock
        |
        v
observation step
        |
        v
append witness
        |
        v
deterministic projection
        |
        v
replayable state
```

This separation keeps live observation non-determinism outside the audit projection while preserving the facts needed to reproduce the decision later.

## What v0.1 does not claim

- It does not prove witness authenticity.
- It does not define cryptographic provenance.
- It does not guarantee that every relevant event was observed.
- It does not define ordering across distributed writers.
- It does not turn a weak/transcribed witness into a strong/observed witness.
- It does not prescribe how external side effects are verified.

Those are separate evidence-quality and provenance boundaries. This conformance layer answers one narrower question: **given this exact recorded witness sequence, is outcome derivation deterministic, append-only, and replayable?**
