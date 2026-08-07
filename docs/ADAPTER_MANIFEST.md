# Adapter manifest and automatic finding export

v0.8 separates contract-specific QA metadata from the report renderer.

A reviewed adapter manifest describes the authorized engagement surface and the human-readable meaning of actions and invariants. A deterministic explorer result contains the discovered path and replay evidence. `tools/export_finding.py` joins both inputs into the existing finding JSON contract, which can then be rendered by `tools/render_finding.py`.

## Pipeline

```text
authorized adapter
      ↓
explorer result JSON
      +
adapter manifest JSON
      ↓
strict provenance + evidence validation
      ↓
tools/export_finding.py
      ↓
CGQA-xxx.finding.json
      ↓
tools/render_finding.py
      ↓
CGQA-xxx.md
```

## Adapter manifest

The manifest is reviewable before execution and contains:

- adapter ID;
- contract and network/environment label;
- scope ID, authorization wording/reference, and target identifier;
- bounded search depth;
- future-relevant state-field names;
- allowed action IDs, display templates, and actors;
- invariant IDs and client-facing finding metadata.

Machine-readable schema:

`graph/schema/adapter-manifest.schema.json`

Example:

`manifests/examples/adapter-fixture.json`

### Parameterized action display

An action display may contain the literal placeholder `{parameter}`:

```json
{
  "id": "deposit",
  "display": "deposit({parameter})",
  "actor": "authorized depositor"
}
```

The explorer result must then contain a string or integer `parameter` for that step. Supplying a parameter to an action without the placeholder is rejected so evidence cannot be silently reformatted.

## Explorer result

The exporter accepts a deterministic result containing:

- the exact adapter ID and scope ID used for the run;
- finding ID;
- invariant ID;
- exact replay command;
- optional explored-candidate count and notes;
- ordered path steps with action ID, pre-state, post-state, effect, and optional parameter.

Machine-readable schema:

`graph/schema/explorer-result.schema.json`

Example:

`results/examples/CGQA-005.result.json`

The exporter requires `result.adapterId == manifest.adapterId` and `result.scopeId == manifest.scope.scopeId`. It also rejects a path whose length exceeds the manifest's declared `search.maxDepth`.

The result does not duplicate actor names, action labels, severity, summary, impact, recommendation, contract, network, or authorization text. Those come from the reviewed manifest.

## Export

```bash
python tools/export_finding.py \
  manifests/examples/adapter-fixture.json \
  results/examples/CGQA-005.result.json \
  --output /tmp/CGQA-005.finding.json
```

Then render:

```bash
python tools/render_finding.py \
  /tmp/CGQA-005.finding.json \
  --output /tmp/CGQA-005.md
```

For deterministic CI checks:

```bash
python tools/export_finding.py \
  manifests/examples/adapter-fixture.json \
  results/examples/CGQA-005.result.json \
  --check reports/examples/CGQA-005.finding.json

python tools/render_finding.py \
  reports/examples/CGQA-005.finding.json \
  --check reports/examples/CGQA-005.md
```

## Fail-closed validation

The exporter rejects, among other cases:

- missing/empty authorization metadata;
- adapter or scope provenance mismatch;
- a discovered path deeper than the manifest search depth;
- duplicate action or invariant IDs;
- unknown action IDs in the result;
- unknown invariant IDs;
- empty paths;
- malformed candidate counts;
- missing parameters required by a display template;
- unexpected parameters for non-parameterized actions.

The manifest's `stateFields` are documentation/review evidence in v0.8. The Solidity adapter's `_stateHash()` remains the executable source of truth, so reviewers must verify that the manifest list and actual hash implementation match.

## Safety boundary

A manifest is not authorization. The v0.6 authorization gate and v0.7 fork adapter remain the execution boundary for real fork testing.

Do not treat a public address, a manifest file, or a discovered ABI as permission to test a third-party production target.

## v0.8 boundary

v0.8 automates deterministic conversion from **manifest + machine-readable explorer result** to the existing client finding/report contract.

It does not yet automatically capture Solidity explorer output into result JSON. Direct Foundry path export, manifest-to-adapter code generation, and automatic invariant synthesis are follow-up work.
