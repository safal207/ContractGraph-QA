# CGQA-001 — Double payout accounting invariant is reachable

**Severity:** HIGH  
**Contract:** `VulnerableEscrow`  
**Network / environment:** `local-foundry`

## Executive summary

A bounded breadth-first search finds an accepted three-action path that records both a release and a refund against the same deposit. The path is deterministic and replayable against the deliberately vulnerable local fixture.

## Violated invariant

**payout-conservation**

```text
releasedAmount + refundedAmount <= depositedAmount
```

## Minimal failing path

| Step | Actor | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|---|
| 1 | authorized test actor | `fund(100)` | `CREATED` | `FUNDED` | deposit recorded |
| 2 | authorized test actor | `release()` | `FUNDED` | `FUNDED` | release recorded without closing terminal state |
| 3 | authorized test actor | `refund()` | `FUNDED` | `REFUNDED` | refund recorded after release |

## Impact

The accounting model can represent two mutually exclusive payout outcomes for one deposit. In a real escrow design, an equivalent state-machine defect could break conservation assumptions and must be prevented before deployment.

## Evidence and replay

- **Authorization:** Deliberately vulnerable local fixture owned by this repository; no third-party production target is involved.
- **Replay:** `forge test --match-test test_AutomaticallyFindsMinimalDoublePayoutPath -vvv`
- **Explored candidates:** 18
- **Notes:** The explorer searches shortest action sequences first, so the first discovered violation is minimal by action count within the modeled action alphabet and depth.

## Recommendation

Make release a terminal state transition atomically with its accounting update, and ensure refund is unreachable after release. Preserve this exact path as a regression test after the fix.

## Retest checklist

- [ ] Apply the proposed fix in the authorized target.
- [ ] Replay the exact minimal failing path.
- [ ] Confirm the violated invariant now holds after every accepted transition.
- [ ] Keep the path as a regression test.

## Scope note

This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.
