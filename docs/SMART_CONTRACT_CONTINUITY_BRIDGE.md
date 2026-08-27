# Smart Contract Continuity Bridge v0.1

The bridge converts reviewed ContractGraph-QA smart-contract evidence into the
existing LTP request/outcome continuity input. It does not contain or invoke a
second continuity verifier.

```text
logical intent / attempt
  -> RPC receipt + block/head witness
  -> reviewed EVM receipt/event adapter
  -> reviewed downstream observations
  -> CGQA deterministic LTP envelope export
  -> normative LTP v0.1 verifier
  -> CGQA durable evidence manifest
```

## Repository ownership

| Boundary | ContractGraph-QA | LTP |
|---|---|---|
| Intent/evidence validation | Owns | Does not infer |
| EVM receipt/event mapping | Owns reviewed adapter boundary | Treats outcome content as supplied evidence |
| Request/outcome envelopes | Produces pinned v0.1 shapes | Owns normative schemas |
| Continuity semantics | Does not compute | Owns `verifyRequestOutcomeContinuity()` |
| Exit codes | CGQA product codes (`0`, `10`, `70`) | Normative continuity codes (`0`, `1`, `2`) |
| Finality/reorg | Metadata and non-claim only | Not represented in v0.1 terminal statuses |

The bridge report deliberately has no `overall_status` or continuity verdict.
`BRIDGE_READY` means only that the projection was produced without an unresolved
root mapping gap.

## Commands

`--intent` is repeatable so retry attempts retain one logical `requestId` and
distinct `attemptId` values.

```bash
cgqa continuity-export \
  --intent intent-attempt-1.json \
  --intent intent-attempt-2.json \
  --capture rpc-capture-attempt-1.json \
  --capture rpc-capture-attempt-2.json \
  --receipt-trace receipt-trace-attempt-2.json \
  --observations observations.json \
  --as-of 2026-08-27T10:10:00Z \
  --out continuity-input.json \
  --bridge-report-out bridge-report.json

pnpm -w ltp:continuity -- \
  continuity-input.json \
  --out continuity-report.json
```

Outputs are deterministic sorted-key JSON with a final newline. Existing output
files require `--force`. Input/output identity is checked across direct paths,
symbolic links, and hard links.

## Smart Contract Intent v0.1

Profile: `cgqa-smart-contract-intent-v0.1`.

`requestId` is a logical business action and is rejected when it has the shape
of an EVM transaction hash. `attemptId` is one dispatch attempt. Raw args and
sensitive payloads are not accepted; the contract carries `argsDigest` and
`payloadDigest` only. Chain, address, selector, function, sender, nonce, retry,
parent, and explicit-offset timestamps are required and fail closed.

## External Observation v0.1

Profile: `cgqa-external-observation-v0.1`.

Supported source kinds are:

- `CONTRACT_RECEIPT`
- `CONTRACT_EVENT`
- `INDEXER_RECORD`
- `BACKEND_STATE`
- `API_RESPONSE`

An observation is not automatically an LTP record. A reviewer must provide an
explicit `ltpProjection` as either `REQUEST` or `OUTCOME`. This prevents the
adapter from inventing an expected downstream operation or a terminal result.

Arbitrary observation `metadata` participates in the input digest but is never
copied into public bridge evidence. The output contains a small allow-listed
projection: source kind, observation identity, subject digest, parent identity,
and a digest of the claim boundary.

## Root on-chain outcome gate

A root smart-contract outcome is emitted only when all load-bearing bindings
agree:

1. logical `requestId`, `traceId`, and `attemptId` match the reviewed intent;
2. the `CONTRACT_RECEIPT` observation contains a complete reviewed `evmBinding`;
3. chain, contract, selector, function, args digest, sender, nonce, and payload
   digest match the intent;
