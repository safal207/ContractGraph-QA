# GLOBAL P1-8 — Compatibility and Migration Replay

Status: **reference/conformance contract**. This document does not claim merge,
deployment, production persistence, external effects, or upstream adoption.

## Scope

P1-8 closes the next transition after independent P1-7 replay:

```text
exact source subjects
    -> contract observations
    -> current compatibility control
    -> unsupported-new rejection
    -> source-preserving recovery
    -> cross-repository compatibility receipt
```

The bounded surface is deliberately limited to the existing exact subjects:

- ProofPath authorization-record schema `v0.1`;
- LiminalDB protocol `1.0.0`, commands schema, and events schema;
- RINSE Kairos/LiminalDB receipt `v0.1` and reflection graph `v0.2`;
- the canonical `intent -> proofpath -> cml -> liminaldb -> rinse -> contractgraph_qa`
  route from the frozen RESONANCE interoperability fixture.

The matrix also binds a CML route fixture so that compatibility evidence does not
silently remove a hop from the P1-7 chain.

## Policy

The current policy is `EXACT_CURRENT_REVISION_ONLY`:

1. Current source subjects are accepted only when their exact schema/version,
   route, strictness, and authority boundary match the pinned observations.
2. Candidate ProofPath `v0.2`, LiminalDB protocol `1.1.0`, and RINSE receipt
   `v0.2` cargo is rejected as unsupported. No implicit coercion, field dropping,
   or silent downgrade is performed.
3. A route reorder is rejected before a compatibility receipt can be emitted.
4. Any candidate that raises execution, mutation, or external-effect authority
   is rejected.
5. For every rejection, the original canonical source payload is recovered and
   its digest must remain identical. Recovery is evidence replay, not a write.

This is a migration boundary, not a claim that the candidate revisions exist or
are supported. A future migration may be admitted only by adding an explicit
versioned adapter and new exact subjects; the current machine path stays closed
until then.

## Receipt contents

The independent verifier emits one `cgqa.p1-8-compatibility-receipt.v0.1` with:

- exact Git revision and committed blob for every subject;
- SHA-256 subject-set fingerprint;
- observed contract identities and strictness;
- accepted current control and every rejected candidate;
- source and recovered payload digests for rejected cases;
- explicit `write_performed=false` and fail-closed authority flags;
- receipt digest and an outer replay witness digest.

The verifier checks these fields from raw checkouts. It does not import a
producer-side compatibility implementation or accept a precomputed green
summary as proof.

## Negative surface

The unit and workflow suites cover:

- unsupported ProofPath, LiminalDB, and RINSE revisions;
- route reordering;
- authority escalation;
- receipt digest tamper;
- duplicate subject identity;
- exact revision mismatch;
- committed-blob/worktree tamper;
- recovery digest drift.

All cases remain conformance-only. No merge, deployment, production ledger
mutation, or external side effect is performed.
