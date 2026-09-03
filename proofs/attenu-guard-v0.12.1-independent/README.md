# Independent reproduction: Attenu `bundle_vectors_v1.2`

**Bounded result: 17/17 released cases conformant.** The same pinned official
case objects also discriminate the published verifier defect: Python 0.11.0
and npm 0.6.0 accept all four new reject rows, while Python 0.12.1 and npm
0.7.1 reject each at `monotonicity`, sequence 1, node `vectors:n1`, with the
changed authority dimension named in the diagnostic.

This is a new evidence subject. It preserves the v1.1 proof and the earlier
locally constructed before/after replay rather than rewriting either result.

## Causal engagement spine

- `spineId`: `attenu-v12-independent-2026-09-03`
- Purpose: independently score the immutable v1.2 corpus and test whether its
  four isolated rows distinguish the vulnerable and corrected releases.
- Exact subject: the fixture, source tags, registry artifacts, probes, reports,
  and repository generation bound by the external receipt listed below.
- Parent contract: the v1.1 result remained `HOLD` for official-corpus
  discrimination until an isolated upstream revision existed.
- Invariants: exact bytes; first twelve cases unchanged; literal-subset base;
  one authority-dimension mutation per reject row; integrity, anchor, and
  containment remain valid; identical case digests cross version/language.
- Forbidden outcomes: count a substituted bundle, an unexecuted check, a
  changed package, an extra causal failure, or a missing exact position as
  PASS.
- Authority boundary: the evidence branch and draft PR are within this
  engagement; merge, upstream adoption, and release claims remain human
  decisions.
- Stop conditions: any artifact/hash mismatch, moved subject, failed required
  check, or unresolved review finding changes the state to `HOLD`.

The Orientation Center is `BALANCED` for local execution: the source ancestry,
fixture identity, registry artifacts, and expected transition are resolved.
Hosted CI and exact-head review remain separate publication gates.

## Preregistered verification plan

1. Pin the exact v1.2 fixture and score all 17 cases with a standalone verifier.
2. Prove the first twelve case objects are structurally identical to v1.1.
3. Prove positions 13–17 use the literal-subset base and isolate one authority
   change per reject row.
4. Feed those exact official objects, plus stable accept/reject controls, to
   four hash-pinned registry packages.
5. Require old false-accept → new positioned-reject transitions for all four
   defect rows in both languages.
6. Freeze package bytes before extraction, bind the wheel-carried fixture,
   byte-compare the regenerated package report, and compare the 17-case report
   after the declared environment/path normalization.
7. Run focused tests, repository tests, hosted CI, and exact-head review.

## Exact identities

### Fixture and source tags

- Fixture: `bundle_vectors_v1.json`
- Contract/revision: `bundle_vectors_v1` / `bundle_vectors_v1.2`
- Size: 146,765 bytes
- SHA-256: `54311d68c8342c01ce233f4b1aea251125a4f3323fd9776c01843d3b2f5700ea`
- Git blob SHA-1: `88aee3fd8b346810423266a51783ee10c80a6b1f`
- Python `v0.12.1` tag object:
  `53063b6bfc353ccb52388aac6c2fe91be4f85bf5`
- Python tag peeled commit: `cdcef1368d564ccfdf0733508d1df9d062068c0f`
- TypeScript `v0.7.1` tag object:
  `bacd49171e435864e85cd42b804b02dbfb56d32b`
- TypeScript tag peeled commit: `d85db5b040093cefb5c61f45e4c9971f3c8d4703`

The Python source fixture, TypeScript source fixture, and Python 0.12.1 wheel
fixture are byte-identical. The wheel `RECORD` binds the same digest and size.
The npm package does not carry the fixture; equality with the TypeScript source
tag is corroboration, not a package-to-source attestation.

### Registry artifacts

| Role | Artifact | Bytes | SHA-256 |
|---|---|---:|---|
| Python before | `attenu_guard-0.11.0-py3-none-any.whl` | 312,444 | `cae895475f116deb862295b6c8938f5e586f115ea20bdd6df2f6b2e38df880b0` |
| Python after | `attenu_guard-0.12.1-py3-none-any.whl` | 321,186 | `bccba92a439b1c7bed9314589488b279d6236055d21d32278434b368f3f9c36f` |
| TypeScript before | `attenu-guard-0.6.0.tgz` | 222,495 | `9099da7270cda6e662a76ddf6ca08bd568bd8232970078cd1e47e76dd2377a13` |
| TypeScript after | `attenu-guard-0.7.1.tgz` | 214,567 | `0edc239d686ad1a709813f6382549745d3d48d1f5a5354a5d90fb1d4521ea5be` |

