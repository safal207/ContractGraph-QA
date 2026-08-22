# Witness Projection Adapter API

`Witness Projection Conformance v0.1` can be run against any reducer or agent runtime through a thin adapter exposing:

```python
projection(witnesses, now) -> state
```

The conformance harness deliberately supplies `now`. A replay-safe projection may receive it, but identical witnesses must not derive different outcomes merely because evaluator time changed.

## Python API

```python
from contractgraph_qa.witness_projection_conformance import (
    run_witness_projection_conformance,
)

report = run_witness_projection_conformance(my_projection)

print(report.conformant)
print(report.to_dict())
```

The machine-readable shape is:

```json
{
  "spec": "witness-projection-conformance/v0.1",
  "conformant": true,
  "checks": [
    {
      "name": "deterministic_across_evaluator_time",
      "passed": true,
      "detail": "..."
    }
  ]
}
```

A CI gate can fail when `report.conformant` is false and surface individual check details as diagnostic evidence.

## Canonical adapter boundary

The v0.1 harness uses three canonical witness kinds:

- `sent`
- `absence`
- `response`

A framework does not need to store those exact objects internally. Its adapter may translate them into native events before invoking the framework reducer.

Example:

```python
def crew_projection(witnesses, now):
    native_events = [to_crew_event(witness) for witness in witnesses]
    return crew_reducer(native_events, now=now)

report = run_witness_projection_conformance(crew_projection)
assert report.conformant
```

The adapter must not repair a non-conformant reducer by hiding ambient dependencies. In particular, it must not discard `now` solely to make a clock-reading implementation appear deterministic. The point of the signature is to leave the violating capability reachable so the suite can detect whether the implementation declines to use it.

## Checks in v0.1

The reusable runner checks:

1. identical witnesses produce the same result across evaluator times;
2. an explicit absence witness is required to enable the time-dependent transition;
3. replay of a frozen witness sequence is stable;
4. old prefixes remain stable after append;
5. state can change after a new witness without rewriting evidence;
6. deadline semantics are carried by evidence;
7. an absence witness missing its deadline fails closed;
8. the projection does not mutate the witness sequence.

The repository test suite additionally runs deliberately bad implementations to guard the guard:

- a projection that reads the evaluator clock;
- a projection that ignores witness-bound deadlines;
- a projection that mutates the evidence log.

All three must be rejected.

## Scope

Passing this API means only that the supplied adapter/reducer satisfies the v0.1 deterministic replay boundary for the canonical fixture semantics.

It does not prove:

- witness authenticity or completeness;
- cryptographic provenance;
- distributed ordering correctness;
- authorization policy correctness;
- external side-effect execution;
- framework-wide conformance outside the adapter path exercised by the suite.

Those claims require separate evidence boundaries.
