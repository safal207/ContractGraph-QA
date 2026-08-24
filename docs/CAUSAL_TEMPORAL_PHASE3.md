# Causal-Temporal Phase 3 — Proof Integrity

Phase 3 verifies the integrity of the verification process itself.

## Executable capabilities

```bash
python -m contractgraph_qa.proof_integrity_cli freeze --input freeze.json
python -m contractgraph_qa.proof_integrity_cli plan --input plan.json
python -m contractgraph_qa.proof_integrity_cli trace --input trace.json
python -m contractgraph_qa.proof_integrity_cli readiness --input evidence.json
python -m contractgraph_qa.proof_integrity_cli root-cause --input findings.json
python -m contractgraph_qa.proof_integrity_cli metamorphic --input roundtrip.json
python -m contractgraph_qa.proof_integrity_cli durable-build --root evidence --path finding.json --path trace.json
python -m contractgraph_qa.proof_integrity_cli durable-verify --root evidence --manifest manifest.json
```

## Exact-Subject Freeze

Evidence is attributed only while the exact subject remains unchanged across collection:

```text
subject_before != subject_after
=> STALE_SUBJECT
```

Same branch, PR number, artifact label, or filename is weaker than exact content/version identity.

## Preregistered Verification Plan

The verification plan is hashed before final outcomes are interpreted. Amendments are explicit, append-only, hash-chained records with reasons. Silent bound, subject, or capability changes fail closed.

```text
CommitBeforeObserve
```

Preregistration exposes post-hoc changes; it does not guarantee good hypotheses.

## Trace Integrity

The trace checker rejects duplicate IDs/sequences, out-of-order records, unmarked gaps, broken predecessor links, foreign-subject events, and partial traces without explicit gap semantics.

```text
missing != absent
unknown != false
partial trace != complete trace
```

## Evidence Type and Readiness

Evidence classes remain explicit:

```text
WITNESSED
REPORTED
REFLECTED
DERIVED
MODEL_OUTPUT
NON_DETECTION
COUNTEREVIDENCE
```

A `WITNESSED` claim requires a direct-observation source. Required freshness, replayability, independence, and counterevidence coverage are structural readiness properties, not truth probabilities.

```text
HighEvidenceReadiness != Truth
REFLECTION_ONLY != WitnessedExecution
```

## Root-Cause Collapse

Declared `CAUSES` edges group downstream symptoms under the first causal roots without merging independent roots.

```text
many red symptoms != many independent root defects
```

The result is graph-relative; it is not universal causality proof.

## Metamorphic / Round-Trip Verification

Round-trip cases compare declared state, effect, history, and exact-subject preservation across transformations such as persist/reopen, serialize/rehydrate, or checkpoint/restore.

## Durable Reopen

Durable evidence verification uses actual persisted bytes:

```text
write
→ build SHA-256/size manifest
→ reopen from filesystem
→ recompute bytes
→ reject missing/tampered artifacts
```

```text
InMemoryVerified != DurableEvidenceVerified
```

A valid local durable manifest still does not prove external authenticity without an independent anchor.
