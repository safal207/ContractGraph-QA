# Unified Agent Payment Decision Gate v0.1

The gate answers one operational question:

> May the agent make the next monetary action now?

It composes four independent claims already modeled elsewhere in ContractGraph-QA:

```text
AUTHORITY
→ PAYMENT FINALITY
→ RETRY AUTHORITY
→ FULFILLMENT FINALITY
→ DECISION
```

Possible decisions are deliberately small:

- `ALLOW` — a monetary action is authorized by the currently proven state;
- `HOLD` — do nothing financial because authority is unresolved;
- `STOP` — the logical operation is complete, revoked, expired, or retry is not authorized;
- `RECONCILE` — collect discriminating evidence before any new monetary action;
- `COMPENSATE` — resolve refund/compensation disposition before repurchase.

## Core rules

```text
UNKNOWN(authority)                       → HOLD
REVOKED/EXPIRED(authority)               → STOP
NONFINAL(payment)                        → RECONCILE
FAILED(payment) + UNRESOLVED(retry)      → HOLD
FAILED(payment) + DOCUMENTED(retry=true) → ALLOW
COMMITTED(payment) + UNKNOWN(fulfillment)→ RECONCILE
COMMITTED(payment) + NOT_DELIVERED       → COMPENSATE
COMMITTED(payment) + DELIVERED           → STOP
AUTHORIZED + NOT_STARTED(payment)        → ALLOW
```

The important boundary is that **finality never creates authority by itself**. A failed payment can be final while retry remains unauthorized; a committed payment can be final while fulfillment remains unknown.

## CLI

```bash
cgqa agent-payment-decision \
  --input benchmarks/agent-payment-recovery-v0.1/unified-decision/examples/reconcile-ambiguous.json
```

The command exits `0` for a structurally valid decision, including safe `HOLD`, `STOP`, `RECONCILE`, and `COMPENSATE` outcomes. Exit `10` is reserved for malformed/contradictory decision inputs.

## Composition boundary

This gate does not call provider APIs and does not invent provider semantics. Upstream components remain responsible for normalizing evidence:

- Provider Adapter → payment finality + retry authority;
- Payment Recovery Benchmark → ambiguity containment;
- Payment ↔ Fulfillment Coupling → fulfillment state.

The gate only applies precedence between already-normalized safety claims. It is research-only and does not grant production financial authority.
