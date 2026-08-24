# Executable Orientation Capabilities v0.1

This document describes the first executable layer built on the agent protocol in `AGENTS.md` and the causal-temporal model in `ORIENTATION_CENTER_AND_MEANING_TRAJECTORY.md`.

The three commands are deterministic, provider-neutral evaluators. They do not replace native target tests or claim formal proof.

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

### Strict endpoint subject binding

Existing v0.1 models remain valid by default. For evidence assembled from independently produced endpoint receipts, enable:

```json
{
  "requirements": {
    "requireEndpointSubjectBinding": true
  }
}
```

Then `origin`, `aThenB`, `bThenA`, and `loop.returned` must each carry `subjectHash` equal to the canonical SHA-256 of the top-level `subject`. A foreign or missing receipt fails validation before geometry classification.

This prevents a correct-looking endpoint from another commit/object/generation from being compared as if it belonged to the verified subject.

The repository negative controls cover value/effect torsion, history divergence, `FLAT_LOOP`, `HOLONOMY`, `CURVATURE_DETECTED`, and foreign endpoint binding.

## 2. Ancestral Validity

```bash
cgqa ancestry --trace scenarios/ancestry-rejected-branch-reentry.json
```

The evaluator distinguishes:

```text
localValidity
effectiveValidity
```

Finding families include:

```text
STALE_PARENT
REJECTED_BRANCH_REUSE
MISSING_AUTHORITY_HANDOFF
INVALID_ROOT_INHERITANCE
MEMORY_WITHOUT_EVIDENCE_ORIGIN
REMEDIATION_WITHOUT_FAULT_LINK
FOREIGN_SCOPE_ANCESTOR
```

Structural trace gaps/cycles and a locally invalid target also fail closed.

The output additionally exposes:

```text
firstInvalidity
affectedDescendants
```

`firstInvalidity` is ordered by the causal boundary event's deterministic `occurredAt`, not alphabetically by finding code. `affectedDescendants` records the downstream target path whose effective validity inherits the first break.

The repository negative control contains a locally valid retry that points back to an earlier approval after a later rejection superseded that branch. The expected result is local validity with effective invalidity, with the rejection identified as the first invalidating boundary.

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
geometryResults
ancestryResults
requirements
```

Readiness classifications:

```text
BALANCED
INDETERMINATE
UNSTABLE
```

Examples:

- invalid ancestry, invalid authority, confirmed contradictory evidence, omitted expected counterevidence, or failed required verification -> `UNSTABLE`;
- unresolved counterevidence, missing required evidence/witness, deferred/blocked/not-run required verification, or geometry torsion/curvature requiring review -> `INDETERMINATE`;
- all declared requirements resolved without hard findings -> `BALANCED`.

### Subject-bound child receipts

Every supplied `geometryResults[]` or `ancestryResults[]` receipt must contain a `subjectHash` matching the Orientation Center subject. A foreign-subject receipt fails validation rather than being silently aggregated.

Optional requirements can make those child capabilities mandatory:

```json
{
  "requirements": {
    "requireGeometry": true,
    "requireAncestryReceipt": true
  }
}
```

`TORSION_DETECTED` or `CURVATURE_DETECTED` does not become a security failure; it keeps readiness non-BALANCED pending review. An ancestry receipt with `effectiveValidity=invalid` makes the center `UNSTABLE`.

To make counterevidence inventory explicit, `requirements.expectedCounterevidenceIds` can declare evidence IDs that must be present in the aggregate input. Missing declared counterevidence is a hard orientation-integrity finding.

The result always emits:

```json
{
  "securityVerdictAuthorized": false
}
```

`BALANCED` is a readiness statement only. It is not a truth, security, or safety verdict.

Core distinctions:

```text
Unverified != Invalid
Deferred != Pruned
Completed != PASS
TORSION_DETECTED != automatic defect
BALANCED != Secure
```

## Cross-capability gate

The Phase 1 integration path is now executable:

```text
exact subject
→ Transition Geometry receipt
→ Ancestral Validity receipt
→ subjectHash binding
→ Orientation Center
→ BALANCED / INDETERMINATE / UNSTABLE
```

A clean pair of subject-bound geometry and ancestry receipts can contribute to `BALANCED`. Geometry tension keeps the center `INDETERMINATE`; effective ancestry invalidity makes it `UNSTABLE`; mixed-subject receipts fail validation.

## Determinism and evidence boundary

All three evaluators:

- use canonical JSON hashing;
- emit deterministic sorted JSON through the existing `cgqa` dispatcher;
- fail validation on malformed or subject-mismatched input;
- use non-zero validation exit codes for `hold`/`fail` results;
- preserve explicit claim-boundary text in machine-readable output.

The current v0.1 layer evaluates normalized supplied observations. It does not yet automatically derive geometry endpoints, causal trace events, or Orientation Center evidence from Foundry/runtime captures. That adapter integration belongs to the next layer rather than being implied by Phase 1 readiness.
