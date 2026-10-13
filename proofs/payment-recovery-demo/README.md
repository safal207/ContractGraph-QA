# A timeout is not permission to retry

A bounded, offline ContractGraph-QA demonstration. The website animates recorded Python results; it does not run or control a live payment agent.

## Exact subject

Baseline repository: `safal207/ContractGraph-QA`.
Baseline commit: `776a43cd554fd25c9f9a4a258c7818719f81cac3`.
Evaluator: `contractgraph_qa/payment_recovery.py`, blob `90999a956df3962112d6363df0e55c5195f6cc21`.
The runner checks the evaluator and all four seed files against their exact Git blob hashes before importing the evaluator. The repository's original implementation is not modified.

## Reproduce

Check out the commit containing this directory. With Python 3.11 or later, from the repository root:

```sh
python proofs/payment-recovery-demo/reproduce.py --check
```

No pip packages, API keys, payment provider, or network are required. The runner forbids Python socket creation. `--check` recomputes the evidence and compares parsed JSON and the candidate patch to the committed artifacts. Without `--check`, it writes a fresh `payment-recovery-demo-results/` directory.

## Observed local results

| Witness | Result | Meaning |
|---|---|---|
| Four upstream seeds | 4/4 expected verdicts match | Two PASS, two expected FAIL; not a safety score |
| Baseline witness | 47 tests: 46 passed, one expected failure | Known post-commit submit gap remains visible |
| Isolated candidate | 50 tests passed | Tested same-operation submit/new_payment gap rejected |
| Seed parity | Four complete native outputs unchanged | Candidate does not change these four seed results |

The witness includes a 32-case outcome/order/action containment matrix, invalid inputs, repeated immutable replay, serialization and consistent identity renaming, and a negative control that removes reconciliation. It is a refactored standard-library witness for the prior local package, not the full upstream native suite.

## The revealing case

`authorize -> submit -> ambiguous -> reconcile(committed) -> submit(same operation)` receives PASS from the pinned baseline. The explicit `retry` label after commit is already rejected. The candidate adds APR-010 for same-operation `submit` / `new_payment` after recorded committed reconciliation. It exists only in a temporary directory when the runner executes. `candidate.patch` is an unapplied review artifact, not a deployed fix.

Unknown followed by stop is different: its native result is FAIL with noncritical APR-009. Ambiguity is contained, but the outcome remains unresolved. No native HOLD result is invented.

`evidence.json` contains nine exact scenarios and a declared projection of native outputs: status, criticalFailure, invariants and violations. Candidate output is included where it differs. Scenario hashes are over compact sorted-key JSON; source hashes identify bytes, not evidence authenticity.

## Claim ceiling and debt

Synthetic ordered traces, no live provider, no second-charge demonstration, no independent audit, no source-completeness or event-authenticity proof. The patch does not resolve contradictory reconciliation history, evidence authority, wall-clock finality, storage/restart durability, operation identity semantics or distributed enforcement. PASS only describes the supplied trace under the checked implementation.

Local execution is recorded here; GitHub Actions results belong to their specific run and must be inspected separately. No model leaderboard, model-specific performance or OpenAI endorsement is claimed. AI assistance was used for test construction, bounded analysis and presentation, not as an external witness.

Publication decision: PROMOTE the bounded demonstration; DEFER any shipped safety guarantee and engine patch. Keep this change in a draft PR; no merge is requested. The website can be published independently in RESONANCE with links to this exact evidence commit.
