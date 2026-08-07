# CGQA-003 — Refund becomes reachable before the intended delay

**Severity:** HIGH  
**Contract:** `VulnerableTimedEscrow`  
**Network / environment:** `local-foundry`

## Executive summary

A bounded parameter-and-time search finds a three-step path where refund succeeds after one day even though the modeled business invariant requires a seven-day delay.

## Violated invariant

**refund-timing**

```text
state != REFUNDED || block.timestamp >= expectedRefundAfter
```

## Minimal failing path

| Step | Actor | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|---|
| 1 | authorized test actor | `fund(1)` | `CREATED` | `FUNDED` | deposit recorded |
| 2 | test clock | `wait(1 day)` | `FUNDED @ T0` | `FUNDED @ T0+1d` | clock advanced by one day |
| 3 | authorized test actor | `refund()` | `FUNDED @ T0+1d` | `REFUNDED @ T0+1d` | refund recorded before expected seven-day delay |

## Impact

A mismatch between intended and implemented time guards can make a state transition reachable earlier than the business rules allow. The local fixture demonstrates how explicit time actions expose that discrepancy.

## Evidence and replay

- **Authorization:** Deliberately vulnerable local fixture owned by this repository; no third-party production target is involved.
- **Replay:** `forge test --match-test test_TemporalCorpusFindsEarlyRefundPath -vvv`
- **Notes:** Each candidate resets both contract state and the baseline timestamp so time from one candidate cannot leak into another.

## Recommendation

Use the intended seven-day delay when calculating the refund threshold and retain the one-day path as a regression test that must remain rejected.

## Retest checklist

- [ ] Apply the proposed fix in the authorized target.
- [ ] Replay the exact minimal failing path.
- [ ] Confirm the violated invariant now holds after every accepted transition.
- [ ] Keep the path as a regression test.

## Scope note

This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.
