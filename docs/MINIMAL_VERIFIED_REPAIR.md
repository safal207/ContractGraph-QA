# Minimal Verified Repair Search v0.1

`CGQ-CAUSAL-002 — MINIMAL_VERIFIED_REPAIR_AMONG_REVIEWED_CANDIDATES`

This layer sits on top of causal repair verification. It answers a narrower optimization question:

> Among the candidate repair sets that were actually evaluated, which smallest set repairs every declared target while preserving the supplied comparable evidence?

## Important claim boundary

The verifier does **not** generate patches and does **not** infer what a combination of patches would do from single-patch results.

Every `candidateSet` must have its own reviewed assessment snapshot and evidence hash. This is necessary because repair interactions may be non-linear.

Therefore `minimal_verified_repair` means:

- minimal by number of atomic repairs;
- among the candidate sets explicitly present in the model;
- using the supplied reviewed baseline/candidate evidence;
- with all declared target invariants repaired;
- with declared guards preserved;
- with no new FAIL or weakened PASS in comparable invariant evidence supplied by both snapshots.

It does **not** mean globally minimal over every possible source-code change.

## MilePact example

The included fixture evaluates three atomic repair ideas:

1. `explicit-dispute-cutoff`
2. `resolve-disputed-state`
3. `ui-hide-late-dispute`

Targets:

- `CGQ-RACE-001`
- `CGQ-LIVE-001`

Guards:

- `CGQ-SAFE-001`
- `CGQ-CONS-001`

The seven reviewed combinations produce:

```text
candidate                  RACE   LIVE   result
------------------------------------------------------
cutoff                     PASS   FAIL   partial
resolve                    FAIL   PASS   partial
ui                         FAIL   FAIL   no effect
cutoff + resolve           PASS   PASS   VERIFIED
cutoff + ui                PASS   FAIL   partial
resolve + ui               FAIL   PASS   partial
cutoff + resolve + ui      PASS   PASS   VERIFIED
```

The minimum verified candidate contains two repairs:

```text
explicit-dispute-cutoff
+
resolve-disputed-state
```

The three-repair candidate also works, but it is not minimal among the reviewed candidates.

## CLI

```bash
cgqa-repair-search \
  --model scenarios/milepact-minimal-repair-search.json
```

Expected high-level result:

```json
{
  "status": "pass",
  "classification": "minimal_verified_repair",
  "minimumRepairCount": 2,
  "selectedRepair": {
    "candidateSetId": "cutoff-plus-resolve",
    "repairIds": [
      "explicit-dispute-cutoff",
      "resolve-disputed-state"
    ]
  }
}
```

## Fractal use

The same evidence shape can be reused at different scales as long as the invariant snapshots are explicit:

```text
function repair
    ↓
contract repair
    ↓
protocol repair
    ↓
wallet + contract repair
    ↓
product workflow repair
```

The optimization stays deterministic; only the reviewed evidence feeding it changes.
