# AutoGen saved-state conformance benchmark

This benchmark applies `Witness Projection Conformance v0.1` to AutoGen's explicit agent state save/load boundary.

## Pinned upstream source

Repository: `microsoft/autogen`

Commit:

```text
027ecf0a379bcc1d09956d46d12d44a3ad9cee14
```

Observed source boundaries:

```text
python/packages/autogen-core/src/autogen_core/_agent.py
python/packages/autogen-core/src/autogen_core/model_context/_chat_completion_context.py
python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py
```

At the pinned commit:

- the core `Agent` protocol exposes `save_state()` and `load_state()`;
- saved agent state must be JSON serializable;
- `ChatCompletionContext.save_state()` serializes its ordered message list;
- `ChatCompletionContext.load_state()` restores that list;
- `AssistantAgent.save_state()` delegates to its model context and `load_state()` restores it.

The repository is in maintenance mode at this pinned head; the benchmark records the capability of this source snapshot and is not a recommendation to start a new project on AutoGen.

## Scope boundary

This benchmark does **not** claim AutoGen natively defines the domain-specific `sent / absence / response` state machine used by the conformance spec.

It measures a narrower capability:

> Can a thin AutoGen-compatible agent state store preserve an append-only witness log, including explicit absence/deadline evidence, through a JSON save/load round trip and replay the frozen projection without consulting wall-clock time?

The hosted state payload stores only witnesses:

```json
{
  "witnesses": [
    {"kind": "sent", "at": 1000, "deadline": 2500},
    {
      "kind": "absence",
      "checked_at": 3000,
      "window": [1000, 3000],
      "deadline": 2500,
      "result": "no_response"
    }
  ]
}
```

No derived decision and no evaluator `now` value is persisted.

## Expected result

```text
Witness Projection Conformance v0.1
AutoGen hosted saved-state boundary
CONFORMANT — 8/8

PASS  deterministic_across_evaluator_time
PASS  explicit_absence_enables_transition
PASS  replay_stability
PASS  prefix_stability
PASS  non_monotone_state_over_monotone_evidence
PASS  deadline_bound_to_evidence
PASS  missing_deadline_fails_closed
PASS  projection_does_not_mutate_evidence
```

## Why this is different from the CrewAI benchmark

The CrewAI benchmark evaluates the current native tool-event vocabulary and finds that the pinned boundary cannot represent an explicit absence/deadline witness by itself.

AutoGen exposes a generic persisted agent-state contract. That contract does not supply the domain semantics either, but it can carry the complete witness log without requiring a synthetic wall-clock-derived fact during replay.

So the result is a **hostability result**, like the LangGraph state/checkpoint benchmark:

- it means the framework can host the frozen contract cleanly;
- it does not mean every application built on the framework is conformant;
- application code can still violate the contract by reading ambient time/config or rewriting evidence.

## Reproduce

```bash
python -m unittest tools.tests.test_autogen_saved_state_conformance -v
```

Machine-readable expected result:

```text
benchmarks/autogen-saved-state-conformance-v0.1/result.json
```
