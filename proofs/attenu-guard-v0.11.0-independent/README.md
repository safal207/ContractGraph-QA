# Independent reproduction: Attenu `bundle_vectors_v1`

**Result: 8/8 cases conformant.** A standalone stdlib-only verifier accepted the valid schema-v2 bundle and reported every mandatory `{reason, seq, node}` at the position declared by the released corpus.

This proof responds to the independence boundary discussed in `crewAIInc/crewAI#5888`: the Python and TypeScript reference verifiers share one maintainer, so this run uses neither implementation.

## Pinned inputs

- `attenu-guard 0.11.0`: commit `68d4062a8f5610e9c2a80f9f378b9eedbb6d9fed`
- Release wheel SHA-256: `cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0`
- `attenu-guard-ts 0.6.0`: commit `4fd6a17bf1c05534f2b81db46adcdbd84d6d7af6`
- Fixture path: `tests/vectors/bundles/bundle_vectors_v1.json`
- Fixture size: `69,573` bytes
- Fixture SHA-256: `90d7fa70eabe92cbfa4df04bad50ac78995b57e83812cc5671e1ba9de01619ce`
- Fixture Git blob SHA-1 in both release tags: `7a78f025eed9f219f2ee055cef3ec1ae3fe1f352`
- Verifier SHA-256: `16b5a0f867a2d4b02c4b03a57ac993793df816cbd2f6e5ed82b62a13ee757bd0`

## Independence boundary

`independent_bundle_verifier.py` imports no `attenu_guard` module and does not invoke either published verifier. It independently implements the rules exercised by this corpus:

- strict JSON loading and corpus-profile canonical bytes;
- entry hash-chain recomputation;
- HS256 signed-anchor verification;
- authority narrowing and containment;
- schema-v2 `allow` → `outcome` binding, including params identity and ordering.

The verifier fails closed on JSON values outside its published corpus profile rather than claiming complete RFC 8785 number support.

## Results

| Case | Required result | Independent result |
|---|---|---|
| `valid_bundle_v2` | accept | accept |
| `reject_params_mismatch` | `params_mismatch` at seq 3 | PASS |
| `reject_outcome_without_allow` | `outcome_without_allow` at seq 6 | PASS |
| `reject_outcome_before_allow` | `outcome_before_allow` at seq 2 | PASS |
| `reject_duplicate_outcome` | `duplicate_outcome` at seq 4 | PASS |
| `reject_duplicate_call_id` | `duplicate_call_id` at seq 4 | PASS |
| `reject_rehashed_chain` | `integrity(anchor)` | PASS |
| `reject_tampered_entry` | `integrity` at seq 3 | PASS |

`report.json` contains the machine-readable score and observed diagnostics.

## Reproduce

Download the fixture from the pinned Python commit, verify its bytes, then run:

```bash
python3 independent_bundle_verifier.py bundle_vectors_v1.json --report reproduced_report.json
```

The verifier exits non-zero if the fixture hash differs, the case set changes, acceptance differs, or a mandatory positioned failure is missing.

## Diagnostic differences

There is no accept/reject disagreement and no mandatory failure is missing. Two extra-diagnostic differences are allowed by the corpus's minimal-set scoring rule:

1. `reject_duplicate_call_id`: this verifier additionally reports downstream node/params ambiguity caused by the duplicated identifier.
2. `reject_tampered_entry`: the Python reference additionally reports `integrity(anchor)`; this verifier reports the positioned entry-integrity failure, because the stored ledger head still matches the signed anchor body.

## Claim boundary

This establishes an independent reproduction of **these eight released fixtures**. It does not certify CrewAI runtime capture, all RFC 8785 values, implementation completeness outside the corpus, production security, or the release supply chain.
