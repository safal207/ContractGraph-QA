# StreamPay exact settlement v0.1

External, bounded ContractGraph-QA lifecycle oracle for
[StreamPay-Contracts issue #153](https://github.com/Streampay-Org/StreamPay-Contracts/issues/153).

This benchmark is deliberately **not** imported into the StreamPay production
contract. It is verification evidence for the repair; native Rust regression
tests in the target repository remain the source-to-implementation binding.

## Scope

The finite model covers the lifecycle:

```text
Created -> Active -> Cancelled
                  -> Ended
```

and the timestamp witnesses `T_before = end_time - 1`,
`T_exact = end_time`, and `T_after = end_time + 1`.

It checks:

- I1 — once-only settlement;
- I2 — accrual never passes the configured end time for a bounded stream;
- I3 — `initial_balance = cumulative_settled + remaining_balance`;
- I4 — terminal settlement is immutable under repeated settle/cancel calls;
- I5 — identical state plus ledger timestamp gives the same outcome;
- I6 — only the payer may cancel.

The negative-control model keeps the pre-fix `now` semantics. It must expose
the end-time-cap and terminal-state violations; this proves the oracle is able
to distinguish the repaired semantics from the original defect.

## Run

From the ContractGraph-QA repository root:

```bash
PYTHONPATH=. python benchmarks/streampay-exact-settlement-v0.1/verify.py
```

Expected result: `"boundedVerdict": "PASS"`. The reachability outcome
`not_found_within_bound` is bounded evidence, not a security certification.

## Boundaries

| Witness | Settle | Cancel |
| --- | --- | --- |
| Before end | Pays only through the current witness and stays active. | Uses the cancellation witness as the terminal boundary. |
| At end | Pays the final allowed interval and becomes `Ended`. | Matches the natural end result. |
| After end | Caps accrual at the configured end and becomes `Ended`. | Natural end wins; no value accrues after end. |
| Repeat | No further value moves. | The terminal transition is rejected/no-op for value. |

## Limits

The model is exact only for the declared finite graph, rates, balance, and
three temporal witnesses. It does not claim exhaustive verification of all
StreamPay functionality.
