# ContractGraph-QA CLI

The installable command is `cgqa`.

## Exit codes

- `0` — success;
- `10` — validation / verification failure;
- `20` — expected runtime failure;
- `70` — unexpected internal failure;
- `130` — interrupted.

## `cgqa demo`

Generate a repository-owned demonstration finding and deterministic evidence bundle without Forge or external RPC access.

```bash
cgqa demo --output-dir cgqa-demo
```

The destination must be fresh. The command writes repository-owned packaged inputs, exports the finding/report, creates the evidence ZIP, and verifies it before returning success.

## `cgqa doctor`

Inspect local runtime dependencies.

```bash
cgqa doctor
cgqa doctor --require-forge
```

`--require-forge` fails when Foundry is unavailable.

## `cgqa init-engagement`

Create a fail-closed client engagement scaffold.

```bash
cgqa init-engagement acme-escrow
cgqa init-engagement acme-escrow --directory ./work/acme-escrow
```

The scaffold intentionally contains blocking TODO values for authorization, target, state model, actions, invariants, and capture adapters. It is not execution-ready until a human reviews and replaces them.

## `cgqa validate`

Validate a reviewed adapter manifest and optionally an explorer result.

```bash
cgqa validate --manifest manifests/client.json
cgqa validate --manifest manifests/client.json --result results/client.result.json
```

Validation includes strict field sets, manifest/result binding, path-depth bounds, action references, invariant references, and manifest fingerprint verification.

## `cgqa fingerprint`

Print the canonical SHA-256 fingerprint of a validated adapter manifest.

```bash
cgqa fingerprint --manifest manifests/client.json
```

## `cgqa reachability`

Run the bounded adversarial capability-reachability engine against a strict JSON model.

```bash
cgqa reachability --model scenarios/adversarial-wallet-replay.json
```

The command requires no Forge and performs no network access. It:

1. loads the model with the stdlib-only runtime validator;
2. rejects schema drift, unknown references, duplicate identifiers, and whitespace-only semantic fields;
3. computes a canonical `modelSha256` fingerprint;
4. runs deterministic bounded breadth-first search;
5. emits `reachable` or `not_found_within_bound` plus the shortest reachable impact path when present.

A successful command can still return `not_found_within_bound`; this means no target capability was found within the declared model and search bound. It is not a safety certification.

Representative output:

```json
{
  "maxDepth": 4,
  "modelSha256": "...",
  "path": {
    "crossedBoundaries": ["settlement-idempotency"],
    "impact": "duplicate financial settlement",
    "initialCapability": "request-spend",
    "invariantIds": ["settlement-at-most-once"],
    "targetCapability": "duplicate-settlement",
    "transitions": [],
    "violatedAssumptions": ["fresh-policy-state", "unique-settlement"]
  },
  "status": "reachable",
  "targetCapabilities": ["duplicate-settlement", "overspend"],
  "violatedAssumptions": ["fresh-policy-state", "unique-settlement"]
}
```

Model semantics and schema are documented in [`ADVERSARIAL_REACHABILITY.md`](ADVERSARIAL_REACHABILITY.md).

## `cgqa run`

Run the single-finding capture and evidence pipeline.

```bash
cgqa run --config cgqa.toml
cgqa run --config cgqa.toml --clean
```

The pipeline is:

```text
manifest validation
→ optional Foundry capture
→ result validation / manifest binding
→ deterministic finding JSON
→ Markdown report
→ deterministic evidence ZIP
→ independent verification
```

`--clean` removes generated finding/report/bundle/result files before capture. It never removes the reviewed manifest.

## `cgqa engagement-run`

Run the direct multi-invariant capture workflow from an engagement-run TOML config.

```bash
cgqa engagement-run --config engagements/acme-escrow/cgqa.toml
```

This path is intended for fixed-scope client engagements where one Foundry capture produces multiple invariant outcomes.

## `cgqa engagement`

Build a multi-invariant engagement report and deterministic evidence bundle from an already captured engagement result.

```bash
cgqa engagement \
  --manifest manifests/client.json \
  --result results/client.engagement-result.json \
  --output-dir reports/client \
  --bundle dist/client.engagement.zip
```

## `cgqa verify-bundle`

Independently verify a single-finding evidence ZIP.

```bash
cgqa verify-bundle dist/client.evidence.zip
```

Verification fails closed on duplicate/unsafe ZIP entries, missing files, unexpected files, digest mismatches, semantic manifest/result/finding mismatches, or non-canonical generated finding/report bytes.

## `cgqa verify-engagement-bundle`

Independently verify a multi-invariant engagement evidence ZIP.

```bash
cgqa verify-engagement-bundle dist/client.engagement.zip
```

Verification reconstructs the semantic chain from the included manifest and engagement result and compares canonical generated artifacts with the bundle contents.

## Automation

All successful commands emit JSON except argparse help/version text and Markdown files written to disk. Error details are emitted on stderr.

For CI, prefer checking both the process exit code and the explicit semantic status in generated JSON. In particular, bounded search outcomes such as `not_found_within_bound` are evidence about the declared bound, not a security guarantee.
