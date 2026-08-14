# Fractal Causal Refactoring Protocol (FCRP) v0.1

FCRP is a small machine-readable contract for reasoning about a defect across **scale, time, causality, and intent** before accepting a repair.

The core question is not only:

> Where did the symptom appear?

It is:

> Where did the observed trajectory first meaningfully diverge from the idea and invariants of the system, and what is the smallest repair point with sufficient causal leverage?

## v0.1 boundary

FCRP v0.1 is **not** an automated root-cause oracle, theorem prover, or production change authorizer.

It validates that a causal-refactoring case makes the following coordinates explicit and internally coherent:

```text
scope + idea
     ↓
past / present / future
     ↓
causal path
     ↓
first meaningful divergence
     ↓
cause point
     ↓
selected refactor point
     ↓
local verification
     ↓
upward verification or justified stop
```

The executable evaluator lives in:

```text
contractgraph_qa/fcrp.py
```

## Fractal navigation

The same contract can be used at different scales:

```text
product
  → service
    → component
      → function
        → state transition
          → test invariant
```

Navigation is explicit:

- `DOWN` — the current level explains the symptom but not the mechanism;
- `UP` — a local observation is caused by a higher-level contract, intent, or system assumption;
- `SIDEWAYS` — a dependency or sibling system carries the relevant cause;
- `STOP` — the causal explanation is complete at the current boundary.

FCRP does not require the symptom point, cause point, and refactor point to be identical.

## Time model

Every case carries:

- `past` — how the relevant state or decision arose;
- `present` — what is actually true now;
- `future` — the intended post-repair trajectory.

This prevents a locally correct change from being accepted without considering the trajectory it creates.

## Upward verification

A local repair is insufficient by itself.

An FCRP case must either record upward verification as `PASS`, or mark it `NOT_REQUIRED` only when all stop conditions are true:

```text
parentInvariantsPreserved = true
crossBoundaryEffectsAbsent = true
causalExplanationComplete = true
```

This encodes the rule:

> Search for mechanism downward, search for context upward, repair at the point of causal leverage, and verify both locally and upward until the change no longer propagates.

## FCRP-SELF-001

The first executable case applies FCRP to ContractGraph-QA itself:

```text
benchmarks/fcrp-v0.1/FCRP-SELF-001.json
```

The target is the provider-evidence external-digest regression test in PR #49.

### Idea

The test must prove that a valid evidence pack with the wrong separately supplied digest fails **because of the external digest boundary**.

### Symptom

The original test could remain green while not proving that boundary.

### First meaningful divergence

The test fixture used an invalid placeholder evidence pack.

That meant the test could raise `ProviderDecisionEvidenceError` later during schema validation even if external digest checking disappeared.

### Refactor point

The repair is at fixture/assertion construction, not in the production verifier:

```text
valid evidence pack
+ guaranteed-different external digest
+ exact "external digest mismatch" assertion
```

### Executable verification

`tools/tests/test_fcrp_self_001.py` does two things:

1. evaluates the machine-readable FCRP causal case;
2. replays the real provider-evidence invariant with a valid pack and incorrect external digest.

The existing focused regression test in `tools/tests/test_canonical_json_types.py` is corrected in the same way.

## Relationship to existing ContractGraph-QA machinery

FCRP is intentionally thin. It composes with existing components rather than replacing them:

```text
FCRP
  → chooses causal coordinates and repair boundary

reachability / graph delta / historical replay
  → prove path changes and forbidden-state behavior

provider/payment evaluators
  → execute domain semantics

evidence packs
  → preserve replayable evidence

trusted causal gate
  → enforce selected repository invariants
```

Future versions may add deterministic scoring for competing refactor points, parent/child scale contracts, cross-project propagation, and evidence-bound simulation results. v0.1 deliberately starts with the smallest contract that can be tested against the repository itself.
