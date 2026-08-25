# StreamPay exact settlement v0.2 — independent second-audit evidence

Append-only supplemental evidence for StreamPay issue #153 / PR #161. It does
not modify or supersede v0.1.

## Exact subject and runtime

- repository: `Streampay-Org/StreamPay-Contracts`
- target commit: `2baa37b533c07790d6aa38ab0a5c0170fcbbb44f`
- target tree: `3eb31ad4643617d37e07ac0ad03412bf7f237aa4`
- changed-file commit-blob SHA-256:
  - `src/lib.rs`: `fb16000550ca2a31036af721c3607d4e71ef2f40fc2994e34a0cf1d5d621e7da`
  - `tests/issue153_paused_regressions.rs`: `96afb4a790032c38c8ef70dead081f96ad3f67c86e521aea9bc087b4f4555e65`
- CGQA: tag `v1.9.0`, commit
  `6ab1f8b79a3211a7139e6f52da6b3fb7a75c0fb9`

The exact Git tree binds the complete target commit. The verifier repeats
content attestation only for the two PR-changed files; it also checks the exact
base/merge-base, diff path set, and all tracked-worktree cleanliness. Untracked
audit artifacts are excluded. The extracted v1.9 release is bound by version,
the imported package path, six critical-file hashes, and a complete regular-file
release-tree fingerprint: 523 files, 7,782,031 bytes, SHA-256
`25ef98993d124175a5b82a367a037ee5d73a2553231cb1526e72216aeb95f65f`.
Only VCS metadata and generated interpreter caches are excluded. A checkout
with `.git` additionally fails closed unless `HEAD` is the declared commit.

## Independent oracle and bounded result

`verify.py` replays attempted actions into a separate lifecycle and computes
the union of eligible active intervals against the immutable absolute
configured end. It does not read the candidate cursor, pause marker, lifecycle
phase, or payout arithmetic. Expected recipient accounting is:

```text
min(initial_balance, saturating_i128(rate * union(active_intervals).seconds))
```

Deterministic result for the exact bindings:

- `45/47` supplemental checks pass;
- `2/47` are expected `TEST_HOST_ONLY_CORE_REJECTS_ZERO_CLOSE_TIME` REDs;
- `0` production-applicable model failures;
- `9/9` required mutants killed by dedicated independent-oracle probes;
- verdict: `HOLD_TEST_HOST_BOUNDARY`;
- two final runs are byte-identical: `30,419` stdout bytes, SHA-256
  `f2ce20ad065483afe606670ea41c4c0ab15c7c56dd01ed9799de6d0ae636c2a2`.

This is a supplemental bounded model, not exhaustive H1–H10 coverage. The
native Rust audit carries broader H1, H7, and H8 matrices. Mutant kills are
dedicated probes; the main scenario set is not claimed to kill every mutant.

The exact native audit source is retained byte-for-byte at
`native/issue153_second_audit.rs` (40,852 bytes, SHA-256
`ec2f8c41b5986e78b9d37d9c654b9628c4a9b063e5ad60303d930597b3c2053f`).
`native/native-regression-receipt.json` binds its replay command and observed
18-test result: 16 pass and two retained H2 test-host REDs.

### H2 boundary counterevidence

Two exact-head representations fail at timestamp zero in the Soroban test
host:

1. pause writes `paused_at=0`, so later settlement accrues a paused window and
   resume rejects;
2. cancel/stop writes terminal `end_time=0`, colliding with the unlimited
   sentinel and allowing a later restart/accrual resurrection.

