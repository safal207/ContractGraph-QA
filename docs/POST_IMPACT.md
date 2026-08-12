# Post-Impact Control Graph

The post-impact layer extends Adversarial Reachability beyond the first forbidden capability.

Its question is:

> Once a forbidden capability becomes reachable, where should propagation be contained, how is state restored, and what evidence verifies that containment or recovery actually happened?

## Canonical chain

```text
forbidden capability
        ↓ contained_by
containment node
        ↓ recovered_by
recovery node
        ↓ restores_to
allowed capability

containment / recovery
        ↓ verified_by
verification node
```

This is deliberately separate from the initial capability search. Reachability answers **whether the forbidden capability is reachable**. The post-impact control graph answers **what happened after it became reachable and whether the control/recovery claim is independently representable as evidence**.

## Node semantics

- `ContainmentNode` — a control boundary or isolation action applied to a reached capability. Outcomes: `contained` or `escaped`.
- `RecoveryNode` — a compensating or restoration action linked to containment. Outcomes: `recovered`, `failed`, or `not_attempted`.
- `VerificationNode` — evidence over a containment or recovery node. Outcomes: `verified`, `failed`, or `inconclusive`.

A successful recovery must name the restored capability. Runtime validation rejects a recovery that claims success while restoring to another forbidden capability.

## Repository-owned demo

```bash
python tools/run_post_impact.py \
  --reachability-model scenarios/adversarial-adapter-fixture.json \
  --post-impact-model scenarios/post-impact-adapter-fixture.json
```

The local fixture produces an explicit graph such as:

```text
capability:terminal-state-reachable
        ↓ contained_by
containment:terminal-state-containment
        ↓ recovered_by
recovery:reset-fixture-state
        ↓ restores_to
capability:advance-state-machine

containment:terminal-state-containment
        ↓ verified_by
verification:verify-containment

recovery:reset-fixture-state
        ↓ verified_by
verification:verify-recovery
```

The result is bound to the exact canonical reachability model SHA-256 and the selected forbidden target capability. A post-impact model that only describes an unrelated capability fails closed.

## Determinism and safety boundary

The implementation is stdlib-only, repository-local, deterministic, and does not execute any external target. It models control and recovery evidence; it does not claim that a textual recovery declaration proves a production system was repaired.

The next integration step is to bind this post-impact graph into the existing reachability-aware evidence bundle so an independent verifier can re-run both the forbidden-capability path and its containment/recovery/verification chain.
