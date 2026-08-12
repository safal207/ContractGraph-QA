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

## CLI

The repository-owned model can be executed directly:

```bash
cgqa reachability --model scenarios/adversarial-wallet-replay.json
```

The command loads and validates the strict JSON model, runs deterministic bounded breadth-first search, and emits an evidence-oriented JSON result with:

- `status`: `reachable` or `not_found_within_bound`;
- `modelSha256`: canonical model fingerprint;
- `maxDepth`;
- declared violated assumptions and target capabilities;
- the shortest reachable `ImpactPath`, when one exists.

Example shape:

```json
{
  "status": "reachable",
  "modelSha256": "...",
  "maxDepth": 4,
  "path": {
    "initialCapability": "request-spend",
    "targetCapability": "duplicate-settlement",
    "violatedAssumptions": ["fresh-policy-state", "unique-settlement"],
    "invariantIds": ["settlement-at-most-once"],
    "crossedBoundaries": ["settlement-idempotency"],
    "impact": "duplicate financial settlement",
    "transitions": []
  }
}
```

The exact selected path is deterministic for the same semantic model and bound. When multiple targets are reachable at the same depth, deterministic adjacency ordering provides the tie-break.

## Runtime model contract

`contractgraph_qa.reachability` includes a strict stdlib-only loader. The runtime rejects:

- unexpected root or entity fields;
- missing required fields;
- whitespace-only identifiers or descriptions;
- duplicate values in capability/assumption reference arrays;
- duplicate capability, assumption, or transition identifiers;
- unknown source/target capabilities;
- unknown assumption references;
- invalid `maxDepth` values.

The checked-in JSON Schema is:

[`graph/schema/adversarial-reachability.schema.json`](../graph/schema/adversarial-reachability.schema.json)

`tools/check_schema_contract.py` binds this schema to the runtime key sets, required fields, non-blank string rules, optional fields, and bound semantics so schema/runtime drift fails CI.

## Determinism and fail-closed behavior

The MVP follows the existing ContractGraph-QA evidence philosophy:

- edge traversal requires all declared assumption violations;
- adjacency ordering is deterministic;
- model serialization is canonicalized before SHA-256 fingerprinting;
- search is bounded by `maxDepth`;
- no reachable path is not a proof of safety beyond the declared model and bound;
- malformed or ambiguous models fail closed before search.

## Python API

```python
from pathlib import Path
from contractgraph_qa.reachability import (
    load_reachability_model,
    run_reachability_model,
)

model = load_reachability_model(Path("scenarios/adversarial-wallet-replay.json"))
result = run_reachability_model(model)
```

The module provides the domain model, strict validation, deterministic model hashing, bounded reachability, and stable semantic serialization for evidence integration.

## Evidence bundle integration

The reachability model can now be bound into the existing single-finding product pipeline with an optional product-config field:

```toml
reachabilityModel = "scenarios/adversarial-wallet-replay.json"
```

When `reachabilityModel` is absent, `cgqa run` keeps producing the existing backward-compatible **bundle v1**.

When it is present, the pipeline loads and re-runs the model, attaches the deterministic result to `finding.json -> evidence.reachability`, and emits **bundle v2**:

```text
manifest.json
result.json
reachability-model.json
reachability.json
finding.json
report.md
bundle.json
```

The reachability model is serialized canonically inside the bundle. `reachability.json` contains the bounded result and `modelSha256`; `finding.json` references both bundle artifacts and embeds the same deterministic semantic result.

`cgqa verify-bundle` independently checks the v2 chain:

```text
reachability-model.json
        ↓ strict runtime validation
canonical model SHA-256
        ↓
deterministic bounded search
        ↓
reachability.json
        ↓
finding.json evidence binding
        ↓
report.md
```

Verification rejects artifact hash/size drift, non-canonical model bytes, a reachability result that does not recompute from the bundled model, a mismatched `reachabilityModelSha256`, or a finding that does not match the recomputed reachability evidence.

This keeps the existing contract/result evidence chain intact while adding a second independently recomputable causal path.

## Next integration steps

1. Record recovery/containment and verification nodes explicitly.
2. Render a dedicated human-readable capability/reachability section in the client report.
3. Add dedicated examples for approval bypass, stale/revoked authority, idempotency/replay, and duplicate settlement.
4. Include the graph path in the client proof pack.
5. Compare old/new reachability graphs to detect newly reachable forbidden capabilities after a patch or PR.

Tracking issue: #26.
