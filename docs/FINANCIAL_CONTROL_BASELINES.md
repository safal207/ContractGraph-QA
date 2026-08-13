# Financial Control Baselines v0.1

The repository already contains synthetic financial **failure examples** for escrow approval, stale authority, revoked authority, idempotency replay, and duplicate settlement. Those examples intentionally mark one control assumption as violated so the corresponding forbidden financial capability is reachable.

A customer-facing change gate needs the opposite starting point: a reviewed baseline where the same forbidden capability, transition, invariant, and control boundary remain explicitly modeled, but the control assumption is not declared broken.

This directory provides those safe baseline states.

## Why preserve the forbidden path shape?

The baseline does not delete or rename the dangerous security object. It keeps the exact causal vocabulary required for future PR comparison:

```text
allowed source capability
      ↓
security-sensitive transition
      ↓ guarded by a control assumption
forbidden financial capability
      ↓
invariant + control boundary + business impact
```

With the guard intact, the transition is not traversable. If a later PR declares or introduces evidence that the assumption is violated, the trusted change gate can report the newly reachable forbidden capability without inventing a new identity after the fact.

## Baseline pack

| Baseline | Guarded assumption | Forbidden capability | Invariant / boundary |
|---|---|---|---|
| Escrow approval | `approval-threshold-enforced` | `release-without-required-approval` | `escrow-release-requires-approval` / `approval-threshold` |
| Authority freshness | `authority-state-fresh` | `spend-under-stale-authority` | `payment-authority-must-be-current` / `authority-freshness` |
| Authority revocation | `revocation-propagated` | `spend-after-revocation` | `revoked-authority-cannot-spend` / `authority-revocation` |
| Idempotency continuity | `idempotency-identity-stable` | `create-second-payment-attempt` | `retry-must-preserve-idempotency` / `idempotency-continuity` |
| Settlement deduplication | `settlement-single-application` | `apply-duplicate-settlement` | `settlement-applied-once` / `settlement-deduplication` |

Every baseline has an empty `violatedAssumptions` array. The corresponding failure example keeps exactly one declared violation and therefore reaches the same forbidden target.

## Machine-readable profile

`financial-control-gate.toml` is a strict Change Gate configuration listing the five baseline models. The repository-wide `causal-security-gate.toml` now registers those same model IDs and exact paths after the baseline bytes have already landed in trusted `main` history.

The standalone financial profile remains useful as the compact product-facing control pack; the repository-wide profile is the actual trusted PR enforcement surface.

## Two-step onboarding is a security property

The trusted Change Gate fails closed when a newly configured model does not exist in the base commit. Therefore a new protected baseline cannot be introduced and registered as trusted history in one self-approving PR.

The safe rollout is:

```text
Phase A
merge reviewed baseline model bytes into main
        ↓
Phase B
register those existing base paths in causal-security-gate.toml
        ↓
trusted pull_request_target judge compares base ↔ candidate
```

Phase A and Phase B are intentionally separate changes. Once Phase B is merged, subsequent PRs that mutate any registered financial baseline are compared against trusted historical bytes from the base commit.

That prevents a candidate PR from simultaneously inventing both a new security baseline and the historical state it claims to preserve.

## What `not_found_within_bound` means

A safe baseline is expected to return `not_found_within_bound` for its declared forbidden target because the required assumption violation is absent. This is a bounded model result, not a proof that a production system is universally safe.

The baseline pack is local, deterministic, synthetic, and repository-owned. It makes no claim about any third-party payment provider, wallet implementation, RPC endpoint, or deployed contract.

## Intended pilot story

With trusted-gate registration in place, a financial-control pilot can demonstrate:

```text
reviewed safe baseline
→ PR weakens one control
→ forbidden capability becomes reachable
→ trusted gate BLOCKS with exact path
→ evidence artifact is preserved
→ guard is restored
→ historical path replay confirms the fix
→ PASS
```

That is the contract: not "the system is safe," but "this reviewed control state did not silently regress into a newly reachable forbidden financial capability without producing causal evidence."
