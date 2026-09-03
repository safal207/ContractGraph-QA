# Independent reproduction: Attenu `bundle_vectors_v1.1`

**Released-corpus result: 12/12 cases conformant.** A standalone stdlib-only
verifier accepted the valid schema-v2 bundle and reported every mandatory
`{reason, seq, node}` at the exact position declared by the `bundle_vectors_v1.1`
corpus shipped in `attenu-guard 0.12.0`.

This proof is additive. It does not replace or rewrite the pinned 8/8 result for
`attenu-guard 0.11.0` and corpus revision `bundle_vectors_v1`.

## Pinned release identities

- `attenu-guard 0.12.0` annotated tag object:
  `b8f8d41cf142ae34e4e3c4398d7eec4787d10a8b`
- Python tag peeled commit: `91262878b4342814ed83c69a565ef0cef52e54ce`
- PyPI wheel SHA-256:
  `0c17b0f14379ac2f85d091abcb30b5180bce0b6e19d97a88a080c985abec5dc7`
- `attenu-guard-ts 0.7.0` annotated tag object:
  `f542602656e7c01ecc2d601cc8d0cbb9c942b3a6`
- TypeScript tag peeled commit: `d972fa4ace1e537b56264d901594b07f4b8f991a`
- npm tarball SHA-256:
  `6461138a638a2ac991000f4fcf1c84f317aee1155eef6f53bbc5a932e8b30b12`
- Vendored fixture: `bundle_vectors_v1.json`
- Fixture revision: `bundle_vectors_v1.1`
- Fixture size: `104,579` bytes
- Fixture SHA-256:
  `b21c5a44a79d422d52857f03e2f3327d559c409e98c482b4664e1ab726327403`
- Fixture Git blob SHA-1 in both release tags:
  `de376308bdb5d469f09b096e75eae4cd762f2262`
- Verifier SHA-256:
  `ec57e24d9ee85530b4acbd44427247700ca8a2a55dc83c39002792929f09695f`
- Generated report SHA-256:
  `0be4a61065fa63d87ca79433e2a17b6bf384d8dd83f152867f52a6a6fd45cd5f`

The Python source tag, TypeScript source tag, and installed Python wheel carry
the same fixture bytes. The wheel's `RECORD` also binds the same byte count and
SHA-256 digest.

## Independence boundary

`independent_bundle_verifier.py` imports no `attenu_guard` module and invokes
neither published verifier. It independently implements only the rules needed
by this corpus profile:

- strict JSON loading and corpus-profile canonical bytes;
- entry hash-chain recomputation;
- HS256 signed-anchor verification;
- authority monotonicity across scopes, TTL, and the exercised `max_rows`
  ceiling;
- allow containment;
- schema-v2 `allow` to `outcome` binding.

Unknown canonical number forms and constraint forms fail closed rather than
being presented as complete RFC 8785 or draft-vocabulary support.

## Released-corpus results

| Case | Required result | Independent result |
|---|---|---|
| `valid_bundle_v2` | accept | PASS |
| `reject_params_mismatch` | `params_mismatch`, seq 3 | PASS |
| `reject_outcome_without_allow` | `outcome_without_allow`, seq 6 | PASS |
| `reject_outcome_before_allow` | `outcome_before_allow`, seq 2 | PASS |
| `reject_duplicate_outcome` | `duplicate_outcome`, seq 4 | PASS |
| `reject_duplicate_call_id` | `duplicate_call_id`, seq 4 | PASS |
| `reject_rehashed_chain` | `integrity(anchor)`, chain-level | PASS |
| `reject_tampered_entry` | `integrity`, seq 3 | PASS |
| `reject_widened_scope` | `monotonicity`, seq 1 | PASS |
| `reject_uncontained_allow` | `containment`, seq 4 | PASS |
| `reject_increased_ttl` | `monotonicity`, seq 1 | PASS |
| `reject_loosened_ceiling` | `monotonicity`, seq 1 | PASS |

## Supplemental defect-boundary checks

The released v1.1 TTL and ceiling rows use `crm.read` below a parent holding
`crm.*`. That scope difference means an older verifier can reject the row at
the required position even while still mishandling a literal-subset grant. The
release maintainer has said a v1.2 fixture will rebuild those rows on a literal
subset base.

`test_containment_regressions.py` therefore keeps a separate, non-conformance
test layer. It rebuilds the chain and anchor after each local mutation and
checks five boundaries:

1. a literal-subset control remains valid;
2. literal-subset plus increased TTL rejects;
3. literal-subset plus loosened ceiling rejects;
4. literal-subset plus omitted TTL rejects;
5. literal-subset plus omitted child ceiling rejects.

Result: **5/5 PASS**. These local mutations demonstrate the behavior of this
independent verifier only. They are not released vectors and do not prove the
reference implementations fixed the defect.

## Published-package before/after replay

The separate reference replay closes that proof gap against the exact
published artifacts, without importing either implementation into the
independent 12/12 scorer. It constructs the same literal-subset bundle under
all four versions, re-hashes and re-signs each mutation, and requires integrity
and containment to stay green while only monotonicity changes.

| Runtime | Before | After | Four defect cases | Two controls |
|---|---:|---:|---|---|
| Python wheel | 0.11.0 | 0.12.0 | false accept -> reject | stable |
| npm package | 0.6.0 | 0.7.0 | false accept -> reject | stable |

