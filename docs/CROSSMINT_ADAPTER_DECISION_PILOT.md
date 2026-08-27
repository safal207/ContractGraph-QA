# Crossmint adapter-backed Agent Payment Decision pilot

This pilot composes the repository's reviewed **Crossmint public-contract provider adapter** with the **Unified Agent Payment Decision Gate**.

It carries provider-normalized evidence into a monetary-action decision without treating a documentation gap, timeout, missing webhook, or terminal failure as permission to create another payment.

## Reviewed public-contract shape

The reviewed Crossmint profile records the following public-contract facts and conservative interpretation boundaries:

- transaction creation supports `x-idempotency-key`;
- the public Create Transaction page describes that key as preventing duplicate transaction creation, but does not specify the exact response returned by a same-key replay;
- `GET transaction` is the authoritative finality surface used for transaction status reconciliation;
- terminal transaction states are `success` and `failed`;
- transfer webhooks are at-least-once notification evidence and must be deduplicated, so webhook delivery is not promoted to canonical state;
- `onChain.txId` is settlement/confirmation material once broadcast, not a reliable discovery mechanism before broadcast;
- Crossmint does not publish a complete normative precedence rule for the timeout-recovery case.

The profile therefore does not use same-key replay as a documented discovery guarantee. When a transaction ID is already known, `GET transaction → lookup until terminal → settlement evidence` is a **derived integration composition**, not a separate normative provider guarantee.

## Causal path

```text
captured Crossmint observation
        ↓
Crossmint public adapter v0.3 profile
        ↓
provider reconciliation
        ↓
explicit authority evidence
        ↓
retry-authority bridge
        ↓
Unified Agent Payment Decision
        ↓
ALLOW / HOLD / STOP / RECONCILE / COMPENSATE
```

The bridge performs **no network calls**. It consumes only an adapter profile, already-captured observations, and explicit authority evidence.

## Ambiguous create / timeout

A lost HTTP response is not evidence that no transaction exists.

```text
create transaction with idempotency key K
→ timeout / response lost
→ preserve the same logical operation
→ do not infer the response shape of a same-key replay
→ if a transaction ID was captured, canonical lookup establishes current state
→ otherwise remain RECONCILE / HOLD pending documented discovery
→ nonterminal state remains RECONCILE
→ no new monetary operation is authorized by ambiguity alone
```

This is the first Crossmint instantiation of the repository's Ambiguous Financial State Protocol (AFSP).

## Public-contract cases

### Webhook-only `succeeded`

The profile marks `wallet-transfer-webhook` as non-authoritative for finality. A webhook-only `succeeded` observation remains non-final:

```text
wallet-transfer-webhook:succeeded
→ notification evidence
→ finality authority absent
→ provider reconciliation = nonfinal
→ Unified Decision = RECONCILE
→ monetaryActionAllowed = false
```

### Authoritative GET `success`

A `get-transaction:success` observation reconciles as committed. For the same logical operation, another monetary action is blocked:

```text
get-transaction:success
→ provider reconciliation = final / committed
→ Unified Decision = STOP
→ logical_operation_already_satisfied
→ monetaryActionAllowed = false
```

### Final `failed` under adapter v0.3

Provider Adapter Contract v0.3 explicitly separates **reconciliation finality** from **retry authority**.

The reviewed Crossmint profile records idempotency-key support but keeps exact same-key replay semantics unresolved. It also does not invent a public rule authorizing a new monetary operation after terminal `failed`.

```text
get-transaction:failed
→ provider reconciliation = final / failed
→ retrySemanticsStatus = unresolved
→ retryAllowed = false
→ Unified Decision = HOLD
→ monetaryActionAllowed = false
```

This distinction is deliberate: replaying the same idempotent creation request for discovery is not equivalent to authorizing a fresh spend.

## Evidence provenance

The profile preserves three different evidence classes:

```text
provider-documented primitive
        ↓
conservative adapter classification
        ↓
derived integration composition
```

A derived composition must never be relabeled as a provider guarantee. This prevents hindsight or implementation assumptions from silently gaining authority.

## Authority boundary

Provider success, failure, idempotency support, transaction finality, or settlement evidence never establish actor authority. Callers must supply an explicit authority status and evidence reference. Revoked, expired, or unknown authority remains fail-closed in the Unified Agent Payment Decision Gate.

## Claim boundary

This is a **public-contract composition test**, not a live Crossmint audit. The linked mutable public pages were re-reviewed on 2026-08-27 UTC; no archived provider snapshot or private clarification is treated as evidence.

No Crossmint credentials, API calls, wallet operations, testnet/mainnet writes, production authorization, vulnerability claim, compliance claim, endorsement, or security certification are involved. The Crossmint semantics used here are limited to the reviewed public-contract profile, public documentation, and deterministic repository fixtures.
