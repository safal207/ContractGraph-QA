# Provider Adapter Contract v0.1

Provider adapters connect a provider-specific **public contract** to the vendor-neutral Agent Payment Recovery Benchmark without putting vendor logic into the benchmark engine.

```text
provider public contract
  ↓
Provider Adapter Contract v0.1
  ↓
provider states → committed / failed / pending / unknown
  ↓
evidence source precedence
  ↓
final / non-final reconciliation
  ↓
Agent Payment Recovery Benchmark
```

## Adapter fields

A profile declares:

- `providerId` and `profileVersion`;
- create/idempotency semantics;
- provider-state → normalized-outcome mapping;
- observable evidence sources;
- which sources are authoritative for finality;
- explicit evidence precedence;
- retry continuity policy;
- public contract references used to justify the mapping.

The adapter is declarative. It makes **no network calls** and does not test a provider by itself.

## Fail-closed precedence

The highest-precedence observed source is selected. A lower-precedence `success` cannot override a higher-precedence `pending` or `unknown` observation.

Example:

```text
webhook = success
status-api = pending
precedence = status-api > webhook

⇒ NON-FINAL
⇒ retry remains blocked
```

When a higher-precedence source that is authoritative for finality reports a final state, the adapter emits a normalized `reconcile` event that can feed the payment-recovery benchmark.

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

## Example profile is not a provider claim

`example-public-contract.json` is deliberately synthetic. It demonstrates the contract shape and precedence mechanics only. It must not be interpreted as documentation of Crossmint, PayRam, Valta, x402, or any other named provider.

A real provider adapter should be created only from public documentation or an explicitly authorized engagement, with source references preserved in `publicContractRefs`.

## Safety boundary

Provider adapters normalize evidence; they do not certify payment systems, authorize production actions, or establish that an upstream evidence source is truthful. Production probing remains out of scope without explicit authorization.
