# ContractGraph-QA v1.8.0

Causal-temporal smart-contract QA with source-bound measurement provenance and independently verifiable evidence.

## What is new in v1.8.0

ContractGraph-QA now records not only **what verdict was produced**, but also **why the measurement was eligible to support that verdict**.

The engagement evidence chain is:

```text
AUTHORIZED SCOPE
      ↓
DECLARED INVARIANT POPULATION
      ↓
OBSERVED CHECK POPULATION
      ↓
SOURCE RECEIPT
      ↓
MEASUREMENT PROVENANCE
      ↓
ENGAGEMENT EVIDENCE
      ↓
INDEPENDENT VERIFICATION
```

The final provenance-bound engagement ZIP contains:

- `base-engagement.zip` — the complete legacy engagement evidence bundle;
- `measurement-input.json` — measurement epoch, scope, denominator, numerator, and requirement;
- `measurement-source.json` — exact source artifact digests and declared/observed invariant IDs;
- `measurement-provenance.json` — deterministic provenance verdict;
- `bundle.json` — content-addressed wrapper manifest.

`cgqa verify-engagement-bundle` automatically verifies both legacy engagement ZIPs and the v1.8 provenance wrapper.

## Measurement semantics

The v1.8 gate fails closed on:

- `EPOCH_MISMATCH` — measurement values from incompatible schema/measurement epochs;
- `PARTIAL_COVERAGE` — observed coverage below the explicitly required population;
- `UNMEASURED` — the relevant observation is unknown rather than a false measurement.

For engagement evidence, the denominator is independently derived from the invariant IDs declared in the reviewed manifest. The numerator is derived from the invariant IDs actually emitted by the engagement result. Blocked provenance cannot become authoritative client evidence.

## 30-second proof

1. Download the wheel and `DEMO_EVIDENCE.zip` from this release.
2. Install the wheel into Python 3.11+.
3. Run:

```bash
cgqa --version
cgqa demo --output-dir cgqa-demo
cgqa verify-bundle cgqa-demo/CGQA-005.evidence.zip
```

The demo uses only repository-owned packaged evidence. It makes no external RPC call, requires no Foundry installation, and is not presented as a third-party audit.

For an authorized multi-invariant engagement:

```bash
cgqa engagement-run --config engagements/acme-escrow/cgqa.toml
cgqa verify-engagement-bundle engagements/acme-escrow/evidence/engagement.evidence.zip
```

A successful v1.8 engagement run reports `measurementProvenanceStatus: pass` only after the measurement boundary and embedded engagement evidence independently verify.

## Verify release integrity

The release includes:

- `SHA256SUMS` — checksum manifest for the wheel and release proof files;
- `SHA256SUMS.attestation.json` — Sigstore/GitHub artifact attestation bundle for that checksum manifest;
- `SBOM.cdx.json` — CycloneDX 1.5 artifact-level SBOM for the wheel;
- `SBOM.attestation.json` — signed SBOM attestation bound to the wheel;
- `DEMO_REPORT.md` and `DEMO_EVIDENCE.zip` — repository-owned proof output;
- `CLIENT_PROOF.md` — the fixed-scope pilot proof pack.

Verify local checksums first:

```bash
sha256sum -c SHA256SUMS
```

Then, with GitHub CLI authentication available, verify the signed checksum manifest:

```bash
gh attestation verify SHA256SUMS --repo safal207/ContractGraph-QA
```

The release workflow installs the built wheel, runs the self-serve demo outside the checkout, independently verifies its evidence bundle, verifies the SBOM against the wheel digest and version, creates attestations, and refuses to overwrite an existing GitHub Release for the same tag.

## Compatibility

- existing single-finding evidence verification is unchanged;
- legacy multi-invariant engagement bundles remain verifiable;
- the new provenance wrapper adds an outer evidence layer rather than silently redefining the embedded legacy bundle;
- package version and evidence bundle version remain separate compatibility contracts.

## Safety boundary

Measurement provenance proves the declared measurement boundary and source binding. It does **not** prove that the chosen invariants are complete, that bounded exploration found every vulnerability, or that a target was authorized.

A public address, ABI, source repository, or RPC endpoint is not authorization. Real target execution remains behind explicit written scope and the existing fail-closed engagement gates.
