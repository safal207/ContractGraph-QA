# Gonka Verification Execution Surface

Pinned upstream revision: `f040d0a5b5ef207a0c431894c9f9e2608f9d3073`.

## Primary execution target

Use Gonka's own local `devshard/testenv` Docker stack for G-001 and G-002.

The upstream testenv runs production `devshardd`, `devshardctl`, and `versiond` against local mock dependencies:

- mock-chain
- mock-dapi
- mock-openai
- versiond router / HA participants
- devshard gateway

This gives us a real protocol path without mainnet funds, public-user impact, or external credentials.

## Why local testenv is the first choice

It exposes the exact boundaries needed by CGQA:

`client -> devshardctl -> versiond/devshardd -> mock ML -> request accounting -> local chain state`

It also includes deterministic fault hooks and upstream integration coverage such as `TestGatewayChat` and adversarial fault scenarios. CGQA should reuse those mechanics while adding semantic operation correlation and reconciliation evidence.

## Secondary surfaces

### Community broker

Useful for a benign G-001 smoke test only when the broker's terms and access permit it.

Do not assume a broker exposes Gonka's internal `/v1/requests/{request_id}` accounting endpoint or allows intentional timeout/fault experiments. Broker behavior is not equivalent to protocol behavior.

### Community DevNet / External Test Lab

Useful after explicit access and scope are confirmed. It can provide independent multi-node evidence, but it is not required to implement the first reproducible G-001/G-002 slice.

### Self-hosted production gateway

Not a first-slice test target. Current production gateway creation requires an allowlisted on-chain creator address and real escrow funds. CGQA v0.1 does not need that risk or governance dependency.

## Safety rules

1. Prefer local `devshard/testenv` for fault injection.
2. Do not run destructive or ambiguity-inducing experiments against public production gateways.
3. Never use real funds for G-001/G-002 development.
4. Public brokers may be used only for normal requests unless their operator explicitly permits a stronger test scope.
5. Treat any financially relevant discrepancy as a private hypothesis until independently reproduced and responsibly disclosed.

## Execution ladder

1. **Contract guard** — verify that upstream still exposes the correlation/accounting primitives our profile depends on.
2. **G-001 local control** — one normal request, one terminal outcome, reconciled accounting evidence.
3. **G-002A local ambiguity** — disconnect/timeout after dispatch and retry with the same `X-Request-Id`.
4. **G-002B semantic retry** — retry with a new transport ID while CGQA preserves one `logical_operation_id`.
5. **Reconcile** — compare transport outcomes, execution nonces, winner/attempt costs, state deltas, and terminal disposition.
6. **Escalate only if needed** — repeat on an explicitly permitted Community DevNet or operator-owned gateway to determine whether a local finding survives a less synthetic environment.

## Decision rule

A local discrepancy is not automatically a vulnerability. It becomes a candidate `CGQA-GONKA-*` hypothesis only when:

- the behavior is reproducible;
- expected protocol semantics do not explain it;
- the evidence links user intent, transport attempts, execution nonces, accounting, and final state;
- an upstream control or documentation path does not already classify the behavior as expected.
