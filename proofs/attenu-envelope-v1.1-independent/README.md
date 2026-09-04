# Attenu observer-envelope v1.1 — independent 18/18 proof

> **Preregistered result:** `18/18 AGREE` — five accepting controls and thirteen rejecting controls, scored by a standalone verifier that does not import `attenu_guard`.

This proof checks the observer-envelope contract discussed around A2A issue #1575. Its question is deliberately narrow: given the same frozen bytes and trust inputs, does an independent implementation reach the same verdicts, required failure positions, and per-entry evidence states?

The committed report becomes evidence only when hosted CI regenerates it byte-for-byte from the exact subjects below.

## Exact subjects

| Source | Pinned subject |
|---|---|
| Python repository | `attenu-io/attenu-guard@f34a351c12ddc08e9c8bd3beca9da4695a46376f` |
| Python vector | `tests/vectors/envelopes/envelope_vectors_v1.json` |
| PyPI distribution | `attenu-guard==0.13.0` |
| TypeScript repository | `attenu-io/attenu-guard-ts@51eebfc957c47aeba3738e5f1f67e8d3d55da50f` |
| TypeScript release | `v0.8.0` |
| TypeScript vector | `test/fixtures/vectors/envelopes/envelope_vectors_v1.json` |
| Contract / revision | `envelope_vectors_v1` / `envelope_vectors_v1.1` |
| Cases | `18` |
| Vector SHA-256 | `6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64` |

The npm package is **not** used as a raw-vector source: its published file set contains runtime artifacts rather than the vendored test fixture. The workflow instead checks the exact TypeScript repository commit behind release `v0.8.0`. That boundary is explicit so a package-layout assumption cannot masquerade as interoperability evidence.

Before scoring, CI requires byte identity among:

1. the pinned Python-repository vector;
2. the vector shipped in the exact PyPI wheel;
3. the vendored vector at the pinned TypeScript-repository commit.

## What the independent verifier checks

1. **Base evidence remains sound.** The previously merged standalone bundle-v1.2 verifier rechecks the ledger chain, signed anchor, authority narrowing, containment, and execution binding. The intentionally unanchored row receives a deterministic local-only anchor solely for those subordinate checks; that synthetic anchor is never presented as upstream evidence.
2. **`entry_hash` carries the binding.** The envelope subject is located by `seq`; `entry_hash` is recomputed from the actual bundle and must match. `chain_id`, `node`, `event`, and `call_id` are locators: disagreement is detectable, but agreement does not become a second evidentiary claim.
3. **The signed shape cannot widen silently.** Version, type, top-level members, `observed`, `witness`, and event-specific subject members are exact sets.
4. **Bytes and signatures are separate gates.** The verifier independently reconstructs RFC 8785/JCS bytes, checks the raw-wire negative control, and verifies Ed25519 over `JCS(envelope - sig)`.
5. **One entry gets at most one envelope.** A second envelope claiming the same `seq` produces `envelope_duplicate_subject`; the entry falls back to `process-asserted`, so array order cannot choose which witness statement appears authoritative.
6. **Failures stay where the evidence lives.** An `envelope_*` failure must land on a hop an envelope claims to cover. It may not fabricate a chain-level anchor failure or spread to an uncovered hop.
7. **State mapping is exact.** Every entry is compared against the corpus-declared `witness-signed` or `process-asserted` state, not merely the entries with a valid envelope.

## Result map

| Group | Cases | Expected independent outcome |
|---|---:|---|
| Positive controls | 5 | Accept |
| Negative controls | 13 | Reject |
| Named failure vocabulary | 7/7 | Exercised |
| Verdict + required failure + position + state | 18/18 | Agree |

The seven independently exercised failure tokens are:

`envelope_unknown_version`, `envelope_unknown_member`, `envelope_subject_mismatch`, `envelope_duplicate_subject`, `envelope_non_canonical`, `envelope_unknown_witness`, and `envelope_bad_signature`.

The machine-readable result is [`report.json`](./report.json).

## The important boundary

A valid envelope supports one bounded statement:

```text
this configured witness key signed the identity of this committed entry
```

It does **not** prove:

- global capture completeness, including that every relevant action was recorded;
- whether an absent envelope was expected, missing, or never promised;
- witness freshness, non-equivocation, independence, or non-bypassability;
- that stripping the top-level `envelopes` array would be detectable from the ledger anchor;
- that a `matched` observation proves the real-world effect globally;
- adoption or endorsement by A2A, CrewAI, Attenu maintainers, or any standards body.

The useful product result is therefore not “the trace proves everything.” It is stricter and more valuable: **strong evidence about one recorded transition must not be promoted into a stronger claim about complete execution.**

## Known v1 limits preserved, not hidden

1. **Intended coverage is absent.** `process-asserted` combines “nobody undertook to witness this hop” with “a witness was expected but produced nothing.” A signed per-witness coverage declaration belongs to a later envelope version.
2. **The envelope array is outside the bundle anchor.** A stripped array can look like a bundle that never carried envelopes. Binding envelope-set presence or a head commitment also belongs to a later contract.

## Reproduce

After placing the three exact source copies at the paths shown below:

```bash
python proofs/attenu-envelope-v1.1-independent/run_pinned_proof.py \
  --vectors external/attenu-guard/tests/vectors/envelopes/envelope_vectors_v1.json \
  --python-vector /tmp/attenu-python-envelope.json \
  --typescript-vector external/attenu-guard-ts/test/fixtures/vectors/envelopes/envelope_vectors_v1.json \
  --json-out /tmp/attenu-envelope-report.json

diff -u \
  proofs/attenu-envelope-v1.1-independent/report.json \
  /tmp/attenu-envelope-report.json
```

The hosted workflow performs the complete Python-repository, PyPI-wheel, and TypeScript-repository byte comparison, independent score, deterministic report diff, and proof-contract tests.

## Claim ceiling

This is **interoperability evidence for one frozen corpus**. It is not certification, a completeness theorem, a production security audit, or proof that every conforming implementation is safe.
