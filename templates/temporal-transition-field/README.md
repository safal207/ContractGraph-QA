# Temporal Transition Field Template

A reusable ContractGraph-QA pattern for stateful systems where correctness depends on **state + transition + time + invariants + evidence**, not only on individual request/response pairs.

## Core idea

Instead of asking only `did the request return the expected status?`, model the system as:

`Test Case -> Transition -> State Vector -> Guard -> Invariant -> Evidence -> Forbidden-State Reachability -> Finding`

This makes concurrency, retry/idempotency, boundary behavior, stale state, accounting divergence, impossible transitions, and shortest violating paths explicit and testable.

## Files

### v0.1 — transition field

- `transition_field.example.yaml` — generic state vector, states, events, transitions, and invariants.
- `test_matrix_template.csv` — reusable test matrix for boundaries, retries, concurrency, evidence, and reset/isolation.
- `transition_adjacency_matrix.csv` — example adjacency matrix for allowed and forbidden transitions.
- `generate_paths.py` — bounded breadth-first path generator for graph exploration.
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
- `test_detect_forbidden_state.py` — regression tests for limit crossing, rejected-state mutation, missing evidence, deterministic finding IDs, scoped replay rules, and fail-closed missing operands.

The detector deliberately does **not** use `eval()` or arbitrary expression execution. Rules use a small allow-listed comparison vocabulary (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `nonempty`) over JSON paths or literal values.

A rule has three parts:

`WHEN condition(s) -> ASSERT invariant -> otherwise FORBIDDEN_STATE`

If the assertion fails, the detector emits a deterministic finding bound to the observed-transition fingerprint. Generated verdict/invariant annotations are excluded from that fingerprint so annotating the same observation does not change its identity. If a required operand is missing, the result is `inconclusive`, never PASS.

### v0.4 — automatic path-to-finding

- `synthetic_adapter.py` — offline in-memory safe and deliberately buggy adapters for demonstration/regression.
- `auto_path_to_finding.py` — explores bounded paths in breadth-first order, replays every candidate from an isolated adapter instance, captures every transition, invokes the detector, and stops on the first violation.
- `test_auto_path_to_finding.py` — verifies shortest-path discovery, safe bounded search, deterministic finding IDs, and hard search bounds.

The v0.4 loop was:

`MODEL -> BFS PATH -> ISOLATED REPLAY -> EVIDENCE RECORD -> DETECTOR -> QX? -> MINIMAL FINDING`

Because candidate paths are breadth-first and each candidate is replayed from a fresh adapter state, the first detected violation is a **shortest violating path within the configured depth/path bounds**. That statement is intentionally bounded; it is not a claim that no shorter path exists outside the modeled transition graph or input corpus.

### v0.5 — guarded transitions

- `transition_guards.example.json` — binds explicit pre-state predicates to exact `(from, event, to)` edges.
- `guard_engine.py` — evaluates transition guards using the same constrained comparison vocabulary as the forbidden-state detector.
- `test_guard_engine.py` — checks allowed, blocked, undeclared, and fail-closed inconclusive guard outcomes.
- `auto_path_to_finding.py` — now performs **guarded BFS** instead of expanding every syntactically reachable edge.

The v0.5 loop is:

`MODEL -> CURRENT X(t) -> EDGE GUARD -> ALLOW / BLOCK / INCONCLUSIVE`

Allowed edges may execute. Blocked edges are pruned and never expanded. If a guard cannot be evaluated because required state is missing or incomparable, that branch becomes `inconclusive` and is not expanded.

This means a transition may exist in the static graph while still being unreachable from the current observed state. Example:

`Q2_READY --duplicate_retry--> Q6_REPLAY_CHECK`

is statically declared, but the bundled guard requires `transaction_count > 0`. Immediately after policy setup, `transaction_count == 0`, so that edge is pruned rather than executed.

The guarded search loop is therefore:

`MODEL -> BFS PREFIX -> X(t) -> GUARD -> EXECUTE -> EVIDENCE -> DETECTOR -> QX?`

