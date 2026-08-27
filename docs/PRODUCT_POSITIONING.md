# ContractGraph-QA Product Positioning

## Category

**Bounded verification for stateful financial systems.**

ContractGraph-QA is the evidence engine and umbrella brand. It should not be presented only as a Solidity tool or as a generic QA platform.

## Primary commercial wedge

### Ambiguous Outcome Recovery Verification

Buyer decision:

```text
After an ambiguous execution result:
ZERO    → retry may be allowed
ONE     → stop
UNKNOWN → block retry pending reconciliation
```

Primary systems:

- agent payments;
- payment orchestration;
- wallets and delegated credentials;
- payouts and vendor transfers;
- on/off-ramps;
- stablecoin and cross-chain operations;
- provider / rail / ledger reconciliation.

## Secondary product route

### Smart-Contract State-Machine Review

Primary systems:

- escrow;
- settlement;
- release / refund;
- fees and value conservation;
- role and authority transitions;
- exact-time boundaries;
- terminal states;
- replay and ordering.

The two routes share one engine but should not be mixed in the same cold outreach.

Assigned public issues and source-only leads can first enter through the **External Investigation Gate**. That intake product preserves an exact source subject, evidence state, blocker, and verification debt without pretending that native or CGQA execution already occurred. It is a bridge into the state-machine review, not a third commercial route to pitch in parallel.

## Primary ideal customer profile

| Buyer / champion | Trigger |
|---|---|
| Head of Payment Reliability | ambiguous outcomes, duplicate payment risk, reconciliation backlog |
| Head of Payments Engineering | new rail, retry redesign, fallback or orchestration change |
| Wallet / Stablecoin Infrastructure Lead | delegated authority, on-chain/off-chain divergence, replay |
| Principal or Staff Engineer | a specific cross-system invariant lacks reproducible evidence |
| VP Product, Payments | agentic payment launch needs an independently testable control boundary |
| CTO of an API-first fintech | one expensive state-transition risk needs bounded external pressure testing |

## Buying job

> Turn one costly financial promise into an explicit state/evidence contract, executable failure fixture, deterministic verdict, and exact retest.

The buyer purchases the result. ContractGraph-QA is operated as the verification engine underneath.

## Qualification rules

A strong lead has:

- one named financial or contract-state boundary;
- a public or authorized product signal;
- a concrete failure scenario that fits in one paragraph;
- at least one evidence surface to model;
- an identifiable product, engineering, reliability, or developer-relations owner;
- no competing active outreach thread from us.

## Productized-service packaging

### Design-partner pilot

- **Price:** $750 fixed;
- **Scope:** one named boundary;
- **Delivery target:** five business days after accepted inputs;
- **Communication:** async by default;
- **Retest:** one bounded in-scope retest;
- **Initial access:** public docs, synthetic traces, local fixture, or sandbox are sufficient.

The first paid pilots should optimize for learning and reusable fixtures, not for maximum scope.

## North-star metric

> Number of client recovery or state-machine boundaries accepted as useful, reproducible verification results.

Supporting funnel:

```text
qualified lead
→ substantive technical reply
→ boundary confirmed
→ fixture permission
→ paid pilot
→ accepted evidence pack
→ retest or expansion
```

## What not to optimize for yet

- number of CLI commands;
- universal provider coverage;
- a hosted multi-tenant dashboard;
- broad automatic invariant synthesis;
- stars without buyer conversations;
- unbounded claims of security or correctness.

## Repository metadata target

Suggested GitHub description:

> Evidence-first verification for payment retries, financial state machines, wallets, ledgers, and smart contracts.

Suggested topics:

```text
payment-reliability
agentic-payments
bounded-verification
financial-state-machines
idempotency
payment-reconciliation
wallet-security
smart-contract-testing
foundry
solidity
```

Repository settings are not part of the code review boundary and should be updated separately after the positioning PR merges.
