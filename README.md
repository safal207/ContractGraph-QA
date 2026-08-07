# ContractGraph-QA

**Causal-temporal state-transition testing for smart contracts.**

ContractGraph-QA treats a smart contract as a reachable state space rather than a collection of isolated functions.

The core question is:

> Can an allowed sequence of actors, transactions and time changes drive the contract into a state that violates a business or security invariant?

## Mental model

```text
CAUSE
  ↓
ACTOR
  ↓
ACTION / TRANSACTION
  ↓
PRE-STATE
  ↓
STATE TRANSITION
  ↓
POST-STATE
  ↓
EFFECT
  ↓
FUTURE REACHABLE STATES
```

A finding should be reproducible as:

```text
Finding → Cause → Path → Evidence → Replay → Fix → Retest
```

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
- A deliberately vulnerable toy escrow used only to prove invariant detection.
- Machine-readable graph schema and scenario description.
- GitHub Actions CI and Slither static analysis.

## Repository layout

```text
src/
  examples/
    Escrow.sol
    VulnerableEscrow.sol
  harness/
    CausalGraphHarness.sol
    PathExplorerHarness.sol

test/
  EscrowGraph.t.sol
  VulnerableEscrowGraph.t.sol
  PathExplorer.t.sol

graph/schema/
  contract-graph.schema.json

scenarios/
  escrow.yaml

docs/
  CAUSAL_MODEL.md
  INVARIANTS.md
  PATH_EXPLORER.md

.github/workflows/
  ci.yml
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

Optional static analysis:

```bash
slither .
```

## What the project proves today

The project does **not** claim that bounded graph exploration proves an arbitrary contract secure.

v0.1 established the causal-temporal evidence model. v0.2 adds automatic bounded action-sequence search and deterministic replay. Security conclusions remain limited to the modeled actors, actions, parameters, depth, time assumptions and explicit invariants.

Planned follow-up work includes parameter fuzzing, temporal actions inside the explorer, state hashing and deduplication, fork testing, multi-contract graphs, failing-path export and generated audit reports.

## Safety

Use this project only on contracts you own, open-source test targets, or systems where you have explicit authorization to test.

## License

Apache-2.0
