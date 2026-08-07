# ContractGraph-QA

**Causal-temporal state-transition testing for smart contracts.**

ContractGraph-QA treats a smart contract as a reachable state space rather than a collection of isolated functions.

The core question is:

> Can an allowed sequence of actors, transactions, parameter values, and time changes drive the contract into a state that violates a business or security invariant?

## Mental model

```text
CAUSE
  ↓
ACTOR
  ↓
ACTION / TRANSACTION
  ↓
PARAMETER / TIME INPUT
  ↓
PRE-STATE
  ↓
STATE TRANSITION
  ↓
POST-STATE
  ↓
STATE HASH
  ↓
EFFECT
  ↓
FUTURE REACHABLE STATES
```

A finding should be reproducible as:

```text
Finding → Cause → Path → Evidence → Replay → Fix → Retest
```

## v0.8: adapter manifest and automatic finding export

v0.8 separates reviewed client metadata from machine-discovered path evidence.

```text
adapter manifest
      +
explorer result
      ↓
provenance + depth validation
      ↓
automatic finding JSON
      ↓
deterministic Markdown report
```

The exporter binds an explorer result to the exact `adapterId` and `scopeId`, rejects paths deeper than the declared search depth, resolves only action and invariant IDs present in the manifest, and fails closed on parameter-template mismatches.

The checked-in `CGQA-005` example is verified byte-for-byte in CI from manifest → finding JSON → Markdown.

See [`docs/ADAPTER_MANIFEST.md`](docs/ADAPTER_MANIFEST.md).

## v0.7: fork adapter template

v0.7 connects the authorized fixed-block fork context to the existing parameter/time explorer, state deduplication, invariant checks, deterministic replay, and report pipeline.

A contract-specific adapter supplies five explicit pieces:

```text
deterministic fork reset
        ↓
action / parameter corpus
        ↓
step execution
        ↓
protocol invariant
        ↓
complete protocol state hash
```

The protocol state digest is bound to the authorization `scopeHash`, chain ID, fixed block, target address, and target code hash before deduplication. The local default-CI regression proves that equivalent states are pruned while the shortest violating path remains replayable.

A copyable skeleton lives at `fork-test/AuthorizedAdapterTemplate.t.sol.example`; it is not executable until every `TODO` is replaced for a real explicitly authorized engagement.

See [`docs/FORK_ADAPTER_TEMPLATE.md`](docs/FORK_ADAPTER_TEMPLATE.md) and the deterministic example finding [`CGQA-004`](reports/examples/CGQA-004.md).

## v0.6: authorized fork context

v0.6 adds a separate, fail-closed path for fixed-block EVM fork testing.

The default CI never opens an external fork. A fork run requires explicit scope metadata, an authorization reference, an exact chain/block/target, confirmation equal to `YES`, and a secret RPC endpoint. GitHub execution is manual through the `Authorized fork smoke` workflow and the `authorized-fork` environment.

The first fork smoke is intentionally read-only:

```text
authorization preflight
  ↓
fixed block fork
  ↓
chain + block verification
  ↓
target code existence
  ↓
read-only snapshot fingerprint
```

It does not broadcast a transaction or call a target function. A public address alone is not treated as authorization.

See [`docs/FORK_TESTING.md`](docs/FORK_TESTING.md).

## v0.5: state hashing and deduplication

v0.5 adds a breadth-first search mode that keeps one shortest representative path per unique modeled state hash.

Equivalent states reached by cycles, no-op actions, or convergent paths are pruned instead of being expanded repeatedly.

The local regression fixture has three actions:

```text
noopA
noopB
advance
```

At depth 8, exhaustive candidate enumeration would contain 9,840 paths. The deduplicating explorer executes only 12 child transitions when no violation is enforced and discovers four unique states before the frontier is exhausted.

With the terminal invariant enabled, it still finds the minimal violating path:

```text
advance → advance → advance
```

The state hash is part of the QA model: it must include every modeled value that can change future reachability. An incomplete hash can make pruning unsound.

The engine caps actual work at 4,096 retained unique states and 65,536 attempted child transitions rather than rejecting a search from its theoretical `branching^depth` size.

See [`docs/STATE_DEDUP.md`](docs/STATE_DEDUP.md).

## v0.4: parameter and time exploration

v0.4 extends bounded breadth-first search from action order to a finite corpus of parameterized steps.

A step is modeled as `(action, parameter)`, where the parameter may represent a business value or a time delta.

The local demonstration corpus contains:

```text
fund(1)
fund(100)
fund(101)
wait(1 day)
wait(7 days)
refund()
```

It demonstrates two classes of finding against a deliberately vulnerable local fixture:

```text
fund(101) → deposit-cap invariant violated
```

and:

```text
fund(1) → wait(1 day) → refund() → refund-timing invariant violated
```

Every candidate starts from a fresh target and a reset baseline timestamp, preserving deterministic replay.

See [`docs/PARAMETER_TIME_EXPLORER.md`](docs/PARAMETER_TIME_EXPLORER.md).

## v0.3: deterministic finding reports

v0.3 turns machine-readable evidence into a deterministic client-facing Markdown finding.

The reporting layer validates the evidence contract before rendering and requires a reproducible failing path, invariant, replay command, impact, recommendation, and explicit authorization/scope statement.

