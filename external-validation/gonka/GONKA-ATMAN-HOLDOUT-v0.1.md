# GONKA-ATMAN Held-Out Benchmark v0.1

Status: experimental, prospective only.

## Purpose

Measure whether the frozen GONKA-ATMAN evidence selector reaches the evidence check that resolves a previously unknown Gonka discrepancy with fewer evidence checks than a fixed baseline order.

This protocol must not be backfilled onto already-known GONKA-001/GONKA-002 targets and then described as held-out evidence.

## Pre-reveal seal

Before the hidden target cause is known, persist:

- case_id
- logical_operation_id
- pinned source revision
- runtime generation
- evidence generation
- competing hypotheses
- already-observed evidence checks
- frozen policy_id
- SHA-256 commitment over the canonical public case payload

The sealed payload MUST NOT contain `target_cause`, `oracle`, or equivalent target labels.

## Frozen baseline order

1. TRACE_REQUEST_IDENTITY
2. WAIT_NEXT_PROTOCOL_DIFF
3. RECONCILE_EXECUTION_NONCES
4. RECONCILE_SETTLEMENT_REFS
5. COMPARE_RUNTIME_FINGERPRINT

This order is intentionally simple and fixed before the oracle is revealed.

## Reveal

After independent evidence establishes which bounded check actually resolves the hidden discrepancy, reveal:

- target_cause
- resolving_check_id

Then evaluate the sealed case without rewriting its hypotheses, policy id, generations, or observed-evidence state.

## Metrics

- baseline_checks_to_resolution
- ATMAN first selected check
- ATMAN checks to resolution (v0.1 reports 1 only when the first selection is resolving; otherwise unresolved-on-first-check)
- evidence_checks_saved
- verdict

## Interpretation

`ATMAN_EARLIER` means only that the frozen selector chose the resolving evidence check earlier than the fixed baseline on that prospectively sealed case.

It does not prove:

- a vulnerability,
- severity,
- real-world causality,
- universal search superiority,
- or correctness outside the bounded hypothesis/check set.

## Anti-hindsight invariants

- Known target != held-out target.
- Post-reveal hypothesis edits invalidate the benchmark.
- Post-reveal policy edits create a new policy generation and cannot be scored as the original run.
- Repeated use of the same revealed target is evaluation reuse, not fresh evidence.
- A failed ATMAN selection must be preserved; it may inform a future policy revision but cannot be retroactively rescored.

## Next valid milestone

The first publishable held-out number requires a genuinely new Gonka discrepancy whose case seal predates target resolution.
