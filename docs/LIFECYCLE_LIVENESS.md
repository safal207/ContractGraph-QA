# Lifecycle Liveness Verification

ContractGraph-QA lifecycle liveness verification checks a system-level property that function-level tests can miss:

> Every reachable state that still holds locked economic value must retain a path to at least one declared safe economic terminal.

This is intentionally separate from adversarial capability reachability. Capability reachability asks whether a forbidden capability can become reachable. Lifecycle liveness asks whether value can become trapped after otherwise valid state transitions.

## CLI

```bash
cgqa lifecycle-liveness --model scenarios/escrow-disputed-dead-end.json
```

A failing model returns exit code `10` and deterministic JSON similar to:

```json
{
  "status": "fail",
  "invariantId": "CGQ-LIVE-001",
  "violations": [
    {
      "state": "Disputed",
      "reason": "reachable_value_holding_dead_end",
      "counterexampleStates": ["Active", "Funded", "Disputed"],
      "counterexampleTransitions": ["fund", "raise-dispute-from-funded"],
      "outgoingTransitions": []
    }
  ]
}
```

If every reachable value-holding state can reach a declared safe terminal, the command returns `status: pass` and exit code `0`.

## Model contract

The model is a finite directed state graph:

```json
{
  "states": [
    {
      "id": "Funded",
      "description": "Escrow holds funded value.",
      "holdsValue": true,
      "safeTerminal": false
    },
    {
      "id": "Refunded",
      "description": "Escrow value returned to the buyer.",
      "holdsValue": false,
      "safeTerminal": true
    }
  ],
  "transitions": [
    {"id": "refund", "source": "Funded", "target": "Refunded"}
  ],
  "initialState": "Funded",
  "invariantId": "CGQ-LIVE-001"
}
```

The JSON Schema is [`graph/schema/lifecycle-liveness.schema.json`](../graph/schema/lifecycle-liveness.schema.json).

## Semantics

The analyzer first computes all states reachable from `initialState`. Unreachable modeled states do not create findings.

It then computes, by reverse graph traversal, every state that can reach a `safeTerminal`. Any state that is both reachable and `holdsValue: true` but cannot reach a safe terminal violates the invariant.

Two failure shapes are distinguished:

- `reachable_value_holding_dead_end` — no outgoing transition exists;
- `reachable_value_holding_trap` — outgoing transitions exist, but every path remains trapped away from safe economic termination, including closed cycles.

This distinction prevents a superficial fix that merely adds another transition while leaving value trapped in a cycle.

## Evidence boundary

The result contains a canonical model SHA-256 and a deterministic minimal path from the initial state to each violating state.

The result is exact over the declared finite graph. It does **not** prove that the declared graph is a complete extraction of an external contract. Source-to-model completeness must be established separately by adapter review, capture evidence, or another provenance boundary.

## Benchmark connection

The repository fixture `scenarios/escrow-disputed-dead-end.json` is the executable form of **CGQ-B001 — The Disputed Dead-End**.

Canonical distinction:

```text
Function verification: PASS
Lifecycle liveness: FAIL

Active → Funded → Disputed → DEAD_END
```

The same graph algorithm also verifies **CGQ-B003 — Timeout Without Escape** through `scenarios/timeout-without-recovery.json` and invariant `CGQ-LIVE-002 — TIMEOUT_REQUIRES_RECOVERY_PATH`:

```text
Funded → DeadlineExceeded → DEAD_END
```

Adding a valid recovery edge such as `DeadlineExceeded → Refunded` makes the model pass. Adding only another non-terminal review state does not help if the new path remains trapped in a cycle.

This reuse is deliberate: dispute dead-ends and timeout dead-ends have different business causes, but both reduce to the same graph property — reachable locked value without a path to safe economic termination.

This is the product-level lesson:

> A function can be correct while the lifecycle is wrong.
