# Distribution and self-serve demo

ContractGraph-QA v1.7 keeps the self-serve proof path from v1.6 and adds cross-platform release gates, an artifact-level SBOM, signed attestations, and tag-triggered GitHub Release assets.

## Fastest product proof

Install the built wheel and run:

```bash
cgqa demo --output-dir cgqa-demo
```

The command uses only repository-owned packaged demo evidence and creates:

```text
cgqa-demo/
  inputs/
    manifest.json
    result.json
  CGQA-005.finding.json
  CGQA-005.md
  CGQA-005.evidence.zip
```

The evidence ZIP is independently verified before `cgqa demo` returns success.

You can verify it again from any directory:

```bash
cgqa verify-bundle cgqa-demo/CGQA-005.evidence.zip
```

## What the demo proves

The demo proves that the installed product can:

1. load and validate a reviewed manifest/result pair;
2. reconstruct a deterministic finding;
3. render the client-facing Markdown report;
4. create a deterministic integrity/provenance bundle;
5. independently verify the semantic chain.

The demo does **not** claim that a third-party smart contract was audited. It uses a repository-owned local fixture and makes no external RPC call.

## Portability gate

The `Portability` workflow builds the wheel and runs the installed product on both `ubuntu-latest` and `windows-latest`.

Each platform:

- installs the built wheel rather than importing the checkout;
- executes `cgqa demo` from a temporary directory outside the repository;
- verifies the evidence bundle;
- requires canonical LF bytes for packaged inputs, finding JSON, and Markdown;
- runs the demo twice and requires byte-identical finding/report/evidence artifacts.

This permanently covers the Windows CRLF class of regression discovered during the v1.6.0 release.

## Distribution artifact

The `Distribution` GitHub Actions workflow runs on `v*` tags and can also be started manually after merge.

It produces a verified Actions artifact and, for a new tag, a GitHub Release containing:

- `contractgraph_qa-<version>-py3-none-any.whl`;
- `DEMO_REPORT.md`;
- `DEMO_EVIDENCE.zip`;
- `CLIENT_PROOF.md`;
- `SBOM.cdx.json`;
- `VERIFY.md`;
- `SHA256SUMS`;
- `SHA256SUMS.attestation.json`;
- `SBOM.attestation.json`.

The workflow installs the wheel it just built, runs `cgqa demo` outside the checkout, verifies the evidence bundle, generates and independently verifies the SBOM, checks every checksum-listed payload, creates GitHub/Sigstore attestations, and only then publishes release assets.

An existing GitHub Release for the same tag is not overwritten automatically.

## Verify downloaded files

On Linux/macOS:

```bash
sha256sum -c SHA256SUMS
```

On PowerShell, compare entries in `SHA256SUMS` with `Get-FileHash -Algorithm SHA256`.

With GitHub CLI authentication available, verify the signed checksum manifest:

```bash
gh attestation verify SHA256SUMS --repo safal207/ContractGraph-QA
```

`SBOM.cdx.json` is CycloneDX 1.5 and is bound to the built wheel SHA-256, package version, and source commit. The Distribution workflow independently verifies those fields before signing/publishing.

## From demo to a real engagement

The recommended operator flow is:

```text
cgqa demo
  ↓
review client proof pack
  ↓
obtain explicit written authorization / safe-harbor scope
  ↓
cgqa init-engagement <name>
  ↓
replace every TODO and review the adapter/invariants/state hash
  ↓
cgqa engagement-run --config <engagement>/cgqa.toml
  ↓
verify engagement evidence bundle
  ↓
deliver report + evidence ZIP
```

A public contract address, ABI, or readable chain state is not authorization.

## Release boundary

Git tags are release identifiers and must match the package version exactly (`v1.7.0` for package `1.7.0`). Tag creation remains an explicit operator action after the exact release head has passed all gates. The tag-triggered workflow then creates the signed distribution and GitHub Release.
