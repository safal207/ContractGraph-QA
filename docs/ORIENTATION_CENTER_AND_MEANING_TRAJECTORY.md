# Orientation Center and Meaning Trajectory

ContractGraph-QA already verifies bounded reachable paths, explicit invariants, replayable evidence, reviewed adapter bindings, and provenance-bound artifacts. This document adds an agent-facing causal-temporal orientation layer over those existing mechanisms.

It is a verification discipline, not a claim that every concept below is already implemented as a first-class CLI feature.

## Core thesis

A state is not enough to verify a system.

For a consequential transition, correctness depends on more than the final value:

```text
Meaning(t)
  = ExactSubject
  × CausalHistory
  × TransitionPath
  × Authority(t)
  × Evidence(t)
  × WorldResponse
  × PreservedMemory
```

The verification question becomes:

> What exact subject is in this state, by what path did it arrive here, what authority is still valid now, what evidence and counterevidence apply to this exact point, and what did the external world actually confirm?

## 1. Orientation Center

Every investigation should maintain an explicit `OrientationCenter(t)`:

```text
OrientationCenter(t) = {
  exact_subject,
  current_state,
  branch_or_generation,
  causal_ancestry,
  authority_now,
  supporting_evidence,
  counterevidence,
  unresolved_verification_debt,
  independent_world_witnesses,
  dormant_patterns,
  active_watchpoints
}
```

Suggested readiness classifications:

- `BALANCED` — the declared causal context is sufficiently resolved to continue.
- `INDETERMINATE` — material evidence, counterevidence, provenance, or verification work remains unresolved.
- `UNSTABLE` — a causal-integrity failure is present, such as unresolved memory influence, broken ancestry, stale authority, or provenance loss.

`BALANCED` does not mean `TRUE`, `SAFE`, or `PASS`. It means the orientation context is coherent enough for the next verification step.

## 2. Causal transition spine through time

Use this as the default temporal graph:

```text
WORLD(t-1)
   ↓
SENSE / OBSERVE
   ↓
ORIENTATION CENTER O(t)
   ↓
PROPOSAL
   ↓
CAUSAL + AUTHORITY CHECK
   ↓
COMMIT
   ↓
EXECUTE
   ↓
EFFECT / PROOF-OF-NON-EFFECT
   ↓
INDEPENDENT WITNESS
   ↓
OUTCOME
   ↓
EVIDENCE
   ↓
INTERPRETATION
   ↓
MEMORY
   ↓
REPLICATION / WATCHPOINT
   ↓
DRIFT / ACTIVATION
   ↓
REMEDIATION
   ↓
WORLD(t+1)
   ↓
NEW ORIENTATION CENTER O(t+1)
```

Do not collapse these boundaries into one status field.

Examples of invalid collapses:

```text
accepted request != executed effect
executed effect != correct business outcome
completed verification != PASS
historical PASS != current authorization
reported execution != witnessed execution
same final state != same causal path
```

## 3. Transition Geometry

Locally valid operations do not imply path independence.

For operations `A` and `B`, compare:

```text
B(A(X))
vs
A(B(X))
```

Suggested classifications:

- `CLOSED` — same relevant semantic endpoint and equivalent required history.
- `HISTORY_DIVERGENT` — same semantic endpoint, but materially different causal history, authority, lineage, or receipts.
- `TORSION_DETECTED` — operation order changes a semantic, economic, security, or authorization dimension.

For intended closed loops:

```text
X → A → B → ... → X'
```

classify:

- `FLAT_LOOP` — semantic and relevant history return to the required origin condition.
- `HOLONOMY` — semantic state returns, but history legitimately advances.
- `CURVATURE_DETECTED` — the loop changes a semantic/economic/security dimension that was expected to close.

Core laws:

```text
Valid(A) + Valid(B) != Commute(A,B)
same observable result != same causal path
same balance != same value history
```

Useful contract examples:

```text
settle → cancel     vs cancel → settle
pause → naturalEnd  vs naturalEnd → pause
expire → retry      vs retry → expire
allocate → settle   vs settle → allocate
```

Path dependence is evidence. It is not automatically a defect. A bounded reviewer may classify it as `HOLD` when reconciliation or policy interpretation is required.

## 4. Ancestral Validity

A locally valid transition can inherit causal invalidity from an ancestor.

Always challenge:

- stale parent cause reused for a new workflow;
- previously rejected branch re-entered without fresh approval;
- delegated agent action without explicit authority handoff;
- memory-derived action whose evidence origin is unresolved;
- valid-looking leaf transition inside an invalid thread/root;
- remediation detached from the fault/responsibility chain it addresses.

Therefore:

```text
local_PASS != effective_PASS
```

For consequential transitions, walk the relevant ancestry and answer:

1. Is the root valid for this exact workflow?
2. Has any rejection or superseding decision invalidated the path?
3. Was authority explicitly delegated across actor boundaries?
4. Is the parent still fresh for the current context?
5. If memory influenced the action, can the source evidence be resolved?
6. If this is remediation, is the original fault still bound into the causal chain?

## 5. Exact subject and object identity

Labels are weaker than identity.

Use the strongest available binding:

```text
count coverage
  < event-id coverage
  < (event-id, exact subject/object-id) coverage
  < independent witness + exact object binding
```

General law:

```text
label equality < exact subject identity
```

Examples:

```text
same fd != same kernel object
same path != same object
same PR number != same PR head SHA
same stream id != same stream generation
same account label != same authority context
same idempotency key != same business operation
```

The target repository, commit, model, adapter, evidence artifact, actor, and business object should be bound as exactly as the available system permits.

## 6. Independent Witness

A ledger cannot prove its own completeness merely by containing internally consistent rows.

Where completeness matters, prefer an observation path with an independent failure domain.

