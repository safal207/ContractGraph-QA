# Provider Adapter Contract

Provider adapters connect a provider-specific **public contract** to the vendor-neutral Agent Payment Recovery Benchmark without putting vendor logic into the benchmark engine.

```text
provider public contract
  ↓
Provider Adapter Contract
  ↓
provider states → committed / failed / pending / unknown
  ↓
evidence authority + documented precedence
  ↓
final / non-final reconciliation
  ↓
Agent Payment Recovery Benchmark
```

## Versions

### v0.1 — fully specified contract

v0.1 requires explicit evidence precedence and retry policy. It is useful when the source contract actually documents those semantics.

### v0.2 — public-contract uncertainty is first-class

Real provider documentation is often incomplete at exactly the recovery boundary. v0.2 therefore allows:

```text
evidencePrecedenceStatus = unresolved
evidencePrecedence = []
```

This is deliberate. The adapter must not invent an ordering merely to satisfy a schema.

When precedence is unresolved:

- one observed authoritative finality surface may produce a final result;
- no authoritative surface produces `NON-FINAL`;
- multiple authoritative surfaces without documented precedence produce `NON-FINAL`;
- a conflicting or lower-authority signal never silently unlocks retry.

The runtime records a `reconciliationBlockReason` such as:

- `no_authoritative_finality_surface_observed`;
- `evidence_precedence_unresolved`.

## Adapter fields

A profile declares only what can be grounded:

- `providerId` and `profileVersion`;
- create/idempotency semantics;
- provider-state → normalized-outcome mapping;
- observable evidence sources;
- which sources are sufficiently documented to be treated as authoritative for finality;
- documented precedence, or explicit `unresolved` precedence in v0.2;
- public contract references;
- unresolved public questions when useful.

The adapter is declarative. It makes **no network calls** and does not test a provider by itself.

## Fail-closed precedence

With documented precedence, the highest-precedence observed source is selected. A lower-precedence `success` cannot override a higher-precedence `pending` or `unknown` observation.

```text
webhook = success
status-api = pending
precedence = status-api > webhook

⇒ NON-FINAL
⇒ retry remains blocked
```

With unresolved precedence, the adapter refuses to manufacture that ordering.

## Commands

Validate a provider profile:

```bash
cgqa provider-adapter-validate \
  --adapter benchmarks/agent-payment-recovery-v0.1/provider-adapters/example-public-contract.json
```

Normalize captured evidence:

```bash
cgqa provider-adapter-reconcile \
  --adapter benchmarks/agent-payment-recovery-v0.1/provider-adapters/example-public-contract.json \
  --observations benchmarks/agent-payment-recovery-v0.1/provider-adapters/example-observations-final.json
```

A final reconciliation exits `0`.

A structurally valid but **non-final** reconciliation exits `10`. This makes the command usable as a fail-closed gate before a retry or other monetary action.

## First public provider profile: Crossmint

`crossmint-public-contract.v0.1.json` is intentionally conservative and is grounded only in Crossmint's public wallet transaction documentation.

The public contract documents:

- `x-idempotency-key` on Create Transaction as a mechanism to prevent duplicate transaction creation;
- transaction states `awaiting-approval`, `pending`, `failed`, and `success`;
- `success` as confirmed onchain;
- GET Transaction as a status lookup by transaction ID;
- wallet transfer webhooks with `succeeded` / `failed` outcomes.

The reviewed public pages did **not** establish a canonical precedence among GET status, webhook and onchain evidence, nor did they document same-key replay as the canonical recovery procedure after an ambiguous Create Transaction timeout. Those facts remain explicit open questions instead of being filled by assumption.

The Crossmint profile performs no Crossmint API calls and makes no vulnerability claim.

## Example profile is not a provider claim

`example-public-contract.json` remains deliberately synthetic. It demonstrates the contract shape and precedence mechanics only.

A real provider adapter should be created only from public documentation or an explicitly authorized engagement, with source references preserved in `publicContractRefs`.

## Safety boundary

Provider adapters normalize evidence; they do not certify payment systems, authorize production actions, or establish that an upstream evidence source is truthful. Production probing remains out of scope without explicit authorization.
