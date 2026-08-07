# Path Explorer

`PathExplorerHarness` is the v0.2 search layer for ContractGraph-QA.

Instead of writing one expected exploit or failure sequence by hand, a concrete test model exposes a finite action alphabet and lets the explorer enumerate reachable action sequences.

## Search model

For an action set `A` and maximum depth `D`, the explorer checks candidate sequences in breadth-first order:

```text
depth 1:  A0, A1, A2, ...
depth 2:  A0A0, A0A1, A0A2, ...
depth 3:  A0A0A0, A0A0A1, ...
```

Each candidate starts from a fresh target instance.

For every action:

1. execute the action;
2. reject the path if the transition is not accepted;
3. check the invariant immediately after an accepted transition;
4. stop when the invariant first fails.

Because depths are explored from shortest to longest, the first failing sequence is minimal by action count within the modeled action space.

## Escrow example

The demo action alphabet is:

```text
0 = fund
1 = release
2 = refund
```

The deliberately vulnerable escrow keeps the contract in `FUNDED` after `release()`.

The explorer therefore discovers:

```text
CREATED
  ↓ fund
FUNDED
  ↓ release
FUNDED
  ↓ refund
REFUNDED
  ↓
releasedAmount + refundedAmount > depositedAmount
```

No violation is reachable in one or two accepted actions. The first violation requires three actions:

```text
fund → release → refund
```

## Deterministic replay

The returned `SearchResult.path` can be replayed against a fresh target with `_replay(path)`.

That gives the QA evidence chain:

```text
Search
  ↓
Minimal failing path
  ↓
Deterministic replay
  ↓
Invariant violation
  ↓
Regression test after fix
```

## Current boundary

v0.2 intentionally keeps the model finite and deterministic. It does not claim exhaustive verification of arbitrary Solidity programs.

The current explorer assumes:

- a finite action alphabet;
- a bounded search depth;
- deterministic target reset;
- explicit invariant functions supplied by the test model.

Future versions can add parameter fuzzing, state hashing/deduplication, temporal actions, fork-based execution, multi-contract action spaces and search heuristics.
