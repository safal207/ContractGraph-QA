# Solidity → Contract Lattice Benchmark v0.1

This benchmark proves that ContractGraph-QA can move from real Solidity compiler evidence to a lifecycle theorem and a Contract Lattice template without inventing runtime facts.

## Vulnerable case

`src/examples/DisputedDeadEndEscrow.sol`

```text
Created → Funded → Released
               ├→ Refunded
               └→ Disputed → ∅
```

Reviewed semantics:

- value-holding: `Funded`, `Disputed`;
- safe economic terminals: `Released`, `Refunded`;
- invariant: `CGQ-LIVE-001`.

Expected result:

```text
Function-local behavior: valid
Extraction: complete
Lifecycle verification: FAIL
Counterexample: Created → Funded → Disputed
```

## Control case

`src/examples/Escrow.sol` must PASS the same lifecycle property with `Funded` as the value-holding state and `Released` / `Refunded` as safe terminals.

## Regression target

The vulnerable fixture intentionally uses builtin string reverts:

```solidity
if (state != State.Funded) revert("invalid state");
```

An earlier extractor version treated that compiler-AST shape as unresolved. v0.1 freezes support for both builtin `revert(...)` calls and custom-error `RevertStatement` nodes.

## Lattice boundary

The static projection emits relative transition versions and value-presence classification only. Concrete balances, authority, time witnesses, transaction order and committed versions require runtime evidence.
