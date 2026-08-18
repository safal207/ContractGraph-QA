# G-005 held-out observation 001

Status: `HOLD_GENERATION_REPIN_REQUIRED`

This observation was created after `G-005-restart-recovery.sealed.json` was committed. It does not modify the sealed hypothesis set or baseline order.

## First ATMAN evidence check

`COMPARE_RUNTIME_FINGERPRINT`

## Observation

The historical CGQA Gonka coverage analysis in `upstream-gap-map.md` was pinned to upstream revision:

`f040d0a5b5ef207a0c431894c9f9e2608f9d3073`

The currently inspected upstream restart-persistence test is at revision:

`379bebced638aeb5e6077bfd51c986f898443832`

Therefore the historical coverage interpretation and the current upstream restart test are not yet generation-coherent evidence for one target-side claim.

## Current upstream restart contract observed

`TestVersiondRestartSessionPersistence` explicitly verifies that gateway chat plus session nonce/state survive one versiond restart and then all versiond restarts using Postgres-backed recovery. It checks stable/advanced gateway session snapshots around restart.

This is strong persistence coverage, but this observation alone does not establish whether pending usage preserves the full causal mapping:

`logical_operation_id -> transport attempt(s) -> execution nonce(s) -> accounting mutation -> settlement ref(s)`

## ATMAN verdict

`VERIFIER_GENERATION_MISMATCH / HOLD`

No target-side FAIL/PASS claim is permitted from this mixed-generation evidence.

## Next best evidence

1. Repin the G-005 investigation to one exact upstream revision and runtime/image fingerprint.
2. Re-read the restart test and storage/accounting path on that same revision.
3. Only then execute `TRACE_REQUEST_IDENTITY` around a restart with pending usage.

## Epistemic boundary

`HistoricalCoverage != CurrentAuthorizationToClaim`

`RestartSessionPersistence != CausalAccountingLineagePreservation`
