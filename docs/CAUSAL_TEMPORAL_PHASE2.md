# Causal-Temporal Phase 2

Phase 2 turns temporal evidence continuity into executable, deterministic checks.

## Commands

```bash
python -m contractgraph_qa.causal_temporal_cli witness --input witness.json
python -m contractgraph_qa.causal_temporal_cli debt --input debt.json
python -m contractgraph_qa.causal_temporal_cli watch --input watchpoints.json
python -m contractgraph_qa.causal_temporal_cli replicate --input replication.json
python -m contractgraph_qa.causal_temporal_cli remediate --input remediation.json
```

All commands emit canonical, sorted JSON. `pass` returns exit code `0`; `hold` or `fail` returns `2`.

## Independent Witness

Core rule:

```text
A ledger cannot prove its own completeness.
```

Coverage levels are ordered:

```text
COUNT_COVERAGE
< EVENT_ID_COVERAGE
< SUBJECT_OBJECT_COVERAGE
```

A witness must use a distinct source identity and failure domain. Equal counts do not satisfy exact event coverage, and equal event IDs do not satisfy exact object coverage.

## Verification Debt

Workflow state remains separate from verdict state:

```text
Unverified != Invalid
Deferred != Pruned
Completed != PASS
```

Only `COMPLETED_PASS` or `NOT_APPLICABLE` resolves required work in v0.1. Required unresolved work blocks a balanced Orientation Center.

## Dormant Causal Patterns / Watchpoints

A watchpoint contains explicit activation conditions and a deterministic step window. Step passage alone cannot activate a watchpoint. Foreign-subject evidence is retained as rejected evidence and cannot activate the pattern.

## Replication / Drift

Core rule:

```text
Confirmed_t != Confirmed_t+1
```

Replication requires newer generation evidence and a new evidence hash. External modes additionally require a distinct declared source. Replication batches cannot be used for refitting before scoring.

Drift classifications:

```text
NONE
STRUCTURAL_DRIFT
PERFORMANCE_DRIFT
BOTH
```

A drift signal produces `hold`; it is not model falsehood and does not authorize remediation.

## Forward Remediation

Core rules:

```text
PersistentDrift != AutomaticRollback
ForwardRollback != HistoryRewrite
```

A structurally admissible remediation creates a generation strictly newer than the current generation. `SAFE_ROLLBACK` may use an older generation as its source topology/state, but the resulting generation must still move history forward. The verifier never grants execution or mutation authority.

## Cross-capability route

The regression corpus exercises:

```text
historical evidence
→ independent witness
→ fresh replication
→ drift signal
→ unresolved verification debt
→ Orientation Center INDETERMINATE
→ reviewed remediation proposal
→ forward generation
```

Historical evidence is preserved throughout; no capability rewrites prior validity.
