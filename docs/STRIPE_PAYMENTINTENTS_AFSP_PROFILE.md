# Stripe PaymentIntents AFSP profile

This document instantiates the Ambiguous Financial State Protocol (AFSP) against Stripe's public PaymentIntents contract.

It is intentionally provider-specific evidence feeding a provider-neutral continuation gate.

## Public contract used

The reviewed public documentation establishes:

- Stripe API v1 supports idempotency keys on POST requests so a connection-error retry can repeat the same request without creating the same operation twice;
- the first result for an idempotency key is retained and returned on same-key replay, subject to the documented key-retention semantics;
- Stripe recommends one PaymentIntent per order or customer session and recommends reusing the same PaymentIntent if checkout is interrupted;
- a PaymentIntent tracks payment lifecycle state and creates at most one successful charge;
- a PaymentIntent can be retrieved by ID through the API;
- `processing` and other intermediate PaymentIntent states are nonterminal;
- `succeeded` means the payment flow is complete;
- webhooks can be retried, duplicated, and delivered out of order; Stripe explicitly recommends retrieving API objects when event context is missing.

Public references:

- https://docs.stripe.com/api/idempotent_requests
- https://docs.stripe.com/api/payment_intents
- https://docs.stripe.com/payments/payment-intents
- https://docs.stripe.com/payments/paymentintents/lifecycle
- https://docs.stripe.com/api/payment_intents/retrieve
- https://docs.stripe.com/webhooks

## AFSP mapping

```text
higher-level order / agent intent
        ↓
create or confirm PaymentIntent
        ↓
response lost / timeout
        ↓
preserve idempotency identity and PaymentIntent identity
        ↓
retrieve PaymentIntent state
        ↓
processing / requires_action / requires_capture → RECONCILE
succeeded                                → STOP
canceled                                 → HOLD unless separate continuation authority exists
```

Webhook observations are useful triggers, but the AFSP profile does not promote a webhook-only observation to canonical finality because webhook delivery can be duplicated or out of order.

## Why this is a portability proof

Crossmint and Stripe expose different rails and different state machines, yet AFSP applies the same invariants:

```text
transport ambiguity != permission
notification != canonical state
provider finality != actor authority
final failure != automatic new-operation authority
```

The provider adapters differ. The continuation decision engine does not.

## Important semantic boundary

Stripe documents retry-safe idempotency and reuse of a PaymentIntent. That does not mean every terminal or failed-looking state authorizes an autonomous system to create a fresh PaymentIntent.

AFSP therefore separates:

```text
same logical operation recovery
from
new logical monetary operation authorization
```

The reviewed profile keeps new-operation retry authority fail-closed unless a separate policy or business-authority layer proves it.

## Deterministic cases

The repository includes fixtures and tests for:

- canonical API lookup reporting `succeeded` → `STOP`;
- webhook-only `succeeded` → `RECONCILE`;
- API lookup reporting `processing` → `RECONCILE`;
- API lookup reporting `canceled` → `HOLD` because new-operation authority is unresolved.

No live Stripe API call, credential use, customer payment, production mutation, vulnerability claim, compliance claim, or provider endorsement is part of this profile.
