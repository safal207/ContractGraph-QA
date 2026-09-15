# Independent verification proofs

This registry exposes the repository's reproducible third-party interoperability
checks as first-class evidence artifacts.

A green result here means **agreement with one named, frozen corpus at the
pinned boundary**. It does not mean that the upstream implementation, a live
deployment, or every untested path is secure, complete, certified, or endorsed.

## LangGraph b1 identity / authority adapter v0.1

**Result: PASS — baseline 2 effects, guarded 1 effect across fresh-process recovery.**
Hosted CI installed exact `langgraph==1.2.11` and
`langgraph-checkpoint-sqlite==3.1.1`, crashed the subject process at the
deterministic `b1` boundary after the external effect but before pending writes
persisted, then recovered from the same SQLite checkpoint in a fresh process.

In the baseline, recovery re-entered the node and produced a second external
effect. In the guarded arm, recovery still re-entered the node with the same
stable `action_id`, but external receipt reconciliation produced `return_prior`;
the one-use permit remained consumed exactly once and the external effect count
stayed one.

The first hosted run acquired the observed A/B result without a committed
expected report. The result was then frozen as `report.json`; a second hosted run
regenerated the report and matched it byte-for-byte.

This is an application-side runtime adapter result, not a LangGraph framework
fix. It is scoped to the pinned local SQLite `b1` recovery boundary and does not
claim reproduction of the LangGraph Cloud ~180-second sweeper.

