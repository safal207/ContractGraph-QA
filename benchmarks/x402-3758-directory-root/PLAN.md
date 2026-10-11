# Preregistered verification plan

Recorded before execution of this suite on 2026-10-11.

## Causal spine

- `spineId`: `X402-3758-DIRECTORY-ROOT-20261011`.
- Exact subject: the frozen HTTP directory response from
  `https://fractalai.net.co/.well-known/x402-receipt-keys`, epoch 1, publishedAt
  1791653681, raw SHA-256
  `eeb8badd5ad01dd622717651146bed7b9f138e69dd3a3a096268c13ff7217f2f`.
- Parent contract: independently recompute §7.2 before attributing a root
  mismatch to the producer; keep commitment checks separate from trust,
  delivery, and payment-retry claims.
- Normative subject: `johnInarti/x402` commit
  `4d3f2387bd3f2db8007cca324ef8dea23264c248`,
  `specs/extensions/delivery-receipt.md` §7.2; implementation mapping is
  `typescript/packages/extensions/src/delivery-receipt/directory.ts`
  `computeDirectoryRoot` and `encoding.ts` `canonicalJson`.
- CGQA base: `f13e586ea9118e026c69438b8c93d0585b8e38ba`.
- Model: `verify.mjs`; independent serializer/oracle: `oracle.py`.
- Time: historical fetched artifact, not a live freshness check; lifecycle
  fields are commitment inputs, not a simulated key-rotation state machine.
- Symptom: independent comment 6103479775 tried five preimages without the
  exact normative seven-field projection. Its equality result alone did not
  constitute a root recomputation.
- Navigation: down to exact projection and encoding, sideways to independent
  serialization, up to the limited evidentiary claim.
- Authority: user request authorizes local independent testing and a focused
  own-test improvement; this subtask does not publish, commit, push, merge,
  alter upstream, pay the route, or fetch during tests.
- `authorizationRef`: `USER-ACTION-X402-ROOT-20261011`, delegated local test scope.
- Selected improvement: a new, separately named offline fixture suite. Do not
  modify `benchmarks/x402-3758` or the synthetic repayment evidence in PR #211.

## Orientation center

`BALANCED` for this narrow commitment experiment, with unresolved wider
verification debt. Evidence is the frozen published artifact, the versioned
normative formula, the producer's matching explicit projection, and the
researcher's listed alternatives. The published root remains the value under
test, never the oracle. Source provenance does not independently establish
issuer trust or the truth of a paid-delivery claim.

## Acceptance criteria and search bounds

1. Preserve raw fixture hashes; independently produce the seven-field
   projection `{spec,issuer,epoch,prevRoot,publishedAt,governanceKeys,keys}`.
   Sort governance keys by `alg` and receipt keys by `kid` before canonicalizing.
2. Node and guarded Python serializers must emit byte-identical preimages and
   compute the expected root independently. Neither imports producer code.
3. Positive cases: frozen epoch, recursive object-member reordering, both
   array order permutations, repeated calculation, unchanged input, and
   deterministic child-process reopen.
4. Negative controls: mutate every top-level committed field and each key's
   nested identity, key material, usage, status and lifecycle fields; reject
   missing committed top-level fields; distinguish absent nested members from
   explicit null. Check both governance-key algorithms and public keys.
5. Reproduce all five researcher alternatives and establish that their
   digests differ from the normative root for this fixture.
6. `root` and `signatures` are excluded from the commitment; changing published
   `root` must fail root equality. Signature mutation retaining the root is
   not a signature PASS: separately require Ed25519 one-bit message/signature
   rejection.
7. Auxiliary receipt checks: independently compute receiptId, compare its
   directory digest and epoch to the fixture, and verify the receipt and
   directory Ed25519 signatures using Node's built-in crypto.
8. Constrain both encoders to ASCII strings/keys and safe integers (plus
   booleans/null/arrays/plain objects), reject unsupported values. This is an
   RFC 8785-compatible fixture domain, not a general JCS implementation and
   not whole-protocol conformance validation.
9. No network or dependency installation inside test commands. Fixed cases,
   finite per-field mutations and permutations, no probabilistic search.

## Stop conditions, debt and learning

If exact fixture identity or independent byte comparison fails, stop the
root conclusion and report `INCONCLUSIVE` or the reproducible discrepancy.
No production defect is claimed merely because incomplete projections fail.
No native producer regression is required absent a demonstrated producer bug.

ML-DSA verification, full schema/key-lifecycle/chain/rollback validation,
out-of-band issuer trust, Polygon RPC verification, and paid response body
verification are outside this suite and remain `NOT_RUN`. The Python witness
has a different serialization implementation but consumes the same frozen
observation, so it does not provide independent data-collection provenance.
No current-time freshness or later epoch replication is performed.

Watchpoint: a future epoch or spec change requires a new snapshot with its own
identity, an updated normative mapping, and full trust/chain validation before
carrying results forward. Decision pending execution: promote only the narrow
projection/mutation fixture, defer all untested protocol claims.
