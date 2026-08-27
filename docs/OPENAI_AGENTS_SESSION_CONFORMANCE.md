# OpenAI Agents SDK session conformance

This benchmark applies `Witness Projection Conformance v0.1` to the OpenAI Agents SDK Python session persistence boundary.

## Pinned upstream source

Repository: `openai/openai-agents-python`

Commit:

```text
7f7a44f8dc0650296bd5ab6c745c9bcbaa6ac3b7
```

Observed source boundaries:

```text
src/agents/memory/session.py
src/agents/memory/sqlite_session.py
```

At this source snapshot, `Session` is explicitly a conversational-memory protocol over `TResponseInputItem` history. `SQLiteSession` persists each item with `json.dumps(item)` in an autoincrement row and restores valid JSON items in chronological `id ASC` order.

## Boundary under test

The SDK does **not** expose `Session` as a generic workflow checkpoint or immutable evidence ledger. The benchmark therefore uses a thin hosted-domain envelope:

1. encode each canonical witness into a normal Responses-style user message item;
2. persist each item through the same JSON/SQLite ordering shape used by `SQLiteSession`;
3. restore items in insertion order;
4. decode the witness envelope;
5. replay the frozen ContractGraph-QA projection without consulting ambient wall-clock time.

## Confirmed conformance target

```text
Witness Projection Conformance v0.1
OpenAI Agents SDK SQLiteSession hosted envelope
CONFORMANT

PASS  deterministic_across_evaluator_time
PASS  explicit_absence_enables_transition
PASS  replay_stability
PASS  prefix_stability
PASS  non_monotone_state_over_monotone_evidence
PASS  deadline_bound_to_evidence
PASS  missing_deadline_fails_closed
PASS  projection_does_not_mutate_evidence
```

Score: **8/8** for the restricted hosted adapter boundary.

## Important mutation caveat

The native `Session` protocol is **not append-only by contract**. It exposes:

```text
pop_item()
clear_session()
```

Therefore an application must not treat an unrestricted SDK session as an evidence ledger merely because the hosted projection scores 8/8.

For evidence-safe usage, the adapter boundary must restrict writes to append-only witness insertion and exclude destructive session operations from the evidence path.

This distinction is intentional:

```text
projection conformance != storage immutability
```

The benchmark proves that the SDK session substrate can *carry* the witness contract. It does not prove that arbitrary session consumers preserve evidence.

## Why session timestamps are not evidence

`SQLiteSession` maintains database timestamps for session/message bookkeeping. Those timestamps are persistence metadata, not the business observation that causes a deadline-dependent transition.

The decision-changing fact stays inside the explicit witness:

```json
{
  "kind": "absence",
  "checked_at": 3000,
  "window": [1000, 3000],
  "deadline": 2500,
  "result": "no_response"
}
```

Replay must derive the same result regardless of when the session row is later read.

## Interpretation

A PASS means the pinned OpenAI Agents SDK session persistence shape can host the frozen witness contract with a restricted adapter and without semantic loss or ambient-time replay dependence.

It does **not** mean:

- the SDK natively implements Witness Projection Conformance v0.1;
- `Session` is an immutable evidence store;
- `pop_item()` or `clear_session()` are safe on evidence history;
- arbitrary agent conversation history is sufficient proof;
- witness authenticity/completeness is established;
- external side effects become replay-safe automatically.

## Reproduce

```bash
python -m unittest discover -s tools/tests -p 'test_openai_agents_session_conformance.py' -v
```

Machine-readable expectation:

```text
benchmarks/openai-agents-session-conformance-v0.1/result.json
```
