# Synthetic Case Study — Ambiguous Vendor-Payment Recovery

**Purpose:** show the exact shape of an Ambiguous Outcome Recovery Pilot without making a claim about any named payment provider.

This is a repository-owned synthetic scenario. No production system, real customer data, or real-value transfer is involved.

## Business promise

A finance agent is allowed to pay invoice `INV-782` once.

```text
one authorized invoice-payment intent
→ at most one vendor credit
```

The system must not release a second transfer while the first attempt remains unresolved.

## Scenario

```text
logicalOperationId = invoice-payment:INV-782
amount = USD 250
policy = ALLOW
executionId = exec-1
idempotencyKey = idem-INV-782
```

The agent dispatches the transfer. The API response times out after the provider accepts the request.

At that moment:

- the provider API response is ambiguous;
- the customer ledger records `pending`;
- the destination-rail receipt is not yet available;
- a webhook may arrive late, twice, or out of order;
- the agent is capable of retrying.

The dangerous path is:

```text
dispatch(exec-1)
→ timeout
→ outcome unresolved
→ retry(exec-2)
→ two economic effects become possible
```

## Evidence surfaces

The fixture models four evidence surfaces:

| Surface | What it may prove | What it does not automatically prove |
|---|---|---|
| Provider status lookup | Provider-side lifecycle state | Final destination credit or customer-ledger convergence |
| Webhook | A provider event was emitted | Exactly-once delivery or cross-system settlement |
| Destination-rail receipt | External transfer outcome | Correct local ledger state |
| Customer ledger | Internal accounting state | External settlement unless declared authoritative |

The pilot requires an explicit precedence rule. Arrival time alone is not evidence authority.

## Recovery classification

### Case A — authoritative failure

```text
dispatch(exec-1, idem-INV-782)
→ timeout
→ provider status = failed
→ destination receipt = no credit
→ classify ZERO
→ retry(exec-2, retryOf=exec-1, idem-INV-782)
```

Expected verdict: **PASS**. Retry may proceed under the same logical operation and declared policy.

### Case B — external success, stale local state

```text
dispatch(exec-1, idem-INV-782)
→ timeout
→ destination receipt = credited
→ customer ledger = pending
→ classify ONE
→ block retry
→ converge local ledger
```

Expected verdict: **PASS** only when the second monetary action is blocked and local recovery converges without paying again.

### Case C — no authoritative close-out

```text
dispatch(exec-1, idem-INV-782)
→ timeout
→ provider status = processing
→ webhook absent
→ destination receipt absent
→ customer ledger = pending
→ classify UNKNOWN
→ retry attempted
```

Expected verdict: **FAIL** with `APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION`.

### Case D — duplicate and out-of-order webhook

```text
webhook(processing, updatedAt=T2)
→ webhook(processing, updatedAt=T2)  # duplicate
→ webhook(accepted, updatedAt=T1)    # older state arrives later
```

Expected verdict: duplicate delivery creates no duplicate economic action, and the older event does not regress the authoritative state.

### Case E — idempotency drift

```text
dispatch(exec-1, idem-INV-782)
→ timeout
→ authoritative failure
→ retry(exec-2, idem-NEW)
```

Expected verdict: **FAIL** with `APR-004_IDEMPOTENCY_CHANGED_ON_RETRY` when the declared integration contract requires continuity.

## What the pilot delivers

```text
declared business promise
→ expected-state contract
→ evidence-precedence map
→ executable fixture
→ deterministic verdicts
→ minimized unsafe trace
→ remediation guidance
→ exact retest
```

A client receives:

- the `ZERO / ONE / UNKNOWN` state machine;
- explicit logical-operation, execution, idempotency, and authority identities;
- test cases for timeout, duplicate, delayed, out-of-order, retry, and stale-state paths;
- machine-readable outcomes and violation codes;
- a client-readable findings report;
- one bounded retest after an in-scope fix.

## Buyer value

The result answers a decision the team can act on:

> What exact evidence permits retry, what exact evidence requires stop, and what unresolved state must remain held?

That reduces two opposing risks:

- **duplicate value movement** from retrying too early;
- **stuck or abandoned operations** from never resolving a safe retry.

## Claim boundary

This case study proves only the shape and semantics of the repository-owned fixture.

It does not claim:

- that a named provider is vulnerable;
- that every relevant event was emitted;
- that one evidence surface is authoritative for every integration;
- that bounded testing proves the whole payment platform correct or secure.

[Read the pilot offer](../../PILOT.md) · [Run the executable benchmark](../../benchmarks/agent-payment-recovery-v0.1/README.md)
