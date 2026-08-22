# ContractGraph-QA State-Transition Benchmark Suite v0.1

This benchmark suite tests failures that can remain invisible when individual functions pass in isolation.

Core thesis:

> Functions may pass. The lifecycle may still fail.

The suite focuses on reachable state-machine failures, economic liveness, replay semantics, timeout recovery, and composition safety.

## Benchmark matrix

| ID | Name | Function verification | Lifecycle verification | Primary invariant |
|---|---|---:|---:|---|
| CGQ-B001 | The Disputed Dead-End | PASS | FAIL | `NO_LOCKED_VALUE_DEAD_END` |
| CGQ-B002 | Replay Without Theft | PASS | FAIL | `AT_MOST_ONCE_ECONOMIC_EFFECT` |
| CGQ-B003 | Timeout Without Escape | PASS | FAIL | `TIMEOUT_REQUIRES_RECOVERY_PATH` |
| CGQ-B004 | Valid Functions, Invalid Composition | PASS | FAIL | `SINGLE_VALID_SUCCESSOR_PER_STATE_VERSION` |

## CGQ-B001 — The Disputed Dead-End

A participant can move an escrow into `Disputed`, but no contract-level path returns the locked value to an economically terminal state.

```text
Active
  ↓
Funded
  ├──→ Delivered → Released
  └──→ Disputed → DEAD_END
```

Required property:

```text
locked_value(state) > 0
⇒ exists path(state, Released | Refunded)
```

Expected result:

```text
FUNCTION TESTS: PASS
LIFECYCLE: FAIL
COUNTEREXAMPLE: Active → Funded → Disputed → DEAD_END
```

Product message: **17/17 tests passed. Funds can still be locked forever.**

## CGQ-B002 — Replay Without Theft

A finalized business action must not produce a second economic effect when replayed, even if no direct token theft occurs.

Required property:

```text
finalized(action_id)
⇒ future execution(action_id) = rejected
```

or equivalently:

```text
economic_effect_count(action_id) <= 1
```

Expected result:

```text
FUNCTION TESTS: PASS
LIFECYCLE: FAIL
COUNTEREXAMPLE: Delivered → release(A) → Released → release(A) → DUPLICATE_EFFECT
```

## CGQ-B003 — Timeout Without Escape

Rejecting a late action is not enough. A time-bounded state that still holds value must retain a recovery path after expiry.

```text
Funded
  ↓ time passes
Expired
  ↓
DEAD_END
```

Required property:

```text
deadline_expired(state)
⇒ exists recovery_path(state)
```

Expected result:

```text
DEADLINE ENFORCEMENT: PASS
LIFECYCLE: FAIL
COUNTEREXAMPLE: Funded → DeadlineExceeded → NO_VALID_TRANSITION
```

## CGQ-B004 — Valid Functions, Invalid Composition

Two operations may each be valid against the same observed state while being mutually incompatible when committed.

```text
S0 = Funded@v7

Actor A reads S0
Actor B reads S0

A → deliver()
B → raiseDispute()
```

Required property:

```text
transition(T).authorized_state_version
=
transition(T).committed_parent_state_version
```

and:

```text
mutually_exclusive(T1, T2)
⇒ not committed(T1 and T2)
```

Expected result:

```text
FUNCTION TESTS: PASS
AUTHORIZATION: PASS
LIFECYCLE: FAIL
COUNTEREXAMPLE:
Funded@v7
├→ Delivered@v8
└→ Disputed@v8
```

## Invariant families

The suite defines four initial families:

1. **Reachability** — can a dangerous state be reached?
2. **Liveness** — once reached, does a safe terminal path still exist?
3. **Economic safety** — can value be duplicated, destroyed, or permanently inaccessible?
4. **Transition consistency** — were authorization and commit bound to the same state/version?

Canonical IDs are in [`invariants.json`](invariants.json).

## Machine-readable cases

Each benchmark case is stored under [`cases/`](cases/) as JSON with:

- benchmark ID and name;
- expected function-level outcome;
- expected lifecycle outcome;
- invariant ID;
- minimal counterexample path;
- risk class;
- expected ContractGraph-QA verdict.

See [`suite.json`](suite.json) for the suite manifest.

## Standard expected output

```text
ContractGraph-QA Verification Report

Benchmark: CGQ-Bxxx
Function verification: PASS | FAIL
State-transition verification: PASS | FAIL
Economic verification: PASS | FAIL
Invariant: <invariant_id>
Counterexample: S0 → S1 → ... → FAILURE
Economic consequence: <description>
Confidence: low | medium | high
```

## Positioning

Developer:

> Unit tests verify operations. ContractGraph-QA verifies their composition.

Security:

> Find reachable economic failures that are invisible at the function boundary.

Executive:

> Green tests are evidence, not proof of a safe lifecycle.

Landing-page line:

> **17/17 tests passed. The funds can still be locked forever.**
