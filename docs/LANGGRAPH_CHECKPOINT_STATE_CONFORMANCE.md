# LangGraph checkpoint/state conformance benchmark

This benchmark asks whether current LangGraph state/checkpoint primitives can host `Witness Projection Conformance v0.1` without hiding time-dependent semantics in ambient wall-clock reads.

## Pinned upstream source

Repository: `langchain-ai/langgraph`

Commit:

```text
f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f
```

Observed source boundaries:

```text
libs/langgraph/langgraph/graph/state.py
libs/checkpoint/langgraph/checkpoint/base/__init__.py
```

At that commit:

- `StateGraph` state keys can use reducers with signature `(Value, Value) -> Value`;
- checkpoints persist graph state in `Checkpoint.channel_values`;
- checkpoint IDs are documented as unique and monotonically increasing;
- checkpoints carry an ISO-8601 timestamp, but the hosted projection does not use it as a decision input.

## Scope: hosted adapter, not native-domain claim

LangGraph does not define the domain-specific `sent -> absence -> response` state machine used by Witness Projection Conformance v0.1. It provides a generic state machine and persistence substrate.

So this benchmark does **not** claim:

```text
LangGraph natively implements Witness Projection Conformance v0.1
```

It tests the narrower and useful claim:

```text
Can LangGraph host an append-only witness log and replayable projection
without losing explicit absence/deadline evidence or consulting now()?
```

## Thin hosted integration

The model uses one state key:

```text
witnesses: append-only list
```

A LangGraph-compatible reducer appends new witnesses without mutating the old list.

Conceptually:

```python
def reducer(current, update):
    return current + [update]
```

The resulting witness sequence is stored under checkpoint `channel_values`, restored byte-for-byte at the semantic level, and then passed to the frozen deterministic projection.

```text
live observation
      |
      v
explicit witness
      |
      v
StateGraph append reducer
      |
      v
checkpoint.channel_values["witnesses"]
      |
      v
restore same witness sequence
      |
      v
Witness Projection v0.1
```

The checkpoint timestamp is evidence about checkpoint creation time only. It is not used to infer that a deadline elapsed or that a response was absent.

## Result

Expected result:

```text
Witness Projection Conformance v0.1
LangGraph hosted checkpoint/state adapter
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

Result: **8/8**.

This is meaningfully different from the CrewAI tool-event benchmark. CrewAI's pinned tool-event vocabulary cannot natively represent the canonical absence/deadline witness at the measured boundary. LangGraph's generic state/checkpoint substrate can preserve that witness as ordinary state, so no semantic information has to be synthesized during replay.

## What makes the PASS legitimate

The adapter does not:

- inspect current wall-clock time;
- derive expiry from the checkpoint timestamp;
- read mutable deadline configuration;
- rewrite old witnesses after a later witness arrives;
- invent an observation during replay.

Instead, the live observation step must append the explicit absence/deadline witness before the projection can change state.

## Reproduce

```bash
python -m unittest tools.tests.test_langgraph_checkpoint_state_conformance -v
```

Machine-readable expected result:

```text
benchmarks/langgraph-checkpoint-state-conformance-v0.1/result.json
```

## Boundary of the result

An 8/8 hosted-adapter result does not prove:

- that every LangGraph application records the needed witnesses;
- that user reducers are correct;
- that checkpoint storage is authentic or tamper-proof;
- that every checkpointer backend has equivalent durability under all failures;
- that external side effects are exactly-once;
- that LangGraph itself promises this conformance contract as part of its public API.

It proves a narrower architectural fact: **the pinned StateGraph + checkpoint model can carry the exact append-only evidence needed for deterministic witness projection without requiring ambient time at replay.**
