# CGQA-004 — Fork adapter preserves the minimal terminal-state violation path

**Severity:** INFO  
**Contract:** `AdapterFixtureMachine`  
**Network / environment:** `local-foundry-adapter-regression`

## Executive summary

The v0.7 adapter regression binds protocol state to authorization/fork provenance, deduplicates equivalent states, and preserves the shortest three-step path to the modeled terminal invariant violation.

## Violated invariant

**adapter-terminal-state**

```text
phase < 3
```

## Minimal failing path

| Step | Actor | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|---|
| 1 | authorized adapter test actor | `advance()` | `phase=0` | `phase=1` | future-relevant protocol state changes |
| 2 | authorized adapter test actor | `advance()` | `phase=1` | `phase=2` | second unique state is reached |
| 3 | authorized adapter test actor | `advance()` | `phase=2` | `phase=3` | terminal invariant becomes false |

## Impact

This local regression demonstrates the client-adapter evidence path: protocol-specific state is bound to fork/scope provenance, equivalent states are pruned, and the shortest invariant-violating sequence remains replayable.

## Evidence and replay

- **Authorization:** Local adapter fixture owned by this repository; no third-party production target is involved.
- **Replay:** `forge test --match-test test_AdapterPreservesMinimalViolatingPathWithDedup -vvv`
- **Notes:** The regression uses a local fixture so default CI never opens an external fork. Real fork adapters remain gated by v0.6 authorization preflight.

## Recommendation

For a real authorized engagement, replace the fixture actions, protocol state hash, and invariant with contract-specific definitions reviewed against the written scope, then export any discovered path through the same deterministic report pipeline.

## Retest checklist

- [ ] Apply the proposed fix in the authorized target.
- [ ] Replay the exact minimal failing path.
- [ ] Confirm the violated invariant now holds after every accepted transition.
- [ ] Keep the path as a regression test.

## Scope note

This report describes evidence from the explicitly modeled and authorized test scope. It is not a claim of exhaustive security verification.