Only prefixes that remain model-consistent and guard-enabled are expanded. This reduces impossible-path exploration before any real adapter is called and makes the transition model closer to a guarded state machine than a plain adjacency graph.

## Modeling pattern

Represent state at time `t` as a vector:

`X(t) = [resource_balance, consumed_budget, budget_limit, per_action_limit, tx_count, evidence_count, accepted_count, rejected_count]`

A guarded transition is:

`X(t) --[guard(event, X(t))]--> X(t+1)`

A useful test does not only inspect the HTTP/RPC result. It checks whether the edge was enabled, whether the observed transition preserves invariants, and whether all evidence surfaces agree with the committed state.

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

for all guard-enabled action sequences within the bounded model.

## Recommended workflow

1. Define the state vector.
2. Enumerate stable states.
3. Define events and static transitions.
4. Bind pre-state guards to transitions that are only conditionally enabled.
5. Define global invariants and forbidden states.
6. Explore guarded transition paths breadth-first under explicit bounds.
7. Execute only within an authorized sandbox/local-fork/test environment.
8. Capture `before -> guard -> request -> decision -> mutation -> after -> evidence`.
9. Serialize one `evidence_record` per executed transition.
10. Build a deterministic evidence graph and record digest.
11. Run the forbidden-state detector against explicit machine-readable rules.
12. Classify observations as `violated`, `inconclusive`, or bounded non-findings.
13. Stop at the first forbidden state and retain the minimal guard-enabled replay path plus evidence records.
14. Convert that violation into a reproducible finding tied to the observed-transition fingerprint.

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

## Guarded automatic path-to-finding demo

Deliberately buggy, fully in-memory concurrency model:

```bash
python auto_path_to_finding.py \
  --adapter synthetic-buggy \
  --max-depth 6 \
  --max-paths 250 \
  --out-dir path-to-finding
```

Guards are enabled by default from `transition_guards.example.json`. Use `--no-guards` only for v0.4 compatibility/regression.

Expected minimal path in the bundled synthetic model:

`fund -> set_policy -> concurrent_action -> CUMULATIVE_LIMIT_EXCEEDED`

The output includes guard statistics and the number of candidate paths pruned before execution/expansion.

The output directory contains:

```text
path-to-finding/
  search_result.json
  finding.json
  minimal_path.json
  evidence_records/
    step-01.json
    step-02.json
    step-03.json
  violating_evidence_graph/
    evidence.dot
    evidence.md
    record.sha256
```

The safe in-memory adapter can be used as a negative control:

```bash
python auto_path_to_finding.py --adapter synthetic-safe
```

`not_found_within_bound` and `not_found_within_observed_transition` are bounded evidence only. They are not security certifications and do not imply that all paths, parameters, actors, time shifts, guards, or invariants have been covered.

## Adapter boundary

`auto_path_to_finding.py` depends only on two adapter operations:

- `snapshot()` — return a state snapshot with `state_id` and `values`;
- `apply(event)` — execute one modeled event and return request, decision, mutation, and evidence fields.

The guard engine runs against `snapshot()` **before** `apply(event)`. Therefore a real adapter can be protected from impossible or out-of-scope calls before target interaction happens.

The bundled CLI exposes only offline synthetic adapters. Real integrations should instantiate `search_paths(...)` programmatically with a separately reviewed adapter that enforces authorization, endpoint/contract scope, environment restrictions, bounded concurrency, credential handling, and reset/replay isolation.

## Safety defaults

The runner/search templates are intentionally conservative:

- bounded `max_depth` and `max_paths`;
- guard evaluation before adapter action execution;
- blocked and inconclusive branches are not expanded;
- isolated adapter instance for each candidate path;
- dry-run by default where a network-capable runner exists;
- credentials only through environment variables;
- explicit endpoint/target allow-list in real adapters;
- bounded concurrency;
- no production assumptions;
- no hidden load testing;
- reset/isolation between independent runs where supported.

The evidence-graph builder, forbidden-state detector, guard engine, and bundled synthetic adapters are offline-only and perform no target-system network request.

This template is intentionally client-neutral and can be adapted to Solidity state machines, payment APIs, agent-control systems, workflow engines, and other stateful software.
