# Microsoft Agent Framework checkpoint conformance

This benchmark applies `Witness Projection Conformance v0.1` to Microsoft Agent Framework's native Python workflow checkpoint boundary.

## Pinned upstream source

Repository: `microsoft/agent-framework`

Commit:

```text
d9d3fb6252f7ae9e7f8104edce7266f0782a813c
```

Observed source boundaries:

```text
python/packages/core/agent_framework/_workflows/_checkpoint.py
python/packages/core/agent_framework/_workflows/_checkpoint_encoding.py
```

At this source snapshot, `WorkflowCheckpoint` explicitly captures complete workflow execution state for pause/resume. Its `state` field contains committed workflow/user state, while checkpoint lineage is tracked separately with `previous_checkpoint_id`. File checkpoint storage encodes checkpoint values, writes JSON atomically, and decodes them on load.

## Boundary under test

Microsoft Agent Framework does **not** natively define the domain-specific `sent / absence / response` semantics from the conformance spec.

The benchmark tests a narrower but concrete capability:

1. place an append-only canonical witness list in committed `WorkflowCheckpoint.state`;
2. pass the JSON-safe witness subset through a storage-shaped round trip;
3. restore the exact ordered witness sequence;
4. replay the frozen ContractGraph-QA projection;
5. ignore checkpoint timestamp/lineage as decision inputs.

The canonical witness fixtures use only JSON-safe primitives, so the benchmark deliberately uses a plain JSON round trip. This is stricter than relying on framework pickle support for these fixtures and avoids adding Microsoft Agent Framework as a runtime dependency of ContractGraph-QA.

## Expected result

```text
Witness Projection Conformance v0.1
Microsoft Agent Framework WorkflowCheckpoint hosted boundary
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

Expected score: **8/8**.

## Why the checkpoint timestamp is not evidence

`WorkflowCheckpoint` has its own creation timestamp. That timestamp is useful checkpoint metadata, but the projection must not reinterpret it as the business deadline observation.

The decision-changing fact remains explicit in the witness itself:

```json
{
  "kind": "absence",
  "checked_at": 3000,
  "window": [1000, 3000],
  "deadline": 2500,
  "result": "no_response"
}
```

Changing only checkpoint creation time must not change the projected outcome.

## Interpretation

A PASS means Microsoft Agent Framework's native workflow checkpoint substrate can host the frozen witness contract without semantic loss or ambient-time replay dependence.

It does **not** mean:

- Agent Framework natively implements Witness Projection Conformance v0.1;
- every Agent Framework workflow is deterministic;
- checkpoint timestamps are trusted business observations;
- witness authenticity/completeness is proven;
- external side effects are replay-safe automatically.

It means the framework already provides the state/checkpoint machinery needed for a thin conformant integration.

## Reproduce

```bash
python -m unittest discover -s tools/tests -p 'test_ms_agent_framework_checkpoint_conformance.py' -v
```

Machine-readable expectation:

```text
benchmarks/ms-agent-framework-checkpoint-conformance-v0.1/result.json
```
