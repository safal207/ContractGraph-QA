# Raw EVM → Hydrated Contract Lattice Benchmark v0.1

This benchmark exercises the full path from raw JSON-RPC receipt evidence to the
multi-layer ContractGraph-QA verdict.

```text
Solidity + reviewed lifecycle profile
        ↓
static Contract Lattice

raw JSON-RPC receipt + reviewed event profile
        ↓
ExecutionTrace v0.1

reviewed authority/evidence bindings
        ↓
Hydrated Contract Lattice
        ↓
liveness + economic cardinality + successor consistency + conformance
```

## One command

```bash
cgqa-evm-hydrated \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/solidity-lattice-disputed-dead-end-profile.json \
  --receipt scenarios/evm-receipt-double-settlement.json \
  --receipt-profile scenarios/evm-receipt-double-settlement-profile.json \
  --bindings scenarios/hydration-bindings-evm-receipt-race.json \
  --root .
```

## Expected result

```text
receipt normalization           PASS
static lifecycle                FAIL  (Disputed dead-end)
runtime economic cardinality    FAIL  (duplicate effect)
runtime successor consistency   FAIL  (two children from Funded@7)
static/runtime conformance       PASS  (both transitions exist statically)
binding verification            PASS
overall                         FAIL
```

The important distinction is that a provider-evidence adapter can successfully
normalize evidence while the system represented by that evidence is unsafe.
