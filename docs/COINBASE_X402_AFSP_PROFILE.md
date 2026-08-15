# Coinbase x402 v2 — AFSP portability profile

This profile maps the public Coinbase Developer Platform x402 v2 / x402 Foundation protocol surface into the repository's Ambiguous Financial State Protocol (AFSP).

It is a public-contract composition only. It performs no live facilitator calls, wallet signing, settlement, mainnet/testnet mutation, or provider certification.

## Why x402 is a different portability test

Crossmint and Stripe expose durable provider objects plus conventional idempotent request semantics. x402 is different: it is an HTTP-native payment protocol where a client receives payment requirements, signs a payment payload, the resource server verifies it, settlement is performed, and the resource response carries settlement details.

The core x402 v2 exact-EVM flow includes a unique authorization nonce, time constraints, and signature verification for replay-attack prevention. That cryptographic replay protection is **not the same contract** as application-level recovery or duplicate-call idempotency.

The public Coinbase x402 FAQ separately describes the optional **Payment Identifier** extension as an idempotency extension for servers or facilitators handling duplicate calls. The AFSP core profile deliberately does not pretend that this optional extension is always present.

## Public state boundary

The reviewed profile distinguishes verification from settlement:

```text
PAYMENT-REQUIRED
→ PAYMENT-SIGNATURE
→ facilitator /verify
→ valid authorization
→ facilitator /settle
→ settlement result
→ server PAYMENT-RESPONSE + resource
```

`/verify` answers whether the payment payload is valid against requirements. It does not itself establish that funds have settled.

`/settle` returns a settlement response with a success flag and, on success, a transaction identifier/network/payer record. Therefore the adapter treats facilitator settlement success as finality evidence and verification as non-final evidence.

A generic `success:false` settlement response is kept non-final in this profile. The public API exposes multiple settlement error reasons, and the profile does not promote every error class into proof that no monetary effect can appear.

## AFSP mapping

```text
facilitator-verify: verify-valid
→ payment authorization accepted
→ settlement not yet proven
→ RECONCILE
→ monetaryActionAllowed = false
```

```text
facilitator-settle: settle-success
→ final / committed
→ STOP same logical operation
→ monetaryActionAllowed = false
```

```text
facilitator-settle: settle-failed
→ outcome remains unknown without a typed non-effect guarantee
→ RECONCILE
→ monetaryActionAllowed = false
```

The last case is intentionally conservative. A failed settlement response does not automatically become permission for an autonomous caller to construct a fresh economic action.

## Recovery gap exposed by x402

x402 makes AFSP's distinction sharper:

```text
anti-replay nonce
    !=
duplicate-call idempotency
    !=
read-after-settle discovery
    !=
new-operation authority
```

If settlement succeeds but the final HTTP resource response or `PAYMENT-RESPONSE` is lost, the client may have an ambiguous economic state. The reviewed public core flow establishes settlement responses and an optional Payment Identifier extension, but this profile does not infer a universal client-side read-after-settle lookup procedure that is not explicitly present in the reviewed contract.

That gap is exactly where AFSP applies: ambiguity remains `RECONCILE`/`HOLD`, never implicit permission to pay again.

## Public references

- https://docs.cdp.coinbase.com/x402/core-concepts/how-it-works
- https://docs.cdp.coinbase.com/x402/core-concepts/facilitator
- https://docs.cdp.coinbase.com/api-reference/v2/rest-api/x402-facilitator/verify-payment
- https://docs.cdp.coinbase.com/api-reference/v2/rest-api/x402-facilitator/settle-payment
- https://docs.cdp.coinbase.com/x402/support/faq
- https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md

## Claim boundary

This profile does not claim a vulnerability, production defect, race condition, compliance property, or endorsement by Coinbase or the x402 Foundation. It records a provider-neutral continuation model from public protocol semantics and deterministic fixtures only.