- [Proof README](proofs/langgraph-b1-identity-authority-v0.1/README.md)
- [Machine-readable A/B report](proofs/langgraph-b1-identity-authority-v0.1/report.json)
- [Executable runtime experiment](proofs/langgraph-b1-identity-authority-v0.1/run_ab.py)
- [Experiment issue #176](https://github.com/safal207/ContractGraph-QA/issues/176)
- [Acquisition/freeze issue #177](https://github.com/safal207/ContractGraph-QA/issues/177)

## CrewAI identity / authority adapter v0.1

**Result: PASS — baseline 2 effects, guarded 1 effect with two tool entries.**
Hosted CI installed exact `crewai==1.15.21` and ran an A/B experiment on the
same synchronous retry surface used by the admitted external Crashpoint record.

In the baseline, the first invocation commits an external effect and raises
before returning; CrewAI re-enters the tool and the unguarded second invocation
commits a second effect. In the guarded arm, the first invocation consumes a
one-use permit and commits one effect; on the same CrewAI retry, a matching
external receipt for the stable `action_id + target + intent_hash` produces
`return_prior`, so the runtime still enters the tool twice but the external
effect count remains one.

This is a runtime adapter result, not a CrewAI framework fix. It is scoped to
the pinned same-process synchronous retry path and a local SQLite receipt/permit
store outside CrewAI runtime state.

- [Proof README](proofs/crewai-identity-authority-adapter-v0.1/README.md)
- [Machine-readable A/B report](proofs/crewai-identity-authority-adapter-v0.1/report.json)
- [Executable runtime experiment](proofs/crewai-identity-authority-adapter-v0.1/run_experiment.py)
- [Experiment issue #174](https://github.com/safal207/ContractGraph-QA/issues/174)

## Identity / authority boundary v0.1

**Result: 6/6 PASS; 2/2 unsafe mutants detected.** A framework-neutral executable
contract now separates stable logical action identity from fresh execution
authority. Recovery preserves the same `action_id`, but a consumed permit is
never reusable and `UNKNOWN` read-back fails closed rather than redispatching.
Only a proved `NOT_EXECUTED` result may proceed to an explicit new authorization
and a newly issued one-use permit.

- [Proof README](proofs/identity-authority-boundary-v0.1/README.md)
- [Machine-readable report](proofs/identity-authority-boundary-v0.1/report.json)
- [Executable harness](proofs/identity-authority-boundary-v0.1/harness.py)
- [Boundary issue #172](https://github.com/safal207/ContractGraph-QA/issues/172)

## External evidence admission: CrewAI retry duplication v0.1

**Status: ADMITTED (BOUNDED), 90/90 receipt agreement.** ContractGraph-QA
independently downloaded the public `mstevens843/crashpoint` publication
artifact, matched its published file hashes, and recomputed the raw 90-trial
CrewAI retry receipts without relying on the producer's aggregate summary.

The admitted result is deliberately narrower than an independent rerun. It
establishes that the frozen evidence bytes support the recorded same-process
CrewAI 1.15.21 claim: when an unguarded external effect commits and the tool
then raises before returning, the built-in synchronous `ToolUsage._use` retry
can re-enter the tool and produce a second external effect for the same logical
action. It does **not** establish process-crash, fresh-worker, checkpoint/resume,
real-provider, or idempotency-guard behavior.

- [Admission README](proofs/crewai-retry-external-admission-v0.1/README.md)
- [Machine-readable admission](proofs/crewai-retry-external-admission-v0.1/admission.json)
- [Independent recomputation report](proofs/crewai-retry-external-admission-v0.1/report.json)
- [Pinned verifier](proofs/crewai-retry-external-admission-v0.1/verify_admission.py)
- [Frozen external source](https://github.com/mstevens843/crashpoint/blob/606893ebb353df5dab3ac68738051eb5fbb7286e/evidence/crewai_retry.json)

## Latest proof: Attenu observer-envelope v1.2

**Result: 19/19 AGREE** — five accepting controls and fourteen rejecting
controls. Every required `{reason, seq, node}` and every declared per-entry
state was reproduced by a standalone verifier that imports neither the Python
nor the TypeScript reference implementation.

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
| Immutable merge | `3747cd2518ecee4051246c08ef24114f5fea432e` |

Before scoring, hosted CI required byte identity among the Python-repository
fixture, the exact PyPI wheel copy, and the TypeScript-repository fixture. The
npm tarball is not claimed as a raw-vector source because it does not ship the
vector.

### Row 19: the state-lie discriminator

`reject_duplicate_subject_defective_second` distinguishes two algorithms that
both reject the bundle but do **not** report the same evidence state:

| Observation | Required result at `seq=1` |
|---|---|
| Full row: valid first envelope plus defective duplicate | `envelope_duplicate_subject`; `process-asserted` |
| First valid envelope alone | no envelope failure; `witness-signed` |
| Defective second envelope alone | `envelope_bad_signature`; `process-asserted` |

The important property is claim-first ordering: once a second envelope names an
already claimed entry, later validation failure cannot make that duplicate
vanish while leaving the earlier, stronger `witness-signed` state in place.

The envelope-verification core was not retuned for row 19. It is byte-identical
to the verifier used for the earlier v1.1 18/18 proof.

### Evidence links

- [Client-facing proof brief](docs/client-proof/INDEPENDENT_VERIFICATION_BRIEF.md)
- [Proof README](proofs/attenu-envelope-v1.2-independent/README.md)
- [Machine-readable report](proofs/attenu-envelope-v1.2-independent/report.json)
- [Pinned runner](proofs/attenu-envelope-v1.2-independent/run_pinned_proof.py)
- [Immutable proof tree](https://github.com/safal207/ContractGraph-QA/tree/3747cd2518ecee4051246c08ef24114f5fea432e/proofs/attenu-envelope-v1.2-independent)
- [Merged review PR #162](https://github.com/safal207/ContractGraph-QA/pull/162)
- [Upstream row-19 release notice](https://github.com/a2aproject/A2A/issues/1575#issuecomment-5557848990)
- [Independent 19/19 submission](https://github.com/a2aproject/A2A/issues/1575#issuecomment-5559145070)
- [Unmasked source-pin correction](https://github.com/a2aproject/A2A/issues/1575#issuecomment-5559148305)

## Proof matrix

| Frozen subject | Result | Main distinction | Artifact |
|---|---:|---|---|
| LangGraph b1 identity / authority adapter `v0.1` | **PASS: 2 effects -> 1 effect** | Fresh-process recovery re-enters node; external receipt reconciliation suppresses the second effect | [Open](proofs/langgraph-b1-identity-authority-v0.1/README.md) |
| CrewAI identity / authority adapter `v0.1` | **PASS: 2 effects -> 1 effect** | Real CrewAI 1.15.21 retry still re-enters tool twice; receipt reconciliation suppresses second external effect | [Open](proofs/crewai-identity-authority-adapter-v0.1/README.md) |
| Identity / authority boundary `v0.1` | **6/6 PASS; 2/2 mutants** | Stable identity survives recovery while execution authority does not | [Open](proofs/identity-authority-boundary-v0.1/README.md) |
| CrewAI 1.15.21 recorded retry evidence | **ADMITTED / 90/90 receipt agreement** | Third-party evidence admission; same-process retry duplication; no independent rerun | [Open](proofs/crewai-retry-external-admission-v0.1/README.md) |
| Attenu observer-envelope `v1.2` | **19/19 AGREE** | Claim-first duplicate-subject handling and exact evidence-state mapping | [Open](proofs/attenu-envelope-v1.2-independent/README.md) |
| Attenu observer-envelope `v1.1` | **18/18 AGREE** | Baseline envelope verdicts, positions, failure vocabulary, and states | [Open](proofs/attenu-envelope-v1.1-independent/README.md) |
| Attenu bundle vectors `v1.2` | **17/17 conformant** | Released-corpus score plus old-versus-fixed release discrimination | [Open](proofs/attenu-guard-v0.12.1-independent/README.md) |
| Attenu bundle vectors `v1.1` | **12/12 conformant** | Exact mandatory failure positions on the additive twelve-case corpus | [Open](proofs/attenu-guard-v0.12.0-independent/README.md) |
| Attenu bundle vectors `v1` | **8/8 conformant** | First standalone bundle-verifier reproduction | [Open](proofs/attenu-guard-v0.11.0-independent/README.md) |

## How to review a proof

For each entry, inspect four layers separately:

1. **Subject identity** — repository commits, releases, artifact hashes, vector
   size, and vector digest.
2. **Independence boundary** — which upstream runtime or verifier code is not
   imported, and which shared assumptions remain.
3. **Machine result** — case count, exact verdict, required failure position,
   state assertions, and diagnostic allowances.
4. **Non-claims** — what the corpus cannot establish about live execution,
   capture completeness, witnesses, bypass resistance, certification, or
   untested paths.

Never treat `PASS`, `AGREE`, or `conformant` as a stronger statement than the
individual proof README permits.

## Evidence principle

> Each external proof lowers the cost of the next trust decision only when the
> previous proof's exact subject, boundary, result, and non-claims survive into
> the next step.
