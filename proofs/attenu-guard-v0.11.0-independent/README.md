# Independent reproduction: Attenu `bundle_vectors_v1`

**Result: 8/8 cases conformant.** A standalone stdlib-only verifier accepted the valid schema-v2 bundle and reported every mandatory `{reason, seq, node}` at the position declared by the released corpus.

This proof responds to the independence boundary discussed in `crewAIInc/crewAI#5888`: the Python and TypeScript reference verifiers share one maintainer, so this run uses neither implementation.

## Pinned inputs

- `attenu-guard 0.11.0`: commit `68d4062a8f5610e9c2a80f9f378b9eedbb6d9fed`
- Release wheel SHA-256: `cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0`
- `attenu-guard-ts 0.6.0`: commit `4fd6a17bf1c05534f2b81db46adcdbd84d6d7af6`
- Vendored fixture: `bundle_vectors_v1.json`
- Original fixture path: `tests/vectors/bundles/bundle_vectors_v1.json`
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

`report.json` is the direct `--report` output of the verifier beside it. It uses `failure_details` rows carrying `reason`, `seq`, `node`, `call_id`, and `detail`.

## Reproduce

From the repository root:

```bash
python3 \
  proofs/attenu-guard-v0.11.0-independent/independent_bundle_verifier.py \
  proofs/attenu-guard-v0.11.0-independent/bundle_vectors_v1.json \
  --report proofs/attenu-guard-v0.11.0-independent/report.json
```

Then check that the committed report still comes from that exact verifier and fixture:

```bash
python3 proofs/attenu-guard-v0.11.0-independent/check_report_provenance.py
```

The provenance check verifies both source hashes, the exact fixture size, the 8/8 result, the report schema, and regenerated-versus-committed equality. It normalizes only environment metadata and the input path so the check is portable across machines.

## Artifact provenance correction

The `report.json` committed at `61dc428` recorded the same 8/8 verdicts and scored `{reason, seq, node}` tuples, but its shape was not the direct output of the verifier pinned beside it. That report is superseded by this generated artifact. The verifier logic and bounded result did not change.

## Diagnostic differences

There is no accept/reject disagreement and no mandatory failure is missing. Additional diagnostics remain permitted by the corpus's minimal-set scoring rule.

1. `reject_duplicate_call_id`: two code-independent implementations using first-sighting binding report the same three downstream diagnostics: the orphaned outcome at seq 3 and the node/params failures at seq 6. These remain **MAY** diagnostics; a conformant verifier may stop at the identifier collision or represent the ambiguity differently.
2. `reject_tampered_entry`: this verifier validates the signed anchor against the stored terminal hash and reports entry-chain integrity separately. A verifier that recomputes the terminal head from entry bodies may additionally report `integrity(anchor)`. The relevant implementation choice is therefore **stored-head versus recomputed-head anchor validation**, and the additional anchor finding remains **MAY**.

## Known coverage gap

`valid_bundle_v2` exercises scope coverage, ceiling monotonicity, and TTL narrowing only on a valid delegation. This corpus has no negative bundle-level containment case. Passing it is therefore not negative evidence that widened scope, increased TTL, or a loosened ceiling are implemented correctly. Those should be isolated as separate one-change rejecting vectors in a future corpus.

## Claim boundary

This establishes an independent reproduction of **these eight released fixtures**. It does not certify CrewAI runtime capture, all RFC 8785 values, implementation completeness outside the corpus, production security, or the release supply chain.
