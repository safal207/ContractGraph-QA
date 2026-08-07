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
