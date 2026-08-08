# ContractGraph-QA release

Causal-temporal smart-contract QA with reproducible, independently verifiable evidence.

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

The release workflow itself also installs the built wheel, runs the self-serve demo outside the checkout, independently verifies its evidence bundle, verifies the SBOM against the wheel digest and version, and refuses to overwrite an existing GitHub Release for the same tag.

## From proof to a real engagement

```text
self-serve demo
  ↓
client proof pack
  ↓
fixed-scope pilot
  ↓
written authorization / safe-harbor scope
  ↓
cgqa init-engagement
  ↓
review adapter + state hash + invariants
  ↓
cgqa engagement-run
  ↓
report + independently verifiable evidence
  ↓
fix → replay → retest
```

A public address, ABI, source repository, or RPC endpoint is not authorization. Real target execution remains behind explicit written scope and the existing fail-closed engagement gates.
