# Temporal Transition Field Template

A reusable ContractGraph-QA pattern for stateful systems where correctness depends on **state + transition + time + guards + invariants + evidence**, not only on isolated request/response pairs.

## Core idea

`Test Case -> State Vector -> Adapter Contract -> Guard -> Transition -> Evidence -> Invariant -> Forbidden-State Reachability -> Minimal Finding`

This makes concurrency, retry/idempotency, boundary behavior, stale state, accounting divergence, impossible transitions, adapter safety boundaries, and shortest violating paths explicit and testable.

## Version ladder

- **v0.1 — Transition Field:** state vector, transitions, invariants, test matrix, bounded path generation.
- **v0.2 — Evidence Graph:** deterministic `PRE -> REQUEST -> DECISION -> MUTATION -> POST -> EVIDENCE -> VERDICT` trace and SHA-256 record digest.
- **v0.3 — Forbidden-State Detector:** fail-closed constrained rule DSL, deterministic findings, no arbitrary expression execution.
- **v0.4 — Automatic Path-to-Finding:** bounded BFS, isolated replay, per-transition evidence capture, shortest violating path within configured bounds.
- **v0.5 — Guarded Transitions:** pre-state predicates decide whether a static edge is executable before the adapter is called.
- **v0.6 — Real Adapter Contract:** machine-readable authorization/scope/capability/state/evidence contract enforced before and during adapter execution.

## v0.6 real adapter contract

v0.6 separates the causal-temporal engine from a concrete target through a manifest plus runtime wrapper.

Files:

- `adapter_manifest.schema.json` — JSON Schema for the adapter contract.
- `adapter_manifest.synthetic.json` — valid offline manifest used by regression tests.
- `adapter_manifest.template.json` — intentionally fail-closed scaffold for a real integration; `authorized=false` and no supported events until reviewed.
- `adapter_contract.py` — semantic validation, model coverage checks, search-bound enforcement, snapshot/evidence validation, and runtime event allow-listing.
- `test_adapter_contract.py` — regression tests for production rejection, secret-container rejection, model coverage, search bounds, state/evidence shape, and contract-bound search.

A manifest declares:

```text
IDENTITY
  adapter_id / target_kind
        ↓
SCOPE
  authorized / environment / production=false / target
        ↓
EXECUTION BOUNDS
  dry-run default / max concurrency / max depth / max paths
        ↓
CREDENTIAL POLICY
  none OR environment-variable names only
        ↓
CAPABILITIES
  snapshot / apply / full model event coverage
        ↓
STATE CONTRACT
  required X(t) fields
        ↓
EVIDENCE CONTRACT
  required request / decision / mutation / evidence fields
```

The search engine validates the manifest and full model-event coverage **before the first adapter action**. Each `snapshot()` and `apply(event)` result is validated again through `ContractBoundAdapter`.

Production scope is rejected by the reusable template. Literal credential values do not belong in adapter manifests; only environment-variable names may be declared.

## v0.5 guarded transitions

- `transition_guards.example.json` binds guards to exact `(from, event, to)` edges.
- `guard_engine.py` evaluates guards with an allow-listed comparison vocabulary.
- `auto_path_to_finding.py` performs guarded BFS and never expands a blocked or inconclusive branch.

A static edge may exist without being executable for the current state:

`Q2_READY --duplicate_retry--> Q6_REPLAY_CHECK`

The bundled guard requires `transaction_count > 0`. Immediately after policy setup the count is zero, so the edge is pruned before `apply(event)`.

The contract-bound guarded search loop is:

`MODEL -> ADAPTER MANIFEST/PREFLIGHT -> BFS PREFIX -> X(t) -> GUARD -> APPLY -> EVIDENCE -> DETECTOR -> QX? -> MINIMAL FINDING`

Allowed edges execute. Blocked edges are pruned. Missing/incomparable guard operands produce `inconclusive`, never PASS, and the branch is not expanded.

## Modeling pattern

Represent state at time `t` as:

`X(t) = [resource_balance, consumed_budget, budget_limit, per_action_limit, transaction_count, evidence_count, accepted_count, rejected_count]`

A guarded, contract-bound transition is:

`AdapterScope ⊢ X(t) --[guard(event, X(t))]--> X(t+1)`

The preferred bounded property is:

`P(reachable(QX_FORBIDDEN)) = 0`

for all adapter-authorized, guard-enabled action sequences inside the declared model/search bounds.

## Core files

- `transition_field.example.yaml` — v0.6 state model; references adapter, guard, and forbidden-state documents.
- `adapter_manifest.schema.json` — adapter manifest schema.
- `adapter_manifest.synthetic.json` — valid offline adapter contract.
- `adapter_manifest.template.json` — fail-closed real-integration scaffold.
- `adapter_contract.py` — v0.6 contract enforcement.
- `transition_guards.example.json` / `guard_engine.py` — v0.5 edge guards.
- `forbidden_state_rules.example.json` / `detect_forbidden_state.py` — v0.3 forbidden-state assertions.
- `evidence_record.schema.json` / `build_evidence_graph.py` — v0.2 evidence contract/graph.
- `synthetic_adapter.py` — offline safe and deliberately buggy adapters.
- `auto_path_to_finding.py` — v0.6 contract-bound guarded BFS engine.
- `test_matrix_template.csv` / `transition_adjacency_matrix.csv` — reusable planning artifacts.

## Contract-bound path-to-finding demo

```bash
python auto_path_to_finding.py \
  --adapter synthetic-buggy \
  --adapter-manifest adapter_manifest.synthetic.json \
  --max-depth 6 \
  --max-paths 250 \
  --out-dir path-to-finding
```

The synthetic adapter manifest and guards are enabled by default. Expected minimal path in the deliberately buggy model:

`fund -> set_policy -> concurrent_action -> CUMULATIVE_LIMIT_EXCEEDED`

The safe in-memory adapter is a negative control:

```bash
python auto_path_to_finding.py --adapter synthetic-safe
```

Compatibility switches `--no-guards` and `--no-adapter-contract` exist for regression comparison only; real target integrations should not bypass the reviewed adapter contract.

## Starting a real integration

Copy `adapter_manifest.template.json` and replace TODOs only after explicit authorization/scope review. The template intentionally cannot pass v0.6 validation as shipped because:

- `scope.authorized` is `false`;
- `supported_events` is empty;
- target and credential environment-variable names are placeholders.

A real adapter then implements only:

- `snapshot()` — observed state with `state_id` and all manifest-required `values`;
- `apply(event)` — one allow-listed modeled event returning all manifest-required request/decision/mutation/evidence fields.

The engine does not need to know whether that adapter talks to a REST API, a smart contract local fork, an agent wallet sandbox, or a workflow engine.

## Safety and evidence semantics

- explicit non-production authorization contract before execution;
- full modeled-event coverage check before search;
- manifest-enforced `max_depth`, `max_paths`, and `max_concurrency` ceilings;
- credential values excluded from manifests; environment-variable names only;
- snapshot/evidence contract validation on every adapter interaction;
- guard evaluation before adapter action execution;
- blocked/inconclusive branches are not expanded;
- fresh adapter instance per candidate path;
- no hidden load testing;
- detector and guards use constrained DSLs, not `eval()`;
- missing evidence fails closed as `inconclusive`;
- `not_found_within_bound` is bounded evidence only, never a security certification.

The bundled evidence builder, detector, guard engine, adapter contract, and synthetic adapters are offline-only.

This template is client-neutral and can be adapted to Solidity state machines, payment APIs, agent-control systems, workflow engines, and other stateful software.
