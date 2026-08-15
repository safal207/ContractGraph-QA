# GLOBAL P2-4 — Maintenance Routine Contract and Routine Evaluator

Status: **reference/conformance contract**. This document does not claim merge,
deployment, production persistence, external effects, or routine autonomy in
production.

## Purpose

P2-4 makes the Maintenance Mesh operationally testable without introducing a
second authority. Two bounded routines emit the same closed run shape:

```text
routine identity
  -> exact target/source subject
  -> observation and causal case
  -> minimal patch intent
  -> independent verification and negative cases
  -> exact draft outcome
  -> routine-quality receipt
```

The evaluator answers only whether the declared routine runs are complete,
replay-stable, independently verified, outcome-attributed and authority-safe.
It does not answer whether a repository is globally healthy or whether a patch
should be merged.

## Bounded fixture

The fixture contains two routines:

- `contract_drift_detector` — targets the exact ProofPath authorization schema;
- `evidence_auditor` — targets the frozen RESONANCE interoperability fixture.

Every run binds routine ID/version/rule digest, target repository and subject,
finding and scope digests, causal case, patch digest, verification evidence,
negative cases, draft PR outcome and a canonical routine-run digest.

The evaluator independently checks that:

- target subjects equal the pinned external checkouts;
- run digests reproduce from canonical bytes;
- routine, finding and patch identities are unique;
- verification is `PASS` and replay is `SAME_RESULT`;
- outcome routine/patch identities match the run;
- authority, merge, deployment, external-effect and side-effect flags are false.

## Quality receipt

The receipt is `cgqa.maintenance-routine-evaluation.v0.1`. Its metrics are
bounded counts for evidence completeness, independent verification,
outcome attribution, authority-boundary checks and replay stability. The
policy is `QUALITY_ONLY_NO_MERGE_AUTHORITY`.

The workflow runs the evaluator twice and compares the emitted bytes. The
artifact contains the evaluation receipt, exact subject records, run context
and a SHA-256 manifest.

## Negative surface

The unit and workflow suites reject:

- stale target head;
- missing or unlisted evidence;
- changed contract subject;
- duplicate finding identity;
- false-green replay result;
- outcome attributed to the wrong routine or patch;
- routine self-authorization;
- exact revision or worktree subject tamper.

These cases stay fail-closed. A green evaluator result is evidence about the
routine contract only; it cannot authorize merge, deployment, production
persistence or an external effect.
