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

## v0.1 scope

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

test/
  EscrowGraph.t.sol
  VulnerableEscrowGraph.t.sol

graph/schema/
  contract-graph.schema.json

scenarios/
  escrow.yaml

docs/
  CAUSAL_MODEL.md
  INVARIANTS.md

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

## What v0.1 proves

The project does **not** claim that graph exploration alone proves a contract secure. v0.1 establishes the testing model and evidence format: transitions are observed, paths are replayable, and explicit invariants decide whether the resulting state is acceptable.

Future versions can add state-space exploration, fuzzed action sequences, automatic invariant synthesis, fork testing, multi-contract graphs and report generation.

## Safety

Use this project only on contracts you own, open-source test targets, or systems where you have explicit authorization to test.

## License

Apache-2.0
