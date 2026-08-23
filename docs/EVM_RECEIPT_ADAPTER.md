# EVM Receipt Adapter v0.1

The EVM Receipt Adapter turns a mined JSON-RPC transaction receipt into the
normalized `ExecutionTrace v0.1` consumed by ContractGraph-QA runtime verifiers.

It is intentionally not an ABI-guessing layer.

```text
JSON-RPC receipt
      +
reviewed event mapping profile
      ↓
exact topic0/address match
      ↓
supported 32-byte word decoding
      ↓
ExecutionTrace v0.1
      ↓
economic-cardinality / successor-consistency
```

## Command

```bash
cgqa-evm-receipt \
  --receipt scenarios/evm-receipt-double-settlement.json \
  --profile scenarios/evm-receipt-double-settlement-profile.json \
  --trace-out /tmp/execution-trace.json
```

`--trace-out` writes only the canonical normalized trace. The command stdout also
contains adapter diagnostics and provenance hashes.

## Reviewed mapping

A profile pins:

- chain ID;
- optional contract-address allowlist;
- exact `topic0` values;
- the semantic event name;
- how each `economicEffect` / `stateCommit` field is obtained.

Supported field sources:

- `constant`;
- `eventRef` (`transactionHash:logIndex`);
- `txHash`;
- `logIndex`;
- emitting `address`;
- `topic[index]`;
- `dataWord[index]`.

For topics and data words the only v0.1 decoders are:

- `uint256`;
- `bytes32`;
- `address`;
- `bool`.

A reviewed `enumMap` may translate a decoded scalar into a state name. `prefix`
and `suffix` can bind an extracted scalar into a stable logical identifier.

## Fail-closed behavior

The adapter does not synthesize missing facts.

- Unknown `topic0` -> ignored and counted as unmatched.
- Address outside a non-empty allowlist -> ignored and counted.
- Removed log -> ignored and counted.
- Reverted transaction -> `INCONCLUSIVE`, zero normalized events.
- Successful receipt with no matched event -> `INCONCLUSIVE`.
- Referenced topic/data word absent -> validation failure.
- Enum value absent from the reviewed map -> validation failure.
- Duplicate profile `topic0` -> validation failure.

In particular, state versions are emitted only if the mapped log actually carries
them. The adapter never substitutes log order or block height for a business-state
version.

## Provenance

Every result contains:

- `receiptSha256`;
- `profileSha256`;
- transaction hash;
- chain ID;
- per-event `sourceRef = evm:<chainId>:<txHash>:log:<logIndex>`.

This lets downstream findings point back to the exact receipt log from which the
normalized semantic claim was derived.

## Claim boundary

A receipt does not prove the completeness of all EVM execution semantics. Receipt
logs do not expose arbitrary internal calls, storage writes, authority decisions,
or time witnesses unless the contract explicitly emits evidence for them.

Therefore adapter PASS means only:

> at least one successful receipt log was deterministically normalized under the
> reviewed mapping profile.

It does **not** mean the transaction or contract is safe. Safety is evaluated by
the downstream ContractGraph-QA invariants.
