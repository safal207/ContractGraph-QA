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

## Portable conformance kit

Before publishing a Python, Rust, TypeScript, Elixir, Go, JVM, or .NET adapter,
run the same language-neutral suite:

```bash
cgqa liminalqa-conformance
```

The self-contained kit lives in
[`contractgraph_qa/conformance/liminalqa-v0.1/`](../contractgraph_qa/conformance/liminalqa-v0.1/).
It pins the manifest, suite and result schemas, both producer schemas, both
golden fixtures, and their SHA-256 digests. The reference runner refuses a
rewritten manifest or asset before evaluating any vector.

The 14 vectors cover both interchange directions. Golden fixtures must produce
`VALID_NON_AUTHORIZING`; authority escalation, semantic mismatch, temporal
inversion, unknown fields, weakened independent replay, unsafe identifiers, and
ambiguous duplicate-key JSON must produce `INVALID_BLOCKED`. Every result also
records `sideEffectExecuted=false` and `mayAuthorizeAction=false`.
If an adapter accepts an authorizing or fresh-verification-weakening profile,
the runner records `UNSAFE_ACCEPTED` and fails the suite rather than treating
the runner's outer guard as proof that the adapter blocked it.

Mutation semantics are byte-stable across implementations:

- `identity` preserves the golden fixture bytes exactly.
- `add`, `replace`, and `remove` use the declared RFC 6901 JSON Pointer, then
  emit UTF-8 JSON with recursively sorted object keys, compact separators, and
  one trailing LF.
- `duplicate_root_key` inserts the declared duplicate before the fixture's
  first root member while preserving the remaining fixture bytes.

Every case pins `expectedInputSha256`. A runner must stop before invoking its
adapter if the generated mutation does not match that digest; semantically
similar but byte-different test input is not the pinned v0.1 vector.

Other language implementations should vendor the exact suite bytes, apply the
declared mutation operations, and publish a result with their own adapter name,
version, and implementation language. Passing the suite proves behavior only
for the pinned fixtures and mutations. It does not prove production correctness
or security and never authorizes a target-system action.

## Adapter strategy

The canonical engines remain Python (ContractGraph-QA) and Rust (LiminalQA).
Language packages are thin validators around these versioned JSON profiles,
golden fixtures, and the exact conformance result rather than independent
reimplementations of verdict logic. Native suite runners now exist in Python,
Rust, and Elixir. Consumer SDKs for TypeScript/JavaScript, Go, JVM, and .NET
live under [`sdks/`](../sdks/) and pin every case and producer digest.

See the [SDK release matrix](SDK_RELEASE.md) for package coordinates and the
[five-language quickstarts](i18n/) for application-level examples.

Every consumer must pin the producer schema version and digest, reject unknown
critical fields, preserve exact subject and causal identity, and keep network
transport opt-in. The v0.1 reference path performs no network calls.

## Non-claims

This bridge does not establish exhaustive correctness, production security,
request/outcome continuity, or authorization to act. It only provides a strict,
replayable interchange boundary for bounded evidence and candidate hypotheses.
