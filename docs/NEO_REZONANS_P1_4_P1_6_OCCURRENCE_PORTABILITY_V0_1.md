# Neo Resonance P1-4 — P1-6: Authorization Occurrence Portability

Status: draft conformance contract. No production `/ledger` migration, deployment, external effect, or security authorization is performed by this work.

## Goal

Preserve the identity of one concrete authorization occurrence across the Neo Resonance proof route, prove that concurrent/replayed consumers cannot duplicate it, and emit a durable consumption receipt that binds the exact permission to the exact consumer and action.

Canonical route:

```text
ProofPath
  -> CML
  -> LiminalDB
  -> RINSE
  -> ContractGraph-QA
```

The load-bearing identity rule is:

```text
semantic decision identity
  != authorization occurrence identity
  != consumption fact
```

`decision_ref` identifies the semantic decision. `cites_event_id` identifies the concrete authorization occurrence. A successful consumption is a third fact and receives its own receipt.

## P1-4 — Cross-adapter occurrence binding

The route envelope carries these fields unchanged through every hop:

- `decision_ref`
- `cites_event_id`
- `action_digest`
- `authority_revision`
- `issued_at_epoch`
- `expires_at_epoch`
- `revoked`

Every hop carries the same canonical JSON bytes and SHA-256 fingerprint. The route itself has a separate fingerprint derived from the exact ordered adapter list, the occurrence fingerprint, and all hop fingerprints.

The verifier fails closed if:

- adapter order changes;
- any hop changes the envelope bytes;
- any hop changes the occurrence fingerprint;
- semantic JSON differs from the originating occurrence;
- the route fingerprint no longer matches the exact route.

Thus `cites_event_id` cannot silently disappear, be replaced, or be semantically reconstructed from `decision_ref` later in the route.

## P1-5 — Race and replay matrix

The reference ledger is an in-memory conformance model with no external effects. It models compare-and-set consumption using an occurrence version.

Required outcomes:

| Case | Required result |
| --- | --- |
| expired occurrence | `OCCURRENCE_EXPIRED` |
| revoked occurrence | `OCCURRENCE_REVOKED` |
| not-yet-valid occurrence | `OCCURRENCE_NOT_YET_VALID` |
| changed `action_digest` | `ACTION_MISMATCH` |
| two consumers with the same expected version | exactly one `CONSUMED`, one `CONCURRENT_CONSUMPTION_CONFLICT` |
| retry with the same `request_id` after timeout | `REPLAY_SAME_RECEIPT`; no second consumption |
| new request after successful consumption | `ALREADY_CONSUMED` |
| same `request_id` rebound to another consumer/action/route | `REQUEST_ID_CONFLICT` |

This keeps synchronous implementations free to execute resolution and consumption in one call while preserving the causal distinction between `RESOLVED_ALLOW` and `CONSUMED`.

## P1-6 — ConsumptionReceipt

A successful one-time consumption emits:

```text
ConsumptionReceipt
├─ decision_ref
├─ cites_event_id
├─ consumer_id
├─ action_digest
├─ authority_revision
├─ route_fingerprint
├─ request_id
├─ consumed_at_epoch
├─ result = CONSUMED
└─ receipt_digest
```

`receipt_digest` is SHA-256 over canonical receipt payload bytes. Verification checks both the digest and its binding back to the routed occurrence. A changed consumer, event id, action, authority revision, route, request id, timestamp, or result invalidates the receipt.

## Executable evidence

- reference implementation: `contractgraph_qa/occurrence_portability.py`
- focused unit suite: `tools/tests/test_occurrence_portability.py`
- machine matrix: `tools/occurrence_portability_matrix.py`
- exact-head CI: `.github/workflows/fcrp-p1-4-6-occurrence-portability.yml`

The matrix deliberately records:

```text
side_effects_executed = false
production_ledger_mutated = false
```

The current work is therefore a provider-neutral conformance/reference layer, not a claim that CrewAI, AG2, AutoGen, or another upstream project has adopted the contract.
