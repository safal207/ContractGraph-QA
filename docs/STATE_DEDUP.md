# State hashing and deduplication

v0.5 adds a breadth-first search mode that keeps one shortest representative path for every unique modeled state hash.

## Why

Action-sequence search grows exponentially when many paths converge to the same state.

For example, if two accepted no-op actions and one advance action are available, exhaustive enumeration at depth 8 considers:

```text
3 + 9 + 27 + 81 + 243 + 729 + 2187 + 6561 = 9840 candidate paths
```

But if those paths reach only four distinct states, re-expanding every equivalent path adds cost without adding reachable-state coverage.

## Search model

`StateDedupPathExplorerHarness` performs breadth-first expansion:

```text
shortest path
  ↓
execute one modeled step
  ↓
check invariant
  ↓
compute state hash
  ↓
new hash? ── yes ─→ keep representative path
     │
     no
     ↓
prune equivalent state
```

The first path stored for a hash is shortest by step count because exploration is breadth-first.

## Required state-hash contract

Deduplication is only sound when `_stateHash()` captures every modeled value that can affect future behavior.

Depending on the target this may include:

- relevant contract storage;
- balances and accounting totals;
- actor/role context;
- block time or a safe temporal equivalence class;
- oracle freshness/value;
- governance epoch;
- external-contract state that affects subsequent calls.

If two states receive the same hash but have different reachable futures, pruning can hide a path. The hash definition is therefore part of the test model and must be reviewed like an invariant.

For the local convergent fixture the complete future-relevant state is only:

```solidity
keccak256(abi.encode(machine.phase()))
```

## Demonstrated reduction

The v0.5 regression fixture exposes three accepted actions:

```text
noopA
noopB
advance
```

Both no-op actions converge to the current phase. `advance` moves through phases 0 → 1 → 2 → 3.

With no terminal violation enforced, a depth-8 exhaustive candidate count is 9,840. The deduplicating search executes only 12 child transitions and discovers four unique states before the frontier becomes empty.

With the terminal invariant enabled, the search still discovers the minimal violating path:

```text
advance → advance → advance
```

while pruning the equivalent no-op branches.

## Fail-closed budgets and assumptions

The engine caps actual work rather than the theoretical exhaustive tree:

- at most 4,096 unique modeled states are retained;
- at most 65,536 child transitions are attempted;
- every retained representative path must replay successfully after reset, otherwise the harness reverts with `replay drift`;
- the target reset must be deterministic;
- state hashing must include all future-relevant modeled context.

This lets deduplication unlock deeper bounded searches when the reachable state graph is much smaller than the raw path tree, while still preventing runaway execution.

Deduplication does not make the search exhaustive outside the explicit actions, parameters, actors, time model, depth and invariants.

## Next step

The natural follow-up is fork-based execution against explicitly authorized real-world contracts, while preserving state hashes, minimal paths and deterministic report evidence.
