# StreamPay exact settlement v0.1

External, bounded ContractGraph-QA evidence for
[StreamPay-Contracts issue #153](https://github.com/Streampay-Org/StreamPay-Contracts/issues/153)
and [PR #161](https://github.com/Streampay-Org/StreamPay-Contracts/pull/161).

## Exact bindings

- StreamPay repository: `Streampay-Org/StreamPay-Contracts`
- target commit: `2baa37b533c07790d6aa38ab0a5c0170fcbbb44f`
- target tree: `3eb31ad4643617d37e07ac0ad03412bf7f237aa4`
- target commit-blob SHA-256:
  - `src/lib.rs`: `fb16000550ca2a31036af721c3607d4e71ef2f40fc2994e34a0cf1d5d621e7da`
  - `tests/issue153_paused_regressions.rs`: `96afb4a790032c38c8ef70dead081f96ad3f67c86e521aea9bc087b4f4555e65`
- CGQA runtime: tag `v1.8.0`, core commit
  `51c8e81a42e53ea8b26b396f0c1df4f64418c351`
- verifier path: `benchmarks/streampay-exact-settlement-v0.1/verify.py`
- verifier SHA-256:
  `907149fd313782fde5ff6d40756e1e9bf9e0d8b8cb4f9da89c26d25cf8f22adf`

The verifier does not trust these labels alone. `--target-checkout` is
mandatory. It requires exact target HEAD and tree, clean tracked scope, the two
expected commit blobs, and working content canonically equal to those blobs.
It also resolves the imported `contractgraph_qa` package to a clean checkout
at the exact core commit and tag.

For publication, `--evidence-commit` must equal the evidence checkout HEAD;
the verifier and this README must be clean, tracked, and byte-identical to the
blobs in that commit. Omitting it produces development-only
`boundedVerdict: UNBOUND`, never `PASS`.

## Model and independent oracle

Production lifecycle fields are represented by `phase`, `cursor`, and
`paused_at`. A separate `oracle_phase` is advanced from action history and
authorization rules; it never reads implementation phase, cursor, payout
formula, or `paused_at`. Eligible active time is accumulated only from this
independent lifecycle oracle.

The fixed value-moving semantics use:

```text
end_bound = end_time == 0 ? now : min(now, end_time)
accrual_bound = paused_at == 0 ? end_bound : min(end_bound, paused_at)
effective_cursor = paused_at == 0 ? cursor : max(cursor, paused_at)
```

`effective_cursor` accepts both fresh fixed states (`cursor == paused_at`) and
the persisted pre-fix paused shape (`cursor < paused_at`, interval already
accounted). An accepted value-moving action normalizes the cursor and cannot
repay that interval.

The executable lifecycle includes `start`, `pause`, `resume`, `settle`,
`batch_settle`, `cancel`, and payer-authorized terminal `stop`. Terminal
settlement uses the same end/pause-aware boundary and clears stale pause state.
Terminal pause/resume/cancel/stop attempts are generated and must reject
without economic mutation; permissionless settle/batch calls remain inert and
accepted.

Economic state is split into:

- `recipient_accounted`;
- `payer_returned`;
- `remaining_custody`;
- `eligible_active_seconds` from the independent oracle.

`payer_returned` is a conceptual terminal allocation of retained value. It
does not claim that the native contract performs a token transfer that is not
present in its implementation.

The principal invariants are:

```text
initial_value
= recipient_accounted + payer_returned + remaining_custody

after each accepted value-moving action:
recipient_accounted
= min(initial_value, saturating_i128(rate * eligible_active_seconds))
```

The verifier also checks non-overlapping paid intervals, end caps, natural-end
terminality, terminal immutability, authorization/reference-acceptance parity,
rejected-action atomicity, pause normalization, stale pause cleanup, and
terminal allocation.

## Deterministic bounded coverage

There is no randomness and no seed. Exploration uses exact immutable state
equality and maximum transition depth `5`.

| Configuration | Rate | Initial value | End | Graph witnesses |
| --- | ---: | ---: | ---: | --- |
| bounded | 10 | 1,000 | 10 | 2, 10, 11 |
| unlimited | 10 | 1,000 | 0 | 2, 100 |
| small balance | 10 | 15 | 1 | 1, 2 |
| u64/i128 extreme | `i128::MAX` | `i128::MAX` | 0 | `u64::MAX` |

The bounded graph has two initial roots:

- clean `Created`;
- persisted legacy `Paused` with `cursor=0`, `paused_at=2`, and `[0,2]`
  already recipient-accounted.

The deterministic development replay checks:

- 30/30 executable lifecycle/economic scenarios;
- 7/7 real multi-stream batch scenarios;
- 28/28 fixed invariant searches with no counterexample within bound;
- 67 fixed states and 686 fixed transitions across four configurations.

The nine required paused regressions remain explicit: late bounded pause,
pause-settle, pause-cancel, pause-settle-cancel, unlimited late settle,
pause-batch, late resume-pause, exact-end pause, and small-balance/high-rate
late pause. Additional cases cover three legacy-paused continuations, stop
before/after end, settle-stop, paused-stop, unauthorized stop, terminal
lifecycle rejection, resumed-interval underpayment sensitivity, and the
u64/i128 extreme witness.

## Real batch model

`BatchWorld` stages an ordered collection of streams and commits only after
the complete call succeeds. It checks:

1. mixed active/paused/terminal streams in forward order;
2. the same streams in reverse order;
3. duplicate IDs (`first amount`, then `0`);
4. missing ID after a valid ID with full rollback;
5. exactly 25 IDs accepted;
6. 26 IDs rejected atomically;
7. empty batch as a no-op.

Output length/order and per-stream conservation are asserted. This is separate
from the per-item `batch_settle` graph transition and prevents a single-stream
alias from being reported as collection-level evidence.

## Negative controls

The paused-defect mutant reproduces the reviewed old behavior: raw pause
accrual, stale cursor, ignored `paused_at` in settle/batch/cancel, stale pause
on terminal paths, and late resume resurrection. All nine repaired paused
expectations must kill it, and reachability must expose I1, I2, I4, I6, and I7.

The independent underpayment mutant accepts `resume` but leaves implementation
accrual paused. The history oracle becomes Active; the next settlement must
expose the missing resumed interval through I6. This prevents an
implementation-derived lifecycle oracle from masking underpayment.

## Replay

From the ContractGraph-QA evidence checkout in PowerShell:

```powershell
$env:PYTHONPATH='C:\path\to\ContractGraph-QA-v1.8.0'
$python='C:\path\to\python.exe'
$target='C:\path\to\StreamPay-Contracts-at-2baa37b'
& $python benchmarks\streampay-exact-settlement-v0.1\verify.py `
  --target-checkout $target
```

Expected development result: exit `0`, `semanticVerdict: PASS`,
`boundedVerdict: UNBOUND`, and `publishable: false`.

After committing both benchmark files:

```powershell
$evidenceCommit = git rev-parse HEAD
& $python benchmarks\streampay-exact-settlement-v0.1\verify.py `
  --target-checkout $target `
  --evidence-commit $evidenceCommit
```

Expected publication result: exit `0`, `boundedVerdict: PASS`, and
`publishable: true`. A different target/evidence SHA, target tree or source
blob, dirty scoped source, wrong core HEAD/tag, or mismatched committed
verifier/README produces `FAIL` and nonzero exit.

## Claim boundary

Even a fully bound `PASS` is exact evidence only for the declared roots,
configurations, witnesses, actions, batch cases, and depth. It is **not** a
production proof or security certification. Native Rust tests at the exact
StreamPay target commit and GitHub CI state remain separate evidence.
