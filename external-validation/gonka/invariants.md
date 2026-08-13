# Gonka Verification Invariants v0.1

## I1 — Authorization before execution
A request that is not validly authorized must not cause inference execution, billable usage, escrow mutation, settlement mutation, or reward-side accounting effects.

Evidence: request/auth result, execution trace, pre/post escrow state, settlement state.

## I2 — Escrow precedes billable execution
A billable inference must be attributable to a valid devshard / escrow context. Rejected, expired, or unavailable escrow state must not produce an unintended billable mutation.

Evidence: devshard id, escrow state before request, request timestamp, execution/accounting outcome.

## I3 — One logical request, one billable effect
Retries, transport redelivery, gateway restarts, or duplicate submissions of the same logical operation must not create multiple independent billable effects unless the protocol explicitly defines them as distinct requests.

Evidence: logical_operation_id, execution attempts, request digests, accounting deltas, settlement references.

## I4 — Result and usage share causal identity
The returned inference result and the usage charged for it must be causally attributable to the same logical operation, model/executor context, and relevant protocol state.

Evidence: request/result digests, model metadata, executor/host references, usage record.

## I5 — Off-chain accounting matches observed execution
Usage accumulated off-chain must equal the protocol-defined charge for completed billable work and must exclude rejected or non-billable attempts.

Evidence: token/compute inputs, pricing parameters, usage accumulator before/after, request verdicts.

## I6 — Settlement matches accumulated usage
The on-chain settlement submitted for a devshard must reconcile with the authoritative off-chain usage state for that settlement interval.

Evidence: off-chain usage digest, settlement transaction/reference, on-chain pre/post balances or escrow state.

## I7 — Settlement finalization is idempotent
Replaying or retrying the same settlement intent must not debit the developer or credit recipients twice.

Evidence: repeated settlement attempts, transaction identifiers, pre/post balances, final state.

## I8 — Epoch rotation preserves accounting continuity
Rotating devshards or escrow across an epoch boundary must neither orphan valid unsettled usage nor settle it twice. New-epoch activity must not mutate the closed epoch's accounting unexpectedly.

Evidence: epoch N closing state, rotation event, epoch N+1 opening state, outstanding usage and settlement references.

## I9 — Reward claim obeys epoch and recovery semantics
A reward earned in epoch N must be claimed only according to the protocol's valid claim window and verification rules. Retryable failures must not silently convert into duplicate claims; terminal failures must produce an explicit non-success disposition.

Evidence: epoch id, seed commitment/reveal references where applicable, claim attempts, retry chronology, final chain state.
