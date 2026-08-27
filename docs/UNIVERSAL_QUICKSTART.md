# Universal Smart-Contract Quickstart

ContractGraph-QA v1.9 adds a safe first command for an unfamiliar local smart-contract repository:

```bash
cgqa quickstart --target /path/to/project
```

The command answers four practical questions before a reviewer builds a deep model:

1. What smart-contract ecosystem and framework appear to be present?
2. Which contract/program source files and declarations are in scope?
3. Which native local test command is available?
4. Which source locations deserve early manual review?

Quickstart is a discovery and routing layer. It is not a universal vulnerability scanner and it does not replace a reviewed ContractGraph-QA state/action/invariant model.

## Safe default

Without additional flags, quickstart does **not execute project code**:

```text
source discovery
→ framework detection
→ exact source hashes
→ project fingerprint
→ declaration inventory
→ bounded review-signal extraction
→ native command plan
→ starter report
```

Default outputs:

```text
<project>/.cgqa/quickstart/
  quickstart.json
  REPORT.md
```

Use another destination when needed:

```bash
cgqa quickstart \
  --target /path/to/project \
  --output-dir /path/to/report
```

An existing output directory is never overwritten implicitly. To replace an output directory inside the target project:

```bash
cgqa quickstart --target . --force
```

`--force` is deliberately restricted to an output path inside the target project.

## Optional native tests

After reviewing the planned command, native tests can be run explicitly:

```bash
cgqa quickstart --target /path/to/project --run-native
```

The command is invoked as a subprocess argument list, not through a shell string. A bounded timeout can be selected:

```bash
cgqa quickstart --target . --run-native --timeout 600
```

The native result is one of:

```text
not_requested
not_available
pass
fail
timeout
error
```

Failure, timeout, or execution error is surfaced as `NATIVE_TESTS_FAILED`; it is never converted into a clean result. Standard output and error are retained in bounded log files under the quickstart output directory.

## Supported discovery routes

| Ecosystem | Framework/marker | Planned native command |
|---|---|---|
| EVM / Solidity | Foundry (`foundry.toml`) | `forge test` |
| EVM / Solidity | Hardhat config or package dependency | local `hardhat test` |
| EVM / Solidity | Truffle config/dependency | local `truffle test` |
| EVM / Vyper | Ape, Brownie, standalone Vyper | `pytest` when available |
| Stellar | Soroban (`soroban-sdk`) | `cargo test` |
| Solana | Anchor (`Anchor.toml` / `anchor-lang`) | `anchor test` |
| Move | `Move.toml` / Move sources | `aptos move test` or `sui move test` |
| Starknet / Cairo | `Scarb.toml` / Cairo sources | `scarb test` |
| EVM / Solidity | standalone `.sol` sources | adapter/test-runner selection required |

Quickstart recognizes `.sol`, `.vy`, `.rs`, `.move`, and `.cairo` source files.

The deep automatic stateful path remains strongest for reviewed Foundry/Solidity engagements. Other ecosystems receive a bounded source inventory, framework/native-test route, and an explicit `adapter_required` result rather than a fabricated universal proof.

## Source inventory boundaries

Quickstart excludes common generated/dependency trees by default:

```text
.git
.cgqa
.venv
artifacts
build
cache
coverage
dist
lib
node_modules
out
target
venv
```

Symlinked directories and files are not followed. To avoid accidental resource exhaustion, the current command limits discovery to:

- 5,000 recognized source files;
- 2 MiB per source file;
- 500 configured review-signal occurrences;
- 256 KiB retained per native test log stream.

Every included source file receives a byte count and SHA-256. The project fingerprint is derived from the sorted source path/hash/size inventory, so it is stable for identical in-scope source bytes even when the repository lives at another absolute path.

## Declaration inventory

Quickstart records recognizable declarations without claiming full parser completeness:

