# Gonka Verification Invariants v0.1

## I1 — Authorization before execution
A request that is not validly authorized must not cause inference execution, billable usage, escrow mutation, settlement mutation, or reward-side accounting effects.

Evidence: request/auth result, execution trace, pre/post escrow state, settlement state.

## I2 — Escrow precedes billable execution
A billable inference must be attributable to a valid devshard / escrow context. Rejected, expired, or unavailable escrow state must not produce an unintended billable mutation.

Evidence: devshard id, escrow state before request, request timestamp, execution/accounting outcome.

## I3 — Logical operation identity survives retries
A stable `logical_operation_id` represents the semantic user operation across retries/re-drives. Each concrete transport/execution attempt has its own `execution_attempt_id`.

A timeout or lost response is **ambiguous** unless evidence proves non-execution. Recovery must not silently reinterpret a transport retry as an unrelated new intent. If multiple executions are protocol-permitted, their usage/billing effects must be explicitly distinguishable and reconcilable.

Evidence: logical_operation_id, execution_attempt_ids, request digests, transport outcomes, accounting deltas, settlement references.

## I4 — Result and usage share causal identity
The returned inference result and the usage charged for it must be causally attributable to the same logical operation, model/executor context, and relevant protocol state.

Evidence: request/result digests, model metadata, executor/host references, usage record.

## I5 — Off-chain accounting matches observed execution
Usage accumulated off-chain must be explainable from observed billable work and exclude rejected/non-billable attempts. No hidden duplicate, orphan, or unrelated usage mutation may remain after reconciliation.

Evidence: execution observations, pricing inputs, usage accumulator before/after, request verdicts.

## I6 — Settlement matches accumulated usage
The on-chain settlement submitted for a devshard must reconcile with the authoritative off-chain usage state for that settlement interval.

Evidence: off-chain usage digest, settlement transaction/reference, on-chain pre/post balances or escrow state.

## I7 — Settlement retry converges
If a settlement submission result is ambiguous, retry/recovery must converge on one explainable terminal financial state. Already-applied chain state must be recognized rather than blindly duplicated.

Evidence: repeated settlement attempts, transaction identifiers, confirmation state, pre/post balances, final state.

## I8 — Epoch rotation preserves accounting continuity
Rotating devshards or escrow across an epoch boundary must neither orphan valid unsettled usage nor settle it twice. Pending usage must have one authoritative settlement owner.

Evidence: epoch N closing state, rotation event, epoch N+1 opening state, outstanding usage and settlement references.

## I9 — Reward claim obeys epoch and recovery semantics
A reward earned in epoch N must be claimed only according to the protocol's valid claim window and verification rules. Retryable failures must not silently convert into duplicate claims; terminal failures must produce an explicit non-success disposition.

Evidence: epoch id, claim attempts, retry chronology, verification prerequisites, final chain state.

## Evidence rule

A functional 2xx response alone is insufficient to establish these invariants. Verification should capture enough evidence to reconstruct:

`intent -> attempt(s) -> execution observation -> usage/accounting delta -> settlement/recovery -> terminal disposition`

Every FAIL remains a hypothesis until the environment, source revision, reproduction, and evidence are pinned.