# Solidity → ContractGraph Lifecycle Extraction

ContractGraph-QA can derive lifecycle transitions from Solidity compiler AST evidence and feed the extracted graph directly into the deterministic lifecycle-liveness verifier.

The design deliberately separates two evidence classes:

1. **structural facts from compiler AST** — enum states, guarded source states, and writes to the configured state selector;
2. **reviewed economic semantics from a profile** — initial state, states that hold locked value, safe economic terminals, and the invariant ID.

The extractor does **not** guess that a state holds money merely because its name looks like `Funded`, and it does not infer safe termination from naming conventions.

## One-command check with Foundry

```bash
cgqa solidity-lifecycle-check \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/disputed-dead-end-extractor-profile.json \
  --root .
```

Internally this runs:

```bash
forge inspect <target> ast
```

and then performs:

```text
Solidity source
   ↓ compiler
Solidity AST
   ↓ structural extractor
Lifecycle graph
   + reviewed economic profile
   ↓
Lifecycle-liveness verifier
   ↓
PASS | FAIL | INCONCLUSIVE
```

You can also supply a previously captured AST:

```bash
forge inspect src/examples/Escrow.sol:Escrow ast > escrow-ast.json
cgqa solidity-lifecycle-check \
  --ast escrow-ast.json \
  --profile profile.json
```

## Supported v0.1 transition shapes

The extractor recognizes state writes of the form represented in compiler AST as:

```solidity
state = State.Funded;
agreement.state = State.Disputed;
```

The configured `selectorKind` determines whether the state selector is expected as:

- `identifier` — a direct state variable such as `state`;
- `member` — a struct/member access such as `agreement.state`;
- `either` — either representation.

Entry-state guards are currently extracted from supported top-level shapes such as:

```solidity
require(state == State.Funded, "invalid state");
require(state == State.Funded || state == State.Delivered, "invalid state");
if (state != State.Funded) revert InvalidState();
```

## Fail-closed extraction

If a function writes the configured state selector but the extractor cannot prove an unambiguous entry-state guard, it does **not** silently invent an edge.

Instead:

```json
{
  "status": "inconclusive",
  "reason": "incomplete_state_transition_extraction"
}
```

The unresolved writer is preserved in `extraction.unresolvedStateWriters`.

This is important because an invented transition could create a fake recovery path and incorrectly turn a real lifecycle defect into a PASS.

## Profile contract

Example:

```json
{
  "contractName": "DisputedDeadEndEscrow",
  "enumName": "State",
  "stateSelector": "state",
  "selectorKind": "identifier",
  "initialState": "Created",
  "valueHoldingStates": ["Funded", "Disputed"],
  "safeTerminalStates": ["Released", "Refunded"],
  "invariantId": "CGQ-LIVE-001"
}
```

Schema: [`graph/schema/solidity-lifecycle-profile.schema.json`](../graph/schema/solidity-lifecycle-profile.schema.json).

All profile states must exist in the extracted enum. A safe terminal may not simultaneously be declared as holding locked value.

## Evidence output

The combined check returns:

- canonical AST SHA-256;
- canonical profile SHA-256;
- extracted enum states;
- each extracted transition with function and AST node ID;
- unresolved state writers;
- the exact generated lifecycle model;
- the deterministic lifecycle-verification result.

For the disputed dead-end fixture, the important extracted path is:

```text
Created → Funded → Disputed → DEAD_END
```

with `Disputed` declared as value-holding and no path to `Released` or `Refunded`.

## Claim boundary

A PASS proves the liveness property over the **successfully extracted and reviewed model**. It does not prove that every possible Solidity control-flow shape is supported by the v0.1 extractor.

Unsupported state writers force `INCONCLUSIVE` rather than PASS. Modifier-derived guards, complex branch-sensitive assignments, assembly, cross-contract state machines, and dynamically reconstructed state semantics remain future extractor work.

The intended product direction is:

```text
contract → compiler facts → reviewed semantics → graph → invariants → counterexample → evidence
```