- Solidity contracts, abstract contracts, interfaces, and libraries;
- one Vyper contract per source file;
- Soroban `#[contract]` structs;
- Anchor `#[program]` modules;
- Move modules;
- Cairo modules.

The inventory helps choose an exact target for deeper review. A declaration missing from this bounded parser is a coverage gap, not evidence that the declaration does not exist.

## Solidity review signals

Before matching configured signals, the source is normalized so comments and string contents do not create obvious false positives.

Current prompts include:

```text
TX_ORIGIN
DELEGATECALL
SELFDESTRUCT
LOW_LEVEL_CALL
INLINE_ASSEMBLY
UNCHECKED_ARITHMETIC
TIMESTAMP_DEPENDENCE
SIGNATURE_RECOVERY
CREATE2
```

These are **review prompts**, not findings. For example, a low-level call can be entirely correct when its success, return data, value flow, authorization, and reentrancy behavior are handled deliberately.

A confirmed defect still needs the normal evidence route:

```text
signal
→ exact subject
→ reviewed invariant
→ reproducible path/native RED
→ minimal cause
→ fix
→ native GREEN
→ ContractGraph-QA retest/evidence
```

## Readiness states

The starter result uses bounded readiness descriptions:

```text
READY_FOR_NATIVE_AND_CGQA_REVIEW
READY_FOR_REVIEW_ADAPTER_REQUIRED
BLOCKED_NO_CONTRACT_SOURCES
NATIVE_TESTS_FAILED
```

`READY_FOR_NATIVE_AND_CGQA_REVIEW` means a recognized framework and local native test command were found. It does not mean the project was tested unless `--run-native` was explicitly used.

`READY_FOR_REVIEW_ADAPTER_REQUIRED` means relevant contract sources were found but a deep semantic adapter/model or native tool route is still needed.

## Deep Foundry follow-up

For an authorized Foundry target:

```bash
cgqa quickstart --target . --run-native
cgqa doctor --require-forge
cgqa init-engagement my-contract
```

Then review and replace the scaffold's authorization, exact target, action corpus, future-relevant state, invariants, and capture adapter before running:

```bash
cgqa engagement-run --config engagements/my-contract/cgqa.toml
cgqa verify-engagement-bundle engagements/my-contract/dist/engagement.evidence.zip
```

A public address or public repository is not by itself testing authorization. Use only owned targets, repository-local fixtures, explicitly authorized systems, or assets covered by clearly applicable bounty/safe-harbor rules.

## Unified causal-temporal CLI

The installed `cgqa` command now directly exposes the vNext layers that previously required knowledge of internal Python modules:

```bash
cgqa geometry --model geometry.json
cgqa ancestry --trace ancestry.json
cgqa orient --bundle orientation.json
cgqa witness --input witness.json
cgqa debt --input debt.json
cgqa watch --input watchpoints.json
cgqa replicate --input replication.json
cgqa remediate --input remediation.json
cgqa subject-freeze --input freeze.json
cgqa verification-plan --input plan.json
cgqa trace-integrity --input trace.json
cgqa evidence-readiness --input evidence.json
cgqa root-cause --input findings.json
cgqa metamorphic --input roundtrip.json
cgqa durable-build --root evidence --path finding.json --path trace.json
cgqa durable-verify --root evidence --manifest manifest.json
cgqa plan-verification --input campaign.json
cgqa record-verification-cost --input cost.json
```

All public aliases use the stable `cgqa` exit-code boundary: success is `0`, validation/HOLD/FAIL is `10`, interrupted is `130`, and unexpected internal failure is `70`.

## Non-claims

Quickstart does not claim:

- that every smart-contract language/framework is fully understood;
- that review-signal presence proves vulnerability;
- that absence of a signal proves safety;
- that native tests cover every business/security invariant;
- that a detected contract declaration is the intended deployment target;
- that an open-source/public target is authorized for active testing;
- that deep stateful CGQA can operate without a reviewed semantic adapter/model.

The command makes the first step easy while keeping the final claim bounded and reproducible.
