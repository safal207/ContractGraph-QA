# Crossmint adapter-backed Agent Payment Decision pilot

This pilot composes the repository's reviewed **Crossmint public-contract provider adapter** with the **Unified Agent Payment Decision Gate**.

It carries provider-normalized evidence into a monetary-action decision without treating a documentation gap, timeout, missing webhook, or terminal failure as permission to create another payment.

## Clarified public-contract shape

The reviewed Crossmint profile now records the following public guarantees and externally clarified interpretation boundary:

- transaction creation supports `x-idempotency-key`;
- same-key replay is documented as returning the existing transaction rather than creating a duplicate;
- `GET transaction` is the authoritative finality surface used for transaction status reconciliation;
- terminal transaction states are `success` and `failed`;
- transfer webhooks are at-least-once notification evidence and must be deduplicated, so webhook delivery is not promoted to canonical state;
- `onChain.txId` is settlement/confirmation material once broadcast, not a reliable discovery mechanism before broadcast;
- Crossmint does not publish a complete normative precedence rule for the timeout-recovery case.

The operational sequence `same-key replay → lookup until terminal → settlement evidence` is therefore modeled as a **derived integration composition**, not as a separate normative provider guarantee.

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
→ same-key replay may discover the existing transaction
→ canonical transaction lookup establishes current state
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

The reviewed Crossmint profile records same-key replay as documented, but it does not invent a public rule authorizing a new monetary operation after terminal `failed`.

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
provider clarification of public semantics
        ↓
derived integration composition
```

A derived composition must never be relabeled as a provider guarantee. This prevents hindsight or implementation assumptions from silently gaining authority.

## Authority boundary

Provider success, failure, idempotency support, transaction finality, or settlement evidence never establish actor authority. Callers must supply an explicit authority status and evidence reference. Revoked, expired, or unknown authority remains fail-closed in the Unified Agent Payment Decision Gate.

## Claim boundary

This is a **public-contract composition test**, not a live Crossmint audit.

No Crossmint credentials, API calls, wallet operations, testnet/mainnet writes, production authorization, vulnerability claim, compliance claim, endorsement, or security certification are involved. The Crossmint semantics used here are limited to the reviewed public-contract profile, public documentation, bounded external clarification, and deterministic repository fixtures.
