# ContractGraph-QA Client Proof Pack

This pack is the shortest path from **technical capability** to a **client-understandable proof of value**.

It does not claim a completed third-party security audit. The worked cases are repository-owned local fixtures designed to show exactly what ContractGraph-QA produces and how the evidence can be independently recomputed.

## The client question

> What do I get if I pay for a ContractGraph-QA pilot?

You get a bounded, reproducible Smart Contract / agent-payment QA engagement focused on explicit business/security invariants, reachable state transitions, containment/recovery, and fix verification.

Typical evidence chain:

```text
AUTHORIZED SCOPE
      ↓
REVIEWED MANIFEST / MODEL
      ↓
BOUNDED SEARCH
      ↓
VIOLATED / NOT_FOUND_WITHIN_BOUND / INCONCLUSIVE
      ↓
MINIMAL REPLAYABLE PATH
      ↓
FORBIDDEN CAPABILITY + IMPACT
      ↓
CONTAINMENT → RECOVERY → VERIFICATION
      ↓
FIX
      ↓
EXACT HISTORICAL PATH REPLAY
      ↓
ALTERNATE-PATH SEARCH
      ↓
PR CHANGE GATE RESULT
      ↓
CONTENT-ADDRESSED CLIENT EVIDENCE
```

## Proof case

The repository-owned demo engagement `CGQA-E-001` checks three invariants in one bounded search session and records three distinct evidence outcomes:

- **1 violated** — the terminal-state invariant is broken by the shortest path `advance → advance → advance`;
- **1 not_found_within_bound** — no negative phase is found inside the declared action corpus and `maxDepth=4` model;
- **1 inconclusive** — an intentionally unresolved property remains unresolved instead of being misreported as clean.

See [`SAMPLE_ENGAGEMENT.md`](SAMPLE_ENGAGEMENT.md).

## Causal security proof

`proof.json` now also carries a separate repository-owned causal fixture. It is intentionally labeled separately from `CGQA-E-001` so the engagement evidence is not conflated with the reachability/control demo.

The causal proof binds one client-readable chain:

```text
broken assumption
→ cross-terminal-state-boundary
→ adapter-terminal-state invariant
→ terminal-state-boundary
→ terminal-state-reachable (forbidden)
→ modeled impact
→ contained_by
→ recovered_by
→ restores_to advance-state-machine
→ verified_by
→ proposed fix
→ exact historical path blocked by restored assumption guard
→ no alternate path to the same forbidden capability
→ fix_verified
```

The checked-in proof is regression-tested against the live reachability, post-impact, and replay engines. If the machine semantics drift, the proof-pack tests fail rather than leaving a stale client narrative.

The claim boundary remains explicit: this is an authorized repository-local model demonstration. It is not proof of production exploitability and not an exhaustive security certification.

## Bind PR change-gate evidence

The pull-request gate already emits one canonical machine result: `.cgqa/causal-security-gate.json`. Client proof packs consume that **same object** instead of reconstructing targets, invariants, paths, or fix conclusions a second time.

Bind an exact gate artifact into a proof pack with:

```bash
python tools/bind_change_gate_client_proof.py \
  --proof docs/client-proof/proof.json \
  --gate-result .cgqa/causal-security-gate.json \
  --output .cgqa/client-proof.with-gate.json
```

The resulting `changeGateEvidence` contains:

- `schema = cgqa.client-change-gate-evidence.v1`;
- the complete gate result, preserved verbatim as JSON semantics;
- a canonical SHA-256 over that exact result.

The client-proof layer validates only the result envelope needed for identity binding: schema version, `PASS / REVIEW / BLOCK`, exact base commit SHA, exact head commit SHA, and the model-result array. It deliberately does **not** re-derive forbidden targets, invariants, shortest paths, or replay status. Those claims remain owned by the gate JSON itself.

`verify_change_gate_evidence(...)` recomputes the canonical digest and rejects nested tampering. Rebinding a proof pack to a different gate result also fails closed instead of silently replacing historical review evidence. A `blocked` gate result is still valid client evidence; a fatal runner/config error without explicit commit identity is not.

This gives one continuous delivery-to-client chain:

```text
PR base/head
→ causal security gate JSON
→ introduced forbidden path OR exact verified fix replay
→ CI decision
→ canonical gate-result digest
→ client proof pack
```

## Reproduce the proof

From the repository root:

```bash
cgqa engagement-run --config cgqa.engagement.example.toml
cgqa verify-engagement-bundle dist/CGQA-E-001-run/CGQA-E-001.engagement.zip

cgqa reachability --model scenarios/adversarial-adapter-fixture.json
cgqa reachability-replay \
  --prior-model scenarios/adversarial-adapter-fixture.json \
  --fixed-model scenarios/adversarial-adapter-fixture-fixed.json
```

The Product E2E workflow runs the installed `cgqa` wheel outside the checkout, performs the engagement twice, requires byte-for-byte identical ZIP output, and verifies the final bundle independently. Unit regressions also recompute the client proof's causal path, control graph, exact fix replay, and content-addressed change-gate binding.

## Commercial pilot

See [`PILOT_OFFER.md`](PILOT_OFFER.md) for a fixed-scope offer designed to reduce buying friction without presenting ContractGraph-QA as a replacement for a formal protocol security audit.

Default pilot anchor:

**$200 fixed** for a small authorized contract/feature slice, including modeled invariants, bounded state-transition search, reproducible findings, evidence bundle, and one retest pass.

## Outreach

See [`OUTREACH.md`](OUTREACH.md) for concise messages suitable for founders, protocol teams, Solidity developers, agent-payment teams, and audit-readiness leads.

## Positioning boundary

ContractGraph-QA is strongest as:

- Smart Contract and programmable-wallet QA;
- stateful functional/invariant testing;
- adversarial capability reachability;
- containment/recovery evidence;
- Foundry regression/fuzz/invariant readiness;
- audit-readiness evidence;
- reproducible defect discovery and exact-path retest.

A successful run means the **declared bounded model and evidence chain verified**. It does **not** mean the target is exhaustively secure.
