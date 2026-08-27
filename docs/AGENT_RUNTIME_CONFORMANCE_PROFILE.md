# Agent Runtime Conformance Profile v0.1

The **Agent Runtime Conformance Profile v0.1** is a portable, machine-readable way to publish one source-pinned runtime boundary result without collapsing distinct guarantees into a single score.

It complements the repository-wide `Agent Runtime Conformance Matrix v0.1` by giving external runtimes a self-contained submission format.

## Validate a profile

```bash
cgqa runtime-conformance-profile \
  --input examples/openai-agents-runtime-conformance-profile-v0.1.json
```

A valid profile emits JSON containing separate claims:

```json
{
  "profileValid": true,
  "projectionConformant": true,
  "projection": {"status": "pass", "passed": 8, "total": 8},
  "axes": {
    "replay": "pass",
    "explicitAbsence": "pass",
    "deadlineBinding": "pass",
    "persistence": "pass",
    "appendOnly": "fail",
    "destructiveMutations": "present"
  }
}
```

`profileValid=true` means only that the document matches the v0.1 contract and is internally consistent. It is deliberately **not** an overall safety verdict.

`projectionConformant=true` means all eight `Witness Projection Conformance v0.1` checks passed at the declared boundary.

## Portable JSON Schema

The schema ships with the Python package:

```text
contractgraph_qa/schemas/agent-runtime-conformance-profile-v0.1.schema.json
```

It uses JSON Schema Draft 2020-12. ContractGraph-QA also applies its own dependency-free Python validator so the CLI does not require an external JSON Schema package.

## Required source pin

Every profile must identify an exact upstream source:

```json
{
  "source": {
    "repository": "owner/repository",
    "commit": "40-character-lowercase-git-sha"
  }
}
```

Branch names such as `main`, floating tags, or shortened SHAs are rejected. The profile is a claim about one measured source boundary, not an evergreen framework label.

## Seven axes

The profile records:

1. `projection` — the eight-check Witness Projection score;
2. `replay` — whether the recorded witness sequence replays consistently;
3. `explicitAbsence` — whether an absence observation can be represented explicitly;
4. `deadlineBinding` — whether time-dependent transitions are bound to recorded evidence;
5. `persistence` — whether the measured boundary preserves the required evidence through save/restore;
6. `appendOnly` — whether evidence immutability is native, fails, requires adapter policy, or was not measured;
7. `destructiveMutations` — observed history-removal operations at the measured boundary.

Capability status vocabulary:

```text
pass
fail
adapter_required
not_measured
```

Mutation-surface vocabulary:

```text
present
absent
not_measured
```

## Guardrails

The profile validator fails closed on inconsistent claims. In particular:

- `projection.status=pass` requires `8/8`;
- an `8/8` projection requires replay, explicit-absence, and deadline-binding axes to be `pass`;
- known destructive mutation operations require `appendOnly=fail`;
- destructive operations must be named when their status is `present`;
- at least one evidence reference is required;
- unknown top-level fields are rejected in v0.1.

## Evidence references

`evidenceRefs` are pointers to the artifacts that support the profile, for example benchmark JSON, test documentation, CI artifacts, or source-pinned reports.

The v0.1 validator checks that these references are present and non-empty. It does **not** fetch them or prove their authenticity/completeness. Cryptographic evidence binding is a separate future layer.

## Canonical example

```text
examples/openai-agents-runtime-conformance-profile-v0.1.json
```

This example intentionally demonstrates why projection and storage must stay separate: the hosted OpenAI Agents SDK projection is `8/8`, while the measured native Session mutation surface contains `pop_item()` and `clear_session()`, so append-only evidence is `fail` at that boundary.

## Core rule

> A valid conformance profile states exactly what was measured, where it was measured, and what remains unproven.

That is the purpose of v0.1: portable claims without upgrading a narrow benchmark into a framework-wide security assertion.
