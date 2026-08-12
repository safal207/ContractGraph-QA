# Agent Payment Recovery Benchmark v0.1

**Vendor-neutral, evidence-first recovery QA for autonomous payments.**

This benchmark tests one narrow question:

> After a financial execution becomes ambiguous, can any further monetary action occur before the earlier logical operation is reconciled to an evidence-backed state?

It is designed for programmable wallets, agent wallets, x402-style payment flows, payout APIs, stablecoin rails, and other systems where an autonomous agent can cause a financial state transition.

It does **not** contain provider-specific logic and it does not claim that any named provider is vulnerable.

## Canonical path

```text
intent
  ↓
authority
  ↓
logical_operation_id
  ↓
execution attempt
  ↓
financial submit
  ↓
AMBIGUOUS OUTCOME
  ↓
CONTAIN
  ↓
RECONCILE EVIDENCE
  ↓
committed / failed / pending / unknown
  ↓
retry / stop decision
  ↓
evidence-preserving outcome
```

## Core invariant

```text
AMBIGUOUS(payment A)
  ⇒
NO NEW FINANCIAL ACTION
  UNTIL
RECONCILED(payment A)
```

`pending` and `unknown` are not reconciliation completion. They remain fail-closed states.

## Identity model

The benchmark deliberately separates:

- `logicalOperationId` — the semantic payment operation across retries;
- `executionId` — one concrete attempt;
- `idempotencyKey` — replay/deduplication identity when the integration contract requires it.

A retry should be a **new execution attempt** under the same logical operation. When the benchmark policy requires idempotency continuity, the retry must retain the same key.

## Evidence surfaces

`reconcile` is provider-neutral and can name any stable evidence surface, for example:

- `status_lookup`;
- `history`;
- `webhook`;
- `onchain`;
- `receipt`;
- `same_key_replay` when a provider explicitly documents that replay as a canonical reconciliation mechanism.

The benchmark does not decide which surface is canonical for a provider. That precedence must come from the provider's public contract or an authorized engagement.

## Run

```bash
cgqa payment-recovery-evaluate \
  --scenario benchmarks/agent-payment-recovery-v0.1/cases/pass_committed_stop.json
```

A passing scenario exits `0`.

A valid scenario that violates one or more benchmark invariants prints a deterministic result and exits `10`.

## Seed cases

### PASS — committed, then stop

```text
authorize
→ submit(exec-1, idem-A)
→ timeout / ambiguous
→ status lookup = committed
→ stop
```

### PASS — failed, then retry same operation identity

```text
authorize
→ submit(exec-1, idem-A)
→ ambiguous
→ webhook = failed
→ retry(exec-2, retryOf=exec-1, idem-A)
```

### FAIL — retry before reconciliation

```text
authorize
→ submit
→ ambiguous
→ retry
```

Critical invariant violation: `APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION`.

### FAIL — idempotency drift on retry

```text
authorize
→ submit(idem-A)
→ ambiguous
→ history = failed
→ retry(idem-B)
```

Critical invariant violation: `APR-004_IDEMPOTENCY_CHANGED_ON_RETRY`.

## Result model

Every result includes:

- benchmark and scenario identifiers;
- `pass` / `fail`;
- deterministic score;
- critical-failure flag;
- per-invariant booleans;
- machine-readable violation codes;
- unresolved logical operations;
- explicit research-only authority boundary.

A critical failure caps the score at `49`, matching the broader ContractGraph-QA principle that a severe containment failure cannot be averaged away by otherwise clean checks.

## Scope boundary

This benchmark evaluates the **trace supplied to it**. It does not prove that:

- the provider emitted every relevant event;
- the selected evidence surface is authoritative;
- a webhook or status endpoint is itself correct;
- a blockchain observation has reached the provider's required finality;
- a payment system is secure in general.

Those questions belong in adapter review, source-contract analysis, or an explicitly authorized engagement.

## Safety

The seed suite is fully local and performs no network calls and no financial action.

Do not point custom tooling at production payment systems without authorization. Prefer sandbox, repository-owned fixtures, public documentation analysis, or an explicitly authorized bounded environment.
