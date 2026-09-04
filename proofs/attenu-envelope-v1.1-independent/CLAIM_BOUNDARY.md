# Claim boundary

## Supported by this proof

- The exact `envelope_vectors_v1.1` file at the pinned upstream commit has the declared SHA-256.
- The repository, PyPI `attenu-guard==0.13.0`, and npm `attenu-guard@0.8.0` copies are byte-identical.
- A standalone implementation agrees with the frozen corpus on all 18 verdicts, required failure positions, and per-entry `witness-signed` / `process-asserted` states.
- The released cases exercise all seven envelope-v1 failure tokens.

## Explicitly unsupported

- Global capture completeness.
- Proof that an absent envelope was expected or missing.
- Witness freshness, non-equivocation, independence, or deployment non-bypassability.
- Detection of a top-level envelope array stripped outside the ledger anchor.
- Specification correctness beyond the frozen cases.
- A2A adoption, certification, or endorsement.
