# Reachability Graph Delta

Reachability Graph Delta compares two strict adversarial reachability models and asks a change-review question:

> Did this revision make a forbidden capability newly reachable, remove a declared control boundary, or eliminate a previously reachable forbidden path?

## CLI

```bash
cgqa reachability-delta \
  --base-model scenarios/adversarial-adapter-fixture-before.json \
  --head-model scenarios/adversarial-adapter-fixture.json
```

The command is deterministic, local, and performs no network or target execution.

## Result semantics

The comparison snapshots every forbidden capability that is reachable within each model's declared `maxDepth`, not only the first selected target. It reports:

- `newlyReachableForbiddenCapabilities`;
- `noLongerReachableForbiddenCapabilities`;
- `removedDeclaredControlBoundaries`;
- `addedDeclaredControlBoundaries`;
- `removedReachableForbiddenBoundaries`;
- the exact shortest `introducedForbiddenPaths` for newly reachable capabilities;
- canonical SHA-256 fingerprints for the before/after models.

Statuses are intentionally narrow:

- `risk_increase_detected` — at least one forbidden capability became newly reachable;
- `control_boundary_change` — no new forbidden capability, but a declared boundary was removed;
- `risk_reduced` — a previously reachable forbidden capability is no longer reachable;
- `no_material_delta` — none of the above occurred.

For CI, `cgqa reachability-delta` exits `10` on `risk_increase_detected` and `0` for the other valid outcomes. A removed boundary remains explicit evidence for review even when it has not yet produced a newly reachable forbidden target.

## Exact prior-path replay after a fix

A generic before/after delta is not enough to prove that the **specific previously failing causal path** has been removed. Use the replay gate after a proposed fix:

```bash
cgqa reachability-replay \
  --prior-model scenarios/adversarial-adapter-fixture.json \
  --fixed-model scenarios/adversarial-adapter-fixture-fixed.json
```

The fixed fixture intentionally preserves capability and transition identity while restoring the assumption guard, so the replay demonstrates a real causal block rather than merely disappearing because identifiers changed.

The command deterministically selects the prior model's shortest target path, then replays that exact ordered transition sequence against the fixed model.

Replay checks are fail-closed:

- the original initial capability must still resolve;
- every prior transition id must still resolve to the same source/target edge;
- the fixed model must still satisfy every transition's current assumption guards;
- the original target must still be classified consistently;
- after exact replay, a fresh bounded search checks for an alternate path to the same forbidden target.

The statuses distinguish a real repair from a path-shaped patch:

- `failing_path_persists` — the exact historical path still reaches the forbidden target;
- `path_eliminated_but_risk_remains` — the exact path is blocked, but another path still reaches the same forbidden target;
- `fix_verified` — the exact path is eliminated and the same forbidden target is no longer reachable within the fixed model and declared bound.

For CI, `cgqa reachability-replay` exits `0` only for `fix_verified`; the two remaining-risk statuses exit `10`.

Representative verification chain:

```text
prior failing model
  ↓ deterministic shortest path
exact historical capability sequence
  ↓ proposed fix
exact transition replay
  ↓
blocked / still traversable
  ↓ fresh search for same forbidden target
alternate path absent / present
  ↓
fix_verified / remaining risk
```

A `fix_verified` result is scoped to the declared models and search bound. It is not a claim that production exploitability is impossible.

## Change-review interpretation

A newly reachable path is evidence about the declared before/after models and bounded search, not proof that the underlying production system is exploitable. The value of the delta is causal localization:

```text
before: forbidden capability not reachable
              ↓ code / policy / adapter revision
head:   forbidden capability reachable
              ↓
exact shortest capability path + invariant + boundary + impact
```

Together, delta + exact replay gives PR review a stable machine-readable cycle:

```text
change introduced forbidden path
→ fix proposed
→ exact prior path replayed
→ alternate path search
→ fixed or remaining risk
```

This preserves the ContractGraph-QA requirement that actual target claims remain tied to authorized evidence and reviewed adapters.
