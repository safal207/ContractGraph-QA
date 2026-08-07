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
  harness/
    CausalGraphHarness.sol
    PathExplorerHarness.sol
    ParameterizedPathExplorerHarness.sol
    StateDedupPathExplorerHarness.sol

test/
  EscrowGraph.t.sol
  VulnerableEscrowGraph.t.sol
  PathExplorer.t.sol
  ParameterizedTemporalExplorer.t.sol
  StateDedupPathExplorer.t.sol

graph/schema/
  contract-graph.schema.json

scenarios/
  escrow.yaml

reports/examples/
  CGQA-001.finding.json
  CGQA-001.md
  CGQA-002.finding.json
  CGQA-002.md
  CGQA-003.finding.json
  CGQA-003.md

tools/
  render_finding.py

docs/
  CAUSAL_MODEL.md
  INVARIANTS.md
  PATH_EXPLORER.md
  REPORTING.md
  PARAMETER_TIME_EXPLORER.md
  STATE_DEDUP.md

.github/workflows/
  ci.yml
  reporting.yml
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

Render an example client finding:

```bash
python tools/render_finding.py reports/examples/CGQA-001.finding.json --output /tmp/CGQA-001.md
```

Optional static analysis:

```bash
slither .
```

## What the project proves today

The project does **not** claim that bounded graph exploration proves an arbitrary contract secure.

v0.1 established the causal-temporal evidence model. v0.2 added automatic bounded action-sequence search and deterministic replay. v0.3 added deterministic evidence-to-report rendering. v0.4 added finite corpus-based parameter and time exploration. v0.5 adds state hashing and equivalent-state pruning while preserving shortest representative paths under the explicit state-hash model.

Security conclusions remain limited to the modeled actors, actions, parameter corpus, search depth, time assumptions, state-hash completeness, and explicit invariants.

Planned follow-up work includes fork testing, generated parameter corpora, multi-contract graphs, direct failing-path export into the report schema, and richer invariant libraries.

## Safety

Use this project only on contracts you own, open-source local test targets, systems where you have explicit authorization, or public bug-bounty assets strictly within their published scope and rules.

## License

Apache-2.0
