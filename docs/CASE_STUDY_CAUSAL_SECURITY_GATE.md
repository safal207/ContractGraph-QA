# Case study: BLOCK → verified fix → PASS

ContractGraph-QA's Causal Security Gate is designed to answer a narrow but expensive pull-request question:

> Did this change make a forbidden capability reachable, or did it actually remove a previously demonstrated path to that capability?

This repository contains a live two-PR canary demonstration of both sides of that decision.

## What the gate protects

The gate evaluates repository-owned reachability models from a trusted base context. The candidate pull request supplies model data, but it does not supply the Python judge that decides its own result.

```text
trusted base code
      ↓
exact base SHA + exact candidate SHA
      ↓
causal reachability delta
      ↓
new forbidden reachability? ── yes → BLOCK + exact path + evidence
      ↓ no
historical forbidden path removed?
      ↓ yes
exact historical replay
      ↓
old path blocked + no alternate path?
      ├─ no  → BLOCK
      └─ yes → FIX VERIFIED → PASS
```

The evidence artifact is produced before enforcement and is also bound into the client proof pack.

## Red canary: an unsafe payout becomes reachable

[PR #37](https://github.com/safal207/ContractGraph-QA/pull/37) intentionally introduced a new forbidden capability without changing the ordinary configured target list:

```text
advance-state-machine
  → canary-bypass-payout-authorization
  → canary-unauthorized-payout
```

The trusted gate discovered the new forbidden capability from the complete forbidden-capability snapshot and returned:

| Field | Observed result |
|---|---|
| Gate status | `blocked` |
| Gate reason | `new_forbidden_reachability` |
| Forbidden target | `canary-unauthorized-payout` |
| Invariant | `canary-payout-authorization` |
| Boundary | `canary-payment-boundary` |
| Introduced transition | `canary-bypass-payout-authorization` |
| Trusted gate run | `31661020759` |
| Evidence artifact | `causal-security-gate-37` |
| Artifact SHA-256 | `9369ca3cbd5f082bdfc3a46cc6cd9d4c98e4938735fa0846271126f6c01f9c0d` |

The workflow still uploaded machine JSON and client-readable proof evidence; only the final enforcement step failed, which is the intended behavior for an unsafe PR.

## Green canary: restore the authorization guard

[PR #38](https://github.com/safal207/ContractGraph-QA/pull/38) used the red canary commit as its non-main base. It preserved the historical forbidden target, transition identity, source/target identity, invariant and boundary. The only material security change was restoring a dedicated authorization guard:

```text
canary-payout-authorization-intact
```

That guard is not violated in the candidate model. The gate therefore did more than observe that the target disappeared from a fresh bounded search: it replayed the exact historical transition sequence against the candidate state.

| Field | Observed result |
|---|---|
| Gate status | `pass` |
| Graph delta | `risk_reduced` |
| Historical replay | `fix_verified` |
| Exact block reason | `assumption_guard_restored` |
| Missing violated assumption | `canary-payout-authorization-intact` |
| Blocked transition | `canary-bypass-payout-authorization` |
| Alternate reachability | `false` |
| Historical target still present | `true` |
| Historical target still forbidden | `true` |
| Trusted gate run | `31661372388` |
| Evidence artifact | `causal-security-gate-38` |
| Artifact SHA-256 | `a13401d97aa6b0efa2f54a1977877dd993cee7564dd3dec430b076dbc614a12c` |

The final enforcement step succeeded.

## Why this is stronger than a normal regression test

A normal regression test can tell you that one expected example now passes or fails. This demo binds the decision to the causal security object that matters:

```text
change
→ capability transition
→ forbidden target
→ invariant / control boundary
→ evidence
→ exact historical replay
→ alternate-path search
→ decision
```

The fix is not accepted by deleting the historical target, relabeling it as allowed, shrinking the search bound, or merely breaking the previously recorded transition ID. The target must remain the same forbidden security object, the historical path must actually be blocked, and no alternate path to the same target may remain within the model.

## Trust boundary

The gate runs through `pull_request_target` from the exact trusted base. Candidate content is checked out separately as data-only input. Trusted Python performs the comparison, summary rendering and client-proof binding; the candidate checkout is not used as `PYTHONPATH` and candidate Python/shell/build logic is not executed by the gate.

This matters because a security gate that lets the candidate change its own judge is not an independent gate.

## What this demo proves — and what it does not

This is a repository-owned synthetic canary, not an external audit and not a claim of exhaustive reachability over arbitrary production systems. It demonstrates the mechanics and evidence contract of the change gate under a controlled financial-capability scenario.

The two canary PRs are intentionally kept out of `main`:

```text
unsafe PR #37 → BLOCK → evidence
                       ↓
              authorization guard restored
                       ↓
fix PR #38 → exact historical replay → FIX VERIFIED → PASS
```

That is the product loop: detect a dangerous capability regression before merge, preserve the exact causal evidence, and require a machine-verifiable fix rather than a narrative claim.