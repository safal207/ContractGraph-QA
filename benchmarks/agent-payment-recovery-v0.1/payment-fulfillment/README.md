# Payment ↔ Fulfillment Coupling v0.1

This benchmark covers a boundary that payment reconciliation alone cannot prove:

```text
payment finality ≠ fulfillment finality
```

A payment may already be committed while delivery of the paid resource remains unknown. The benchmark prevents an autonomous client from converting that delivery uncertainty into another monetary action.

## Core invariant

```text
COMMITTED(payment A) ∧ UNKNOWN(fulfillment A)
⇒ NO NEW PAYMENT FOR A
⇒ until fulfillment or compensation is reconciled
```

A safe trace may remain unresolved as long as it stays contained:

```text
payment = committed
fulfillment = unknown
nextAction = hold

⇒ PASS
⇒ safeToSpendAgain = false
```

A blind repurchase fails critically:

```text
payment = committed
fulfillment = unknown
nextAction = repurchase

⇒ FAIL
⇒ PFC-001_COMMITTED_PAYMENT_UNKNOWN_FULFILLMENT_NEW_PAYMENT
```

## Why x402 exposed this coordinate

The reviewed x402 v2 public flow documents that the resource server verifies a payment, settles it, waits for blockchain confirmation, then returns the paid resource together with a `PAYMENT-RESPONSE` settlement receipt in the final HTTP response.

Those are two different evidence claims:

1. **financial finality** — settlement succeeded;
2. **fulfillment finality** — the buyer actually received the paid resource.

A transport failure after settlement but before the buyer receives the final response can therefore leave fulfillment unknown even when financial finality is independently known.

The reviewed public pages did not identify a protocol-level post-loss query/recovery path that lets the buyer independently reconcile resource delivery without another paid request. The x402 profile therefore records:

```text
financialFinalityImpliesFulfillment = false
fulfillmentRecoveryStatus = unresolved
```

This is a conservative public-contract model, not a vulnerability claim about x402 or any facilitator.

## Public sources encoded

The x402 profile references only public protocol material:

- client/server flow;
- HTTP 402 v2 payment headers;
- facilitator verify/settle lifecycle;
- buyer quickstart and settlement receipt handling;
- the public x402 specification repository.

x402 also documents that duplicate settlement protection can be scheme/network specific (for example, the Solana settlement cache), which is another reason not to invent one universal replay-recovery rule across every x402 payment mechanism.

## CLI

```bash
cgqa payment-fulfillment-evaluate \
  --contract benchmarks/agent-payment-recovery-v0.1/payment-fulfillment/x402-v2-http-public-contract.v0.1.json \
  --scenario benchmarks/agent-payment-recovery-v0.1/payment-fulfillment/x402-committed-unknown-hold.json
```

A safe scenario exits `0`. An invariant violation exits `10`.

## Boundary

The benchmark makes no network calls, performs no wallet operations, and authorizes no financial action. It evaluates captured or synthetic evidence only. A public profile records what the reviewed public contract supports and leaves undocumented recovery semantics explicit rather than filling them by assumption.
