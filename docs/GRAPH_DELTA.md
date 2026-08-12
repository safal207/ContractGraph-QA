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

## Change-review interpretation

A newly reachable path is evidence about the declared before/after models and bounded search, not proof that the underlying production system is exploitable. The value of the delta is causal localization:

```text
before: forbidden capability not reachable
              ↓ code / policy / adapter revision
head:   forbidden capability reachable
              ↓
exact shortest capability path + invariant + boundary + impact
```

This gives PR review a stable machine-readable answer to **what security-relevant reachability changed**, while preserving the existing ContractGraph-QA requirement that actual target claims remain tied to authorized evidence and reviewed adapters.