4. observation `resultDigest` binds the exact RPC capture;
5. capture transaction/chain and adapter transaction/chain agree;
6. adapter `receiptSha256` matches the captured receipt bytes;
7. selected event IDs resolve to exact, non-removed receipt logs from the
   declared contract;
8. reviewed ExecutionTrace semantics bind the logical action/function and show
   an applied effect or committed state transition.

Mapping rules:

| Evidence | LTP terminal status |
|---|---|
| Successful receipt + reviewed mapped event | `COMPLETED` |
| Reverted receipt + explicit reviewed binding | `FAILED` |
| Successful explicit cancellation event | `CANCELLED` |
| Recorded pre-dispatch policy refusal | `REJECTED` |
| Separately recorded timeout fact | `TIMED_OUT` |
| Receipt not observed or RPC timeout | no outcome |
| Deadline elapsed without a recorded outcome | no invented timeout; LTP may find `BROKEN_MISSING_OUTCOME` |
| API/indexer success for root on-chain request | rejected mapping |

The current RPC capture does not independently decode calldata, nonce, or sender.
Those fields therefore remain reviewed binding declarations in v0.1; the bridge
report states that limitation explicitly.

## Downstream continuity

Receipt/event, indexer, backend, and API work are separate logical
requests/outcomes. A receipt can be continuous while a later indexer request is
`BROKEN_MISSING_OUTCOME`. No layer is hidden inside one aggregate result digest.

Example:

```text
releasePayment request/outcome
  -> indexer request/outcome
  -> backend reconciliation request/outcome
  -> API exposure request/outcome
```

## Finding diagnosis

| LTP finding | Bridge/operator check |
|---|---|
| `BROKEN_ORPHAN_RESPONSE` | Find the missing reviewed request envelope; do not fabricate it post hoc. |
| `BROKEN_MISSING_OUTCOME` | Check the operative deadline and the observation channel for that exact downstream request. |
| `BROKEN_CONFLICTING_OUTCOMES` | Reconcile multiple canonical terminal observations and economic cardinality. |
| `BROKEN_TIME_REVERSAL` | Recheck explicit-offset clocks, block time mapping, and parent/child order. |
| `BROKEN_PARENT_GAP` | Supply or correct the reviewed parent logical request. |
| `BROKEN_RETRY_GAP` | Restore exact earlier attempt lineage under the same logical request. |
| `BROKEN_ATTEMPT_GAP` | Bind the outcome to an observed attempt; do not substitute the tx hash for `requestId`. |
| `BROKEN_TRACE_MISMATCH` | Reconcile lifecycle trace identity across request and outcome. |
| `BROKEN_REPLAY_GAP` | Restore the canonical outcome referenced by a replay. |
| `REPLAY_DETECTED` | Confirm that the replay does not create a second economic effect. |

## Threat model and non-claims

The adapter rejects unknown critical fields, ambiguous JSON keys, unsafe output
aliases, binding mismatches, fabricated API-as-chain completion, and conflicting
same-transaction capture/trace records. It does not establish authorization,
complete observation history, RPC independence, canonical chain truth, finality,
absence of reorg, or universal exactly-once execution.

The LTP schemas are not silently copied. The external validation contract pins
the LTP repository commit/tree and four schema SHA-256 values in
`contractgraph_qa/schemas/ltp_continuity_external_contract_v0_1.json`.

## Adding adapters

An EVM adapter must produce the existing reviewed
`evm-receipt-adapter-result-v0.1` and `ExecutionTrace` shapes. A future Soroban
adapter must produce equivalent reviewed logical bindings without weakening the
request/attempt distinction or changing the LTP verifier. Soroban is phase 2.

## v0.2 boundary

Repeated captures, receipt disappearance, block-hash replacement, transaction
replacement, confirmation policy, multi-RPC corroboration, and reorg/finality
semantics are deliberately deferred. See
`docs/issues/SMART_CONTRACT_FINALITY_CONTINUITY_V0_2.md`.
