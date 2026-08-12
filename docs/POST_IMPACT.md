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

## Independently verified control evidence bundle v3

The post-impact model can now be embedded together with an already verified reachability-aware bundle v2. The v3 control bundle contains:

```text
manifest.json
result.json
reachability-model.json
reachability.json
post-impact-model.json
post-impact.json
finding.json
report.md
base-bundle.json
bundle.json
```

`base-bundle.json` preserves the exact v2 bundle manifest. The v3 verifier reconstructs the original deterministic v2 ZIP, checks its recorded SHA-256, and calls the existing independent `verify_evidence_bundle` path before accepting any post-impact evidence.

It then canonicalizes and re-runs both the reachability model and the post-impact model, checking that:

- the original finding/reachability evidence still verifies independently;
- the post-impact graph is bound to the exact canonical reachability-model SHA-256;
- containment targets the exact selected forbidden capability;
- successful recovery restores only to a declared non-forbidden capability;
- `post-impact.json` is exactly the deterministic result of the bundled model;
- every artifact hash and byte count in bundle v3 matches the embedded bytes.

Build and verify a repository-local v3 bundle with:

```bash
python tools/build_control_bundle.py build \
  --base-bundle dist/CGQA-005/CGQA-005.evidence.zip \
  --post-impact-model scenarios/post-impact-adapter-fixture.json \
  --output dist/CGQA-005/CGQA-005.control.evidence.zip

python tools/build_control_bundle.py verify \
  dist/CGQA-005/CGQA-005.control.evidence.zip
```

Bundle v1 and v2 semantics are unchanged. v3 is an additive control-evidence envelope over a previously verified v2 reachability bundle.

## Determinism and safety boundary

The implementation is stdlib-only, repository-local, deterministic, and does not execute any external target. It models control and recovery evidence; it does not claim that a textual recovery declaration proves a production system was repaired.

The next integration step is to expose this v3 control bundle through the product-facing CLI/report path and then use the same graph vocabulary for PR/patch risk deltas.
