# Replay Recovery & Idempotence v0.1

This benchmark is a replay-only adapter for ambiguous external actions such as broker order placement, payouts, or other monetary side effects where a request timed out and the caller must decide whether a retry is safe.

It deliberately does **not** submit, resubmit, cancel, or otherwise execute any action.

## Reused ContractGraph-QA primitives

The adapter is intentionally thin:

- `economic_cardinality.py` deduplicates repeated observations of the same `occurrenceId` and detects more than one distinct applied occurrence for the same `(actionId, effectKey)` pair.
- `payment_recovery.py` checks retry identity continuity and idempotency continuity after a ZERO reconciliation.

`path_replay.py` is not used here because capability-path reachability is a different proof question from economic-effect cardinality.

## Cardinality and verdicts

| Evidence state | Cardinality | Verdict |
| --- | --- | --- |
| No complete evidence and fewer than two distinct confirmed occurrences | `UNKNOWN` | `HOLD_UNRESOLVED` |
| Complete evidence sources disagree, or a partial observation contradicts a complete source | `UNKNOWN` | `HOLD_EVIDENCE_CONFLICT` |
| Complete evidence proves no occurrence and retry identity is continuous | `ZERO` | `RETRY_ALLOWED` |
| Complete evidence proves no occurrence but retry identity/idempotency changes | `ZERO` | `BLOCK_RETRY_IDENTITY` |
| Complete evidence proves exactly one occurrence | `ONE` | `BLOCK_ALREADY_APPLIED` |
| Evidence proves at least two distinct occurrences | `MULTIPLE` | `BLOCK_DUPLICATE_EFFECT` |

`RETRY_ALLOWED` is a policy verdict only. The evaluator always emits `executionAuthorized=false`, `productionAuthorization=false`, and `financialAuthorization=false`.

## Claim boundary

The result is exact only over the declared normalized evidence. Whether a source is truthful and whether a source marked `complete=true` is actually complete remain external assumptions.

The seed case `case-timeout-reconcile-zero.json` models one bounded path:

1. the original request times out and does not prove an execution result;
2. a complete replay/reconciliation surface reports zero matching occurrences;
3. the proposed retry preserves logical-operation and idempotency identity;
4. the evaluator returns `ZERO / RETRY_ALLOWED` without executing the retry.

Run the focused regression with:

```bash
python -m unittest tools.tests.test_replay_recovery -v
```
