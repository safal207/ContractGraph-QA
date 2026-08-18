# GONKA-ATMAN v0.1 — self-auditing causal verification

Status: experimental profile layered on top of `gonka-verification-v0.1`.

This profile does **not** replace existing Gonka PASS/FAIL/INCONCLUSIVE semantics and does not promote verifier-side uncertainty into a target vulnerability claim.

## Purpose

GONKA-ATMAN adds four explicit observer planes around the existing Gonka evidence model:

```text
A1_LOCAL      request -> dispatch -> execution -> accounting
A2_TEMPORAL   timeout/retry/protocol-time continuity
A3_BINDING    request/accounting/settlement bind to one logical-operation lineage
A4_COHERENCE  verifier generation, freshness, clock model, and evidence coherence
```

## Core lineage

```text
logical_operation_id
        |
        +-- client_correlation_id(s)   # caller controlled; may repeat
        +-- transport_request_id(s)
        +-- execution_nonce(s)
        +-- escrow_id(s)
        +-- accounting_ref(s)
        +-- settlement_ref(s)
```

Two governing relations:

```text
SameCorrelation != SameOperation
SameOperation => ExplainableAttempts
```

A repeated client correlation value is not idempotency and must not collapse independent logical operations. Conversely, all attempts attributed to one logical operation must remain causally reconcilable.

## Generation coherence

Before target-side interpretation, the verifier must establish a coherent execution generation.

```text
source revision
runtime/image fingerprint
runtime generation
evidence generation
protocol generation (when applicable)
```

A mismatch is classified as verifier-side uncertainty:

```text
VERIFIER_GENERATION_MISMATCH
```

It is not a target defect.

## Evidence states

Evidence is not binary. GONKA-ATMAN distinguishes:

```text
ABSENT
PENDING
STALE
SUPERSEDED
REJECTED
CONFIRMED
AMBIGUOUS
```

This prevents a timeout, readable-but-stale row, or superseded artifact from being silently collapsed into "not found".

## Competing hypotheses

For an inconclusive result, the current bounded hypothesis set may include:

```text
IDENTITY_PROPAGATION_FAILURE
ACCOUNTING_LOOKUP_FAILURE
PROTOCOL_TIME_DELAY
STALE_RUNTIME_GENERATION
DUPLICATE_EXECUTION
SETTLEMENT_RECONCILIATION_FAILURE
```

The helper in `contractgraph_qa/gonka_atman.py` chooses the next bounded evidence check with the highest declared information gain over the current hypothesis set.

Generation mismatch always wins first because stale execution invalidates downstream causal interpretation.

## Next Best Evidence

Example input:

```json
{
  "case_id": "G-004",
  "logical_operation_id": "op-42",
  "source_revision": "f040d0a5",
  "runtime_generation": "img-v7",
  "expected_runtime_generation": "img-v7",
  "evidence_generation": "img-v7",
  "hypotheses": [
    "PROTOCOL_TIME_DELAY",
    "SETTLEMENT_RECONCILIATION_FAILURE"
  ],
  "observed_evidence": []
}
```

Expected direction:

```text
WAIT_NEXT_PROTOCOL_DIFF
```

If the runtime fingerprint/generation is stale, the selector instead returns:

```text
COMPARE_RUNTIME_FINGERPRINT
```

## Safety boundary

```text
ATMAN signal != vulnerability claim
Generation mismatch != Gonka failure
High information gain != truth
Selected check != verified finding
INCONCLUSIVE != PASS
```

The existing Gonka replay, invariant, reconciliation, and disclosure rules remain authoritative.

## Schemas

- `gonka-atman-lineage.schema.json`
- `gonka-atman-generation.schema.json`
- `gonka-atman-evidence-state.schema.json`

## Next benchmark

The next meaningful test is held-out and target-blind:

1. freeze the hypothesis/check table before revealing the hidden target;
2. run a new bounded Gonka scenario;
3. compare ordinary evidence collection with ATMAN Next Best Evidence ordering;
4. measure checks-to-resolution and false verifier-side FAILs;
5. only then consider promoting any ATMAN rule into the generic ContractGraph-QA core.
