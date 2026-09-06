# Independent Verification Brief

## When “rejected” can still lie about the evidence

### Executive summary

ContractGraph-QA independently reproduced the released Attenu observer-envelope
interoperability corpus at its exact published boundary:

- **19/19 cases agreed**;
- five accepting controls and fourteen rejecting controls;
- every required `{reason, seq, node}` matched;
- every declared per-entry evidence state matched;
- the standalone verifier imported neither the Python nor the TypeScript
  reference implementation.

The most important case is not a simple accept-versus-reject check. It catches a
more subtle failure: a system can reject the overall evidence bundle while still
leaving one record with a falsely strong `witness-signed` state.

That distinction matters whenever downstream software uses individual evidence
states to decide whether to retry a payment, release value, resume an agent,
accept a delegation, or close an investigation.

## The defect shape

The new adversarial case is:

`reject_duplicate_subject_defective_second`

It contains:

1. one valid observer envelope for a ledger entry;
2. a second envelope that names the same entry;
3. a deliberately defective signature on that second envelope.

Two implementations can both reject the whole bundle and still disagree on the
meaning of the affected entry:

| Processing order | Bundle verdict | State left on the entry |
|---|---|---|
| **Claim first:** reserve `subject.seq`, then validate the rest | reject | `process-asserted` |
| **Validate first:** discard the defective duplicate before claiming its subject | reject | incorrectly remains `witness-signed` |

The second path creates a **state lie**. The top-level verdict is conservative,
but the record-level evidence still looks stronger than the submitted evidence
supports.

## What the independent run observed

| Observation | Required result at `seq=1` |
|---|---|
| Full row: valid first envelope plus defective duplicate | `envelope_duplicate_subject`; `process-asserted` |
| First valid envelope alone | no envelope failure; `witness-signed` |
| Defective second envelope alone | `envelope_bad_signature`; `process-asserted` |

This three-way discrimination shows why a single overall `PASS` or `FAIL` is not
enough for evidence-bearing systems. The verifier must also preserve the correct
local state after an adversarial sequence.

## Frozen subject and reproducibility

| Subject field | Frozen value |
|---|---|
| Contract / revision | `envelope_vectors_v1` / `envelope_vectors_v1.2` |
| Cases | `19` |
| Vector bytes | `197,346` |
| Vector SHA-256 | `a8be5ff764a86122ca09e94340416b7169531bf5d0cc76a0b1fc87f8272eb16e` |
| Python source | `attenu-io/attenu-guard@8a8d598e2036d6815b50df01b776a13777c1d72b` (`v0.15.0`) |
| PyPI artifact | `attenu-guard==0.15.0` |
| TypeScript source | `attenu-io/attenu-guard-ts@ae055c92ce2f23e476c42b1a742c3babfa543bb2` (`v0.9.0`) |
| Verifier-core SHA-256 | `e814afb84f7e9ecaff4183a3a685f249ca6065309e293e4a224ec9afbba64a8d` |
| Generated-report SHA-256 | `4328c5a38e647b601b73fa5ff4a8b8f9f5375296318ba1a5d440372c9edbbd6b` |
| Immutable merged proof | `3747cd2518ecee4051246c08ef24114f5fea432e` |

Before scoring, hosted CI required byte identity among:

- the pinned Python-repository fixture;
- the copy shipped in the exact PyPI wheel;
- the pinned TypeScript-repository fixture.

The npm package is not claimed as a fixture source because it does not ship the
vector.

The verifier core was not changed for the nineteenth case. It is byte-identical
to the core used for the earlier eighteen-case run. The new external vector was
therefore evaluated without retuning the verification rules to fit it.

## Why this matters commercially

A payment, wallet, ledger, agent, or smart-contract workflow rarely consumes one
binary verdict in isolation. It consumes a sequence of local facts:

```text
request authorized
→ attempt dispatched
→ outcome ambiguous
→ external evidence arrives
→ evidence state classified
→ retry, release, stop, or hold
```

If any local state remains stronger than the surviving evidence permits, a later
component may make a dangerous but internally “valid” decision.

Examples include:

- retrying after a record was incorrectly treated as unwitnessed or resolved;
- releasing value because one entry still appears independently confirmed;
- resuming an agent after a conflicting observer record was filtered out;
- accepting a delegation path whose local authority state no longer matches the
  full evidence set;
- closing reconciliation because the overall bundle rejected, while a consumer
  continued reading stale per-entry states.

The practical lesson is:

> A safe verifier must preserve both the correct global verdict and the correct
> local evidence state after every permitted ordering, duplicate, retry, and
> malformed-input path.

## How ContractGraph-QA applies the pattern

For a bounded client scenario, the same method becomes:

1. Name one high-risk decision boundary.
2. Define the evidence states a downstream component is allowed to consume.
3. Separate global verdicts from record-level state transitions.
4. Build positive controls and one-change adversarial vectors.
5. Pin the exact subject, inputs, versions, hashes, and expected positions.
6. Run a standalone verifier and preserve a deterministic report.
7. Minimize any disagreement to the smallest sequence that changes the decision.
8. Retest the same path after the repair without broadening the original claim.

A suitable first boundary is often:

> After dispatch returns an ambiguous result, which evidence is authoritative
> before another monetary or irreversible action is permitted?

See the [Recovery Design Partner Lab](../../PILOT.md) for the bounded engagement
workflow.

## What this proof does not establish

This result is intentionally narrow. It does **not** prove:

- that every possible observer-envelope defect is covered;
- that a live deployment cannot bypass its verifier;
- that all expected events were captured;
- that an absent envelope should have existed;
- witness freshness, independence, or non-equivocation;
- integrity of a top-level envelope array removed outside the anchored ledger;
- general correctness of either upstream implementation;
- A2A adoption, security certification, or endorsement.

It establishes agreement with one named, frozen nineteen-case corpus and the
specific state discrimination exercised there.

## Evidence

- [Independent proof registry](../../PROOFS.md)
- [Proof README](../../proofs/attenu-envelope-v1.2-independent/README.md)
- [Machine-readable report](../../proofs/attenu-envelope-v1.2-independent/report.json)
- [Pinned runner](../../proofs/attenu-envelope-v1.2-independent/run_pinned_proof.py)
- [Immutable proof tree](https://github.com/safal207/ContractGraph-QA/tree/3747cd2518ecee4051246c08ef24114f5fea432e/proofs/attenu-envelope-v1.2-independent)
- [Merged proof PR #162](https://github.com/safal207/ContractGraph-QA/pull/162)
- [Upstream release notice](https://github.com/a2aproject/A2A/issues/1575#issuecomment-5557848990)
- [Independent 19/19 submission](https://github.com/a2aproject/A2A/issues/1575#issuecomment-5559145070)