[Stellar Core's `checkCloseTime` implementation](https://github.com/stellar/stellar-core/blob/master/src/herder/HerderSCPDriver.cpp#L275-L296)
rejects a proposed close time that is not strictly later than the prior ledger
close time. From that source, this audit infers that the exact timestamp-zero
host shapes are not reachable by a deployed contract after genesis. They are
retained as honest test-host / sentinel boundary counterexamples, not deployed
production defects.

### H3 compatibility boundary

The legacy shapes use absolute `start=100`, configured `end=110`, and pauses
at `105`, `110`, and `112`. The first two cannot replay already-accounted
intervals. The last shape (`paid=12`, while only 10 seconds are eligible) is
detectable and terminalizes without further payment, but a cursor repair
cannot claw back a historical transfer. Whether that overpaid shape ever
existed in deployment is unproven.

## Geometry

The verifier computes every row from fresh candidate paths. Operation
acceptance/rejection is an explicit semantic dimension; therefore
pause→cancel/stop versus cancel/stop→pause is intentional torsion, not by itself
a defect.

| Pair | Classification |
| --- | --- |
| settle ↔ cancel | `HISTORY_DIVERGENT` |
| settle ↔ stop | `HISTORY_DIVERGENT` |
| pause ↔ settle | `HISTORY_DIVERGENT` |
| settle ↔ batch alias | `HISTORY_DIVERGENT` |
| pause ↔ cancel | `TORSION_DETECTED` (intentional terminality/acceptance) |
| pause ↔ stop | `TORSION_DETECTED` (intentional terminality/acceptance) |
| pause→resume→settle ↔ settle→pause→resume | `HISTORY_DIVERGENT` |
| settle(A)→batch([A]) ↔ batch([A])→settle(A) | `HISTORY_DIVERGENT` |
| independent batch ID permutation | `CLOSED` after normalization by ID |

## H10 activated out-of-scope watchpoint

The supplemental model and native audit derive the same explicit lifecycle
shape: start at 100, natural-end settle at 110 pays 10, terminal retained
balance is 90, repeated settle pays 0, restart rejects, and archive policy
rejects because balance is nonzero. This activates the archive/retained-balance
watchpoint. It does **not** prove token custody lock, entitlement loss, or TTL
behavior; those remain outside #153.

The generic lifecycle-liveness projection uses conceptual
`terminal-allocated` with `holdsValue=false`. Its PASS therefore does not test
H10; H10 is preserved separately as activated watch evidence.

## v1.9 unified CLI inputs

All files under `inputs/` are manually normalized projections. They are not
raw Soroban receipts and are not independent witnesses. In particular:

- `reachability`, `lifecycle-liveness`, `economic-cardinality`, and
  `execution-trace-check` are exact only over their declared finite/normalized
  inputs;
- `geometry.json` exercises the v1.9 geometry engine for pause/settle; the
  larger nine-row geometry matrix is computed by `verify.py`;
- `witness-blocked.json` is a manual `BLOCKED` status artifact, intentionally
  not a schema-valid `cgqa witness` input; no fabricated independent source is
  passed to the witness engine;
- `remediate.json` is a non-authorizing schema-valid fixture. Forward
  Remediation is `NOT_APPLICABLE` because no production-applicable defect was
  fixed in this audit, and it is not listed as executed evidence;
- debt and orientation are expected to remain HOLD/INDETERMINATE because
  GitHub CI has no jobs (`action_required`) and H2 counterevidence is retained;
- trace integrity is explicitly partial and contains a declared GAP marker.

## Replay

Run from the exact v1.9 checkout/release directory. Running from the v0.1
evidence checkout would put its older package first on `sys.path` and is not a
valid v1.9 replay.

```powershell
$python = 'C:\path\to\python.exe'
$cgqa = 'C:\path\to\ContractGraph-QA-v1.9.0'
$evidence = 'C:\path\to\ContractGraph-QA-evidence'
$target = 'C:\path\to\StreamPay-Contracts-at-2baa37b'
$env:PYTHONPATH = $cgqa
Push-Location $cgqa

& $python -m contractgraph_qa.cli --version
& $python "$evidence\benchmarks\streampay-exact-settlement-v0.2\verify.py" `
  --target-checkout $target --cgqa-root $cgqa

& $python -m contractgraph_qa.cli subject-freeze --input "$evidence\benchmarks\streampay-exact-settlement-v0.2\inputs\subject-freeze.json"
& $python -m contractgraph_qa.cli verification-plan --input "$evidence\benchmarks\streampay-exact-settlement-v0.2\inputs\verification-plan.json"
& $python -m contractgraph_qa.cli geometry --model "$evidence\benchmarks\streampay-exact-settlement-v0.2\inputs\geometry.json"
& $python -m contractgraph_qa.cli ancestry --trace "$evidence\benchmarks\streampay-exact-settlement-v0.2\inputs\ancestry.json"

# Run the remaining inputs with the command/path mapping in CAPABILITY_MATRIX.md.
& $python -m contractgraph_qa.cli durable-verify `
  --root "$evidence\benchmarks\streampay-exact-settlement-v0.2" `
  --manifest "$evidence\benchmarks\streampay-exact-settlement-v0.2\manifest.json"
Pop-Location
```

## Claim boundary

Bounded deterministic evidence is historical evidence for one exact target,
model, runtime, inputs, and bounds. It is not production proof, a security
certification, a substitute for native Rust tests, a token-custody audit, or a
claim that GitHub CI is green.
