# Shared Causal Graph Vocabulary

Adversarial reachability paths are mapped into one deterministic causal vocabulary so financial-control, capability-escalation, recovery, and evidence layers can refer to the same graph semantics.

The core relations are:

- `requires` — a capability transition requires an explicit assumption violation;
- `enables` — a reachable capability enables the selected transition;
- `escalates_to` — the transition reaches the next capability;
- `violates` — the transition binds to an invariant that becomes explicitly violated on the selected path.

`contractgraph_qa.causal_graph.build_causal_graph()` derives this graph from an already-selected deterministic `ImpactPath`; it does not widen search or invent additional reachability.

Example shape:

```text
capability:request-escrow-release
  └─ enables → transition:bypass-approval-threshold
                    ├─ requires → assumption-violation:approval-threshold-enforced
                    ├─ violates → invariant:escrow-release-requires-approval
                    └─ escalates_to → capability:release-without-required-approval
```

The transition node preserves its declared control boundary and business impact. The graph also records `firstInvariantViolation` with the exact path index, transition id, invariant id, source capability, and target capability.

`usedAssumptionViolations` is intentionally path-scoped: only assumption violations actually required by the selected transitions are included, even if the broader scenario declares additional broken assumptions. This avoids overstating causal evidence.

The mapper is local, deterministic, stdlib-only, and safe to use in client proof/evidence generation. It does not claim production exploitability or infer missing edges.
