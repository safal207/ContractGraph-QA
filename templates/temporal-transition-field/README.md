# Temporal Transition Field Template

A reusable ContractGraph-QA pattern for stateful systems where correctness depends on **state + transition + time + invariants + evidence**, not only on individual request/response pairs.

## Core idea

Instead of asking only `did the request return the expected status?`, model the system as:

`Test Case -> Transition -> State Vector -> Invariant -> Evidence -> Forbidden-State Reachability`

This makes concurrency, retry/idempotency, boundary behavior, stale state, and accounting divergence explicit and testable.

## Files

### v0.1 — transition field

- `transition_field.example.yaml` — generic state vector, states, events, transitions, and invariants.
- `test_matrix_template.csv` — reusable test matrix for boundaries, retries, concurrency, evidence, and reset/isolation.
- `transition_adjacency_matrix.csv` — example adjacency matrix for allowed and forbidden transitions.
- `generate_paths.py` — bounded path generator for graph exploration.
- `bounded_runner_template.py` — sandbox-only execution skeleton with dry-run default and explicit scope guards.

### v0.2 — evidence graph

- `evidence_record.schema.json` — machine-readable contract for one observed transition.
- `evidence_record.example.json` — synthetic client-neutral concurrency example.
- `build_evidence_graph.py` — converts one record into Graphviz DOT, Markdown trace, and deterministic SHA-256 digest.
- `test_build_evidence_graph.py` — regression checks for graph topology, report output, and digest determinism.

The evidence chain is modeled as:

`PRE-STATE -> REQUEST -> DECISION -> MUTATION -> POST-STATE -> EVIDENCE -> VERDICT`

Invariant nodes branch from the observed post-state and feed the final verdict. This keeps the final conclusion traceable to both state mutation and independent evidence surfaces.

### v0.3 — forbidden-state detector

- `forbidden_state_rules.example.json` — constrained, client-neutral rule DSL.
- `detect_forbidden_state.py` — evaluates one evidence record against explicit forbidden-state rules.
- `test_detect_forbidden_state.py` — regression tests for limit crossing, rejected-state mutation, missing evidence, deterministic finding IDs, and fail-closed missing operands.

The detector deliberately does **not** use `eval()` or arbitrary expression execution. Rules use a small allow-listed comparison vocabulary (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `nonempty`) over JSON paths or literal values.

A rule has three parts:

`WHEN condition(s) -> ASSERT invariant -> otherwise FORBIDDEN_STATE`

If the assertion fails, the detector emits a deterministic finding bound to the exact evidence fingerprint. If a required operand is missing, the result is `inconclusive`, never PASS.

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
8. Capture `before -> request -> decision -> mutation -> after -> evidence`.
9. Serialize one `evidence_record` per observed transition.
10. Build a deterministic evidence graph and record digest.
11. Run the forbidden-state detector against explicit machine-readable rules.
12. Classify the observation as `violated`, `inconclusive`, or `not_found_within_observed_transition`.
13. Convert a violation into a reproducible finding tied to its evidence fingerprint.

## Evidence graph usage

```bash
python build_evidence_graph.py evidence_record.example.json --out-dir evidence-graph
```

It produces:

```text
evidence-graph/
  evidence.dot
  evidence.md
  record.sha256
```

## Forbidden-state detector usage

```bash
python detect_forbidden_state.py \
  evidence_record.example.json \
  forbidden_state_rules.example.json \
  --output detector-result.json
```

Exit codes:

- `0` — no forbidden state found in this observed transition;
- `1` — one or more explicit rules were violated;
- `2` — evaluation is inconclusive because required evidence is missing or not comparable.

`not_found_within_observed_transition` is bounded evidence only. It is not a security certification and does not imply that all paths or invariants have been covered.

## Safety defaults

The runner template is intentionally conservative:

- dry-run unless execution is explicitly enabled;
- credentials only through environment variables;
- explicit endpoint allow-list;
- bounded concurrency;
- no production assumptions;
- no hidden load testing;
- reset/isolation between independent runs where supported.

The evidence-graph builder and forbidden-state detector are offline-only: they perform no target-system action and make no network request.

This template is intentionally client-neutral and can be adapted to Solidity state machines, payment APIs, agent-control systems, workflow engines, and other stateful software.
