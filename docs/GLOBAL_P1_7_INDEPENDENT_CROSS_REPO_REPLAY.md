# GLOBAL P1-7 — Independent Cross-Repository Replay

Status: **reference/conformance contract**. This document does not claim merge, deployment, live authority, production ledger mutation, or upstream framework adoption.

## Why P1-7 exists

P1-4/P1-5/P1-6 prove occurrence portability, race/replay behavior, and immutable consumption receipts inside the ContractGraph-QA reference model. P1-7 deliberately changes the verifier vantage.

The P1-7 verifier **does not import `contractgraph_qa.occurrence_portability`** and does not accept a producer summary as proof. It rebuilds the critical identities from raw inputs and exact repository subjects.

The load-bearing invariant is:

```text
semantic decision identity
  != authorization occurrence identity
  != consumption fact
  != cross-repository verifier subject
```

A valid replay must bind all four without collapsing them.

## Inputs

P1-7 uses two independent input classes.

1. **Raw authorization/consumption fixture**
   - multiple occurrences may share one `decision_ref`;
   - `cites_event_id` selects the concrete permission occurrence;
   - action, authority revision, validity interval, consumer, request and consumption time remain explicit;
   - the observed `ConsumptionReceipt` is treated as a claim to verify, not as trusted truth.

2. **Pinned repository subjects**
   - ProofPath: `4a05ee31d7497979c2505dd55bfef08823302e24`
   - CML: `2a649903693fc61a560ee056834127ada3120206`
   - LiminalDB: `61b02fc81e0cb5cf1f1ed4658ecff58f683cb728`
   - RINSE: `3be0d2ceb1440641b141cdb80c82ed118e4186dd`
   - RESONANCE: `85c3baea0a551751263ef563a3dd1c75492f57ae`
   - ContractGraph-QA: the exact workflow head under verification.

For every subject, the verifier checks repository `HEAD`, resolves the committed Git blob for the configured path, hashes the worktree file, and rejects any worktree/commit drift.

## Independent reconstruction

The verifier independently performs:

```text
decision_ref + cites_event_id
    -> exact occurrence
    -> canonical occurrence envelope
    -> occurrence fingerprint
    -> order-sensitive route fingerprint
    -> reconstructed ConsumptionReceipt
    -> receipt digest
    -> pinned raw repository subjects
    -> cross_repo_subject_fingerprint
    -> independent replay witness
```

The RESONANCE interoperability fixture is used only as a raw route/scope contract. Its SYSTEM-007 route must remain:

```text
intent -> proofpath -> cml -> liminaldb -> rinse -> contractgraph_qa
```

and its authority boundary must remain fail-closed (`execution_authorized`, `mutation_authorized`, and `external_effects_authorized` are all false).

## Falsification surface

The focused unit suite covers exact replay plus fail-closed cases for:

- missing `cites_event_id` when one semantic decision has multiple occurrences;
- unknown and cross-bound event identifiers;
- route reordering;
- receipt decision, route fingerprint, and digest mutation;
- repository revision mutation;
- raw subject mutation;
- duplicate repository component identity.

The workflow additionally executes live negative tamper probes against cloned exact subjects: route reorder, ambiguity, receipt tamper, revision tamper, and RINSE raw-subject worktree tamper.

## Evidence rule

P1-7 is `VERIFIED` only when the dedicated workflow succeeds on the **final exact ContractGraph-QA head**. A green run on an earlier SHA is historical evidence, not proof of a later head.

The workflow emits:

- `result.json` — independently reconstructed replay witness and receipt;
- `run-context.json` — exact verifier and external revisions;
- `SHA256SUMS` — immutable digest manifest for the emitted evidence bundle.

No committed evidence file is added after the green exact-head run; the final receipt should be attached as PR review/comment metadata so the verified branch SHA does not move.
