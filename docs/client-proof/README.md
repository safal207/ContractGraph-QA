# ContractGraph-QA Client Proof Pack

This pack is the shortest path from **technical capability** to a **client-understandable proof of value**.

It does not claim a completed third-party security audit. The worked case is a repository-owned local fixture designed to show exactly what ContractGraph-QA produces and how the evidence can be independently verified.

## The client question

> What do I get if I pay for a ContractGraph-QA pilot?

You get a bounded, reproducible Smart Contract QA engagement focused on explicit business/security invariants and reachable state transitions.

Typical evidence chain:

```text
AUTHORIZED SCOPE
      ↓
REVIEWED MANIFEST
      ↓
FOUNDRY MULTI-INVARIANT SEARCH
      ↓
VIOLATED / NOT_FOUND_WITHIN_BOUND / INCONCLUSIVE
      ↓
MINIMAL REPLAYABLE PATH(S)
      ↓
FINDING JSON + CLIENT MARKDOWN
      ↓
ENGAGEMENT COVERAGE SUMMARY
      ↓
DETERMINISTIC EVIDENCE ZIP
      ↓
INDEPENDENT VERIFICATION
```

## Proof case

The repository-owned demo engagement `CGQA-E-001` checks three invariants in one bounded search session and records three distinct evidence outcomes:

- **1 violated** — the terminal-state invariant is broken by the shortest path `advance → advance → advance`;
- **1 not_found_within_bound** — no negative phase is found inside the declared action corpus and `maxDepth=4` model;
- **1 inconclusive** — an intentionally unresolved property remains unresolved instead of being misreported as clean.

See [`SAMPLE_ENGAGEMENT.md`](SAMPLE_ENGAGEMENT.md).

## Reproduce the proof

From the repository root:

```bash
cgqa engagement-run --config cgqa.engagement.example.toml
cgqa verify-engagement-bundle dist/CGQA-E-001-run/CGQA-E-001.engagement.zip
```

The Product E2E workflow also runs the installed `cgqa` wheel outside the checkout, performs the engagement twice, requires byte-for-byte identical ZIP output, and verifies the final bundle independently.

## Commercial pilot

See [`PILOT_OFFER.md`](PILOT_OFFER.md) for a fixed-scope offer designed to reduce buying friction without presenting ContractGraph-QA as a replacement for a formal protocol security audit.

Default pilot anchor:

**$200 fixed** for a small authorized contract/feature slice, including modeled invariants, bounded state-transition search, reproducible findings, evidence bundle, and one retest pass.

## Outreach

See [`OUTREACH.md`](OUTREACH.md) for concise messages suitable for founders, protocol teams, Solidity developers, and audit-readiness leads.

## Positioning boundary

ContractGraph-QA is strongest as:

- Smart Contract QA;
- stateful functional/invariant testing;
- Foundry regression/fuzz/invariant readiness;
- audit-readiness evidence;
- reproducible defect discovery and retest.

A successful run means the **declared bounded model and evidence chain verified**. It does **not** mean the contract is exhaustively secure.
