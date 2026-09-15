# CrewAI identity / authority adapter v0.1

**Target:** real `crewai==1.15.21` synchronous `ToolUsage._use` retry path.

This proof binds the framework-neutral identity/authority contract from PR #173 to the same CrewAI retry surface independently recorded by `mstevens843/crashpoint` and admitted in PR #171.

The experiment is deliberately A/B.

## A — baseline

The tool performs one local external effect and then raises before returning success.

CrewAI's built-in synchronous retry re-enters the tool. With no reconciliation guard, the second invocation performs the effect again.

Expected result:

- tool entries: `2`;
- external effects: `2`;
- verdict: `DUPLICATED`.

## B — identity / authority guard

The logical action has one stable `action_id`. A one-use permit authorizes the first dispatch and is consumed. The external effect produces a durable receipt in local SQLite, which is outside CrewAI runtime state.

The first invocation again commits the effect and then raises before returning success.

When CrewAI re-enters the tool, the guard performs read-back before any new dispatch. A matching confirmed receipt for the same `action_id + target + intent_hash` yields `return_prior`; the consumed permit is not reused and a second effect is not produced.

Expected result:

- tool entries: `2`;
- guard decisions: `dispatch -> return_prior`;
- external effects: `1`;
- consumed permit remains consumed;
- verdict: `RECONCILED_NO_DUPLICATE`.

## Frozen runtime

- CrewAI: `1.15.21`
- issue: [#174](https://github.com/safal207/ContractGraph-QA/issues/174)
- predecessor external admission: [#171](https://github.com/safal207/ContractGraph-QA/pull/171)
- predecessor framework-neutral contract: [#173](https://github.com/safal207/ContractGraph-QA/pull/173)
- upstream source used for interface comparison: `mstevens843/crashpoint@606893ebb353df5dab3ac68738051eb5fbb7286e`
- upstream CrewAI runtime-harness blob: `c13b2c162ef6d24de4da6632f72df351d38c9088`

Crashpoint is MIT-licensed. This proof does not copy its experiment implementation; it uses the same public CrewAI surface and failure boundary to make the A/B comparison inspectable.

## Reproduce

```bash
python -m pip install 'crewai==1.15.21'
python proofs/crewai-identity-authority-adapter-v0.1/run_experiment.py \
  --write-report /tmp/crewai-identity-authority-report.json

diff -u \
  proofs/crewai-identity-authority-adapter-v0.1/report.json \
  /tmp/crewai-identity-authority-report.json
```

The hosted CI workflow runs exactly this pinned runtime and requires byte-for-byte equality with the committed report.

## Claim ceiling

A PASS establishes only that, in this pinned same-process synchronous CrewAI 1.15.21 retry path:

1. the baseline reproduces two external effects after an after-effect/pre-return failure; and
2. the tested ContractGraph-QA reconciliation guard lets CrewAI re-enter the tool while suppressing the second external effect by returning the prior confirmed result.

It does **not** establish:

- a CrewAI framework fix;
- process-crash or fresh-worker recovery safety;
- checkpoint/resume safety;
- distributed authorization durability;
- a separate-host external ledger;
- global exactly-once execution.

The core invariant remains:

> Stable identity tells recovery **which action** it is reconciling. It is not fresh authority to execute that action again.
