# Crossmint adapter-backed Agent Payment Decision pilot

This pilot composes the repository's existing **Crossmint public-contract provider adapter** with the **Unified Agent Payment Decision Gate**.

It is the first provider-named decision path in ContractGraph-QA that carries provider-normalized evidence into the final monetary-action decision without treating public-documentation gaps as permission.

## Causal path

```text
captured Crossmint observation
        ↓
Crossmint public adapter
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

## Public-contract cases

### Webhook-only `succeeded`

The Crossmint profile marks `wallet-transfer-webhook` as non-authoritative for finality and keeps evidence precedence unresolved. Therefore a webhook-only `succeeded` observation remains non-final:

```text
wallet-transfer-webhook:succeeded
→ normalized committed-looking evidence
→ finality authority absent
→ provider reconciliation = nonfinal
→ Unified Decision = RECONCILE
→ monetaryActionAllowed = false
```

### Authoritative GET `success`

The public profile marks `get-transaction` as authoritative for finality. A GET `success` observation therefore reconciles as committed. For the same logical operation, the decision gate does not authorize another monetary action:

```text
get-transaction:success
→ provider reconciliation = final / committed
→ Unified Decision = STOP
→ logical_operation_already_satisfied
→ monetaryActionAllowed = false
```

### Final `failed` under adapter v0.2

This is the important fail-closed edge.

Provider Adapter Contract v0.2 can represent unresolved **evidence precedence**, but it does not encode an explicit retry-authority contract. The older reconciliation layer can return `retryAllowed=true` for a final failure, but the decision bridge deliberately refuses to reinterpret that legacy value as permission to create another monetary action.

For the Crossmint v0.2 public profile:

```text
get-transaction:failed
→ provider reconciliation = final / failed
→ v0.2 has no explicit retry-authority semantics
→ retryAuthorityStatus = unresolved
→ retryAllowed = false
→ Unified Decision = HOLD
→ monetaryActionAllowed = false
```

This matches the profile's existing open question: reviewed public documentation does not establish a safe same-key recovery/retry procedure after an ambiguous Create Transaction failure path.

## Authority boundary

Provider success, failure, idempotency support, or transaction finality never establish actor authority. Callers must supply an explicit authority status and evidence reference. Revoked, expired, or unknown authority remains fail-closed in the Unified Agent Payment Decision Gate.

## Claim boundary

This is a **public-contract composition test**, not a live Crossmint audit.

No Crossmint credentials, API calls, wallet operations, testnet/mainnet writes, production authorization, vulnerability claim, compliance claim, endorsement, or security certification are involved. The Crossmint semantics used here are limited to the repository's reviewed public-contract profile and deterministic fixtures.
