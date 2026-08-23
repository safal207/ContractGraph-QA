# Causal Repair Verification v0.1

`CGQ-CAUSAL-001 — REPAIR_REMOVES_TARGET_WITHOUT_REGRESSION` compares two reviewed assessment snapshots around one declared change.

It answers a narrow question:

> Did the candidate change move every declared target invariant from `FAIL` to `PASS` while every declared guard invariant remained `PASS`?

This is the first verification primitive for Fractal Causal Refactoring in ContractGraph-QA. The same before/after proof shape can be reused at function, lifecycle, contract, protocol, wallet, or product scale.

## Command

```bash
cgqa-causal-repair --model scenarios/milepact-causal-repair-dispute-cutoff.json
```

## Classification

- `verified_repair`: every target moved `FAIL -> PASS`, guards remained `PASS`, and no failures remain in the supplied candidate snapshot.
- `partial_repair`: the declared targets were repaired without guard regression, but other failures remain in the supplied candidate snapshot.
- `regression`: at least one declared guard moved `PASS -> FAIL`.
- `no_effect`: the target repair did not remove all declared target failures.
- `inconclusive`: required evidence is missing/weakened, a target was not a proven baseline failure, or a guard was not a proven baseline pass.

The machine `status` is independent of classification:

- `pass`: all declared target failures were repaired and declared guards stayed green.
- `fail`: target remains failed or a declared guard regressed.
- `inconclusive`: proof material is insufficient for that claim.

## MilePact example

The fixture models one candidate repair for MP-05: add an explicit dispute cutoff so `raiseDispute()` is no longer valid once `autoRelease()` becomes valid.

```text
BEFORE
CGQ-RACE-001  FAIL
CGQ-LIVE-001  FAIL
CGQ-SAFE-001  PASS
CGQ-CONS-001  PASS

CHANGE
explicit raiseDispute cutoff

AFTER
CGQ-RACE-001  PASS
CGQ-LIVE-001  FAIL
CGQ-SAFE-001  PASS
CGQ-CONS-001  PASS

RESULT
status          PASS
classification  PARTIAL_REPAIR
```

The result intentionally does **not** claim the contract is fixed globally: MP-05 is removed in the reviewed model, while the earlier `Disputed` liveness failure remains.

## Claim boundary

v0.1 does not infer source-level causality, generate patches, prove global correctness, prove that the declared invariant set is complete, or prove that a repair is minimal. Baseline/candidate assessment fingerprints and `changedElements` are explicit reviewed evidence.

A future minimal-repair search can build on this primitive by enumerating candidate/subset changes and requiring each candidate to pass `CGQ-CAUSAL-001`; minimality must be proved separately rather than assumed from patch size.
