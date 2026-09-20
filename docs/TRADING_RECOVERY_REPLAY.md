# Trading Recovery Replay v0.1

This bounded adapter answers one replay-only question:

> After an ambiguous trading action, does the supplied normalized evidence prove enough to permit a controlled retry policy decision?

It composes existing ContractGraph-QA primitives rather than creating a second recovery engine:

- `payment_recovery.py` for ambiguity containment, reconciliation, identity continuity, and retry invariants;
- `economic_cardinality.py` for distinct applied-effect cardinality.

## Verdicts

| State | Retry verdict | Meaning |
|---|---|---|
| `ZERO` | `RETRY_ALLOWED` | Authoritative final failure plus declared complete effect evidence proves zero applied target occurrences. This is a policy verdict only. |
| `ONE` | `BLOCK_ALREADY_APPLIED` | The intended effect is already established. |
| `MULTIPLE` | `BLOCK_DUPLICATE_EFFECT` | More than one distinct applied target occurrence is declared. |
| `UNKNOWN` | `HOLD_*` | Evidence is unresolved, non-authoritative, incomplete, or conflicting. |
| `UNKNOWN` | `BLOCK_RECOVERY_INVARIANT` | The replay trace already violates a fail-closed recovery invariant. |

`executionAuthorized` is always `false`. The module performs no exchange call, order placement, credential use, or live execution.

## Evidence boundary

The economic-cardinality engine is exact over declared normalized events, but source-to-event completeness is external. Therefore the adapter requires an explicit `effectEvidenceComplete` declaration before absence of an applied event can become `ZERO` or a single observed event can become exactly `ONE`.

Likewise, a final reconciliation only releases `UNKNOWN` when `reconciliationAuthoritative` is explicitly declared for the replay scope.

These booleans are assertions supplied by the fixture owner; this module does not independently authenticate external sources or certify production applicability.

## Synthetic example

Run the test suite against:

`benchmarks/trading-recovery-replay-v0.1/cases/failed-zero-retry-allowed.json`

The fixture models:

`authorize → submit → ambiguous → authoritative failed reconciliation → complete zero-effect evidence → RETRY_ALLOWED`

The result still keeps `executionAuthorized=false`.

## Intended bridge

A later cross-repository evidence envelope may feed this replay layer only after the upstream market-data path has produced its own bounded decision state:

`Latency → Staleness → Decision Validity → Recovery Cardinality → Retry Safety`

That future bridge must not reinterpret `CONTINUE_CHECKS` or `RETRY_ALLOWED` as live financial authorization.