Distinguish:

- aggregate liveness: was the observation channel alive at all?
- exact event coverage: were these exact consequential events observed?
- exact object coverage: did both sides refer to the same object/subject?
- provenance independence: could the same failed collector fabricate both the event and its supposed completeness witness?

Do not let an internal record prove the completeness of the same channel it is meant to validate.

## 7. Verification Debt

Verification work has a lifecycle separate from semantic verdicts.

Useful states:

```text
SUBMITTED
ADMITTED
DEFERRED
COMPLETED
```

Core distinctions:

```text
Unverified != Invalid
Deferred != Pruned
Admitted != Verified
Completed != PASS
```

Required unresolved verification debt forces `HOLD` or an equivalent unresolved verdict, not a false PASS and not an invented FAIL.

When verification capacity is finite, preserve every required deferred item explicitly. Do not silently drop work because another check passed.

## 8. Meaning Trajectory

Track how the meaning of a transition evolves without rewriting history:

```text
SIGNAL
→ WITNESS
→ EVIDENCE
→ CAUSE
→ AUTHORITY
→ TRANSITION
→ OUTCOME
→ INTERPRETATION
→ MEMORY
→ WATCHPOINT
→ REPLICATION
→ DRIFT
→ REMEDIATION
→ NEW ORIENTATION
```

A later interpretation may:

- `REFINE` an earlier interpretation;
- `SUPERSEDE` an earlier active reading;
- become `SUPPORTED_BY` new evidence;
- become `CONTRADICTED_BY` counterevidence.

But the source trace remains immutable.

Core rule:

```text
history is immutable
interpretation may evolve
```

Time should remain explicit where useful:

- `valid_time` — when the interpretation applies;
- `recorded_time` — when it was recorded;
- `reviewed_time` — when it was reviewed.

A later interpretation must not pretend it was known earlier.

## 9. Dormant Causal Patterns and Temporal Watchpoints

Not every important causal pattern is already an active failure.

A dormant pattern can be represented as:

```text
DormantPattern
  = observed_shape
  + inactive_status
  + activation_conditions
```

A temporal watchpoint adds an activation window:

```text
latent cause
+ time/ordered steps
+ matching conditions
→ activated causal concern
```

This is not prediction. It is conditional causal memory.

Suggested lifecycle:

```text
OBSERVED
→ DORMANT
→ WATCHING
→ ACTIVATED | EXPIRED
→ REVIEWED
→ PROMOTED_TO_REGRESSION
```

If adversarial exploration produces an almost-counterexample that fails only because one explicit activation condition is absent, preserve the pattern instead of discarding it as meaningless.

Document:

- first observed trace;
- missing activation conditions;
- deterministic activation window where possible;
- on-activation review/test action.

## 10. Temporal and External Replication

A PASS is historical evidence, not permanent authority.

Core law:

```text
Confirmed_t != Confirmed_t+1
```

For high-impact claims, consider:

```text
freeze exact confirmed subject
→ obtain genuinely fresh later/external evidence
→ score/replay without silently retraining assumptions away
→ detect stable result or drift
→ preserve old historical PASS
→ issue a new current interpretation/verdict
```

Freshness should be provenance-based. Renaming, rewrapping, or rehashing the same underlying evidence does not make it fresh.

## 11. Forward Remediation

Rollback must not erase history.

Avoid:

```text
State 8 failed
→ pretend State 7 was current all along
```

Prefer:

```text
State 7
  ↓
State 8
  ↓ later drift/failure evidence
remediation decision
  ↓
State 9 = selected topology/state from 7
          + new remediation evidence/history
```

Core laws:

```text
ForwardRollback != HistoryRewrite
RecoveryChoice != ErasureOfFormerValidity
Drift != AutomaticRollback
```

A remediation decision should remain causally linked to the fault/drift evidence that justified it.

## 12. Capability matrix for agent reviews

Every serious investigation should explicitly classify these capabilities:

| Capability | Allowed status |
|---|---|
| Orientation Center | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Transition Geometry | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Ancestral Validity | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Exact Subject/Object Identity | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Independent Witness | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Verification Debt | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Meaning Trajectory | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Dormant Patterns / Watchpoints | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Temporal / External Replication | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Forward Remediation | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |

No silent omissions.

## 13. Agent execution route

Use this as an orientation route on top of the existing ContractGraph-QA workflow:

```text
Exact Subject
    ↓
Orientation Center
    ↓
Causal Ancestry
    ↓
Native Mapping / Reviewed Adapter
    ↓
Invariants + Forbidden States
    ↓
Transition Geometry
    ↓
Adversarial Reachability / Stateful Search
    ↓
Independent Witness / Observed Pre-Post
    ↓
Counterexample or Verification Debt
    ↓
Minimize + Deterministic Replay
    ↓
Native Regression in target repository
    ↓
Meaning Trajectory
    ↓
Dormant Watchpoints
    ↓
Temporal Replication / Drift
    ↓
Forward Remediation
    ↓
New Orientation Center
```

## 14. Completion questions

Before ending an investigation, answer:

1. What exact subject and exact version/commit were verified?
2. What is the current Orientation Center state?
3. What ancestry authorizes the consequential transition?
4. Did operation order matter?
5. Could the same final state hide a different value/security history?
6. Was the observation path independent enough for the claim being made?
7. What verification debt remains unresolved?
8. What counterevidence exists?
9. Did any almost-counterexample deserve a dormant watchpoint?
10. Is the verdict historical only, or was later/fresh replication performed?
11. If remediation occurred, was history preserved rather than rewritten?
12. Can another reviewer reproduce the path and evidence from exact artifacts?

If an applicable question cannot be answered, keep the result bounded or unresolved rather than broadening the claim.
