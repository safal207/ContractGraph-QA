# ContractGraph-QA CLI

The installable command is `cgqa`.

Run the unified command list with:

```bash
cgqa --help
```

## Exit codes

- `0` — success;
- `10` — validation, bounded HOLD, or verification failure;
- `20` — expected runtime failure;
- `70` — unexpected internal failure;
- `130` — interrupted.

The causal-temporal Phase 2/3/4 commands use the same public exit-code contract even though their internal Python modules historically returned `2` for validation/HOLD results.

## `cgqa external-investigation`

Validate and summarize a chain-neutral source-bound investigation record:

```bash
cgqa external-investigation \
  --record scenarios/external-investigation-stellar-dice-duel.json
```

The command validates exact source identity, authorization, evidence states, separate native/CGQA execution states, the complete `AGENTS.md` capability matrix, blockers, verification debt, impact classification, and explicit non-claims.

A valid blocked journal exits `0` and emits `recordValidationStatus: VALID` because the record itself is valid. Consumers must inspect `workflowStatus`; exit code `0` is not a target-security verdict. Structurally invalid or overclaiming records exit `10`.

See [`EXTERNAL_INVESTIGATION_GATE.md`](EXTERNAL_INVESTIGATION_GATE.md).

## `cgqa quickstart`

Inspect an unfamiliar local smart-contract repository without executing project code by default.

```bash
cgqa quickstart --target /path/to/project
```

Default output:

```text
<project>/.cgqa/quickstart/
  quickstart.json
  REPORT.md
```

Use another destination:

```bash
cgqa quickstart --target . --output-dir /tmp/cgqa-report
```

Run the detected native local test command only after explicit review:

```bash
cgqa quickstart --target . --run-native --timeout 600
```

An existing output directory is never overwritten implicitly. `--force` may replace an output directory only when it is inside the target project.

Quickstart detects common Foundry, Hardhat, Truffle, Ape/Brownie/Vyper, Soroban, Anchor, Move, and Cairo/Scarb routes. It writes a deterministic source inventory and project fingerprint, contract/program declaration inventory, bounded Solidity review signals, native test plan/result, and next-step recommendations.

Review signals are prompts, not confirmed vulnerabilities. Native test success is not a security proof. See [`UNIVERSAL_QUICKSTART.md`](UNIVERSAL_QUICKSTART.md).

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

The scaffold intentionally contains blocking TODO values for authorization, target, state model, actions, invariants, and capture adapters. It is not execution-ready until a human reviews and replaces them. Run `cgqa quickstart` first to identify the framework, declarations, tools, and likely target surface.

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

Model semantics and schema are documented in [`ADVERSARIAL_REACHABILITY.md`](ADVERSARIAL_REACHABILITY.md).

## `cgqa control-bundle-build`

Upgrade an already verified reachability-aware bundle v2 into a deterministic control evidence bundle v3 by binding the post-impact containment/recovery/verification model.

```bash
cgqa control-bundle-build \
  --base-bundle dist/client.evidence.zip \
  --post-impact-model scenarios/post-impact-adapter-fixture.json \
  --output dist/client.control.evidence.zip
```

The command first verifies the supplied base v2 bundle. It then canonicalizes and runs the post-impact model, binds it to the exact reached forbidden capability and reachability-model SHA-256, and writes a deterministic v3 ZIP. Existing v1/v2 semantics are unchanged.

## `cgqa verify-control-bundle`

Independently verify a control evidence bundle v3.

```bash
cgqa verify-control-bundle dist/client.control.evidence.zip
```

Verification reconstructs the exact embedded v2 bundle, checks its SHA-256, runs the existing v2 semantic verifier, then independently re-runs both reachability and post-impact models.

## `cgqa payment-recovery-evaluate`

Evaluate a vendor-neutral Agent Payment Recovery Benchmark v0.1 trace.

```bash
cgqa payment-recovery-evaluate \
  --scenario benchmarks/agent-payment-recovery-v0.1/cases/pass_committed_stop.json
```

The evaluator checks whether an ambiguous financial execution is reconciled before another monetary action occurs. Passing traces exit `0`; valid traces with benchmark violations exit `10`.

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

## Causal-temporal vNext commands

The main installed `cgqa` command directly exposes all vNext layers.

### Transition reasoning

```bash
cgqa geometry --model geometry.json
cgqa ancestry --trace ancestry.json
cgqa orient --bundle orientation.json
```

### Temporal evidence and continuity

```bash
cgqa witness --input witness.json
cgqa debt --input debt.json
cgqa watch --input watchpoints.json
cgqa replicate --input replication.json
cgqa remediate --input remediation.json
```

### Verification-of-verification

```bash
cgqa subject-freeze --input freeze.json
cgqa verification-plan --input plan.json
cgqa trace-integrity --input trace.json
cgqa evidence-readiness --input evidence.json
cgqa root-cause --input findings.json
cgqa metamorphic --input roundtrip.json
cgqa durable-build --root evidence --path finding.json --path trace.json
cgqa durable-verify --root evidence --manifest manifest.json
```

### Active verification planning

```bash
cgqa plan-verification --input campaign.json
cgqa record-verification-cost --input cost.json
```

These commands preserve the core non-equivalences:

```text
BALANCED != security verdict
Completed != PASS
Selected != Verified
ExpectedInformationGain != Truth
Confirmed_t != Confirmed_t+1
ForwardRollback != HistoryRewrite
InMemoryVerified != DurableEvidenceVerified
```

## Automation

All successful commands emit JSON except argparse help/version text and Markdown files written to disk. Error details are emitted on stderr.

For CI, check both the process exit code and the explicit semantic status in generated JSON. In particular, bounded search outcomes such as `not_found_within_bound` are evidence about the declared bound, not a security guarantee.
