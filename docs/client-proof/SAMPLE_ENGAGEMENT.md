# Sample Engagement — CGQA-E-001

## Executive summary

This is a **repository-owned local demonstration**, not a third-party client audit.

ContractGraph-QA runs one bounded state-space search across three declared invariants and preserves the outcome of each invariant independently. The purpose of the case is to show a prospective client the exact shape of evidence they receive: what was violated, what was not found inside the declared bound, what remains inconclusive, and how the result can be replayed and verified.

## Scope

- **Engagement:** `CGQA-E-001`
- **Adapter:** `engagement-fixture-v1.3`
- **Scope:** `local-v1.3-engagement-fixture`
- **Target:** repository-owned local fixture
- **Network:** `local-foundry-engagement`
- **Search depth:** `4`
- **Authorization:** repository-owned fixture; no third-party production target is involved

## Outcome

| Invariant | Status | Evidence |
|---|---|---|
| `terminal-state-bound` | `violated` | shortest path reaches `phase=3` |
| `phase-nonnegative` | `not_found_within_bound` | no negative phase found in declared bounded model |
| `budget-sensitive-branch` | `inconclusive` | intentionally unresolved; not promoted to a clean result |

Coverage summary:

```text
3 declared invariants
3 checked invariants
1 violated
1 not_found_within_bound
1 inconclusive
```

## Finding — terminal state becomes reachable

**Finding ID:** `CGQA-E-001-F01`

**Invariant:**

```text
phase < 3
```

**Minimal failing path:**

| Step | Action | Pre-state | Post-state | Effect |
|---:|---|---|---|---|
| 1 | `advance()` | `phase=0` | `phase=1` | first future-relevant state reached |
| 2 | `advance()` | `phase=1` | `phase=2` | second future-relevant state reached |
| 3 | `advance()` | `phase=2` | `phase=3` | terminal-state invariant becomes false |

The important commercial property is not the toy state machine itself. It is that the engine returns a **shortest replayable causal path** rather than only a generic statement that an invariant failed.

## Bounded no-finding evidence

For `phase-nonnegative`, the engine records:

```text
not_found_within_bound
```

This means only that no negative phase was discovered inside the declared action corpus and `maxDepth=4` model. It is intentionally not labeled `safe`, `secure`, or `passed globally`.

## Inconclusive evidence

For `budget-sensitive-branch`, the result is:

```text
inconclusive
```

This demonstrates a core ContractGraph-QA evidence rule: insufficient coverage cannot silently become a clean result. A real engagement would respond by increasing the search budget, narrowing the model, or adding missing state/action coverage.

## Reproduction

```bash
cgqa engagement-run --config cgqa.engagement.example.toml
```

The capture path is generated directly by Foundry and bound to the reviewed manifest fingerprint.

Independent bundle verification:

```bash
cgqa verify-engagement-bundle \
  dist/CGQA-E-001-run/CGQA-E-001.engagement.zip
```

## What a client receives

For an authorized engagement, the equivalent package contains:

- reviewed scope/manifest;
- explicit modeled state fields, actions, actors, and invariants;
- generated multi-invariant search result;
- engagement coverage summary;
- one finding JSON + Markdown report per violation;
- minimal replayable failing paths;
- authorization/provenance metadata;
- deterministic evidence ZIP;
- independent verification command;
- retest evidence after a fix, when included in scope.

## Interpretation boundary

This example proves the **workflow and evidence semantics**, not the security of an external protocol. Real client conclusions are limited to the explicitly authorized target, modeled state, action corpus, invariants, and search bounds.
