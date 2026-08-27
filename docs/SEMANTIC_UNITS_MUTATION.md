# Semantic Units Mutation v0.1

`cgqa-semantic-units-mutate` creates source-bound decimal counterfactuals only after two independent inputs agree:

1. a reviewed unit binding declares the semantic fact, for example `ASSET_DECIMALS` represents a 6-decimal asset;
2. Foundry compiler AST confirms that the exact symbol is a unique constant integer declaration initialized by the reviewed numeric literal.

```text
reviewed unit semantics
        +
Foundry compiler AST
        ↓
exact source span
        ↓
decimal counterfactual
        ↓
Mutation Acquisition
        ↓
CGQ-SPEC-001
```

The engine does **not** infer token units from variable names, comments, symbols, or nearby arithmetic. A review/AST mismatch is `INCONCLUSIVE` rather than guessed.

## Example

```bash
cgqa-semantic-units-mutate \
  --config scenarios/decimal-scaler-semantic-units.json \
  --project-root . \
  --output-dir semantic-units-evidence \
  --execute
```

The repository fixture reviews:

- `ASSET_DECIMALS = 6` and challenges it with `18`;
- `PRICE_DECIMALS = 8` and challenges it with `18`.

The generated mutants are ordinary `solidity-mutation-plan-v0.1` inputs, so existing Foundry mutation execution and `CGQ-SPEC-001` semantics are reused without inventing a second verdict system.

## Claim boundary

A generation `PASS` means only that each reviewed unit binding was confirmed by compiler AST and produced the declared source-bound decimal counterfactual. It does not prove that the unit model is complete, that the mutant compiles, that the specification detects it, or that the contract is secure.

`--execute` adds the stronger evidence legs: the mutant must compile, the bound Foundry selector must execute, and `CGQ-SPEC-001` determines whether the reviewed property detected every generated decimal counterfactual.

## Deferred operators

v0.1 does not yet mutate arbitrary scaling expressions, base/quote orientation, fee-on-transfer semantics, or version/replay logic. Those require additional reviewed semantic bindings rather than name-based heuristics.
