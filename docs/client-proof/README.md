# ContractGraph-QA Client Proof Pack

This pack is the shortest path from **technical capability** to a **buyer-understandable proof of value**.

It contains repository-owned demonstrations and product materials. It does not claim a completed third-party security audit.

## Start with the buyer problem

For payment, wallet, payout, stablecoin, ledger, and agentic-commerce teams:

> After an ambiguous execution result, what evidence proves `ZERO`, `ONE`, or `UNKNOWN` economic effects before retry?

For smart-contract teams:

> Can an allowed sequence of actors, calls, values, retries, ordering, and time changes reach a state that violates an explicit business or security invariant?

## Primary product route

The [Ambiguous Outcome Recovery Pilot](../../PILOT.md) verifies one named recovery boundary for a design-partner price of **$750 fixed**.

It produces:

- an expected-state contract;
- an evidence-precedence map;
- one executable local or sandbox-backed fixture;
- deterministic recovery verdicts;
- a minimized unsafe trace where applicable;
- bounded remediation and one retest.

See the [synthetic payment-recovery case study](../case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md).

## Repository-owned engine proof

The sample engagement `CGQA-E-001` demonstrates three distinct evidence outcomes in one bounded session:

- **violated** — a shortest replayable path reaches the forbidden state;
- **not_found_within_bound** — no violation was found inside the declared model and search bound;
- **inconclusive** — missing evidence remains unresolved instead of becoming a fake PASS.

See [SAMPLE_ENGAGEMENT.md](SAMPLE_ENGAGEMENT.md).

The causal fixture in `proof.json` separately demonstrates:

```text
broken assumption
→ capability
→ control boundary / invariant
→ forbidden capability
→ modeled impact
→ containment
→ recovery
→ exact replay
→ alternate-path search
→ fix verification
```

These are repository-local demonstrations of workflow and evidence semantics, not claims about an external provider.

## Evidence chain

```text
AUTHORIZED SCOPE / EXACT SUBJECT
      ↓
REVIEWED MODEL
      ↓
BOUNDED SEARCH
      ↓
VIOLATED / NOT_FOUND_WITHIN_BOUND / INCONCLUSIVE
      ↓
MINIMAL REPLAYABLE PATH
      ↓
EVIDENCE MAP + PROVENANCE
      ↓
FIX
      ↓
EXACT RETEST
      ↓
CONTENT-ADDRESSED CLIENT EVIDENCE
```

## Reproduce the sample engagement

```bash
cgqa engagement-run --config cgqa.engagement.example.toml
cgqa verify-engagement-bundle \
  dist/CGQA-E-001-run/CGQA-E-001.engagement.zip
```

The Product workflow runs the installed wheel outside the checkout, repeats the engagement, checks deterministic output, and independently verifies the final bundle.

## Advanced evidence binding

The pull-request causal security gate, exact historical path replay, and client-proof binding remain documented separately in [Causal Security Change Gate](../CHANGE_GATE.md). This buyer-facing pack links to that authoritative technical contract instead of re-deriving the gate semantics here.

## Commercial materials

- [Primary Recovery Pilot](../../PILOT.md)
- [Design-Partner Pilot Offer](PILOT_OFFER.md)
- [Question-First Outreach](OUTREACH.md)
- [Synthetic Recovery Case Study](../case-studies/AMBIGUOUS_PAYMENT_RECOVERY.md)
- [Sample Smart-Contract Engagement](SAMPLE_ENGAGEMENT.md)

## Positioning boundary

ContractGraph-QA is strongest as:

- ambiguous-outcome recovery verification;
- payment, wallet, payout, and ledger state-machine QA;
- smart-contract stateful/invariant testing;
- adversarial capability reachability;
- containment and recovery evidence;
- reproducible defect discovery and exact-path retest.

A successful run means the **declared bounded model and evidence chain verified**. It does not mean the target is exhaustively secure.
