# Solidity → Contract Lattice

ContractGraph-QA can derive a reviewed lifecycle graph from Solidity compiler AST evidence and project the result into a Contract Lattice template.

```text
Solidity source
  → forge build --ast --build-info
  → source-unit compiler AST
  → supported state guards + state writes
  + reviewed economic profile
  → lifecycle liveness verification
  → Contract Lattice template
```

## Command

```bash
cgqa solidity-lattice-check \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/solidity-lattice-disputed-dead-end-profile.json \
  --root .
```

The deliberately vulnerable fixture contains:

```text
Created → Funded → Released
               ├→ Refunded
               └→ Disputed → ∅
```

`Funded` and `Disputed` are declared value-holding states. `Released` and `Refunded` are declared safe economic terminals. The expected result is `FAIL` with a `CGQ-LIVE-001` counterexample reaching `Disputed`.

## Supported v0.1 structural shapes

The extractor recognizes direct enum-state writes such as:

```solidity
state = State.Disputed;
agreement.state = State.Disputed;
```

when a supported entry-state guard is present before the write, including:

```solidity
require(state == State.Funded, "invalid state");
if (state != State.Funded) revert InvalidState();
if (state != State.Funded) revert("invalid state");
```

The builtin `revert("...")` form is intentionally covered because it exposed the integration gap in the earlier extractor attempt.

Unsupported or ambiguous state writers produce `INCONCLUSIVE`, not `PASS`.

## Static lattice template

Static source code does not establish runtime balances, transaction order, concrete state versions, caller authority or time observations. The emitted lattice therefore uses explicit non-claims:

- `valuePresence` is a reviewed boolean classification, not an amount;
- each transition declares relative `versionDelta = 1` only;
- authority is `not_inferred_from_static_ast`;
- time witness is `not_inferred_from_static_ast`;
- per-transition AST node/function evidence is retained.

Concrete runtime coordinates are supplied by normalized execution evidence and remain checked by the existing economic-cardinality and successor-consistency engines.

## Claim boundary

A lifecycle `PASS` means every reachable state classified as holding value has a path to a declared safe terminal **within the completely extracted finite graph**. Model completeness with respect to unsupported Solidity control flow remains a separate claim; unresolved writers force `INCONCLUSIVE`.
