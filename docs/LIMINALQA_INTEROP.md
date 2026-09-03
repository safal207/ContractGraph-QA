# ContractGraph-QA ↔ LiminalQA interop v0.1

This file-first bridge lets ContractGraph-QA and LiminalQA exchange evidence
without merging their verdict semantics.

## Ownership boundary

| Artifact | Producer and schema owner | Consumer meaning |
|---|---|---|
| `org.contractgraph-qa.liminalqa-evidence.v0.1` | ContractGraph-QA | Exact-subject, bounded invariant evidence |
| `org.liminalqa.cgqa-candidates.v0.1` | LiminalQA | Non-authoritative candidate seeds requiring a fresh CGQA replay |
| LTP continuity result | LTP only | Normative request/outcome continuity verdict |
| Action authorization | The active action gate / operator | Never inferred from either interchange artifact |

The CGQA status vocabulary is preserved exactly:

- `violated`
- `not_found_within_bound`
- `inconclusive`

In particular, `not_found_within_bound` is not exported as `pass` or as proof
that no violation exists.

## Export bounded evidence

```bash
cgqa export-liminalqa \
  --manifest manifests/examples/engagement-fixture.json \
  --result results/examples/CGQA-E-001.engagement-result.json \
  --repository https://github.com/safal207/ContractGraph-QA \
  --commit-sha <full-40-character-commit-sha> \
  --adapter-version 1.3.0 \
  --trace-id trace-CGQA-E-001 \
  --operation-id bounded-search-CGQA-E-001 \
  --attempt-id attempt-001 \
  --valid-at 2026-09-03T10:00:00Z \
  --observed-at 2026-09-03T10:01:00Z \
  --recorded-at 2026-09-03T10:02:00Z \
  --out cgqa-evidence.json
```

The command is offline and deterministic for identical inputs. It rejects
duplicate JSON keys, non-finite numbers, symlink inputs, unsafe output
collisions, partial commit SHAs, missing offsets, and temporal inversions.

The producer-owned JSON Schema is
[`contractgraph_qa/schemas/cgqa-liminalqa-evidence-v0.1.schema.json`](../contractgraph_qa/schemas/cgqa-liminalqa-evidence-v0.1.schema.json).
Runtime validation also checks semantic relationships that plain JSON Schema
cannot express concisely, including status counts and total explored candidates.

## Import LiminalQA candidates

```bash
cgqa import-liminalqa-candidates \
  --input liminal-candidates.json \
  --out cgqa-seed-receipt.json
```

The receipt records `acceptedAs=non_authoritative_seed`,
`mayAuthorizeAction=false`, and `requiresFreshCgqaVerification=true`. Importing
a candidate does not execute it, verify it, turn it into a finding, or authorize
any external action.

The consumer pin records the exact LiminalQA producer commit and candidate
schema SHA-256 in
[`contractgraph_qa/schemas/liminalqa-cgqa-candidates-v0.1.external-contract.json`](../contractgraph_qa/schemas/liminalqa-cgqa-candidates-v0.1.external-contract.json).

## Adapter strategy

The canonical engines remain Python (ContractGraph-QA) and Rust (LiminalQA).
Language packages should be thin wrappers around these versioned JSON profiles,
golden fixtures, and conformance tests rather than independent reimplementations
of verdict logic. Initial packaging targets are Python, TypeScript/Node, Rust,
Go, JVM, and .NET.

Every consumer must pin the producer schema version and digest, reject unknown
critical fields, preserve exact subject and causal identity, and keep network
transport opt-in. The v0.1 reference path performs no network calls.

## Non-claims

This bridge does not establish exhaustive correctness, production security,
request/outcome continuity, or authorization to act. It only provides a strict,
replayable interchange boundary for bounded evidence and candidate hypotheses.
