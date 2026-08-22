# Successor Consistency Verification

ContractGraph-QA verifies the composition invariant:

> one conflict-domain parent state version may produce at most one distinct committed child commit.

This is the executable form of `CGQ-CONS-001 — SINGLE_VALID_SUCCESSOR_PER_STATE_VERSION` and benchmark `CGQ-B004 — Valid Functions, Invalid Composition`.

## Why function tests are insufficient

Two operations can each be locally valid when authorized against the same parent snapshot:

```text
Funded@v7 → deliver      → Delivered@v8
Funded@v7 → raiseDispute → Disputed@v8
```

If both commits are accepted, each function may have behaved correctly in isolation while the composed state machine has forked from one committed parent version.

The required protection is normally an atomic compare-and-set, optimistic version check, serialized commit boundary, or equivalent state-version binding.

## Run

```bash
cgqa successor-consistency --model scenarios/conflicting-successors-same-parent-version.json
```

The canonical B004 fixture returns `status=fail` because the same `(conflictKey, parentState, parentVersion)` has two distinct committed `commitId` values.

## Model semantics

Each observation declares:

- `eventId` — evidence-row identity;
- `commitId` — stable identity of the actual committed child;
- `conflictKey` — logical object/domain whose successor commits are mutually exclusive;
- `parentState` and `parentVersion` — committed parent snapshot;
- `operation` — operation that attempted the transition;
- `successorState` and `successorVersion` — resulting child state/version;
- `committed` — whether that child commit actually became authoritative.

Repeated observations of the same `commitId` are deduplicated. A pending or rejected competing attempt does not create a violation. A violation requires more than one distinct committed child for the same conflict-domain parent state version.

## Evidence output

The result includes:

- deterministic model SHA-256;
- committed observation count;
- distinct committed child count;
- checked parent-version domains;
- every conflicting child commit and successor;
- a deterministic minimal two-event counterexample.

## Claim boundary

The verifier is exact over the normalized commit evidence supplied to it. It does not prove that every commit source was captured or that authorization itself was complete. Extraction/capture completeness is a separate provenance claim.

## Relationship to other engines

- lifecycle liveness asks whether locked value can still reach safe termination;
- economic cardinality asks whether one logical effect slot settled more than once;
- successor consistency asks whether one committed parent version forked into multiple authoritative children.

Together these cover three different ways a system can pass function-level tests while failing at lifecycle or composition level.
