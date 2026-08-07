# Multi-invariant engagement runs

v1.2 adds an engagement layer above the existing single-finding pipeline.

The goal is to represent the result of one bounded, authorized QA search session without collapsing every outcome into either "bug" or "clean".

## Evidence model

```text
reviewed manifest
      ↓
one bounded search session
      ↓
all declared invariants classified exactly once
      ↓
violated / not_found_within_bound / inconclusive
      ↓
0..N deterministic findings
      ↓
one engagement summary
      ↓
one deterministic evidence ZIP
      ↓
independent semantic verification
```

## Status semantics

### `violated`

A concrete failing path was observed and can be replayed. The check must include a safe `findingId` and a non-empty path. The path is converted through the existing manifest/result exporter into a normal ContractGraph-QA finding.

### `not_found_within_bound`

No violation was found within the declared actors, actions, parameter corpus, time assumptions, search depth, state-hash model, snapshot, and search budget represented by the engagement evidence.

This is **not** equivalent to "secure" or "proved safe". It cannot include a synthetic failing path or finding ID.

### `inconclusive`

The search cannot support either a violation finding or a bounded no-violation conclusion. Typical causes include budget exhaustion, incomplete state modeling, adapter uncertainty, unavailable dependencies, or interrupted evidence collection.

An inconclusive check remains visible in the client engagement report and cannot be silently treated as clean.

## Complete invariant coverage

Every invariant in the reviewed manifest must appear exactly once in the engagement result. The runtime rejects:

- omitted declared invariants;
- unknown invariants;
- duplicate invariant checks;
- duplicate finding IDs;
- provenance mismatches;
- clean/inconclusive statuses that carry failing paths;
- violated statuses without a finding ID and path.

This makes the engagement report answer both questions:

1. What failed?
2. What exactly was checked and what remained unresolved?

## Example

```bash
cgqa engagement \
  --manifest manifests/examples/engagement-fixture.json \
  --result results/examples/CGQA-E-001.engagement-result.json \
  --output-dir dist/CGQA-E-001 \
  --bundle dist/CGQA-E-001/CGQA-E-001.engagement.zip
```

The repository example produces one violation, one bounded no-violation result, and one inconclusive result.

## Bundle contents

A v2 engagement bundle contains exactly the semantic artifacts needed to reconstruct the engagement:

```text
manifest.json
engagement-result.json
engagement.json
engagement.md
findings/<finding-id>.finding.json
findings/<finding-id>.md
bundle.json
```

The number of finding pairs is zero or more and is derived only from `violated` checks.

`bundle.json` records the producer tool version, engagement ID, manifest SHA-256, search-run ID, finding IDs, and SHA-256/byte counts for every semantic artifact.

## Independent verification

```bash
cgqa verify-engagement-bundle dist/CGQA-E-001/CGQA-E-001.engagement.zip
```

Verification re-runs the semantic chain from the embedded manifest and engagement result. It rejects bundle path traversal, duplicate entries, reordering, unexpected artifacts, oversized entries, provenance mismatches, modified engagement summaries, modified findings/reports, and inconsistent bundle metadata.

The verifier uses the producer version recorded in the bundle metadata rather than forcing it to equal the currently installed `cgqa` version, so historical v2 evidence remains independently verifiable after future product upgrades.

## Authorization boundary

The engagement layer does not create authorization. The same existing scope rules apply: use only repository-owned/local fixtures, systems you own, client-authorized targets, or published bug-bounty assets strictly within their stated scope and rules.

A public contract address, ABI, RPC endpoint, source repository, or verified source code is not authorization by itself.
