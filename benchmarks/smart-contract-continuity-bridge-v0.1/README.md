# Smart Contract Continuity Bridge v0.1 benchmark

This is an offline synthetic EVM escrow lifecycle:

```text
deposit
  -> delivery accepted
  -> releasePayment attempt 1 (receipt not observed)
  -> retry attempt 2
  -> one successful receipt + PaymentReleased event
  -> indexer update
  -> backend released state
  -> API released state
```

No live RPC endpoint, credentials, customer data, or real-value transaction is
used.

## Frozen source subjects

- ContractGraph-QA source main: `007c1fa68dac5b19b73e6ab1b4f606727e620ed7`
- ContractGraph-QA source tree: `4abd38371fdedc907825b17f27d6ccbd3ee2519c`
- ContractGraph-QA publication base after main moved:
  `ff617b3cbbf29ad6a0e5bdee5760e44f30d77ab7`
- ContractGraph-QA publication-base tree:
  `bd9bf9f2243c3251c1c0040276c1c85c299f0aee`
- LTP source main: `08734d248c24dfb2ee8e4f4a3f689887ead0ea24`
- LTP source tree: `5eb684d990701fa959f0b2a87125ebd765df70cd`

Both source worktrees were clean before the local bridge candidate was created.
The later ContractGraph-QA movement changed only
`docs/LANGGRAPH_RECOVERY_SAFETY.md`; the candidate was rebased and the complete
CGQA suite rerun before the publication branch was updated.

## Rebuild

```bash
cgqa continuity-export \
  --intent benchmarks/smart-contract-continuity-bridge-v0.1/intent-attempt-1.json \
  --intent benchmarks/smart-contract-continuity-bridge-v0.1/intent-attempt-2.json \
  --capture benchmarks/smart-contract-continuity-bridge-v0.1/rpc-capture-attempt-1.json \
  --capture benchmarks/smart-contract-continuity-bridge-v0.1/rpc-capture-attempt-2.json \
  --receipt-trace benchmarks/smart-contract-continuity-bridge-v0.1/receipt-trace-attempt-2.json \
  --observations benchmarks/smart-contract-continuity-bridge-v0.1/observations-pass.json \
  --as-of 2026-08-27T10:10:00Z \
  --out benchmarks/smart-contract-continuity-bridge-v0.1/generated-pass-continuity-input.json \
  --bridge-report-out benchmarks/smart-contract-continuity-bridge-v0.1/generated-pass-bridge-report.json \
  --force

python benchmarks/smart-contract-continuity-bridge-v0.1/build_ltp_mutants.py
```

Then run each `cases/*.json` file through the normative LTP command. Expected
results are pinned in `cases/fixture-matrix.json`.

## Verified matrix

| Case | LTP exit | Status / finding |
|---|---:|---|
| one request / one completed outcome | 0 | `CONTINUOUS` |
| timeout retry / one canonical outcome | 0 | `CONTINUOUS` |
| expired request / no outcome | 2 | `BROKEN_MISSING_OUTCOME` |
| outcome without request | 2 | `BROKEN_ORPHAN_RESPONSE` |
| incompatible terminal outcomes | 2 | `BROKEN_CONFLICTING_OUTCOMES` |
| retry parent missing | 2 | `BROKEN_RETRY_GAP` |
| event/indexer trace mismatch | 2 | `BROKEN_TRACE_MISMATCH` |
| receipt present / indexer outcome absent | 2 | `BROKEN_MISSING_OUTCOME` |
| both transaction attempts paid | 2 | `BROKEN_CONFLICTING_OUTCOMES` |
| duplicate exact delivery | 0 | `REPLAY_DETECTED`, one canonical outcome |
| attempt reused by two logical requests | 1 | semantic input rejection |
| extra input property | 1 | JSON Schema rejection |

Bridge-level negative controls additionally reject transaction-hash
`requestId`, mismatched chain/address/args binding, API-as-chain completion,
unknown critical fields, duplicate JSON keys, and output/input aliases.

## Deterministic replay

- generated LTP input file SHA-256:
  `a738785a60166e71ac4f8e7111b1384a87c18925715a5bcfe5eb832878cf3f74`
- generated LTP report file SHA-256:
  `48744831e209647e155b82e836f7e9521a6bb513a82c2081f93fb93b409d75c8`
- a second independent LTP CLI run produced byte-identical report output.

These are byte identities, not security, authorization, or finality claims.

## Evidence index

- `exact-subject.json` freezes both source commits/trees and the collection
  window.
- `schemas-and-hashes.json` pins the canonical CGQA schema paths and the
  external LTP schema contract.
- `VALIDATION.md` records RED/GREEN chronology, commands, exit codes, and claim
  boundaries.
- `CAPABILITY_MATRIX.md` classifies every repository-required verification
  capability.
- `durable-manifest.json` hashes the 39 load-bearing benchmark artifacts;
  `durable-verification.json` records the successful reopen.

From the ContractGraph-QA repository root:

```bash
python -m contractgraph_qa.cli durable-verify \
  --root benchmarks/smart-contract-continuity-bridge-v0.1 \
  --manifest benchmarks/smart-contract-continuity-bridge-v0.1/durable-manifest.json
```

The durable check proves local byte integrity and reopenability. It does not
provide an independent authenticity or blockchain-finality anchor.
