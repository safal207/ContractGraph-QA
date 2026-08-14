# Fractal Causal Refactoring Protocol (FCRP) v0.2

FCRP v0.2 is an **additive** evidence-contract upgrade over v0.1. It does not replace `cgqa.fcrp-case.v0.1` and does not claim autonomous root-cause discovery, theorem proving, or production change authority.

Its purpose is narrower:

> Make the boundaries discovered by FCRP's own self-tests machine-readable before a causal explanation is accepted.

## Why v0.2 exists

The first self-tests exposed several classes of divergence that a simple causal path alone cannot represent safely:

```text
SELF-001  test evidence proved the wrong boundary
SELF-002  local PASS did not preserve a parent invariant
SELF-003  wall-clock time was confused with protocol-time
SELF-005  branch capability was confused with canonical reality
SELF-006  historically verified evidence was confused with current applicability
SELF-007  provenance identity was confused with semantic compatibility identity
SELF-008  domain interpretation was confused with shared semantic authority
SELF-009  evidence maturity was confused with authorization portability
```

v0.2 takes the generic lessons from those cases without hard-coding any one repository's domain model.

## Additive contract

```text
IdeaContract
├── purpose
├── expectedOutcome
├── invariants[]
├── forbiddenOutcomes[]
├── dependencies[]
└── parentContract

Evidence[]
├── kind
├── ref
├── claim
├── strength
└── mayGrantAuthority = false

TimeModel
├── domains[]
├── primaryDomain
├── causalAdvanceRequired
└── causalAdvanceEvidenceRefs[]

CausalPath
├── symptomPoint
├── FirstMeaningfulDivergence
├── causePoint
└── selectedRefactorPoint

Simulation
├── PASS | FAIL | NOT_REQUIRED
├── checkedSurfaces[]
└── evidenceRefs[]

Authorization
├── evidenceMayGrantAuthority = false
├── mutationAuthorized
├── authorizationRef
└── authorityBoundary

Verification
├── local
├── upward
├── evidenceRefs[]
└── stopConditions
    ├── parentInvariantsPreserved
    ├── crossBoundaryEffectsAbsent
    ├── causalPropagationStopped
    └── causalExplanationComplete
```

## Evidence strength is not authority

v0.2 recognizes five evidence-strength classes:

- `OBSERVED`
- `RECOMPUTABLE`
- `ATTESTED`
- `PROVENANCE_ONLY`
- `SYNTHETIC`

They describe **how a claim is supported**, not what a system is permitted to do.

Every evidence item therefore carries:

```text
mayGrantAuthority = false
```

and the case-level authorization boundary separately requires:

```text
evidenceMayGrantAuthority = false
```

A mutation can be represented as authorized only when `mutationAuthorized=true` and a distinct `authorizationRef` is supplied.

This means:

```text
FCRP decision = PASS
```

can coexist with:

```text
mutationAuthorized = false
```

`PASS` means the causal/refactor case satisfies the protocol contract. It does **not** mean the agent has permission to execute the proposed change.

## Typed time

v0.2 makes time semantics explicit:

- `WALL_CLOCK`
- `PROTOCOL_CLOCK`
- `CAUSAL_SEQUENCE`
- `REPOSITORY_HISTORY`

If a transition requires a causal state-advance event, the case must set:

```text
causalAdvanceRequired = true
```

and bind evidence showing that the advance actually occurred.

This directly encodes the lesson from the Gonka G-004P / FCRP-SELF-003 investigation: elapsed seconds cannot substitute for an event that advances protocol state.

## Simulation is evidence-bearing

A simulation marked `PASS` requires evidence references. A `FAIL` simulation blocks the FCRP decision even when local and upward verification are otherwise green.

This does not claim exhaustive future prediction. It only prevents an unbound statement such as "the fix should be safe" from being treated as a completed simulation step.

## The fourth stop condition

The original FCRP article required four conditions before upward verification can stop:

```text
parent invariants preserved
AND
no affected cross-boundary dependency
AND
causal propagation stopped
AND
explanation complete
```

v0.1 encoded only three of these explicitly.

v0.2 adds:

```text
causalPropagationStopped
```

If upward verification is `NOT_REQUIRED`, **all four** conditions must be true.

## FCRP-V02-PORT-001

The first v0.2 portability case consumes the canonical result of LiminalOSAI `FCRP-SELF-009`:

```text
safal207/LiminalOSAI@f84888a943c71041f7c31b41d70d592ad60b2157
```

SELF-009 proved that even a synthetic external-review state with maximum evidence maturity (`EEW=100/100`) transfers no execution authority.

The v0.2 case preserves that boundary across repositories:

```text
review evidence
      ↓
stronger evidence maturity
      ↓
FCRP PASS
      ↓
mutationAuthorized = false
```

Case:

`benchmarks/fcrp-v0.2/FCRP-V02-PORT-001-liminalosai-authority.json`

Binding tests:

`tools/tests/test_fcrp_v02.py`

## Compatibility

v0.1 remains unchanged in:

`contractgraph_qa/fcrp.py`

v0.2 lives separately in:

`contractgraph_qa/fcrp_v02.py`

No existing v0.1 case is silently reinterpreted as v0.2.

## Still outside v0.2

FCRP v0.2 still does not provide:

- autonomous recovery of `IdeaContract` from arbitrary repositories;
- autonomous causal graph discovery;
- deterministic Refactor Score ranking among competing repair points;
- exhaustive state-space simulation;
- production mutation authority;
- cross-repository transactionality;
- formal proof that all causal propagation has stopped.

Those are future research directions, not implied capabilities of this release.

## Core principle

```text
Understand != Authorize
Evidence != Authority
Elapsed time != Causal progress
Historical identity != Current compatibility
Local PASS != System PASS
```

FCRP v0.2 turns those distinctions into a stricter machine-readable causal contract.
