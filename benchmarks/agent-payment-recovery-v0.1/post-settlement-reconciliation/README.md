# Astra Post-Settlement Reconciliation Fixture v0.1

This fixture isolates one post-decision causal boundary:

```text
PAYMENT ATTEMPT
  → CLAIMED RESULT
  → ACTUAL SETTLEMENT / FINALITY
  → RECEIPT
  → RESOURCE / OUTCOME DELIVERY
  → RECONCILIATION
```

The narrow question is:

> When settlement and delivery are independently evidenced, can a downstream reconciliation surface still remain absent or unknown without being misclassified as payment or delivery failure?

This is intentionally **post-decision**. It does not evaluate spend policy, mandate validity, pre-execution authorization, or whether a payment should have been approved.

## Core invariant

```text
SETTLEMENT = ESTABLISHED
AND DELIVERY = ESTABLISHED
AND RECONCILIATION = UNKNOWN

⇒ do not rewrite settlement as failed
⇒ do not rewrite delivery as failed
⇒ do not claim reconciliation succeeded
⇒ preserve the unresolved downstream state explicitly
```

The corresponding Astra state is:

```text
financial_effect = ESTABLISHED
buyer_visible_delivery = ESTABLISHED
receipt_binding = PARTIAL_OR_UNKNOWN
reconciliation = UNKNOWN
```

`UNKNOWN` is a first-class outcome, not a failure synonym.

## Public evidence fixture

`coinbase-bazaar-solana-2026-09-15.v0.1.json` records two already-published x402/CDP Solana-mainnet observations from the public x402 issue tracker.

The source report states that both calls:

- used the current JavaScript x402 stack (`2.23.0`);
- settled 5000 atomic USDC to the same payee;
- had `meta.err = null` on Solana;
- returned HTTP 200 to the buyer;
- retained top-level `resource` plus `extensions.bazaar` in a capture-before-send through the same x402 client path;
- passed Coinbase validation before settlement;
- produced empty facilitator extension-response objects (`{}`) on both verify and settle;
- still had `payToRows: 0` in the canonical Bazaar lookup at the published T+10 minute checkpoint.

Public source comments:

- https://github.com/x402-foundation/x402/issues/3284#issuecomment-5675671394
- https://github.com/x402-foundation/x402/issues/3284#issuecomment-5678803463

The two public settlement signatures are:

```text
5Rf6x6o4XqtVH34dBKCfbAtdpfy2Kq5HcuzAb7v1osbKtxCChDrzDo74wfNbmA3YGRHBu8izjBn37djDaUpZ6TXd
4RnXctJeiDZ1ooSStfWnLSo8ixiyBhwLLVMCA4gyuSTFZRq4oYoS9WY3uWtn5KcDjtdTXbtDtJx1PzTPf399BY1R
```

## What is established vs not established

### Established by the cited public report

- two distinct paid resource calls;
- successful on-chain settlement as reported with exact transaction signatures and slots;
- 5000 atomic USDC transferred per call;
- HTTP 200 delivery for each call;
- valid live 402 challenge/validation path;
- no visible Bazaar row at the T+10 minute checkpoint;
- no facilitator-exposed Bazaar success/processing/rejected/job state in the recorded extension responses.

### Not established by this fixture

- Coinbase's internal ingestion job state;
- whether a later T+24 or T+48 lookup becomes indexed;
- an exact buyer-visible response-body digest;
- a `PAYMENT-RESPONSE` receipt/body hash binding for these two calls;
- that the missing catalog row is a vulnerability or financial-loss condition;
- that settlement caused the discovery symptom;
- that every Solana/CDP/x402 resource behaves this way.

Therefore the fixture classifies the boundary as:

```text
SETTLEMENT          ESTABLISHED
DELIVERY            ESTABLISHED
RECEIPT BINDING     PARTIAL / UNKNOWN
BAZAAR RECONCILIATION UNKNOWN at published T+10m checkpoint
ROOT CAUSE          UNKNOWN
```

## Read-only recheck

`recheck_public.py` is deliberately incapable of making a payment. It only:

1. performs a public GET against the Bazaar `discovery/resources?payTo=` surface;
2. optionally performs Solana JSON-RPC read calls for the already-known transaction signatures;
3. writes a checkpoint JSON to stdout or a local file.

It contains no wallet key handling, signing, settlement request, facilitator `/verify`, or facilitator `/settle` call.

Example:

```bash
python benchmarks/agent-payment-recovery-v0.1/post-settlement-reconciliation/recheck_public.py \
  --fixture benchmarks/agent-payment-recovery-v0.1/post-settlement-reconciliation/coinbase-bazaar-solana-2026-09-15.v0.1.json \
  --output /tmp/astra-bazaar-checkpoint.json
```

If public network access is unavailable, the script records the access failure rather than fabricating an empty catalog.

## Decision rule for future checkpoints

For T+24 / T+48 observations:

```text
catalog row appears
  → RECONCILIATION = ESTABLISHED_LATE

catalog remains empty
  → RECONCILIATION = STILL_UNRESOLVED

request fails / response cannot be verified
  → RECONCILIATION = UNKNOWN
```

Only an authoritative provider-side statement or observable public state should distinguish `NOT_ATTEMPTED`, `REJECTED`, `PROCESSING`, or another internal ingestion state.

## Outreach boundary

The useful maintainer-facing question is not "why did payment fail?" The payment did not fail in the cited evidence.

The narrow question is:

> For these already-settled transactions, did either payment create a Bazaar ingestion job, and if so, what public evidence can distinguish processing, rejection, and successful indexing?

That keeps Astra focused on independent causal/economic-outcome verification after the payment decision rather than competing with the increasingly crowded pre-execution policy layer.

## Safety

No new transaction is required to use this fixture. Do not replay or repurchase the resources merely to refresh evidence. Prefer read-only chain/catalog observations and maintainer-provided internal correlation when available.
