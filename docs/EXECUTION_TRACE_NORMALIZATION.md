# Normalized Execution Trace Verification

ContractGraph-QA uses one normalized execution-evidence stream to feed multiple independent verification engines.

```text
raw runtime/provider/EVM evidence
          ↓ adapter/review boundary
normalized execution trace
          ├── economic effect projection ─→ CGQ-SAFE-001
          └── state commit projection ─────→ CGQ-CONS-001
```

The normalization layer is intentionally conservative. It does not infer that an arbitrary log, call, webhook, storage write, or transaction hash is economically authoritative. An adapter or reviewed capture process must establish that meaning first.

## CLI

```bash
cgqa execution-trace-check \
  --trace scenarios/execution-trace-double-settlement-conflict.json
```

A trace fails if any applicable projected verifier fails. A trace passes only when every applicable verifier passes.

## Event contract

One event may carry an economic effect, a state commit, or both:

```json
{
  "eventId": "evt-release",
  "sourceRef": "tx:0xaaa",
  "economicEffect": {
    "actionId": "escrow-42:settle",
    "effectKey": "escrow-payout",
    "occurrenceId": "settlement:aaa",
    "applied": true
  },
  "stateCommit": {
    "commitId": "commit:aaa",
    "conflictKey": "escrow:42",
    "parentState": "Funded",
    "parentVersion": 7,
    "operation": "release",
    "successorState": "Released",
    "successorVersion": 8,
    "committed": true
  }
}
```

`sourceRef` is preserved as trace provenance but does not itself establish authority.

## Economic projection

Each `economicEffect` becomes an event for the economic-cardinality verifier.

The invariant is:

```text
CGQ-SAFE-001 — AT_MOST_ONCE_ECONOMIC_EFFECT
```

Two observations of the same `occurrenceId` are deduplicated. Two distinct applied occurrences for one `(actionId, effectKey)` fail.

## Successor projection

Each `stateCommit` becomes an event for the successor-consistency verifier.

The invariant is:

```text
CGQ-CONS-001 — SINGLE_VALID_SUCCESSOR_PER_STATE_VERSION
```

Repeated observations of the same `commitId` are deduplicated. Two distinct committed children for one `(conflictKey, parentState, parentVersion)` fail.

## Why one trace

Using one trace prevents two adapters from independently interpreting the same execution and silently disagreeing about identity. A single canonical trace SHA-256 binds the shared evidence stream, while each verifier still emits its own model SHA-256 and violation evidence.

## Claim boundary

A PASS is exact only over the declared normalized evidence. It does not prove that:

- the raw provider/EVM trace was complete;
- every external side effect was captured;
- every state version was observed;
- a transaction hash necessarily represents the intended business occurrence;
- provider/webhook evidence is authoritative without a reviewed adapter contract.

Those are capture and normalization claims and remain separate evidence boundaries.

## Next adapter layer

Raw adapters should target this schema rather than call verification engines directly. Candidate adapters include:

- Foundry/Anvil local transaction traces;
- decoded contract events plus reviewed storage snapshots;
- provider payment observations;
- wallet execution receipts.

Unsupported or ambiguous raw evidence should remain unresolved at the adapter boundary rather than being converted into a synthetic PASS.