### Proof artifacts

- Repository: `safal207/ContractGraph-QA`
- Pull request / branch: `#152` /
  `proof/attenu-guard-v0.12.1-independent`
- External repository-subject receipt:
  https://github.com/safal207/ContractGraph-QA/pull/152#issuecomment-5528155565

The receipt is outside the commit graph to avoid a self-referential commit
identifier. It binds the exact base commit, head commit, and tree after hosted
verification; a moved head makes that receipt stale until explicitly replaced.

- Verifier SHA-256:
  `ad229ed3074b2c9dfd502beac4eb4ce9929c036946ebbf75bd46451016d412dd`
- 17-case report SHA-256:
  `5744e240e2ecb12b0c25c428f9b679eeee2abcc50f6b9b3d83049ab73ae375df`
- Python probe SHA-256:
  `cd051b7c6b08c6ea7479e2455ee500d1ce72247ad6c01c6faf3c0da255ebbf44`
- TypeScript probe SHA-256:
  `2802a02230fd353cb4d7ecd2fc276b3f6207cff66af77191b436908ab1838107`
- Replay driver SHA-256:
  `6445b789c2dfb088151652c891a288ba1f3e132565913b336af0c41842e0f894`
- Published-package report SHA-256:
  `bffd6372cc33db4141f01089356d0f825526c3b974105e6cd21fdd7d0c28f6e0`

## Independent 17-case score

`independent_bundle_verifier.py` is a separately pinned copy of the prior
stdlib-only verifier with only fixture identity, case-list, and claim metadata
re-pinned to v1.2. It imports no `attenu_guard` module and invokes neither
reference implementation.

| Corpus segment | Result |
|---|---:|
| First twelve v1.1 cases | 12/12 PASS |
| `valid_bundle_v2_literal` | PASS (accept) |
| Four literal-subset reject rows | 4/4 PASS |
| Total | **17/17 PASS** |

The first twelve case objects are structurally unchanged. The five appended
objects use root scopes `{crm.read, mail.send}` and child scopes `{crm.read}`;
no wildcard creates a second reason to reject. Relative to the valid base, the
four rejects change only child TTL, child `max_rows`, bounded TTL to `null`, or
the presence of the child ceiling.

## Exact-package discrimination

The replay parses the pinned fixture once and sends these exact official case
objects to each extracted package:

- stable accept: `valid_bundle_v2_literal`;
- four defect rows: `reject_increased_ttl_literal`,
  `reject_loosened_ceiling_literal`, `reject_null_ttl_literal`, and
  `reject_omitted_ceiling_literal`;
- stable reject: `reject_widened_scope`.

| Runtime | Before | After | Four defect rows | Two controls |
|---|---:|---:|---|---|
| Python wheel | 0.11.0 | 0.12.1 | accept → positioned reject | stable |
| npm package | 0.6.0 | 0.7.1 | accept → positioned reject | stable |

Result: **24/24 observations matched, 8/8 defect transitions proved, and 4/4
control transitions stayed stable.** Every after-release defect diagnostic is
the only failure and names the applicable TTL or ceiling dimension.

The driver reads and verifies all four artifacts before any package code runs.
Extraction consumes the same immutable in-memory bytes; path-swap regressions
prove that replacing a supplied wheel or tarball after verification cannot
change the executed snapshot. Archive traversal and a tampered fixture fail
closed.

## Reproduce

From the repository root:

```bash
python3 \
  proofs/attenu-guard-v0.12.1-independent/independent_bundle_verifier.py \
  proofs/attenu-guard-v0.12.1-independent/bundle_vectors_v1.json \
  --report proofs/attenu-guard-v0.12.1-independent/report.json

python3 \
  proofs/attenu-guard-v0.12.1-independent/check_report_provenance.py

python3 -m unittest tools/tests/test_attenu_bundle_v12_proof.py -v
```

After downloading the four exact registry artifacts listed above:

```bash
python3 \
  proofs/attenu-guard-v0.12.1-independent/check_reference_replay_provenance.py \
  --python-before-wheel /path/to/attenu_guard-0.11.0-py3-none-any.whl \
  --python-after-wheel /path/to/attenu_guard-0.12.1-py3-none-any.whl \
  --typescript-before-tarball /path/to/attenu-guard-0.6.0.tgz \
  --typescript-after-tarball /path/to/attenu-guard-0.7.1.tgz
```

The check requires the regenerated package report to match the committed bytes
exactly. The path-scoped GitHub workflow performs the same registry download
and replay under Python 3.12.13 and Node 24.19.0.

## Capability matrix

| Capability | Status | Current-bound reason |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Artifacts are digest-bound; the external receipt binds repository, branch, base, head, and tree. |
| Preregistered Verification Plan | RUN | Acceptance criteria above precede publication. |
| Orientation Center | RUN | Local evidence is `BALANCED`; hosted gates remain explicit. |
| Native Mapping / Adapter Review | RUN | Probes call each published package's native bundle verifier. |
| Safety Invariants | RUN | Invalid authority widening must reject. |
| Liveness / Reachability | NOT_APPLICABLE | Pure offline verification has no progress property. |
| Financial Conservation | NOT_APPLICABLE | No value-transfer invariant is in this corpus. |
| Authorization / Capabilities | RUN | Parent/child scopes, TTL, and ceilings are exercised. |
| Replay / Idempotency | RUN | Released duplicate outcome/call-id rows remain in the 17-case score. |
| Temporal Lifecycle | NOT_RUN | TTL authority narrowing is exercised, but no clock, expiry boundary, or repeated post-boundary operation is executed. |
| Crash / Recovery | NOT_APPLICABLE | No persisted transition or restart boundary exists. |
| Causal / Ancestral Validity | RUN | Every new reject is evaluated against exact parent authority. |
| Transition Geometry | RUN | Order-sensitive released rows and same-input version transitions are checked. |
| Negative Control | RUN | Vulnerable releases must falsely accept all four isolated rows. |
| Stateful / Property Search | SKIPPED_WITH_REASON | Claim is limited to immutable official cases, not generative completeness. |
| Independent Witness | RUN | Standalone scorer plus Python and TypeScript package probes. |
| Trace Integrity | RUN | Entry chain, signed anchor, package, fixture, and report identities are checked. |
| Evidence Type / Readiness | RUN | Raw bytes, execution results, and corroboration are kept distinct. |
| Counterexample Minimization | RUN | Four one-dimension official mutations are replayed unchanged. |
| Root-Cause Collapse | RUN | Scope syntax is held constant while TTL/ceiling changes. |
| Deterministic Replay | RUN | The package report regenerates byte-for-byte; the 17-case report uses declared environment/path normalization. |
| Metamorphic / Round-Trip Verification | RUN | First twelve rows and per-case hashes remain stable across revisions/runtimes. |
| Native Regression | RUN | Exact installed-package APIs execute the official defect rows. |
| Durable Evidence Reopen / Integrity | RUN | Static checkers reopen and verify committed artifacts. |
| Verification Debt | RUN | Build provenance and behavior beyond selected cases remain unresolved. |
| Active Verification Planning | RUN | Hosted CI and review are named gates. |
| Meaning Trajectory | RUN | v1.1 `HOLD` is refined by fresh isolated v1.2 evidence. |
| Dormant Patterns / Watchpoints | SKIPPED_WITH_REASON | No new latent pattern beyond explicit provenance debt was observed. |
| Temporal / External Replication | RUN | Fresh 0.12.1/0.7.1 artifacts revalidate the earlier fix. |
| Forward Remediation | NOT_APPLICABLE | This branch verifies an upstream correction; it does not change the packages. |

## Verdict and claim boundary

`PASS_WITHIN_BOUND` locally for the exact 17 fixture objects and the six
selected case objects executed under four exact registry artifacts. Repository
generation is bound separately by the external exact-subject receipt above.

This does not prove general verifier completeness, package-to-source build
provenance, CrewAI integration behavior, production security, or behavior
outside the declared corpus and package replay. A draft PR is not merge
approval; moved heads, failed CI, or unresolved review findings require fresh
collection.