The four cases are increased TTL, loosened ceiling, unbounded TTL, and a
dropped child ceiling. The controls are an accepted literal-subset grant and a
rejected scope widening. Result: **24/24 observations matched** and **8/8
runtime defect transitions proved** (four in each implementation).

Pinned before-release artifacts:

- Python 0.11.0 wheel: 312,444 bytes, SHA-256
  `cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0`;
- npm 0.6.0 tarball: 222,495 bytes, SHA-256
  `9099da7270cda6e662a76ddf6ca08bd568bd8232970078cd1e47e76dd2377a13`.

The after-release artifact hashes are the 0.12.0 and 0.7.0 hashes already
pinned above. `reference_release_report.json` records every observation, both
probe hashes, the exact runtime identities, and one canonical SHA-256 for each
of the six input bundles. Every probe fixes the root `params_salt` to the same
16-byte value, and the driver requires each case's canonical bundle digest to
match across both releases and both languages before accepting the transition.

The driver reads and verifies all four package artifacts once before any probe
runs. Extraction consumes those same immutable in-memory bytes rather than
reopening the caller-supplied paths, so a later path replacement cannot detach
the reported digest from the code that is executed. The packages are extracted
into a private temporary directory; they are not installed and the replay uses
no network after the initial caller-managed download.

## Exact-tag source corroboration

The released source trees were checked separately, without treating source
tests as package provenance:

- Python peeled commit `91262878b4342814ed83c69a565ef0cef52e54ce`:
  `tests/test_bundle_vectors.py` passed **28/28**, including all ten
  `TestMonotonicityDimensions` boundaries;
- TypeScript peeled commit `d972fa4ace1e537b56264d901594b07f4b8f991a`:
  its full `npm test` build and suite reported **298 passed, 0 failed, 1
  skipped**. The skipped cross-language CLI test was not load-bearing for the
  monotonicity fix or the published-package replay.

This is corroboration of source behavior at the two exact commits. It does not
by itself bind either source tree to a registry artifact.

## Reproduce

From the repository root:

```bash
python3 \
  proofs/attenu-guard-v0.12.0-independent/independent_bundle_verifier.py \
  proofs/attenu-guard-v0.12.0-independent/bundle_vectors_v1.json \
  --report proofs/attenu-guard-v0.12.0-independent/report.json

python3 \
  proofs/attenu-guard-v0.12.0-independent/check_report_provenance.py

python3 \
  proofs/attenu-guard-v0.12.0-independent/test_containment_regressions.py
```

The provenance check binds the exact verifier, fixture bytes, fixture revision,
case list and order, report schema, regenerated report, and 12/12 result. It
normalizes only machine-specific environment metadata and the input path.

For the published-package before/after replay, first download the four named
release artifacts, then run:

```bash
python3 \
  proofs/attenu-guard-v0.12.0-independent/check_reference_replay_provenance.py \
  --python-before-wheel /path/to/attenu_guard-0.11.0-py3-none-any.whl \
  --python-after-wheel /path/to/attenu_guard-0.12.0-py3-none-any.whl \
  --typescript-before-tarball /path/to/attenu-guard-0.6.0.tgz \
  --typescript-after-tarball /path/to/attenu-guard-0.7.0.tgz
```

That check pins the driver, both probes, committed report, all four package
hashes and byte counts, then requires an exact byte-for-byte regenerated
report.

The Product workflow's `Attenu exact published artifacts` job runs the static
proof gates, downloads the four exact registry artifacts, verifies their pinned
hashes and sizes before execution, and performs the complete 24/24 replay under
the runtime versions recorded in the committed report.

## Diagnostic differences

There is no accept/reject disagreement and no required failure is missing.
The two previously documented optional-diagnostic boundaries remain unchanged:

- `reject_duplicate_call_id`: first-sighting binding produces the same three
  optional downstream diagnostics recorded by the prior independent runs;
- `reject_tampered_entry`: this verifier checks the signed anchor against the
  stored terminal hash, so it does not add the optional recomputed-head
  `integrity(anchor)` finding.

The four v1.1 cases produce exactly one failure each, matching their isolation
contract.

## Publication boundary

This folder is ready as a bounded proof of the exact `bundle_vectors_v1.1`
bytes shipped in the 0.12.0 releases.

- **PASS — published-package regression fix:** the discriminating negative
  control directly proves the four false accepts in Python 0.11.0 and npm 0.6.0
  become positioned monotonicity rejects in Python 0.12.0 and npm 0.7.0.
- **HOLD — official-corpus isolation claim:** v1.1's own TTL and ceiling rows
  still do not isolate the original literal-subset gate. Recollect and score
  the immutable fixture identity when upstream publishes v1.2.

The first conclusion no longer depends on v1.2; the second deliberately does.

## Claim boundary

This establishes independent reproduction of the twelve released v1.1
fixtures and a bounded before/after runtime result for four exact published
package artifacts. It does not certify behavior outside the six replay cases,
CrewAI runtime capture, all RFC 8785 values, production security, or the release
supply chain. In particular, no independently verified build attestation binds
the tested wheel and npm tarballs back to the two source-tag commits.
