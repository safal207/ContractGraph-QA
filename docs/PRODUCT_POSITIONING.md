# ContractGraph-QA Product Positioning

## Category

**Bounded verification for stateful financial systems.**

ContractGraph-QA is the evidence engine and umbrella brand. It should not be presented only as a Solidity tool or as a generic QA platform.

## Primary commercial wedge

### Recovery Design Partner Lab

The Lab is the capped commercial program for Ambiguous Outcome Recovery Verification. It co-creates one declared business/evidence contract with the buyer, then uses ContractGraph-QA to turn that contract into a bounded fixture, evidence pack, and retest.

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

> Co-create one costly financial promise as an explicit state/evidence contract, executable failure fixture, deterministic verdict, and exact retest.

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

### Recovery Design Partner Lab

- **Capacity:** maximum five design partners;
- **Price:** $750 fixed per one-boundary pilot;
- **Scope:** one named ambiguous-outcome recovery boundary;
- **Delivery target:** five business days after the Boundary Brief and required inputs are accepted;
- **Communication:** async by default;
- **Retest:** one bounded in-scope retest;
- **Initial access:** public docs, synthetic traces, local fixture, or sandbox are sufficient.

The client confirms the Promise, Evidence, and Decision checkpoints. ContractGraph-QA owns the bounded model, fixture, test execution, evidence pack, and explicit remaining uncertainty. The first paid pilots should optimize for useful product learning, not maximum scope.

## North-star metric

> Number of client recovery or state-machine boundaries accepted as useful, reproducible verification results.

Supporting funnel:

```text
question
→ mirror boundary
→ confirm Boundary Brief
→ paid fixture
→ evidence pack
→ bounded retest
→ product learning
```

## From client pattern to product pack

A pilot remains client-specific by default. A repeated pattern becomes a reusable-pack candidate only when every gate below passes:

1. **Repeat:** the same invariant, evidence, and decision shape appears in at least two separately scoped client boundaries. A single request or shared provider label is not enough.
2. **Abstract:** the useful part can be expressed as a vendor-neutral state/evidence contract, invariant set, synthetic scenario, violation code, and acceptance check.
3. **Rebuild:** core fixtures use repository-owned synthetic evidence or separately authorized public material, not copied client artifacts.
4. **Verify:** the candidate pack has a negative control, deterministic replay, bounded coverage, and an explicit assurance statement.
5. **Separate:** generic interfaces may live in core; client-specific status mappings, authority choices, private schemas, endpoints, credentials, configuration, traces, and adapters stay in the client-controlled or private engagement layer.
6. **No implied endorsement:** do not publish a client name, material, result, compatibility claim, or validation claim without explicit permission and separate supporting evidence.

Promotion preserves the reusable recovery pattern, not the client's integration. A retest or successful pilot does not automatically promote anything into core.

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
