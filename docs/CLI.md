# `cgqa` CLI

## Install from a checkout

```bash
python -m pip install -e .
cgqa --version
```

Python 3.11+ is required. Foundry is required for capture-enabled runs.

## `cgqa init-engagement`

```bash
cgqa init-engagement acme-escrow
```

From the current ContractGraph-QA project root, this creates `engagements/acme-escrow/` with:

- `manifest.json` — structurally valid but visibly TODO-marked authorization, target, state, action, and invariant placeholders;
- `cgqa.toml` — an `engagement-run` config whose working directory points back to the current project root;
- `capture/ClientEngagementCapture.t.sol.example` — a non-compiled, fail-closed capture skeleton;
- `README.md` — engagement completion checklist;
- `.gitignore` — ignores generated search/evidence outputs.

A custom destination is allowed only when it is a new directory inside the current project root:

```bash
cgqa init-engagement acme-escrow --directory engagements/clients/acme-escrow
```

The command never overwrites an existing destination. Its JSON summary reports `executionReady: false`. The generated capture remains `.example` and contains `CGQA scaffold not configured`; creating a scaffold is not authorization and does not create validated evidence.

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

## `cgqa engagement-run`

```bash
cgqa engagement-run --config cgqa.engagement.example.toml
```

This is the one-command direct multi-invariant product path. The strict TOML config contains the reviewed manifest, generated result path, dedicated output directory, final engagement ZIP, and Foundry capture profile/test.

Example:

```toml
schemaVersion = 1
workingDirectory = "."
manifest = "manifests/examples/engagement-fixture.json"
result = "results/generated/CGQA-E-001.engagement-result.json"
outputDirectory = "dist/CGQA-E-001-run"
bundle = "dist/CGQA-E-001-run/CGQA-E-001.engagement.zip"

[capture]
profile = "capture"
test = "test_CaptureMultiInvariantEngagementResult"
verbosity = 3
```

Execution is fail-closed:

1. validates the reviewed manifest;
2. computes its canonical SHA-256;
3. removes only the configured generated result so stale capture output cannot be reused;
4. invokes Foundry using a process argument array, not a shell string;
5. passes `FOUNDRY_PROFILE`, `CGQA_ENGAGEMENT_MANIFEST_SHA256`, and `CGQA_ENGAGEMENT_RESULT_PATH` to capture;
6. requires Foundry to produce a fresh multi-invariant result;
7. validates full manifest/result provenance and invariant coverage;
8. emits engagement JSON/Markdown and 0..N deterministic findings;
9. creates the deterministic v2 engagement evidence ZIP;
10. independently re-opens and verifies the ZIP before returning success.

`outputDirectory` must be a dedicated artifact directory and cannot equal the working directory or manifest directory. `engagement-run` always performs a fresh capture; to package an already-produced result without execution, use `cgqa engagement` instead.

## `cgqa engagement`

```bash
cgqa engagement \
  --manifest manifests/examples/engagement-fixture.json \
  --result results/examples/CGQA-E-001.engagement-result.json \
  --output-dir dist/CGQA-E-001 \
  --bundle dist/CGQA-E-001/CGQA-E-001.engagement.zip
```

This command consumes one reviewed manifest and one multi-check engagement result representing a bounded search session. Every invariant declared by the manifest must appear exactly once with one of three statuses:

- `violated` — a replayable minimal failing path exists and produces its own finding;
- `not_found_within_bound` — no violation was found inside the declared bounded model;
- `inconclusive` — the evidence is insufficient for a clean conclusion.

The command writes `engagement.json`, `engagement.md`, per-finding JSON/Markdown under `findings/`, and one deterministic v2 engagement ZIP. It immediately re-opens and semantically verifies that ZIP before returning success.

A `not_found_within_bound` status is not a claim that a contract is secure. An `inconclusive` status must remain visibly inconclusive.

## `cgqa verify-bundle`

```bash
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

Verification is independent of the working tree artifacts. The bundle contains the complete manifest/result/finding/report chain needed for validation.

## `cgqa verify-engagement-bundle`

```bash
cgqa verify-engagement-bundle dist/CGQA-E-001/CGQA-E-001.engagement.zip
```

The verifier reconstructs the manifest → engagement result → coverage summary → findings → reports chain from the ZIP itself. It rejects missing, reordered, duplicate, oversized, traversal, unexpected, hash-inconsistent, or semantically inconsistent entries.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | success |
| `2` | argparse usage error |
| `10` | validation/integrity error for validation-oriented commands |
| `20` | product runtime/capture/config/engagement-generation/scaffold failure |
| `70` | unexpected internal failure |
| `130` | interrupted by operator |

Automation should treat every non-zero code as a failed engagement step and should not publish the generated report/bundle as validated evidence.

## Capture safety

`capture.profile` accepts only letters, digits, `_`, `.`, and `-`.

`capture.test` accepts only letters, digits, and `_`.

The CLI does not execute a user-supplied shell command. It constructs the Foundry process argument list directly.
