# Gonka Verification Profile v0.1

Independent state-transition verification profile for Gonka decentralized AI inference, billing, settlement, epoch transitions, and reward recovery.

## Scope

This profile models critical Gonka behavior as:

`actor -> action -> state transition -> invariant -> evidence`

Primary surfaces:

1. Developer/gateway request authorization
2. Devshard escrow creation and rotation
3. Off-chain per-request accounting
4. On-chain settlement
5. Retry / duplicate / timeout behavior
6. Epoch boundary behavior
7. Host reward claim and recovery

## Safety boundary

- DevNet / local / explicitly permitted environments only.
- No destructive or adversarial testing against Gonka mainnet.
- No publication of security-sensitive findings before coordinated disclosure.
- Public artifacts should contain reproducible evidence only after remediation or explicit approval.

## Verification spine

```text
Developer
  -> Gateway / Broker
  -> signed inference request
  -> devshard escrow
  -> Host / Executor
  -> inference result
  -> validation / accounting
  -> off-chain usage state
  -> on-chain settlement
  -> epoch rotation / recovery
```

## Initial invariants

See `invariants.md`.

## Scenario matrix

See `scenarios.md`.

## Evidence contract

Every executed scenario should produce an evidence bundle with:

- logical_operation_id
- execution_id / attempt
- actor
- request digest
- resolved target / endpoint / model metadata
- pre-state snapshot or digest
- observed state transitions
- post-state snapshot or digest
- expected invariant
- observed outcome
- timestamps / epoch identifier
- relevant transaction / settlement / validation references
- verdict

## Status

v0.1 is a verification design profile. It does not claim any Gonka vulnerability or protocol failure.
