# Gonka Verification Profile v0.1

Independent ContractGraph-QA profile for critical Gonka state transitions.

## Scope

This profile focuses on causal integrity across:

`client intent -> gateway -> funded devshard -> execution -> usage/accounting -> settlement -> recovery`

It is deliberately narrower than a generic security audit. The target is whether financial and protocol state transitions remain explainable under normal operation, retries, ambiguity, restart, and epoch/devshard boundaries.

## Safety boundary

- Local Gonka `devshard/testenv`, Community DevNet, or another explicitly permitted environment only.
- Fault injection defaults to the local Docker testenv.
- No destructive testing against mainnet.
- No real-funds fault injection.
- Secrets are redacted from evidence.
- Security-sensitive or financially relevant findings remain private until coordinated disclosure.

## Why this is complementary to Gonka's own tests

Gonka already ships substantial Docker-backed end-to-end coverage for gateway chat, epoch switching, versiond failover/restart persistence, HA/storage recovery, validation lease races, rolling updates, escrow warmup, and gRPC-only chain transport.

ContractGraph-QA adds a different lens: one stable **logical operation identity** across transport attempts, then reconciles transport disposition, execution nonce(s), request accounting, cost, settlement, and recovery evidence across boundaries.

See `upstream-gap-map.md` for the coverage mapping and `execution-surface.md` for the safety/execution ladder.

## First target

### G-001 — control

Normal inference through `/v1/chat/completions` establishes a funded-devshard control and a complete evidence baseline.

Contract: `cases/G-001-normal-inference.yaml`

### G-002 — first independent delta

Create an ambiguous client timeout after dispatch in the local Gonka testenv, retry the same semantic operation once, and verify that final request accounting remains causally explainable.

Contract: `cases/G-002-timeout-retry.yaml`

The test does **not** assume Gonka promises HTTP idempotency. It verifies the stronger and more implementation-neutral property that all observed transport, execution, and cost effects remain explicit and reconcilable.

Two variants are implemented:

- **G-002A** — retry reuses the same `X-Request-Id`.
- **G-002B** — retry uses a fresh transport `X-Request-Id` while CGQA keeps one semantic `logical_operation_id`.

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
  -> transport_attempt_1
  -> ambiguous client outcome
  -> protocol may continue
  -> transport_attempt_2
  -> observed execution nonce(s)
  -> request accounting / cost
  -> reconciled terminal state
```

## Evidence rule

A reconciliation `PASS` is valid only when:

1. every declared transport request ID has at least one known disposition;
2. required request/accounting/state source artifacts exist;
3. every observed execution nonce has request lineage;
4. winner and non-winner totals derived from `attempts[]` equal the reported cost fields;
5. aggregate cost arithmetic reconciles;
6. there are no unexplained effects.

`INCONCLUSIVE` means evidence is insufficient to make a causal claim. `FAIL` means a reconciliation invariant was violated; it is still a private verification hypothesis until independently reproduced and triaged.

## Files

- `graph.yaml` — causal transition map, including funded escrow before inference dispatch.
- `invariants.md` — verification invariants.
- `scenarios.md` — scenario matrix and hypotheses.
- `cases/G-001-normal-inference.yaml` — control contract.
- `cases/G-002-timeout-retry.yaml` — timeout/retry contract.
- `harness/cgqa_gonka_test.go` — Docker testenv evidence harness.
- `evidence.schema.json` — reconciliation JSON Schema.
- `runbook.md` — manual/portable execution procedure.
- `execution-surface.md` — safe execution ladder.
- `upstream-gap-map.md` — mapping to Gonka's existing testenv coverage.
- `verification-report.md` — evidence and verdict template.

## Current status

G-001, G-002A, and G-002B are implemented against pinned Gonka revision `f040d0a5b5ef207a0c431894c9f9e2608f9d3073`. The upstream contract guard compiles the harness and runs Gonka's own request-accounting controls. Docker-backed evidence execution is the active verification gate; no public-network result or vulnerability claim is implied by implementation alone.