See [`docs/REPORTING.md`](docs/REPORTING.md) and the checked-in examples under [`reports/examples/`](reports/examples/).

## v0.2: automatic Path Explorer

v0.2 adds bounded breadth-first exploration of action sequences.

A concrete smart-contract test model defines:

- the available action alphabet;
- how to reset the target to a deterministic initial state;
- how each action is executed;
- which invariant must hold after every accepted transition.

The explorer enumerates shortest paths first and stops on the first invariant violation. Within the modeled action space, that gives a minimal failing path by action count.

For the deliberately vulnerable escrow fixture, the explorer automatically discovers:

```text
fund → release → refund → payout invariant violated
```

and then deterministically replays the same path against a fresh contract instance.

See [`docs/PATH_EXPLORER.md`](docs/PATH_EXPLORER.md).

## v0.1 foundation

- Foundry-compatible Solidity tests with no external test dependency.
- Causal transition recorder for actor/action/pre-state/post-state/time evidence.
- Temporal scenarios using block timestamp changes.
- Business/security invariant checks.
- A safe escrow example.
- Deliberately vulnerable local fixtures used only to prove invariant detection.
- Machine-readable graph schema and scenario description.
- GitHub Actions CI and Slither static analysis.

## Repository layout

```text
src/
  examples/
    Escrow.sol
    VulnerableEscrow.sol
    VulnerableTimedEscrow.sol
    ConvergentStateMachine.sol
    AdapterFixtureMachine.sol
  harness/
    CausalGraphHarness.sol
    PathExplorerHarness.sol
    ParameterizedPathExplorerHarness.sol
    StateDedupPathExplorerHarness.sol
    ForkAuthorization.sol
    ForkContextHarness.sol
    ForkAdapterTemplate.sol

test/
  EscrowGraph.t.sol
  VulnerableEscrowGraph.t.sol
  PathExplorer.t.sol
  ParameterizedTemporalExplorer.t.sol
  StateDedupPathExplorer.t.sol
  ForkAuthorization.t.sol
  ForkAdapterTemplate.t.sol

fork-test/
  AuthorizedForkSmoke.t.sol
  AuthorizedAdapterTemplate.t.sol.example

fork/
  scope.example.json

graph/schema/
  contract-graph.schema.json
  adapter-manifest.schema.json
  explorer-result.schema.json

manifests/examples/
  adapter-fixture.json

results/examples/
  CGQA-005.result.json

scenarios/
  escrow.yaml

reports/examples/
  CGQA-001.finding.json
  CGQA-001.md
  CGQA-002.finding.json
  CGQA-002.md
  CGQA-003.finding.json
  CGQA-003.md
  CGQA-004.finding.json
  CGQA-004.md
  CGQA-005.finding.json
  CGQA-005.md

tools/
  render_finding.py
  export_finding.py
  validate_fork_scope.py

docs/
  CAUSAL_MODEL.md
  INVARIANTS.md
  PATH_EXPLORER.md
  REPORTING.md
  PARAMETER_TIME_EXPLORER.md
  STATE_DEDUP.md
  FORK_TESTING.md
  FORK_ADAPTER_TEMPLATE.md
  ADAPTER_MANIFEST.md

.github/workflows/
  ci.yml
  reporting.yml
  authorized-fork.yml
```

## Example invariant

For an escrow:

```text
releasedAmount + refundedAmount <= depositedAmount
```

A valid state path might be:

```text
CREATED → FUNDED → RELEASED
```

or:

```text
CREATED → FUNDED → time passes → REFUNDED
```

but never:

```text
CREATED → FUNDED → RELEASED → REFUNDED
```

## Run locally

Install Foundry, then:

```bash
forge test -vvv
forge build
```

Export the v0.8 example finding:

```bash
python tools/export_finding.py manifests/examples/adapter-fixture.json results/examples/CGQA-005.result.json --output /tmp/CGQA-005.finding.json
```

Render a client finding:

```bash
python tools/render_finding.py /tmp/CGQA-005.finding.json --output /tmp/CGQA-005.md
```

Optional static analysis:

```bash
slither .
```

Authorized fork execution is intentionally separate; see [`docs/FORK_TESTING.md`](docs/FORK_TESTING.md).

## What the project proves today

The project does **not** claim that bounded graph exploration proves an arbitrary contract secure.

v0.1 established the causal-temporal evidence model. v0.2 added automatic bounded action-sequence search and deterministic replay. v0.3 added deterministic evidence-to-report rendering. v0.4 added finite corpus-based parameter and time exploration. v0.5 added state hashing and equivalent-state pruning. v0.6 added an authorization-gated, fixed-block fork context. v0.7 added a reviewable contract-specific adapter template. v0.8 adds a strict adapter manifest/result contract and deterministic automatic export into the client finding/report pipeline.

Security conclusions remain limited to the modeled actors, actions, parameter corpus, search depth, time assumptions, state-hash completeness, fork scope, snapshot block, adapter mapping, manifest correctness, and explicit invariants.

Planned follow-up work includes direct Foundry path capture into explorer-result JSON, generated parameter corpora, multi-contract graphs, and richer invariant libraries.

## Safety

Use this project only on contracts you own, open-source local test targets, systems where you have explicit authorization, or public bug-bounty assets strictly within their published scope and rules.

## License

Apache-2.0
