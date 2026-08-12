# Adversarial Reachability

Adversarial Reachability extends ContractGraph-QA from state/invariant reachability into explicit **capability reachability**.

The question is not only whether a reachable state violates an invariant. It is also:

> Can a broken system assumption make a previously forbidden capability reachable, cross a control boundary, and produce a reproducible impact?

## Canonical causal chain

```text
actor / action
      ↓
assumption
      ↓
assumption violation
      ↓
state transition
      ↓
capability transition
      ↓
invariant / control boundary
      ↓
reachable forbidden capability
      ↓
impact
      ↓
recovery / containment
      ↓
verification / evidence
```

This layer is intentionally narrower than autonomous exploit generation. It treats exploit-like reasoning as a **hypothesis about reachability** that must be represented by explicit edges and then backed by deterministic evidence.

## Core entities

### `Assumption`

An explicit condition the modeled system relies on, for example:

- policy state is fresh;
- authority has not expired or been revoked;
- a logical payment settles at most once;
- a rejected request does not mutate financial state.

### `AssumptionViolation`

Evidence or a test hypothesis that an assumption does not hold.

A broken assumption is not itself an invariant failure. It is a guard that may make new transitions reachable.

### `Capability`

A behavior that an actor or system can perform or cause. Capabilities can be expected or forbidden.

Examples:

```text
request-spend
→ authorized-spend
→ overspend               [forbidden]
```

or:

```text
authorized-spend
→ duplicate-settlement    [forbidden]
```

### `CapabilityTransition`

A directed edge from one capability to another. An edge may require one or more violated assumptions and may record:

- the invariant implicated by the transition;
- the control boundary crossed;
- the impact made reachable.

### `ImpactPath`

The shortest deterministic path currently known from an allowed initial capability to a target capability.

The MVP uses bounded breadth-first search and returns no path when the target is not reachable within the configured depth.

## Programmable wallet example

Repository-owned demo model:

[`scenarios/adversarial-wallet-replay.json`](../scenarios/adversarial-wallet-replay.json)

One reachable path is:

```text
request-spend
  --[fresh-policy-state violated]-->
authorized-spend
  --[daily-limit invariant / delegated-spend-policy boundary]-->
overspend
  → unauthorized financial loss
```

A second path requires the settlement uniqueness assumption to be violated:

```text
request-spend
  --[fresh-policy-state violated]-->
authorized-spend
  --[unique-settlement violated]-->
duplicate-settlement
  → duplicate financial settlement
```

## Determinism and fail-closed behavior

The MVP follows the existing ContractGraph-QA evidence philosophy:

- models reject duplicate capability and transition identifiers;
- unknown source/target capabilities are rejected;
- unknown assumption references are rejected when assumptions are declared;
- edge traversal requires all declared assumption violations;
- adjacency ordering is deterministic;
- search is bounded by `max_depth`;
- no reachable path is not a proof of safety beyond the declared model and bound.

## Python API

The first vertical slice lives in `contractgraph_qa.reachability`:

```python
from contractgraph_qa.reachability import find_shortest_impact_path
```

The module currently provides the domain model, validation, bounded deterministic search, and stable semantic serialization for later evidence integration.

## Next integration steps

1. Parse the JSON model directly into the Python domain objects.
2. Add schema/runtime contract checks to CI.
3. Bind `ImpactPath` output into finding JSON and deterministic evidence ZIPs.
4. Record recovery/containment and verification nodes explicitly.
5. Add CLI support such as `cgqa reachability --model ...`.
6. Compare old/new reachability graphs to detect newly reachable forbidden capabilities after a patch or PR.

Tracking issue: #26.
