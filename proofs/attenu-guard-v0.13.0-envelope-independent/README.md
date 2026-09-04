# Independent reproduction: Attenu observer envelopes v1.1

**Bounded result: 18/18 released cases conformant.**

## Exact subject

- Repository: `attenu-io/attenu-guard`
- Release tag: `v0.13.0`
- Commit: `8042a0ce33a9f8a7bf54a1917d5e8a0ac0344084`
- Contract: `envelope_vectors_v1`
- Revision: `envelope_vectors_v1.1`
- Vector SHA-256: `6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64`
- Verifier: `safal207-independent-envelope-v1.1` `0.1.0`
- Base ledger scorer: `safal207-independent-bundle-v1.2` `0.3.1`
- Upstream verifier execution: **disabled**.

## Case matrix

| Case | Expected | Observed | Required failures | Extra failures | States match | Canonical bytes match | Result |
|---|---|---|---|---|---|---|---|
| `valid_spawn_envelope` | accept | accept | — | — | yes | yes | **AGREE** |
| `valid_allow_envelope` | accept | accept | — | — | yes | yes | **AGREE** |
| `valid_jcs_reorder` | accept | accept | — | — | yes | yes | **AGREE** |
| `absent_envelope` | accept | accept | — | — | yes | yes | **AGREE** |
| `indeterminate_result` | accept | accept | — | — | yes | yes | **AGREE** |
| `reject_rehashed_chain_sparse` | reject | reject | `integrity(anchor)@None`, `envelope_subject_mismatch@2` | — | yes | yes | **AGREE** |
| `reject_subject_mismatch` | reject | reject | `envelope_subject_mismatch@1` | — | yes | yes | **AGREE** |
| `reject_bad_signature` | reject | reject | `envelope_bad_signature@1` | — | yes | yes | **AGREE** |
| `reject_unknown_version` | reject | reject | `envelope_unknown_version@1` | — | yes | yes | **AGREE** |
| `reject_non_canonical` | reject | reject | `envelope_non_canonical@1` | `envelope_bad_signature@1` | yes | yes | **AGREE** |
| `reject_member_without_bump` | reject | reject | `envelope_unknown_member@1` | — | yes | yes | **AGREE** |
| `reject_masked_bundle_mutation` | reject | reject | `envelope_subject_mismatch@1` | — | yes | yes | **AGREE** |
| `reject_rehashed_chain_anchored` | reject | reject | `integrity(anchor)@None`, `envelope_subject_mismatch@1` | `envelope_subject_mismatch@2` | yes | yes | **AGREE** |
| `reject_rehashed_chain_unanchored` | reject | reject | `envelope_subject_mismatch@1` | — | yes | yes | **AGREE** |
| `reject_unknown_witness` | reject | reject | `envelope_unknown_witness@1` | — | yes | yes | **AGREE** |
| `reject_locator_mismatch` | reject | reject | `envelope_subject_mismatch@1` | — | yes | yes | **AGREE** |
| `reject_duplicate_subject` | reject | reject | `envelope_duplicate_subject@1` | — | yes | yes | **AGREE** |
| `reject_unknown_alg` | reject | reject | `envelope_unknown_witness@1` | — | yes | yes | **AGREE** |

The corpus uses a minimal-set rule: extra findings are permitted, but every declared `{reason, seq, node}` must be present, and the per-entry state must match exactly. Envelope failures are constrained to covered hops; they never manufacture a chain-level anchor failure.

## What this independently checks

1. The exact released JSON bytes, revision, SHA-256 and 18-case order.
2. The ledger hash chain, HS256 anchor where present, delegation monotonicity, containment and bundle-v2 execution binding through the already merged standalone ContractGraph-QA scorer.
3. Envelope-v1 member sets, event-specific subjects, recomputed `entry_hash`, locator consistency and one-envelope-per-entry.
4. Ed25519 verification under the `kid`-selected trusted key, with `EdDSA` as the only accepted v1 algorithm.
5. Raw-byte JCS canonicality for the non-canonical negative control and exact signing bytes for the reorder positive control.
6. Exact required reason/position pairs and every entry's `witness-signed` or `process-asserted` state.

## Boundary preserved

A valid envelope proves that a configured witness key signed the identity of one committed entry. It does not prove that the witness was authoritative, that coverage was complete, or that a missing top-level `envelopes` array was never stripped. Envelope v1 keeps that array outside the ledger anchor; this report preserves the limitation rather than upgrading absence into evidence.

## Non-claims

This is frozen-corpus interoperability evidence. It is not a general security audit, runtime certification, proof of witness independence, proof of global coverage, A2A conformance certification, or endorsement in either direction.
