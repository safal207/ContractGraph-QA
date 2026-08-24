# Executable Orientation Capabilities v0.1

This document describes the first executable layer built on the agent protocol in `AGENTS.md` and the causal-temporal model in `ORIENTATION_CENTER_AND_MEANING_TRAJECTORY.md`.

The three commands are deliberately small, deterministic, provider-neutral evaluators. They do not replace native target tests or claim formal proof.

## 1. Transition Geometry

```bash
cgqa geometry --model scenarios/geometry-settle-cancel.json
```

The input binds an exact subject, two named operators, an origin endpoint, and the observed endpoints for:

```text
B(A(X))
vs
A(B(X))
```

Each endpoint separates:

```text
state
 effects
 history
```

Pair classifications:

```text
CLOSED
HISTORY_DIVERGENT
TORSION_DETECTED
```

Optional closed-loop evaluation compares the origin with a returned endpoint and emits:

```text
FLAT_LOOP
HOLONOMY
CURVATURE_DETECTED
```

`TORSION_DETECTED` and `CURVATURE_DETECTED` produce `status=hold`. They show path dependence that requires review; they are not automatically labeled defects.

Core law:

```text
Valid(A) + Valid(B) != Commute(A,B)
same observable result != same causal path
```

The repository negative control intentionally makes `settle -> cancel` and `cancel -> settle` reach the same visible terminal state with different economic effects.

## 2. Ancestral Validity

```bash
cgqa ancestry --trace scenarios/ancestry-rejected-branch-reentry.json
```

The evaluator distinguishes:

```text
localValidity
effectiveValidity
```

Current finding families:

```text
STALE_PARENT
REJECTED_BRANCH_REUSE
MISSING_AUTHORITY_HANDOFF
INVALID_ROOT_INHERITANCE
MEMORY_WITHOUT_EVIDENCE_ORIGIN
REMEDIATION_WITHOUT_FAULT_LINK
```

Structural trace gaps/cycles and a locally invalid target also fail closed.

The repository negative control contains a locally valid retry that points back to an earlier approval after a later rejection superseded that branch. The expected result is local validity with effective invalidity.

Core law:

```text
local_PASS != effective_PASS
```

The evaluator does not claim the supplied trace is complete or independently witnessed. That remains a separate evidence boundary.

## 3. Orientation Center

```bash
cgqa orient --bundle scenarios/orientation-unresolved-debt.json
```

The input aggregates:

```text
exact subject
current state
ancestry status
current authority
supporting evidence
counterevidence
verification debt
independent witnesses
watchpoints
requirements
```

Readiness classifications:

```text
BALANCED
INDETERMINATE
UNSTABLE
```

Examples:

- invalid ancestry, invalid authority, confirmed contradictory evidence, or failed required verification -> `UNSTABLE`;
- unresolved counterevidence, missing required evidence/witness, or deferred/blocked/not-run required verification -> `INDETERMINATE`;
- all declared requirements resolved without hard findings -> `BALANCED`.

`BALANCED` is a readiness statement only. It is not a truth, security, or safety verdict.

The repository negative control preserves a required restart/replay verification item as `DEFERRED`, so the center remains `INDETERMINATE` rather than converting incomplete verification into PASS.

Core distinctions:

```text
Unverified != Invalid
Deferred != Pruned
Completed != PASS
BALANCED != Secure
```

## Determinism and evidence boundary

All three evaluators:

- use canonical JSON hashing;
- emit deterministic sorted JSON through the existing `cgqa` dispatcher;
- fail validation on malformed input;
- use non-zero validation exit codes for `hold`/`fail` results;
- preserve explicit claim-boundary text in machine-readable output.

The current v0.1 layer evaluates normalized supplied observations. It does not yet automatically derive geometry endpoints, causal trace events, or Orientation Center evidence from Foundry/runtime captures. That adapter integration is the next layer.
