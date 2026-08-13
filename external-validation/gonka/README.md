# Gonka Verification Profile v0.1

Independent ContractGraph-QA profile for critical Gonka state transitions.

## Scope

This profile focuses on causal integrity across:

`client intent -> gateway -> devshard execution -> usage/accounting -> settlement -> recovery`

It is deliberately narrower than a generic security audit. The target is whether financial and protocol state transitions remain explainable under normal operation, retries, ambiguity, restart, and epoch/devshard boundaries.

## Safety boundary

- Local Gonka `devshard/testenv`, Community DevNet, or another explicitly permitted environment only.
- No destructive testing against mainnet.
- No real-funds fault injection.
- Secrets are redacted from evidence.
- Security-sensitive or financially relevant findings remain private until coordinated disclosure.

## Why this is complementary to Gonka's own tests

Gonka already ships substantial Docker-backed end-to-end coverage for gateway chat, epoch switching, versiond failover/restart persistence, HA/storage recovery, validation lease races, rolling updates, escrow warmup, and gRPC-only chain transport.

ContractGraph-QA adds a different lens: one stable **logical operation identity** across transport attempts, then reconciles execution, usage/accounting, settlement, and recovery evidence across boundaries.

See `upstream-gap-map.md` for the coverage mapping.

## First target

### G-001 — control

Normal inference through `/v1/chat/completions` establishes a clean evidence baseline.

Contract: `cases/G-001-normal-inference.yaml`

### G-002 — first independent delta

Create an ambiguous client/gateway timeout after dispatch, retry the same semantic operation once, and verify that final accounting remains causally explainable.

Contract: `cases/G-002-timeout-retry.yaml`

The test does **not** assume Gonka promises HTTP idempotency. It verifies the stronger and more implementation-neutral property that retries cannot create hidden, unexplained, or orphaned financial effects.

## Core model

```text
actor
  -> action
  -> state transition
  -> invariant
  -> evidence
```

For retries:

```text
logical_operation_id
  -> execution_attempt_1
  -> ambiguous transport outcome
  -> execution_attempt_2
  -> observed execution(s)
  -> usage/accounting delta
  -> settlement/recovery
  -> reconciled terminal state
```

## Files

- `graph.yaml` — causal transition map.
- `invariants.md` — verification invariants.
- `scenarios.md` — scenario matrix and hypotheses.
- `cases/G-001-normal-inference.yaml` — control contract.
- `cases/G-002-timeout-retry.yaml` — timeout/retry contract.
- `upstream-gap-map.md` — mapping to Gonka's existing testenv coverage.
- `verification-report.md` — evidence and verdict template.

## Current status

Design complete for G-001/G-002. Execution has **not** yet been claimed. The next engineering step is to implement G-002 inside Gonka's Docker-backed local testenv, reusing its existing gateway chat control and mock services, then emit a CGQA evidence bundle.