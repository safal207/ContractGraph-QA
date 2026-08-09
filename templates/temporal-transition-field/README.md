# Temporal Transition Field Template

A reusable ContractGraph-QA pattern for stateful systems where correctness depends on **state + transition + time + invariants + evidence**, not only on individual request/response pairs.

## Core idea

Instead of asking only `did the request return the expected status?`, model the system as:

`Test Case -> Transition -> State Vector -> Guard -> Invariant -> Evidence -> Forbidden-State Reachability -> Finding`

This makes concurrency, retry/idempotency, boundary behavior, stale state, accounting divergence, impossible transitions, and shortest violating paths explicit and testable.

## Version ladder

- **v0.1 — Transition Field:** state vector, transitions, invariants, test matrix, bounded path generation.
- **v0.2 — Evidence Graph:** deterministic `PRE -> REQUEST -> DECISION -> MUTATION -> POST -> EVIDENCE -> VERDICT` trace and SHA-256 record digest.
- **v0.3 — Forbidden-State Detector:** fail-closed constrained rule DSL, deterministic findings, no arbitrary expression execution.
- **v0.4 — Automatic Path-to-Finding:** bounded BFS, isolated replay, per-transition evidence capture, shortest violating path within configured bounds.
- **v0.5 — Guarded Transitions:** pre-state predicates decide whether a static edge is executable before the adapter is called.

## v0.5 guarded transitions

- `transition_guards.example.json` binds guards to exact `(from, event, to)` edges.
- `guard_engine.py` evaluates guards with the same allow-listed comparison vocabulary as the forbidden-state detector.
- `test_guard_engine.py` covers allowed, blocked, undeclared, and fail-closed inconclusive outcomes.
- `auto_path_to_finding.py` performs guarded BFS and never expands a blocked or inconclusive branch.

A static edge may exist without being executable for the current state:

`Q2_READY --duplicate_retry--> Q6_REPLAY_CHECK`

The bundled guard requires `transaction_count > 0`. Immediately after policy setup the count is zero, so the edge is pruned before `apply(event)`.

The guarded search loop is:

`MODEL -> BFS PREFIX -> X(t) -> GUARD -> EXECUTE -> EVIDENCE -> DETECTOR -> QX? -> MINIMAL FINDING`

Allowed edges execute. Blocked edges are pruned. Missing/incomparable guard operands produce `inconclusive`, never PASS, and the branch is not expanded.

## Modeling pattern

Represent state at time `t` as:

`X(t) = [resource_balance, consumed_budget, budget_limit, per_action_limit, transaction_count, evidence_count, accepted_count, rejected_count]`

A guarded transition is:

`X(t) --[guard(event, X(t))]--> X(t+1)`

The preferred bounded property is:

`P(reachable(QX_FORBIDDEN)) = 0`

for all guard-enabled action sequences inside the declared model/search bounds.

## Core files

- `transition_field.example.yaml` — state model and static edges; references the guard/rule documents.
- `transition_guards.example.json` — v0.5 edge guards.
- `forbidden_state_rules.example.json` — forbidden-state assertions.
- `test_matrix_template.csv` — reusable boundary/retry/concurrency/evidence test matrix.
- `transition_adjacency_matrix.csv` — static adjacency example.
- `generate_paths.py` — plain bounded graph path generator.
- `bounded_runner_template.py` — conservative dry-run execution skeleton.
- `evidence_record.schema.json` / `evidence_record.example.json` — transition evidence contract/example.
- `build_evidence_graph.py` — Graphviz/Markdown/digest evidence outputs.
- `detect_forbidden_state.py` — v0.3 detector.
- `guard_engine.py` — v0.5 guard evaluator.
- `synthetic_adapter.py` — offline safe and deliberately buggy adapters.
- `auto_path_to_finding.py` — guarded BFS path-to-finding engine.

## Guarded path-to-finding demo

```bash
python auto_path_to_finding.py \
  --adapter synthetic-buggy \
  --max-depth 6 \
  --max-paths 250 \
  --out-dir path-to-finding
```

Guards are enabled by default from `transition_guards.example.json`. `--no-guards` is available only for v0.4 compatibility/regression.

Expected minimal path in the bundled buggy model:

`fund -> set_policy -> concurrent_action -> CUMULATIVE_LIMIT_EXCEEDED`

The result includes `paths_pruned_by_guard` and aggregate guard statistics. A violating run exports `finding.json`, `minimal_path.json`, per-step evidence records, and the violating evidence graph/digest.

The safe in-memory adapter is a negative control:

```bash
python auto_path_to_finding.py --adapter synthetic-safe
```

## Adapter boundary

The path engine depends on:

- `snapshot()` — observed state with `state_id` and `values`;
- `apply(event)` — request, decision, mutation, and evidence for one modeled event.

The guard engine runs against `snapshot()` **before** `apply(event)`. A real adapter can therefore avoid impossible or out-of-scope target calls rather than detecting them only after execution.

Real integrations must use separately reviewed, explicitly authorized adapters with environment/target allow-lists, bounded concurrency, credential isolation, and reset/replay isolation.

## Safety and evidence semantics

- bounded `max_depth` and `max_paths`;
- guard evaluation before adapter action execution;
- blocked/inconclusive branches are not expanded;
- fresh adapter instance per candidate path;
- dry-run default where network-capable runners exist;
- credentials via environment variables only;
- no production assumptions or hidden load testing;
- detector and guards use a constrained DSL, not `eval()`;
- missing evidence fails closed as `inconclusive`;
- `not_found_within_bound` is bounded evidence only, never a security certification.

The bundled evidence builder, detector, guard engine, and synthetic adapters are offline-only.

This template is client-neutral and can be adapted to Solidity state machines, payment APIs, agent-control systems, workflow engines, and other stateful software.
