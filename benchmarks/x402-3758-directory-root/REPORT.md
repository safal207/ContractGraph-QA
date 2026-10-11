# x402 #3758: independent directory.root recalculation

Verdict: **PASS_WITHIN_BOUND** for the published epoch-1 directory's §7.2 digest construction.
The production snapshot independently recalculates to
`9daec3d9df75826056ba182b0c176e6684b85aab723a59efbd4d75f4c999e538`.
No directory-generation defect is established by this case.

## Exact subject and authority

- Specification/reference: [johnInarti/x402@4d3f2387bd3f2db8007cca324ef8dea23264c248](https://github.com/johnInarti/x402/tree/4d3f2387bd3f2db8007cca324ef8dea23264c248).
  The branch resolved to that SHA initially and on final GET. Commit date:
  2026-10-10T09:56:55Z.
- Host base: ContractGraph-QA `f13e586ea9118e026c69438b8c93d0585b8e38ba`.
  This additive suite has its own branch, separate from [PR #211](https://github.com/safal207/ContractGraph-QA/pull/211)'s synthetic buyer-composition controls.
- Directory: [public catalogue](https://fractalai.net.co/.well-known/x402-receipt-keys), epoch 1, issuer `https://fractalai.net.co`.
- Receipt: [public receipt](https://fractalai.net.co/x402/receipts/77795afae30c36075ed22e6593e28d0b4d7ae24c23acebfdcf8e0c0dc494b5fb).
- Causal spine: `X402-3758-DIRECTORY-ROOT-20261011`; authorizationRef:
  `USER-ACTION-X402-ROOT-20261011` (the user requested independent verification, a focused improvement to their own tests and, if warranted, publication in #3758). No merge or production action is part of this engagement.
- Captured on 2026-10-11 UTC. The repeat HTTP response is dated 17:10:25Z and is byte-identical to the first direct HTTP capture.
  Earlier structured extraction agreed after removing its local save's trailing newline; direct HTTP bytes are the retained fixture authority.

Raw byte identities:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `fixtures/directory.json` | 10563 | `eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f` |
| `fixtures/receipt.json` | 5411 | `91c153cb2bd6e8789209f896783d669e7c3a4f14230af911a370c380418fb654` |
| Normative canonical projection | 5906 | `9daec3d9df75826056ba182b0c176e6684b85aab723a59efbd4d75f4c999e538` |

## Normative construction and implementation

[§7.2](https://github.com/johnInarti/x402/blob/4d3f2387bd3f2db8007cca324ef8dea23264c248/specs/extensions/delivery-receipt.md#72-format) specifies:

```text
lowercase_hex(SHA-256(JCS({
  spec, issuer, epoch, prevRoot, publishedAt,
  governanceKeys: sort by alg,
  keys: sort by kid
})))
```

This is a projection of **seven fields**. Both `root` and `signatures` are excluded.
Array ordering is applied before object-member canonicalization.

[computeDirectoryRoot](https://github.com/johnInarti/x402/blob/4d3f2387bd3f2db8007cca324ef8dea23264c248/typescript/packages/extensions/src/delivery-receipt/directory.ts)
explicitly selects those seven fields, copies and sorts the two arrays, canonicalizes and hashes UTF-8 bytes.
The builder uses that function; the reference verifier recomputes the root before checking governance signatures.
The implementation's canonicalizer rejects unsupported numeric values and invalid Unicode; this fixture contains only ASCII strings and safe integers, so the independently guarded Python serializer is sufficient for this exact input.
The Python oracle is not a general RFC 8785 implementation.

Static source snapshots were checked against immutable Git blob identities.
Specification SHA-256: `409c1d9f9f68a1e9f527b2c68622c81ddfb00d598fd1e273e97fc82e58a859cc`;
directory implementation SHA-256: `229ff3defad5fee4606728c2e090d7a1d0f9c9b67f20d0386ddaf8a58f6b2185`.
Fetched project code was not executed. Matching the reference source is not a deployed-build attestation.

## Comparison with the external report

[External comment 6103479775](https://github.com/x402-foundation/x402/issues/3758#issuecomment-6103479775)
was created/last updated at 2026-10-10T23:51:08Z, after the pinned source commit.
All five reported digest prefixes reproduce on the captured directory; the full independently computed digests are:

| Trial preimage | Independently reproduced SHA-256 | Difference from §7.2 |
|---|---|---|
| Document without signatures | `8e1a7c87d6cd1bf355b8abdf980cfba00dcfa8b3b7f26f1c4ffc797f6f0682d9` | Still includes `root`. |
| Whole document | `eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f` | Includes `root` and `signatures`. |
| `keys` | `35c3b77cba0189961d74694ab5769dc935345ca5ff781b443125c095b77b7e93` | Omits the six other fields. |
| `governanceKeys` | `f7d6db30c01f3d00617595794dc27a34e4ba3b03832c1ede9222c2f561c1b309` | Omits the six other fields. |
| `{epoch,keys,governanceKeys}` | `6cb9ae03d3f459e9ddc4b7f7c642ebc75b907c01e9e4e90405178f1e8572e016` | Omits `spec`, `issuer`, `prevRoot`, `publishedAt`. |
| Normative seven-field projection | `9daec3d9df75826056ba182b0c176e6684b85aab723a59efbd4d75f4c999e538` | Matches the published root. |

Adjudication: **CONFIRMED** positive digest reproduction; **NOT_CONFIRMED** generation-defect hypothesis.
The documented root-check attempts used non-normative preimages. That explains their failure.
The unseen external verifier source was not inspected, so this does not establish a code defect in that verifier.
No root-construction ambiguity was identified for this snapshot and pinned specification.
A worked directory projection vector could improve discoverability without changing the normative formula.

## Test scope and integration

The existing native tests statically inspected cover generated-directory verification, key-status tampering and fixture regeneration with the reference implementation.
This new suite contributes a public production snapshot with an independent preimage oracle, complete seven-field perturbations and permutation checks.
It imports no upstream implementation or production dependency and has no wallet, RPC or paid endpoint calls.
See `README.md`, `PLAN.md` and the retained execution results for reproduction.

Root comparison is distinct from directory shape, key trust, signature validation and delivery.
Changing a signature leaves the root preimage unchanged; that is not evidence that the signature remains valid.
Changing the published `root` leaves the computed hash unchanged and must fail their equality comparison.

## Evidence boundaries

- Ed25519 mathematical verification under keys published in this snapshot does not verify ML-DSA. ML-DSA verification is **NOT_RUN** by this suite, regardless of runtime support.
- A self-published governance key is not independently pinned identity or issuer authority.
- `receipt.payload.keyDirectoryDigest == directory.root` is only equality. Here the additional independent preimage computation supports the root construction.
- Receipt ID/signatures bind the stated payload; they do not establish factual response delivery.
  The paid response body was not available, so `delivery.sha256` is **NOT_RUN**.
- Polygon settlement was reported by the external researcher; this engagement does not independently replay an RPC or validate the transfer. No fresh on-chain verdict is issued.
- The `PAYMENT-RESPONSE` raw reference envelope was not captured. Its external `digest` binding is outside this check.
- Epoch archives, revocation freshness, chain completeness, governance handover, issuer/payee relationship and deployed executable provenance are outside this digest-focused scope.
- Prior PR #211 uses synthetic settlements. It neither validates this production receipt nor gains a production payment conclusion from these tests.

## Capability/debt matrix

“RUN” below describes the bounded checks actually performed, not invocation of every ContractGraph-QA CLI or whole-protocol conformance.

| Capability | Status | Evidence or reason |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Immutable source SHA, public fixture byte hashes, initial/final ref checks. |
| Preregistered Verification Plan | RUN | PLAN recorded before new suite execution; exploratory calculations are separately identified. |
| Orientation Center | RUN | BALANCED for digest construction; body/trust/chain debt retained. |
| Native Mapping / Adapter Review | RUN | Static §7.2 ↔ computeDirectoryRoot ↔ external preimages mapping. |
| Safety Invariants | RUN | Covered field changes cannot retain accepted original root. |
| Liveness / Reachability | NOT_APPLICABLE | No state machine or custodial recovery exercised. |
| Financial Conservation | NOT_APPLICABLE | No payment or value flow executed. |
| Authorization / Capabilities | SKIPPED_WITH_REASON | Issuer authority and pinned-key trust not established; signature mathematics is separate. |
| Replay / Idempotency | RUN | Deterministic pure-function replay and input nonmutation only; no payment retry claim. |
| Temporal Lifecycle | SKIPPED_WITH_REASON | Live epoch/revocation transition verification exceeds snapshot scope. |
| Crash / Recovery | NOT_APPLICABLE | No persistent stateful target is executed. |
| Causal / Ancestral Validity | RUN | Exact normative preimage discriminates trial-projection explanation from generator-defect hypothesis. |
| Transition Geometry | RUN | Reordering members and arrays challenges permutation invariance; no lifecycle commutativity claim. |
| Negative Control | RUN | Seven-field changes, nested changes and five non-normative projections. |
| Stateful / Property Search | RUN | Bounded deterministic permutation/mutation exploration only; stateful search not applicable. |
| Independent Witness | RUN | Separately implemented guarded Python preimage matches Node byte-for-byte; both consume the same snapshot. |
| Trace Integrity | RUN | Raw byte hashes and execution logs; fixture authenticity/truth not inferred from hashes. |
| Evidence Type / Readiness | RUN | Reproduced digest observation; no full production-correctness conclusion. |
| Counterexample Minimization | NOT_APPLICABLE | No production counterexample; one-change negative controls are test inputs. |
| Root-Cause Collapse | RUN | Removing non-normative projection choice resolves discrepancy on identical data. |
| Deterministic Replay | RUN | Fresh-process suite reruns and independent preimage calculation. |
| Metamorphic / Round-Trip Verification | RUN | Permutation invariance, serialization and unchanged-input checks. |
| Native Regression | NOT_RUN | Upstream source inspected statically; no upstream defect/fix proposed. |
| Durable Evidence Reopen / Integrity | RUN | Frozen files reopened by tests and manifest hashes checked. |
| Verification Debt | RUN | Explicit ML-DSA/body/chain/trust/RPC/deployment limitations. |
| Active Verification Planning | RUN | Smallest next check is external researcher's rerun of exact projection. |
| Meaning Trajectory | RUN | Signal → five digests reproduced → normative recomputation → bounded clarification. |
| Dormant Patterns / Watchpoints | RUN | Future source/epoch changes require fresh capture; old result remains historical. |
| Temporal / External Replication | RUN | Two direct HTTP captures agree; independent source inspection; no future stability claim. |
| Forward Remediation | NOT_APPLICABLE | No production remediation; original external observation remains preserved. |

Learning decision: **PROMOTE** the bounded regression fixture and projection oracle through a focused draft PR.
Reusable lesson: digest equality is weaker than reproducing the normative preimage.
Applicability: this exact §7.2 seven-field format, within the explicit serializer domain.
False-positive risk: interpreting root success as complete directory/receipt trust or delivery verification.
Publication authority is the separate user request above; this decision grants no merge authority.

## Executed checks

Two fresh Node 24.19.0 processes each passed all 43 tests (0 failures, 0 skipped),
including the separately launched Python byte oracle. Retained TAP results are
`evidence/attempt-1.tap` and `evidence/attempt-2.tap`; the standalone oracle result
is `evidence/python-oracle.json`. Python 3.12.14 emitted 5906 preimage bytes with
the matching root. Workflow YAML parsed with its explicit Node 22/24 matrix.
Dedicated remote CI is pending at packet creation; its final status must be
checked on the exact draft-PR commit, separately from these local observations.

AI-assisted implementation with separate static inspection and test review.
