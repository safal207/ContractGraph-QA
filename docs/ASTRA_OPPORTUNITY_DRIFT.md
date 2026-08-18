# ASTRA Opportunity Drift Watch v0.1

Opportunity Drift Watch compares two frozen Opportunity Exact-Head scorecards for the same company without rewriting the earlier record.

## Purpose

The watch answers a narrow question:

> Has the product moved into a materially different execution state that deserves renewed verification attention?

It is not a CRM auto-send engine and it never authorizes outreach.

## Core distinctions

```text
score changed
!=
product changed

product generation changed
!=
new execution surface proven

new public claim
!=
coherent current evidence

prior strong lead
!=
current strong lead
```

## Classification

- `STABLE` — no material observed drift.
- `SCORE_DRIFT_ONLY` — analyst score changed without execution-surface evidence; no automatic promotion.
- `GENERATION_DRIFT` — product generation changed but no new execution surface is yet proven; reverify.
- `MATERIAL_POSITIVE_DRIFT` — a new reviewed execution surface is present; prioritize review.
- `NEGATIVE_DRIFT` — a previously reviewed execution surface disappeared.
- `REVERIFY` — current scorecard is incomplete or held.
- `IDENTITY_DRIFT` — scorecards do not resolve to the same company identity.

## Positive-transition rule

A company is not promoted merely because its TOS/score rises. Positive material drift requires a newly reviewed execution surface, for example:

```text
read-only finance assistant
→ payment initiation

single-chain wallet
→ cross-chain autonomous routing

manual payout
→ agent-triggered payout

recommendation engine
→ direct financial mutation
```

The output remains advisory-only:

```text
MATERIAL_POSITIVE_DRIFT
→ PRIORITIZE_REVIEW
→ fresh exact-head scorecard
→ human/outreach decision outside this module
```

## History rule

The previous scorecard remains immutable history. Drift creates a new observation; it never edits the old score to make the trajectory look cleaner in hindsight.
