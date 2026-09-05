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

## `cgqa tsse`

Verify one reviewed finite Time-Space-State-Environment trace without executing
or scanning the represented target.

```bash
cgqa tsse --model scenarios/tsse-payment-lifecycle.json
```

The command checks exact-subject and evidence bindings, monotonic time,
causal-step/predecessor/path continuity, declared time/space/state/environment
changes, and forbidden phase transitions. A structurally valid hold returns the
public `cgqa` validation code `10` and still emits machine-readable JSON.

The standalone `cgqa-tsse` entry point exposes finer exit codes: `0` pass, `1`
hold, and `2` structural/output validation. See
[`TSSE_TRANSITION_MODEL.md`](TSSE_TRANSITION_MODEL.md).
Existing output files require explicit `--force`; the input model can never be
used as the output destination.

## `cgqa tsse-adapt`

Verify a reviewed scanner/replay capture, reopen every bound source and tool
artifact, and compile eligible Cargo/Soroban/Foundry/Echidna/Medusa observations into TSSE:

```bash
cgqa tsse-adapt \
  --capture scenarios/tsse-tools/foundry-capture.json \
  --profile scenarios/tsse-tools/foundry-profile.json \
  --model-out tsse-model.json \
  --output adapter-result.json
```

The `--profile` file is a separate reviewer-controlled subject, observation-hash,
and policy anchor; capture policy and dynamic observations must match it exactly.
`--model-out` requires a companion
`--output` adapter receipt. Slither JSON is normalized only into static replay
seeds and remains `inconclusive`; it cannot emit a TSSE model. A successful dynamic import returns
top-level `ready`, not a scan/security `pass`. The standalone command returns
`0` for `ready`, `1` for `hold`/`inconclusive`, and `2` for invalid input/output.
Unified `cgqa` maps the latter two to validation exit code `10`.

See [`TSSE_TOOL_ADAPTERS.md`](TSSE_TOOL_ADAPTERS.md).

## `cgqa-graph-layers`

Compare a reviewed idea graph and verification plan with the fact graph
produced by a bounded run:

```bash
cgqa-graph-layers \
  --input outputs/soroban-five-graph-layers.json \
  --output outputs/soroban-five-graph-layer-diff.json
```

The input keeps three layers separate: `idea` records the intended
transitions, `plan` records the checks that were actually scheduled, and
`fact` records observed or explicitly blocked/static-gap edges. Layer status is
strict (`desired`, `planned`, and `observed`/`blocked`/`static-gap`
respectively). The result reports missing, unexpected, un-evidenced, and
geometry-mismatched edges. `aligned` means only that the declared plan is
represented by observed fact geometry; it is not a security verdict. Existing
outputs require `--force`.

## `cgqa action-guard`

Evaluate one exact-subject agent-action trace against a reviewed authorization
envelope, independent monitor, canaries, denial history, and evidence/witness
requirements:

```bash
cgqa action-guard \
  --input scenarios/action-guard/soroban-five-preflight.json \
  --output action-guard-result.json
```

The evaluator never executes the recorded tool action. It returns separate
`guardStatus`, `agentConformance`, and `evidenceStatus` fields plus a bounded
`pass`/`hold`/`fail` status. `hold` is used for a safe denial, false stop, or
missing receipt/witness; `fail` is reserved for a monitor/control bypass such
as an out-of-scope `ALLOW` or execution after `DENY`. Prior denial identifiers
are carried for continuity but are explicitly not independently verified. An
action at `LIVE_WRITE` additionally requires the authorization envelope's
separate `liveWriteApprovalRef`.

The standalone entry point is `cgqa-action-guard`; existing output files
require `--force`, and the input file can never be overwritten. See
[`AGENT_ACTION_GUARD.md`](AGENT_ACTION_GUARD.md) for the control graph and
capability ladder.

The public CLI intentionally has no command-execution subcommand. It checks
reviewed traces and already-produced evidence only. A separate isolated runner
may execute tools and export receipts, but its containment, authorization, and
witnessing stay outside this process.

## `cgqa continuity-export`

Project reviewed smart-contract intent, capture, receipt/event, and downstream
observations into the pinned LTP request/outcome input contract.

```bash
cgqa continuity-export \
  --intent intent-attempt-1.json \
  --intent intent-attempt-2.json \
  --capture rpc-capture.json \
  --receipt-trace receipt-adapter-result.json \
  --observations observations.json \
  --as-of 2026-08-27T12:00:00Z \
  --out continuity-input.json \
  --bridge-report-out bridge-report.json
```

The command computes no continuity verdict. Validate the result with the
normative LTP CLI. `--force` is required for existing outputs, and output/input
aliases through direct paths, symbolic links, or hard links are rejected. See
[`SMART_CONTRACT_CONTINUITY_BRIDGE.md`](SMART_CONTRACT_CONTINUITY_BRIDGE.md).

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
