# Changelog

All notable ContractGraph-QA changes are documented here.

The project follows Semantic Versioning for the product runtime. Engine research increments before v1.0 are retained in Git history and README release notes.

## 1.9.0 — Universal smart-contract quickstart and unified CLI

### Added

- `cgqa quickstart --target <project>` as a safe zero-config front door for local smart-contract repositories;
- deterministic project fingerprints, framework/ecosystem detection, source inventory, contract/program declarations, review signals, native test planning, and a Markdown starter report;
- detection and routing for Foundry, Hardhat, Truffle, Ape/Brownie/Vyper, Soroban, Anchor, Move, and Cairo/Scarb projects;
- optional `--run-native` execution that uses only a detected local command and remains disabled by default;
- installed-wheel access to causal-temporal vNext capabilities through the main `cgqa` command, including witness, debt, watchpoints, replication, proof-integrity, durable reopen, and active-verification planning;
- unified top-level help that makes the previously hidden vNext surface discoverable.

### Fixed

- an installed wheel no longer requires users to know or invoke internal `python -m contractgraph_qa.*_cli` modules for vNext capabilities;
- Phase 2/3/4 sub-CLI validation exits are normalized to the stable public `cgqa` exit-code contract;
- onboarding no longer begins with a blank manual adapter: quickstart first identifies the project, contracts, tools, and exact local next step;
- comments and string literals are removed before Solidity review-signal matching to avoid obvious false positives;
- dependency/build directories and symlinked trees are excluded from source inventory by default.

### Claim boundary

- quickstart review signals are investigation prompts, not vulnerability findings;
- native test success is not a security proof;
- deep stateful ContractGraph-QA analysis still requires a reviewed state/action/invariant model or adapter;
- native project code is never executed unless the operator explicitly passes `--run-native`.

## 1.8.0 — Measurement provenance and source-bound engagement evidence

### Added

- executable Measurement Provenance Gate with explicit `schemaEpoch`, `coverageScope`, expected/observed population, and fail-closed verdicts;
- deterministic negative semantics for `EPOCH_MISMATCH`, `PARTIAL_COVERAGE`, and `UNMEASURED`;
- source-bound change-gate provenance that derives the eligible model population independently from base/head configs and binds exact gate/config digests into client proof;
- provenance-bearing engagement wrapper containing the verified legacy engagement bundle plus `measurement-input.json`, `measurement-source.json`, `measurement-provenance.json`, and a content-addressed outer `bundle.json`;
- installed-wheel Product E2E for the full engagement path, including deterministic byte replay and provenance-wrapper verification outside the repository checkout.

### Evidence and compatibility semantics

- authoritative client evidence now requires a passing measurement-provenance boundary before it can be emitted;
- engagement measurement coverage uses manifest-declared invariant IDs as the independent denominator and emitted checks as the observed population;
- exact manifest/result artifact SHA-256 values are bound into the source receipt, so rehashing an outer bundle cannot legitimize tampered provenance or source evidence;
- `cgqa verify-engagement-bundle` auto-detects legacy engagement bundles and v1.8 provenance wrappers, preserving backward verification compatibility;
- legacy bundle semantics remain independently verified inside the wrapper rather than being replaced by checksums;
- `UNMEASURED` remains unknown rather than being coerced to a false observation, and blocked provenance cannot become authoritative client evidence.

## 1.7.0 — Release trust and portability

### Added

- dedicated Linux + Windows installed-wheel portability gate;
- cross-platform regression that runs the self-serve demo twice outside the checkout and requires byte-identical evidence artifacts;
- explicit canonical-LF assertions for packaged inputs, finding JSON, and Markdown output;
- deterministic CycloneDX 1.5 artifact-level SBOM generation bound to the built wheel, source commit, and release timestamp;
- independent SBOM verification against wheel metadata and SHA-256;
- GitHub/Sigstore artifact attestations for the release checksum manifest and wheel SBOM;
- client-facing GitHub Release quick-start and verification guide;
- tag-triggered GitHub Release publication after all distribution verification and attestations succeed.

### Release trust semantics

- release assets are checksum-verified before attestation or publication;
- an existing GitHub Release for the same tag is never silently overwritten;
- the signed checksum manifest and SBOM attestation are additional supply-chain evidence and do not weaken CGQA evidence-bundle semantic verification;
- portability CI uses only repository-owned demo evidence and performs no external RPC or third-party contract execution.

## 1.6.0 — Self-serve demo and distribution

### Added

- `cgqa demo` runs entirely from the installed wheel and requires no repository checkout or Foundry installation;
- packaged repository-owned demo manifest/result assets;
- the demo produces a deterministic finding JSON, Markdown report, and independently verifiable evidence ZIP in one command;
- wheel package-data configuration explicitly includes only the safe demo JSON assets;
- release/distribution workflow builds the wheel, runs the installed-wheel demo outside checkout, writes SHA-256 checksums, and uploads release artifacts.

### Safety / positioning semantics

- the demo is explicitly repository-owned evidence and is not presented as a third-party audit;
- demo output requires a fresh directory and never overwrites an existing non-empty destination;
- the self-serve demo does not create testing authorization or contact an external RPC;
- real client execution remains behind the existing explicit authorization, fixed-block fork, reviewed manifest, and fail-closed engagement gates.

## 1.5.0 — Client engagement scaffold

### Added

- `cgqa init-engagement <name>` creates a client engagement directory from an installed wheel;
- generated scaffold includes a structurally valid manifest, engagement-run TOML, README checklist, ignored evidence directories, and a Solidity capture `.example`;
- working-directory paths are derived from the current ContractGraph-QA project root;
- scaffold output explicitly reports `executionReady: false` until the TODOs and capture adapter are implemented;
- Product E2E exercises scaffold creation from outside the checkout using the installed wheel.

