# Solidity Lifecycle Extraction

ContractGraph-QA can derive a reviewed lifecycle-liveness model from Solidity compiler AST evidence.

```text
Solidity source
  → forge build --ast --build-info
  → compiler output.sources[source].ast
  → structural transition extraction
  + reviewed economic profile
  → lifecycle-liveness verification
  → PASS | FAIL | INCONCLUSIVE
```

## CLI

```bash
cgqa solidity-lifecycle-check \
  --target src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow \
  --profile scenarios/disputed-dead-end-extractor-profile.json \
  --root .
```

A previously captured source-unit AST can be checked instead:

```bash
cgqa solidity-lifecycle-check \
  --ast captured-source-unit-ast.json \
  --profile reviewed-profile.json
```

## Why compiler build-info

Foundry 1.7 does not expose `ast` as a `forge inspect` field. The extractor therefore invokes `forge build --ast --build-info` and reads the Solidity standard compiler output under:

```text
out/build-info/*.json
  → output.sources[<source>].ast
```

The actual Foundry `out` directory is resolved through `forge config --json` rather than assumed.

If multiple build-info files contain the requested source, ContractGraph-QA accepts them only when the canonical AST hashes are identical. Divergent AST candidates fail closed instead of selecting one silently.

## Evidence separation

The compiler AST establishes structural facts only:

- enum members;
- supported entry-state guards;
- supported writes to the lifecycle state selector;
- source and target states for extracted transitions.

A strict reviewed profile supplies economic meaning:

- contract and enum identity;
- lifecycle state selector;
- initial state;
- states that hold locked economic value;
- safe economic terminal states;
- invariant ID.

The extractor does not infer that a state named `Funded` necessarily contains funds or that a state named `Released` is economically safe.

## Supported v0.1 shapes

Representative supported guards and writes include:

```solidity
require(state == State.Funded, "invalid state");
require(state == State.Funded || state == State.Delivered, "invalid state");
if (state != State.Funded) revert InvalidState();
state = State.Disputed;
agreement.state = State.Disputed;
```

`stateSelector` supports `identifier`, `member`, and `either` selector kinds.

## Fail-closed extraction

A state-writing function is not treated as safely modeled merely because its target state is recognizable.

If ContractGraph-QA cannot establish an unambiguous supported entry-state guard before the write, the extraction records an unresolved state writer and the combined result becomes:

```text
INCONCLUSIVE
```

rather than PASS.

Examples intentionally outside v0.1 include modifier-derived guards, assembly, complex branch-sensitive writes, and cross-contract lifecycle reconstruction.

## Executable dead-end case

The repository fixture `DisputedDeadEndEscrow.sol` contains:

```text
Created → Funded → Released
                 → Refunded
                 → Disputed → ∅
```

The reviewed profile marks `Funded` and `Disputed` as value-holding and `Released` / `Refunded` as safe terminals. The extracted model therefore fails `CGQ-LIVE-001` with `Disputed` as a reachable value-holding dead end.

The normal repository `Escrow.sol` is also exercised as a negative-control fixture and must PASS the same liveness theorem.

## Claim boundary

A PASS proves lifecycle liveness only over the transitions successfully extracted from the compiler AST plus the reviewed economic profile. It does not claim source-to-model completeness for unsupported Solidity constructs.

This is the intended product boundary:

> automate what can be proved; make uncertainty explicit where it cannot.
