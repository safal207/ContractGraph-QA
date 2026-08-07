# Direct Foundry result capture

v0.9 removes the last manually authored evidence handoff between the Solidity explorer and the v0.8 manifest/report pipeline.

## Pipeline

```text
bounded dedup BFS
      ↓
minimal violating StepInput[]
      ↓
deterministic replay
      ↓
pre-state / post-state / effect capture
      ↓
Foundry writes explorer-result JSON
      ↓
manifest provenance validation
      ↓
finding JSON
      ↓
client Markdown report
```

The checked-in regression uses only `AdapterFixtureMachine`, a repository-owned local fixture. Default contract CI remains separate from the capture profile.

## Isolation

Direct filesystem output is enabled only under the dedicated Foundry profile:

```toml
[profile.capture]
test = "capture-test"
fs_permissions = [{ access = "read-write", path = "./results/generated" }]
```

The normal profile does not receive filesystem write permission from v0.9.

The capture output path is fixed inside the regression to:

`results/generated/CGQA-005.result.json`

## Manifest provenance

The capture test does not hard-code the v0.8 manifest fingerprint. CI computes the canonical SHA-256 using the same Python implementation used by the exporter:

```bash
python tools/manifest_fingerprint.py manifests/examples/adapter-fixture.json
```

The digest is passed to Foundry as `CGQA_MANIFEST_SHA256`. The Solidity writer accepts only a 64-character lowercase hexadecimal SHA-256 value. The downstream v0.8 exporter then recomputes the canonical manifest fingerprint and requires exact equality.

This creates two provenance gates:

1. Solidity capture refuses malformed fingerprint syntax.
2. Python export refuses a syntactically valid fingerprint that does not match the reviewed manifest.

## Deterministic evidence capture

The local regression first executes the real deduplicating explorer. It then replays the returned minimal path from a fresh baseline and derives each result step from observed state:

```text
phase=0 --advance--> phase=1
phase=1 --advance--> phase=2
phase=2 --advance--> phase=3
```

The generated file must match `results/examples/CGQA-005.result.json` byte-for-byte before the reporting pipeline continues.

CI then feeds the generated file, not the hand-authored fixture, into `tools/export_finding.py`.

## Run locally

```bash
export CGQA_MANIFEST_SHA256="$(python tools/manifest_fingerprint.py manifests/examples/adapter-fixture.json)"
FOUNDRY_PROFILE=capture forge test --match-test test_CaptureExplorerResult -vvv
cmp results/generated/CGQA-005.result.json results/examples/CGQA-005.result.json
```

Then run the downstream conversion:

```bash
python tools/export_finding.py \
  manifests/examples/adapter-fixture.json \
  results/generated/CGQA-005.result.json \
  --check reports/examples/CGQA-005.finding.json
```

## Safety boundary

v0.9 does not expand testing authorization. The regression is local-only and does not open an external fork.

For a future client fork adapter, the existing v0.6 authorization gate and v0.7 fixed-block adapter boundary still apply. The capture layer records evidence after an authorized test; it is not permission to execute one.

## v0.9 boundary

v0.9 proves direct Foundry-to-result capture for a deterministic local adapter regression. Contract-specific action labels, state descriptions, and effect descriptions are still explicit adapter code.

Planned follow-up work can generalize those description hooks across fork adapters and package a single command that runs capture → export → render for an authorized engagement.
