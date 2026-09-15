# Proof Identity / Signed Admission v0.3

This directory adds cryptographic identity binding to the external-proof intake layer.

Pipeline:

`submission signature -> key registry -> v0.2 evidence admission -> platform decision signature -> registry candidate`

## Three different identities

v0.3 deliberately keeps these roles separate:

1. **Source producer** — the repository/artifact named by `source`.
2. **Submission signer** — the holder of the private key that signed the submission manifest.
3. **Platform signer** — the holder of the private key that signed the admission decision.

A signature for one role is not evidence for another role.

The first fixture therefore uses the real external source
`mstevens843/crashpoint`, but the signed submission is made by the synthetic
fixture identity `cgqa-fixture-submitter`. Nothing in v0.3 claims that
`mstevens843` signed the fixture.

## Canonical signed bytes

The signed submission payload is the complete v0.3 manifest **without** the
`signature` object, encoded as UTF-8 JSON with:

- object keys sorted lexicographically;
- separators `,` and `:` with no extra whitespace;
- Unicode emitted directly (`ensure_ascii=false`).

This encoding is named **CGQA canonical JSON v0.3**. It is intentionally scoped
to this manifest format and is not claimed to be RFC 8785 JCS.

The signature envelope stores both:

- SHA-256 of those canonical payload bytes;
- detached Ed25519 signature over the exact same bytes.

## Key registry

`keys.v0.3.json` binds a `key_id` to:

- Ed25519 public key;
- SPKI SHA-256 fingerprint;
- allowed purpose (`external_submission` or `admission_decision`);
- status;
- declared identity binding.

The fixture keys are **test-only identities**. Their registry entries do not
prove a GitHub account, legal identity, organization, source authorship, or
external PKI binding.

Private keys are not committed.

## Admission flow

`process_signed_submission.py` verifies the submission signature before invoking
the merged v0.2 intake processor. Only after identity verification succeeds does
v0.2 evaluate:

- immutable source bytes;
- trusted verifier profile;
- requested-claim ceiling;
- bounded evidence semantics.

The v0.2 decision is then wrapped in a v0.3 identity envelope. The envelope has
its own digest so identity metadata cannot be added or changed without changing
the signed decision bytes.

## Platform decision signature

`sign_decision.py` can sign an identity-bound decision using an externally
provided Ed25519 private key. The helper verifies that the private key derives
the public-key fingerprint registered for the selected `admission_decision`
key before signing.

No private signing key is stored in this repository.

`verify_signed_decision.py` verifies a frozen signed decision and can also compare
its unsigned core against a freshly regenerated identity-bound decision.

## Negative controls

The hosted fixture includes:

- valid signature + valid identity -> proceeds to v0.2 admission;
- manifest changed after signing -> `REJECTED_SIGNATURE`;
- unknown key ID -> `REJECTED_IDENTITY`;
- cryptographically valid signature from a key bound to a different identity -> `REJECTED_IDENTITY`.

These controls prevent a valid key from becoming a generic identity assertion.

## Claim ceiling

A v0.3 submitter signature proves only:

> the exact manifest bytes were signed by the private key corresponding to the registered public key.

A v0.3 platform signature proves only:

> the exact admission-decision bytes were signed by the private key corresponding to the registered platform public key.

Neither signature proves:

- real-world identity;
- ownership of a GitHub account;
- source authorship;
- source truthfulness;
- claim truth;
- secure key custody;
- revocation freshness;
- framework safety;
- certification;
- automatic promotion into the canonical proof registry.

Tracking issue: [#194](https://github.com/safal207/ContractGraph-QA/issues/194).
