# ContractGraph-QA Recovery Design Partner Lab

## One-boundary ambiguous-outcome recovery pilot

- **Capacity:** maximum **5 design partners**
- **Price:** **$750 fixed per one-boundary pilot**
- **Scope:** one named ambiguous-outcome recovery boundary
- **Delivery target:** five business days after the Boundary Brief and required inputs are accepted
- **Communication:** async by default
- **Retest:** one bounded retest for an in-scope fix delivered within 14 calendar days

The pilot is designed to reduce buying friction without presenting ContractGraph-QA as a formal full-platform security audit.

## Working sequence

```text
question
→ mirror boundary
→ confirm Boundary Brief
→ paid fixture
→ evidence pack
→ bounded retest
→ product learning
```

The [one-page Recovery Boundary Brief](BOUNDARY_BRIEF.md) freezes three async client checkpoints before the fixture is treated as confirmed: **Promise**, **Evidence**, and **Decision**. Missing or conflicting authority remains `UNKNOWN`; silence is not approval.

## Good targets

- agent-payment retry after timeout;
- wallet dispatch with uncertain execution;
- payout reconciliation across provider, rail, and ledger;
- payment-orchestration fallback;
- on/off-ramp fiat and crypto legs;
- stablecoin mint, burn, bridge, or cross-chain reconciliation.

Core decision:

```text
ZERO    → retry may be allowed
ONE     → stop
UNKNOWN → block retry pending reconciliation
```

## Included

- explicit authorization and scope boundary;
- action, actor, identity, and state-transition model;
- up to five prioritized invariants or recovery obligations;
- one executable local or sandbox-backed fixture;
- bounded state or sequence exploration;
- shortest reproducible path for each discovered violation;
- classification as `violated`, `not_found_within_bound`, or `inconclusive`;
- client-readable report plus machine-readable evidence;
- deterministic evidence bundle and verification command where applicable;
- one bounded retest.

## Inputs

- exact workflow, contract, or feature in scope;
- repository, documentation, schemas, or synthetic traces;
- expected roles, identities, statuses, and business rules;
- authorization reference for any active non-local testing;
- the highest-value property the team wants protected.

Production credentials, customer data, and real-value transactions are not required for an initial documentation, local-fixture, or sandbox-backed pilot.

## Not included

Unless separately agreed, the pilot excludes:

- whole-platform or whole-protocol audit coverage;
- unbounded or exhaustive verification;
- cryptographic design review;
- broad economic or game-theoretic analysis;
- unauthorized production testing;
- live exploitation or fund movement;
- unlimited retesting or open-ended consulting.

## Deliverable shape

```text
confirmed Boundary Brief
→ expected-state / recovery contract
→ bounded fixture and search
→ deterministic outcomes
→ minimal counterexample
→ evidence map and report
→ fix
→ exact retest
```

A clean bounded result is described as `not_found_within_bound`, never as a blanket claim that the target is secure.

## Expansion path

A useful pilot can expand into:

1. broader invariant or scenario coverage;
2. additional providers, rails, wallets, ledgers, or recovery boundaries;
3. authorized integration or fixed-block testing;
4. regression-suite hardening;
5. CI evidence gates;
6. recurring release verification.

Smart-contract state-machine review remains a separate product route and is not bundled into this Lab offer.

[Canonical Lab scope and learning questions](../../PILOT.md) · [Boundary Brief](BOUNDARY_BRIEF.md) · [Synthetic Recovery Case Study](../case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md) · [Discuss a Lab boundary](mailto:safal0645@gmail.com?subject=ContractGraph-QA%20Recovery%20Design%20Partner%20Lab)
