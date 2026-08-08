# Distribution and self-serve demo

ContractGraph-QA v1.6 adds a distribution path that can demonstrate the evidence product without a repository checkout or a Foundry installation.

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

## Distribution artifact

The `Distribution` GitHub Actions workflow runs on `v*` tags and can also be started manually after merge.

It produces one Actions artifact containing:

- `contractgraph_qa-<version>-py3-none-any.whl`;
- `DEMO_REPORT.md`;
- `DEMO_EVIDENCE.zip`;
- `CLIENT_PROOF.md`;
- `SHA256SUMS`.

The workflow installs the wheel it just built, runs `cgqa demo` outside the checkout, verifies the evidence bundle, and only then assembles the distribution artifact.

## Verify downloaded files

On Linux/macOS:

```bash
sha256sum -c SHA256SUMS
```

On PowerShell, compare each entry in `SHA256SUMS` with:

```powershell
Get-FileHash .\contractgraph_qa-1.6.0-py3-none-any.whl -Algorithm SHA256
```

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

Git tags are release identifiers and must match the package version exactly (`v1.6.0` for package `1.6.0`). The repository currently requires an operator to create the tag after the exact release head has passed all gates.
