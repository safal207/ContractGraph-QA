# Hydrated Contract Lattice Benchmark v0.1

This benchmark composes the repository's first static Solidity lattice failure with the first normalized runtime replay/successor conflict.

## Inputs

- `src/examples/DisputedDeadEndEscrow.sol`
- `scenarios/solidity-lattice-disputed-dead-end-profile.json`
- `scenarios/execution-trace-double-settlement-conflict.json`
- `scenarios/hydration-bindings-escrow-race.json`

## Expected result

```text
static lifecycle            FAIL  (Disputed value-holding dead end)
runtime economic cardinality FAIL (two distinct applied settlements)
runtime successor consistency FAIL (two committed children of Funded@7)
static/runtime conformance   PASS  (both observed transitions are legal possibilities)
binding verification         PASS  (declared authority/evidence bindings present)
overall                      FAIL
```

The combination is intentional: a transition may be legal in the static contract while the *observed composition* of transitions is unsafe at runtime.

## Run

```bash
cgqa-hydrated \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/solidity-lattice-disputed-dead-end-profile.json \
  --trace scenarios/execution-trace-double-settlement-conflict.json \
  --bindings scenarios/hydration-bindings-escrow-race.json \
  --root .
```

## Benchmark thesis

> Static possibility and runtime actuality are different proof legs. A trustworthy audit must preserve both.
