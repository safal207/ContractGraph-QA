# OpenEscrow partial-funding liveness benchmark v0.1

This benchmark captures a source-grounded reachability finding against the public OpenEscrow repository without making a claim of a full independent audit.

## Source pin

- Upstream: `omslice/OpenEscrow`
- Commit: `0ed38ea3192e0248ba8d1d77e85f0a8b83192a3e`
- Contract: `contracts/OpenEscrow.sol`
- Git blob: `07d47a2fc7ef94bf0a2f29400fba3a8ace3224e6` (`40,609` bytes)
- Public testnet/demo scope only in the upstream project.

## Verification boundary

This is a source-reviewed, deterministic reachability model for the exact
commit and blob above. The model was checked against the contract's funding,
proposal-cancellation, no-claim, and withdrawal entry points. It does not embed
or execute the upstream Foundry suite, prove deployed bytecode identity, observe
live funds, or claim a full audit. "Permanent" is bounded to the transitions
available to the funded tenant in this pinned lifecycle when the remaining
tenant and landlord both stop progressing it; upgrades or external intervention
are outside the model.

## Observed lifecycle

The current contract permits a multi-tenant agreement to remain `ReadyToFund` after one tenant has already funded its required share. The funding function records that contribution into both `depositAmount` and `locked`; the phase advances to `Active` only when total deposits equal `agreedAmount`.

A stalled partially funded agreement has no funded-tenant-controlled refund transition:

- `cancelProposal` may refund partial contributions, but only the landlord may call it;
- `withdraw` requires `Closed` or `Cancelled`;
- `withdrawNoClaim` requires `Active` and an expired claim window;
- there is no funding deadline or tenant-initiated partial-funding timeout.

Therefore, if a remaining co-tenant never funds and the landlord never cancels, an already-funded tenant's principal can remain locked indefinitely in `ReadyToFund`.

## Minimal causal path

```text
ReadyToFund
  ↓ first tenant funds
ReadyToFund + depositAmount>0 + locked>0
  ↓ remaining tenant stops + landlord does not cancel
PERMANENT PRINCIPAL LOCK
```

The machine-readable reachability model is `scenarios/openescrow-partial-funding-lock.json`.

## Invariant

`funded-tenant-unilateral-recovery`

> Once a tenant's principal has entered escrow before full activation, the lifecycle must preserve a unilateral, time-bounded path by which that tenant can recover its own contribution if the other required participants stop progressing the agreement.

## Expected result

- function-level accounting: can remain internally conserved;
- aggregate solvency: can remain intact;
- lifecycle liveness: **FAIL** under stalled co-tenant + stalled landlord assumptions;
- direct theft: not demonstrated;
- impact: indefinite principal lock / griefing;
- suggested severity: **Medium** as a lifecycle/security-design issue; economic severity is reduced by the upstream project's explicit testnet-only scope.

## Why this benchmark matters

This is a useful ContractGraph-QA case because no single function needs to be locally incorrect. `fundTenantShare` can correctly receive and account for the first contribution, and `cancelProposal` can correctly refund it when the landlord cooperates. The failure appears only when future reachable states are evaluated from the partially funded state and the required external actors stop cooperating.
