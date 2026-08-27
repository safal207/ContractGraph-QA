# Protective Ordering Benchmark v0.1

Invariant: `CGQ-RACE-001` — `PROTECTIVE_ACTION_CANNOT_BE_DEFEATED_BY_ORDERING`.

This benchmark covers a class that successor-consistency does not: two actions may both be legal from one parent state/version, only one may commit because execution is serialized, yet the protected business right can still be lost solely because the competing action is ordered first.

## MilePact-style fixture

Parent: `Delivered@7`

- protective action: `raiseDispute`
- competing terminal action: `autoRelease`

Counterfactual A:

```text
autoRelease -> raiseDispute
Released
freelancer paid
dispute reverts
protective right lost
```

Counterfactual B:

```text
raiseDispute -> autoRelease
Disputed
dispute commits
autoRelease reverts
protective right preserved
```

Run:

```bash
cgqa-race --model scenarios/milepact-protective-ordering-race.json
```

Expected result: `FAIL` with the shortest violating ordering `autoRelease -> raiseDispute`.

## Claim boundary

The verifier does not infer Solidity enablement, mempool behavior, or intended product policy. The reviewed model must establish that both actions are enabled from the same parent state/version and that the protective action is intended to remain effective across ordering. The verifier then deterministically evaluates the declared two-order counterfactual.

## Timeout/recoverability companion

`scenarios/milepact-funded-timeout-client-unavailable.json` reuses `CGQ-LIVE-002`. It models the separate N3 hypothesis: after a timeout, a branch in which the client is unavailable remains value-holding with no independent recovery path.

That fixture proves a recoverability failure only under the declared requirement that timed-out locked value must retain a path to a safe terminal despite client unavailability. If the protocol intentionally requires the client to remain available forever, classify the result as a design/recoverability risk rather than automatically escalating it to a security vulnerability.
