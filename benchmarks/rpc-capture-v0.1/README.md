# RPC Capture Benchmark v0.1

This benchmark freezes the boundary between provider observation and ContractGraph-QA verification.

## Required properties

A conforming implementation must:

1. bind the requested transaction hash to `receipt.transactionHash`;
2. bind `receipt.blockHash` and `receipt.blockNumber` to the fetched block;
3. record the observed head and derive confirmation count without claiming finality;
4. omit the RPC URL/credentials from all output;
5. return `INCONCLUSIVE` when the receipt is not observed;
6. fail closed on contradictory receipt/block/head evidence.

## End-to-end integration case

The repository's existing synthetic double-settlement receipt is used as downstream evidence after the transport leg is substituted with a deterministic fixture.

Expected composition:

```text
RPC capture integrity            PASS
receipt normalization            PASS
static lifecycle                 FAIL
runtime economic cardinality     FAIL
runtime successor consistency    FAIL
static/runtime conformance       PASS
overall hydrated assessment      FAIL
```

The important distinction is that **capture success does not imply contract safety**. It means only that the observed evidence is internally bound strongly enough to enter later verification layers.

## Negative cases

- receipt absent → `INCONCLUSIVE`;
- requested tx != receipt tx → reject;
- receipt block hash != fetched block hash → reject;
- receipt block number != fetched block number → reject;
- observed head < receipt block → reject;
- RPC endpoint/secret appears in output → benchmark failure.
