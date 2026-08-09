# Temporal Transition Field Template

A reusable ContractGraph-QA pattern for stateful systems where correctness depends on **state + transition + time + invariants + evidence**, not only on individual request/response pairs.

## Core idea

Instead of asking only `did the request return the expected status?`, model the system as:

`Test Case -> Transition -> State Vector -> Invariant -> Evidence -> Forbidden-State Reachability`

This makes concurrency, retry/idempotency, boundary behavior, stale state, and accounting divergence explicit and testable.

## Files

- `transition_field.example.yaml` — generic state vector, states, events, transitions, and invariants.
- `test_matrix_template.csv` — reusable test matrix for boundaries, retries, concurrency, evidence, and reset/isolation.
- `transition_adjacency_matrix.csv` — example adjacency matrix for allowed and forbidden transitions.
- `generate_paths.py` — bounded path generator for graph exploration.
- `bounded_runner_template.py` — sandbox-only execution skeleton with dry-run default and explicit scope guards.

## Modeling pattern

Represent state at time `t` as a vector:

`X(t) = [resource_balance, consumed_budget, budget_limit, per_action_limit, tx_count, evidence_count, accepted_count, rejected_count]`

A transition is:

`X(t) --event--> X(t+1)`

A useful test does not only inspect the HTTP/RPC result. It checks whether the transition preserves invariants and whether all evidence surfaces agree with the committed state.

## Forbidden states

Examples:

- cumulative consumption exceeds policy limit;
- rejected action mutates financial or durable state;
- duplicate/retry produces a second mutation;
- committed state is missing audit evidence;
- transaction history and state diverge;
- concurrent requests create an impossible aggregate state;
- equivalent endpoints enforce different policy semantics.

The preferred property is:

`P(reachable(QX_FORBIDDEN)) = 0`

for all valid action sequences within the bounded model.

## Recommended workflow

1. Define the state vector.
2. Enumerate stable states.
3. Define events and allowed transitions.
4. Define global invariants.
5. Mark forbidden states explicitly.
6. Generate bounded transition paths.
7. Execute only within an authorized sandbox/local-fork/test environment.
8. Capture before -> request -> response -> after -> evidence.
9. Evaluate invariant verdicts.
10. Convert any forbidden transition into a reproducible finding.

## Safety defaults

The runner template is intentionally conservative:

- dry-run unless execution is explicitly enabled;
- credentials only through environment variables;
- explicit endpoint allow-list;
- bounded concurrency;
- no production assumptions;
- no hidden load testing;
- reset/isolation between independent runs where supported.

This template is intentionally client-neutral and can be adapted to Solidity state machines, payment APIs, agent-control systems, workflow engines, and other stateful software.