### Safety / onboarding semantics

- engagement names are restricted to a safe artifact character class;
- scaffold destinations must be new directories inside the current project root and are never overwritten;
- the generated Solidity capture is not compiled by default and contains a fail-closed `CGQA scaffold not configured` sentinel;
- generated manifests use explicit TODO markers for authorization, target, state, actions, and invariants so placeholder facts are visible during review;
- creating a scaffold does not authorize a target and does not produce validated security evidence.

## 1.4.0 — One-command engagement-run

### Added

- `cgqa engagement-run --config <file>` executes direct multi-invariant Foundry capture and engagement packaging in one product command;
- strict engagement-run TOML configuration for working directory, manifest, generated result, output directory, bundle, and capture test/profile;
- manifest fingerprint is computed before execution and injected into Foundry capture automatically;
- generated engagement result is immediately validated through the existing engagement semantic chain;
- the final bundle is independently re-opened and verified before the command returns success;
- repository-owned Product E2E executes the complete flow twice and requires byte-for-byte identical evidence bundles.

### Safety / execution semantics

- engagement-run always performs fresh Foundry capture; pre-existing result-only packaging remains the separate `cgqa engagement` command;
- capture profile and test names are allow-listed and invoked as a subprocess argument array, never as a shell command string;
- output directory collisions with the working directory or manifest directory are rejected;
- existing authorization/safe-harbor requirements remain unchanged for any real fork target;
- `not_found_within_bound` and `inconclusive` retain the v1.2/v1.3 bounded-evidence semantics.

## 1.3.0 — Direct multi-invariant Foundry capture

### Added

- one bounded breadth-first state-space walk evaluates every declared invariant in the same search session;
- per-invariant outcomes are recorded as `violated`, `not_found_within_bound`, or `inconclusive`;
- shortest discovered path evidence is retained independently for each violated invariant;
- unresolved invariants become `inconclusive` when the search cannot complete its declared transition/state budget;
- a test-only deterministic engagement-result writer emits the v1.2 runtime contract directly from Foundry;
- repository-owned capture fixture proves one search can produce one violation, one bounded no-finding outcome, and one inconclusive outcome;
- Product CI compares direct Foundry engagement capture byte-for-byte with the checked-in golden result before packaging the engagement bundle.

### Safety / evidence semantics

- direct capture is still bounded evidence and does not imply complete protocol security;
- equivalent-state pruning remains conditional on a complete future-relevant state hash;
- `inconclusive` is fail-closed and cannot be silently converted to a clean result;
- the default capture fixture is repository-local and performs no third-party network interaction.

## 1.2.0 — Multi-invariant engagement engine

### Added

- one engagement result can classify every manifest invariant as `violated`, `not_found_within_bound`, or `inconclusive`;
- full declared-invariant coverage is mandatory: omitted and unknown invariant checks fail closed;
- every violated invariant is exported into its own deterministic finding JSON and Markdown report;
- one deterministic engagement summary reports coverage counts and all invariant outcomes;
- one deterministic v2 engagement evidence ZIP contains manifest, search result, engagement summary/report, and every finding artifact;
- `cgqa engagement` and `cgqa verify-engagement-bundle` commands;
- engagement-result JSON Schema and schema/runtime parity checks;
- regression coverage for provenance mismatch, false clean statuses, unsafe artifact IDs, tampering, and semantic bundle verification.

### Safety / evidence semantics

- `not_found_within_bound` is explicitly bounded evidence, not a security claim;
- `inconclusive` cannot carry a clean conclusion or a synthetic finding;
- finding IDs used as artifact paths are restricted to a safe filename character class;
- engagement bundles reject duplicate, reordered, unexpected, oversized, traversal, or semantically inconsistent entries;
- bundle verification preserves the producer tool version so evidence remains independently verifiable across future runtime upgrades.

## 1.0.0 — Product runtime

### Added

- installable Python package and `cgqa` command;
- strict TOML product configuration;
- one-command local pipeline: capture → validate → finding → report → evidence bundle;
- deterministic ZIP evidence bundles with per-artifact SHA-256 and byte counts;
- independent `cgqa verify-bundle` semantic verification;
- `cgqa doctor`, `validate`, and `fingerprint` operator commands;
- stable product exit-code contract;
- end-to-end product CI using the repository-owned adapter fixture;
- product, CLI, engagement, and release documentation.

### Security / safety

- capture invocation uses argument arrays, never a shell command string;
- capture profile/test names are allow-listed by character class;
- input/output artifact paths must be distinct;
- evidence ZIP entry names/order are fixed and entry sizes are capped;
- bundles are rejected if hashes, sizes, manifest/result provenance, finding export, or report rendering do not verify;
- authorized fork execution remains governed by the existing v0.6/v0.7 scope gates.

## 0.9.0

- direct Foundry capture of discovered/replayed paths into explorer-result JSON.

## 0.8.0

- reviewed adapter manifest + strict result contract + automatic finding export.

## 0.7.0

- fixed-block fork adapter template.

## 0.6.0

- authorization-gated fork context.

## 0.5.0

- state hashing and equivalent-state deduplication.

## 0.4.0

- parameter and time exploration.

## 0.3.0

- deterministic finding reports.

## 0.2.0

- bounded breadth-first path exploration and replay.

## 0.1.0

- causal-temporal graph model, fixtures, invariants, Foundry tests, CI, and Slither.
