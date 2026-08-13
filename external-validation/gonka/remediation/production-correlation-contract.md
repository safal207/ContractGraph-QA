# Gonka request correlation remediation contract

Status: **recommended production shape; not an upstream patch**

This contract is derived from the reproduced `CGQA-GONKA-001` and
`CGQA-GONKA-002` controls plus the `G-002-COLLISION` storage guard against the
naive proof patch.

## Problem boundary

The verification established three distinct identities that must not be
collapsed:

```text
client_correlation_id
        ↓
internal_request_id
        ↓
execution attempt nonce(s)
```

- `client_correlation_id` is caller-controlled correlation input. It may be
  missing, malformed, or reused across independent calls.
- `internal_request_id` is gateway-generated and uniquely identifies one
  user-facing request execution/race inside Gonka.
- execution nonce(s) identify one or more host attempts belonging to that
  internal request.

A semantic/logical operation can span multiple internal request IDs when a
client retries after an ambiguous timeout. That relationship belongs above the
transport layer and must not be inferred by overwriting request accounting.

## Verified constraints

### C1 — internal request identity stays canonical

`request_accounting.request_id` MUST remain a gateway-controlled unique request
identity. Caller-provided IDs MUST NOT be used directly as the canonical
`request_id` primary-key component.

Reason: the pinned Gonka storage contract keys `request_accounting` by
`(request_id, escrow_id)`. The `G-002-COLLISION` guard demonstrated that two
independent logical operations written with the same caller-controlled request
ID collapse into one request row, retain attempts from both operations, and let
the second completion replace the winner.

### C2 — client correlation is persisted as a separate relation

A safe persistence shape is one-to-many:

```text
request_correlations
----------------------------------------
escrow_id
client_correlation_id
internal_request_id
created_at

PRIMARY KEY (escrow_id, client_correlation_id, internal_request_id)
FOREIGN/semantic target -> request_accounting(internal_request_id, escrow_id)
```

The relation MUST allow one `client_correlation_id` to map to multiple
`internal_request_id` values without mutation or overwrite.

### C3 — generated fallback remains mandatory

If no usable client correlation ID is supplied, Gonka MUST continue generating
an internal request ID. A supplied correlation value does not replace the
internal ID.

### C4 — background completion preserves the internal identity

When inference deliberately detaches from HTTP cancellation so protocol
completion can continue after the client disconnects, the detached context MUST
carry the same `internal_request_id` that was created at the HTTP request
boundary.

This is the mechanism proven by `CGQA-GONKA-001`.

### C5 — timeout lookup is explicit about multiplicity

A client that timed out before receiving the generated internal request ID may
query by its known `client_correlation_id`. The result MUST NOT silently choose
one internal request when multiple matches exist.

Acceptable semantics:

```json
{
  "client_correlation_id": "client-123",
  "matches": [
    {"internal_request_id": "req-a", "escrow_id": "42"},
    {"internal_request_id": "req-b", "escrow_id": "42"}
  ]
}
```

or an equivalent API that returns all mappings.

A single-match convenience resolver is acceptable only when the persisted
relation proves exactly one match.

### C6 — retry is not idempotency

Reusing a `client_correlation_id` MUST NOT by itself suppress execution,
coalesce billing, or imply idempotency. If Gonka later defines an idempotency
contract, it needs a separate explicit key and semantic policy.

## Evidence model

For a timeout/retry operation, verification should be able to reconstruct:

```text
logical_operation_id (CGQA / caller semantic layer)
  ├─ client_correlation_id
  ├─ internal_request_id A
  │    └─ attempt nonce(s) / winner / cost
  └─ internal_request_id B   # retry if one occurred
       └─ attempt nonce(s) / winner / cost
```

Then the reconciliation question is:

```text
all observed execution effects
==
union(attempts for every internal request mapped to the logical operation)
```

with no unexplained nonce, charge, settlement effect, or overwritten lineage.

## Required regression guards

1. **Normal request** — internal accounting addressable by generated internal ID.
2. **Timeout, no retry** — client correlation resolves the completed internal request after the client lost the response.
3. **Repeated client correlation, independent operations** — two internal request rows remain distinct.
4. **Timeout + same correlation retry** — correlation returns both internal requests; neither is overwritten.
5. **Fresh correlation retry** — both request lineages remain independently addressable and can be grouped only by higher-level logical-operation evidence.
6. **Cache hit** — cached alias/correlation keeps source cost lineage without pretending a cached transport request was a new execution.
7. **Restart/recovery** — correlation mappings survive gateway restart with the canonical accounting rows they reference.

## Non-goals

This contract does not claim that Gonka should guarantee HTTP retry idempotency,
exactly-once inference execution, or exactly-once billing merely because a
client correlation value is repeated. Those are separate protocol/product
policies.

## Verification status

- `CGQA-GONKA-001`: reproduced; local identity-propagation proof gives `FAIL -> PASS`.
- `CGQA-GONKA-002`: reproduced; local caller-ID binding proof gives `FAIL -> PASS`.
- `G-002-COLLISION`: direct caller-ID canonicalization rejected as a production remediation because repeated IDs coalesce independent accounting records.

The next executable slice should implement this non-collapsing correlation
shape only inside the pinned local Gonka checkout, prove the regression guards,
and then run the full G-002A/G-002B timeout/retry cost reconciliation.
