# CrewAI tool-event conformance benchmark

This benchmark applies `Witness Projection Conformance v0.1` to the closest current CrewAI-native evidence boundary that exists in upstream source today.

## Pinned upstream source

Repository: `crewAIInc/crewAI`

Commit:

```text
f4731f5025f861c78e3af0487cc80bf5e7c64782
```

Observed source boundaries:

```text
lib/crewai/src/crewai/events/types/tool_usage_events.py
lib/crewai/src/crewai/agents/tools_handler.py
```

At that commit the tool lifecycle vocabulary includes:

```text
tool_usage_started
tool_usage_finished
tool_usage_error
tool_failure_detected
tool_validate_input_error
tool_selection_error
tool_execution_error
```

`ToolsHandler.on_tool_use(...)` is a post-use callback/cache handler. This benchmark does **not** claim that CrewAI already exposes the proposed replayable authorization reducer from crewAIInc/crewAI#5888.

## Why this boundary is still useful

The current tool events are the nearest native persisted/observable evidence vocabulary around tool execution. If that vocabulary cannot represent a required witness, a deterministic reducer cannot reconstruct that fact from these events alone later.

The adapter therefore uses only semantics present at the pinned source boundary:

```text
sent     -> tool_usage_started
response -> tool_usage_finished
absence  -> no native representation
```

It deliberately does not invent a timeout/absence event just to make the conformance test green.

## Result

Expected result:

```text
Witness Projection Conformance v0.1
CrewAI current tool-event evidence boundary
NOT CONFORMANT

PASS  deterministic_across_evaluator_time
FAIL  explicit_absence_enables_transition
PASS  replay_stability
PASS  prefix_stability
PASS  non_monotone_state_over_monotone_evidence
FAIL  deadline_bound_to_evidence
PASS  missing_deadline_fails_closed
PASS  projection_does_not_mutate_evidence
```

So the current boundary is **6/8**, with exactly two missing capabilities:

1. a recorded absence observation can change state;
2. the deadline/window used by that observation is bound into evidence.

This is narrower than saying "CrewAI is nondeterministic." The benchmark shows the opposite for the properties it can express: evaluator time does not affect the adapter, replay is stable, prefixes remain stable, and evidence is not mutated. The gap is representability of time-dependent absence evidence.

## Minimal contract delta

A future middleware/authorization layer can close this gap without making the projection read `now()`.

The observation step may read live time, but it should append a fact with semantics equivalent to:

```json
{
  "type": "tool_absence_observed",
  "checked_at": 3000,
  "window": [1000, 3000],
  "deadline": 2500,
  "result": "no_response"
}
```

The replayable decision layer then consumes that record. The exact event name is not normative; the recorded semantics are.

## Reproduce

```bash
python -m unittest tools.tests.test_crewai_tool_event_conformance -v
```

Machine-readable expected result:

```text
benchmarks/crewai-tool-event-conformance-v0.1/result.json
```

## Scope boundary

This benchmark does not evaluate:

- authorization policy correctness;
- whether CrewAI should persist these events in a particular store;
- witness authenticity or provenance;
- distributed event ordering;
- side-effect verification;
- a future implementation of the proposed middleware hook.

It answers one current-source question only: **can the pinned native CrewAI tool-event vocabulary, without invented fields or ambient clock reads, express the witnesses needed by Witness Projection Conformance v0.1?**
