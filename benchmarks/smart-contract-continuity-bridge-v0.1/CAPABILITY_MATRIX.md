# ContractGraph-QA capability matrix

The subject is the offline Smart Contract Continuity Bridge v0.1 candidate and
its pinned LTP v0.1 compatibility boundary. `RUN` is bounded to the stated
synthetic EVM escrow fixture and local repository tests; it is not a production
chain, authorization, finality, or completeness claim.

| Capability | Status | Evidence / bound |
|---|---|---|
| Exact Subject / Artifact Gate | RUN | Both source commits/trees were frozen; later CGQA main movement was recorded, classified, rebased, and revalidated on the exact publication base. |
| Preregistered Verification Plan | RUN | The supplied v0.1 specification and RED-before-GREEN work plan fixed ownership, non-goals, fixtures, and exit contracts before implementation. |
| Orientation Center | RUN | Repository instructions, production adapters, LTP verifier, CLI, and all four normative schemas were reviewed before modeling. |
| Native Mapping / Adapter Review | RUN | Existing RPC capture, EVM receipt adapter, and ExecutionTrace boundaries were reviewed; the bridge reuses rather than replaces them. |
| Safety Invariants | RUN | Fail-closed binding, no invented timeout, no API-as-chain completion, unique attempt ownership, and no input overwrite were tested. |
| Liveness / Reachability | RUN | Missing root and downstream outcomes after deadlines produce the normative missing-outcome finding. |
| Financial Conservation | RUN | Bounded to economic cardinality: two paid attempts and release/dispute terminal conflicts are detected; amounts and balances are not recomputed. |
| Authorization / Capabilities | SKIPPED_WITH_REASON | The intent preserves reviewed sender identity, but v0.1 has no independent authorization-policy source and makes no authorization claim. |
| Replay / Idempotency | RUN | Exact replay is distinguished from conflicting economic outcomes; retry lineage and duplicate attempt ownership are checked. |
| Temporal Lifecycle | RUN | Explicit offsets, deadline behavior, retry order, snapshot time, and LTP temporal findings were exercised. |
| Crash / Recovery | RUN | Bounded lost-response path: RPC timeout / absent receipt on attempt 1, retry attempt 2, one canonical outcome. No process-storage crash claim. |
| Causal / Ancestral Validity | RUN | Parent request, retry parent, trace, attempt, event source, and downstream parent observation links were challenged. |
| Transition Geometry | RUN | Input permutation is byte invariant; one-vs-two attempts and release-vs-dispute outcome combinations were compared. |
| Negative Control | RUN | Transaction-hash request IDs, binding mismatches, API fabrication, duplicate keys, non-finite numbers, unsafe paths, conflicts, gaps, and orphan outcomes are rejected or found. |
| Stateful / Property Search | RUN | Deterministic bounded mutant matrix covers 12 pass, broken, replay, and invalid states; no unbounded/property-fuzz claim. |
| Independent Witness | SKIPPED_WITH_REASON | The fixture is offline and synthetic; one RPC plus its derived adapter trace is not an independent canonical-chain witness. |
| Trace Integrity | RUN | Exact transaction/log/sourceRef binding and a cross-layer trace mismatch mutant were verified. |
| Evidence Type / Readiness | RUN | Bridge report separates supplied, reviewed, derived, and non-claimed facts; hashes and claim boundaries are durable. |
| Counterexample Minimization | RUN | Each broken fixture isolates one primary continuity fault, except the deliberate economic double-effect case. |
| Root-Cause Collapse | NOT_APPLICABLE | No production defect was asserted; the work validates an adapter and compatibility contract. |
| Deterministic Replay | RUN | Export and normative LTP report reproduce byte identically; hashes are pinned. |
| Metamorphic / Round-Trip Verification | RUN | Reordered logical inputs produce identical bytes; installed-wheel export matches the source-tree fixture. |
| Native Regression | RUN | CGQA Python tests and LTP Vitest compatibility tests are native regressions in their owning repositories. |
| Durable Evidence Reopen / Integrity | RUN | The append-only benchmark is hashed by the native durable manifest and reopened with `durable-verify`. |
| Verification Debt | RUN | Independent calldata/sender/nonce decoding, authorization, observation completeness, finality/reorg, and Soroban are explicitly recorded. |
| Active Verification Planning | RUN | v0.1 gates and a separate v0.2 finality issue draft preserve the next verification boundary. |
| Meaning Trajectory | RUN | Intent, attempt, receipt/event, indexer, backend/API, LTP projection, verifier report, and durable evidence remain separate linked stages. |
| Dormant Patterns / Watchpoints | RUN | Receipt disappearance, block replacement, transaction replacement, confirmation drift, and multi-RPC disagreement are preserved as v0.2 watchpoints, not v0.1 findings. |
| Temporal / External Replication | NOT_APPLICABLE | Repeated captures and external chain revalidation are explicit v0.2 non-goals for this offline v0.1 fixture. |
| Forward Remediation | NOT_APPLICABLE | No production defect or state transition was remediated, and no history was rewritten. |

## Completion gate

1. The tested source snapshots and publication base are recorded exactly in
   `exact-subject.json`; at the initial evidence-collection boundary the bridge
   candidate was an uncommitted local working-tree delta on named branches.
   The later main movement and publication revalidation are separate explicit
   transitions.
2. The Orientation Center is resolved for adapter ownership and v0.1 schema
   compatibility, but intentionally unresolved for chain finality and witness
   independence.
3. Safety, bounded liveness, economic cardinality, replay, temporal, recovery,
   ancestry, and trace integrity were checked.
4. Searched forbidden states include orphan/missing/conflicting outcomes,
   duplicate effects, retry/attempt/trace gaps, fabricated API completion, and
   binding mismatches.
5. The adapter could mirror a bad reviewed mapping; exact raw transaction-body
   decoding is therefore recorded as verification debt.
6. Causal ancestry and operation order were challenged with retry, parent,
   downstream, permutation, and conflicting-outcome cases.
7. Negative controls were detected, minimized to bounded fixtures, and replayed.
8. No production defect was claimed, so no production fix/native RED-to-GREEN
   regression was required; the bridge and compatibility tests are native
   integration regressions.
9. Remaining debt is authorization, independent observation completeness,
   transaction-body decoding, finality/reorg/replacement, and Soroban.
10. Counterevidence is the explicit lack of an independent live RPC/chain
    witness; observed confirmations are metadata only.
11. Finality/replacement patterns are preserved in the v0.2 issue draft.
12. The result was temporally rechecked only against repository heads, not a
    changing blockchain subject.
13. Another reviewer can rebuild the exporter, matrix, LTP reports, hashes, and
    durable verification offline from the pinned subjects.
