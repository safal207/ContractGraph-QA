# Changelog

All notable ContractGraph-QA changes are documented here.

The project follows Semantic Versioning for the product runtime. Engine research increments before v1.0 are retained in Git history and README release notes.

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
