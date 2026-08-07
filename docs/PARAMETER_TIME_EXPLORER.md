# Parameter and time explorer

v0.4 extends bounded path exploration from action order to a finite corpus of **parameterized steps**.

A step is modeled as:

```text
(action, parameter)
```

The parameter may be a business input such as an amount, or a temporal input such as a time delta.

## Why this matters

Many smart-contract defects are not reachable through call order alone. They depend on:

- boundary values;
- amounts around a business limit;
- timestamps and waiting periods;
- combinations of value choices and state transitions.

v0.4 makes those dimensions explicit and replayable.

## Search model

A concrete model exposes a finite step corpus. The local timed-escrow example uses:

```text
fund(1)
fund(100)
fund(101)
wait(1 day)
wait(7 days)
refund()
```

The explorer performs breadth-first search over sequences of those concrete cases. Each candidate starts from a deterministic baseline timestamp and a fresh target instance.

The first invariant violation is therefore minimal by **step count** within the modeled corpus and depth.

## Parameter-boundary example

The fixture declares a maximum deposit of 100 but deliberately fails to enforce it.

The one-step corpus sweep checks:

```text
fund(1)   -> invariant holds
fund(100) -> invariant holds
fund(101) -> deposit-cap invariant fails
```

This demonstrates deterministic boundary-value exploration rather than a single hard-coded happy path.

## Temporal example

The fixture's intended refund delay is seven days, while its deliberately incorrect implementation allows refund after one day.

The explorer discovers:

```text
CREATED
  ↓ fund(1)
FUNDED
  ↓ wait(1 day)
FUNDED @ T+1d
  ↓ refund()
REFUNDED
  ↓
refund occurred before expected T+7d
```

The same three-step path is replayed against a fresh instance to confirm the temporal invariant fails deterministically.

A control path using `wait(7 days)` is also tested and preserves the timing invariant.

## Deterministic reset

Temporal exploration must reset both contract state and clock state. The test model therefore restores a fixed baseline timestamp before deploying each fresh target.

Without a clock reset, one candidate's time jump could leak into later candidates and invalidate reproducibility.

## Scope boundary

The corpus is explicit and finite. v0.4 does not claim exhaustive fuzzing of every numeric value or timestamp.

The current model provides deterministic corpus-based parameter exploration. Future work can combine this with Foundry-generated fuzz values, state hashing/deduplication, adaptive corpus growth, fork execution, and automatic export into the v0.3 finding-report format.

Use only on owned, local, open-source, explicitly authorized, or in-scope bug-bounty targets.
