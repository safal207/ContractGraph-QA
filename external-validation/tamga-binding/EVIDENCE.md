# Evidence and applicability — Tamga binding case

## Exact subject and authority

- Subject: `goun7/tamga-protocol`, parent `7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b` -> fix `c62d4a822d7e3546931197905e137d0eb6fb490e`.
- Hosting repository provenance: `safal207/ContractGraph-QA@f13e586ea9118e026c69438b8c93d0585b8e38ba`; CGQA engine **NOT_RUN**.
- Spine: `tamga-binding-case-20261011`.
- Authorization reference: `user-go-20261011T001058+0300`, approving the preceding case-publication and scoped author-review proposal. Publication route is a separate branch and draft PR; merge is a separate decision.
- Interpretation: `PASS_WITHIN_BOUND` for the four-scenario historical comparison. Author accuracy review **PENDING**.

## Preregistered contract and observed result

Before execution, the matrix required original acceptance on both versions, parent acceptance/fix rejection of each selected stale-field mutation at the expected location, and acceptance of a consistently rewritten fixture on both versions. Unexpected JSON, return code, stderr, identity, or branch outcomes prevent the corresponding claim.

The same fixed-version committed fixture and Keccak dependency are used for both verifiers. The fix's parent relation and two-file diff show that these shared files are unchanged across the selected pair. The harness invokes exact verifier source bytes; it does not substitute a reimplemented verifier. Its independent assertions inspect `ok`, `where`, return code, and absence of stderr.

Observed: **8/8 expected outcomes**, repeated with identical result JSON. This means four scenarios across two versions. The accepted consistent rewrite is an intentional limitation control, not a successful security test. It updates the input, fixture commitment, charge input hash, record hash, and envelope hash while retaining the prior output bytes.

Raw outputs and all six input source identities are in [results.json](results.json). Six Git blob identities are checked before every run. Source identities and raw results are committed with this case; source SHA-256 and sizes are also retained in the results.

## Execution environment and omissions

Python 3.12.14; inspected stdlib-only harness plus upstream verifier and Keccak module. Execution used temporary synthetic fixture copies, isolated Python mode, no site packages, sanitized child environments, resource limits, and inherited external seccomp restrictions blocking network sockets and selected privileged syscalls. A socket creation probe confirmed denial. Filesystem namespace isolation was unavailable; the containment claim is limited to those restrictions.

The published reproducer does not install this local containment profile. Review fetched code before execution in your own environment. Its initial download needs network access; the verifier invocations operate on local bytes. No provider call or payment is performed.

The full Tamga runtime, complete ledger verification, trusted anchor/signature verification, upstream full suite, and CGQA engine were **NOT_RUN**. The maintainer's historical report of 21 controls is not counted as our execution result. Source labels `observed`, `simulated`, and `derived` describe upstream fixture metadata, not an independently witnessed agent run.

## Attribution and claim boundary

- [Initial author acknowledgement of review](https://github.com/x402-foundation/x402/issues/3379#issuecomment-5560621478).
- [Author links the fix, native controls, and adopted scope](https://github.com/x402-foundation/x402/issues/3379#issuecomment-5562472232).
- [Attributed implementation commit](https://github.com/goun7/tamga-protocol/commit/c62d4a822d7e3546931197905e137d0eb6fb490e).
- [Native control source at the fixed revision](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/tests/at007_pairing_fixture.sh).

Review: Alexey Safonov (`safal207`). Implementation/native regression authorship: `goun7`. The phrase “updated fixture commitment” is intentional: the mutation recomputes hash metadata and does not digitally sign anything.

The compared verifier checks supplied fixture consistency. It does not authenticate receipt provenance, establish global ledger completeness, verify input-to-output execution semantics, or establish execution, settlement finality, buyer receipt/acceptance, effect count, or exactly-once. A complete consistent rewrite remains accepted. This is not an attack on a separate ledger verifier or a claim about current Tamga/x402 releases.

## Capability classification

| Capability | Status | Evidence or reason |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Pinned parent/fix; six source blobs checked before invocation. |
| Preregistered Verification Plan | RUN | Four scenarios and exact acceptance/failure locations recorded before execution. |
| Orientation Center | RUN | Historical consistency claim resolved; author review and broader claims remain outside the result. |
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
| Trace Integrity | RUN | Source hashes, raw JSON outputs, exit codes, and stderr retained; deterministic replay identical. |
| Evidence Type / Readiness | RUN | Fresh CLI results distinguished from maintainer comments and simulated settlement metadata. |
| Counterexample Minimization | RUN | Single record field plus one envelope digest; input bytes plus one fixture commitment. Mirrors native controls, not a global minimum proof. |
| Root-Cause Collapse | RUN | Two missing equalities identified in parent and added in fix. |
| Deterministic Replay | RUN | Second eight-invocation run matched first result byte-for-byte. |
| Metamorphic / Round-Trip Verification | RUN | Consistent input rebind intentionally remains accepted, bounding the claim; no semantic input-output relation verified. |
| Native Regression | RUN | AT-007g/h mutation shapes executed against native verifier; upstream Bash suite not run. |
| Durable Evidence Reopen / Integrity | RUN | Saved result reopened and compared with repeat; publication readback is a separate delivery gate. |
| Verification Debt | RUN | Author accuracy review and third-party reproduction pending; current releases and full suites not assessed. |
| Active Verification Planning | RUN | Selected tests discriminate parent/fix; no additional production changes proposed. |
| Meaning Trajectory | RUN | Review -> attributed fix -> native controls -> historical replay -> bounded public case. |
| Dormant Patterns / Watchpoints | NOT_APPLICABLE | No latent lifecycle pattern claimed. |
| Temporal / External Replication | RUN | Fresh October replay of September historical versions; no current-release or third-party result. |
| Forward Remediation | NOT_APPLICABLE | Existing historical fix studied; no new upstream remediation. |

## Learning harvest and continuation

**Decision: PROMOTE** this bounded historical case and replay artifact through a separate branch/PR. Applicability: fixture verifiers with duplicated commitments or record identifiers must check the selected equality relationships when those relationships are part of their declared contract. A matching self-contained fixture does not establish external authenticity. This case does not become a universal rule or endorsement of a product.

A separate AI static review agreed with source attribution, mutations, and assertions. It explicitly identified consistently rewritten metadata and retained output as counterevidence against execution/authenticity claims.

Stop and revise the case if a source identity or result differs, or if author feedback identifies an attribution or scope error. Preserve the historical evidence and append corrections through a new commit. Remaining continuation: author accuracy review and independent third-party reproduction. No automated recurring watchpoint is created.

