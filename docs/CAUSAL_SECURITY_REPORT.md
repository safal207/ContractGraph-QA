# Causal Security Path in Client Reports

Reachability-aware single-finding reports now render a deterministic **Causal security path** section directly from the independently recomputable `finding.json -> evidence.reachability` block.

The client-facing question is:

> Which broken assumptions made the forbidden capability reachable, which control boundary was crossed, which invariant ties that path to the observed finding, and what exact capability transitions form the shortest bounded path?

## Report shape

For a reachability-bound finding, `report.md` adds a section with:

- reachability status;
- the exact bound invariant;
- canonical reachability-model SHA-256;
- declared broken assumptions;
- the ordered capability chain;
- crossed control boundaries;
- reachability impact;
- a transition table showing `source -> target`, invariant, boundary, and required assumption violations.

Example:

```text
stale-policy-state violated
        ↓
request-settlement
        ↓ authorize-with-stale-policy
forbidden-settlement
        ↓
violated invariant + crossed approval boundary
```

The renderer validates that the human-readable path remains bound to the same finding provenance before it emits Markdown. In particular it rejects:

- a reachability block whose `boundInvariantId` differs from the finding invariant;
- a `boundManifestSha256` that differs from finding provenance;
- a target that is not one of the declared reachability targets;
- a non-contiguous capability transition chain;
- a transition that requires an assumption violation not declared by the reachability result;
- a path that does not contain the bound finding invariant.

## Backward compatibility

Findings without `evidence.reachability` render byte-for-byte using the existing report shape. This preserves checked-in report fixtures and bundle v1 behavior.

Reachability-aware bundle v2 verification already regenerates `report.md` from the recomputed finding. Therefore the new section becomes part of the existing independent semantic verification path automatically: a manually edited causal path in the Markdown report will fail bundle verification.

## Scope boundary

The rendered path is a human-readable view of the declared bounded graph. It does not claim exhaustive proof that no other causal path exists outside the model or search bound.

Post-impact containment/recovery/verification remains represented in control bundle v3. A later client-report slice can render that control graph alongside this pre-impact causal path without weakening the existing v1/v2/v3 verification contracts.
