# CGQA-002 — Deposit cap boundary is not enforced

**Severity:** MEDIUM  
**Contract:** `VulnerableTimedEscrow`  
**Network / environment:** `local-foundry`

## Executive summary

A bounded parameter corpus reaches a one-step state where the declared maximum deposit of 100 is exceeded by fund(101).

## Violated invariant

**deposit-cap**

```text
depositedAmount <= MAX_DEPOSIT
```

## Minimal failing path

| Step | Actor | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|---|
| 1 | authorized test actor | `fund(101)` | `CREATED` | `FUNDED` | deposit recorded above declared cap |

## Impact

A contract whose implementation omits an intended deposit cap can accept states outside its declared business rules. The local fixture demonstrates how deterministic boundary-value exploration can surface that mismatch.

## Evidence and replay

- **Authorization:** Deliberately vulnerable local fixture owned by this repository; no third-party production target is involved.
- **Replay:** `forge test --match-test test_ParameterCorpusFindsOversizedDeposit -vvv`
- **Explored candidates:** 3
- **Notes:** The corpus checks values below, at, and immediately above the declared boundary: 1, 100, and 101.

## Recommendation

Enforce the maximum deposit atomically inside fund() and keep fund(101) as a regression case after the fix.

## Retest checklist

- [ ] Apply the proposed fix in the authorized target.
- [ ] Replay the exact minimal failing path.
- [ ] Confirm the violated invariant now holds after every accepted transition.
- [ ] Keep the path as a regression test.

## Scope note

This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.
