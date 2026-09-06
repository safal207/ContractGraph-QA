The twenty Attenu Delegation Token vectors had no pinned run from an independent standalone verifier outside another delegation protocol. This adds a separately authored Node.js scorer, frozen source data and reproducible evidence for that specific corpus.

The first run scores **20/20**: seven accepts and thirteen rejections, matching all eight declared rejection reason tokens. The verifier and harness have not changed since that run; the report regenerates byte-for-byte.

Scope: draft-asor-wimse-agent-delegation-chain-01 steps 1–5 under the corpus's single-signer HS256 test profile. DPoP, revocation, actual action authorization and production Ed25519 are not tested. Null audience, omitted holder claims, inherited child depth limits and the restricted numeric domain are explicit qualifications.

- Upstream: `attenu-io/attenu-guard@419f6584c120736688aa946b9c46cfe1c8124292`.
- Published verifier snapshot: `cb080a795f26bd1c0417d32cdd297960511cad88`, whose tree is identical to first local run commit `921173318176165a0d16e8b81c6913dbda4aa472`.
- Twenty original files: 30,695 bytes, individually hashed; vendored and both upstream source copies match.
- Local validation: eleven native Node tests, scorer negative controls, deterministic replay, source identity and artifact integrity.
- A pinned, read-only CI workflow is included; hosted execution is pending.

The proof includes preregistration, independence statement, per-case report, command evidence, capability matrix and limits. Existing production code and earlier proof results are unchanged.

This is interoperability evidence for a frozen corpus, not general draft conformance, a production security audit or certification.
