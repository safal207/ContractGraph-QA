# Attenu observer-envelope v1.1 — independent 18/18 proof

> **Result:** `18/18 AGREE` — five accepting controls and thirteen rejecting controls, scored by a standalone verifier that does not import `attenu_guard`.

This proof checks the observer-envelope contract introduced around the A2A #1575 discussion. It is intentionally narrow: the question is not whether the envelope design is universally correct, but whether an independent implementation reaches the same verdicts, failure positions, and per-entry evidence states for the exact released corpus.

## Exact subject

| Item | Pinned value |
|---|---|
| Upstream repository | `attenu-io/attenu-guard` |
| Upstream commit | `f34a351c12ddc08e9c8bd3beca9da4695a46376f` |
| Vector path | `tests/vectors/envelopes/envelope_vectors_v1.json` |
| Contract / revision | `envelope_vectors_v1` / `envelope_vectors_v1.1` |
| Cases | `18` |
| Vector SHA-256 | `6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64` |
| Python copy | `attenu-guard==0.13.0` |
| TypeScript copy | `attenu-guard@0.8.0` |

The workflow extracts the vector independently from the pinned repository, the PyPI wheel, and the npm tarball. All three copies must be byte-identical before scoring begins.

## What the independent verifier checks

1. **Base evidence remains sound.** The previously published standalone bundle-v1.2 verifier rechecks the ledger chain, signed anchor, authority narrowing, containment, and execution binding. The intentionally unanchored row receives a deterministic local-only anchor solely for those subordinate base checks; that synthetic anchor is never presented as upstream evidence.
2. **`entry_hash` carries the binding.** The envelope subject is located by `seq`; `entry_hash` is recomputed from the actual bundle and must match. `chain_id`, `node`, `event`, and `call_id` are treated as locators: disagreement is detectable, but agreement does not become a second evidentiary claim.
3. **The signed shape cannot widen silently.** Version, type, top-level members, `observed`, `witness`, and event-specific subject members are exact sets.
4. **Bytes and signatures are separate gates.** The verifier independently reconstructs RFC 8785/JCS bytes, checks the supplied raw-wire negative control, and verifies Ed25519 over `JCS(envelope - sig)`.
5. **One entry gets at most one envelope.** A second envelope claiming the same `seq` produces `envelope_duplicate_subject`; the entry falls back to `process-asserted`, so array order cannot choose which witness statement appears authoritative.
6. **Failures stay where the evidence lives.** Every `envelope_*` failure must land on a hop that an envelope claims to cover. An envelope failure may not fabricate a chain-level anchor failure or spread to an uncovered hop.
7. **State mapping is exact.** Every entry is compared against the corpus-declared `witness-signed` or `process-asserted` state, not only the entries with a valid envelope.

## Result map

| Group | Cases | Independent outcome |
|---|---:|---|
| Positive controls | 5 | Accept |
| Negative controls | 13 | Reject |
| Named failure vocabulary | 7/7 | Exercised |
| Verdict + required failure + position + state | 18/18 | Agree |

The seven independently exercised failure tokens are:

`envelope_unknown_version`, `envelope_unknown_member`, `envelope_subject_mismatch`, `envelope_duplicate_subject`, `envelope_non_canonical`, `envelope_unknown_witness`, and `envelope_bad_signature`.

The machine-readable result is in [`report.json`](./report.json).

## The important boundary

A valid envelope proves a bounded statement:

```text
this configured witness key signed the identity of this committed entry
```

It does **not** prove any of the following:

- global capture completeness, including that every relevant action was recorded;
- that an absent envelope was expected, missing, or never promised;
- that the witness was fresh, non-equivocating, independent, or non-bypassable;
- that stripping the entire top-level `envelopes` array would be detectable from the ledger anchor;
- that an observed `matched` result proves the real-world effect globally;
- that A2A, CrewAI, or another project has adopted or endorsed this format.

That distinction is the useful product result: **strong evidence about one recorded transition must not be promoted into a stronger claim about complete execution.**

## Known v1 limits preserved, not hidden

Two omissions remain first-class design boundaries rather than being “fixed” by this proof:

1. **Intended coverage is absent.** `process-asserted` combines “nobody undertook to witness this hop” with “a witness was expected but produced nothing.” A signed per-witness coverage declaration would require a later envelope version.
2. **The envelope array is outside the bundle anchor.** A stripped array can look like a bundle that never carried envelopes. Binding envelope-set presence or a head commitment belongs to a later contract.

## Reproduce

From the repository root, after extracting the three pinned vector copies:

```bash
python proofs/attenu-envelope-v1.1-independent/verify_envelope_vectors.py \
  --vectors external/attenu-guard/tests/vectors/envelopes/envelope_vectors_v1.json \
  --python-vector /tmp/attenu-python-envelope.json \
  --npm-vector /tmp/attenu-npm-envelope.json \
  --json-out /tmp/attenu-envelope-report.json

diff -u \
  proofs/attenu-envelope-v1.1-independent/report.json \
  /tmp/attenu-envelope-report.json
```

The hosted workflow performs the complete repository/PyPI/npm extraction, byte comparison, independent score, deterministic report diff, and repository tests.

## Claim ceiling

This is **interoperability evidence for a frozen corpus**. It is not certification, a completeness theorem, a production security audit, or proof that every conforming implementation is safe.
