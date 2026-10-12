# Evidence and applicability — Tamga binding case

## Exact subject and authority

- Subject: `goun7/tamga-protocol`, parent `7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b` -> fix `c62d4a822d7e3546931197905e137d0eb6fb490e`.
- Hosting repository **base for the case branch**: `safal207/ContractGraph-QA@f13e586ea9118e026c69438b8c93d0585b8e38ba`. This base does not contain the case artifacts; CGQA engine **NOT_RUN** for this comparison.
- Original evidence-bearing snapshot: [`3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6`](https://github.com/safal207/ContractGraph-QA/tree/3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6/external-validation/tamga-binding), containing the original case, reproducer, evidence notes, and recorded results.
- Original reproducer snapshot: [`7d4e8682b3fdb364356299d3352d9b4e4c333203`](https://github.com/safal207/ContractGraph-QA/blob/7d4e8682b3fdb364356299d3352d9b4e4c333203/external-validation/tamga-binding/reproduce.py); Git blob `bb57f438ed957e9f9d68a556c818e02dc256693c`, SHA-256 `255784d59e50b4185281fcb033112186dbefa95f13ab3c0c4e37ed95a0926cb8`, 6919 bytes.
- Spine: `tamga-binding-case-20261011`.
- Authorization reference: `user-go-20261011T001058+0300`, approving the preceding case-publication and scoped author-review proposal. The initial publication route was a separate branch and draft PR; merge remains a separate decision.
- Interpretation: `PASS_WITHIN_BOUND` for the four-scenario historical comparison. Author attribution and technical-scope accuracy **CONFIRMED** by [goun7 on 11 October 2026](https://github.com/safal207/ContractGraph-QA/pull/209#issuecomment-6111831002), for the [case submitted at `3a6bcd1`](https://github.com/safal207/ContractGraph-QA/blob/3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6/docs/case-studies/TAMGA_RECEIPT_BINDING.md). This discussion confirmation is not a formal PR approval.

## Preregistered contract and observed result

Before execution, the matrix required original acceptance on both versions, parent acceptance/fix rejection of each selected stale-field mutation at the expected location, and acceptance of a consistently rewritten fixture on both versions. Unexpected JSON, return code, stderr, identity, or branch outcomes prevent the corresponding claim.

The same fixed-version committed fixture and Keccak dependency are used for both verifiers. The fix's parent relation and two-file diff show that these shared files are unchanged across the selected pair. The harness invokes exact verifier source bytes; it does not substitute a reimplemented verifier. The original harness inspected `ok`, `where`, return code, and absence of stderr. The revised harness additionally requires the complete expected JSON payload, including success hashes and ordered checks or the exact scenario-specific failure reason. That stronger requirement is not retroactively attributed to the original execution.

Original recorded observation: **8/8 expected outcomes**, with an identical repeat reported at publication. The original second-run record was not separately committed. This means four scenarios across two versions. The accepted consistent rewrite is an intentional limitation control, not a successful security test. It updates the input, fixture commitment, charge input hash, record hash, and envelope hash while retaining the prior output bytes.

Raw outputs and all six input source identities are in [results.json](results.json). Six Git blob identities are checked before every run. Source identities and raw results are committed with this case; source SHA-256 and sizes are also retained in the results.

## Execution environment and omissions

Python 3.12.14; inspected stdlib-only harness plus upstream verifier and Keccak module. Execution used temporary synthetic fixture copies, isolated Python mode, no site packages, sanitized child environments, resource limits, and inherited external seccomp restrictions blocking network sockets and selected privileged syscalls. A socket creation probe confirmed denial. Filesystem namespace isolation was unavailable; the containment claim is limited to those restrictions.

The published reproducer does not install this local containment profile. Review fetched code before execution in your own environment. Its default initial download needs network access; the committed `--source-packet` permits reproduction without that download; the verifier invocations operate on local bytes. No provider call or payment is performed.

The full Tamga runtime, complete ledger verification, trusted anchor/signature verification, upstream full suite, and CGQA engine were **NOT_RUN**. The maintainer's historical report of 21 controls is not counted as our execution result. Source labels `observed`, `simulated`, and `derived` describe upstream fixture metadata, not an independently witnessed agent run.

## Recorded review replay

Codex review at `dcceead958e1ade2011590f4a7b3aa0372165f91` identified incomplete payload assertions, an ambiguous base/evidence reference, and the absent second-run record. A subsequent Codex review at `8b96f1cd2c5b4bf2d754294536ed857f071c487e` identified that falsy offline packets could silently select network downloads. Codex review at `5abd2d4f4617e205062984349b7e4d7301bf1ef0` then identified that the offline replay packet was missing from a fresh checkout. This follow-up preserves [the original results at `3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6`](https://github.com/safal207/ContractGraph-QA/blob/3a6bcd1e08cbf7c85a60e70abe8ca2392afdf3d6/external-validation/tamga-binding/results.json) and adds two **fresh** executions of the revised reproducer: [first output](review-results.json) and [repeat output](review-repeat-results.json). Each matched **8/8** expected outcomes; report bytes are identical. Their shared SHA-256 is `7aec7cc504a054e85342e27b4c4409d862fb0e11976ed3e1d73ea7c68b095bd9`. [The replay record](REPLAY_VERIFICATION.json) binds both outputs, the revised harness, test file, commands, environment, and verification results.

The revised harness used in those executions is Git blob `abf4c9087dc9ce14164f29c7ec8288bb69a544d0`, SHA-256 `3cbc14e62ebf0b716bd8c3ce8f59fd6fa66ef69c8472de9a7e9f7d0dc396aab2`, 8697 bytes. It was tested as a local overlay based on reviewed head `5abd2d4f4617e205062984349b7e4d7301bf1ef0` and is published with these records. Removing its added expected-payload and harness-identity metadata leaves the same historical source identities and outcomes as the original report. These fresh records demonstrate repeatability of the pinned historical comparison; they do not recover or independently attest to the unrecorded original repeat, and they do not assess current releases.

The exact [offline source packet](utf8-source-packet.json) is committed: 16070 bytes, Git blob `e91fe543fc2055cc4ee7600a09026800f4da6fae`, SHA-256 `9d6461283d0e5e32ee8ee50ade84738cf25d762aeab22f7e8c0047f2a0b09307`. Its six decoded UTF-8 source contents retain the upstream identities in the results; no source bytes were edited. The manifest records the packet, its digest, and the working directory needed by the replay commands. [Upstream Apache-2.0 license](TAMGA_LICENSE.txt) and [source/package notices](THIRD_PARTY_NOTICES.md) accompany the packet. A clean temporary directory containing only the committed script, tests, packet, and notices passed all 22 tests and both offline 8/8 runs; its reports matched the committed outputs byte-for-byte.

The offline packet is read explicitly as UTF-8. When `--source-packet` is supplied, its top-level `contents` object and all six required string entries are validated before any download or verifier invocation; malformed or incomplete packets stop execution instead of selecting online mode. With a literal-Unicode packet under `LC_ALL=C` and Python UTF-8 mode disabled, the original harness raised `UnicodeDecodeError`; the revised harness completed both eight-invocation matrices. [Fourteen offline oracle regression tests and eight source-packet regressions](test_reproduce.py) pass: 22 tests in total. Main-boundary tests verify that invalid supplied packets cause neither a network fetch nor verifier execution. Replacing the full-payload comparator with the previous `ok/where/status/stderr` predicate produced 14 failing unittest entries, confirming that the tests detect its false-positive paths. These tests import the local harness without running upstream code. The dedicated CI job is configured to run the oracle and packet-validation tests, execute the historical matrix twice using the committed offline packet, and compare the two generated reports. CI execution remains distinct from the separately recorded local review replay.

The original execution environment above remains a historical record. These review executions used Python 3.12.14, the six verified offline source contents, and isolated child interpreter flags; no new claim about the original external containment profile is made.

## Attribution and claim boundary

- [Initial author acknowledgement of review](https://github.com/x402-foundation/x402/issues/3379#issuecomment-5560621478).
- [Author links the fix, native controls, and adopted scope](https://github.com/x402-foundation/x402/issues/3379#issuecomment-5562472232).
- [Attributed implementation commit](https://github.com/goun7/tamga-protocol/commit/c62d4a822d7e3546931197905e137d0eb6fb490e).
- [Author confirmation of attribution, technical scope, and comfort linking the historical case](https://github.com/safal207/ContractGraph-QA/pull/209#issuecomment-6111831002).
- [Native control source at the fixed revision](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/tests/at007_pairing_fixture.sh).

Independent review and fresh reproduction: Alexey Safonov (`safal207`). Implementation/native regression authorship: `goun7`. Author confirmation applies to those distinct contributions and the stated historical scope. His agreement to link the case, with its historical-commit note visible, does not establish that an upstream documentation link has been published or that Tamga adopted or endorsed ContractGraph-QA. The phrase “updated fixture commitment” is intentional: the mutation recomputes hash metadata and does not digitally sign anything.

The compared verifier checks supplied fixture consistency. It does not authenticate receipt provenance, establish global ledger completeness, verify input-to-output execution semantics, or establish execution, settlement finality, buyer receipt/acceptance, effect count, or exactly-once. A complete consistent rewrite remains accepted. This is not an attack on a separate ledger verifier or a claim about current Tamga/x402 releases.

## Capability classification

The matrix describes the bounded historical Tamga subject. Rows that mention the review replay are supported by the separately recorded fresh executions above. Original results and source pins remain unchanged; the stronger harness assertions are a distinct verification event.

| Capability | Status | Evidence or reason |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Pinned parent/fix; six source blobs checked before invocation. |
| Preregistered Verification Plan | RUN | Four scenarios and exact acceptance/failure locations recorded before execution. |
| Orientation Center | RUN | Historical consistency claim resolved; author attribution/scope confirmed separately; broader claims remain outside the result. |
| Native Mapping / Adapter Review | RUN | Inspected upstream verifier, Keccak dependency, and AT-007g/h. Harness mutates inputs and invokes upstream CLI. |
| Safety Invariants | RUN | Selected fixed-version stale-field acceptance forbidden; exact JSON location and process status checked. |
| Liveness / Reachability | NOT_APPLICABLE | Stateless fixture verification; no lifecycle claim. |
| Financial Conservation | NOT_APPLICABLE | No real settlement or financial state transition. |
| Authorization / Capabilities | NOT_APPLICABLE | Receipt authenticity, signer authority, and action permission are not verified. |
| Replay / Idempotency | NOT_APPLICABLE | No external action or redispatch; deterministic test replay is recorded separately. |
| Temporal Lifecycle | NOT_APPLICABLE | No time-dependent application state tested. |
| Crash / Recovery | NOT_APPLICABLE | No persistent runtime or external effect tested. |
| Causal / Ancestral Validity | RUN | Review comments, attributed implementation commit, native controls, fresh outcomes linked. |
| Transition Geometry | NOT_APPLICABLE | Independent stateless fixture scenarios; no operation ordering claim. |
| Negative Control | RUN | Parent accepts both mutations; fix rejects both at expected checks. |
| Stateful / Property Search | NOT_APPLICABLE | Fixed enumerated matrix; no stateful/property exploration claimed. |
| Independent Witness | RUN | Fresh execution of pinned verifier. Maintainer provenance labels and execution remain independently unwitnessed. |
| Trace Integrity | RUN | Source hashes, raw JSON outputs, exit codes, and stderr retained; revised harness blob/SHA-256 and both fresh outputs bound in REPLAY_VERIFICATION.json. |
| Evidence Type / Readiness | RUN | Fresh CLI results distinguished from maintainer comments and simulated settlement metadata. |
| Counterexample Minimization | RUN | Single record field plus one envelope digest; input bytes plus one fixture commitment. Mirrors native controls, not a global minimum proof. |
| Root-Cause Collapse | RUN | Two missing equalities identified in parent and added in fix. |
| Deterministic Replay | RUN | Two fresh revised-harness outputs are committed separately with identical bytes and matching SHA-256 in REPLAY_VERIFICATION.json; original second-run record was not separately committed. |
| Metamorphic / Round-Trip Verification | RUN | Consistent input rebind intentionally remains accepted, bounding the claim; no semantic input-output relation verified. |
| Native Regression | RUN | AT-007g/h mutation shapes executed against native verifier; upstream Bash suite not run. |
| Durable Evidence Reopen / Integrity | RUN | Fresh outputs reopened and compared; script/test/output digests independently checked; original results retained; publication readback remains a separate delivery gate. |
| Verification Debt | RUN | Author attribution/scope confirmed; independent third-party reproduction pending; current releases and full suites not assessed. |
| Active Verification Planning | RUN | Selected tests discriminate parent/fix; no additional production changes proposed. |
| Meaning Trajectory | RUN | Review -> attributed fix -> native controls -> historical replay -> bounded public case. |
| Dormant Patterns / Watchpoints | NOT_APPLICABLE | No latent lifecycle pattern claimed. |
| Temporal / External Replication | RUN | Fresh October replay of September historical versions; no current-release or third-party result. |
| Forward Remediation | NOT_APPLICABLE | Existing historical fix studied; no new upstream remediation. |

## Learning harvest and continuation

**Decision: PROMOTE** this bounded historical case and replay artifact through a separate branch/PR. Applicability: fixture verifiers with duplicated commitments or record identifiers must check the selected equality relationships when those relationships are part of their declared contract. A matching self-contained fixture does not establish external authenticity. This case does not become a universal rule or endorsement of a product.

A separate AI static review agreed with source attribution, mutations, and assertions. It explicitly identified consistently rewritten metadata and retained output as counterevidence against execution/authenticity claims.

Stop and revise the case if a source identity or result differs, or if author feedback identifies an attribution or scope error. Preserve the historical evidence and append corrections through a new commit. Author accuracy review is complete for attribution and technical scope. Remaining continuation: final PR review and independent third-party reproduction. No automated recurring watchpoint is created.


Review learning decision: **PROMOTE** the focused oracle regressions and explicit replay record into this same case PR. Applicability is limited to this pinned verifier comparison and its result assertions; no general security rule or production change is inferred. Merge remains a separate decision.
