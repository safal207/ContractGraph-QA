# Preregistered verification boundary

Recorded before implementing or scoring the new verifier on 2026-09-06.

## Causal spine

- `spineId`: `attenu-delegation-20-2026-09-06`.
- Purpose: independent, reproducible conformance scoring of the **twenty Delegation Token files**, separate from the earlier bundle and observer-envelope proofs.
- Exact subject: `attenu-io/attenu-guard@419f6584c120736688aa946b9c46cfe1c8124292`, direct `tests/vectors/*.json` only.
- ContractGraph-QA base: `f861b934d77e64fd35f768e2a33bb4a00963bc19`.
- Parent contract: `draft-asor-wimse-agent-delegation-chain-01`, sections 3–6, constrained by the published corpus profile and the request below.
- Request: https://github.com/crewAIInc/crewAI/issues/5888#issuecomment-5556680654 .
- `authorizationRef`: user's 2026-09-06 instruction “Rafaela — 20 векторов … независимая проверка в обозначенных границах … го”. Authorizes local implementation, execution and preparation of reviewable evidence. No external comment, upstream modification, merge, or paid engagement is authorized here.
- Scale: standalone, offline verifier and corpus harness; no production integration.
- Time: explicit corpus `now`, in NumericDate seconds; collection time is separate. No real clock in semantic verification.
- Past: prior 18/18 observer-envelope result is independent historical context, not coverage of these twenty files.
- Present: corpus and normative sources identified; verification has **not run** at this registration point.
- Intended transition: frozen bytes → independently computed verdicts → comparison with declared expectations → reproducible report and reviewable commit.
- Selected work location: new proof directory; no existing verifier or production package modifications.

## Acceptance criteria and invariants

1. Freeze the exact twenty file names, sizes and SHA-256 digests before scoring. Reject missing, changed, added, or duplicate input identities before accepting a corpus result.
2. Read the files as data; do not run the upstream generator, import the upstream runtime, or use its verification output as the independent verdict.
3. Use a standalone Node.js implementation with built-in crypto and ECMAScript number serialization. Input to its semantic API is only `(tokens, signer, now)`, never the filename, description or expected result.
4. Implement the corpus boundary of steps 1–5: strict JSON/JCS, HS256 signatures with the supplied public test signer, exact parent Signing Input commitment, depth, scope/constraint subsumption and time.
5. Score **both** accept/reject and the declared rejection token. Denominators stay at 20; exceptions, gaps and mismatches never become passes.
6. Preserve the first actual score and any later correction. Never predeclare 20/20 or rename evidence to conceal a mismatch.
7. Regenerate the machine report byte-for-byte. Pin verifier, harness, plan and source identities. Reopen committed evidence and repeat the proof.
8. Test the observation boundary: always-accept and always-reject controls must fail scoring; expectation metadata must not affect the verifier; changed corpus bytes must fail the artifact gate. Additional checks stay local and synthetic.
9. Check replay determinism and time boundaries using the existing valid chain, without creating a live target or an offensive workflow.

## Declared profile choices and debt before implementation

- All twenty files use **HS256 with an intentionally published test key**. This does not exercise the draft's required production Ed25519 support or establish an asymmetric trust boundary.
- One signer is used across the chain. Key discovery, issuer-to-key binding across organizations and multiple signers are outside this run.
- Steps 6 (holder proof), 7 (revocation) and 8 (authorization of an actual action) are NOT_RUN/outside scope. `cnf` is absent in the valid corpus; `aud` is null. Acceptance here cannot be reported as full JWT access-token or full draft conformance.
- Children omit `del_max_depth`. For this corpus profile an omitted value inherits the prior limit; an explicit value cannot increase it. This is a declared corpus interpretation, not a new normative requirement.
- Integral numbers outside ±(2**53−1) are rejected as required by this corpus. This is a stricter domain than general RFC 8785 binary64 serialization.
- `rank` uses the declared egress order `none < internal < any`. Arbitrary rank registries and ambiguous cross-type constraint relationships remain unsupported.
- Error vocabulary comes from the corpus contract, not an upstream runtime call. Nonmonotonic absolute expiry maps to `expired` even when detected during subsumption.
- Strict canonical JSON needs parsing before semantic/signature validation; lexical rejection is distinct from a cryptographic result.
- No production implementation defects are being sought or reproduced. No network at scoring time, live service calls, token minting, fuzz campaign or exploitation.

## Verification route and stop conditions

Orientation is BALANCED for the limited task, not a safety verdict. The source expectations are an external oracle but not proof of corpus completeness. Independent verification means separately authored code and a different language/runtime; it does not mean a blinded study or independent human review.

Read source documentation and fixture bytes, implement the verifier, preserve first score, execute focused tests, replay from a fresh process, check artifact identity, and document every applicable AGENTS.md capability with real states. Stop after those gates resolve the stated claim. A mismatch stays visible and is classified before any correction. Broad state search, production native suites and unrelated financial models do not apply to this read-only fixture scorer.

External publication is a separate decision under `.cursor/rules/scoped-verdict-evidence-routing.mdc`; prepare the complete work first. Hosted CI and third-party reruns are NOT_RUN until they actually execute. Learning harvest may be NO_PROMOTION or DEFER; no repository rules will be silently changed.
