# Independent Delegation Token run — 20/20

**Observed result: 20/20 AGREE, on the first run and deterministic replay.** Seven accepting files and thirteen rejecting files match both the verdict and declared rejection reason. All eight rejection tokens in the corpus are exercised. The bounded verdict is `PASS_WITHIN_BOUND`.

This answers [Rafaela's request](https://github.com/crewAIInc/crewAI/issues/5888#issuecomment-5556680654) for an outside run of the **Delegation Token** corpus. It is separate from the earlier 18-case observer-envelope and 17-case evidence-bundle proofs.

## Scope stated before the result

This run covers the corpus profile of **draft-asor-wimse-agent-delegation-chain-01 §6, steps 1–5**, with one signer for the complete chain. Step 6 (DPoP holder proof), step 7 (Token Status List) and step 8 (authorization of an actual action) are outside scope and NOT_RUN.

All twenty files use HS256 with an intentionally published test key. The independent implementation uses Node.js built-in HMAC/SHA-256 and ECMAScript serialization. **It does not test production Ed25519, asymmetric key trust, or full JWT access-token conformance.** This is an offline interoperability scorer, not a production authorization service.

## Exact subjects

| Subject | Immutable identity |
|---|---|
| Upstream | `attenu-io/attenu-guard@419f6584c120736688aa946b9c46cfe1c8124292` |
| Inputs | Exactly twenty direct `tests/vectors/*.json` files, 30,695 bytes total |
| Other upstream source copy | `src/attenu_guard/vectors/`, at the same commit |
| ContractGraph-QA base | `f861b934d77e64fd35f768e2a33bb4a00963bc19` |
| First local run / verifier commit | `921173318176165a0d16e8b81c6913dbda4aa472` |
| Published, byte-identical verifier snapshot | `cb080a795f26bd1c0417d32cdd297960511cad88` |
| Verifier SHA-256 | `0d0101d0b32892938a36634e55b6f986fb85409c8444a1104e72f015f3ee0389` |
| Harness SHA-256 | `de8bf6534251881f93f492cdf08ccec70464d34101dc28a7f74923779dd2b1ae` |
| Source manifest SHA-256 | `d141d80ff3af8553df38ac90da5a85cd9880b887574276e1b521a7d0217d0556` |
| Generated report SHA-256 | `33c5f099e014a8847a1ec8f86d489e1fa7d8590fc96b49786a6fd85920be34a3` |

[source-pins.json](./source-pins.json) lists every input's name, size, hash and expectation, plus hashes of reviewed source documents. Local fixtures match **both upstream repository copies byte-for-byte**. A released wheel and the TypeScript distribution were not downloaded or scored here.

The initial and final upstream identities matched. `collection.json` preserves the initial pre-execution snapshot, not the final score. `validation.json` records actual commands and the local runtime. `artifacts.json` inventories the final proof; its revision anchor is the Git commit containing that manifest.

## Independence and method

[verifier.mjs](./verifier.mjs) was separately authored from the draft, corpus README, fixture descriptions and decoded data. Only the module documentation at the top of upstream `wire.py` was read for its boundary. No upstream verifier or generator implementation was copied, imported, installed or executed. The earlier Python proof is not a dependency. This is code independence, not blinded development or independent human review.

The semantic API receives only `(tokens, signer, now)`. It cannot read case names, descriptions or expectations. [run-proof.mjs](./run-proof.mjs) separately freezes identity, calls that API and compares verdict plus reason against the published oracle. Unexpected exceptions become `ERROR`, never expected rejections.

Checks cover strict JSON, duplicate names, finite/safe-domain numbers, Unicode, byte-for-byte JCS, test-signer matching and HMAC signatures, exact parent Signing Input hashing with constant-time digest comparison, positional depth, scope/constraint narrowing and explicit time. JSON parsing precedes signature verification. The informational `c14n` marker is not required.

No fixture or expected outcome was edited. The verifier and harness are unchanged since the first run. [first-run.json](./first-run.json) and [report.json](./report.json) are identical bytes.

## Results

| Expected outcome | Files | Actual |
|---|---:|---|
| `accept` | 7 | 7 accepting |
| `not_narrower` | 4 | 4 matching rejections |
| `malformed` | 3 | 3 matching rejections |
| `signature_invalid` | 1 | 1 matching rejection |
| `par_hash_mismatch` | 1 | 1 matching rejection |
| `depth_invalid` | 1 | 1 matching rejection |
| `expired` | 1 | 1 matching rejection |
| `non_finite` | 1 | 1 matching rejection |
| `duplicate_member` | 1 | 1 matching rejection |

The report includes each file, input hash, expectation, actual result, first failing stage, token position and completed checks. Stage/position are diagnostics; verdict and reason are the corpus scoring obligations.

**Eleven focused native tests passed.** Constant-answer controls fail the scorer: always-accept scores 7/20; always-reject with `not_narrower` scores 4/20 despite matching thirteen rejection booleans. All twenty simulated runtime errors remain ERROR. Changing names, descriptions and expectations leaves actual verification unchanged. Changed, missing, extra and symlinked input files fail the artifact gate.

Further tests cover JSON edge cases, JCS round-trip, numeric-looking property ordering, scope direction and six constraint comparison directions. These helper tests do not expand the corpus denominator. Replaying the existing valid chain at `now=299,300,301,3601,0,301` gives accept, accept, reject, reject, accept, reject while preserving inputs. The inclusive expiry boundary follows draft-01, not a general JWT time policy. Reversing corpus iteration order changes no individual result.

CGQA's own subject-freeze capability reopens the input and implementation/plan files; its changed-digest control is `STALE_SUBJECT`. The native durable-manifest verifier checks retained expectations after reopening.

## Profile interpretations and remaining coverage

1. Valid fixtures omit `cnf` and set `aud` to null. Acceptance establishes neither holder possession nor audience policy.
2. Children omit `del_max_depth`. This implementation inherits an omitted limit and rejects an explicit increase. Reduced child-limit semantics are not covered by these twenty files.
3. Integral numbers outside ±(2**53−1) are rejected. This is a corpus restriction; general RFC 8785 supports a larger binary64 domain.
4. Rank is supported only for the documented egress order `none < internal < any`. Other rank registries, multiple authorization details, repeated constraint dimensions and cross-kind relations are unsupported. Unknown profiles fail closed.
5. Lexical `non_finite` and `duplicate_member` failures precede signatures. Increasing absolute expiry maps to the corpus reason `expired`, even when detected during subsumption.
6. The corpus exercises `max` and egress rank. Direct helper tests exercise all six directions, but this is not signed-token coverage of all constraint types, dropped constraints, `nbf`, narrowed child depth, algorithm/key transitions or JOSE extensions. JSON nesting has a local bound of 128.
7. The upstream README describes the exponent control as including `1e16`; the pinned file and its own description use `1e15`. The scorer uses the actual bytes. This is documentation drift, not a failing vector.
8. The IETF draft is work in progress. There is no claim of endorsement, certification, production audit, completeness or universal verifier safety.

No corpus mismatch required a repair, and no production defect was investigated. These gaps stay visible for a future corpus revision.

## Reproduce

Node.js **24.19.0**, no npm dependencies. From the repository root:

~~~sh
node --test proofs/attenu-delegation-20-independent/verify.test.mjs
node proofs/attenu-delegation-20-independent/run-proof.mjs \
  --check proofs/attenu-delegation-20-independent/report.json
node proofs/attenu-delegation-20-independent/check-artifacts.mjs
python3 proofs/attenu-delegation-20-independent/cgqa-checks.py
~~~

Python 3.12.13 was used for native CGQA identity/reopen checks; the Node scorer does not depend on Python. To repeat source identity checking, check out upstream at the pinned commit, then run:

~~~sh
node proofs/attenu-delegation-20-independent/check-sources.mjs /path/to/attenu-guard
~~~

This reads upstream without executing its code. The `check-artifacts.mjs --write` option regenerates expectations for a maintainer; reviewers should use the read-only command above.

The [workflow](../../.github/workflows/attenu-delegation-proof.yml) repeats source checks, native tests, artifact verification and deterministic scoring. At the original local handoff, **hosted CI was NOT_RUN**. See [PUBLICATION.md](./PUBLICATION.md) for the subsequent publication authority and commit mapping, and the PR checks for live CI status. Human review, an upstream README pin and an external rerun are separate states.

## Completion and learning

[REVIEW.md](./REVIEW.md) contains the required capability matrix, completion answers and debt. [PLAN.md](./PLAN.md) preserves the pre-execution boundary. [PR.md](./PR.md) is the prepared PR body.

Learning: **DEFER** profile questions and the small README drift for maintainer consideration; **NO_PROMOTION** of repository rules or general security claims. The user subsequently authorized publication of this proof branch and PR; PUBLICATION.md preserves that transition. No message was sent to Rafaela; no upstream files were changed.

Vendored fixtures remain unchanged Apache-2.0 upstream data; license and notice are retained in `UPSTREAM-LICENSE` and `UPSTREAM-NOTICE`. New code uses the repository's Apache-2.0 license.
