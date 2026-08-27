# Universal Quickstart Hardening

`cgqa quickstart` is a discovery and routing layer for unfamiliar smart-contract repositories. It is intentionally safer and more conservative than an automatic audit button.

## Exact project subject

The v0.2 quickstart subject binds both:

```text
contract/program source bytes
+
build, compiler, dependency, framework, and lock configuration bytes
```

The report exposes separate `sourceFingerprint`, `configurationFingerprint`, and combined `projectFingerprint` values. A compiler/configuration change therefore cannot silently reuse evidence produced for an older project subject.

When `--run-native` is used, CGQA re-scans the subject after the native command. Source/config or Git-status drift produces:

```text
STALE_SUBJECT_AFTER_NATIVE_TESTS
```

A passing native command is not attributed to the earlier subject after that boundary moves.

## Native execution safety

Native project code is never executed unless `--run-native` is explicit.

By default, native tests receive a sanitized environment and an isolated temporary HOME. Likely API keys, tokens, provider/RPC URLs, passwords, mnemonics, seed phrases, and private keys are not inherited. Git global/system configuration and npm user configuration are also isolated.

A project that genuinely requires operator-provided environment state must use the visibly stronger opt-in:

```bash
cgqa quickstart --target /path/to/project --run-native --inherit-env
```

`--inherit-env` transfers responsibility for those credentials to the operator. The report records the environment policy and variable names, never their values.

Missing native tools are not success:

```text
--run-native + no usable runner
→ BLOCKED_NATIVE_TOOL_MISSING
→ HOLD / exit 10
```

Timeouts terminate the native process group where the platform supports it.

## Monorepos and ecosystems

Quickstart scans bounded nested project roots rather than assuming the selected directory itself is the only contract project. It can route common EVM, Stellar/Soroban, Solana/Anchor, Move, Cairo/Scarb, Fuel/Sway, TON/Tact, Tezos/LIGO, CosmWasm, NEAR, ink!, Stylus, and native Rust/Solana layouts.

Framework-specific commands run from the detected nested project root. Dependency/build trees remain excluded. Foundry `lib/` is excluded only at an actual Foundry project root, so unrelated first-party `lib/` directories are not globally discarded.

## Incomplete inventory

Unreadable, oversized, or otherwise uninspected source/configuration files remain visible evidence debt:

```text
INCOMPLETE_PROJECT_INVENTORY
```

Quickstart does not convert a partial inventory into a clean result.

## Atomic reports

`--force` builds the replacement report in a sibling staging directory. The previous report is moved only after the new JSON and Markdown are complete. A failed refresh therefore preserves the last durable report.

External existing output directories are never recursively replaced with `--force`; replacement authority is limited to a destination inside the target project.

## What “easy testing” means

The intended path is:

```text
cgqa quickstart --target PROJECT
→ exact project/framework/contract inventory
→ optional native tests
→ reviewed next step
→ cgqa init-engagement for deep stateful work
→ model + invariants + negative controls
→ deterministic evidence bundle
```

Quickstart signals are investigation prompts. Native test success is not a security proof. Deep causal-temporal claims still require a reviewed model/adapter, explicit invariants, and reproducible evidence.
