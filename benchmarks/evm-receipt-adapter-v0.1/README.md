# EVM Receipt Adapter Benchmark v0.1

This benchmark proves that ContractGraph-QA can derive its existing runtime
verification input from raw receipt logs instead of a hand-authored ExecutionTrace.

## Fixture

`scenarios/evm-receipt-double-settlement.json` contains two synthetic successful
logs from one escrow contract:

```text
Funded@7 --release------> Released@8
Funded@7 --raiseDispute-> Disputed@8
```

Both logs also declare the same logical economic action/effect slot but have
distinct on-chain occurrences.

The reviewed mapping is:

`scenarios/evm-receipt-double-settlement-profile.json`

## Expected pipeline

```text
raw JSON-RPC receipt
        ↓
EVM Receipt Adapter       PASS
        ↓
ExecutionTrace v0.1
        ├─ economic-cardinality   FAIL
        └─ successor-consistency  FAIL
```

The adapter itself must PASS because the receipt evidence is well-formed and fully
mapped. The downstream invariant engines must FAIL because the mapped execution
contains both a duplicate economic effect and competing committed successors.

This separation is intentional: evidence acquisition success is not a safety
verdict.

## Regression requirements

The benchmark also covers:

- reverted receipt -> adapter `INCONCLUSIVE`;
- successful but unmatched receipt -> `INCONCLUSIVE`;
- removed logs are ignored;
- address filtering prevents cross-contract topic collisions;
- missing ABI words fail closed;
- duplicate topic mappings are rejected.
