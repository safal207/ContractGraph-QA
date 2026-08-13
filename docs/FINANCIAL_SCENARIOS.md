# Financial Control Reachability Scenarios

These repository-owned models turn the generic adversarial reachability engine into concrete financial-control examples for AI-agent payments, programmable wallets, and escrow workflows.

Each scenario is local, deterministic, bounded, and synthetic. It demonstrates a control failure shape; it is not a claim about a third-party provider or production system.

| Scenario | Broken assumption | Forbidden capability | Invariant / boundary |
|---|---|---|---|
| Escrow approval bypass | required approval threshold is enforced | release without required approval | `escrow-release-requires-approval` / `approval-threshold` |
| Stale authority | authority state is fresh | spend under stale delegated authority | `payment-authority-must-be-current` / `authority-freshness` |
| Revoked authority | revocation is propagated before resolution | spend after revocation | `revoked-authority-cannot-spend` / `authority-revocation` |
| Idempotency replay | retry identity remains stable until final reconciliation | create a second financial attempt | `retry-must-preserve-idempotency` / `idempotency-continuity` |
| Duplicate settlement | committed settlement is applied at most once | apply settlement effects twice | `settlement-applied-once` / `settlement-deduplication` |

Run any example with:

```bash
cgqa reachability --model scenarios/escrow-approval-bypass.json
cgqa reachability --model scenarios/stale-authority.json
cgqa reachability --model scenarios/revoked-authority.json
cgqa reachability --model scenarios/idempotency-replay.json
cgqa reachability --model scenarios/duplicate-settlement.json
```

The intended client-facing pattern is:

```text
financial intent
→ broken control assumption
→ capability transition
→ invariant/control boundary
→ forbidden financial capability
→ business impact
→ containment/recovery/verification
→ fix replay
```

The scenarios deliberately keep one causal transition each so the evidence is easy to inspect. More realistic adapters can expand the same vocabulary into multi-step resolution, retry, webhook, ledger, settlement, approval, and authority paths without changing the fail-closed semantics of the engine.

## Failure examples vs reviewed baselines

The five models above are deliberately unsafe examples: each one declares the control assumption needed to traverse its forbidden transition as violated.

For PR-level regression gating, use the corresponding reviewed baseline models under `scenarios/financial-control-baselines/`. They preserve the same assumption, forbidden capability, transition, invariant, boundary, and impact identities while leaving `violatedAssumptions` empty.

See [`FINANCIAL_CONTROL_BASELINES.md`](FINANCIAL_CONTROL_BASELINES.md) and the machine-readable `financial-control-gate.toml` profile for the staged path from synthetic examples to a trusted financial-control pilot.
