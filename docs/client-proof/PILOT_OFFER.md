# ContractGraph-QA Design-Partner Pilot Offer

## Bounded verification for one stateful financial promise

**Price:** **$750 fixed**  
**Scope:** one named recovery boundary or one narrowly defined smart-contract state machine  
**Delivery target:** five business days after accepted scope and inputs  
**Communication:** async by default  
**Retest:** one bounded retest for an in-scope fix delivered within 14 calendar days

The pilot is designed to reduce buying friction without presenting ContractGraph-QA as a formal full-platform security audit.

## Choose one track

### Track A — Ambiguous Outcome Recovery

Good targets:

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

### Track B — Smart-Contract State-Machine Review

Good targets:

- escrow release / refund;
- settlement and fee conservation;
- deposit / withdrawal accounting;
- role and authority transitions;
- deadline and exact-time behavior;
- terminal-state exclusivity;
- replay, ordering, or retry behavior.

## Included

- explicit authorization and scope boundary;
- chain-neutral source investigation record when executable access is not ready;
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

A source-bound investigation record may establish the exact property, finding, evidence readiness, blocker, and next transition before the executable fixture is ready. It does not replace the included fixture, bounded execution, and retest unless scope is explicitly redefined.

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
scope
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
2. additional providers, rails, wallets, ledgers, or contracts;
3. authorized integration or fixed-block testing;
4. regression-suite hardening;
5. CI evidence gates;
6. recurring release verification.

[Primary Recovery Pilot](../../PILOT.md) · [Synthetic Recovery Case Study](../case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md) · [Discuss a pilot](mailto:safal0645@gmail.com?subject=ContractGraph-QA%20Design-Partner%20Pilot)
