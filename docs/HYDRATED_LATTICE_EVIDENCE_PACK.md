# Hydrated Contract Lattice Evidence Pack v0.1

This layer turns a Hydrated Contract Lattice assessment into a portable deterministic replay artifact.

```text
static lattice result
+ normalized ExecutionTrace
+ reviewed hydration bindings
        ↓
hydrated assessment
        ↓
canonical content hashes
        ↓
deterministic ZIP
        ↓
independent local replay verification
```

## Why this exists

`cgqa-hydrated` composes static possibility evidence and runtime actuality, but a printed result alone is not a self-contained proof object. The evidence pack preserves the exact inputs and the composed result so another verifier can replay the same bounded claim without the original working directory or ambient clock.

## Pack contract

Canonical entry order:

1. `static-result.json`
2. `execution-trace.json`
3. `hydration-bindings.json`
4. `assessment.json`
5. `client-summary.md`
6. `manifest.json`

JSON entries use UTF-8, sorted keys, compact separators, no NaN, and a single trailing newline. The ZIP uses stored compression, the fixed timestamp `1980-01-01 00:00:00`, Unix regular-file mode `0644`, and the exact entry order above.

The manifest hashes and sizes every content entry. Verification rejects entry drift, non-canonical metadata, non-canonical JSON, manifest drift, malformed normalized inputs, and semantic replay drift.

## Build

First preserve the exact static result produced by the Solidity/lattice step. Then build the pack:

```bash
cgqa-hydrated-evidence build \
  --static-result static-result.json \
  --trace scenarios/execution-trace-double-settlement-conflict.json \
  --bindings scenarios/hydration-bindings-escrow-race.json \
  --output hydrated-evidence.zip
```

A successful build returns the complete ZIP SHA-256. Building a pack for an assessment whose verdict is `FAIL` or `INCONCLUSIVE` is still a successful packaging operation; the verdict is evidence, not a CLI failure.

## Verify

Local deterministic replay:

```bash
cgqa-hydrated-evidence verify --pack hydrated-evidence.zip
```

Externally anchored byte verification:

```bash
cgqa-hydrated-evidence verify \
  --pack hydrated-evidence.zip \
  --expected-sha256 <separately-obtained-complete-pack-sha256>
```

The verifier:

1. checks canonical ZIP structure and metadata;
2. optionally checks the complete ZIP bytes against the separately supplied SHA-256;
3. checks canonical JSON encoding;
4. recomputes manifest entry hashes and sizes;
5. reparses the normalized ExecutionTrace and hydration bindings;
6. reruns `run_hydrated_lattice` from the embedded static result + trace + bindings;
7. compares canonical JSON bytes of the replayed and packed assessments, preserving type distinctions such as `false` versus `0`;
8. regenerates the client summary and verifies manifest status/schema bindings.

## Trust boundary

There are two deliberately different claims:

```text
no external digest
→ local replay consistency only

separately obtained expected ZIP digest
→ exact bytes externally bound + local replay consistency
```

The second statement is still an integrity statement, not an identity signature. A SHA-256 value alone does not prove who published the evidence.

Neither mode proves:

- raw EVM/provider capture completeness;
- correctness or authority of semantic normalization;
- concrete token/native balances from static `valuePresence`;
- truth of external authority or time-witness sources;
- provider endorsement;
- security certification;
- compliance approval;
- production or financial authorization.

Those remain independent provenance/authority claims.

## Client interpretation

The human summary keeps the proof legs separate:

- static lifecycle;
- runtime economic cardinality;
- runtime successor consistency;
- static/runtime transition conformance;
- authority/time/evidence binding completeness;
- overall PASS / FAIL / INCONCLUSIVE.

This preserves the core product rule: a legal static transition can still participate in an unsafe runtime composition, while missing proof material must remain `INCONCLUSIVE` instead of becoming a synthetic PASS.
