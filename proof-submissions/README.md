# External Proof Submission v0.2

This directory defines the first generic intake path for third-party proof artifacts.

A submission is data, not executable authority. Submitters select a trusted verification profile; they do not supply verifier code.

Pipeline:

`submission -> source integrity -> trusted verification profile -> requested claim policy -> ADMITTED | REJECTED -> registry candidate`

Key rule:

> A submitter may request a claim, but only a trusted verification profile may authorize admission of that claim.

## Statuses

- `ADMITTED_BOUNDED` — source integrity passed, trusted verifier passed, and every requested claim is allowed by that profile.
- `REJECTED_INTEGRITY` — source bytes do not match the pinned source declaration.
- `REJECTED_CLAIM_OVERREACH` — at least one requested claim exceeds the trusted profile's claim catalog.
- `REJECTED_VERIFICATION` — integrity passed but the trusted verifier did not support the evidence.
- `REJECTED_PROFILE` — unknown or disabled verification profile.

## Protocol namespaces

`protocol_namespace` is an open namespace string. v0.2 ships the first trusted profile under `CGQA`. Future profiles can use `TIP`, `DRP`, `DI`, `DIF`, or other registered namespaces without changing the submission envelope.

## Files

- `schema.v0.2.json` — portable submission manifest schema.
- `profiles.v0.2.json` — trusted verification-profile catalog.
- `process_submission.py` — stdlib intake processor.
- `examples/` — one admitted and two rejected control submissions.

An admitted result contains a `registry_candidate` object, but CI never mutates `proof-registry/registry.v0.1.json` automatically. Promotion into the canonical registry still requires review and an immutable merge commit.
