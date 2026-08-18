# ASTRA Transition Intelligence v0.1

ASTRA is an experimental prioritization and interpretation layer for ContractGraph-QA.

It does **not** replace deterministic bounded exploration, invariant checks, replay, or evidence verification. The existing explorer remains the baseline. ASTRA scores transitions that are already inside the reviewed model and highlights where a path begins to accelerate toward a risky or inconsistent state.

## Core model

For one transition, ASTRA computes:

```text
TPS = stimulus
    * state_complexity
    * future_pressure
    * witness_gap
    * divergence
    * 100
```

Every component is explicit and normalized to `[0, 1]`.

- `stimulus` — pressure introduced by retry, timeout, time advance, role change, external settlement, revocation, or another modeled trigger.
- `state_complexity` — how many causally relevant state planes or liabilities the transition touches.
- `future_pressure` — how strongly the transition expands or approaches risky future reachability.
- `witness_gap` — lack of independent evidence for the resulting state.
- `divergence` — observed inconsistency between primary state, mirrors, accounting, receipts, balances, or other reviewed state planes.

TPS is an interpretation score, not a vulnerability severity score and not a proof by itself.

## Failure gradient

For an ordered bounded path:

```text
DeltaTPS(t) = TPS(t) - TPS(t-1)
```

ASTRA reports:

- first material acceleration;
- first crystallized transition (`TPS >= 85`);
- peak transition and peak TPS.

The phase labels are:

```text
A     low pressure / amorphous
M     mixed or unstable
M_UP  mixed and materially accelerating
C     crystallized high-pressure state
```

A `C` phase still does not bypass the normal ContractGraph-QA finding requirements. It is a prioritization signal for focused replay, invariant evidence, and causal review.

## Verifier reflection

Before promoting a high-pressure path to a target candidate, ASTRA can fail closed on unresolved verifier assumptions:

```text
wrong_clock_model
missing_witness
stale_execution_artifact
state_plane_ambiguity
model_precondition_unproven
```

If any flag is true, the ASTRA verdict is `VERIFIER_FAIL`, even when TPS is high.

This is intentionally aligned with the Gonka protocol-time lesson: a verifier must not convert a wrong causal model into an upstream defect claim.

## CLI

Example input:

```json
{
  "material_acceleration": 5.0,
  "transitions": [
    {
      "id": "request",
      "stimulus": 0.7,
      "state_complexity": 0.7,
      "future_pressure": 0.7,
      "witness_gap": 0.7,
      "divergence": 0.7
    },
    {
      "id": "ambiguous-timeout",
      "stimulus": 0.9,
      "state_complexity": 0.9,
      "future_pressure": 0.9,
      "witness_gap": 0.9,
      "divergence": 0.9
    },
    {
      "id": "duplicate-settlement",
      "stimulus": 1.0,
      "state_complexity": 1.0,
      "future_pressure": 1.0,
      "witness_gap": 1.0,
      "divergence": 1.0
    }
  ],
  "verifier_reflection": {
    "wrong_clock_model": false,
    "missing_witness": false
  }
}
```

Run:

```bash
cgqa astra-transition --input astra-path.json
```

## Safety and interpretation

ASTRA v0.1 is deliberately an overlay.

It must not:

- invent transitions outside the reviewed model;
- turn high TPS into a security finding without invariant/replay evidence;
- replace bounded-search outcome semantics;
- hide `inconclusive` evidence;
- override authorization boundaries;
- interpret correlation as idempotency;
- interpret wall-clock delay as protocol liveness without a proven clock model.

The intended pipeline is:

```text
DETERMINISTIC BOUNDED MODEL
        ↓
LEGAL TRANSITIONS
        ↓
ASTRA TPS / FAILURE GRADIENT
        ↓
CAUSAL FOCUS
        ↓
NORMAL CGQA INVARIANT + REPLAY + EVIDENCE
        ↓
VERIFIER REFLECTION
        ↓
CLIENT-VERIFIABLE FINDING
```

## Next experimental increments

Potential follow-ups, each gated separately:

1. state-plane descriptors and independent witness bindings;
2. state-hash suspicion when causally different states collide under one hash;
3. causal-locality weighting after the first meaningful divergence;
4. pressure-guided exploration with deterministic BFS retained as an independent baseline;
5. evidence-bundle binding for TPS inputs and recomputation.
