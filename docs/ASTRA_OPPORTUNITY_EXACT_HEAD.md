# ASTRA Opportunity Exact-Head Scorecard v0.1

This layer applies LS-style exact-state and fail-closed discipline to ASTRA opportunity analysis.

It is an advisory sales/research scorecard. It does **not** authorize outreach, make vulnerability claims, or convert a high score into evidence.

## Core rule

```text
high opportunity score
!=
current evidence
!=
coherent identity
!=
action authority
```

A candidate is evaluated against one frozen reviewed product state:

```text
company identity
→ initial product generation
→ reviewed public source set
→ execution-surface check
→ evidence-freshness check
→ reachability check
→ final product generation
→ OUTREACH / HOLD / INCOMPLETE
```

The initial and final product-generation tokens must match. Any drift produces `HOLD` even when the opportunity score is 10/10.

`NOT_RUN` and `INCOMPLETE` never become `PASS`.

## Required checks

- `identity`: reviewed sources belong to the intended company/product lineage;
- `execution_surface`: the observed product actually performs or controls the financial/state mutation of interest;
- `evidence_freshness`: the reviewed evidence is current enough for the decision;
- `reachability`: a verified route exists for the intended team/contact class.

Allowed statuses are:

```text
PASS
HOLD
INCOMPLETE
NOT_RUN
```

Decision precedence:

```text
product-generation drift → HOLD
any HOLD                → HOLD
any INCOMPLETE/NOT_RUN  → INCOMPLETE
all required PASS       → OUTREACH
```

The result remains `advisory_only=true` and `outreach_authorized_by_scorecard=false` in every case.

## Evidence identity

`source_set_digest` is SHA-256 over the canonical reviewed source records (`source_id`, locator, claim, and any explicitly included reviewed metadata). It freezes what the analyst reviewed. It is **not** a byte-level attestation of a remote website and must not be described as one.

If remote content needs strong exact-byte provenance, that is a separate capture problem.

## Privacy boundary

The public benchmark must not embed private client correspondence, private email addresses, or message bodies. Reachability may be represented as a reviewed status without publishing private evidence.

```text
private correspondence
!=
public benchmark cargo
```

## First frozen cohort

`benchmarks/astra-v0.1/opportunity-exact-head-2026-08-18.json` freezes four reviewed opportunities using public product evidence only:

- Passes → `OUTREACH`
- Kastle → `OUTREACH`
- FullSeam → `OUTREACH`
- Grade → `INCOMPLETE` because reachability remains unresolved in the public scorecard

These are opportunity-analysis outputs, not statements that any company has a defect or verification failure.

## Relationship to ASTRA, ATMAN, and LS

```text
ASTRA   → where pressure/opportunity is concentrated
ATMAN   → what is known, uncertain, and worth checking next
LS rule → bind the conclusion to one exact reviewed state and fail closed on drift
```

The combined invariant is:

```text
signal
→ lineage
→ exact reviewed state
→ evidence
→ coherence gate
→ advisory action
```

A later response, product change, documentation change, or newly discovered control creates a new scorecard generation. Historical scorecards are not rewritten to match later knowledge.
