# CGQA-005 — Manifest export preserves the minimal terminal-state violation path

**Severity:** INFO  
**Contract:** `AdapterFixtureMachine`  
**Network / environment:** `local-foundry-adapter-manifest`

## Executive summary

A validated v0.8 adapter manifest and explorer result are deterministically transformed into a client finding for the same three-step terminal-state violation detected by the local adapter regression.

## Violated invariant

**adapter-terminal-state**

```text
phase < 3
```

## Minimal failing path

| Step | Actor | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|---|
| 1 | authorized adapter test actor | `advance()` | `phase=0` | `phase=1` | future-relevant protocol state changes |
| 2 | authorized adapter test actor | `advance()` | `phase=1` | `phase=2` | second unique protocol state is reached |
| 3 | authorized adapter test actor | `advance()` | `phase=2` | `phase=3` | terminal invariant becomes false |

## Impact

The manifest layer preserves the evidence needed to map a machine-discovered path into a reviewable finding without manually re-entering action names, actors, invariant metadata, scope wording, or report fields.

## Evidence and replay

- **Authorization:** Local adapter fixture owned by this repository; no third-party production target is involved.
- **Replay:** `forge test --match-test test_AdapterPreservesMinimalViolatingPathWithDedup -vvv`
- **Explored candidates:** 6
- **Notes:** This explorer-result fixture corresponds to the local v0.7 adapter regression and is used only to verify deterministic manifest-to-finding export.

## Recommendation

For a real authorized engagement, review the adapter manifest against the written scope, keep the action and state-field mappings complete, and export only deterministic explorer results produced from the matching fixed-block adapter.

## Retest checklist

- [ ] Apply the proposed fix in the authorized target.
- [ ] Replay the exact minimal failing path.
- [ ] Confirm the violated invariant now holds after every accepted transition.
- [ ] Keep the path as a regression test.

## Scope note

This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.
