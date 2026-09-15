# Identity / authority boundary v0.1

**Result: 6/6 PASS; 2/2 unsafe mutants detected.**

This executable model is the next proof boundary after the admitted CrewAI retry evidence in PR #171 and tracks issue #172.

The invariant is:

> Restoring `action_id` is evidence about which logical action this is; it is not permission to perform the action again.

The model intentionally separates three things that are often collapsed:

1. **identity** — a stable `action_id` derived from intent + target + normalized args;
2. **authority** — a one-use permit bound to action + target + intent;
3. **effect truth** — an external receipt/read-back used during recovery.

## Cases

| Case | Expected decision | Dispatch after recovery |
|---|---|---:|
| `control-new` | fresh permit -> dispatch | 1 |
| `recovery-confirmed` | `return_prior` | 0 |
| `recovery-unknown` | `fail_closed` | 0 |
| `recovery-not-executed` | `fresh_authorization` -> new permit -> dispatch | 1 |
| `replay-old-permit` | `reject_reused_permit` | 0 |
| `target-mismatch` | `reject_target_mismatch` | 0 |

All five recovery cases preserve the same `action_id`. None obtains authority from that identity alone. The only recovery case that dispatches is `recovery-not-executed`, and it does so only after an explicit new permit is issued and consumed.

## Unsafe semantics discriminated

The harness includes two negative controls:

- a mutant authority store that ignores the consumed bit and accepts the same permit twice;
- a recovery mutant that treats `UNKNOWN` read-back plus a persisted action identity as enough authority to dispatch.

Both are detected (`2/2`).

## Reproduce

```bash
python proofs/identity-authority-boundary-v0.1/harness.py \
  --write-report /tmp/identity-authority-report.json

diff -u \
  proofs/identity-authority-boundary-v0.1/report.json \
  /tmp/identity-authority-report.json
```

The hosted workflow `.github/workflows/identity-authority-boundary.yml` runs exactly that command and requires byte-for-byte equality with the committed report.

## Claim ceiling

This is a **framework-neutral executable contract model**, not yet a CrewAI, LangGraph, AutoGen, or ServiceNow runtime integration.

It does **not** establish:

- global exactly-once execution;
- that any specific framework currently preserves this boundary;
- target availability or Byzantine correctness;
- distributed consensus;
- correctness of arbitrary receipt providers;
- durability or non-bypassability of a real authorization service.

The model assumes the authority store is durable and non-bypassable.

## Next step

Bind the same six cases to a real retry/recovery surface without weakening the contract:

`stable action identity -> fresh authorization -> one-use permit -> dispatch -> external receipt/read-back -> bounded recovery decision`

The first runtime adapter should be considered conformant only if it preserves both:

- **identity continuity** across retry/recovery; and
- **authority non-continuity** across retry/recovery.

Links:

- issue: https://github.com/safal207/ContractGraph-QA/issues/172
- predecessor proof: https://github.com/safal207/ContractGraph-QA/pull/171
