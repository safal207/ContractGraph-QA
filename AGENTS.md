# AGENTS.md — ContractGraph-QA Agent Verification Protocol

This file defines the required workflow for AI agents using ContractGraph-QA.

ContractGraph-QA is an independent verification layer. It does not replace the target repository's native tests, CI, code review, security review, or real integration testing.

## Core rule

> **Do not stop after the first PASS. Run every applicable ContractGraph-QA capability and explain why any capability was skipped.**

A PASS-like result is always bounded by the model, evidence, assumptions, adapter, subject identity, and executed search limits.

Never describe bounded exploration as a formal proof of production correctness.

## Required execution route

Use this order unless a step is genuinely not applicable:

```text
Discover
→ Exact Subject / Artifact Gate
→ Orientation Center
→ Native Mapping / Reviewed Adapter
→ Model
→ Invariants / Forbidden States
→ Causal Ancestry
→ Transition Geometry
→ Reachability / Stateful Search
→ Negative Control
→ Adversarial Sequences
→ Independent Witness / Pre-Post Evidence
→ Counterexample Minimization
→ Deterministic Replay
→ Native Regression
→ Verification Debt Review
→ Meaning Trajectory
→ Dormant Watchpoints
→ Temporal / External Replication where applicable
→ Forward Remediation where applicable
→ Final Evidence
```

Read [`docs/ORIENTATION_CENTER_AND_MEANING_TRAJECTORY.md`](docs/ORIENTATION_CENTER_AND_MEANING_TRAJECTORY.md) for the causal-temporal orientation model.

## 1. Discover production reality first

Before modeling, inspect the actual target system:

- assigned issue / specification;
- production implementation;
- tests;
- storage and persistence boundaries;
- actors and authorization rules;
- value flows and fees;
- timestamps/deadlines;
- replay identifiers;
- terminal states;
- CI configuration when relevant.

Do not derive production semantics only from issue prose or from a previous agent's summary.

Record the actual:

- states;
- transitions;
- actors / roles;
- authority boundaries;
- value movements;
- time boundaries;
- persistence boundaries;
- terminal states;
- failure paths.

## 2. Freeze the exact subject

Bind evidence to the strongest available subject identity:

- repository;
- exact commit SHA;
- branch/generation when relevant;
- adapter/model identity;
- workflow/artifact identity;
- business object identity;
- actor/authority context.

Do not accept label equality as exact identity.

Examples:

```text
same PR number != same PR head
same path != same object
same stream id != same stream generation
same key != same business operation
```

If exact subject identity cannot be established, keep the verdict bounded or `INCONCLUSIVE`.

## 3. Build the Orientation Center

For consequential reviews, record:

```text
exact subject
current state
branch/generation/history
causal ancestry
current authority
supporting evidence
counterevidence
unresolved verification debt
independent witnesses
active dormant/watchpoint causes
```

Use one of these readiness descriptions when useful:

- `BALANCED`
- `INDETERMINATE`
- `UNSTABLE`

`BALANCED` is not a truth or security verdict.

## 4. Build an independent model

Model the smallest state required to preserve the properties under review.

Do not blindly copy production control flow or arithmetic into the reference model.

For every important modeled field, ask:

> Could this model PASS while production remains broken because an important state dimension was omitted or because the model duplicated the bug?

Document intentional omissions.

## 5. Evaluate all applicable invariant families

At minimum consider:

### Safety

- forbidden transitions;
- double execution;
- terminal resurrection;
- mutation after failure/rejection;
- partial mutation after revert/error.

### Liveness

- terminal reachability;
- trapped escrow/custody;
- dead-end states;
- recovery convergence.

### Conservation

- principal;
- custody;
- payouts/refunds;
- fees;
- supply;
- cross-object subsidy and insolvency.

### Authorization

- correct/incorrect actor;
- actor binding;
- ownership changes;
- delegation/handoff;
- stale capabilities;
- use-time freshness.

### Replay / Idempotency

- exact replay;
- conflicting replay;
- duplicate terminal operation;
- lost-response retry;
- concurrency;
- restart durability;
- key/business/actor binding.

### Temporal boundaries

- before boundary;
- exactly at boundary;
- immediately after boundary;
- far after boundary;
- repeated operations after boundary.

### Crash / Recovery

- commit → crash;
- partial operation → crash;
- restart → retry;
- stale vs authoritative state;
- continuation vs revalidation.

## 6. Search explicit forbidden states

Do not rely only on expected happy paths.

Examples:

- value moved twice;
- terminal → active;
- unauthorized value movement;
- replay creates a second effect;
- stale approval authorizes a new workflow;
- funds become unreachable;
- evidence history regresses;
- rejected branch executes without fresh approval.

Each reachable forbidden state should be tied to an invariant and a reproducible path.

## 7. Check causal ancestry

A locally valid action can inherit invalidity from its ancestors.

Check for:

- stale parent reused;
- rejection superseding earlier approval;
- delegation without explicit authority handoff;
- memory-derived action without evidence origin;
- valid leaf under invalid thread root;
- remediation detached from the original fault chain.

Core law:

```text
local_PASS != effective_PASS
```

## 8. Run Transition Geometry where order can matter

Compare meaningful operation orders:

```text
B(A(X))
vs
A(B(X))
```

Look for:

- same semantic result but different causal/economic history;
- operation-order dependence;
- closed-loop drift;
- hidden value movement despite restored visible balance/state.

Do not treat path dependence as automatically invalid. Classify and explain it.

## 9. Negative control is required for meaningful oracle claims

Where feasible, introduce or model known-bad semantics and confirm that the verification layer detects them.

Examples:

- remove terminal guard;
- remove end-time cap;
- allow duplicate settlement;
- remove durable idempotency state;
- weaken actor binding;
- double-count a fee.

