# Independent reproduction: Attenu `bundle_vectors_v1.1`

**Result: 12/12 cases conformant.** A standalone stdlib-only verifier accepted the valid schema-v2 bundle and reported every mandatory `{reason, seq, node}` at the position declared by the released corpus.

This is a new proof boundary for the four cases appended in revision `bundle_vectors_v1.1`. The earlier eight-case proof remains preserved separately under `proofs/attenu-guard-v0.11.0-independent`.

## Pinned inputs

- `attenu-guard 0.12.0`: annotated tag object `b8f8d41cf142ae34e4e3c4398d7eec4787d10a8b`, commit `91262878b4342814ed83c69a565ef0cef52e54ce`, tree `7c2f2e780e1d07dc7a296703b869aeac4348f659`
- Python release wheel `attenu_guard-0.12.0-py3-none-any.whl` SHA-256: `0c17b0f14379ac2f85d091abcb30b5180bce0b6e19d97a88a080c985abec5dc7`
- `attenu-guard-ts 0.7.0`: annotated tag object `f542602656e7c01ecc2d601cc8d0cbb9c942b3a6`, commit `d972fa4ace1e537b56264d901594b07f4b8f991a`, tree `27f6a50f3418b00eaf80adee6f8bffbac3baaf03`
- npm release tarball `attenu-guard-0.7.0.tgz` SHA-256: `6461138a638a2ac991000f4fcf1c84f317aee1155eef6f53bbc5a932e8b30b12`
- Vendored fixture: `bundle_vectors_v1.json`
- Python source and wheel path: `attenu_guard/vectors/bundles/bundle_vectors_v1.json`
- TypeScript release-tag path: `test/fixtures/vectors/bundles/bundle_vectors_v1.json`
- Fixture size: `104,579` bytes
- Fixture SHA-256: `b21c5a44a79d422d52857f03e2f3327d559c409e98c482b4664e1ab726327403`
- Fixture Git blob SHA-1 in both release tags: `de376308bdb5d469f09b096e75eae4cd762f2262`
- Verifier SHA-256: `26446ec98f757eb369dc15de8d49bf32f5e625704ea0a435d53f768fc14fa16c`
- Generated report SHA-256: `48c6a56bdd92ed406e5eedaf0f54d08c44d615b894afcfd5a2588b31f07850a5`

The npm tarball does not contain the repository's test fixture. The cross-language byte-identity statement is therefore bound to the two exact release tags; the Python wheel independently carries the same fixture bytes.

## Independence boundary

`independent_bundle_verifier.py` imports no `attenu_guard` module and does not invoke either published verifier. It independently implements the rules exercised by this corpus:

- strict JSON loading and corpus-profile canonical bytes;
- entry hash-chain recomputation;
- HS256 signed-anchor verification;
- scope-, TTL-, and ceiling-aware authority narrowing;
- per-action containment;
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
| `reject_widened_scope` | `monotonicity` at seq 1 | PASS |
| `reject_uncontained_allow` | `containment` at seq 4 | PASS |
| `reject_increased_ttl` | `monotonicity` at seq 1 | PASS |
| `reject_loosened_ceiling` | `monotonicity` at seq 1 | PASS |

The first eight case objects are structurally unchanged from the previous released fixture. Their independent outcomes and diagnostics remain unchanged.

`report.json` is the direct `--report` output of the verifier beside it. It uses `failure_details` rows carrying `reason`, `seq`, `node`, `call_id`, and `detail`.

## Reproduce

From the repository root:

```bash
python3 \
  proofs/attenu-guard-v0.12.0-independent/independent_bundle_verifier.py \
  proofs/attenu-guard-v0.12.0-independent/bundle_vectors_v1.json \
  --report proofs/attenu-guard-v0.12.0-independent/report.json
```

Then verify exact source-to-generated parity:

```bash
python3 proofs/attenu-guard-v0.12.0-independent/check_report_provenance.py
```

The provenance check verifies the verifier and fixture hashes, exact fixture size, vector contract and revision, twelve-case report schema, 12/12 result, and regenerated-versus-committed equality. It normalizes only environment metadata and the input path so the comparison is portable across machines.

## Diagnostic differences retained from v1.0

There is no accept/reject disagreement and no mandatory failure is missing. Additional diagnostics remain permitted by the corpus's minimal-set scoring rule.

1. `reject_duplicate_call_id`: this first-sighting implementation reports the same three downstream diagnostics independently reported by the Rust verifier: the orphaned outcome at seq 3 and the node/params failures at seq 6. They remain **MAY** diagnostics.
2. `reject_tampered_entry`: this verifier checks the signed anchor against the stored terminal hash and reports entry-chain integrity separately. A recomputed-head verifier may additionally report `integrity(anchor)`; that row remains **MAY**.

## Regression-discrimination limitation

Revision v1.1 closes the earlier absence of rejecting monotonicity and containment rows, but it does **not** by itself prove that the 0.12.0 monotonicity defect is fixed.

The exact 0.11.0 reference verifier at commit `68d4062a8f5610e9c2a80f9f378b9eedbb6d9fed` also rejects both `reject_increased_ttl` and `reject_loosened_ceiling` at the required `monotonicity`, seq 1, node `vectors:n1`. Its diagnostics incorrectly identify `crm.read` as a scope not held by the parent `crm.*`. That literal scope-set difference activates the old gate before the changed TTL or ceiling is evaluated, so a buggy build receives the same conformance score for the wrong causal reason.

The smallest discriminating follow-up holds the parent and child scope sets literally equal and changes only one dimension:

- child TTL greater than parent TTL;
- child `max_rows` greater than parent `max_rows`.

The 0.12.0 release notes also name missing TTL and dropped-ceiling variants. Revision v1.1 does not contain isolated rows for those two variants, so this proof does not claim negative corpus coverage for them.

## Claim boundary

This establishes an independent reproduction of **these twelve released fixtures**, 12/12, at the pinned release boundary. It does not by itself establish regression discrimination for the fixed 0.11.x bug, general verifier completeness, CrewAI runtime correctness, full RFC 8785 support, production security, or release-supply-chain certification.
