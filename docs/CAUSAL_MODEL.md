# Causal-temporal model

ContractGraph-QA models execution as an ordered graph of observed state transitions.

## Node

A node represents a contract state at a point in execution time. A useful state snapshot can include:

- contract state label;
- block number;
- timestamp;
- relevant storage values or a storage hash;
- relevant account/contract balances;
- emitted events accumulated up to the node.

## Edge

An edge represents one transition caused by an actor action under explicit preconditions.

```text
(cause, actor, action, parameters, time)
                    ↓
               pre-state
                    ↓
              transition
                    ↓
               post-state
                    ↓
                 effect
```

A transition is evidence, not a claim of philosophical causality. `cause` records the operational trigger we are testing: a transaction, a time threshold, an oracle update, a governance change, a callback, or another observable input.

## Time

Time is part of the state space. Two otherwise identical storage states can have different reachable futures if `block.timestamp`, `block.number`, oracle freshness or governance epochs differ.

Examples:

```text
FUNDED @ T0 --refund--> revert
FUNDED @ T0+7d --refund--> REFUNDED
```

## Reachability

The testing problem is to explore paths of the form:

```text
S0 --a1--> S1 --a2--> S2 ... --an--> Sn
```

and ask whether any reachable `Sn` violates an invariant.

The first practical target is not exhaustive formal verification. v0.1 records deterministic paths and verifies explicit invariants. Later versions can generate and minimize action sequences automatically.

## Minimal failing path

When an invariant fails, the useful artifact is the shortest reproducible path known to the tool:

```text
S0
→ fund(100)
→ release()
→ refund()
→ payout-conservation violated
```

That path can become a regression test after the contract is fixed.

## Evidence principle

A finding should be backed by:

1. initial state;
2. ordered actions;
3. actor identity;
4. time/block context where relevant;
5. pre/post states;
6. invariant expression;
7. exact step where the invariant first fails;
8. deterministic replay instructions.

## Measurement provenance invariant

Evidence is only as attributable as the measurement process that produced it. Before a measured value can support a finding or decision, the measurement itself should carry enough provenance to answer four questions: which semantics produced the value, which routes or sources were observable, what was actually measured, and what consumed the result.

```text
measurement → schema_epoch → coverage_scope → evidence → decision
```

The chain means:

- `measurement` identifies the collector, verifier, scanner, or probe that produced the value;
- `schema_epoch` identifies the version of the measurement semantics and accumulator layout;
- `coverage_scope` declares the routes, sources, nodes, files, calls, or events the instrument was capable of observing;
- `evidence` is the measured claim emitted under that epoch and scope;
- `decision` is the verdict, action, or downstream conclusion that consumes the evidence.

The invariant is violated when a downstream decision treats a measurement as stronger than its provenance permits. Important failure shapes include:

1. **epoch mixing** — counters accumulated under different schemas are combined without an explicit migration or full recomputation;
2. **coverage collapse** — absence of an observation under partial instrumentation is interpreted as proof that the event did not occur;
3. **denominator ambiguity** — a coverage percentage does not state what its denominator represents, for example tool-call route coverage versus source coverage or evidence coverage;
4. **unknown-to-false coercion** — an unmeasured state is represented as `false`, `no read`, or `no finding` rather than `unknown` / `unmeasured`;
5. **authority drift** — a write-time witness that proves binding is later treated as proof that the source is still current at use time.

A robust verifier should therefore keep binding and freshness separate:

```text
write-time witness → proves observation/binding
use-time source check → proves currentness/freshness
```

Coverage accounting is a precondition on those instruments, not a third source of authority. If an ingestion route bypasses the write-time witness, the correct conclusion is that the route is uncovered, not that the source was never observed.

Content identity and source identity should also remain distinct. A digest identifies the observed bytes; a source locator identifies where the evidence came from under a declared namespace and normalization policy. Provenance may need both because source drift is itself a finding rather than a lookup failure.

The executable v0.1 gate lives in `contractgraph_qa.measurement_provenance` with `tools/run_measurement_provenance_gate.py` as the CLI. It blocks `EPOCH_MISMATCH`, coverage below an explicitly declared `requiredCoverage`, and `UNMEASURED`; an unavailable measurement preserves its counts and derived coverage as `null` rather than manufacturing a negative observation.

For ContractGraph-QA, this principle limits evidence claims to what the active measurement epoch and declared coverage scope can actually support. A green result must not silently mean `nothing was measured`.
