# Specification Assurance v0.1

ContractGraph-QA can verify a contract against an invariant, but a passing verifier is only as useful as the property it was asked to check.

`CGQ-SPEC-001 — PROPERTY_DETECTS_REVIEWED_FAULT_MODEL` adds a separate assurance question:

> Is this reviewed property demonstrably active on a passing baseline, and does it detect every required mutation in the reviewed fault model?

## Why this is separate

A contract verifier and a specification verifier answer different questions.

```text
contract + property
      ↓
contract verification
      ↓
PASS
```

does not establish that the property is meaningful, non-vacuous, complete, or sensitive to relevant defects.

Specification assurance therefore challenges the property itself:

```text
PASSING BASELINE
      ↓
ACTIVATION WITNESS
      ↓
REVIEWED FAULT MODEL
      ↓
MUTATION OUTCOMES
      ↓
CGQ-SPEC-001
```

## Verdicts

### `pass / assured_over_reviewed_fault_model`

Requires all of the following:

- the baseline assessment is `pass`;
- an activation witness was observed;
- every required fault class is represented by at least one supplied mutation;
- every mutation belonging to a required fault class is `detected`.

### `fail / weak_specification`

At least one mutation in a required fault class survived the property.

This is concrete evidence that the supplied property does not detect the full reviewed challenge set.

### `inconclusive`

Examples:

- baseline evidence is not a PASS;
- activation was not observed, so vacuity is not excluded;
- a required fault class has no supplied mutation;
- a required mutation outcome is inconclusive.

Missing proof is not converted into failure or success.

## Mutation score

The result reports a mutation score for required mutations:

```text
detected required mutations / all required mutations
```

The score is descriptive only. v0.1 has no arbitrary threshold such as 80% or 90%.

A required surviving mutation causes FAIL regardless of the numeric score.

## Evidence boundary

v0.1 does **not** generate source mutations and does not infer mutation outcomes.

Each baseline, activation witness, and mutation outcome is an evidence input with a SHA-256 binding. This allows results produced by Foundry, Echidna, Medusa, Halmos, Kontrol, Certora, or another reviewed harness to be normalized without pretending that ContractGraph-QA executed those engines itself.

PASS therefore means only:

> The supplied property was active on the supplied passing baseline and detected every supplied mutation in every represented required fault class.

It does not prove:

- exhaustive mutation generation;
- completeness of the fault taxonomy;
- global correctness of the property;
- security of the target contract.

## Repository benchmark

Run the repository-owned race-property challenge:

```bash
cgqa-spec-assurance --model scenarios/spec-assurance-race-property.json
```

The fixture challenges `CGQ-RACE-001` with three reviewed fault classes:

- joint enablement overlap;
- ordering outcome divergence;
- protective-right defeat.

All three mutations are detected, so the fixture returns `assured_over_reviewed_fault_model`.

## Intended evolution

v0.1 is the evidence-normalization layer. Future adapters can acquire mutation evidence automatically from source mutation engines and external verification tools while preserving the same fail-closed verdict semantics.
