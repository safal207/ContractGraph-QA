# `cgqa` CLI

## Install from a checkout

```bash
python -m pip install -e .
cgqa --version
```

Python 3.11+ is required. Foundry is required for capture-enabled runs.

## Product config

`cgqa run` reads a strict TOML config.

Example:

```toml
schemaVersion = 1
workingDirectory = "."
manifest = "manifests/examples/adapter-fixture.json"
result = "results/generated/CGQA-005.result.json"
finding = "dist/CGQA-005/CGQA-005.finding.json"
report = "dist/CGQA-005/CGQA-005.md"
bundle = "dist/CGQA-005/CGQA-005.evidence.zip"

[capture]
enabled = true
profile = "capture"
test = "test_CaptureExplorerResult"
verbosity = 3
```

All artifact paths must be distinct. The evidence bundle must have a `.zip` suffix. Relative paths are resolved from the config file directory.

When capture is disabled, the result file must already exist and is treated as an input rather than a generated output.

## `cgqa doctor`

```bash
cgqa doctor
cgqa doctor --require-forge
```

Returns JSON describing the product version, Python version, Foundry availability/version, and Slither availability.

## `cgqa fingerprint`

```bash
cgqa fingerprint --manifest manifests/client.json
```

Prints the canonical manifest SHA-256 used to bind Foundry result evidence to the reviewed manifest.

## `cgqa validate`

Manifest only:

```bash
cgqa validate --manifest manifests/client.json
```

Manifest + result:

```bash
cgqa validate \
  --manifest manifests/client.json \
  --result results/generated/client.result.json
```

The second form also validates adapter/scope/fingerprint/depth/action/invariant bindings by attempting the deterministic finding export.

## `cgqa run`

```bash
cgqa run --config cgqa.toml --clean
```

Capture-enabled execution:

1. validates the reviewed manifest;
2. computes canonical manifest SHA-256;
3. invokes `forge test --match-test <test>` without a shell;
4. passes `FOUNDRY_PROFILE`, `CGQA_MANIFEST_SHA256`, and `CGQA_RESULT_PATH` to the capture process;
5. validates the generated result against the manifest;
6. writes canonical finding JSON;
7. renders deterministic Markdown;
8. creates a deterministic evidence ZIP;
9. verifies that bundle before returning success.

`--clean` removes only generated artifacts. If capture is disabled, the existing result input is retained.

On success, stdout is a JSON summary containing the finding ID, manifest fingerprint, path length, output paths, and bundle SHA-256.

## `cgqa verify-bundle`

```bash
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

Verification is independent of the working tree artifacts. The bundle contains the complete manifest/result/finding/report chain needed for validation.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | success |
| `2` | argparse usage error |
| `10` | validation/integrity error for validation-oriented commands |
| `20` | product runtime/capture/config failure |
| `70` | unexpected internal failure |
| `130` | interrupted by operator |

Automation should treat every non-zero code as a failed engagement step and should not publish the generated report/bundle as validated evidence.

## Capture safety

`capture.profile` accepts only letters, digits, `_`, `.`, and `-`.

`capture.test` accepts only letters, digits, and `_`.

The CLI does not execute a user-supplied shell command. It constructs the Foundry process argument list directly.
