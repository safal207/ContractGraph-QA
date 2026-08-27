# Fault-Model Mutation Generator v0.1

`cgqa-fault-mutate` converts exact Solidity source bytes plus reviewed test bindings into a deterministic Mutation Acquisition plan.

The purpose is not to guess vulnerabilities. The generator asks a different question:

> If we deliberately introduce representative faults from declared classes, do the bound verification properties notice them?

## Supported v0.1 fault classes

- `authorization` — remove `msg.sender != ...` deny guards;
- `state_transition` — remove `state != ...` guards and `state = State.X` writes;
- `time_boundary` — remove `block.timestamp` deny guards;
- `accounting` — remove writes to common economic state variables such as `*Amount`, `*Balance`, `*Shares`, `*Supply`, `*Debt`, `*Fee`, and `*Reserve`.

The following classes are intentionally unsupported in v0.1:

- `replay_version`;
- `units_decimals`.

Those require semantic/AST-aware mutation rather than unsafe line heuristics. A requested unsupported class is reported as `INCONCLUSIVE`; it is never silently treated as covered.

## Flow

```text
reviewed source SHA
  -> deterministic syntax-local candidate discovery
  -> reviewed test binding by fault class + source function
  -> exact Mutation Acquisition plan
  -> isolated mutant build
  -> exact Foundry selector
  -> detected / survived / inconclusive
  -> CGQ-SPEC-001
```

## Command

Generate only:

```bash
cgqa-fault-mutate \
  --config scenarios/escrow-auto-fault-generator.json \
  --project-root . \
  --output-dir fault-evidence
```

Generate and execute:

```bash
cgqa-fault-mutate \
  --config scenarios/escrow-auto-fault-generator.json \
  --project-root . \
  --output-dir fault-evidence \
  --execute
```

Generation writes:

```text
fault-evidence/
  fault-generation-result.json
  generated-mutation-plan.json
```

Execution additionally writes the Mutation Acquisition evidence tree and a combined execution result.

## Fail-closed rules

- Exact source SHA-256 must match before discovery.
- An exact source line must be unique before it can become a mutation.
- A generated mutation requires a reviewed Foundry test binding.
- Required unsupported classes remain explicit blockers.
- Required supported classes with no generated candidate remain explicit blockers.
- Mutation generation PASS does **not** mean the property detected the mutant.
- Compile-invalid mutants remain `INCONCLUSIVE` downstream.
- Only Mutation Acquisition plus `CGQ-SPEC-001` establishes whether the bound property killed the generated faults.

## Claim boundary

A generation PASS means every declared required fault class is supported by the v0.1 generator and has at least one executable generated mutation under the supplied source and reviewed test bindings.

It does not prove mutation exhaustiveness, fault-model completeness, smart-contract security, or specification strength. Those are separate evidence claims.
