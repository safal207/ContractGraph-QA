# Direct multi-invariant Foundry capture

ContractGraph-QA v1.3 can classify all declared invariants during one bounded state-space walk and emit the engagement-result contract directly from Foundry.

## Flow

```text
reviewed manifest
      ↓
one bounded BFS session
      ↓
all invariant evaluators
      ↓
violated / not_found_within_bound / inconclusive
      ↓
shortest path per violation
      ↓
engagement-result.json
      ↓
cgqa engagement
      ↓
engagement report + evidence bundle
```

The repository-local regression uses `capture-test/EngagementFixtureCapture.t.sol` and writes only under `results/generated/` through the existing Foundry capture profile.

## Capture command

```bash
export CGQA_ENGAGEMENT_MANIFEST_SHA256="$(python tools/manifest_fingerprint.py manifests/examples/engagement-fixture.json)"
export CGQA_ENGAGEMENT_RESULT_PATH="results/generated/CGQA-E-001.engagement-result.json"
FOUNDRY_PROFILE=capture forge test --match-test test_CaptureMultiInvariantEngagementResult -vvv
```

Then package the result:

```bash
cgqa engagement \
  --manifest manifests/examples/engagement-fixture.json \
  --result results/generated/CGQA-E-001.engagement-result.json \
  --output-dir dist/CGQA-E-001 \
  --bundle dist/CGQA-E-001/CGQA-E-001.engagement.zip
```

## Outcome semantics

For every declared invariant, the search produces exactly one final class:

- `violated`: a reachable violating state was observed; the first breadth-first path is retained as shortest by transition count within the modeled corpus.
- `not_found_within_bound`: the declared bounded search completed and no violating state was observed for that invariant.
- `inconclusive`: the evaluator returned unresolved evidence or the global search could not complete its declared state/transition budget.

`not_found_within_bound` is not a security certification. It is evidence only for the reviewed actors, actions, parameters, state hash, invariant definitions, and declared search bounds.

## Deduplication requirement

`_multiStateHash()` must include every future-relevant modeled value. If two states share a hash while differing in future behavior, pruning can be unsound. Fork adapters should bind the protocol-state digest to scope, chain, block, target, and target code hash through the existing fork adapter provenance helper.

## Authorization boundary

The default fixture is repository-owned and local. Real fork capture remains permitted only for owned systems, explicit client authorization, or assets inside a published safe-harbor/bug-bounty scope. A public contract address or RPC endpoint is not authorization.
