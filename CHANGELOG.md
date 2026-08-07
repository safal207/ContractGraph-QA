# Changelog

All notable ContractGraph-QA changes are documented here.

The project follows Semantic Versioning for the product runtime. Engine research increments before v1.0 are retained in Git history and README release notes.

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
