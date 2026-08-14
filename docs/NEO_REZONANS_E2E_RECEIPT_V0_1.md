# NEO REZONANS End-to-End Receipt v0.1

`FCRP-SYSTEM-001` proves the canonical cross-repository topology. `FCRP-SYSTEM-002` asks the next question: can one concrete logical operation traverse that topology without losing identity, evidence lineage, causal lineage, or leaking authority?

## Synthetic heartbeat

The first trace is:

`benchmarks/system-e2e/NEO-REZONANS-E2E-001.json`

It is intentionally synthetic and performs no network call, repository mutation, provider action, deployment, wallet operation, fund movement, or other external effect.

The route is fixed by `NEO-REZONANS-SYSTEM-001`:

```text
RESONANCE
  -> CML
  -> FCRP
  -> LiminalOSAI
  -> ContractGraph-QA
  -> ProofPath
  -> LiminalDB
  -> RINSE
  -> RESONANCE feedback
```

## Identity contract

Every stage and transfer must carry the exact same `logicalOperationId`.

The first stage has no causal parent. Every later stage must name the immediately preceding stage as `parentStageId`.

The first stage inherits no evidence. Every later stage must include the immediately preceding `outputEvidenceRef` in its `inputEvidenceRefs`.

This creates three independent continuity checks:

```text
logical identity
causal parent lineage
evidence lineage
```

A break in any one fails the receipt.

## Transfer typing

Every transfer is checked against the canonical system snapshot. A transfer may carry only facts present in that edge's `allowedFacts` and may not carry a declared forbidden inference.

The only authority-bearing edge remains:

```text
LiminalOSAI -> ContractGraph-QA
```

with:

```text
authorityMode = EXPLICIT_CONTRACT_ONLY
authorityTransferred = true
authorizationRef = explicit non-empty reference
```

Every other edge requires:

```text
authorityTransferred = false
authorizationRef = null
```

So proof/provenance, durable state, and reinterpretation can preserve evidence about an authorized execution without preserving live execution authority itself.

## Final reflection boundary

The end state is:

```text
status = REFLECTED_WITH_EVIDENCE
executionAuthorized = false
sourceMutated = false
```

RINSE may return a reinterpretation candidate to RESONANCE, but the feedback is not an accepted action and cannot rewrite the source trace.

## Deterministic receipt

`contractgraph_qa/system_receipt.py` emits:

- snapshot identity and digest;
- trace identity and digest;
- deterministic per-stage digests;
- deterministic per-transfer digests;
- logical/causal/evidence continuity booleans;
- authority transfer/leak counts;
- feedback count;
- source-mutation and external-effect observations;
- final status;
- deterministic receipt digest.

A valid v0.1 receipt requires:

```text
decision = PASS
stageCount = 8
transferCount = 8
identityPreserved = true
causalLineagePreserved = true
evidenceLineagePreserved = true
authorityTransferCount = 1
authorityLeakCount = 0
feedbackCount = 1
sourceMutationObserved = false
externalEffectObserved = false
finalStatus = REFLECTED_WITH_EVIDENCE
```

## FCRP-SYSTEM-002

The First Meaningful Divergence is the gap between a proven static system topology and a proven dynamic logical-operation traversal.

The selected refactor point is the synthetic chain trace plus deterministic receipt validator.

`PASS` still does not authorize mutation. The FCRP case explicitly requires:

```text
mutationAuthorized = false
```

## Nonclaims

This v0.1 heartbeat does not prove runtime interoperability between the repositories. It does not invoke the native runtime of every layer. It does not prove distributed transactionality or exhaustive causal closure. It does not grant authority. It proves the composition contract can represent and reject violations in one deterministic synthetic end-to-end logical operation.