A verifier that cannot distinguish known-bad behavior from fixed behavior is weak evidence.

## 10. Adversarial sequences and property-based exploration

Prefer combinations of individually valid actions:

```text
settle → settle
settle → cancel
cancel → settle
update → expiry → settle
request → crash → retry
request(K,A) → request(K,B)
reject → retry → execute
restore → merge
```

Include boundary values such as zero, exact deadline, deadline ± 1, insufficient balance, maximum relevant value, empty/malformed inputs, and repeated identities.

Preserve deterministic seeds and search bounds.

## 11. Independent Witness

A ledger cannot prove its own completeness merely through internal consistency.

When the claim requires observation completeness, distinguish:

- observation-channel liveness;
- exact event coverage;
- exact subject/object coverage;
- witness independence.

Do not allow the same failed observation path to manufacture both the event and proof that no events were missed.

## 12. Minimize every real counterexample

Do not patch production first.

Reduce the failing trace while preserving the violation.

Record:

- seed;
- original sequence;
- minimized sequence;
- failing invariant;
- expected state;
- actual state;
- exact subject commit/model.

One deterministic minimal counterexample is stronger evidence than many unrelated passing cases.

## 13. Replay before claiming a defect

Re-run the minimized counterexample independently and deterministically.

A model-only failure should be reproduced against the real target boundary whenever feasible before it is described as a production defect.

## 14. Convert real defects to native regressions

Preferred path:

```text
CGQA counterexample
→ minimize
→ native RED regression in target repository
→ minimal fix
→ native GREEN
→ CGQA re-run
```

Do not add ContractGraph-QA as a production dependency unless explicitly requested.

## 15. Track verification debt

Do not collapse workflow state into verdict state.

Core distinctions:

```text
Unverified != Invalid
Deferred != Pruned
Admitted != Verified
Completed != PASS
```

If required verification is still pending, deferred, blocked, or not run, report that explicitly.

## 16. Track the Meaning Trajectory

For high-impact findings, preserve the evolution:

```text
signal
→ witness
→ evidence
→ cause
→ authority
→ transition
→ outcome
→ interpretation
→ memory
→ watchpoint
→ replication/drift
→ remediation
→ new orientation
```

History remains immutable even when interpretation changes.

Use explicit relations such as `REFINES`, `SUPERSEDES`, `SUPPORTED_BY`, and `CONTRADICTED_BY` where useful.

## 17. Preserve dormant causal patterns

If a dangerous pattern appears but does not yet meet all activation conditions, do not silently discard it.

Record it as a bounded watchpoint candidate with:

- observed shape;
- missing activation conditions;
- deterministic window/steps if possible;
- expected action if activated.

A watchpoint is not a prediction.

## 18. Re-verify across time when the claim requires it

Core law:

```text
Confirmed_t != Confirmed_t+1
```

Historical verification must not silently become permanent current authorization.

Where applicable, use fresh temporal/external evidence and preserve both the old confirmed result and any later drift signal.

## 19. Remediation must move history forward

Rollback/recovery must not erase the fact that the replaced state existed.

Core laws:

```text
ForwardRollback != HistoryRewrite
RecoveryChoice != ErasureOfFormerValidity
Drift != AutomaticRollback
```

Bind remediation to the fault/drift evidence that justified it.

## Capability matrix

Every final agent report MUST classify all applicable rows. No silent omissions.

| Capability | Status |
|---|---|
| Exact Subject / Artifact Gate | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Orientation Center | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Native Mapping / Adapter Review | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Safety Invariants | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Liveness / Reachability | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Financial Conservation | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Authorization / Capabilities | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Replay / Idempotency | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Temporal Lifecycle | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Crash / Recovery | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Causal / Ancestral Validity | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Transition Geometry | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Negative Control | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Stateful / Property Search | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Independent Witness | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Counterexample Minimization | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Deterministic Replay | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Native Regression | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Verification Debt | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Meaning Trajectory | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Dormant Patterns / Watchpoints | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Temporal / External Replication | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |
| Forward Remediation | RUN / NOT_APPLICABLE / BLOCKED / SKIPPED_WITH_REASON / NOT_RUN |

## Verdict discipline

Prefer bounded, explicit verdicts such as:

- `PASS_WITHIN_BOUND`
- `COUNTEREXAMPLE_FOUND`
- `BLOCKED`
- `MODEL_INCOMPLETE`
- `INCONCLUSIVE`
- `NOT_RUN`
- `REFLECTION_ONLY`

Never convert missing evidence, skipped execution, stale subject identity, or blocked verification into PASS.

## Evidence required in final reports

Include where available:

- target repository and exact commit;
- ContractGraph-QA commit/version;
- adapter/model identity and hash;
- seeds and search bounds;
- original/minimized traces;
- negative-control result;
- observed pre/post evidence;
- native regression location/result;
- CI truth;
- capability matrix;
- unresolved verification debt;
- coverage gaps.

## Completion gate

Before ending, answer:

1. What exact production subject was tested?
2. What is the Orientation Center and is it sufficiently resolved?
3. Which invariant families were checked?
4. Which forbidden states were searched?
5. Could the reference model be mirroring the production defect?
6. Was causal ancestry checked for consequential actions?
7. Was operation order/path dependence challenged?
8. Was a negative control performed where meaningful?
9. Were counterexamples minimized and replayed?
10. Were real defects reproduced as native regressions?
11. What verification debt remains?
12. What counterevidence or unresolved evidence exists?
13. Were any dormant/watchpoint patterns preserved?
14. Is the result historical only or temporally revalidated?
15. Can another reviewer reproduce the evidence independently?

If an applicable question has no answer, continue the investigation or keep the verdict explicitly bounded/unresolved.
