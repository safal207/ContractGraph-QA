# Finding reports

v0.3 turns a discovered invariant violation into a deterministic, client-facing Markdown finding.

The reporting layer is intentionally separate from the search layer:

```text
Path Explorer
  ↓
Machine-readable finding JSON
  ↓
Validation
  ↓
Deterministic Markdown renderer
  ↓
Replay / fix / retest evidence
```

## Why this matters

A useful QA result is not only "a test failed". A reviewer or client needs a bounded claim with enough evidence to reproduce and verify it.

The report format captures:

- finding ID and severity;
- target contract and environment;
- executive summary;
- violated invariant;
- minimal failing path;
- impact;
- replay command;
- authorization/scope statement;
- recommendation;
- retest checklist.

## Generate a report

```bash
python tools/render_finding.py \
  reports/examples/CGQA-001.finding.json \
  --output /tmp/CGQA-001.md
```

On Windows PowerShell:

```powershell
python tools/render_finding.py reports/examples/CGQA-001.finding.json --output CGQA-001.md
```

## Verify deterministic output

The checked-in example is treated as a golden report:

```bash
python tools/render_finding.py \
  reports/examples/CGQA-001.finding.json \
  --check reports/examples/CGQA-001.md
```

CI also runs unit tests for the renderer.

## Required evidence

The renderer rejects a finding when key evidence is missing. In particular:

- the failing path must contain at least one step;
- steps must be contiguous and 1-based;
- every step must identify actor, action, pre-state, post-state and effect;
- the invariant must have an ID and expression;
- replay instructions are required;
- an authorization/scope statement is required.

This prevents a visually polished report from being generated without a minimal evidence chain.

## Scope boundary

The Markdown output is a QA/security finding artifact, not a certification that an arbitrary contract is secure. Conclusions remain limited to the modeled actions, parameters, actors, time assumptions, search depth and explicit invariants.

Use the workflow only on owned, local, open-source, explicitly authorized or in-scope bug-bounty targets.
