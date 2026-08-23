# RPC Capture v0.1

`RPC Capture v0.1` removes the manually prepared receipt file from the ContractGraph-QA runtime path while keeping provider trust explicit.

## Capture only

Prefer an environment variable so API keys do not land in shell history:

```bash
export CGQA_RPC_URL='https://your-provider.example/...'

cgqa-rpc-capture \
  --tx-hash 0x... \
  --output capture.json
```

The capture performs:

1. `eth_chainId`
2. `eth_getTransactionReceipt`
3. `eth_getBlockByHash(receipt.blockHash, false)`
4. `eth_blockNumber`

A successful result proves only that one configured endpoint returned a mutually consistent observation at capture time.

## Full audit from a transaction hash

```bash
cgqa-rpc-hydrated \
  --tx-hash 0x... \
  --target src/MyEscrow.sol:MyEscrow \
  --profile lifecycle-profile.json \
  --receipt-profile event-mapping-profile.json \
  --bindings hydration-bindings.json \
  --root . \
  --capture-out capture.json
```

Pipeline:

```text
RPC endpoint + tx hash
        ↓
receipt + block/header witness + observed head
        ↓
reviewed EVM log mapping
        ↓
ExecutionTrace
        ↓
Solidity AST → static Contract Lattice
        ↓
Hydrated Contract Lattice
        ↓
liveness + replay + successor consistency + static/runtime conformance
```

## Fail-closed checks

Capture rejects:

- a receipt whose transaction hash differs from the requested hash;
- a block response whose hash differs from `receipt.blockHash`;
- a block number inconsistent with the receipt;
- an observed head below the containing block;
- malformed hashes/quantities or JSON-RPC errors.

A missing receipt is `INCONCLUSIVE`, not `PASS`.

## Secret boundary

The RPC URL is never persisted in capture output. This matters because provider URLs commonly contain API keys in their path or query string. `CGQA_RPC_URL` is preferred over `--rpc-url` for the same reason.

## Finality boundary

`observedConfirmationCount` is only:

```text
observedHeadNumber - blockNumber + 1
```

It is **not** a chain-finality guarantee. RPC canonicality, independent-provider agreement, reorg risk and protocol-specific finality remain separate proof legs.

## Deterministic provenance

The result includes SHA-256 digests for the returned chain-id, receipt, block and head responses plus a SHA-256 of the normalized capture document. No wall clock participates in verification.
